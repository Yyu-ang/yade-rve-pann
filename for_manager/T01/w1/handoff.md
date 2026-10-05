---
schema: academic-project-worker-handoff/v1
task_id: "T01"
worker_id: "w1"
worker_status: COMPLETED  # COMPLETED | INCOMPLETE_HANDOFF
---

# Worker Handoff — T01

## 指派目标与验收标准
- 目标：核验 YADE 周期单胞应力均匀化链（getStress() → Cauchy σ → S=J·F⁻¹·σ·F⁻ᵀ）与 Hill-Mandel 功率一致性（Phase 0 门禁 G1a/G1b）。
- 验收标准（DOD，见 for_manager/T01/dispatch.md）：
  1. F=I 弛豫 packing：||S||/E < 5e-4（无映射引入的虚假应力）
  2a. 单轴拉伸 F=diag(1.1,1,1) 准静态：S 对称（+ 无黏结 DEM 拉伸行为记录）
  2b. 单轴压缩 F=diag(0.9,1,1) 准静态：S 对称，S₁₁<0
  3. Hill-Mandel：C1 独立 σ=(1/V)Σf⊗l vs getStress()；C2 虚功 |V₀P:dF − Σf·(dF·L₀)|/scale < 1%

## 状态与已完成项
- **工作者状态**：`COMPLETED`
- 已完成项：
  - `rve/homogenize.py`：实现 `set_reference_hsize`、`get_deformation_gradient`（F=hSize·hSize0⁻¹）、`deformation_invariants`（I1/I2/I3）、`cauchy_to_pk2`（S=J·F⁻¹·σ·F⁻ᵀ，论文 Eq.(3)）、`homogenized_stress`、`s_voigt`、`probe_F`（准静态驱动，**修正**：每增量对颗粒做仿射携带，避免直接改 hSize 导致周期边界瞬移）。
  - `rve/tests/test_stress_mapping.py`：自测脚本，DOD 全过（证据见下）。

## Git 工作区与资源交接
- 隔离方式：worktree
- 分支与基线 commit：`worker/T01-w1`，基线 `main @ b03c36a`
- worktree 绝对路径：`/home/hatch/workspace/yade-rve-pann/.worktrees/T01/w1`
- 最终工作树状态：`M rve/homogenize.py`，`?? rve/tests/`（新测试目录）。未 commit，未 push（按纪律）。

## 交付物
- `rve/homogenize.py`（worktree 内）：周期单胞均匀化工具链（含 probe_F 仿射修正）。
- `rve/tests/test_stress_mapping.py`（worktree 内）：T01 自测脚本，可复现全部 DOD 证据。
  运行：`cd /home/hatch/workspace/yade-rve-pann/.worktrees/T01/w1 && /usr/bin/yadedaily -x rve/tests/test_stress_mapping.py`

## 自测与证据
- 命令：`/usr/bin/yadedaily -x rve/tests/test_stress_mapping.py`（worktree 根目录，~20 秒，1000 颗粒，seed=42）
- 实际结果（2026-10-05，yadedaily 20260929-9582，日志 `for_worker/T01/w1/test_run7.log`）：
  - check1：F=I，max|S|=8.89e+01 Pa，**||S||/E=8.9e-06** < 5e-4 ✓
  - check3-C1：1136 接触，独立 Love-Weber vs getStress()，**rel=7.5e-18** < 1e-6 ✓（机器精度）
  - check3-C2：Hill-Mandel 虚功，uniax/shear/vol @F=I 及 uniax @压缩态，**max rel=2.2e-15** < 1e-2 ✓（机器精度）
  - check2b：F=diag(0.9,1,1)，S₁₁=-1.44e5 Pa **<0** ✓，对称性 asym/smax=2.3e-5 < 1e-4 ✓；I1=2.81, I2=2.62, I3=0.81 与解析值一致 ✓
  - check2a：F=diag(1.1,1,1)，S₁₁=0.0（无黏结 DEM 拉伸即开裂，x 向接触打开，**物理正确响应**，已在脚本中注明；符号约定由压缩态实质验证）✓
  - `ALL ASSERTS PASSED`，EXIT:0

## 未完成项、阻塞与接续步骤
- 未完成项：无
- 阻塞：无
- 接续步骤：管理员验收后可并入 main；T02 可开工（Phase 0 门禁已通）。
- WIP 路径：`/home/hatch/workspace/yade-rve-pann/for_worker/T01/w1/`（调试脚本 scratch*.py、test_run*.log，为过程材料）

## 需管理员核验
- 自测日志 `for_worker/T01/w1/test_run7.log` 中的数值与上文一致。
- `rve/homogenize.py` 的 probe_F 仿射修正在 worktree 内 diff 可见。

## 关键技术发现（供 T02 及后续参考）
1. **YADE getStress() 符号约定**：压缩为负。双颗粒标定证实 getStress = −(f_id2⊗l)/V，即其 Love-Weber 求和用的是 id1 受力（或等价地带负号）。独立验证时须用 `-(normalForce+shearForce)` 才能达到机器精度一致。
2. **直接改 O.cell.hSize 不带动颗粒**：周期边界处颗粒会瞬移。densify 与 probe_F 均须对颗粒位置做仿射变换（x_new = F_incr·x_old）。
3. **Hill-Mandel 虚功须用参考分支 L₀=F⁻¹·l**：在 F≠I 态若误用当前 l，压缩态误差达 10%；修正后机器精度。
4. **致密 packing 不可在零压下长时弛豫**：周期无重力体系会自发团聚开裂（1306 接触→16 接触）。策略：densify 到 ~1200 接触即停（此时 ||S||/E~1e-5 已满足 DOD），仅短时（500 步）弛豫暂态。
5. **无黏结 DEM 拉伸 S₁₁≈0 是物理正确**，非 bug；DOD-2a 按派发单原样实现拉伸并如实记录，另加 2b 压缩实质验证符号。
