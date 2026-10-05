# 复现计划（迭代版 v2）— 2026-10-05

> 本文档是对 `docs/reproduction_plan.md`（v1）的修订版。
> 修订依据：GPT 审查意见（原文归档于 `docs/reviews/gpt_review_2026-10-05.md`）逐条评估，
> 加作者对论文 PDF（`docs/references/Harazin_2026_CMAME_452_118726.pdf`）的视觉核验。
> 审查判定为 **REWORK REQUIRED** 的项已全部处理；v1 计划即日起废止（保留 git 历史）。

## 0. 审查意见逐条评估

| # | 审查点 | 是否成立 | 核验方式与结论 |
|---|---|---|---|
| P0-1 | Phase 1 的 Neo-Hookean ≠ 论文 Eq.(33) | ✅ 成立 | 已从 PDF p.11 视觉核验（见 §1）。v1 用的 Simo–Taylor 形式确非论文式，必须替换 |
| P0-2 | DEM 须先证明与 energy-PANN 超弹性前提兼容 | ✅ 成立 | 论文 §2.3 限定 hyperelasticity；FrictMat 摩擦耗散使单值 Ψ(C,u) 不能默认成立。新增 Phase 0 门禁 |
| P0-3 | 用 3 不变量前须验证各向同性 | ✅ 成立 | 论文 §4.2.1/结论明确要求对称性预知且稳定；有限尺寸随机 packing 须做旋转等价测试 |
| P0-4 | `stress(I,u)` 接口丢失 Eq.(6) 所需的 C 依赖 | ✅ 成立 | 由论文 Eq.(6) 直接可得：∂I_α/∂C 依赖 C。接口改为 `stress(C,u)`/`stress(F,u)` |
| P0-5 | 收敛 1000 样本与机械域 LHS 语义混淆 | ✅ 成立 | PDF p.14 原文："For each RVE sample, 1000 samples are drawn in the mechanical space." 两者确为不同抽样，必须拆分 |
| P0-6 | Δ 公式须视觉核验 | ✅ 成立，且有新发现 | 已视觉核验（见 §1）：原式排版与 Fig.10(b)/Δ≤0.5% 判据**自相矛盾**，采用 figure-consistent 定义并记录风险 |
| P1-1 | "microscale-agnostic" 表述过强 | ✅ 成立 | 降级为"待验证的 DEM adaptation"（见 §2） |
| P1-2 | DEM 双相应称 RVE analogue | ✅ 成立 | 术语修正；vf/porosity/配位数明确定义与记录 |
| P1-3 | vf↑⇒刚度↑ 仅作 sanity check | ✅ 成立 | 不再作为硬验收 |
| P1-4 | 论文 q99 误差不可用于材料点验收 | ✅ 成立 | M1 的 q99<1% 改为项目自定义指标；论文 0.1%/0.07% 仅在 Phase 1B（宏观 BVP）可引用 |
| P1-5 | 无宏观 FE 不得称完整框架 | ✅ 成立 | 最终声明收窄为"材料级/局部 DEM 适配验证"，除非完成 Phase 1B/宏观层 |

**总体结论**：审查意见全部合理，已逐条采纳。另有两处作者补充（§1 的 Δ 排版问题分析；
Phase 0 增加 bonded-contact 备选路径，见 §3）。

## 1. PDF 视觉核验记录（Phase 0 / G0 已完成项）

### 1.1 Eq.(33) — p.11, §5.1（P0-1 关闭）

论文原式（modified Neo-Hookean）：

```
S = F⁻¹ · ( κ·ln[J]·F⁻ᵀ + η·( J^(−2/3)·F − tr(J^(−2/3)·C)/3 · F⁻ᵀ ) )
κ = E / (3·(1−2ν)),   η = E / (2·(1+ν))
```

即：括号内为第一类 Piola–Kirchhoff 应力 **P** = ∂Ψ/∂**F**（对应
Ψ = κ/2·(lnJ)² + η/2·(Ī₁−3)，Ī₁ = tr(J^(−2/3)C)），再由 **S** = **F**⁻¹·**P**
得第二类 Piola–Kirchhoff 应力。Phase 1A 必须实现此精确式，并先做
"解析 **S** vs 对 Ψ 数值/autodiff 求导"的一致性测试，再生成训练数据。

### 1.2 收敛判据 Δ — p.14, §5.2（P0-6 关闭，附排版问题记录）

论文排版原式：

```
Δ = ( E(‖S̄‖) − √(VAR(‖S̄‖)) ) / E(‖S̄‖)   , in [%]；判据 Δ ≤ 0.5%
```

