---
schema: academic-project-task-dispatch/v1
task_id: "T04"
title: "Phase 1A-2/3：DoE 数据生成 + PANN 训练（测试应力相对 L2 < 5%）"
parent_goal: "Harazin et al. CMAME 2026 Example I 材料级严格复现（v2 计划 Phase 1A）"
assigned_role: "Experiment Engineer (ML constitutive modeling)"
assignee: "pending"
priority: HIGH
dispatch_status: DISPATCHED
created_at: "2026-10-05"
depends_on: ["T03"]
---

# Task Dispatch: T04 - DoE + PANN 训练

## 1. 任务背景与核心目标
- **任务目标**：基于 T03 已验收的 Eq.(33) 解析本构，生成域分离 DoE 数据
  （**U** 50 LHS × 力学域 100 LHS = 5000 点），训练 PANN 代理 Ψ(**I**,**u**)，
  使测试集应力相对 L2 < 5%（项目内部阈值，非论文阈值）。
- **业务背景**：v2 计划 Phase 1A。论文 Table 2 结构 5→175→175→1 作 baseline；
  输入 (I₁,I₂,I₃,E,ν)，E∈[2.5,3.5]e4 MPa，ν∈[0.21,0.39]，H_ij∈[−0.2,0.2]，
  **F**=**H**+**1**；输入缩放到 [−1,1]（链式法则修正，论文 §4.2.2）。

## 2. 输入依赖与先决条件
- **前置依赖任务**：T03（ACCEPTED）：`examples/ex1_neohooke/neohooke.py`
  提供 `pk2_stress(F,E,nu)` 解析参考。
- **输入物料路径**（只读）：
  - `examples/ex1_neohooke/neohooke.py`（T03 交付物）
  - `docs/reproduction_plan_review_2026-10-05.md` §3（Phase 1A）
  - `surrogate/pann.py`（骨架，接口须按 P0-4 修正）
- **前置就绪检查**：
  - torch 环境：`/home/hatch/workspace/venvs/rve-pann/bin/python -c "import torch"` 成功（torch 2.14.1+cpu，只读使用，不要 pip install 到里面）

## 3. 写入范围与交付路径约束
- **Git 工作区**：
  - 隔离方式：`worktree`
  - 基线分支与 commit：`main` @ `b03c36a`
  - 工作者专属分支：`worker/T04-w1`
  - worktree 绝对路径：`/home/hatch/workspace/yade-rve-pann/.worktrees/T04/w1`
- **工作者专属沙盒**：`for_worker/T04/w1/`（训练日志、曲线图、checkpoint 说明）
- **正式文件直写授权**：
  - `surrogate/pann.py`（实现；接口：`energy(I,u)`、`stress(C,u)`/`stress(F,u)`、
    `tangent(C,u)`，P0-4；softplus 隐层，linear 输出，保证二阶可微）
  - `surrogate/train_pann.py`（新建：DoE 生成 + 训练主脚本）
  - `surrogate/tests/test_pann.py`（新建：自测）
- **预期最终交付物**：
  - 上述三个文件；训练曲线图与 checkpoint 路径记入交接件（checkpoint 本体放沙盒，不进 git）

## 4. 验收标准与完成定义 (DOD)
1. [ ] **功能指标**：
   - DoE：50×100=5000 点，(I₁,I₂,I₃,E,ν)→**S**（voigt 6 分量），90/10 划分，seed 固定并记录
   - PANN baseline 5→175→175→1，softplus；loss = mean‖**S**ᴺᴺ−**S**ʳᵉᶠ‖²（论文 Eq.(12)）
   - 测试集应力相对 L2 < 5%
   - `stress(C,u)` 与数值差分交叉检查通过（沿用 T03 方法）
2. [ ] **格式与规范**：训练超参（lr、epoch、batch、seed）写入交接件；可复现
3. [ ] **自测命令与预期证据**：
   - `/home/hatch/workspace/venvs/rve-pann/bin/python surrogate/tests/test_pann.py`
   - 预期：退出码 0，打印测试集相对 L2（<5%）与训练 loss 曲线尾值

## 5. 已知陷阱与注意事项
- 输入缩放 [−1,1] 后，Eq.(6) 的链式法则必须显式处理（参考论文 §4.2.2 与 Linden et al. 做法）。
- 2 核 CPU 训练：5000 点小网络，epoch 数控制在合理范围（先 2000 epoch 看收敛），总时长应 <1h。
- 不要修改 `for_user/`、看板、WORKLOG（只读）；不要 git commit/push。
