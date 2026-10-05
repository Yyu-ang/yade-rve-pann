---
schema: academic-project-worker-handoff/v1
task_id: "[task-id]"
worker_id: "[agent-id]"
worker_status: INCOMPLETE_HANDOFF  # COMPLETED | INCOMPLETE_HANDOFF
---

# Worker Handoff

## 指派目标与验收标准
- 目标：[原样简述指派事项]
- 验收标准：[逐条列出]

## 状态与已完成项
- **工作者状态**：`COMPLETED` 或 `INCOMPLETE_HANDOFF`
- 已完成项：[逐条列出；没有则写“无”]

## Git 工作区与资源交接
- 隔离方式：[worktree / 平台已隔离 checkout / 顺序 checkout / 不适用]
- 分支与基线 commit：[明确记录；不适用写原因]
- worktree 绝对路径：[路径；不适用写原因]
- 最终工作树状态与资源策略：[git status --short --branch、数据/依赖/数据库/端口隔离；不适用写原因]

## 交付物
- `COMPLETED`：仅列出完整成果的准确相对路径及用途。
- `INCOMPLETE_HANDOFF`：填写“无（仅交接）”；不得把半成品列为交付物或放入 `for_user/`。

## 自测与证据
- 命令/核验动作：[准确记录]
- 实际结果：[据实填写；未运行的检查标明“未运行”]

## 未完成项、阻塞与接续步骤
- 未完成项：[逐条列出；无则写“无”]
- 阻塞：[事实及所需决策；无则写“无”]
- 接续步骤：[明确下一步及所需角色]
- WIP 路径：[仅供接手续做，标记为过程材料；无则写“无”]

## 需管理员核验
- [列出尚需核验的事实；无则写“无”]
