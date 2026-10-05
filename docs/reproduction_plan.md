# 复现计划 — Harazin et al., CMAME 452 (2026) 118726

> Multiscale polymorphic uncertainty quantification based on physics-augmented neural networks

本文档是复现工作的执行计划。方法细节见 `docs/method_notes.md`。

## 1. 复现目标（Scope 界定）

**复现的是方法工作流，不是论文的具体数值。** 原因：

- 论文介观求解器是 FEM（四面体网格、超弹性连续体）；本仓库用 **YADE DEM**
  周期单胞实现 RVE。论文 §4.2 已论证：PANN 代理层与介观求解器无关，
  因此工作流（周期均匀化 → 域分离采样 → PANN → 多态 UQ）可以完整复现，
  但 DEM  packings 的本构响应 ≠ 论文的混凝土 FEM 结果，数值不对标。
- 论文宏观求解器是 FEAP（无开源可用）；宏观 BVP 演示简化为材料点层面的
  UQ + 小规模 patch 驱动。
- 论文用 TensorFlow + KerasTuner（50 种架构、48h）；本仓库用 PyTorch，
  超参搜索缩小为 ~10 种配置。

**对标论文的两个算例：**

| 论文算例 | 本仓库对应 | 价值 |
|---|---|---|
| Ex.I 板带孔，参数化 Neo-Hooke（有解析参考解） | `examples/ex1_neohooke/`：解析 Neo-Hooke 作"RVE"，验证 PANN+UQ 全链条 | 有参考解，可定量验收（论文相对误差 0.1%/0.07%） |
| Ex.II 混凝土 RVE（椭球夹杂）+ 完整多态 UQ | DEM 双相周期单胞 + PANN + MC/区间/p-box | 复现完整框架，定性行为对标（vf 越高越硬） |

## 2. 技术路线

```
Phase 1: Ex.I 解析验证 ──→ Phase 2: DEM RVE 均匀化 ──→ Phase 3: 域分离采样
                                                              │
Phase 6: 报告 ◄── Phase 5: 多态 UQ ◄── Phase 4: PANN 训练 ◄──┘
```

### Phase 1 — Example I 解析验证（最高优先级）

论文 §5.1。RVE 用**解析的**参数化 Neo-Hooke 代替（Simo–Taylor 形式）：

- **S** = μ(**1** − **C**⁻¹) + λ ln(J) **C**⁻¹，K = E/(3(1−2ν))，G = E/(2(1+ν))
- 不确定输入（论文 Table 1）：E ∈ [2.5, 3.5]×10⁴ MPa（β=2.8e-3 置信区间），
  ν ∈ [0.21, 0.39]，H 各分量 ∈ [−0.2, 0.2]，**F** = **H** + **1**
- DoE：U 空间 50 LHS × 力学空间 100 LHS = 5000 点（论文 §5.1）
- PANN：输入 (I₁,I₂,I₃,E,ν) → Ψ；autodiff 得 **S**；loss = mean‖**S**ᴺᴺ−**S**ʳᵉᶠ‖²；
  结构 5→175→175→1，softplus，Adam，90/10 划分
- UQ：MC（1e4 样本，q99 收敛判据：补 2e3 样本直到连续 5 步变化 < 0.5%）；
  区间分析（evolutionary strategy，scipy differential_evolution）
- **验收**：q99 与解析参考解的相对误差 < 1%（论文做到 0.1%/0.07%）；
  输出 p-box 对比图（论文 Fig. 7 类比）

### Phase 2 — DEM RVE 周期均匀化

论文 §2.4、§4.1、§5.2（Fig. 9–10）：

- 周期单胞（`O.periodic=True`），~1500–2500 颗粒双相 packing：
  硬夹杂（高 E）+ 软基体（低 E），两种 `FrictMat`
- 描述子 **u** = (vf, E_matrix, …)；vf 通过硬颗粒体积比控制
- 加载：准静态驱动单胞至目标 **F**（`cell.velGrad` 小增量 + 阻尼），
  `getStress()` 得体积平均 Cauchy 应力 → **S** = J**F**⁻¹σ**F**⁻ᵀ（Eq. 3）
- 收敛性：**F** = **1**+**H**（H_ij=0.1），Δ = std(‖**S**‖)/mean(‖**S**‖) ≤ 0.5%
- **验收**：选定单胞尺寸使 Δ 达标；vf 增大 → 宏观刚度单调增（定性）

### Phase 3 — 域分离采样（数据生成）

论文 §4.2.2, Fig. 4：

- U 空间 LHS → 每个 **u** 生成 RVE + 收敛测试 → 每个 RVE 力学空间 LHS
- 论文规模 50×1000（43 CPU-h，FEM）；本机 2 核，**先导规模 10×100 = 1000 探针**，
  验证管线后按需放大到 20×200
- 后台分批跑，checkpoint 断点续算
- **验收**：数据集 `(I, u, S)` 落盘；抽查应力-应变曲线物理合理

### Phase 4 — PANN 训练

论文 §2.5、§4.2.1、Table 4：

- PyTorch 实现 Ψ(**I**,**u**)，autodiff 求 **S**（Eq. 6）/ ℂ（Eq. 13）
- 输入缩放到 [−1,1]（链式法则修正，论文 §4.2.2）
- ~10 种架构/超参配置搜索，5 次随机重启取最优
- **验收**：测试集 **S** 相对 L2 误差 < 5%

### Phase 5 — 多态 UQ

论文 §3、§5：

- aleatoric：MC；epistemic：区间优化；polymorphic：p-box 组装（§3.3）
- QoI：σ_char = max|主应力|（Eq. 32），材料点层面 + 小 patch 演示
- **验收**：输出 q99 区间与 p-box 图；行为定性合理（vf↑ ⇒ q99↑）

### Phase 6 — 报告

- `docs/report.md`：方法、实现差异、验收结果、图表
- 与论文的定量/定性对比讨论，局限性说明

## 3. 资源与风险

| 项目 | 现状 | 对策 |
|---|---|---|
| CPU | 2 核，实测 ~38 万 particle·iter/s | 探针任务后台分批跑；先导规模验证后再放大 |
| 内存 | 7.7GB，当前余量紧张 | 重任务串行跑，监控 free；torch 仅 CPU 版 |
| PANN 框架 | torch CPU 版安装中（venv） | 备选：numpy 手写小网络 |
| 宏观求解器 | 无 FEAP | 简化为材料点 UQ + patch 演示，报告中声明 |
| DEM vs FEM | 细观物理不同 | 复现方法工作流；数值不对标论文，文档中明确 |

## 4. 里程碑

- [ ] M1：Phase 1 验收通过（q99 误差 < 1%，p-box 图）
- [ ] M2：DEM RVE 收敛性达标（Δ ≤ 0.5%）
- [ ] M3：数据集生成完毕（≥1000 探针，checkpoint 完整）
- [ ] M4：PANN 测试误差 < 5%
- [ ] M5：多态 UQ 跑通，输出 q99 区间与 p-box
- [ ] M6：复现报告定稿

## 5. 与学术管理技能的接口

每个 Phase 结束需满足"验收"条目方可进入下一 Phase；M1–M6 为检查点。
长时间后台任务（Phase 3 数据生成）以 checkpoint 文件为进度凭证。
