---
schema: academic-project-worker-handoff/v1
task_id: "T02b"
worker_id: "w1"
worker_status: COMPLETED  # COMPLETED | INCOMPLETE_HANDOFF
---

# Worker Handoff — T02b

## 指派目标与验收标准
- 目标：T02 判 FrictMat 因摩擦耗散 25% 而 G1c NO-GO；按 v2 计划 fallback #1，
  用 bonded（CohFrictMat）接触重测，检验 energy-PANN 超弹性前提是否成立。
- 验收标准（DOD，见 for_manager/T02b/dispatch.md）：
  1. probe_F 插值 bug 已修（T02 卸载路径回归验证）
  2. G1c 重测：残余 <1e-3；路径无关 <5%；耗散比 <10%（主判据）；断键=0
  3. G2a/G2b 信息性复测（数值如实报告）
  4. `yadedaily -x rve/tests/test_gates.py` 退出码 0
  5. 交接件含 GO/NO-GO + 与 T02 对比表

## 状态与已完成项
- **工作者状态**：`COMPLETED`
- 已完成项：
  - `rve/homogenize.py`：修复 `probe_F` 从参考 hSize 插值的 bug，
    改为从当前 hSize 插值（与 `test_gates._probe_F_history` 的修正一致）；
    回归脚本 `for_worker/T02b/w1/regress_probeF.py` 验证卸载段完全平滑
    （max/mean 跳变比 1.00），终态回到参考 hSize。
  - `rve/generate.py`：FrictMat → CohFrictMat（`Ig2_Sphere_Sphere_ScGeom6D` +
    `Ip2_CohFrictMat_CohFrictMat_CohFrictPhys` +
    `Law2_ScGeom6D_CohFrictPhys_CohesionMoment`）；cohesion 经 `u["cohesion"]`
    参数化（默认 1e6 N）；`fragile=False` 使断键以摩擦接触留存可计数；
    新增 `establish_reference_bonds()`（densify 无键 → 参考态
    `setCohesionNow` 统一建键 → 冻结键拓扑）与 `count_broken_bonds()` /
    `BONDED_IDS`（仅统计参考键集中的新增断裂）。
  - `rve/tests/test_gates.py`：复用门禁，新增断键计数（build/load/unload/
    pathA/pathB），docstring 与汇总表更新为 bonded。
  - 前置检查：`yadedaily -x rve/tests/test_stress_mapping.py` 通过
    （T01 自测，修复后仍全过）。

## Git 工作区与资源交接
- 隔离方式：worktree
- 分支与基线 commit：`worker/T02b-w1`，基线 `main @ 4013e51`
- worktree 绝对路径：`/home/hatch/workspace/yade-rve-pann/.worktrees/T02b/w1`
- 最终工作树状态：`M rve/homogenize.py`，`M rve/generate.py`，
  `M rve/tests/test_gates.py`（仅派发单授权的三文件）。未 commit，未 push。

## 自测与证据（2026-10-05，yadedaily 20260929-9582，1000 颗粒双相 bonded
## packing，vf≈0.19，E_soft=1e7 Pa，cohesion=1e6 N，1416 参考键）

| 门 | T02b bonded 测量值 | T02 FrictMat | DOD 阈值 | T02b 判定 |
|---|---|---|---|---|
| G1c 闭合 | 卸载残余 ‖S‖/E = **1.41e-3** | 7.89e-7 | < 1e-3 | **NO-GO**（1.4× 超标，边缘） |
| G1c 耗散 | 迟滞耗散/加载功 = **0.162** | 0.255 | < 0.10 | **NO-GO** |
| G1c 路径无关 | ‖S_A−S_B‖/‖S_A‖ = **0.0197** | 0.0349 | < 0.05 | **GO** |
| G1c 断键 | build/load/unload/pathA/pathB = **0/0/0/0/0** | n/a | 0 | **GO** |
| G1c 总体 | — | NO-GO | — | **NO-GO**（耗散；闭合边缘超标） |
| G2a 各向同性 | spread = **0.0510** | 0.0070 | < 0.10 | **GO**（信息性） |
| G2b 代表性 | 5 seeds Δ = **3.62%** | 4.93% | ≤ 0.5% | **NO-GO**（信息性，尺寸效应） |

- 命令：`/usr/bin/yadedaily -x rve/tests/test_gates.py`（worktree 根目录，
  ~4 分钟），`GATES DONE`，EXIT:0；日志
  `for_worker/T02b/w1/gates_bonded_run1.log`。
- **总体结论**：bonded fallback **未能挽救** energy-PANN 前提 ——
  G1c 在 10% 应变域仍判 NO-GO（耗散 16% > 10%；闭合 1.4× 边缘超标）。
  容差未放宽。

## 关键技术发现（物理机制，已多轮诊断确认）
1. **bonded 消除了摩擦耗散与损伤**：`frictDissip` 求和 = 0，参考键零断裂
   （cohesion=1e6 N 在 10% 压缩域内不断键；断键数不随 cohesion 1e6→1e8
   变化，证实阈值已远高于局部力）。
2. **剩余耗散来自有限应变下的接触拓扑回滞**，不是摩擦/损伤：10% 压缩中新
   形成 ~640 个无键摩擦接触，卸载后 ~55 个卡住不分离，packing 陷入自应力
   态（maxPen ~3e-3）。这是 DEM 在有限应变下的内禀行为，cohesion 无法消除。
3. **键必须在参考态统一建立**：densify 中陆续成键 → 键静息构型是变形态 →
   卸载出现 +9.8e4 Pa 拉应力、耗散比 2.16（pilot_run3）。`setCohesionNow`
   在平衡好的参考态统一建键后耗散比降至 0.162。erase/reform 退火会松弛
   packing（软 toe），不如原位建键。
4. **YADE 坑**：`Ip2_CohFrictMat_...` 的 `setCohesionOnNewContacts` 默认为
   False（不设则键永不建立，`cohesionBroken` 恒 True）；`CohFrictPhys` 无
   `isBroken()`，用 `cohesionBroken` 属性；`normalAdhesion` 由 Ip2 按粒径
   换算（r=0.05 时 1e6 N → 2500 N）；`count_broken_bonds` 必须限定在参考键
   集内，否则会把加载中新生的摩擦接触误计为断键。
5. **G2b 3.62% vs 4.93%**：bonded 略好但仍为判据 7×，1000 颗粒 DEM 尺寸效应
   与接触模型无关（T02 结论维持）。

## 未完成项、阻塞与接续步骤
- 未完成项：无（全部 DOD 执行完毕，有明确 verdict）。
- 阻塞：无。
- 接续建议（按 v2 计划 §3，bonded 已失败）：
  1. 转带历史变量的 surrogate 并明确声明超出原论文方法（需管理员/用户决策）；
  2. 或将 DEM 轨道记为有充分证据的阴性结果后关闭（T02+T02b 证据链完整）。
- WIP 路径：`/home/hatch/workspace/yade-rve-pann/for_worker/T02b/w1/`
  （`pilot_run*.log`、`diag*_run1.log`、`sweep_run1.log`、
  `regress_probeF.py`、`pilot_bonded.py`、`diag_bonded.py`、
  `diag2_bonded.py`、`diag3_bonded.py`、`sweep_cohesion.py`、
  `probe_cohesion.py`、`check_*.py`）。

## 需管理员核验
- 复核 `gates_bonded_run1.log` 尾部门禁表与上表一致。
- `rve/homogenize.py::probe_F` 的插值修正（本次 DOD-1 要求）。
- 裁决 DEM 轨道后续：历史变量 surrogate vs 记为阴性结果关闭。
