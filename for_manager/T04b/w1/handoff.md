---
schema: academic-project-worker-handoff/v1
task_id: "T04b"
worker_id: "w1"
worker_status: COMPLETED  # COMPLETED | INCOMPLETE_HANDOFF
---

# Worker Handoff — T04b

## 指派目标与验收标准
- 目标：修复 T04 已验收 PANN 在定义域角点 (E=3.5e4, ν=0.39) 系统性低估 S₁₁
  达 5.56% 的问题（根因：κ=E/(3(1−2ν)) 在 ν→0.39 处陡峭约 7×，均匀 LHS
  欠采样边界），使 T05 区间 max DOD（<3%）可通过。不放宽任何 DOD。
- 验收标准（DOD，见 for_manager/T04b/dispatch.md）：
  1. 测试集应力相对 L2 < 5% 无回归（目标 ≤2%）
  2. F=diag(1.1,1,1) 下四角点 (E,ν)∈{2.5e4,3.5e4}×{0.21,0.39} 的 S₁₁ 相对误差全 <3%
  3. 用新 checkpoint 按 T05 方法重验区间 max <3%
  4. 自测退出码 0（含新增角点断言）

## 状态与已完成项
- **工作者状态**：`COMPLETED`
- 已完成项：
  - `surrogate/train_pann.py`（修改）：新增 `generate_boundary_doe()`
    （25 个 U 样本 ν∈[0.33,0.39]×全 E 域 + 4 个精确角点，各 100 H-LHS 力学点
    → 2900 点，seed 固定）、`concat_doe()`、`build_augmented()`
    （边界点只进训练集；测试集 500 点与 T04 逐位一致）；`main()` 默认产物
    改为沙盒 `for_worker/T04b/w1/pann_v2.pt`。
  - `surrogate/tests/test_pann.py`（修改）：新增四角点断言（<3%）；
    训练后保存 `pann_v2.pt` + metrics 至沙盒。
  - 沙盒 checkpoint：`/home/hatch/workspace/yade-rve-pann/for_worker/T04b/w1/pann_v2.pt`
    （260 KB，git 外）。

## 策略选择理由（记录 per dispatch）
- 选 (a) DoE 边界增补。根因是**欠采样**（陡峭区缺数据）而非 loss 错误，
  故直接在目标陡峭处加数据是最诚实的修复。
- 拒 (b) loss 加权：稀疏样本上加权无法创造信息，易过拟合边界 few-shot。
- 拒 (c) 两阶段微调：引入额外超参，有灾难性遗忘风险，且近似"调参刷榜"。
- 单阶段、超参与 T04 完全一致（Adam lr=1e-3, 2000 epochs, batch=256,
  seed=42），无调参。

## 自测与证据（2026-10-05，torch 2.14.1+cpu，2 核，~18 分钟）
- 命令：`cd /home/hatch/workspace/yade-rve-pann/.worktrees/T04b/w1 && /home/hatch/workspace/venvs/rve-pann/bin/python surrogate/tests/test_pann.py`
- 日志：`for_worker/T04b/w1/test_run.log`，退出码 0，`ALL CHECKS PASSED`：
  - DOD① 测试集相对 L2 = **0.4516%** < 5% ✓（T04 为 1.51%，无回归且更优）
  - DOD② 四角点 S₁₁ 相对误差：(2.5e4,0.21) **0.2021%** ✓；
    (2.5e4,0.39) **1.8823%** ✓；(3.5e4,0.21) **1.5035%** ✓；
    (3.5e4,0.39) **1.1319%** ✓（原 −5.56%）
  - stress autograd-vs-FD：2.3e-09 ✓；tangent 对称性 2.3e-17/4.5e-16 ✓；
    tangent dS 预测 2.2e-09 ✓
- DOD③ 区间重验：`for_worker/T04b/w1/reverify_interval.py`
  （复用 T05 已验证的 `uq.material_uq.interval_uq`，仅换 checkpoint），
  日志 `for_worker/T04b/w1/reverify.log`，退出码 0：
  - 区间 max：PANN 5481.39 vs 解析 5544.14，rel **1.1319%** < 3% ✓（原 5.558%）
  - 区间 min：rel **0.2021%** ✓（无回归）
  - MC（信息性）：mean 0.5643% / std 0.0227% / q99 0.5513%，均 <3%

## Git 工作区与资源交接
- 隔离方式：worktree
- 分支与基线 commit：`worker/T04b-w1`，基线 `main @ 76bda73`
- worktree 绝对路径：`/home/hatch/workspace/yade-rve-pann/.worktrees/T04b/w1`
- 最终工作树状态：`M surrogate/train_pann.py`，`M surrogate/tests/test_pann.py`
  （仅派发单授权的两文件）。未 commit，未 push（按纪律）。
- WIP 路径：`/home/hatch/workspace/yade-rve-pann/for_worker/T04b/w1/`
  （`pann_v2.pt`、`metrics.json`、`loss_history.npz`、`scaler.npz`、
  `test_run.log`、`reverify.log`、`reverify_interval.py`）

## 未完成项、阻塞与接续步骤
- 未完成项：无（DOD 全过）。
- 接续：管理员验收后，可用 `pann_v2.pt` 重跑 T05 自测
  （`uq/tests/test_uq.py` 的 CKPT 指向新 checkpoint），预期 DOD 全过；
  T05 交付物（`uq/`）届时可正式验收。

## 需管理员核验
- 复核 `for_worker/T04b/w1/test_run.log` 尾部四角点数值与上表一致。
- 复核 `for_worker/T04b/w1/reverify.log` 的区间 max 1.1319%。
- 确认 `pann_v2.pt` 可被 `PANN.load()` 正常加载（reverify 已加载成功）。
