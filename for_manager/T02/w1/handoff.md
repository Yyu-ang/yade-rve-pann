---
schema: academic-project-worker-handoff/v1
task_id: "T02"
worker_id: "w1"
worker_status: COMPLETED  # COMPLETED | INCOMPLETE_HANDOFF
---

# Worker Handoff — T02

## 指派目标与验收标准
- 目标：Phase 0 生死门禁 —— 判定 YADE DEM（FrictMat 双相 packing，周期单胞）
  是否满足论文式 energy-PANN 的超弹性前提：G1c（加载–卸载闭合、路径无关、
  耗散占比）、G2a（各向同性）、G2b（代表性，Δ≤0.5%）。门禁只在压缩/剪切域
  判定（FrictMat 无黏结，拉伸 S≈0 为物理正确，不测）。
- 验收标准（DOD，见 for_manager/T02/dispatch.md）：
  1. G1c：残余 ‖S‖/E < 1e-3；两条路径应力相对差 < 5%；耗散比 < 10%
  2. G2a：x/y/z 单轴压缩等效刚度相对差 < 10%
  3. G2b：固定 u 下 ≥5 seeds，Δ = std(‖S‖)/mean(‖S‖) ≤ 0.5%
  4. `yadedaily -x rve/tests/test_gates.py` 退出码 0，打印门禁表
  5. 任一门禁超标记 NO-GO 并如实报告数值，不放宽容差

## 状态与已完成项
- **工作者状态**：`COMPLETED`
- 已完成项：
  - `rve/generate.py`：实现双相（硬夹杂/软基体）周期 packing 生成
    `make_rve_packing()`，复用 T01 densify/affine 经验并改进为两阶段
    应力伺服致密（见关键技术发现 1）。
  - `rve/convergence.py`：实现 `representativeness_test()`（固定 u、
    多 seed、Δ 采用 §1.2 变异系数定义）；P0-5 变量分离
    （`N_REP_SEEDS` vs 机械域 LHS，后者归属 sampling/）。
  - `rve/tests/test_gates.py`：新建门禁自测，实现 `_probe_F_history`
   （逐增量记录 F/S/σ/J 的仿射准静态探针）与 `_incremental_work`
   （V₀·P:dF 外力功积分）；G1c/G2a/G2b 全量执行，退出码 0。
  - 前置检查：`yadedaily -x rve/tests/test_stress_mapping.py` 通过
    （ALL ASSERTS PASSED）。

## Git 工作区与资源交接
- 隔离方式：worktree
- 分支与基线 commit：`worker/T02-w1`，基线 `main @ d1858a5`
- worktree 绝对路径：`/home/hatch/workspace/yade-rve-pann/.worktrees/T02/w1`
- 最终工作树状态：`M rve/generate.py`，`M rve/convergence.py`，
  `?? rve/tests/test_gates.py`（仅派发单授权的三个文件）。未 commit，未 push（按纪律）。

## 交付物
- `rve/generate.py`（worktree 内）：双相 RVE packing 生成器。
- `rve/convergence.py`（worktree 内）：代表性测试。
- `rve/tests/test_gates.py`（worktree 内）：门禁自测，
  运行：`cd /home/hatch/workspace/yade-rve-pann/.worktrees/T02/w1 && /usr/bin/yadedaily -x rve/tests/test_gates.py`
- 日志：`for_worker/T02/w1/gates_run2.log`（有效结果），
  `for_worker/T02/w1/gates_run1.log`（作废：卸载插值 bug，见发现 2）。

## 自测与证据（2026-10-05，yadedaily 20260929-9582，1000 颗粒双相 packing，vf≈0.19，E_soft=1e7 Pa）

| 门 | 测量值 | DOD 阈值 | 判定 |
|---|---|---|---|
| G1c 闭合 | 卸载残余 ‖S‖/E = **7.89e-7** | < 1e-3 | **GO** |
| G1c 耗散 | 迟滞耗散/加载功 = **0.255** | < 0.10 | **NO-GO** |
| G1c 路径无关 | ‖S_A−S_B‖/‖S_A‖ = **0.0349** | < 0.05 | **GO** |
| G1c 总体 | — | — | **NO-GO**（耗散） |
| G2a 各向同性 | 刚度 spread = **0.0070**（kx=8.086e6, ky=8.072e6, kz=8.129e6 Pa） | < 0.10 | **GO** |
| G2b 代表性 | 5 seeds Δ = **4.9309%**（‖S‖: 9.09e5–1.01e6 Pa） | ≤ 0.5% | **NO-GO** |