**自相矛盾分析**（视觉核验新发现）：
按字面计算 Δ ≈ 100·(1 − std/mean) ≈ 100%，与"Δ ≤ 0.5%"判据矛盾；
而 Fig.10(b) 纵轴为 "Δ × 10¹"、取值 0.9–1.3（即 Δ ≈ 0.09–0.13%），
与判据自洽；且正文称 Δ "the standard deviation of the obtained sample
points … is used"。三者联合表明排版分子多出的 "E(‖S̄‖) −" 疑似排版错误，
figure-consistent 的可操作定义为变异系数：

```
采用定义：Δ = std(‖S̄‖) / mean(‖S̄‖)   [in %]，判据 Δ ≤ 0.5%
```

记录为**已知转录风险**：实现时用单测手算样例锁定；若后续交叉核验发现
反例，重新评估。`docs/method_notes.md` 须同步记录原式、页码与本分析。

### 1.3 Eq.(6)/(13) — 标准式，文本抽取与常识一致，无需视觉复核

**S** = 2∂Ψ/∂**C** = 2Σ_α (∂Ψ/∂I_α)(∂I_α/∂**C**)；ℂ = 4∂²Ψ/∂**C**∂**C**。
实现时仍以 autodiff 为准、解析式为交叉检查。

## 2. 修正后的方法定位声明（取代 v1/README 过强表述）

> 本项目做两件事：(1) 对 Harazin et al. PANN–polymorphic-UQ 方法的**严格解析
> 基准复现**（Example I，论文 Eq.(33)，有解析参考解）；(2) 在通过 Phase 0
> 物理门禁的前提下，探索该方法向 **YADE-DEM RVE 的条件性适配**
> （"DEM heterogeneous RVE analogue"，不是论文混凝土 FEM RVE 的数值复现）。
> DEM 数值结果不与论文 FEM 数值对标；"PANN/UQ 与细观求解器无关"仅在满足
> 超弹性近似、RVE 代表性、材料对称性三条件下成立，此为**待验证命题**，
> 不是本项目的默认前提。

## 3. 修订实施阶段

### Phase 0 — 方法适用性门禁（新增，最高优先级，先于一切实现）

| 门禁 | 内容 | 通过标准 |
|---|---|---|
| G0 | 公式转录核验 | §1 三项完成并记录（✅ 已完成） |
| G1a | YADE `getStress()` → Cauchy → **S** 映射 | 符号/单位/体积平均核验单测通过 |
| G1b | Hill–Mandel 功率一致性 | 宏观 **P**:**Ḟ** 与细观体积平均偏差 < 容差（项目定 1%） |
| G1c | DEM 超弹性兼容性 | 若干代表性 (**u**, **F** 路径)：加载–卸载闭合、路径无关（同终态 **F** 应力差 < 容差）、残余应变/应力小、摩擦耗散占比小 |
| G2a | 各向同性 | 旋转等价/多方向加载响应差 < 容差，在整个 **U** 域抽查 |
| G2b | RVE 代表性 | 多 seed / 多 VE size 下有效响应不敏感（Δ 定义见 §1.2） |

**停止条件**：任一门禁失败 → 停止"论文式 Ψ-PANN + 当前 DEM 接触"路线。
备选（作者补充）：先试 bonded/cohesive 接触（更接近弹性）重测 G1c；
仍失败则改用带历史变量的 surrogate，并明确声明**已超出原论文方法**。

### Phase 1A — Example I 材料级严格复现（论文方法硬门槛）

- 实现 §1.1 的 Eq.(33) 精确式；先过"解析 **S**/切线 vs autodiff"一致性测试
- DoE：**U** 50 LHS × 力学域 100 LHS（论文 §5.1；H 各分量 ∈ [−0.2,0.2]）
- PANN baseline：5→175→175→1（论文 Table 2），softplus，90/10，输入缩放到 [−1,1]（链式法则修正）
- 数据落盘：`F, C, I, u, S`（P0-4）
- 接口：`energy(I,u)`, `stress(C,u)`/`stress(F,u)`, `tangent(C,u)`（P0-4）
- **验收**：解析应力/切线一致性通过；测试集应力相对 L2 < 5%（**项目内部阈值**，非论文阈值）

### Phase 1B — Example I 宏观结构复现（可选；引用论文 q99 的必要条件）

- 重建 plate-with-hole 宏观 BVP（求解器不限 FEAP），保留随机场（KL 展开）、
  随机位移、Eq.(32) 结构级 QoI σ_char
