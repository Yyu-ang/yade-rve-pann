#!/usr/bin/env python3
"""Initialise an academic-project from templates.

Dry-run by default; --apply to write files.

    python project_init.py --root /path/to/project --type paper --json
    python project_init.py --root /path/to/project --type paper,data_analysis --apply
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from project_check_common import SKILL_VERSION, TEMPLATE_MAP, VALID_PROJECT_TYPES, resolve_root
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from project_check_common import SKILL_VERSION, TEMPLATE_MAP, VALID_PROJECT_TYPES, resolve_root

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = SKILL_DIR / "templates"
PROCESS_DIRS = ("for_user", "for_worker", "for_manager")
MEMORY_ROOTS = (".project-memory", ".paper-memory")


def _closed_marker(root: Path) -> Path | None:
    found = [root / name / "project_closed.json" for name in MEMORY_ROOTS]
    found = [path for path in found if path.is_file()]
    return found[0] if found else None


def _tpl(rel: str) -> str:
    return (TEMPLATES_DIR / rel).read_text(encoding="utf-8")


def _plan(root: Path, types: list[str]) -> tuple[list[tuple[Path, str]], list[str]]:
    files: list[tuple[Path, str]] = []
    warns: list[str] = []
    mr = root / ".project-memory"

    # core templates
    for tpl_rel, target_rel in TEMPLATE_MAP.items():
        target = mr / target_rel
        if target.exists():
            warns.append(f"已存在，跳过：{target.relative_to(root)}")
        else:
            content = _tpl(tpl_rel)
            if tpl_rel == "core/project_overview.md":
                content = content.replace(
                    "[workflow/ 下已创建的子文件夹列表，可随时追加]",
                    " / ".join(types),
                )
            files.append((target, content))

    # workflow templates per type
    for ptype in types:
        tpl_dir = TEMPLATES_DIR / "workflow" / ptype
        if not tpl_dir.is_dir():
            warns.append(f"模板不存在：workflow/{ptype}/")
            continue
        for f in sorted(tpl_dir.iterdir()):
            if f.is_file() and f.suffix == ".md":
                target = mr / "workflow" / ptype / f.name
                if target.exists():
                    warns.append(f"已存在，跳过：{target.relative_to(root)}")
                else:
                    files.append((target, f.read_text(encoding="utf-8")))

    # root-level files: AGENTS.md, PROJECT_DASHBOARD.md, README.md, WORKLOG.md, .gitattributes
    root_files_map = {
        "AGENTS.md": "project-agent/AGENTS.md",
        "PROJECT_DASHBOARD.md": "project-agent/PROJECT_DASHBOARD.md",
        "README.md": "project-agent/README.md",
        "WORKLOG.md": "project-agent/WORKLOG.md",
        ".gitattributes": "project-agent/gitattributes",
    }
    for target_name, tpl_rel in root_files_map.items():
        target = root / target_name
        if target.exists():
            warns.append(f"已存在，跳过：{target_name}")
        else:
            tpl = TEMPLATES_DIR / tpl_rel
            if tpl.exists():
                files.append((target, tpl.read_text(encoding="utf-8")))

    # Temporary collaboration directories (not recreated after final closure)
    if not _closed_marker(root):
        for dirname in PROCESS_DIRS:
            folder = root / dirname
            marker = folder / ".gitkeep"
            if folder.exists() and not folder.is_dir():
                warns.append(f"临时交付路径不是文件夹，跳过：{dirname}")
            elif not marker.exists() and (not folder.exists() or not any(folder.iterdir())):
                files.append((marker, ""))

    # archive/ placeholder
    archive_dir = mr / "archive"
    if not archive_dir.exists():
        files.append((archive_dir / ".gitkeep", ""))

    # Copy academic-project skill into .skill/academic-project
    target_skill_dir = root / ".skill" / "academic-project"
    for item in sorted(SKILL_DIR.rglob("*")):
        if item.is_file():
            rel = item.relative_to(SKILL_DIR)
            parts = rel.parts
            if any(p.startswith(".") or p == "__pycache__" or p.endswith(".pyc") for p in parts):
                continue
            target = target_skill_dir / rel
            if target.exists():
                warns.append(f"已存在，跳过：.skill/academic-project/{rel}")
            else:
                try:
                    content = item.read_text(encoding="utf-8")
                    files.append((target, content))
                except Exception:
                    pass

    return files, warns


def main() -> int:
    ap = argparse.ArgumentParser(description="初始化 academic-project 项目结构（默认 dry-run）")
    ap.add_argument("--version", action="version", version=f"academic-project v{SKILL_VERSION}")
    ap.add_argument("--root", default=".", help="项目根目录")
    ap.add_argument(
        "--type",
        help=f"项目类型（逗号分隔）：{','.join(sorted(VALID_PROJECT_TYPES))}",
    )
    ap.add_argument(
        "--update-skill",
        action="store_true",
        help="更新本地固化技能；对活动项目仅补建缺失的 for_user/、for_worker/、for_manager/，不改写记忆或契约文件",
    )
    ap.add_argument(
        "--reopen",
        action="store_true",
        help="显式重新激活已封存项目：移除封存标记、重建临时交付目录并追加日志（默认预览）",
    )
    ap.add_argument("--apply", action="store_true", help="实际写入（默认仅预览）")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()

    root = resolve_root(args.root)

    if args.reopen:
        if args.update_skill or args.type:
            print("错误：--reopen 不能与 --update-skill 或 --type 同用", file=sys.stderr)
            return 1
        memory_roots = [root / name for name in MEMORY_ROOTS if (root / name).is_dir()]
        markers = [mr / "project_closed.json" for mr in memory_roots if (mr / "project_closed.json").is_file()]
        if len(memory_roots) != 1 or len(markers) != 1:
            print("错误：重新激活要求唯一记忆根目录及有效 project_closed.json", file=sys.stderr)
            return 1
        memory_root = memory_roots[0]
        marker = markers[0]
        try:
            closeout = json.loads(marker.read_text(encoding="utf-8"))
            archive_rel = closeout.get("archive_record")
            archive_path = (memory_root / archive_rel).resolve() if isinstance(archive_rel, str) else None
            if archive_path is None or not archive_path.is_relative_to(memory_root.resolve()) or not archive_path.is_file():
                raise ValueError("缺少或越界的封存凭证")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"错误：封存标记或凭证无效：{exc}", file=sys.stderr)
            return 1
        if any((root / dirname).exists() for dirname in PROCESS_DIRS):
            print("错误：封存项目仍存在临时交付目录，需先人工核验", file=sys.stderr)
            return 1
        if not args.apply:
            if args.json:
                print(json.dumps({"action": "reopen", "applied": False, "root": str(root),
                                  "remove": str(marker.relative_to(root)),
                                  "rebuild": list(PROCESS_DIRS)}, ensure_ascii=False, indent=2))
                return 0
            print(f"[预览] 将移除 {marker.relative_to(root)} 并重建：{', '.join(PROCESS_DIRS)}")
            print("提示：追加 --apply 执行；确认后还需更新 current_status.md。")
            return 0
        marker.unlink()
        for dirname in PROCESS_DIRS:
            folder = root / dirname
            folder.mkdir(parents=True, exist_ok=False)
            (folder / ".gitkeep").write_text("", encoding="utf-8")
        from datetime import datetime
        stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
        worklog = root / "WORKLOG.md"
        if worklog.is_file():
            with worklog.open("a", encoding="utf-8") as handle:
                handle.write(chr(10) * 2 + f"## [{stamp}] 项目重新激活" + chr(10) * 2 + "- 移除封存标记并重建三个临时协作目录；维护者需同步更新当前状态。" + chr(10))
        progress_log = memory_root / "progress" / "progress_log.md"
        if progress_log.is_file():
            with progress_log.open("a", encoding="utf-8") as handle:
                handle.write(chr(10) * 2 + f"## {stamp} 项目重新激活" + chr(10) * 2 + "- 按授权恢复多 AI 临时协作目录。" + chr(10))
        if args.json:
            print(json.dumps({"action": "reopen", "applied": True, "root": str(root),
                              "rebuild": list(PROCESS_DIRS)}, ensure_ascii=False, indent=2))
            return 0
        print(f"已重新激活项目：{root}")
        print("已重建：" + ", ".join(PROCESS_DIRS))
        print("请更新 progress/current_status.md 并运行 project_preflight.py。")
        return 0

    if args.update_skill:
        target_skill_dir = root / ".skill" / "academic-project"
        updated_count = 0
        for item in sorted(SKILL_DIR.rglob("*")):
            if item.is_file():
                rel = item.relative_to(SKILL_DIR)
                parts = rel.parts
                if any(p.startswith(".") or p == "__pycache__" or p.endswith(".pyc") for p in parts):
                    continue
                target = target_skill_dir / rel
                try:
                    content = item.read_text(encoding="utf-8")
                    if args.apply:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_text(content, encoding="utf-8")
                    updated_count += 1
                except Exception:
                    pass
        output_dirs_added: list[str] = []
        if _closed_marker(root) is None:
            for dirname in PROCESS_DIRS:
                folder = root / dirname
                if folder.exists() and not folder.is_dir():
                    print(f"错误：临时交付路径不是文件夹：{folder}", file=sys.stderr)
                    return 1
                marker = folder / ".gitkeep"
                if not folder.exists() or (not any(folder.iterdir()) and not marker.exists()):
                    if args.apply:
                        marker.parent.mkdir(parents=True, exist_ok=True)
                        marker.write_text("", encoding="utf-8")
                    output_dirs_added.append(dirname)
        if args.json:
            print(json.dumps({
                "action": "update-skill", "applied": bool(args.apply), "root": str(root),
                "skill_version": SKILL_VERSION, "synced_files": updated_count,
                "process_dirs_added": output_dirs_added,
            }, ensure_ascii=False, indent=2))
            return 0
        mode_str = "已写入更新" if args.apply else "预览更新（需加 --apply 确认执行）"
        print(f"=== academic-project 本地技能更新 [{mode_str}] ===")
        print(f"项目根：{root}")
        print(f"目标目录：{target_skill_dir}")
        print(f"最新版本：v{SKILL_VERSION}")
        print(f"同步文件数：{updated_count} 个")
        print(f"需补建临时交付目录：{', '.join(output_dirs_added) if output_dirs_added else '无'}")
        if not args.apply:
            print("提示：请追加 --apply 参数以正式写入更新。")
        return 0

    if not args.type:
        print("错误：初始化新项目时必须指定 --type 参数（如 --type paper 或 --type code_project）", file=sys.stderr)
        return 1

    types = [t.strip() for t in args.type.split(",")]
    bad = [t for t in types if t not in VALID_PROJECT_TYPES]
    if bad:
        print(f"错误：无效的项目类型 {bad}", file=sys.stderr)
        return 1
    if (root / ".project-memory").exists() or (root / ".paper-memory").exists():
        print("错误：项目已有 memory root，不应重复初始化", file=sys.stderr)
        return 1

    files, warns = _plan(root, types)

    if args.apply:
        for p, content in files:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")

    if args.json:
        print(json.dumps({
            "action": "apply" if args.apply else "dry-run",
            "root": str(root), "types": types,
            "files": [str(f.relative_to(root)) for f, _ in files],
            "created": len(files) if args.apply else 0,
            "warnings": warns,
        }, ensure_ascii=False, indent=2))
        return 0

    mode = "实际写入" if args.apply else "预览（dry-run）"
    print(f"=== academic-project 初始化 [{mode}] ===")
    print(f"项目根：{root}\n类型：{', '.join(types)}")
    print(f"\n将创建 {len(files)} 个文件：")
    for p, _ in files:
        print(f"  + {p.relative_to(root)}")
    if warns:
        print("\n警告：")
        for w in warns:
            print(f"  - {w}")
    if args.apply:
        print(f"\n已创建 {len(files)} 个文件。运行 project_preflight.py 验证。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
