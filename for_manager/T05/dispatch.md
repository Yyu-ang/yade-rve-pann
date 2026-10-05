---
schema: academic-project-task-dispatch/v1
task_id: "T05"
title: "Phase 1A-4：材料级多态 UQ demo（MC q99 + 区间优化）"
parent_goal: "Harazin et al. CMAME 2026 Example I 材料级严格复现（v2 计划 Phase 1A）"
assigned_role: "Experiment Engineer (UQ)"
assignee: "pending"
priority: HIGH
dispatch_status: DISPATCHED
created_at: "2026-10-05"
depends_on: ["T04"]
---

# Task Dispatch: T05 - 材料级 UQ demo

## 1. 任务背景与核心目标
- **任务目标**：基于 T04 已验收的 PANN 代理，做材料级多态不确定性量化演示：
  对固定变形状态（如单轴拉伸 F=diag(1.1,1,1)），把 (E,ν) 的不确定性
  传播到应力响应，输出 MC 分位数（q99）与区间优化上下界。
- **业务背景**：v2 计划 Phase 1A-4。注意论文的 0.1%/0.07% q99 误差属于
  plate-with-hole 宏观 BVP，**不得**从本 demo 声称；本任务只做材料点级 UQ 方法演示。

## 2. 输入依赖与先决条件
- **前置依赖任务**：T04（ACCEPTED）：`surrogate/pann.py`（`PANN.load`）
  与 checkpoint `/home/hatch/workspace/yade-rve-pann/for_worker/T04/w1/pann.pt`
  （260KB，只读使用，不要复制进 git）。
- **输入物料路径**（只读）：
  - `surrogate/pann.py`（T04 交付物）
  - `docs/reproduction_plan_review_2026-10-05.md` §3（Phase 1A-4）
- **前置就绪检查**：
  `/home/hatch/workspace/venvs/rve-pann/bin/python -c "import torch"` 成功
  （只读使用，不要 pip install）。

## 3. 写入范围与交付路径约束
- **Git 工作区**：
  - 隔离方式：`worktree`
  - 基线分支与 commit：`main` @ `fb7e315`
  - 工作者专属分支：`worker/T05-w1`
  - worktree 绝对路径：`/home/hatch/workspace/yade-rve-pann/.worktrees/T05/w1`
- **工作者专属沙盒**：`for_worker/T05/w1/`
- **正式文件直写授权**：
  - `uq/material_uq.py`（新建：MC 采样 + 区间优化主脚本）
  - `uq/tests/test_uq.py`（新建：自测）
- **预期最终交付物**：上述两个文件；UQ 结果图/表放沙盒，关键数值记入交接件

## 4. 验收标准与完成定义 (DOD)
1. [ ] **MC 传播**：(E,ν) 在训练域内取分布（如 E~U[2.5,3.5]e4 MPa，
   ν~U[0.21,0.39]，seed 固定），N≥20000 样本，输出 S₁₁ 的均值/std/q99，
   与解析 Eq.(33) 的 MC 参考对比相对误差 < 3%
2. [ ] **区间优化**：(E,ν) 取区间（epistemic），用优化（多起点）求 S₁₁
   在区间上的 min/max，与解析参考的区间界对比相对误差 < 3%
3. [ ] **自测命令**：
   `/home/hatch/workspace/venvs/rve-pann/bin/python uq/tests/test_uq.py`
   退出码 0，打印 q99 与区间界及与解析参考的对比
4. [ ] 交接件声明：本 demo 为材料点级，不声称论文宏观 BVP 的 q99 精度

## 5. 已知陷阱与注意事项
- PANN 在训练域内插值可信；MC/区间优化的 (E,ν) 不得超出 [2.5,3.5]e4×[0.21,0.39]。
- checkpoint 路径是 worktree 外的绝对路径，自测脚本中写死该路径并加存在性断言。
- 不要修改 `for_user/`、看板、WORKLOG（只读）；不要 git commit/push。
