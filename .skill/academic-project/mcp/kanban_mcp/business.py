"""Governance write tools: content validation, window folding, ledger recording.

Every public function performs one audited write for an academic-project
governance asset. Raises ValueError/KanbanError on validation failure (nothing
is written), and appends a ledger record on success. ``actor`` is the free-form
identity reported by the caller (recorded only; the launch-time ``role`` on the
Project is the authority).
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path, PurePosixPath

from . import fsops, limits
from .fsops import now_stamp, read_text, today, write_text
from .limits import check_len, check_date as _check_date
from .markdown_util import (append_lines_to_archive, entry_insert_point, is_data_row,
                            parse_row, quarter_from_date, section_range, table_row)
from .model import KanbanError, Project

_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fff][A-Za-z0-9_.\u4e00-\u9fff-]*$")


def entry_insert_point_safe(lines: list[str]) -> int:  # noqa: F811 (kept for tests)
    return entry_insert_point(lines)


def _strip_template_placeholders(lines: list[str], markers: tuple[str, ...]) -> list[str]:
    """Drop an untouched template placeholder entry (still containing YYYY-MM-DD) on first real write."""
    starts = [i for i, ln in enumerate(lines) if ln.startswith("## [")]
    if not starts:
        return lines
    last = starts[-1]
    block = "\n".join(lines[last:])
    if "YYYY-MM-DD" in block and any(m in block for m in markers):
        return lines[:last]
    return lines


_MAINTAINER_ONLY = frozenset({
    "dashboard_update", "worklog_append", "status_update", "progress_append",
    "requirement_append", "decision_append", "milestone_append", "memory_update",
    "contract_update", "human_edit", "dispatch_write", "review_write",
    "accept_deliverable", "workflow_update",
})


def _guard(p: Project, tool: str) -> None:
    """Business-layer role check: defense-in-depth for callers that import the
    library directly instead of going through the role-mounted MCP session."""
    if tool in _MAINTAINER_ONLY and p.role != "maintainer":
        raise KanbanError(f"{tool} 属维护者工具组：当前进程以 {p.role} 角色启动，无权调用")

def _record(p: Project, tool: str, actor: str, targets: list, note: str = "") -> None:
    rels = []
    for t in targets:
        try:
            rels.append(p.rel_of(Path(t)))
        except ValueError:
            rels.append(Project.posix(str(t)))
    fsops.ledger_append(p.root, p.memory_root, tool=tool, role=p.role,
                        actor=actor, targets=rels, note=note)


def _result(p: Project, written: list, folded: list, **extra) -> dict:
    out = {"ok": True, "written": [p.rel_of(Path(w)) for w in written], "folded": folded}
    out.update(extra)
    return out


def _seg(value: str, label: str) -> str:
    value = (value or "").strip()
    if not value or not _SAFE_SEGMENT.match(value) or ".." in value:
        raise KanbanError(f"{label} 非法（只允许字母数字中文与-_.，且不得含路径分隔）：{value!r}")
    return value


# ---------------------------------------------------------------- WORKLOG

def worklog_append(p: Project, actor: str, title: str, goal: str, actions: str,
                   evidence: str, blockers: str = "无", next_step: str = "",
                   related: str = "") -> dict:
    _guard(p, "worklog_append")
    title = check_len(title, "worklog_title", "工作日志条目标题")
    for name, val in (("用户目标", goal), ("执行动作", actions), ("验证证据", evidence)):
        if not (val or "").strip():
            raise KanbanError(f"{name} 不能为空")
    block = (
        f"\n## [{now_stamp()}] {title}\n\n"
        f"- **用户目标**：{goal.strip()}\n"
        f"- **执行动作**：{actions.strip()}\n"
        f"- **验证证据**：{evidence.strip()}\n"
        f"- **阻塞/未知**：{(blockers or '无').strip()}\n"
        f"- **下一步**：{(next_step or '待填').strip()}\n"
        f"- **关联文件**：{(related or '无').strip()}\n"
    )
    path = p.root / "WORKLOG.md"
    if not path.exists():
        raise KanbanError("WORKLOG.md 不存在；请先由初始化流程建立")
    fsops.append_text(path, block)
    _record(p, "worklog_append", actor, [path], title)
    return _result(p, [path], [])


# --------------------------------------------------------------- DASHBOARD

def _memory_milestone_row(p: Project, date: str, text: str, note: str = "-") -> Path:
    """向记忆层 progress/milestones.md 追加一行（沉淀用，由调用方的台账记录覆盖）。"""
    from .fsops import read_text as _rt
    ms = p.memory_root / "progress" / "milestones.md"
    if ms.exists():
        lines = [ln for ln in _rt(ms).splitlines() if "| YYYY-MM-DD |" not in ln]
    else:
        lines = ["# 里程碑", "> 达成时同步在记忆层 git 打 tag（milestone/<名称>）", "",
                 "| 日期 | 里程碑 | 状态 | git tag | 备注 |", "|------|--------|------|---------|------|"]
    lines.append(table_row([date, text, "✅ 达成", "-", note]))
    write_text(ms, "\n".join(lines))
    return ms


def _dashboard_path(p: Project) -> Path:
    path = p.root / "PROJECT_DASHBOARD.md"
    if not path.exists():
        raise KanbanError("PROJECT_DASHBOARD.md 不存在")
    return path


def dashboard_update(p: Project, actor: str, section: str, entry_json: str) -> dict:
    _guard(p, "dashboard_update")
    import json
    try:
        entry = json.loads(entry_json) if entry_json else {}
    except json.JSONDecodeError as exc:
        raise KanbanError(f"entry_json 不是合法 JSON：{exc}") from exc
    handlers = {
        "snapshot": _dash_snapshot, "requirement": _dash_requirement,
        "deliverable": _dash_deliverable, "milestone": _dash_milestone,
        "pending": _dash_pending,
    }
    if section not in handlers:
        raise KanbanError(f"未知 section：{section}；可选 {sorted(handlers)}")
    unknown = set(entry) - limits.DASHBOARD_ENTRY_KEYS[section]
    if unknown:
        raise KanbanError(f"section={section} 不接受字段 {sorted(unknown)}；"
                          f"可用字段：{sorted(limits.DASHBOARD_ENTRY_KEYS[section])}")
    folded, detail = handlers[section](p, entry)
    _record(p, "dashboard_update", actor, [_dashboard_path(p)] + [f for f, _t in folded],
            f"{section}: {str(entry)[:80]}")
    return _result(p, [_dashboard_path(p)], [f for f, _t in folded], section=section, detail=detail)


def _dash_snapshot(p: Project, entry: dict) -> tuple[list, str]:
    stage = check_len(entry.get("stage", ""), "stage", "当前阶段")
    status = (entry.get("status") or "").strip().lower()
    if status not in limits.SNAPSHOT_STATUS:
        raise KanbanError(f"status 须为 {sorted(limits.SNAPSHOT_STATUS)}（green/yellow/red）")
    direction = (entry.get("direction") or "").strip()
    if direction:
        direction = check_len(direction, "direction", "核心攻关方向")
    path = _dashboard_path(p)
    lines = read_text(path).splitlines()
    for idx, line in enumerate(lines):
        if "**更新时间**" in line:
            new = (f"> **更新时间**：{now_stamp()} | **当前阶段**：{stage} | "
                   f"**项目状态**：{limits.SNAPSHOT_STATUS[status]}"
                   + (f" | **核心方向**：{direction}" if direction else ""))
            lines[idx] = new
            break
    else:
        raise KanbanError("看板顶部状态快照行（含 **更新时间**）缺失")
    write_text(path, "\n".join(lines))
    return [], stage


def _artifact_exists(p: Project, artifact: str, label: str) -> None:
    if artifact.startswith(("http://", "https://", "doi:")):
        return
    try:
        if not p.resolve_in_root(artifact).exists():
            raise KanbanError(f"{label} 指向的路径不存在：{artifact}（已交付物料必须真实可查）")
    except KanbanError:
        raise
    except ValueError:
        raise KanbanError(f"{label} 路径非法：{artifact}")


def _dash_requirement(p: Project, entry: dict) -> tuple[list, str]:
    demand = check_len(entry.get("demand", ""), "demand", "用户需求")
    value = check_len(entry.get("value", ""), "value", "成果价值与自测说明")
    status = (entry.get("status") or "").strip()
    if status in limits.STATUS_EMOJI:
        status = limits.STATUS_EMOJI[status]
    elif not re.match(r"^[🟢🟡🔴]", status):
        raise KanbanError("status 须为 delivered/in_progress/blocked 或以 🟢🟡🔴 开头")
    date = (entry.get("date") or today()).strip()
    if entry.get("date"):
        date = _check_date(date, "提出时间")
    artifact = (entry.get("path") or "-").strip()
    if status.startswith("🟢"):
        if artifact == "-":
            raise KanbanError("已交付需求必须给出交付物料路径")
        _artifact_exists(p, artifact, "交付物料路径")
    path = _dashboard_path(p)
    lines = [ln for ln in read_text(path).splitlines()
             if not any(h in ln for h in ("path/to/artifact", "[用户明确提出的具体任务", "[进行中的下一项任务"))]
    start, end = section_range(lines, "1.")
    row = table_row([date, demand, status, f"`{artifact}`" if artifact != "-" else "-", value])
    block_end = max([i for i in range(start, end) if lines[i].lstrip().startswith("|")], default=None)
    if block_end is None:
        raise KanbanError("需求矩阵未找到表头结构")

    def _rows(upto):
        return [i for i in range(start, upto)
                if is_data_row(lines[i]) and "提出时间" not in lines[i]]

    data_idx = _rows(end)
    match = entry.get("update_matching") or {}
    key = match.get("demand_contains", "")
    replaced = False
    if key:
        for i in data_idx:
            if key in lines[i]:
                lines[i] = row
                replaced = True
                break
    if not replaced:
        lines.insert(block_end + 1, row)  # 表尾追加，避开表头/分隔行
    folded: list[tuple[str, str]] = []
    data_idx = _rows(block_end + 3)
    while len(data_idx) > limits.DASHBOARD_WINDOWS["requirements"]:
        # 沉淀最旧的已交付行；本次刚写入/更新的行（表尾最后一行）永不作为受害者
        candidates = data_idx[:-1] if len(data_idx) > 1 else []
        victim = next((i for i in candidates if lines[i].count("🟢") >= 1), None)
        if victim is None:
            break  # 全部进行中：保留超窗，等待用户决策，不悄悄丢弃
        moved = lines.pop(victim)
        cells = parse_row(moved)
        _log_requirement_row(p, cells[0], cells[1], f"看板沉淀：{cells[-1]}")
        folded.append((str(p.memory_root / "requirements" / "requirements_log.md"), cells[1]))
        data_idx = _rows(block_end + 3)
    write_text(path, "\n".join(lines))
    return folded, demand


def _dash_deliverable(p: Project, entry: dict) -> tuple[list, str]:
    category = (entry.get("category") or "").strip()
    if category not in limits.DELIVERABLE_CATEGORIES:
        raise KanbanError(f"category 须为 {sorted(limits.DELIVERABLE_CATEGORIES)}")
    name = (entry.get("name") or "").strip()
    target = (entry.get("path") or "").strip()
    if "\n" in name or "\n" in target:
        raise KanbanError("name/path 不允许换行")
    note = check_len(entry.get("note", ""), "deliverable_note", "一句话说明")
    if not name or not target:
        raise KanbanError("name 与 path 不能为空")
    _artifact_exists(p, target, "成果物料路径")
    path = _dashboard_path(p)
    lines = [ln for ln in read_text(path).splitlines()
             if "(path/to/file)" not in ln]  # 陈列架模板示例行：首写即清除
    start, end = section_range(lines, "2.")
    header = limits.DELIVERABLE_CATEGORIES[category]
    # 分类组缺失时按需建组（老看板升含新分类后的首个条目自动落头），不跨类
    try:
        hpos = next(i for i in range(start, end) if header in lines[i])
    except StopIteration:
        anchors = [i for i in range(start, end) if lines[i].startswith("- **")]
        hpos = (anchors[-1] + 1) if anchors else start + len(_section_preamble(lines[start:end]))
        lines.insert(hpos, f"- **{header}**：")
        end = section_range(lines, "2.")[1]
    # 组边界：本类标题行之后，直到下一个 '- **' 分类标题或小节结束（不跨类！）
    gend = next((i for i in range(hpos + 1, end) if lines[i].startswith("- **")), end)
    group = [i for i in range(hpos + 1, gend) if lines[i].lstrip().startswith("- [")]
    dropped = ""
    if len(group) >= limits.DASHBOARD_WINDOWS["deliverables_per_category"]:
        victim = group[0]
        dropped = lines.pop(victim).strip()
        gend -= 1
        group = [i for i in range(hpos + 1, gend) if lines[i].lstrip().startswith("- [")]
    insert_at = (group[-1] + 1) if group else hpos + 1
    lines.insert(insert_at, f"  - [{name}]({target})：{note}")
    write_text(path, "\n".join(lines))
    return [], (f"新增 {name}；顶替移除：{dropped}" if dropped else f"新增 {name}")


def _dash_milestone(p: Project, entry: dict) -> tuple[list, str]:
    event = check_len(entry.get("event", ""), "milestone", "里程碑事件")
    date = (entry.get("date") or today()).strip()
    if entry.get("date"):
        date = _check_date(date, "日期")
    path = _dashboard_path(p)
    lines = [ln for ln in read_text(path).splitlines()
             if not (ln.startswith("- **YYYY-MM-DD**"))]  # 清除模板示例节点
    start, end = section_range(lines, "3.")
    data = [i for i in range(start, end) if lines[i].startswith("- **")]
    insert_at = (data[-1] + 1) if data else start + len(_section_preamble(lines[start:end]))
    lines.insert(insert_at, f"- **{date}**：{event}")
    dropped = ""
    sunk: list[tuple[str, str]] = []
    end = section_range(lines, "3.")[1]
    data = [i for i in range(start, end) if lines[i].startswith("- **")]
    while len(data) > limits.DASHBOARD_WINDOWS["milestones"]:
        dropped = lines.pop(data[0]).strip()
        cells = re.match(r"- \*\*(\d{4}-\d{2}-\d{2})\*\*：(.*)", dropped)
        if cells:  # 溢出沉淀进记忆层里程碑表，不静默丢弃
            ms = _memory_milestone_row(p, cells.group(1), cells.group(2), note="看板沉淀")
            sunk.append((str(ms), cells.group(2)))
        data = [i for i in range(start, section_range(lines, "3.")[1]) if lines[i].startswith("- **")]
    write_text(path, "\n".join(lines))
    return sunk, (f"新增 {date} {event}；溢出沉淀记忆层：{dropped}" if dropped else f"新增 {date} {event}")


def _dash_pending(p: Project, entry: dict) -> tuple[list, str]:
    action = (entry.get("action") or "add").strip()
    path = _dashboard_path(p)
    lines = [ln for ln in read_text(path).splitlines()
             if "[待确认事项简述" not in ln]  # 待决策模板示例行首写即清除
    start, end = section_range(lines, "4.")
    data = [i for i in range(start, end) if lines[i].lstrip().startswith(("- [", "- ✔", "* ["))]
    if action == "replace":
        items = entry.get("items") or []
        if not isinstance(items, list):
            raise KanbanError("items 须为字符串列表")
        if len(items) > limits.DASHBOARD_WINDOWS["pending"]:
            raise KanbanError(f"待决策事项最多 {limits.DASHBOARD_WINDOWS['pending']} 条")
        new_lines = [f"- [ ] {check_len(i, 'pending', '待决策事项')}" for i in items] or ["- 暂无"]
        lines[start:end] = _section_preamble(lines[start:end]) + new_lines
    elif action == "add":
        text = check_len(entry.get("text", ""), "pending", "待决策事项")
        for i in reversed([i for i in data if "[x]" in lines[i]]):
            lines.pop(i)
        end = section_range(lines, "4.")[1]
        empty = [i for i in range(start, end) if lines[i].strip() in ("- 暂无", "-暂无", "暂无")]
        for i in reversed(empty):
            lines.pop(i)
        end = section_range(lines, "4.")[1]
        live = [i for i in range(start, end) if lines[i].lstrip().startswith(("- [", "* [")) and "- [x]" not in lines[i]]
        if len(live) >= limits.DASHBOARD_WINDOWS["pending"]:
            raise KanbanError("待决策事项已满 3 条；请先用 replace 整理，不自动丢弃用户议题")
        insert_at = (live[-1] + 1) if live else start + len(_section_preamble(lines[start:end]))
        lines.insert(insert_at, f"- [ ] {text}")
    else:
        raise KanbanError("action 须为 add 或 replace")
    write_text(path, "\n".join(lines))
    return [], action


def _section_preamble(body: list[str]) -> list[str]:
    keep = []
    for line in body:
        if line.startswith(">") or not line.strip():
            keep.append(line)
        else:
            break
    while keep and not keep[-1].strip():
        keep.pop()
    return keep


# ---------------------------------------------------------- REQUIREMENTS

def _log_requirement_row(p: Project, date: str, demand: str, completion: str) -> None:
    req = p.memory_root / "requirements" / "requirements_log.md"
    lines = read_text(req).splitlines()
    data = [i for i in range(len(lines)) if is_data_row(lines[i])]
    lines.append(table_row([date, demand, completion]))
    write_text(req, "\n".join(lines))


def requirement_append(p: Project, actor: str, demand: str, completion: str,
                       date: str = "") -> dict:
    _guard(p, "requirement_append")
    demand = check_len(demand, "req_detail", "用户要求")
    completion = check_len(completion, "req_detail", "AI 完成情况")
    date = (date or today()).strip()
    date = _check_date(date, "日期")
    req = p.memory_root / "requirements" / "requirements_log.md"
    lines = [ln for ln in read_text(req).splitlines() if "[对话指示的具体要求]" not in ln]
    lines.append(table_row([date, demand, completion]))

    def _data(upto):
        return [i for i in range(upto) if is_data_row(lines[i]) and "用户要求" not in lines[i]]

    data = _data(len(lines))
    folded: list[str] = []
    while len(data) > limits.REQUIREMENTS_LOG_KEEP:
        victim = lines.pop(data[0])
        cells = parse_row(victim)
        q = quarter_from_date(cells[0] if cells else "")
        arch = p.memory_root / "archive" / f"requirements_log_{q}.md"
        append_lines_to_archive(arch, f"# 用户要求日志归档 {q}\n\n| 日期 | 用户要求 | AI 完成情况 |\n|------|----------|-------------|\n", [victim])
        folded.append(Project.posix(arch))
        data = _data(len(lines))
    write_text(req, "\n".join(lines))
    _record(p, "requirement_append", actor, [req] + folded[:1], demand[:60])
    return _result(p, [req], folded)


# ---------------------------------------------------------- PROGRESS LOG

def progress_append(p: Project, actor: str, title: str, task: str, done: list[str],
                    changed: list[str], next_step: str) -> dict:
    _guard(p, "progress_append")
    title = check_len(title, "progress_title", "进展条目标题")
    if not done:
        raise KanbanError("完成要点不能为空")
    block = (
        f"## [{now_stamp()}] {title}\n"
        f"- **任务**：{task.strip()}\n"
        "- **完成**：\n" + "".join(f"  - {d}\n" for d in done) +
        f"- **变更文件**：{', '.join(changed) if changed else '无'}\n"
        f"- **下一步**：{(next_step or '待填').strip()}\n"
    )
    prog = p.memory_root / "progress" / "progress_log.md"
    lines = _strip_template_placeholders(read_text(prog).splitlines(), ("本次工作标题",))
    pos = entry_insert_point(lines)
    new_lines = block.rstrip("\n").splitlines()
    lines[pos:pos] = ["", *new_lines, ""]
    folded = _fold_progress_entries(p, prog, lines)
    write_text(prog, "\n".join(lines))
    _record(p, "progress_append", actor, [prog] + folded, title)
    return _result(p, [prog], [Project.posix(f) for f in folded])


def _fold_progress_entries(p: Project, prog: Path, lines: list[str]) -> list[Path]:
    starts = [i for i, ln in enumerate(lines) if ln.startswith("## [")]
    folded: list[Path] = []
    while len(starts) > limits.PROGRESS_LOG_KEEP:
        cut = starts[limits.PROGRESS_LOG_KEEP]
        block = lines[cut:]
        lines[cut:] = []
        q = quarter_from_date(block[0])
        arch = p.memory_root / "archive" / f"progress_log_{q}.md"
        append_lines_to_archive(arch, f"# 工作进展日志归档 {q}\n\n", [ln for ln in block if ln.strip()])
        folded.append(arch)
        starts = [i for i, ln in enumerate(lines) if ln.startswith("## [")]
    return folded


# ---------------------------------------------------------- STATUS / ADR

def milestone_append(p: Project, actor: str, milestone: str, status: str = "✅ 达成",
                     git_tag: str = "-", date: str = "", note: str = "-") -> dict:
    _guard(p, "milestone_append")
    if not (milestone or "").strip():
        raise KanbanError("里程碑名称不能为空")
    date = _check_date((date or today()).strip(), "日期")
    ms = p.memory_root / "progress" / "milestones.md"
    if ms.exists():
        lines = [ln for ln in read_text(ms).splitlines() if "| YYYY-MM-DD |" not in ln]
    else:
        lines = ["# 里程碑", "> 达成时同步在记忆层 git 打 tag（milestone/<名称>）", "",
                 "| 日期 | 里程碑 | 状态 | git tag | 备注 |", "|------|--------|------|---------|------|"]
    lines.append(table_row([(date or today()).strip(), milestone.strip(), status.strip(),
                            git_tag.strip() or "-", note.strip() or "-"]))
    write_text(ms, "\n".join(lines))
    _record(p, "milestone_append", actor, [ms], milestone[:40])
    return _result(p, [ms], [])


def memory_update(p: Project, actor: str, relpath: str, content: str) -> dict:
    _guard(p, "memory_update")
    """整档重写白名单内的记忆根文件（project_overview / rules/file_layout 等低频档案）。"""
    allowed = {
        "project_overview.md", "file_registry.md", "rules/file_layout.md",
    }
    rel_path = PurePosixPath(str(relpath).replace("\\", "/"))
    if rel_path.is_absolute() or ".." in rel_path.parts:
        raise KanbanError(f"路径非法：{relpath}")
    rel = rel_path.as_posix()
    # 容忍记忆根前缀写法（.project-memory/project_overview.md 与 project_overview.md 等价）
    mem_prefix = p.posix(p.memory_root.relative_to(p.root)) + "/"
    if rel.startswith(mem_prefix):
        rel = rel[len(mem_prefix):]
    if rel not in allowed:
        raise KanbanError(f"memory_update 仅允许 {sorted(allowed)}（也可带 {mem_prefix} 前缀）；"
                          "其余记忆文件请用专用工具")
    if not (content or "").strip():
        raise KanbanError("content 不能为空")
    target = p.resolve_in_root(f"{p.posix(p.memory_root.relative_to(p.root))}/{rel}")
    if not target.parent.is_dir():
        raise KanbanError(f"目标目录不存在：{target.parent}")
    write_text(target, content)
    _record(p, "memory_update", actor, [target], rel)
    return _result(p, [target], [])


def status_update(p: Project, actor: str, stage: str, in_progress: list[str],
                  todos: list[str], blockers: list[str], next_step: str) -> dict:
    _guard(p, "status_update")
    if not (stage or "").strip():
        raise KanbanError("stage 不能为空")
    body = [
        "# 当前状态快照",
        f"> 更新于：{now_stamp()}",
        "",
        f"**阶段**：{stage.strip()}",
        "",
        "**进行中**：",
    ]
    body += [f"- [ ] {t}" for t in in_progress] or ["- 无"]
    body += ["", "**待办**（按优先级）："]
    body += [f"{i}. [ ] {t}" for i, t in enumerate(todos, 1)] or ["1. [ ] 无"]
    body += ["", "**阻塞/风险**："]
    body += [f"- {b}" for b in blockers] or ['- 无']
    body += ["", f"**下一步建议**：{(next_step or '待填').strip()}", ""]
    st = p.memory_root / "progress" / "current_status.md"
    write_text(st, "\n".join(body))
    _record(p, "status_update", actor, [st], stage[:40])
    return _result(p, [st], [])


def decision_append(p: Project, actor: str, title: str, context: str, decision: str,
                    alternatives: str, evidence_level: str, date: str = "") -> dict:
    _guard(p, "decision_append")
    title = check_len(title, "decision_title", "决策标题")
    for name, val in (("背景", context), ("决定", decision), ("备选与理由", alternatives), ("证据等级", evidence_level)):
        if not (val or "").strip():
            raise KanbanError(f"{name} 不能为空")
    block = [
        f"## [{_check_date((date or today()).strip(), '日期')}] {title}",
        f"- **背景**：{context.strip()}",
        f"- **决定**：{decision.strip()}",
        f"- **备选与理由**：{alternatives.strip()}",
        f"- **证据等级**：{evidence_level.strip()}",
    ]
    dec = p.memory_root / "decisions" / "decision_log.md"
    lines = _strip_template_placeholders(read_text(dec).splitlines(), ("决策标题",))
    pos = entry_insert_point(lines)
    lines[pos:pos] = [*block, ""]
    write_text(dec, "\n".join(lines))
    _record(p, "decision_append", actor, [dec], title)
    return _result(p, [dec], [])


# ---------------------------------------------------------- CONTRACT

def human_edit(p: Project, actor: str, paths: list[str], reason: str) -> dict:
    _guard(p, "human_edit")
    """维护者确认某些治理文件的窗口内变更出自人工编辑，登记 WORKLOG 对账豁免行。

    AI 不得为自己绕过收口调用本工具；paths 必须都是真实存在的治理文件。
    """
    if not paths:
        raise KanbanError("paths 不能为空")
    if not (reason or "").strip():
        raise KanbanError("reason 不能为空：须写明是谁、为什么手工改了这些文件")
    from .fsops import governance_relpaths
    allowed = governance_relpaths(p.root, p.memory_root)
    rels = []
    for raw in paths:
        rel = Project.posix(str(raw).replace("\\", "/")).removeprefix("./")
        if rel in ("AGENTS.md", "WORKLOG.md"):
            raise KanbanError(
                f"{rel} 不允许经 human_edit 豁免：契约键的降级只能由用户亲手编辑，"
                "降级直写的 WORKLOG 豁免行也必须由人或维护者亲手书写（自带警告），"
                "否则本工具可被用来洗白任意绕道直写")
        if rel not in allowed:
            raise KanbanError(f"仅治理文件可登记人工豁免：{rel} 不在收口范围")
        if not p.resolve_in_root(rel).exists():
            raise KanbanError(f"文件不存在：{rel}")
        rels.append(rel)
    line = (f"\n- 未经 MCP 收口：{', '.join(rels)}；原因：人工编辑，维护者「{actor or '未署名'}」"
            f"核验背书；{reason.strip()}\n")
    worklog = p.root / "WORKLOG.md"
    fsops.append_text(worklog, line)
    _record(p, "human_edit", actor, [worklog], f"manual: {', '.join(rels)}")
    return _result(p, [worklog], [], exempted=rels)


def contract_update(p: Project, actor: str, action: str, key: str = "", value: str = "",
                    old: str = "", new: str = "") -> dict:
    _guard(p, "contract_update")
    agents = p.root / "AGENTS.md"
    text = read_text(agents)
    if action == "set_frontmatter":
        allowed = {"mcp_governed_writes", "memory_root", "legacy_memory_root"}
        if key not in allowed:
            raise KanbanError(f"仅允许维护契约字段 {sorted(allowed)}；其余正文用 replace")
        if key == "mcp_governed_writes":
            if value not in ("on", "off"):
                raise KanbanError("mcp_governed_writes 只能为 on 或 off")
            if value == "off" and p.governance() == "off":
                raise KanbanError("mcp_governed_writes 已是 off")
            if value == "off":
                raise KanbanError(
                    "收口开关不允许经受管工具关闭（否则被约束者可以自行解除约束）。"
                    "确需降级：请用户本人直接编辑 AGENTS.md 该行并告知维护者，门禁将按 off 跳过对账。"
                )
        else:
            if not re.fullmatch(r"\.?[A-Za-z0-9_\u4e00-\u9fff][A-Za-z0-9_.\u4e00-\u9fff-]*", value or ""):
                raise KanbanError(f"{key} 只能是单个目录名（不允许路径分隔符或遍历）：{value!r}")
            if ".." in value or "/" in value or "\\" in value:
                raise KanbanError(f"{key} 只能是单个目录名（不允许路径分隔符或遍历）：{value!r}")
        pattern = re.compile(rf"^{re.escape(key)}:\s*\S+.*$", re.M)
        if not pattern.search(text):
            # insert into frontmatter block after first '---' line
            lines = text.splitlines()
            if len(lines) > 1 and lines[0].strip() == "---":
                lines.insert(1, f"{key}: {value}")
                text = "\n".join(lines)
            else:
                raise KanbanError("AGENTS.md 无 frontmatter，无法插入字段")
        else:
            text = pattern.sub(f"{key}: {value}", text, count=1)
    elif action == "replace":
        if not old:
            raise KanbanError("replace 需提供 old 精确文本")
        count = text.count(old)
        if count != 1:
            raise KanbanError(f"old 文本出现 {count} 次，须唯一命中才能替换")
        text = text.replace(old, new)
    else:
        raise KanbanError("action 须为 set_frontmatter 或 replace")
    # 文本级锁：无论 set_frontmatter 还是 replace，结果文本不得把 on 变成 off
    def _switch_of(txt: str) -> str:
        m = re.search(r"^mcp_governed_writes:\s*(\S+)", txt, re.M)
        return (m.group(1).strip("\"'").lower() if m else "off")
    if _switch_of(text) == "off" and p.governance() == "on":
        raise KanbanError("收口开关不允许经受管工具由 on 改为 off（含 replace 路径）。"
                          "确需降级：请用户本人直接编辑 AGENTS.md。")
    write_text(agents, text)
    _record(p, "contract_update", actor, [agents], f"{action}:{key or old[:30]}")
    return _result(p, [agents], [])


# ------------------------------------------------- HANDOFF / REVIEW

def _check_ids(task_id: str, worker_id: str) -> tuple[str, str]:
    return _seg(task_id, "task_id"), _seg(worker_id, "worker_id")


def handoff_write(p: Project, actor: str, task_id: str, worker_id: str, status: str,
                  goal: str, acceptance: list[str], done: list[str],
                  deliverables: list[str], selftest_cmd: str, selftest_result: str,
                  unfinished: list[str], blocker: str, next_steps: str,
                  wip_path: str = "", verify_items: list[str] | None = None) -> dict:
    status = (status or "").strip().upper()
    if status not in limits.HANDOFF_STATUSES:
        raise KanbanError(f"status 须为 {list(limits.HANDOFF_STATUSES)}")
    task_id, worker_id = _check_ids(task_id, worker_id)
    if not (goal or "").strip() or not acceptance:
        raise KanbanError("goal 与 acceptance 不能为空")
    deliverables = [d for d in (deliverables or []) if d.strip()]
    for d in deliverables:
        if "for_user" in Project.posix(d):
            raise KanbanError("交付物不得指向 for_user/：用户交付区仅管理员可写")
    if status == "COMPLETED":
        if not deliverables:
            raise KanbanError("COMPLETED 必须列出成果路径")
        missing = [d for d in deliverables if not p.resolve_in_root(d).exists()]
        if missing:
            raise KanbanError(f"COMPLETED 成果路径不存在：{missing}")
        if not (selftest_cmd or selftest_result or "").strip():
            raise KanbanError("COMPLETED 必须附自测命令/核验动作及结果")
    else:
        if deliverables:
            raise KanbanError("INCOMPLETE_HANDOFF 不得携带交付物；只交接不交付")
        deliverables = []
    content = "\n".join([
        "---",
        "schema: academic-project-worker-handoff/v1",
        f'task_id: "{task_id}"',
        f'worker_id: "{worker_id}"',
        f"worker_status: {status}",
        "---",
        "",
        "# Worker Handoff",
        "",
        "## 指派目标与验收标准",
        f"- 目标：{goal.strip()}",
        "- 验收标准：",
        *[f"  - {a}" for a in acceptance],
        "",
        "## 状态与已完成项",
        f"- **工作者状态**：`{status}`",
        *([f"- 已完成项：{d}" for d in done] or ["- 已完成项：无"]),
        "",
        "## 交付物",
        *([f"- {d}" for d in deliverables] or ["- 无（仅交接）"]),
        "",
        "## 自测与证据",
        f"- 命令/核验动作：{(selftest_cmd or '未运行').strip()}",
        f"- 实际结果：{(selftest_result or '未运行').strip()}",
        "",
        "## 未完成项、阻塞与接续步骤",
        *([f"- 未完成项：{u}" for u in unfinished] or ["- 未完成项：无"]),
        f"- 阻塞：{(blocker or '无').strip()}",
        f"- 接续步骤：{(next_steps or '无').strip()}",
        f"- WIP 路径：{(wip_path or '无').strip()}（过程材料，不作为交付物）",
        "",
        "## 需管理员核验",
        *([f"- {v}" for v in (verify_items or [])] or ["- 无"]),
        "",
    ])
    target_dir = p.root / "for_manager" / task_id / worker_id
    target_dir.mkdir(parents=True, exist_ok=True)
    handoff = target_dir / "handoff.md"
    version = 1
    if handoff.exists():
        while (target_dir / f"handoff_v{version}.md").exists():
            version += 1
        handoff = target_dir / f"handoff_v{version}.md"
        content = content.replace("# Worker Handoff", f"# Worker Handoff (v{version})", 1)
    write_text(handoff, content)
    _record(p, "handoff_write", actor, [handoff], f"{task_id}/{worker_id} {status}")
    return _result(p, [handoff], [])


def review_write(p: Project, actor: str, task_id: str, worker_id: str, manager_id: str,
                 decision: str, worker_status: str, standards: list[str],
                 artifact_check: str, selftest_review: str, next_step: str = "无",
                 keep_wip: str = "无", cleanup: str = "无", final_path: str = "待最终交付") -> dict:
    _guard(p, "review_write")
    if decision not in limits.REVIEW_DECISIONS:
        raise KanbanError(f"decision 须为 {list(limits.REVIEW_DECISIONS)}")
    task_id, worker_id = _check_ids(task_id, worker_id)
    manager_id = _seg(manager_id, "manager_id")
    if worker_status not in limits.HANDOFF_STATUSES:
        raise KanbanError(f"worker_status 须为 {list(limits.HANDOFF_STATUSES)}")
    if decision == "ACCEPTED" and worker_status != "COMPLETED":
        raise KanbanError("仅 COMPLETED 交接可判 ACCEPTED；未完成交接走 HANDOFF_ACCEPTED")
    if not standards:
        raise KanbanError("必须逐条记录核验的验收标准")
    content = "\n".join([
        "---",
        "schema: academic-project-manager-review/v1",
        f'task_id: "{task_id}"',
        f'worker_id: "{worker_id}"',
        f'manager_id: "{manager_id}"',
        f"manager_status: {decision}",
        "---",
        "",
        "# Manager Review",
        "",
        "## 核验结论",
        f"- **工作者状态**：`{worker_status}`",
        f"- **管理员决定**：`{decision}`",
        "- **核验的验收标准**：",
        *[f"  - {s}" for s in standards],
        f"- **产物路径与内容核验**：{artifact_check.strip()}",
        f"- **自测复核**：{selftest_review.strip()}",
        "",
        "## 接续与清理",
        f"- **接续责任/下一步**：{next_step.strip()}",
        f"- **保留的 WIP/复现材料**：{keep_wip.strip()}",
        f"- **清理的过时产物**：{cleanup.strip()}",
        f"- **最终用户交付路径**：{final_path.strip()}",
        "",
    ])
    target = p.root / "for_manager" / task_id / worker_id / "review.md"
    write_text(target, content)
    _record(p, "review_write", actor, [target], f"{task_id}/{worker_id} {decision}")
    return _result(p, [target], [])


def dispatch_write(p: Project, actor: str, task_id: str, title: str,
                   goal: str, assigned_role: str = "Worker", assignee: str = "pending",
                   parent_goal: str = "", inputs: list[str] | None = None,
                   write_scope: list[str] | None = None,
                   acceptance: list[str] | None = None,
                   depends_on: list[str] | None = None,
                   priority: str = "HIGH", status: str = "DISPATCHED",
                   notes: str = "") -> dict:
    _guard(p, "dispatch_write")
    task_id = _seg(task_id, "task_id")
    title = (title or "").strip()
    goal = (goal or "").strip()
    if not title or not goal:
        raise KanbanError("title 与 goal 不能为空")
    if not acceptance:
        raise KanbanError("必须提供至少一条验收标准 (acceptance)")
    priority = (priority or "HIGH").strip().upper()
    if priority not in limits.DISPATCH_PRIORITIES:
        raise KanbanError(f"priority 须为 {list(limits.DISPATCH_PRIORITIES)}")
    status = (status or "DISPATCHED").strip().upper()
    if status not in limits.DISPATCH_STATUSES:
        raise KanbanError(f"status 须为 {list(limits.DISPATCH_STATUSES)}")

    target_dir = p.root / "for_manager" / task_id
    target_dir.mkdir(parents=True, exist_ok=True)
    dispatch_file = target_dir / "dispatch.md"

    inputs = inputs or []
    write_scope = write_scope or [f"for_worker/{task_id}/{assignee if assignee != 'pending' else '[worker-id]'}/"]
    depends_on = depends_on or []

    content = "\n".join([
        "---",
        "schema: academic-project-task-dispatch/v1",
        f'task_id: "{task_id}"',
        f'title: "{title}"',
        f'parent_goal: "{parent_goal.strip()}"',
        f'assigned_role: "{assigned_role.strip()}"',
        f'assignee: "{assignee.strip()}"',
        f"priority: {priority}",
        f"dispatch_status: {status}",
        f'created_at: "{today()}"',
        f"depends_on: {json.dumps(depends_on, ensure_ascii=False)}",
        "---",
        "",
        f"# Task Dispatch: {task_id} - {title}",
        "",
        "## 1. 任务背景与核心目标",
        f"- **任务目标**：{goal}",
        f"- **业务背景**：{(parent_goal or '按指派目标推进').strip()}",
        "",
        "## 2. 输入依赖与先决条件",
        "- **前置依赖任务**：" + (", ".join(depends_on) if depends_on else "无"),
        "- **输入物料路径**：",
        *([f"  - {inp}" for inp in inputs] or ["  - 无特定前置输入物料"]),
        "",
        "## 3. 写入范围与交付路径约束",
        f"- **工作者专属沙盒**：`for_worker/{task_id}/{assignee if assignee != 'pending' else '[worker-id]'}/`",
        "- **正式文件直写授权**：",
        *([f"  - {ws}" for ws in write_scope] or ["  - 无（仅限沙盒内写入）"]),
        "",
        "## 4. 验收标准与完成定义 (DOD Checklist)",
        *[f"- [ ] {acc}" for acc in acceptance],
        "",
        "## 5. 接续与历史上下文",
        f"- {(notes or '无').strip()}",
        "",
    ])
    write_text(dispatch_file, content)
    _record(p, "dispatch_write", actor, [dispatch_file], f"{task_id} {title} -> {assignee}")
    return _result(p, [dispatch_file], [])


# ------------------------------------------------- ACCEPT / WORKFLOW

def accept_deliverable(p: Project, actor: str, src: str, dst: str, note: str = "") -> dict:
    _guard(p, "accept_deliverable")
    src_path = p.resolve_in_root(src)
    dst_path = p.resolve_in_root(dst)
    rel_src = p.rel_of(src_path)
    if not (rel_src.startswith("for_user/") or rel_src.startswith("for_worker/")):
        raise KanbanError("accept_deliverable 只受理 for_user/ 或 for_worker/ 内的文件")
    if not src_path.is_file():
        raise KanbanError(f"源文件不存在：{rel_src}")
    dst_rel = p.rel_of(dst_path)
    for guard in ("for_user", "for_worker", "for_manager", ".project-memory", ".paper-memory", ".skill"):
        if dst_rel == guard or dst_rel.startswith(guard + "/"):
            raise KanbanError(f"正式交付目标不得位于 {guard}/：{dst_rel}")
    if dst_path.exists():
        raise KanbanError(f"目标已存在，拒绝覆盖：{dst_rel}（如需覆盖请先人工处理）")
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src_path), str(dst_path))
    _record(p, "accept_deliverable", actor, [dst_path], f"{rel_src} -> {dst_rel}；{note}")
    return _result(p, [dst_path], [], moved_from=rel_src)


def _active_workflow_types(p) -> set:
    """本项目可写 workflow 的类型集合：project_overview.md「已激活类型」声明 ∪ workflow/ 已有目录。"""
    from .model import KanbanError as KE
    valid = {"paper", "thesis", "review_article", "data_analysis", "code_experiment",
             "code_project", "project_report", "academic_ppt", "dataset_build"}
    declared: set = set()
    ov = p.memory_root / "project_overview.md"
    if ov.exists():
        for ln in fsops.read_text(ov).splitlines():
            if ln.startswith("- **已激活类型**"):
                declared = {t for t in valid if t in ln}
                break
    wf = p.memory_root / "workflow"
    actual = ({c.name for c in wf.iterdir() if c.is_dir() and c.name in valid}
              if wf.exists() else set())
    allowed = declared | actual
    if not allowed:
        raise KE("无法确定本项目已激活类型：请先 memory_update 在 project_overview.md"
                 " 写入「- **已激活类型**：<type>」行")
    return allowed


def workflow_update(p: Project, actor: str, project_type: str, filename: str,
                    action: str, title: str, content: str) -> dict:
    _guard(p, "workflow_update")
    from .model import KanbanError as KE
    valid = {"paper", "thesis", "review_article", "data_analysis", "code_experiment",
             "code_project", "project_report", "academic_ppt", "dataset_build"}
    if project_type not in valid:
        raise KE(f"未知项目类型：{project_type}")
    allowed = _active_workflow_types(p)
    if project_type not in allowed:
        raise KE(f"workflow_update 仅允许本项目已激活类型 {sorted(allowed)}；"
                 f"{project_type} 未激活。确需新增该类型：先 memory_update 更新 "
                 "project_overview.md 的「已激活类型」行（模板文件可由用户从技能包复制实例化）")
    if not filename.endswith(".md") or "/" in filename or "\\" in filename or ".." in filename:
        raise KE("filename 须为 workflow 目录内的纯文件名 .md")
    target = p.memory_root / "workflow" / project_type / filename
    if action == "append":
        block = f"\n## [{now_stamp()}] {title.strip()}\n\n{content.strip()}\n"
        if target.exists():
            fsops.append_text(target, block)
        else:
            write_text(target, f"# {project_type} 工作流跟踪：{filename}\n{block}")
    elif action == "rewrite":
        body = content.strip()
        head = "" if body.startswith("#") else f"# {title}\n\n"  # 避免双一级标题
        write_text(target, head + body + "\n")
    else:
        raise KE("action 须为 append 或 rewrite")
    _record(p, "workflow_update", actor, [target], f"{project_type}/{filename} {action}")
    return _result(p, [target], [])
