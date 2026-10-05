"""Project model: root/memory-root resolution, path guards, switch parsing."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class KanbanError(ValueError):
    """Validation or permission failure surfaced to the caller."""


SWITCH_KEY = "mcp_governed_writes"


@dataclass
class Project:
    root: Path
    role: str  # "maintainer" | "worker"

    def __post_init__(self) -> None:
        self.root = Path(self.root).expanduser().resolve()
        if not self.root.is_dir():
            raise KanbanError(f"项目根目录不存在：{self.root}")
        if self.role not in ("maintainer", "worker"):
            raise KanbanError(f"非法角色：{self.role}")
        new = self.root / ".project-memory"
        legacy = self.root / ".paper-memory"
        present = [p for p in (new, legacy) if p.is_dir()]
        if len(present) == 2:
            raise KanbanError("记忆根目录冲突：同时存在 .project-memory/ 与 .paper-memory/，请先人工处理")
        if not present:
            raise KanbanError("未发现 .project-memory/ 或 .paper-memory/ 记忆根目录，无法执行收口写入")
        self.memory_root: Path = present[0]

    # --- paths ---
    def resolve_in_root(self, rel: str) -> Path:
        candidate = (self.root / rel).resolve()
        if not candidate.is_relative_to(self.root):
            raise KanbanError(f"路径越出项目根目录：{rel}")
        return candidate

    @staticmethod
    def posix(rel: Path | str) -> str:
        return str(rel).replace("\\", "/")

    def rel_of(self, path: Path) -> str:
        return self.posix(Path(path).resolve().relative_to(self.root))

    # --- contract switch ---
    def governance(self) -> str:
        """Return 'on' or 'off'; absent key or unreadable AGENTS.md means off."""
        agents = self.root / "AGENTS.md"
        if not agents.exists():
            return "off"
        try:
            text = agents.read_text(encoding="utf-8")
        except OSError:
            return "off"
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(f"{SWITCH_KEY}:"):
                value = stripped.split(":", 1)[1].strip().strip('"').strip("'").lower()
                return value if value in ("on", "off") else "off"
        return "off"
