---
schema: academic-project-task-dispatch/v1
task_id: "T03"
title: "Phase 1A-1：论文 Eq.(33) 精确实现与 autodiff 一致性测试"
parent_goal: "Harazin et al. CMAME 2026 Example I 材料级严格复现（v2 计划 Phase 1A）"
assigned_role: "Experiment Engineer (constitutive modeling)"
assignee: "pending"
priority: HIGH
dispatch_status: DISPATCHED
created_at: "2026-10-05"
depends_on: []
---

# Task Dispatch: T03 - Eq.(33) 精确实现与一致性测试

## 1. 任务背景与核心目标
- **任务目标**：用 numpy 实现论文 Example I 的解析本构（modified Neo-Hookean，
  论文 Eq.(33)，已从 PDF p.11 视觉核验），并通过"解析 **S** vs 对 Ψ 数值/autodiff
  求导"的一致性测试。这是 Phase 1A 的数学地基：PANN 训练数据的应力标签、
  后续 PANN 精度验收的参考解都来自它。
- **业务背景**：v2 计划 §1.1。GPT 审查 P0-1 指出 v1 用的 Simo–Taylor 形式不是
  论文式，本任务必须实现论文原式，不得替换。

## 2. 输入依赖与先决条件
- **前置依赖任务**：无。
- **输入物料路径**（只读）：
  - `docs/method_notes.md`（"Example I reference law — Eq.(33)" 节，有精确式）
  - `docs/reproduction_plan_review_2026-10-05.md` §1.1
- **前置就绪检查**：`python3 -c "import numpy"` 成功（系统 python 有 numpy 1.26.4，
  不需要 torch；如需 autodiff 用数值差分即可）。

## 3. 写入范围与交付路径约束
- **Git 工作区**：
  - 隔离方式：`worktree`
  - 基线分支与 commit：`main` @ `b03c36a`
  - 工作者专属分支：`worker/T03-w1`
  - worktree 绝对路径：`/home/hatch/workspace/yade-rve-pann/.worktrees/T03/w1`
- **工作者专属沙盒**：`for_worker/T03/w1/`
- **正式文件直写授权**：
  - `examples/ex1_neohooke/neohooke.py`（新建：Eq.(33) 实现，函数签名
    `S = pk2_stress(F, E, nu)`，`E` 单位 MPa；另提供 `psi(F, E, nu)` 用于交叉验证）
  - `examples/ex1_neohooke/test_neohooke.py`（新建，自测脚本）
- **预期最终交付物**：
  - `examples/ex1_neohooke/neohooke.py`
  - `examples/ex1_neohooke/test_neohooke.py`
  - `for_manager/T03/w1/handoff.md`

## 4. 验收标准与完成定义 (DOD)
1. [ ] **功能指标**（论文式，参数 κ=E/(3(1−2ν))，η=E/(2(1+ν))）：
   - **S** = **F**⁻¹·( κ·lnJ·**F**⁻ᵀ + η·(J^(−2/3)·**F** − tr(J^(−2/3)·**C**)/3·**F**⁻ᵀ ) )
   - F=I ⇒ **S**=0（容差 1e-12）
   - **S** 对称（‖S−Sᵀ‖/‖S‖ < 1e-12）
   - 数值验证：对 Ψ(F)=κ/2·(lnJ)²+η/2·(Ī₁−3) 做中心差分得 ∂Ψ/∂**C**，
     2·∂Ψ/∂**C** 与解析 **S** 相对误差 < 1e-6（随机 20 组 F，H_ij∈[−0.2,0.2]）
   - 单轴拉伸 F=diag(1.2,1,1)：S₁₁>0，量级与 E·0.2 同阶
2. [ ] **格式与规范**：docstring 注明公式来源（论文 Eq.(33)，PDF p.11 视觉核验）
3. [ ] **自测命令与预期证据**：
   - `cd /home/hatch/workspace/yade-rve-pann/.worktrees/T03/w1 && python3 examples/ex1_neohooke/test_neohooke.py`
   - 预期：退出码 0，打印各项检查的最大相对误差，全部通过

## 5. 已知陷阱与注意事项
- J^(−2/3) 中 J=det(F) 必须 >0；测试 F 保证 J>0。
- 不要用 Simo–Taylor 或其他 Neo-Hooke 变体替代；如需对比只能另起文件并标注。
- 不要修改 `for_user/`、看板、WORKLOG（只读）。