- 命令：`/usr/bin/yadedaily -x rve/tests/test_gates.py`（worktree 根目录，~4 分钟）
- `GATES DONE`，EXIT:0；门禁表已打印（`gates_run2.log` 尾部）。
- **总体结论**：Phase 0 **NO-GO** —— FrictMat DEM 不满足 energy-PANN 的超弹性
  前提（耗散比超标 2.5×；代表性 scatter 超标 ~10×）。容差未放宽。

## 未完成项、阻塞与接续步骤
- 未完成项：无（全部 DOD 执行完毕，有明确 verdict）。
- 阻塞：无。
- 接续建议（按派发单 §1 备选路径）：
  1. 用 bonded/cohesive 接触重测 G1c（消除摩擦滑移耗散）—— 若通过则 DEM 可进入
     energy-PANN 适配；`rve/generate.py` 的材料/引擎段需替换，门禁脚本复用。
  2. 若仍失败：改用带历史变量的 surrogate，并明确声明超出原论文方法（v2 计划 §3）。
  3. G2b 的 Δ≤0.5% 对 1000 颗粒 DEM 过严是尺寸效应；若坚持该阈值，需更大 RVE
    （超出本机 2 核/30 分钟预算）或放宽为 DEM-specific 判据（需用户/管理员决策，
     工作者无权放宽）。
- WIP 路径：`/home/hatch/workspace/yade-rve-pann/for_worker/T02/w1/`（`gates_run*.log`）。

## 需管理员核验
- 复核 `gates_run2.log` 尾部门禁表数值与上表一致。
- 确认 `rve/tests/test_gates.py` 的 `_probe_F_history` 修正（发现 2）正确。
- 裁决后续：bonded 重测 还是 转历史变量 surrogate。

## 关键技术发现（供后续参考）
1. **致密两阶段应力伺服**：jamming 点附近接触数对体积应变极敏感（一次 0.97
   步：1198→2638 接触，预应力 ‖S‖/E~4e-2）。改用粗步 0.97 至渗流起始 +
   细步 0.997 并以 |mean σ|/E≥1e-4 伺服停止，使 F=I 参考态预应力 ~1e-4·E，
   G1c 闭合门禁才有意义（否则残余应力被预应力淹没）。
2. **探针插值 bug（已修）**：`_probe_F_history` 初版从参考 hSize 而非当前
   hSize 插值，导致卸载/多阶段路径首增量突变（run1 的耗散比=1.000、G2a
   spread=40% 均为此 bug 污染，已作废）。注意 `rve/homogenize.py::probe_F`
   有同样潜在问题（非本次授权文件，未改；T01 用法均从 F=I 出发故未触发）——
   后续若在非参考态调用 probe_F 需先修复。
3. **G2a 方法**：x/y/z 三方向各用同 seed 全新 packing（相同初始微结构），
   方向差异即纯各向异性；spread 仅 0.7%，packing 统计各向同性良好。
4. **耗散比为保守上界**：迟滞回线面积计量的是总机械耗散（含 NewtonIntegrator
   damping），摩擦耗散 ≤ 该值；0.255 已远超 0.10，结论不受此保守性影响。
   物理图像：10% 压缩循环宏观可逆（残余 7.9e-7）但微观摩擦滑移耗散 25% 功——
   正是 energy-PANN 单值 Ψ(C,u) 前提所不容的。
5. **G2b 4.93% 的含义**：1000 颗粒 DEM 的 realization scatter 约为论文 FEM
   判据的 10 倍；这是 RVE 尺寸效应，不是 packing 生成错误（5 seeds 的 ‖S‖
   单调分布 9.09e5–1.01e6 Pa，无异常值）。
