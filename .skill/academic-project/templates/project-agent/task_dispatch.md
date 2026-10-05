---
schema: academic-project-task-dispatch/v1
task_id: "[task-id]"
title: "[子任务简明标题]"
parent_goal: "[关联的宏观用户需求或研究目标]"
assigned_role: "[建议专项角色，如 Data Analyst / Experiment Engineer / Visualization Specialist]"
assignee: "[获派工作者标识，如 worker-data-01，未定填 pending]"
priority: HIGH  # HIGH | MEDIUM | LOW
dispatch_status: DISPATCHED  # DISPATCHED | IN_PROGRESS | ACCEPTED | REWORK | CANCELLED
created_at: "YYYY-MM-DD"
depends_on: []  # 依赖的前置任务 ID，如 ["T01-data-clean"]，无依赖留空
---

# Task Dispatch: [task-id] - [子任务简明标题]

## 1. 任务背景与核心目标
- **任务目标**：[精准描述该子任务需达成的目标与解决的问题]
- **业务背景**：[提供工作者所需的学术或工程背景，说明在整体方案中的定位]

## 2. 输入依赖与先决条件
- **前置依赖任务**：[明确依赖的前置 task_id 及其已验收交付物；无依赖写“无”]
- **输入物料路径**：
  - 核心输入数据/文件：`[相对路径]`（只读）
  - 参考规范/已有代码：`[相对路径]`（只读）
  - 前序任务产物：`[相对路径]`（只读）
- **前置就绪检查**：[工作者开工前必须核实的条件，如“确认原始数据集包含 train.csv 且非空”]

## 3. 写入范围与交付路径约束
- **Git 工作区（本地代码任务必填；非 Git/非代码任务填“不适用”）**：
  - 隔离方式：`worktree` / `执行平台已隔离（注明实际路径）` / `单工作者顺序 checkout` / `不适用`
  - 基线分支与 commit：[明确来源]
  - 工作者专属分支：[唯一分支名；若不适用说明原因]
  - worktree 绝对路径：`[项目根目录/.worktrees/<task-id>/<worker-id>/ 或经说明的同级路径]`
  - 大文件/数据/依赖/数据库/端口方案：[注明只读数据根、需稀疏检出的目录、依赖缓存与隔离输出；没有则填“无”]
- **工作者专属沙盒**：`for_worker/[task-id]/[worker-id]/`（过程产物、调试日志与 WIP 必须在此写入）
- **两类目录区分**：worktree 是代码 checkout；`for_worker/` 是过程材料目录，不能互相替代，也不得把完整 worktree 放入会被项目 closeout 回收的临时目录。
- **正式文件直写授权**：
  - `[相对路径]`（若允许直接修改正式源码或文稿章节，必须在此逐项显式授权；未列出者严格只读）
  - [若不允许直写任何正式文件，填写“无（禁止直接修改正式项目文件，成果统一落盘沙盒由管理员验收迁移）”]
- **预期最终交付物**：
  - `[成果物 1 路径与格式]`：[一句话说明用途]
  - `[成果物 2 路径与格式]`：[一句话说明用途]

## 4. 验收标准与完成定义 (Definition of Done - DOD)
> 工作者提交 COMPLETED 之前必须自测满足以下所有条件，管理员复核时逐条对账：

1. [ ] **功能/内容指标**：[明确具体功能、内容或学术指标要求]
2. [ ] **格式与规范**：[如代码通过 flake8/black 检查，或文稿符合 LaTeX 语法且无未转义公式]
3. [ ] **自测命令与预期证据**：
   - 必须执行的自测命令：`[具体命令，如 pytest tests/test_xxx.py 或 python scripts/check.py]`
   - 预期输出/通过标准：`[明确的成功指示，如“退出码 0，全量测试 pass”]`

## 5. 接续与历史上下文 (可选)
- **接续说明**：[若为接替前任未完成任务，在此注明前任 worker 标识及遗留 WIP 路径]
- **已知陷阱与注意事项**：[提示避免重复犯错的经验教训]
