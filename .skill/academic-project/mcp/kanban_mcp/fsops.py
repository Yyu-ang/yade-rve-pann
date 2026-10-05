"""Filesystem helpers: UTF-8 IO with LF newlines, timestamps, ledger."""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

LEDGER_RELPATH = "mcp_write_ledger.md"


def now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"文件不存在：{path}") from exc


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip("\n") + "\n", encoding="utf-8", newline="\n")


def append_text(path: Path, text: str) -> None:
    existing = ""
    if path.exists():
        existing = path.read_text(encoding="utf-8")
    if existing and not existing.endswith("\n"):
        existing += "\n"
    path.write_text(existing + text, encoding="utf-8", newline="\n")


def ledger_append(root: Path, memory_root: Path, *, tool: str, role: str,                  actor: str, targets: list[str], note: str = "") -> None:
    """Append a single-line JSON record to the governance ledger.

    The ledger is server-written only; the finish gate reconciles it against
    governance-file mtime AND content hash, so a later ungoverned edit of a
    file that was covered earlier in the same window is still caught.
    ``sha`` maps target relpath -> first-12-hexchars sha256 of written bytes.
    The reserved ``sig`` field is a hook for a future HMAC hardening tier and
    stays null at the opportunistic tier.
    """
    import hashlib
    sha_map = {}
    for rel in targets:
        try:
            sha_map[rel] = hashlib.sha256((root / rel).read_bytes()).hexdigest()[:12]
        except OSError:
            sha_map[rel] = "-"
    record = {
        "t": time.time(),
        "ts": now_stamp(),
        "tool": tool,
        "role": role,
        "actor": actor or "",
        "targets": targets,
        "sha": sha_map,
        "note": note,
        "sig": None,
    }
    path = memory_root / LEDGER_RELPATH
    if not path.exists():
        header = (
            "# MCP 写入台账 (mcp_write_ledger)\n"
            "> 本文件由 academic-kanban MCP 独占追加，每行一条 JSON 记录；"
            "门禁脚本据此对账治理文件变更。请勿手工编辑。\n\n"
        )
        path.write_text(header, encoding="utf-8", newline="\n")
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


# Mirror of academic-project v2.2+ project_check_common.governance_files:
# keep both lists in sync when the governed set changes.
GOVERNED_MEMORY_RELS = (
    "project_overview.md",
    "progress/current_status.md",
    "progress/progress_log.md",
    "progress/milestones.md",
    "decisions/decision_log.md",
    "requirements/requirements_log.md",
    "rules/file_layout.md",
)


def governance_relpaths(root: Path, memory_root: Path) -> set[str]:
    rels = {"PROJECT_DASHBOARD.md", "WORKLOG.md", "AGENTS.md"}
    mem_prefix = str(memory_root.resolve().relative_to(root)).replace("\\", "/") + "/"
    rels.update(mem_prefix + r for r in GOVERNED_MEMORY_RELS)
    workflow = memory_root / "workflow"
    if workflow.is_dir():
        rels.update(str(w.resolve().relative_to(root)).replace("\\", "/")
                    for w in workflow.rglob("*.md") if w.is_file())
    return rels
