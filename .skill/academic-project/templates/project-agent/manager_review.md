---
schema: academic-project-manager-review/v1
task_id: "[task-id]"
worker_id: "[agent-id]"
manager_id: "[manager-id]"
manager_status: PENDING_REVIEW  # ACCEPTED | REWORK_REQUIRED | HANDOFF_ACCEPTED | CANCELLED
---

# Manager Review

## 核验结论
- **工作者状态**：`COMPLETED` 或 `INCOMPLETE_HANDOFF`
- **管理员决定**：`ACCEPTED`、`REWORK_REQUIRED`、`HANDOFF_ACCEPTED` 或 `CANCELLED`
- **核验的验收标准**：[逐条记录通过/未通过及证据]
- **产物路径与内容核验**：[检查结果]
- **Git 工作区复核**：[分支、基线、worktree 路径、差异与工作树状态；不适用写原因]
- **自测复核**：[实际复核动作与结果]

## 接续与清理
- **接续责任/下一步**：[无则写“无”]
- **保留的 WIP/复现材料**：[路径和保留理由；无则写“无”]
- **清理的过时产物**：[路径和清理理由；无则写“无”]
- **最终用户交付路径**：[验收后正式路径；尚未最终交付则写“待最终交付”]
