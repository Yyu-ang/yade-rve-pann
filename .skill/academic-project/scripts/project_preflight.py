#!/usr/bin/env python3
"""Run the academic-project preflight gate for one project root."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from project_check_common import SKILL_VERSION, format_result, inspect_project, resolve_root
except ImportError:  # pragma: no cover - supports direct loading by some hosts
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from project_check_common import SKILL_VERSION, format_result, inspect_project, resolve_root


def main() -> int:
    parser = argparse.ArgumentParser(
        description="检查 academic-project 项目的入口、记忆根目录、核心文件和项目级技能。"
    )
    parser.add_argument("--version", action="version", version=f"academic-project v{SKILL_VERSION}")
    parser.add_argument("--root", default=".", help="项目根目录，默认当前目录")
    parser.add_argument(
        "--allow-missing-agents",
        "--allow-missing-agent",
        action="store_true",
        dest="allow_missing_agents",
        help="仅用于旧项目过渡检查；若缺失 AGENTS.md 则不报错（显示警告）",
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    args = parser.parse_args()

    result = inspect_project(resolve_root(args.root), require_agent=not args.allow_missing_agents)
    print(format_result(result, "academic-project preflight", as_json=args.json))
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
