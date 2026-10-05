---
schema: academic-project-task-dispatch/v1
task_id: "T04b"
title: "PANN 边界加权再训练（修复 ν→0.39 角点 -5.6% 系统性低估）"
parent_goal: "Harazin et al. CMAME 2026 Example I 材料级严格复现（v2 计划 Phase 1A）"
assigned_role: "Experiment Engineer (ML constitutive modeling)"
assignee: "pending"
priority: HIGH
dispatch_status: DISPATCHED
created_at: "2026-10-05"
depends_on: ["T04", "T05"]
---

# Task Dispatch: T04b - 边界加权再训练

## 1. 任务背景与核心目标
- **任务目标**：T04 已验收的 PANN（测试 L2=1.51%）在定义域角点
  (E=3.5e4, ν=0.39) 系统性低估 S₁₁ 达 5.56%（四角点：−1.49%/−0.89%/−2.39%/−5.56%），
  导致 T05 的区间 max DOD（<3%）失败。根因：κ=E/(3(1−2ν)) 在 ν→0.39 处陡峭
  约 7×，均匀 LHS 欠采样边界。做边界加权再训练，消除该系统性偏差。
- **业务背景**：v2 计划 Phase 1A corrective。不改变 T04 已验收结论（平均指标），
  只改善最坏情况边界拟合；**不放宽任何 DOD**。

## 2. 输入依赖与先决条件
- **前置依赖任务**：T04（ACCEPTED，`surrogate/`）、T05（HANDOFF_ACCEPTED，
  见 `for_manager/T05/w1/review.md` 根因分析）。
- **输入物料路径**（只读）：
  - `surrogate/pann.py`、`surrogate/train_pann.py`（T04 交付物）
  - `for_manager/T05/w1/handoff.md`（角点误差证据）
- **前置就绪检查**：
  `/home/hatch/workspace/venvs/rve-pann/bin/python -c "import torch"` 成功
  （只读使用，不要 pip install）。

## 3. 写入范围与交付路径约束
- **Git 工作区**：
  - 隔离方式：`worktree`
  - 基线分支与 commit：`main` @ `76bda73`
  - 工作者专属分支：`worker/T04b-w1`
  - worktree 绝对路径：`/home/hatch/workspace/yade-rve-pann/.worktrees/T04b/w1`
- **工作者专属沙盒**：`for_worker/T04b/w1/`（新 checkpoint `pann_v2.pt` 放沙盒，不进 git）
- **正式文件直写授权**：
  - `surrogate/train_pann.py`（修改：边界加权策略，见 §5）
  - `surrogate/tests/test_pann.py`（修改：**新增角点断言**，四角点相对误差 <3%）
- **预期最终交付物**：上述两文件修改 + 沙盒 `pann_v2.pt`

## 4. 验收标准与完成定义 (DOD)
1. [ ] **无回归**：测试集应力相对 L2 < 5%（维持 T04 标准；目标 ≤2%）
2. [ ] **角点修复**：F=diag(1.1,1,1) 下四角点 (E,ν)∈{2.5e4,3.5e4}×{0.21,0.39}
   的 S₁₁ 相对误差绝对值 < 3%（当前：1.49/0.89/2.39/**5.56** → 目标全 <3%）
3. [ ] **T05 区间 max 重验**：用 `pann_v2.pt` 跑 T05 方法，
   区间 max 相对误差 < 3%（T05 自测除该项外已全过）
4. [ ] 自测命令退出码 0（含新增角点断言）
5. [ ] 若加权后角点仍 >3%，如实报告并停止（不得调参刷榜），转入局限记录

## 5. 已知陷阱与注意事项
- 建议策略（选其一或组合，记录选择理由）：
  a) DoE 增补角点/边界面样本（如 4 角点 × 若干力学点，或 ν>0.35 加采样）；
  b) loss 按 ν 接近 0.39 加权；
  c) 两阶段：先均匀训练再边界微调。
- 保持 seed 固定可复现；超参变更记入交接件。
- 2 核 CPU，训练时长控制 ~15 分钟内（DoE 增补后总量 <8000 点）。
- 不要修改 `for_user/`、看板、WORKLOG（只读）；不要 git commit/push。