- **仅在此完成后**，方可将 PANN vs 参考本构的 q99/p-box 与论文 0.1%/0.07% 直接比较

### Phase 2 — YADE DEM RVE 适配（仅 Phase 0 全部通过后）

- 定义 DEM-specific **u**（vf 明确定义 + porosity/配位数随行记录；接触刚度参数
  不得直接命名为 continuum E_matrix，除非完成标定映射）
- 多 realization / 多 VE size 收敛（Δ 定义 §1.2）；对称性在 **U** 域内复查
- 论文 60 mm 尺寸不作为 YADE 必须值，由 DEM 自身收敛研究确定
- 术语：全程 "RVE analogue / DEM adaptation"

### Phase 3 — 域分离采样

- 变量分离：`n_rve_realizations`（收敛/代表性抽样）vs `n_mech_lhs`（机械域 LHS），
  禁止复用同一 `N_MECH_SAMPLES`（P0-5）
- pilot 10×100 仅验证管线；正式规模按 learning curve / 误差收敛决定
- 每个 **u** 的 RVE 代表性证据与训练数据绑定记录

### Phase 4 — PANN 训练

- 先固定论文结构作 baseline（Ex.I：5→175→175→1；Ex.II analogue：5→170→55→1，
  仅输入维度仍为 5 时），再做缩减版超参搜索（~10 配置 × 5 重启）
- "复现论文 PANN" 与 "针对 YADE 重调参" 分开报告

### Phase 5 — 多态 UQ（两级声明）

- **材料级/patch UQ**：验证算法链可运行（MC 1e4 + 补 2e3，q99 五步 <0.5% 停止；
  区间用 differential evolution）
- **宏观结构 UQ**：仅在 Phase 1B 或等价宏观层完成后，方可声称接近论文完整框架

### Phase 6 — 报告

- `docs/report.md`：严格区分"原论文方法 / 本仓库适配 / 实测结果"三类陈述
- 记录数据规模、随机种子、软件版本、误差定义；局限性单列一节

## 4. 硬门槛矩阵（采用审查建议）

| Gate | 必须证明 | 通过后允许的声明 |
|---|---|---|
| G0 | Eq.(33)/Eq.(6)/Eq.(13)/Δ 转录准确（§1） | "论文数学定义已正确实现" |
| G1 | DEM 路径无关/可逆性/能量一致性达容差 | "DEM 可进入 energy-PANN 适配" |
| G2 | RVE 对 realization 不敏感，对称性在 **U** 域稳定 | "可用确定性参数化 RVE 与 3-不变量 PANN" |
| G3 | Ex.I 解析应力/切线验证通过 | "PANN 核心实现通过" |
| G4 | DEM held-out RVE 应力预测达项目阈值 | "DEM-PANN surrogate 有效" |
| G5 | 材料级 UQ 跑通 | "材料级 polymorphic UQ workflow 已复现/适配" |
| G6 | 宏观 BVP + 随机场 + Eq.(32) QoI 跑通 | "接近论文完整 multiscale polymorphic UQ framework" |

## 5. 审查 §8 文件修订清单落实

- [ ] `docs/reproduction_plan.md`：标注 **SUPERSEDED**（本文件取代），保留历史
- [ ] `docs/method_notes.md`：补 Eq.(33) 精确式、Δ 原式+页码+§1.2 分析、论文三限制
  （hyperelasticity / 对称性 / 非收敛 RVE 不在方法能力内）
- [ ] `README.md`：降级 microscale-agnostic 表述；DEM 部分改称 analogue；
  Quick start 在入口文件不存在前标注 planned
- [ ] `surrogate/pann.py`：实现前修正接口（§3 Phase 1A）
- [ ] `rve/convergence.py`：Δ 采用 §1.2 定义；拆分 representativeness/mechanical 两套抽样

## 6. 与 v1 的主要差异

1. 新增 Phase 0 门禁（G0–G2），DEM 适配从"默认可行"改为"条件准入"
2. Phase 1 改为论文 Eq.(33) 精确式（v1 的 Simo–Taylor 作废）
3. Δ 采用 figure-consistent 定义并记录排版风险（v1 误作论文事实）
4. 拆分 Phase 1A（材料级）/ 1B（宏观结构）；q99 论文阈值仅 1B 可引用
5. 收敛抽样与机械 LHS 变量分离；数据落盘 F/C/I/u/S
6. PANN 接口改为 stress(C,u)；先跑论文结构 baseline 再调参
7. 最终声明收窄为"材料级/局部 DEM 适配验证"（除非完成宏观层）
