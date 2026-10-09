# T09 — 3D 宏观 BVP + UQ 流水线（Example I 的 3D analogue）

## 这是什么

把 2D T08 流水线搬到 3D：8×8×t m 板、中心通孔（r=2 m），全 3D Eq.(33)
Neo-Hookean（**不做**平面应力凝聚），3D KL 随机场，Monte Carlo + 论文停止规则，
对比参考解 vs PANN 的 q99 —— 方法论与论文 Fig. 7 完全一致。

**诚实标注**：这是论文 3D FEAP 宏观问题的 *analogue*，不是复刻。
差异：手写结构化六面体网格（非 FEAP）、解析本构参考解（非 FEM RVE）、
PANN 在面外剪切状态下为轻度外推（见 §6）。q99 的**相对误差**结论可比，
绝对 q99 值不对标论文。

## 目录

| 文件 | 说明 |
|---|---|
| `macro3d/mesh3d.py` | 结构化六面体网格：极坐标混合层（圆孔→方板）×厚度挤出；`box_mesh` 供 patch test |
| `macro3d/constitutive3d.py` | 3D Eq.(33) 参考本构 + PANN 本构接口 + 批量前向差分材料切线 |
| `macro3d/solver3d.py` | hex8 全拉格朗日求解器：自适应载荷步进 + Newton + 回溯线搜索（镜像 2D `macro/solver.py`） |
| `macro3d/kl3d.py` | 3D KL 随机场（E：σ=1000 MPa/lc=1 m；ν：μ=0.3/σ=0.03/lc=2 m） |
| `macro3d/uq3d.py` | 采样 → 单样本求解 → QoI（σ_char，定义与 2D 一致，论文 Eq.32）→ 串行 MC |
| `run_3d.py` | 并行 MC 驱动：论文停止规则 + common RNG + 断点续跑（final npz 跳过 + 批内 checkpoint） |
| `validate_3d.py` | 五项验证（V0–V4），见 §5 |

## 环境要求

- 本仓库 worktree（提供 `macro/`、`surrogate/`）
- Python venv：`numpy`、`scipy`、`torch`（与 2D T08 相同环境即可）
- PANN checkpoint：`for_worker/T04b/w1/pann_v2.pt`（main checkout 下），
  用 `--pann-ckpt` 指定，**不要**硬编码 worktree 相对路径
- 不需要 gmsh（网格手写生成）

## 快速开始（在你的高配机器上）

```bash
cd <worktree>   # 含 3d/ 的 checkout
VENV=~/workspace/venvs/rve-pann   # 或你自己的环境

# 1) 验证（约几分钟，单进程）
nice -n 19 $VENV/bin/python -u 3d/validate_3d.py | tee 3d/validation.log

# 2) 全量：2 个 mu × {ref, pann} = 4 runs，后台跑
nohup $VENV/bin/python 3d/run_3d.py \
  --mu 2.8e4 --mu 3.2e4 --constitutive both \
  --theta 32 --nr 6 --nz 4 --thickness 1.0 \
  --pann-ckpt ~/workspace/yade-rve-pann/for_worker/T04b/w1/pann_v2.pt \
  --workers 8 --outdir 3d/output \
  >> 3d/run_3d.log 2>&1 &
```

VM/机器重启后直接重跑同一命令：已收敛的 run 自动跳过，
未完成的 run 从 checkpoint 续跑（`resuming at N=...`）。

## 参数说明

| 参数 | 默认 | 说明 |
|---|---|---|
| `--mu` | 2.8e4, 3.2e4 | 区间参数 μ_E^i [MPa]，可重复指定 |
| `--constitutive` | both | `ref` / `pann` / `both` |
| `--n0/--dn/--ncap` | 10000/2000/40000 | 论文 MC 规则：首批 N0，续抽 dN，q99 五步稳定 <0.5% 停止 |
| `--theta/--nr/--nz` | 32/6/4 | 网格：角向/径向/厚度分段 |
| `--thickness` | 1.0 | 板厚 t [m] |
| `--kl-h/--kl-nz` | 0.5/3 | KL 参考网格间距 / z 层数 |
| `--pann-ckpt` | （见上） | PANN checkpoint 路径 |
| `--workers` | 2 | 并行 worker 数（建议 = 物理核数） |
| `--intra-ckpt` | 500 | 批内 checkpoint 间隔（样本数） |
| `--tag/--outdir` | full3d/3d/output | 输出名前缀 / 目录 |

