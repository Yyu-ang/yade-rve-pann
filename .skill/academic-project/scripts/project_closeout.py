#!/usr/bin/env python3
"""Safely close an academic project and reclaim its temporary AI work areas.

Dry-run is the default. Final artifacts are moved only to project-relative
approved destinations listed in for_manager/closeout_manifest.json. Handoffs
are archived, worker outputs are archived or explicitly discarded, and the
three staging directories are removed only after the complete manifest passes
validation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from project_check_common import SKILL_VERSION, inspect_project, resolve_root
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from project_check_common import SKILL_VERSION, inspect_project, resolve_root

PROCESS_DIRS = ("for_user", "for_worker", "for_manager")
DEFAULT_MANIFEST = "for_manager/closeout_manifest.json"
SCHEMA = "academic-project-closeout/v1"
WORKER_STATUSES = {"COMPLETED", "INCOMPLETE_HANDOFF"}
MANAGER_STATUSES = {"ACCEPTED", "HANDOFF_ACCEPTED", "CANCELLED"}


class CloseoutError(Exception):
    """A fail-closed closeout validation or execution error."""


def _safe_relative(root: Path, value: Any, label: str) -> tuple[Path, Path]:
    if not isinstance(value, str) or not value.strip():
        raise CloseoutError(f"{label} 必须是非空相对路径")
    normalized = value.strip().replace("\\", "/")
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or not pure.parts or ":" in pure.parts[0]:
        raise CloseoutError(f"{label} 必须是项目根目录内的相对路径：{value}")
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise CloseoutError(f"{label} 含空路径段或路径穿越：{value}")
    relative = Path(*pure.parts)
    root_resolved = root.resolve()
    target = (root / relative).resolve(strict=False)
    if not target.is_relative_to(root_resolved):
        raise CloseoutError(f"{label} 越出项目根目录：{value}")
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise CloseoutError(f"{label} 路径经过符号链接，拒绝处理：{value}")
    return relative, target


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _first_part(relative: Path) -> str:
    return relative.parts[0].casefold() if relative.parts else ""


def _is_under(relative: Path, directory: str) -> bool:
    return _first_part(relative) == directory.casefold() and len(relative.parts) > 1


def _read_status(path: Path, key: str, expected: str) -> None:
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*:\s*([A-Z_]+)\b", text)
    if not match or match.group(1) != expected:
        actual = match.group(1) if match else "missing"
        raise CloseoutError(f"{path.name} 的 {key}={actual}，与清单中的 {expected} 不一致")


def _inventory(root: Path, manifest_relative: Path) -> tuple[dict[str, Path], list[str]]:
    files: dict[str, Path] = {}
    placeholders: list[str] = []
    for dirname in PROCESS_DIRS:
        folder = root / dirname
        if folder.is_symlink() or not folder.is_dir():
            raise CloseoutError(f"临时目录缺失或不是普通目录：{dirname}/")
        for path in sorted(folder.rglob("*")):
            if path.is_symlink():
                raise CloseoutError(f"临时目录含符号链接，拒绝递归清理：{path.relative_to(root)}")
            if path.is_dir():
                continue
            if not path.is_file():
                raise CloseoutError(f"发现非普通文件：{path.relative_to(root)}")
            relative = path.relative_to(root)
            key = relative.as_posix()
            if relative == manifest_relative:
                continue
            if path.name == ".gitkeep" and path.stat().st_size == 0:
                placeholders.append(key)
                continue
            files[key] = path
    return files, placeholders


def _expect_source(root: Path, raw: Any, label: str, required_dir: str,
                   inventory: dict[str, Path], claimed: set[str]) -> tuple[str, Path]:
    relative, absolute = _safe_relative(root, raw, label)
    key = relative.as_posix()
    if not _is_under(relative, required_dir):
        raise CloseoutError(f"{label} 必须位于 {required_dir}/：{key}")
    if key not in inventory:
        raise CloseoutError(f"{label} 不在待清理文件清单中或文件不存在：{key}")
    if key in claimed:
        raise CloseoutError(f"同一源文件被重复处置：{key}")
    claimed.add(key)
    return key, absolute


def _expect_destination(root: Path, raw: Any, label: str,
                        allowed_prefix: tuple[str, ...] | None = None) -> tuple[str, Path]:
    relative, absolute = _safe_relative(root, raw, label)
    key = relative.as_posix()
    if _first_part(relative) in {name.casefold() for name in PROCESS_DIRS}:
        raise CloseoutError(f"{label} 不得位于临时交付目录：{key}")
    if _first_part(relative) in {".project-memory", ".paper-memory", ".skill"} and not allowed_prefix:
        raise CloseoutError(f"{label} 不得放入项目记忆或技能目录：{key}")
    if allowed_prefix:
        prefix = tuple(part.casefold() for part in allowed_prefix)
        actual = tuple(part.casefold() for part in relative.parts[:len(prefix)])
        if actual != prefix:
            raise CloseoutError(f"{label} 必须位于 {'/'.join(allowed_prefix)}/：{key}")
    if absolute.exists():
        raise CloseoutError(f"目标已存在，拒绝覆盖：{key}")
    return key, absolute


def _validate_manifest(root: Path, memory_root: Path, manifest_path: Path,
                       manifest_relative: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("schema") != SCHEMA:
        raise CloseoutError(f"manifest schema 必须为 {SCHEMA}")
    if manifest.get("workers_quiesced") is not True:
        raise CloseoutError("workers_quiesced 必须为 true；封存前须确认所有工作者已停止写入")
    summary = manifest.get("manager_summary")
    if not isinstance(summary, str) or not summary.strip() or summary.startswith("["):
        raise CloseoutError("manager_summary 必须填写最终核验结论，不能保留模板占位符")

    workers = manifest.get("worker_statuses", [])
    deliverables = manifest.get("deliverables", [])
    handoffs = manifest.get("handoffs", [])
    work_archive = manifest.get("work_archive", [])
    work_discard = manifest.get("work_discard", [])
    user_discard = manifest.get("user_discard", [])
    for field_name, value in (("worker_statuses", workers), ("deliverables", deliverables),
                              ("handoffs", handoffs), ("work_archive", work_archive),
                              ("work_discard", work_discard), ("user_discard", user_discard)):
        if not isinstance(value, list):
            raise CloseoutError(f"{field_name} 必须是数组")

    inventory, placeholders = _inventory(root, manifest_relative)
    claimed: set[str] = set()
    plan: list[dict[str, Any]] = []
    destination_keys: set[str] = set()
    task_status: dict[tuple[str, str], tuple[str, str]] = {}
    required_handoffs: set[str] = set()
    listed_handoffs: set[str] = set()

    def reserve_destination(key: str) -> None:
        normalized = key.casefold()
        if normalized in destination_keys:
            raise CloseoutError(f"多个过程文件指向同一目标，拒绝覆盖：{key}")
        destination_keys.add(normalized)

    for index, item in enumerate(workers):
        if not isinstance(item, dict):
            raise CloseoutError(f"worker_statuses[{index}] 必须是对象")
        task_id = str(item.get("task_id", "")).strip()
        worker_id = str(item.get("worker_id", "")).strip()
        worker_status = item.get("worker_status")
        manager_status = item.get("manager_status")
        if not task_id or not worker_id:
            raise CloseoutError(f"worker_statuses[{index}] 缺少 task_id 或 worker_id")
        if worker_status not in WORKER_STATUSES:
            raise CloseoutError(f"{task_id}/{worker_id} 的 worker_status 无效")
        if manager_status not in MANAGER_STATUSES:
            raise CloseoutError(f"{task_id}/{worker_id} 尚未完成管理员核验/处置")
        if worker_status == "COMPLETED" and manager_status not in {"ACCEPTED", "CANCELLED"}:
            raise CloseoutError(f"完成任务 {task_id}/{worker_id} 必须由管理员验收或明确取消")
        if worker_status == "INCOMPLETE_HANDOFF" and manager_status not in {"HANDOFF_ACCEPTED", "CANCELLED"}:
            raise CloseoutError(f"未完成任务 {task_id}/{worker_id} 必须完成接手交接或明确取消")
        task_key = (task_id, worker_id)
        if task_key in task_status:
            raise CloseoutError(f"重复的工作者状态：{task_id}/{worker_id}")
        task_status[task_key] = (worker_status, manager_status)
        handoff_raw = item.get("handoff_source")
        review_raw = item.get("review_source")
        handoff_rel, handoff_abs = _safe_relative(root, handoff_raw, "handoff_source")
        review_rel, review_abs = _safe_relative(root, review_raw, "review_source")
        for rel, path, label in ((handoff_rel, handoff_abs, "handoff_source"),
                                 (review_rel, review_abs, "review_source")):
            if not _is_under(rel, "for_manager") or not path.is_file():
                raise CloseoutError(f"{label} 必须是存在于 for_manager/ 下的文件")
        _read_status(handoff_abs, "worker_status", worker_status)
        _read_status(review_abs, "manager_status", manager_status)
        required_handoffs.update((handoff_rel.as_posix(), review_rel.as_posix()))

    inventory_handoffs = {key for key in inventory if Path(key).name.casefold() == "handoff.md"}
    inventory_reviews = {key for key in inventory if Path(key).name.casefold() == "review.md"}
    status_handoffs = {key for key in required_handoffs if Path(key).name.casefold() == "handoff.md"}
    status_reviews = {key for key in required_handoffs if Path(key).name.casefold() == "review.md"}
    if inventory_handoffs != status_handoffs or inventory_reviews != status_reviews:
        raise CloseoutError("for_manager 中每份 handoff.md/review.md 都必须在 worker_statuses 中登记并核验")

    for index, item in enumerate(deliverables):
        if not isinstance(item, dict):
            raise CloseoutError(f"deliverables[{index}] 必须是对象")
        source_key, source = _expect_source(root, item.get("source"), f"deliverables[{index}].source",
                                            "for_user", inventory, claimed)
        verification = item.get("verification")
        if not isinstance(verification, str) or not verification.strip() or verification.startswith("["):
            raise CloseoutError(f"{source_key} 缺少管理员实际核验记录")
        owner_role = item.get("owner_role")
        task_id = str(item.get("task_id", "")).strip()
        worker_id = str(item.get("worker_id", "")).strip()
        if owner_role == "worker":
            status = task_status.get((task_id, worker_id))
            if not task_id or not worker_id or status != ("COMPLETED", "ACCEPTED"):
                raise CloseoutError(f"工作者交付须关联已完成且由管理员验收的任务：{task_id}/{worker_id}")
        elif owner_role == "maintainer":
            if task_id and worker_id:
                status = task_status.get((task_id, worker_id))
                if not status or status != ("COMPLETED", "ACCEPTED"):
                    raise CloseoutError(f"维护者交付引用了未验收的工作者任务：{task_id}/{worker_id}")
        else:
            raise CloseoutError(f"deliverables[{index}].owner_role 必须为 worker 或 maintainer")
        destination_key, destination = _expect_destination(root, item.get("destination"),
                                                            f"deliverables[{index}].destination")
        reserve_destination(destination_key)
        plan.append({"action": "move_verified_deliverable", "source": source_key,
                     "destination": destination_key, "sha256": _sha256(source),
                     "verification": verification})

    for index, item in enumerate(user_discard):
        if not isinstance(item, dict):
            raise CloseoutError(f"user_discard[{index}] 必须是对象")
        source_key, source = _expect_source(root, item.get("source"), f"user_discard[{index}].source",
                                            "for_user", inventory, claimed)
        prepared_by = str(item.get("prepared_by", "")).strip()
        reason = item.get("reason")
        if not prepared_by or not isinstance(reason, str) or not reason.strip() or reason.startswith("["):
            raise CloseoutError(f"{source_key} 必须注明整理人和清理理由")
        plan.append({"action": "discard_obsolete_user_staging", "source": source_key,
                     "sha256": _sha256(source), "prepared_by": prepared_by, "reason": reason})

    for index, item in enumerate(handoffs):
        if not isinstance(item, dict):
            raise CloseoutError(f"handoffs[{index}] 必须是对象")
        source_key, source = _expect_source(root, item.get("source"), f"handoffs[{index}].source",
                                            "for_manager", inventory, claimed)
        if source_key == manifest_relative.as_posix():
            raise CloseoutError("closeout manifest 由收尾凭证自动归档，不应重复列入 handoffs")
        listed_handoffs.add(source_key)
        destination_key, destination = _expect_destination(
            root, item.get("destination"), f"handoffs[{index}].destination",
            (memory_root.name, "archive", "agent-handoffs"))
        reserve_destination(destination_key)
        plan.append({"action": "archive_handoff", "source": source_key,
                     "destination": destination_key, "sha256": _sha256(source)})

    if not required_handoffs.issubset(listed_handoffs):
        raise CloseoutError("worker_statuses 引用的 handoff/review 文件必须全部列入 handoffs 归档清单")

    for index, item in enumerate(work_archive):
        if not isinstance(item, dict):
            raise CloseoutError(f"work_archive[{index}] 必须是对象")
        source_key, source = _expect_source(root, item.get("source"), f"work_archive[{index}].source",
                                            "for_worker", inventory, claimed)
        if not str(item.get("generated_by", "")).strip():
            raise CloseoutError(f"{source_key} 缺少 generated_by")
        reason = item.get("reason")
        if not isinstance(reason, str) or not reason.strip() or reason.startswith("["):
            raise CloseoutError(f"{source_key} 缺少归档理由")
        destination_key, destination = _expect_destination(
            root, item.get("destination"), f"work_archive[{index}].destination",
            (memory_root.name, "archive", "worker-work"))
        reserve_destination(destination_key)
        plan.append({"action": "archive_worker_output", "source": source_key,
                     "destination": destination_key, "sha256": _sha256(source),
                     "generated_by": item["generated_by"], "reason": reason})

    for index, item in enumerate(work_discard):
        if not isinstance(item, dict):
            raise CloseoutError(f"work_discard[{index}] 必须是对象")
        source_key, source = _expect_source(root, item.get("source"), f"work_discard[{index}].source",
                                            "for_worker", inventory, claimed)
        if not str(item.get("generated_by", "")).strip():
            raise CloseoutError(f"{source_key} 缺少 generated_by")
        reason = item.get("reason")
        if not isinstance(reason, str) or not reason.strip() or reason.startswith("["):
            raise CloseoutError(f"{source_key} 缺少明确清理理由")
        plan.append({"action": "discard_obsolete_worker_output", "source": source_key,
                     "sha256": _sha256(source), "generated_by": item["generated_by"],
                     "reason": reason})

    missing = sorted(set(inventory) - claimed)
    if missing:
        raise CloseoutError("下列过程文件未明确迁移、归档或清理：" + ", ".join(missing))
    unexpected = sorted(claimed - set(inventory))
    if unexpected:
        raise CloseoutError("处置清单引用了不在临时目录中的文件：" + ", ".join(unexpected))

    for item in deliverables:
        task_id = str(item.get("task_id", "")).strip()
        worker_id = str(item.get("worker_id", "")).strip()
        if task_id and task_status.get((task_id, worker_id), (None, None))[0] == "INCOMPLETE_HANDOFF":
            raise CloseoutError(f"未完成工作者任务不得包含用户交付物：{task_id}/{worker_id}")

    placeholder_summary = [*placeholders]
    return {
        "plan": plan,
        "inventory": sorted(inventory),
        "placeholders": placeholder_summary,
        "worker_count": len(workers),
        "deliverable_count": len(deliverables),
        "manager_summary": summary.strip(),
    }


def _run(root: Path, manifest_value: str, apply: bool) -> dict[str, Any]:
    result = inspect_project(root, require_agent=True)
    if not result.ok:
        raise CloseoutError("项目预检失败：" + "；".join(result.errors))
    memory_root = result.memory_root
    if memory_root is None:
        raise CloseoutError("未解析到唯一项目记忆根目录")
    closed_marker = memory_root / "project_closed.json"
    if closed_marker.exists():
        raise CloseoutError("项目已封存；如需恢复工作，请先走重新激活流程")

    manifest_relative, manifest_path = _safe_relative(root, manifest_value, "manifest")
    if not _is_under(manifest_relative, "for_manager") or not manifest_path.is_file():
        raise CloseoutError("manifest 必须是 for_manager/ 下已存在的 JSON 文件")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CloseoutError(f"无法读取 closeout manifest：{exc}") from exc
    if not isinstance(manifest, dict):
        raise CloseoutError("closeout manifest 顶层必须是 JSON 对象")

    validated = _validate_manifest(root, memory_root, manifest_path, manifest_relative, manifest)
    record_dir = memory_root / "archive" / "closeouts"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    record_path = record_dir / f"closeout-{stamp}.json"
    if record_path.exists():
        raise CloseoutError(f"收尾凭证目标已存在：{record_path.relative_to(root)}")

    report = {
        "ok": True,
        "action": "apply" if apply else "dry-run",
        "root": str(root),
        "manifest": manifest_relative.as_posix(),
        "workers_quiesced": manifest["workers_quiesced"],
        "worker_count": validated["worker_count"],
        "deliverable_count": validated["deliverable_count"],
        "staging_file_count": len(validated["inventory"]),
        "empty_placeholders": validated["placeholders"],
        "operations": validated["plan"],
        "cleanup_directories": list(PROCESS_DIRS),
        "archive_record": str(record_path.relative_to(root)).replace("\\", "/"),
    }
    if not apply:
        return report

    # Copy and hash-verify all retained files before deleting any staged source.
    created_destinations: list[Path] = []
    try:
        for item in validated["plan"]:
            destination_key = item.get("destination")
            if not destination_key:
                continue
            source = root / item["source"]
            destination = root / Path(*PurePosixPath(destination_key).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            created_destinations.append(destination)
            if _sha256(source) != _sha256(destination):
                raise CloseoutError(f"复制后 SHA-256 不一致：{item['source']}")
    except Exception:
        for destination in reversed(created_destinations):
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                pass
        raise

    record = {
        "schema": SCHEMA,
        "closed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project_root": str(root),
        "manager_summary": validated["manager_summary"],
        "manifest": manifest,
        "operations": validated["plan"],
        "removed_empty_placeholders": validated["placeholders"],
    }
    record_dir.mkdir(parents=True, exist_ok=True)
    with record_path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, indent=2) + chr(10))

    for item in validated["plan"]:
        source = root / item["source"]
        source.unlink()
    (root / manifest_relative).unlink()
    for key in validated["placeholders"]:
        (root / Path(*PurePosixPath(key).parts)).unlink()
    for dirname in PROCESS_DIRS:
        folder = root / dirname
        leftovers = [p for p in folder.rglob("*") if p.is_file() or p.is_symlink()]
        if leftovers:
            raise CloseoutError(f"清理时发现未列入清单的新文件，目录未回收：{leftovers[0].relative_to(root)}")
        shutil.rmtree(folder)

    closed_data = {
        "status": "closed",
        "archive_record": record_path.relative_to(memory_root).as_posix(),
        "closed_at_utc": record["closed_at_utc"],
    }
    with closed_marker.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(closed_data, ensure_ascii=False, indent=2) + chr(10))
    final_check = inspect_project(root, require_agent=True)
    if not final_check.ok:
        raise CloseoutError("回收后结构复核失败：" + "；".join(final_check.errors))
    report["verified_closed"] = True
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="按核验清单归档并回收 academic-project 临时交付区（默认 dry-run）")
    parser.add_argument("--version", action="version", version=f"academic-project v{SKILL_VERSION}")
    parser.add_argument("--root", default=".", help="项目根目录")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST, help="for_manager/ 下的项目相对 JSON 清单")
    parser.add_argument("--apply", action="store_true", help="按已核验清单执行迁移、归档与清理")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()
    try:
        report = _run(resolve_root(args.root), args.manifest, args.apply)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print("academic-project final closeout")
            print(f"模式：{'实际执行' if args.apply else '预览'}")
            print(f"项目根：{report['root']}")
            print(f"工作者任务：{report['worker_count']}；正式交付物：{report['deliverable_count']}；待处置过程文件：{report['staging_file_count']}")
            for item in report["operations"]:
                target = f" -> {item['destination']}" if item.get("destination") else " -> 删除"
                print(f"- {item['action']}: {item['source']}{target}")
            if args.apply:
                print(f"封存凭证：{report['archive_record']}")
                print("封存状态：已核验")
            else:
                print("未执行写入。核对清单后再使用 --apply。")
        return 0
    except (CloseoutError, OSError, ValueError) as exc:
        if args.json:
            print(json.dumps({"ok": False, "action": "apply" if args.apply else "dry-run",
                              "error": str(exc)}, ensure_ascii=False, indent=2))
        else:
            print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
