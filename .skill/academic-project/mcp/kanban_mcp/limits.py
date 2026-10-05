"""Brevity limits from academic-project SKILL.md §6.2 / templates, in characters."""

import re

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

LIMITS: dict[str, int] = {
    "demand": 50,        # 单条需求描述
    "value": 80,         # 成果价值与自测说明
    "deliverable_note": 30,  # 陈列架一句话说明
    "milestone": 40,     # 里程碑单条
    "pending": 60,       # 待决策事项每条
    "stage": 20,         # 看板顶部当前阶段
    "direction": 30,     # 看板顶部核心攻关方向
    "req_detail": 200,   # requirements_log 要求/完成情况每格
    "progress_title": 40,
    "worklog_title": 40,
    "decision_title": 40,
}

DASHBOARD_WINDOWS = {"requirements": 10, "deliverables_per_category": 5, "milestones": 10, "pending": 3}
PROGRESS_LOG_KEEP = 30
REQUIREMENTS_LOG_KEEP = 100

STATUS_EMOJI = {"delivered": "🟢 已交付", "in_progress": "🟡 推进中", "blocked": "🔴 待确认"}
SNAPSHOT_STATUS = {"green": "🟢 正常推进", "yellow": "🟡 存在待确认事项", "red": "🔴 关键受阻"}
REVIEW_DECISIONS = ("ACCEPTED", "REWORK_REQUIRED", "HANDOFF_ACCEPTED", "CANCELLED")
HANDOFF_STATUSES = ("COMPLETED", "INCOMPLETE_HANDOFF")
DISPATCH_STATUSES = ("DISPATCHED", "IN_PROGRESS", "ACCEPTED", "REWORK", "CANCELLED")
DISPATCH_PRIORITIES = ("HIGH", "MEDIUM", "LOW")
DELIVERABLE_CATEGORIES = {
    "docs": "📄 文档与文稿",
    "figures": "📊 图表与可视化",
    "code": "💻 核心代码与工具",
    "bench": "🧪 实验与评测基准",
    "data": "💾 数据与数据集",
}

# 各 section 允许的 entry 字段（未知键拒写，不静默丢弃）
DASHBOARD_ENTRY_KEYS = {
    "snapshot": {"stage", "status", "direction"},
    "requirement": {"demand", "status", "path", "value", "date", "update_matching"},
    "deliverable": {"category", "name", "path", "note"},
    "milestone": {"event", "date"},
    "pending": {"action", "text", "items"},
}


def check_len(text: str, key: str, label: str | None = None) -> str:
    limit = LIMITS[key]
    text = (text or "").strip()
    if not text:
        raise ValueError(f"{label or key} 不能为空")
    if "\n" in text or "\r" in text:
        raise ValueError(f"{label or key} 必须为单行文本（表格/列表行内不允许换行）")
    if len(text) > limit:
        raise ValueError(f"{label or key} 超长：{len(text)} 字 > 上限 {limit} 字，请精简后重提")
    return text


def check_date(date_str: str, label: str = "日期") -> str:
    date_str = (date_str or "").strip()
    if not _DATE_RE.match(date_str):
        raise ValueError(f"{label} 格式非法：{date_str!r}（须为 YYYY-MM-DD）")
    import datetime as _dt
    y, m, d = (int(x) for x in date_str.split("-"))
    try:
        _dt.date(y, m, d)
    except ValueError:
        raise ValueError(f"{label} 不是有效日历日期：{date_str}") from None
    return date_str
