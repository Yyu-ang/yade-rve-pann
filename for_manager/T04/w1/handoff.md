---
schema: academic-project-worker-handoff/v1
task_id: "T04"
worker_id: "w1"
worker_status: COMPLETED  # COMPLETED | INCOMPLETE_HANDOFF
---

# Worker Handoff

## 指派目标与验收标准
- 目标：基于 T03 已验收的 Eq.(33) 解析本构，生成域分离 DoE（U 50 LHS × 力学域 100 LHS = 5000 点），训练 PANN Ψ(I,u)（5→175→175→1，softplus），测试集应力相对 L2 < 5%（项目内部阈值）。
- 验收标准（dispatch §4）：
  1. DoE 5000 点，(I₁,I₂,I₃,E,ν)→S（Voigt 6 分量），90/10 划分，seed 固定
  2. loss = mean‖Sᴺᴺ−Sʳᵉᶠ‖²（论文 Eq.(12)）
  3. 测试集应力相对 L2 < 5%
  4. `stress(C,u)` 与数值差分交叉检查通过
  5. 自测命令退出码 0 并打印 DOD 指标

## 状态与已完成项
- **工作者状态**：`COMPLETED`
- 已完成项：
  1. `surrogate/pann.py` 实现：PANN（5→175→175→1，softplus/linear），接口按 P0-4（`energy(I,u)`、`stress(C,u)`、`stress_F(F,u)`、`tangent(C,u)`）；输入仿射缩放到 [-1,1]，缩放进 autograd 图使链式法则自动成立；tangent 对 9-entry Hessian 做对称化以满足 minor 对称（dS=ℂ:dE，论文 Eq.(13)）
  2. `surrogate/train_pann.py` 新建：DoE 生成（scipy LHS，seed 42，det(F)≤1e-3 丢弃）+ 训练主脚本；产物落沙盒
  3. `surrogate/tests/test_pann.py` 新建：端到端自测（DoE→训练→断言→交叉检查）
  4. 沙盒产物：`for_worker/T04/w1/` 下 `doe.npz`、`pann.pt`、`scaler.npz`、`loss_history.npz`、`metrics.json`、`training_notes.md`

## Git 工作区与资源交接
- 隔离方式：worktree
- 分支与基线 commit：`worker/T04-w1`，基线 `main` @ `b03c36a`
- worktree 绝对路径：`/home/hatch/workspace/yade-rve-pann/.worktrees/T04/w1`
- 最终工作树状态：`M surrogate/pann.py`，`?? surrogate/train_pann.py`，`?? surrogate/tests/`（仅 3 个授权路径；未 commit/push，按纪律）
- 资源：torch 2.14.1+cpu 只读使用 `/home/hatch/workspace/venvs/rve-pann/bin/python`，未 pip install；T03 `examples/ex1_neohooke/neohooke.py` 只读引用（worktree 基线早于 T03 合并，从 main checkout 只读导入）

## 交付物
- `surrogate/pann.py`：PANN 实现（energy/stress/stress_F/tangent，save/load）
- `surrogate/train_pann.py`：DoE + 训练主脚本（`--epochs`、`--outdir`、`--seed`）
- `surrogate/tests/test_pann.py`：自测（DOD 命令）
- 沙盒（不进 git）：`for_worker/T04/w1/pann.pt`（260KB checkpoint，可 `PANN.load`）、`doe.npz`、`metrics.json` 等

## 自测与证据
- 命令：`/home/hatch/workspace/venvs/rve-pann/bin/python surrogate/tests/test_pann.py`（worktree 根目录）
- 实际结果（exit 0，`ALL CHECKS PASSED`）：
  - DoE：5000 点（50×100，n_skipped=0），train=4500 / test=500，seed=42
  - 训练：Adam lr=1e-3，batch=256，epochs=2000，耗时约 445–700 s（2 核）
  - 训练 loss（归一化 MSE）尾值：2.933e-05（500→1000→1500→2000 epoch：1.42e-03→2.33e-04→5.64e-05→2.93e-05）
  - **测试集应力相对 L2 = 1.5144% < 5%** ✅（DOD 通过；训练集 0.6155%）
  - stress autograd vs 能量中心差分：2.11e-09 / 3.20e-09 / 2.55e-09 ✅
  - tangent minor/major 对称性：4.54e-17 / 7.26e-16 ✅；dS=ℂ:dE 的 FD 验证：4.44e-10 ✅
- 超参（可复现）：seed=42（DoE/LHS/划分/训练全固定），hidden=(175,175)，lr=1e-3，batch=256，epochs=2000，torch 2.14.1+cpu，float64
- checkpoint 独立加载验证通过（8 个抽查样本相对误差 0.5%–3.4%）

## 实施中的两个 bug 及修复（记录供复核）
1. `torch.autograd.grad` 在 `torch.no_grad()` 下失败 → stress/tangent 改用 `torch.enable_grad()`；训练用 `create_graph=True` 保留到参数的梯度路径。
2. 自测 FD 交叉检查初版对角元扰动加了两次（`Cp[a,a]+=h` 执行两次）→ 修正为对角单次扰动；另 tangent 的 FD 验证约定为 dS=ℂ:dE（论文 Eq.(13)），初版误写成 dS=ℂ:dC（差因子 2，由 100% 误差反推定位）。

## 未完成项、阻塞与接续步骤
- 未完成项：无（DOD 全过）
- 阻塞：无
- 接续步骤：T05（多态 UQ）可直接使用 `for_worker/T04/w1/pann.pt`（`PANN.load`）与 `doe.npz`；`surrogate/train_pann.py` 支持 `--epochs` 调整重训
- WIP 路径：无（沙盒内均为最终产物说明与 checkpoint）

## 需管理员核验
- DOD 指标真实性（自测输出如上，可重跑验证，约 12 分钟）
- 三个交付文件是否在授权范围内（是：`surrogate/pann.py`、`surrogate/train_pann.py`、`surrogate/tests/test_pann.py`）
- 是否 ACCEPTED 并合入（由管理员执行 commit/push，本工作者未执行）
