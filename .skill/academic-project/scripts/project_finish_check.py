#!/usr/bin/env python3
"""Run the academic-project completion gate for one project root."""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path


def _parse_started_at(value: str) -> float:
    """Accept epoch seconds or local time strings: YYYY-MM-DD[ HH:MM[:SS]]."""
    try:
        return float(value)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip().strip('"'), fmt).timestamp()
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(
        f"--started-at 无法解析：{value!r}（支持 Unix 秒或 'YYYY-MM-DD HH:MM'）")

try:
    from project_check_common import (SKILL_VERSION, format_result, inspect_project,
                                      mcp_reconcile, resolve_root)
except ImportError:  # pragma: no cover - supports direct loading by some hosts
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from project_check_common import (SKILL_VERSION, format_result, inspect_project,
                                      mcp_reconcile, resolve_root)


def _updated_after(path: Path, started_at: float | None) -> bool:
    if started_at is None or not path.exists():
        return False
    # Windows timestamp precision can be coarse; allow a small tolerance.
    return path.stat().st_mtime >= started_at - 1.0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="检查 academic-project 任务完成后的记忆维护和可验证增量。"
    )
    parser.add_argument("--version", action="version", version=f"academic-project v{SKILL_VERSION}")
    parser.add_argument("--root", default=".", help="项目根目录，默认当前目录")
    parser.add_argument(
        "--started-at",
        type=_parse_started_at,
        default=None,
        help="任务开始时刻：Unix 秒或 'YYYY-MM-DD HH:MM'；用于验证 WORKLOG 和 progress_log 是否更新",
    )
    parser.add_argument(
        "--no-project-change",
        action="store_true",
        help="明确声明本次没有改变项目文件或项目状态，不要求日志增量",
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    args = parser.parse_args()

    result = inspect_project(resolve_root(args.root), require_agent=True)
    if not args.no_project_change and args.started_at is None:
        result.errors.append("项目有影响时必须提供 --started-at；若无项目变化请使用 --no-project-change")

    if result.memory_root and not args.no_project_change and args.started_at is not None:
        # WORKLOG.md update is mandatory
        worklog_path = result.root / "WORKLOG.md"
        if not _updated_after(worklog_path, args.started_at):
            result.errors.append(
                f"任务开始后未检测到必需的项目记录更新：{worklog_path.relative_to(result.root)}"
            )
        # PROJECT_DASHBOARD.md advisory check for user visibility
        dashboard_path = result.root / "PROJECT_DASHBOARD.md"
        if dashboard_path.exists() and not _updated_after(dashboard_path, args.started_at):
            result.warnings.append(
                f"PROJECT_DASHBOARD.md 未在任务开始后更新；"
                f"若本次响应了用户需求或产出阶段性成果，建议同步更新看板"
            )

        # progress_log.md update is advisory (aligns with SKILL.md §8:
        # only "trackable progress" requires progress_log; status/blocker
        # changes only need current_status.md)
        progress_log = result.memory_root / "progress" / "progress_log.md"
        if not _updated_after(progress_log, args.started_at):
            result.warnings.append(
                f"progress_log.md 未在任务开始后更新；"
                f"若本次仅更新了 current_status.md 可忽略此警告"
            )

        # MCP write-governance reconciliation (v2.2.0, only for mcp_governed_writes: on)
        if result.mcp_governed == "on":
            gov_errors, gov_warnings = mcp_reconcile(result.root, result.memory_root, args.started_at)
            result.errors.extend(gov_errors)
            result.warnings.extend(gov_warnings)
            if not gov_errors:
                result.notes.append("mcp_reconcile=covered")
            result.mcp_reconcile = "covered" if not gov_errors else "violations"

    title = "academic-project finish check"
    print(format_result(result, title, as_json=args.json))
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
