---
schema: academic-project-task-dispatch/v1
task_id: "T01"
title: "Phase 0 G1a/G1b：YADE 应力映射与 Hill-Mandel 功率一致性验证"
parent_goal: "Harazin et al. CMAME 2026 方法复现：DEM-RVE 适用性门禁（v2 计划 Phase 0）"
assigned_role: "Experiment Engineer (YADE DEM)"
assignee: "pending"
priority: HIGH
dispatch_status: DISPATCHED
created_at: "2026-10-05"
depends_on: []
---

# Task Dispatch: T01 - YADE 应力映射与 Hill-Mandel 验证

## 1. 任务背景与核心目标
- **任务目标**：核验 YADE 周期单胞的应力均匀化链：`getStress()` 体积平均 Cauchy 应力 σ → 第二类 Piola–Kirchhoff 应力 **S** = J·**F**⁻¹·σ·**F**⁻ᵀ（论文 Eq.(3)），包括符号约定、单位、体积平均的正确性；并数值验证 Hill–Mandel 功率一致性（论文 Eq.(9)：**P**:**Ḟ** = 体积平均细观功率）。
- **业务背景**：这是 v2 计划 Phase 0 门禁 G1a/G1b。后续一切 DEM-RVE 收敛性、PANN 训练数据的应力标签都依赖这条映射正确。不通过则 T02（超弹性门禁）不得开工。

## 2. 输入依赖与先决条件
- **前置依赖任务**：无。
- **输入物料路径**（只读）：
  - `docs/method_notes.md`（论文方法摘要）
  - `docs/reproduction_plan_review_2026-10-05.md` §1.3（Eq.(6) 标准式）
  - `rve/homogenize.py`（骨架，含接口说明）
- **前置就绪检查**：`which yadedaily` 存在且 `yadedaily --version` 可运行。

## 3. 写入范围与交付路径约束
- **Git 工作区**：
  - 隔离方式：`worktree`
  - 基线分支与 commit：`main` @ `b03c36a`
  - 工作者专属分支：`worker/T01-w1`
  - worktree 绝对路径：`/home/hatch/workspace/yade-rve-pann/.worktrees/T01/w1`
  - 大文件/数据/依赖/端口方案：无；yadedaily 为系统安装（/usr/bin），只读使用
- **工作者专属沙盒**：`for_worker/T01/w1/`（调试日志、中间输出）
- **正式文件直写授权**：
  - `rve/homogenize.py`（实现 `deformation_invariants(F)`、`homogenized_stress()`、`probe_F()`）
  - `rve/tests/test_stress_mapping.py`（新建，自测脚本）
- **预期最终交付物**：
  - `rve/homogenize.py`： verified 的应力映射实现
  - `rve/tests/test_stress_mapping.py`：可重复运行的自测
  - `for_manager/T01/w1/handoff.md`：标准化交接（含测试证据）

## 4. 验收标准与完成定义 (DOD)
1. [ ] **功能指标**：
   - 未变形周期单胞（F=I，充分弛豫后）：‖**S**‖ ≈ 0（容差 1e-6 相对量级）
   - 单轴拉伸（如 F=diag(1.1,1,1)，准静态）：**S** 对称，S₁₁>0（拉为正），量级合理
   - Hill–Mandel：| **P**:**Ḟ** − ⟨细观功率⟩ | / 尺度 < 1%
2. [ ] **格式与规范**：函数有 docstring，注明论文公式出处（Eq.(3)/Eq.(9)）
3. [ ] **自测命令与预期证据**：
   - `cd /home/hatch/workspace/yade-rve-pann/.worktrees/T01/w1 && yadedaily -x rve/tests/test_stress_mapping.py`
   - 预期：退出码 0，所有 assert 通过，打印三项检查的数值残差

## 5. 已知陷阱与注意事项
- YADE 无显示器环境跑脚本：用 `yadedaily -x <script>`（-x 表示跑完退出，避免卡在 IPython）。
- `getStress()` 返回的是 Cauchy 应力的体积平均；注意 YADE 压缩为负、拉伸为正的符号约定，文档中明确记录。
- 2 核机器，单胞颗粒数控制在 ~1500 以内，单次测试分钟级完成。
- 不要修改 `for_user/`、`PROJECT_DASHBOARD.md`、`WORKLOG.md`（只读）。