## 资源预估方法

总耗时 ≈ 4 runs × N_run × t_sample / n_workers，其中：

- **t_sample**：单样本 3D 求解耗时。先跑一个常 E/ν 单样本实测
  （`validate_3d.py` V2 会打印），再乘以 1.5–2（含随机场采样、PANN 切线、
  偶发 fallback 的开销）。
- **N_run**：论文停止规则下每 run 约 1–2 万样本（2D 全量实测 2.2 万）。
- 网格加细时，t_sample 近似按自由度数 ×1.2–1.5 次方增长（稀疏直接求解器）。

### 实测锚点（本机 2 vCPU）

| 网格 | hex | dofs | 单样本 ref | 单样本 PANN |
|---|---|---|---|---|
| θ=16/r=3/z=2 | 96 | 576 | **5.7 s** | **12.7 s** |
| θ=32/r=6/z=2 | 384 | 2016 | 25 s | — |
| θ=48/r=8/z=3 | 1152 | 5184 | 116 s | — |

默认网格（θ=32/r=6/z=4，768 hex，3360 dofs）外推：ref **~60 s**/样本，
PANN **~130 s**/样本（PANN/ ref ≈ 2.2，V2 实测）。

全量估算（每 run ~2 万样本，按论文停止规则；2D 全量 run1 实测 2.2 万）：

- 2 个 ref run：2 × 20000 × 60 s ≈ 667 h
- 2 个 PANN run：2 × 20000 × 130 s ≈ 1444 h
- 合计 ≈ 2111 CPU·h；**8 worker ≈ 11 天，32 worker ≈ 2.8 天**

> 结论：本机 2 核跑全量不可行（见下），请在高配机器上运行。

### 为什么本机（2 vCPU）跑不动全量

- 2111 CPU·h ÷ 2 核 ≈ **44 天**——且本机还在跑 2D 全量，实际更久。
- 对比：2D 全量单样本 ~2.5 s，本机 ~20 小时跑完 4 runs；
  3D 默认网格单样本 ~60 s（ref），直接慢 24 倍，PANN 更慢（~130 s）。
- 内存倒不是瓶颈（KL streams 4 万样本约 58 MB，见 V3）。

## 验证（V0–V4，本机已跑，见 `validation.log`）

- **V0**：FD 材料切线 vs 中心差分，相对误差 <1e-6
- **V1**：3D patch test（box 网格，全边界面仿射 Dirichlet），数值 S vs 解析 Eq.(33)，相对误差 <1e-8
- **V2**：板孔单样本（常 E/ν）Newton 收敛、σ_char 有限、SCF 合理；PANN 单样本 σ_char 与参考解偏差 <8%
- **V3**：3D KL 采样 10 个实现，无崩溃、有限、有界
- **V4**：N0=50 mini-MC，kill -9 后 resume 样本数连续（N=75 无断档/重复）

## 已知局限（analogue 诚实声明）

1. **体积锁定**：全积分 hex8 在 ν→0.39 时有轻度体积锁定倾向；
   QoI 是相对误差（ref vs PANN 同网格），一阶抵消，但绝对 σ_char 偏刚。
2. **PANN 外推**：PANN 训练于（近）平面应力状态；3D 的面外剪切分量是轻度外推。
   V2 显示单样本偏差 <8%，UQ 级别的 q99 误差以全量为准。
3. **网格**：混合层在 45° 对角线处单元有拉伸（min detJ>0 已检查），非 FEAP 等价。
4. **厚度**：默认 t=1 m 薄板，3D 效应弱，更接近平面应力；加厚请重测 t_sample。
