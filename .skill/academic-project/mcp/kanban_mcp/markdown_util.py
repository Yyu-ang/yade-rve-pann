"""Markdown surgery helpers shared by governance write tools."""
from __future__ import annotations

import re


def split_lines(text: str) -> list[str]:
    return text.splitlines()


def entry_insert_point(lines: list[str]) -> int:
    """Index after the leading '# ' title and '> ' preamble block (newest-first logs)."""
    i = 0
    while i < len(lines) and (lines[i].startswith("# ") or lines[i].startswith(">") or not lines[i].strip()):
        i += 1
        if i < len(lines) and lines[i].startswith("## ["):
            break
    # rewind: preamble consumed greedily above stops at first real entry
    return i


def section_range(lines: list[str], heading_prefix: str) -> tuple[int, int]:
    """Return [start, end) line indexes of a '## x.' section body (excluding heading itself)."""
    pat = re.compile(rf"^##\s*{re.escape(heading_prefix)}")
    start = end = None
    for idx, line in enumerate(lines):
        if start is None and pat.match(line):
            start = idx + 1
        elif start is not None and line.startswith("## "):
            end = idx
            break
    if start is None:
        raise KeyError(f"看板缺少小节标题：## {heading_prefix}")
    return start, len(lines) if end is None else end


def is_data_row(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and not set(s) <= {"|", "-", ":", " "} and "---" not in s


def is_header_row(line: str, first_cell: str) -> bool:
    return first_cell in line


def table_row(cells: list[str]) -> str:
    return "| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |"


def parse_row(line: str) -> list[str]:
    """拆分 markdown 表格行，识别转义竖线 \\|，去除表尾悬挂分隔。"""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    parts = re.split(r"(?<!\\)\|", s)
    return [part.strip().replace("\\|", "|") for part in parts]


def quarter_from_date(date_str: str) -> str:
    m = re.search(r"(\d{4})-(\d{2})", date_str or "")
    if not m:
        from datetime import datetime
        now = datetime.now()
        return f"{now.year}Q{(now.month - 1) // 3 + 1}"
    year, month = int(m.group(1)), int(m.group(2))
    return f"{year}Q{(month - 1) // 3 + 1}"


def append_lines_to_archive(archive_path, header: str, lines: list[str]) -> None:
    from .fsops import append_text
    from pathlib import Path
    p = Path(archive_path)
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(header, encoding="utf-8", newline="\n")
    chunk = [ln for ln in lines if ln.strip()]
    if chunk:
        append_text(p, "\n".join(chunk) + "\n")
