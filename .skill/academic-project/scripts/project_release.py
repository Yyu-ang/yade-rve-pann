#!/usr/bin/env python3
"""academic-project public release and de-sensitisation tool.

Creates clean public release branches or exports clean standalone packages
by stripping AI memory roots, local skills, and internal maintenance scaffolding.

Usage examples:
    # 预览发布排查清单（Dry-run）
    python project_release.py --root . --branch release

    # 正式创建/更新纯净发布分支，并打上版本 tag
    python project_release.py --root . --branch release --tag v1.0.0 --apply

    # 导出纯净文件夹或 ZIP 压缩包（供 Zenodo、匿名盲审或期刊补充材料上传）
    python project_release.py --root . --export-zip ./release_v1.0.0.zip --apply
    python project_release.py --root . --export-dir ./clean_public_export --apply
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

try:
    from project_check_common import SKILL_VERSION
except ImportError:
    SKILL_VERSION = "2.4.2"

# Paths/patterns to exclude from clean public release
ROOT_ONLY_DIRS = {
    ".project-memory",
    ".paper-memory",
    ".skill",
    ".worktrees",
    "for_user",
    "for_worker",
    "for_manager",
}

ROOT_ONLY_FILES = {
    "AGENTS.md",
    "agent.md",
    "WORKLOG.md",
    "PROJECT_DASHBOARD.md",
}

JUNK_DIRS = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".venv",
    "venv",
    "node_modules",
    ".git",
    ".idea",
    ".vscode",
    ".gemini",
}

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".lnk",
}


def _run_git(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    sub_env = os.environ.copy()
    if env:
        sub_env.update(env)
    res = subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        env=sub_env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return res.returncode, res.stdout.strip(), res.stderr.strip()


def _is_git_repo(root: Path) -> bool:
    code, out, _ = _run_git(["rev-parse", "--is-inside-work-tree"], cwd=root)
    return code == 0 and out == "true"


def _should_exclude(rel_path: Path) -> bool:
    parts = rel_path.parts
    if not parts:
        return False
    # root-anchored internal dirs/files: nested copies (e.g. skill template
    # dirs, vendored sources) must survive export untouched
    if parts[0] in ROOT_ONLY_DIRS:
        return True
    if len(parts) == 1 and parts[0] in ROOT_ONLY_FILES:
        return True
    # any-depth junk
    for part in parts:
        if part in JUNK_DIRS:
            return True
    if parts[-1] in {".DS_Store"}:
        return True
    if rel_path.suffix.lower() in EXCLUDE_EXTENSIONS:
        return True
    return False


def _collect_files(root: Path) -> tuple[list[Path], list[Path]]:
    """Walk project root and separate included files from excluded files."""
    included: list[Path] = []
    excluded: list[Path] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if _should_exclude(rel):
            excluded.append(rel)
        else:
            included.append(rel)

    return included, excluded


def _create_release_branch_git(root: Path, branch: str, tag: str | None, message: str, apply: bool) -> tuple[bool, str]:
    """Atomically create or update a release branch using git plumbing without touching current working tree."""
    # Ensure HEAD exists
    code, head_commit, err = _run_git(["rev-parse", "HEAD"], cwd=root)
    if code != 0:
        return False, f"无法获取当前 Git HEAD 提交：{err}"

    # Use a temporary index file so working directory and index are completely untouched
    with tempfile.NamedTemporaryFile(prefix="git_index_", delete=False) as tmp_idx:
        temp_index_path = tmp_idx.name

    try:
        env = {"GIT_INDEX_FILE": temp_index_path}
        # 1. Read current HEAD tree into temp index
        code, _, err = _run_git(["read-tree", "HEAD"], cwd=root, env=env)
        if code != 0:
            return False, f"git read-tree 失败：{err}"

        # 2. Remove excluded patterns from temp index
        remove_targets = [
            ".project-memory", ".paper-memory", ".skill",
            "for_user", "for_worker", "for_manager",
            "AGENTS.md", "agent.md", "WORKLOG.md", "PROJECT_DASHBOARD.md",
        ]
        _run_git(["rm", "-r", "--cached", "--ignore-unmatch"] + remove_targets, cwd=root, env=env)

        # 3. Write tree
        code, tree_hash, err = _run_git(["write-tree"], cwd=root, env=env)
        if code != 0:
            return False, f"git write-tree 失败：{err}"

        # 4. Check if target branch already has a commit
        code, parent_commit, _ = _run_git(["rev-parse", f"refs/heads/{branch}"], cwd=root)
        commit_args = ["commit-tree", tree_hash, "-m", message]
        if code == 0 and parent_commit:
            commit_args.extend(["-p", parent_commit])

        if not apply:
            return True, f"[预览] 将生成纯净树哈希 {tree_hash[:8]} 并提交到分支 '{branch}'"

        # 5. Commit tree
        code, new_commit, err = _run_git(commit_args, cwd=root)
        if code != 0:
            return False, f"git commit-tree 失败：{err}"

        # 6. Update target branch ref
        code, _, err = _run_git(["update-ref", f"refs/heads/{branch}", new_commit], cwd=root)
        if code != 0:
            return False, f"git update-ref 失败：{err}"

        # 7. Optional tag
        tag_msg = ""
        if tag:
            t_code, _, t_err = _run_git(["tag", "-f", tag, new_commit], cwd=root)
            if t_code == 0:
                tag_msg = f" 并打上标签 '{tag}'"
            else:
                tag_msg = f"（但标签 '{tag}' 创建失败：{t_err}）"

        return True, f"成功创建/更新纯净发布分支 '{branch}'（commit: {new_commit[:8]}）{tag_msg}"

    finally:
        if os.path.exists(temp_index_path):
            try:
                os.remove(temp_index_path)
            except OSError:
                pass


def _export_directory(root: Path, target_dir: Path, included: list[Path], apply: bool) -> tuple[bool, str]:
    if not apply:
        return True, f"[预览] 将导出 {len(included)} 个纯净文件至文件夹：{target_dir}"

    target_dir.mkdir(parents=True, exist_ok=True)
    for rel in included:
        src = root / rel
        dst = target_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return True, f"成功导出 {len(included)} 个文件至纯净目录：{target_dir}"


def _export_zip(root: Path, zip_path: Path, included: list[Path], apply: bool) -> tuple[bool, str]:
    if not apply:
        return True, f"[预览] 将打包 {len(included)} 个纯净文件至 ZIP 压缩包：{zip_path}"

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in included:
            src = root / rel
            zf.write(src, arcname=str(rel).replace("\\", "/"))
    return True, f"成功打包 {len(included)} 个文件至 ZIP：{zip_path}"


def main() -> int:
    ap = argparse.ArgumentParser(description="academic-project 公开发布脱敏工具（生成纯净分支或导出包）")
    ap.add_argument("--version", action="version", version=f"academic-project v{SKILL_VERSION}")
    ap.add_argument("--root", default=".", help="项目根目录，默认当前目录")
    ap.add_argument("--branch", help="创建或更新的纯净发布分支名称（如 release 或 public）")
    ap.add_argument("--tag", help="可选的版本 Tag（如 v1.0.0-release）")
    ap.add_argument("--message", default="Release: clean public release without AI memory scaffolding", help="发布提交信息")
    ap.add_argument("--export-dir", help="导出纯净项目文件至指定文件夹")
    ap.add_argument("--export-zip", help="导出纯净项目文件至 ZIP 压缩包（适合盲审/补充材料）")
    ap.add_argument("--apply", action="store_true", help="执行实际操作（默认仅 Dry-run 预览）")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"错误：项目根目录不存在：{root}", file=sys.stderr)
        return 1

    included, excluded = _collect_files(root)

    mode_str = "实际执行" if args.apply else "预览模式 (Dry-run)"
    print(f"=== academic-project 公开发布脱敏工具 [{mode_str}] ===")
    print(f"项目根目录：{root}")
    print(f"可公开发布文件数：{len(included)} 个")
    print(f"自动剥离内部文件数：{len(excluded)} 个")

    if not args.apply:
        print("\n[剥离的内部脚手架示例（部分）]：")
        for f in excluded[:10]:
            print(f"  - (排除) {f}")
        if len(excluded) > 10:
            print(f"  ... 另有 {len(excluded) - 10} 个内部文件已排除")

    performed = False

    # 1. Branch release
    if args.branch:
        performed = True
        if not _is_git_repo(root):
            print(f"错误：--branch 需要项目为 Git 仓库，但未在 {root} 检测到 Git 工作区", file=sys.stderr)
            return 1
        ok, msg = _create_release_branch_git(root, args.branch, args.tag, args.message, args.apply)
        print(f"\n[发布分支]：{msg}")
        if not ok:
            return 2

    # 2. Export Dir
    if args.export_dir:
        performed = True
        target_dir = Path(args.export_dir).expanduser().resolve()
        ok, msg = _export_directory(root, target_dir, included, args.apply)
        print(f"\n[目录导出]：{msg}")
        if not ok:
            return 2

    # 3. Export ZIP
    if args.export_zip:
        performed = True
        zip_path = Path(args.export_zip).expanduser().resolve()
        ok, msg = _export_zip(root, zip_path, included, args.apply)
        print(f"\n[ZIP 导出]：{msg}")
        if not ok:
            return 2

    if not performed:
        print("\n提示：未指定发布操作。可通过以下参数执行发布：")
        print("  --branch <分支名>    : 创建/更新纯净 Git 分支（非破坏性操作，不改动当前工作区）")
        print("  --export-zip <路径>  : 导出脱敏 ZIP 压缩包（适合盲审/补充材料）")
        print("  --export-dir <路径>  : 导出脱敏干净文件夹")
        print("  --apply             : 确认执行实际写入（默认仅预览）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
