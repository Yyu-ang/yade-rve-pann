"""Shared, dependency-free checks for academic-project project gates."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import sys
from typing import Iterable

# Deterministic UTF-8 report output regardless of host locale or -E launches
# (hosts commonly run the gates as `python -E script.py`).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError):
        pass

SKILL_DIR = Path(__file__).resolve().parent.parent
VERSION_FILE = SKILL_DIR / "VERSION"
SKILL_VERSION = VERSION_FILE.read_text(encoding="utf-8").strip() if VERSION_FILE.exists() else "2.1.0"

# Template -> target-path mapping (shared by init script and documentation)
TEMPLATE_MAP: dict[str, str] = {
    "core/project_overview.md":    "project_overview.md",
    "core/file_registry.md":       "file_registry.md",
    "core/current_status.md":      "progress/current_status.md",
    "core/progress_log.md":        "progress/progress_log.md",
    "core/milestones.md":          "progress/milestones.md",
    "core/decision_log.md":        "decisions/decision_log.md",
    "core/requirements_log.md":    "requirements/requirements_log.md",
    "core/file_layout.md":         "rules/file_layout.md",
    "core/commit_log.md":          "git/commit_log.md",
    "core/gitignore.md":           ".gitignore",
}

VALID_PROJECT_TYPES = frozenset({
    "paper", "thesis", "review_article", "data_analysis",
    "code_experiment", "code_project", "project_report", "academic_ppt", "dataset_build",
})

# --- MCP write-governance (v2.2.0) -----------------------------------------
MCP_SWITCH_KEY = "mcp_governed_writes"
MCP_LEDGER_NAME = "mcp_write_ledger.md"
MCP_EXEMPT_MARK = "未经 MCP 收口"
# files inside .project-memory that are reconciled even when governed
MEMORY_GOVERNED_RELPATHS = (
    "project_overview.md",
    "progress/current_status.md",
    "progress/progress_log.md",
    "progress/milestones.md",
    "decisions/decision_log.md",
    "requirements/requirements_log.md",
    "rules/file_layout.md",
)


def parse_mcp_governance(agent_text: str) -> tuple[str, list[str]]:
    """Return (on|off, errors). Absent key means off for full v2.1.0 compatibility."""
    errors: list[str] = []
    for line in agent_text.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{MCP_SWITCH_KEY}:"):
            value = stripped.split(":", 1)[1].strip().strip('"').strip("'").lower()
            if value not in ("on", "off"):
                errors.append(f"AGENTS.md {MCP_SWITCH_KEY} 取值非法：{value!r}（只能 on|off）")
                return "off", errors
            return value, errors
    return "off", errors


def governance_files(root: Path, memory_root: Path) -> list[Path]:
    """Governance assets whose writes must be ledger-covered in 'on' projects."""
    files = [root / "PROJECT_DASHBOARD.md", root / "WORKLOG.md", root / "AGENTS.md"]
    files += [memory_root / rel for rel in MEMORY_GOVERNED_RELPATHS]
    workflow = memory_root / "workflow"
    if workflow.is_dir():
        files += sorted(p for p in workflow.rglob("*.md") if p.is_file())
    return files


def _rel_posix(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def _read_ledger(ledger: Path) -> tuple[dict[str, float], dict[str, set[str] | None], float | None]:
    """Parse ledger JSONL. Returns (latest_ts_by_rel, sha_set_by_rel_or_None, baseline_ts).

    baseline_ts = earliest record time: files modified before the first-ever
    governed write are pre-governance artifacts (init skeletons, the manual
    on-switch edit) -> downgrade to a warning, never a hard violation.
    """
    latest: dict[str, float] = {}
    shas: dict[str, set[str] | None] = {}
    baseline: float | None = None
    if not ledger.exists():
        return latest, shas, baseline
    try:
        text = ledger.read_text(encoding="utf-8")
    except OSError:
        return latest, shas, baseline
    for line in text.splitlines():
        if not line.startswith("{"):
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        stamp = float(record.get("t", 0))
        if baseline is None or stamp < baseline:
            baseline = stamp
        sha_map = record.get("sha") if isinstance(record.get("sha"), dict) else None
        for target in record.get("targets", []):
            rel = str(target).replace("\\", "/")
            latest[rel] = max(latest.get(rel, 0.0), stamp)
            if rel not in shas:
                shas[rel] = set()
            if sha_map is None:
                shas[rel] = None  # legacy record without hashes: match any content
            elif shas[rel] is not None and rel in sha_map:
                shas[rel].add(str(sha_map[rel]))
    return latest, shas, baseline


def _file_sha(path: Path) -> str:
    import hashlib
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    except OSError:
        return "?"


def mcp_reconcile(root: Path, memory_root: Path, started_at: float) -> tuple[list[str], list[str]]:
    """Cross-check governance-file mtime + content hash against the MCP ledger
    / WORKLOG exemptions. Threat model: opportunistic AI drift, not ledger
    forgery. Only called for mcp_governed_writes: on.
    """
    errors: list[str] = []
    warnings: list[str] = []
    covered, sha_sets, baseline = _read_ledger(memory_root / MCP_LEDGER_NAME)
    exemption_text = ""
    worklog = root / "WORKLOG.md"
    if worklog.exists():
        try:
            exemption_text = worklog.read_text(encoding="utf-8")
        except OSError:
            exemption_text = ""
    exempt_lines = [ln for ln in exemption_text.splitlines() if MCP_EXEMPT_MARK in ln]
    try:
        exempt_horizon = worklog.stat().st_mtime + 0.5  # 豁免只覆盖登记时刻之前已发生的变更
    except OSError:
        exempt_horizon = 0.0
    exempt_used: list[str] = []
    pre_governance: list[str] = []
    checked = 0
    for path in governance_files(root, memory_root):
        if not path.exists():
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime < started_at - 1.0:
            continue
        checked += 1
        rel = _rel_posix(path, root)
        stamp = covered.get(rel, 0.0)
        if stamp >= started_at - 1.5:
            allowed_shas = sha_sets.get(rel, None)
            if allowed_shas is None or _file_sha(path) in allowed_shas:
                continue
            # 台账覆盖过该路径，但之后内容又被改动：按违规处理
        hist = sha_sets.get(rel)
        if hist and _file_sha(path) in hist:
            # 当前内容与任一历史台账版本逐字相同：copy/迁移/checkout 只刷新 mtime，
            # 不构成未授权内容变更，不判违规（内容哈希一致即无“改”可偷）。
            continue
        if baseline is None or mtime < baseline:
            pre_governance.append(rel)
            continue
        if any(rel in ln or str(path.relative_to(root)) in ln for ln in exempt_lines) and mtime <= exempt_horizon:
            exempt_used.append(rel)
            continue
        if rel == "WORKLOG.md" and exempt_lines:
            # 降级场景：豁免行只能手书写进 WORKLOG，而 WORKLOG 自身也是治理文件——
            # 顺序无法自证，故按"含豁免行即自证"接受为警告级，不判违规（人工抽查兜底）。
            warnings.append(
                "WORKLOG.md 窗口内变更未被台账覆盖，但文件含豁免行：按降级直写自证接受（警告级；"
                "若当时 MCP 其实可用，应改走 worklog_append/human_edit 登记覆盖，并人工抽查本轮 WORKLOG 续写）")
            continue
        if any(rel in ln for ln in exempt_lines):
            errors.append(
                f"MCP 收口违规：{rel} 在该路径的豁免行登记之后又被改动（豁免只覆盖登记前已发生的降级直写）"
                f"；请重新经 MCP 写入或补一条新的「{MCP_EXEMPT_MARK}：{rel}；原因：…」行"
            )
            continue
        errors.append(
            f"MCP 收口违规：{rel} 在任务窗口内变更（或合规写入后又被改动），台账与 WORKLOG 豁免行均无对应记录"
            f"（{MCP_SWITCH_KEY}=on；应经 academic-kanban MCP 工具写入，或补「{MCP_EXEMPT_MARK}：{rel}；原因：…」豁免行）"
        )
    if pre_governance:
        reason = ("台账尚未生成（收口模式自第一笔 MCP 写入起执法；项目初始化或技能升级之后的变更都属此类）"
                  if baseline is None else "早于首条台账基线")
        warnings.append(
            f"{len(pre_governance)} 个治理文件的变更属收口启用前/基线前产物（{reason}），"
            f"本轮不判违规：{'、'.join(pre_governance[:5])}"
            + ("…" if len(pre_governance) > 5 else "")
            + "；请自本任务起经 MCP 工具写入，或由用户手改后经 human_edit 登记"
        )
    if exempt_used:
        warnings.append(
            f"本窗口有 {len(exempt_used)} 个治理文件经豁免直写：{'、'.join(exempt_used)}；"
            "若 MCP 当时其实可用，这属于收口漂移，应收回降级并改走工具"
        )
    if not covered and (exempt_used or errors):
        warnings.append(
            "台账为空：MCP 从未成功写入过本项目。请核验宿主是否真的挂载了 academic-kanban——"
            '用宿主同款解释器跑 `python -E .skill/academic-project/mcp/server.py --doctor --root .` 自检'
        )
    return errors, warnings



@dataclass
class CheckResult:
    root: Path
    mode: str = "unknown"
    memory_root: Path | None = None
    skill_version: str = SKILL_VERSION
    local_skill_version: str | None = None
    mcp_governed: str = "off"
    mcp_reconcile: str = "n/a"  # n/a | covered | violations（finish_check 对账结论，结构化字段）
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    project_skills: list[str] = field(default_factory=list)
    checked_files: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def resolve_root(value: str | None) -> Path:
    return Path(value or ".").expanduser().resolve()


def _read_utf8(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _required_files(memory_root: Path, legacy: bool) -> list[Path]:
    common = [
        memory_root / "project_overview.md",
        memory_root / "file_registry.md",
        memory_root / "progress" / "current_status.md",
        memory_root / "progress" / "progress_log.md",
        memory_root / "progress" / "milestones.md",
        memory_root / "decisions" / "decision_log.md",
    ]
    if legacy:
        common.append(memory_root / "git_summaries" / "commit_log.md")
        return common
    return common + [
        memory_root / "requirements" / "requirements_log.md",
        memory_root / "git" / "commit_log.md",
    ]


def _recommended_files(memory_root: Path, legacy: bool) -> list[Path]:
    """Present -> check UTF-8; absent -> warning, not error."""
    files: list[Path] = []
    if not legacy:
        files.append(memory_root / "rules" / "file_layout.md")
    return files


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def inspect_project(root: Path, require_agent: bool = True) -> CheckResult:
    result = CheckResult(root=root)
    if not root.exists():
        result.errors.append(f"项目根目录不存在：{root}")
        return result
    if not root.is_dir():
        result.errors.append(f"项目根目录不是文件夹：{root}")
        return result

    agents = root / "AGENTS.md"
    legacy_agent = root / "agent.md"
    if agents.exists():
        result.checked_files.append(_relative(agents, root))
        try:
            agent_text = _read_utf8(agents)
        except UnicodeDecodeError as exc:
            result.errors.append(f"AGENTS.md 不是 UTF-8：{exc}")
            agent_text = ""
        if "primary_skill: academic-project" not in agent_text:
            result.errors.append("AGENTS.md 未声明 primary_skill: academic-project")
        if "project_skill_root: .skill" not in agent_text:
            result.warnings.append("AGENTS.md 未明确声明 project_skill_root: .skill")
        result.mcp_governed, gov_errors = parse_mcp_governance(agent_text)
        result.errors.extend(gov_errors)
        import re as _re
        sv = _re.search(r"^skill_version:\s*([0-9.]+)", agent_text, _re.M)
        if sv and sv.group(1) != SKILL_VERSION:
            result.notes.append(
                f"契约声明 skill_version {sv.group(1)} 落后于本地技能 {SKILL_VERSION}"
                "（仅供参考：契约正文未变时无需改动；收口项目为避免台账误判，请保持版本行原样）"
            )
    elif legacy_agent.exists():
        result.checked_files.append(_relative(legacy_agent, root))
        result.warnings.append("检测到旧版 agent.md，建议统一重命名为标准 AGENTS.md")
        try:
            agent_text = _read_utf8(legacy_agent)
        except UnicodeDecodeError as exc:
            result.errors.append(f"agent.md 不是 UTF-8：{exc}")
            agent_text = ""
        if "primary_skill: academic-project" not in agent_text:
            result.errors.append("agent.md 未声明 primary_skill: academic-project")
        result.mcp_governed, gov_errors = parse_mcp_governance(agent_text)
        result.errors.extend(gov_errors)
    elif require_agent:
        result.errors.append("缺少项目根 AGENTS.md；应由 academic-project 初始化流程生成")
    else:
        result.warnings.append("缺少项目根 AGENTS.md（当前以兼容模式继续检查）")

    dashboard = root / "PROJECT_DASHBOARD.md"
    if dashboard.exists():
        result.checked_files.append(_relative(dashboard, root))
        try:
            _read_utf8(dashboard)
        except UnicodeDecodeError as exc:
            result.errors.append(f"PROJECT_DASHBOARD.md 不是 UTF-8：{exc}")
    else:
        result.warnings.append("建议在根目录建立面向用户的进展汇总看板：PROJECT_DASHBOARD.md")

    worklog = root / "WORKLOG.md"
    if worklog.exists():
        result.checked_files.append(_relative(worklog, root))
        try:
            _read_utf8(worklog)
        except UnicodeDecodeError as exc:
            result.errors.append(f"WORKLOG.md 不是 UTF-8：{exc}")
    else:
        result.errors.append("缺少根目录 WORKLOG.md")

    new_root = root / ".project-memory"
    legacy_root = root / ".paper-memory"
    present = [p for p in (new_root, legacy_root) if p.is_dir()]
    if len(present) == 2:
        result.errors.append("同时存在 .project-memory/ 和 .paper-memory/；必须先人工处理记忆根目录冲突")
        return result
    if not present:
        result.errors.append("未发现 .project-memory/ 或 .paper-memory/ 记忆根目录")
        return result

    result.memory_root = present[0]
    result.mode = "legacy" if result.memory_root == legacy_root else "new"
    legacy = result.mode == "legacy"
    result.notes.append(f"memory_mode={result.mode}")
    result.notes.append(f"mcp_governance={result.mcp_governed}")
    if result.mcp_governed == "on" and not (result.memory_root / MCP_LEDGER_NAME).exists():
        result.warnings.append(
            f"{MCP_SWITCH_KEY}=on 但尚无 {MCP_LEDGER_NAME}；首次经 MCP 收口写入后自动生成，属正常初始状态"
        )
    if result.mcp_governed == "off" and (result.memory_root / MCP_LEDGER_NAME).exists():
        try:
            n_records = sum(1 for ln in (result.memory_root / MCP_LEDGER_NAME).read_text(encoding="utf-8").splitlines()
                            if ln.startswith("{"))
        except OSError:
            n_records = -1
        if n_records != 0:
            result.warnings.append(
                "开关为 off 但存在收口台账"
                + (f"（{n_records} 条记录）" if n_records > 0 else "")
                + "：本项目曾处于收口模式后又降级；若非用户有意为之，请核对 AGENTS.md 该键是否被违规改写"
            )

    closed_marker = result.memory_root / "project_closed.json"
    if closed_marker.exists():
        result.checked_files.append(_relative(closed_marker, root))
        try:
            closeout_data = json.loads(_read_utf8(closed_marker))
            archive_rel = closeout_data.get("archive_record")
            if not isinstance(archive_rel, str) or not archive_rel.strip():
                result.errors.append("项目封存标记缺少 archive_record")
            else:
                archive_path = (result.memory_root / archive_rel).resolve()
                if not archive_path.is_relative_to(result.memory_root.resolve()):
                    result.errors.append("项目封存凭证路径越出记忆根目录")
                elif not archive_path.is_file():
                    result.errors.append(f"项目封存凭证不存在：{archive_rel}")
                else:
                    _read_utf8(archive_path)
                    result.checked_files.append(_relative(archive_path, root))
            for dirname in ("for_user", "for_worker", "for_manager"):
                staged = root / dirname
                if staged.exists():
                    result.errors.append(f"项目已封存但临时交付目录仍存在：{dirname}/")
            result.notes.append("project_state=closed")
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            result.errors.append(f"项目封存标记无效：{exc}")
    else:
        result.notes.append("project_state=active")
        for dirname in ("for_user", "for_worker", "for_manager"):
            staged = root / dirname
            if staged.is_symlink() or not staged.is_dir():
                result.errors.append(f"活动项目缺少临时交付目录或目录类型错误：{dirname}/")

    for path in _required_files(result.memory_root, legacy):
        rel = _relative(path, root)
        if not path.exists():
            result.errors.append(f"缺少核心文件：{rel}")
            continue
        result.checked_files.append(rel)
        try:
            _read_utf8(path)
        except UnicodeDecodeError as exc:
            result.errors.append(f"文件不是 UTF-8：{rel}：{exc}")

    if not legacy and (result.memory_root / "skills").exists():
        result.warnings.append("新结构仍存在 .project-memory/skills/；项目级技能应迁入根目录 .skill/，不要建立竞争目录")

    project_skill_root = root / ".skill"
    if project_skill_root.exists():
        for child in sorted(project_skill_root.iterdir(), key=lambda p: p.name.lower()):
            if child.is_dir() and (child / "SKILL.md").exists():
                result.project_skills.append(child.name)
        local_skill_dir = project_skill_root / "academic-project"
        local_skill = local_skill_dir / "SKILL.md"
        local_version_file = local_skill_dir / "VERSION"
        if local_skill.exists():
            local_ver = None
            if local_version_file.exists():
                try:
                    local_ver = _read_utf8(local_version_file).strip()
                except Exception:
                    pass
            if not local_ver:
                try:
                    for line in _read_utf8(local_skill).splitlines():
                        if line.startswith("version:"):
                            local_ver = line.split(":", 1)[1].strip().strip('"').strip("'")
                            break
                except Exception:
                    pass
            result.local_skill_version = local_ver or "1.0.0"
            result.notes.append(f"local_skill_version=v{result.local_skill_version}")
            if result.local_skill_version != SKILL_VERSION:
                result.warnings.append(
                    f"本地固化技能版本 (v{result.local_skill_version}) 落后于当前最新版本 (v{SKILL_VERSION})。"
                    f"建议运行无损更新：python <academic-project>/scripts/project_init.py --root . --update-skill"
                )
        else:
            result.warnings.append("项目 .skill/ 目录下未固化 academic-project 技能本体；建议复制到 .skill/academic-project/ 供 AI 本地调用")
    else:
        result.warnings.append("项目根目录没有 .skill/；初始化新项目时应创建并固化 academic-project")

    if legacy and (result.memory_root / "wikiskill").exists():
        result.notes.append("legacy_wikiskill=present")

    # --- recommended (non-fatal) files ---
    for path in _recommended_files(result.memory_root, legacy):
        rel = _relative(path, root)
        if not path.exists():
            result.warnings.append(f"建议存在但缺失：{rel}")
            continue
        result.checked_files.append(rel)
        try:
            _read_utf8(path)
        except UnicodeDecodeError as exc:
            result.errors.append(f"文件不是 UTF-8：{rel}：{exc}")

    # --- workflow consistency ---
    overview_path = result.memory_root / "project_overview.md"
    declared_types: set[str] = set()
    if overview_path.exists():
        try:
            overview_text = _read_utf8(overview_path)
            for line in overview_text.splitlines():
                if line.startswith("- **已激活类型**"):
                    declared_types = {
                        t for t in VALID_PROJECT_TYPES if t in line
                    }
                    break
        except UnicodeDecodeError:
            pass
        if not declared_types:
            result.warnings.append(
                "project_overview.md 缺「- **已激活类型**：…」行，类型一致性检查退化为"
                "仅按 workflow/ 目录枚举；请经 memory_update 补写该行")

    workflow_dir = result.memory_root / "workflow"
    actual_types: set[str] = set()
    if workflow_dir.is_dir():
        for child in workflow_dir.iterdir():
            if child.is_dir() and child.name in VALID_PROJECT_TYPES:
                actual_types.add(child.name)

    if declared_types and actual_types:
        missing_dirs = declared_types - actual_types
        extra_dirs = actual_types - declared_types
        if missing_dirs:
            result.warnings.append(
                f"project_overview.md 声明了类型 {missing_dirs} 但 workflow/ 下无对应目录"
            )
        if extra_dirs:
            result.warnings.append(
                f"workflow/ 下存在目录 {extra_dirs} 但 project_overview.md 未声明"
            )
    elif actual_types and not declared_types:
        result.notes.append(f"workflow_types={','.join(sorted(actual_types))}")

    if not workflow_dir.exists():
        result.warnings.append("未发现 workflow/ 目录")

    return result


def format_result(result: CheckResult, title: str, as_json: bool = False) -> str:
    import json

    payload = {
        "title": title,
        "ok": result.ok,
        "root": str(result.root),
        "skill_version": result.skill_version,
        "local_skill_version": result.local_skill_version,
        "mode": result.mode,
        "mcp_governance": result.mcp_governed,
        "mcp_reconcile": result.mcp_reconcile,
        "memory_root": str(result.memory_root) if result.memory_root else None,
        "errors": result.errors,
        "warnings": result.warnings,
        "notes": result.notes,
        "project_skills": result.project_skills,
        "checked_files": result.checked_files,
    }
    if as_json:
        return json.dumps(payload, ensure_ascii=False, indent=2)
    local_ver_display = "未固化"
    if result.local_skill_version:
        is_latest = result.local_skill_version == result.skill_version
        local_ver_display = f"v{result.local_skill_version} {'(最新)' if is_latest else '(可更新)'}"
    lines = [
        title,
        f"项目根：{result.root}",
        f"规范最新版本：v{result.skill_version}",
        f"本地技能版本：{local_ver_display}",
        f"记忆模式：{result.mode}",
    ]
    if result.memory_root:
        lines.append(f"记忆根：{result.memory_root}")
    if result.project_skills:
        lines.append("项目级技能：" + ", ".join(result.project_skills))
    else:
        lines.append("项目级技能：无（.skill 可为空）")
    if result.errors:
        lines.append("错误：")
        lines.extend(f"- {item}" for item in result.errors)
    if result.warnings:
        lines.append("警告：")
        lines.extend(f"- {item}" for item in result.warnings)
    if result.notes:
        lines.append("说明：")
        lines.extend(f"- {item}" for item in result.notes)
    lines.append("结果：" + ("PASS" if result.ok else "FAIL"))
    return "\n".join(lines)
