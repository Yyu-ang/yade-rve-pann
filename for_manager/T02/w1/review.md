# Manager Review — T02
task_id: "T02"
worker_id: "w1"
verdict: ACCEPTED
reviewed_at: "2026-10-05"
reviewer_role: maintainer

## 独立复核
- 交接件 `for_manager/T02/w1/handoff.md` 已读。
- 在 worktree 独立运行门禁自测：`/usr/bin/yadedaily -x rve/tests/test_gates.py` →
  退出码 0（~6 分钟），门禁表数值与工作者报告逐项一致：
  G1c 闭合 7.89e-7（GO）、G1c 耗散 0.255（NO-GO）、G1c 路径无关 0.0349（GO）、
  G2a 0.0070（GO）、G2b Δ=4.9309%（NO-GO）。
- 抽查 `test_gates.py`：`_probe_F_history` 从当前 hSize 插值（run1 bug 已修正）、
  外力功 `_incremental_work` 用 V₀·P:dF 正确；耗散比为保守上界（含 damping），
  0.255≫0.10 结论不受影响。
- 纪律：仅修改授权三文件；容差未放宽；未 commit/push。

## 裁决：ACCEPTED（门禁本身成功执行，DEM 轨道判 NO-GO）
- **G1c 总体 NO-GO**：FrictMat 在 10% 压缩循环中宏观几乎可逆（残余 7.9e-7）且
  路径无关（3.5%），但微观摩擦滑移耗散 25% 外力功——单值 Ψ(C,u) 前提不成立。
  energy-PANN 路线对该接触模型**必须停止**（v2 计划硬门禁 G1）。
- **G2b NO-GO**：1000 颗粒 DEM 的 realization scatter Δ=4.93%，约为论文
  FEM 判据（0.5%）的 10 倍——RVE 尺寸效应，非 packing 错误。工作者拒绝放宽
  容差，正确。
- 交付物迁入正式路径：`rve/generate.py`、`rve/convergence.py`、
  `rve/tests/test_gates.py`（门禁基础设施，后续复用）。
- 工作者分支 `worker/T02-w1` 保留备查。

## 待定事项（需用户/计划级决策）
1. **bonded/cohesive 重测**（v2 计划首选 fallback）：消除摩擦滑移后重测 G1c。
   但 G2b 的尺寸效应与接触模型无关，1000 颗粒下 bonded 仍大概率卡在 Δ≤0.5%。
2. **已知潜在 bug**：`rve/homogenize.py::probe_F` 从参考 hSize 插值，
   非参考态调用会突变（T02 自带修正版 `_probe_F_history` 未动它）。
   若继续 DEM 轨道，需先修复；若关闭轨道，记入 method_notes 即可。
3. **分析轨道（T04/T05）不受影响**：Eq.(33) 解析基准 + PANN 训练继续。
