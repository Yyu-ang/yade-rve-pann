# 复现计划论文对照审查建议

> 审查对象：`docs/reproduction_plan.md`、`docs/method_notes.md`、`README.md` 及当前实现骨架  
> 论文原文：`docs/references/Harazin_2026_CMAME_452_118726.pdf`  
> Harazin et al., *Computer Methods in Applied Mechanics and Engineering* 452 (2026) 118726  
> DOI: 10.1016/j.cma.2025.118726  
> 审查日期：2026-10-05

## 1. 总结结论

**结论：当前方案工程上可实施，但在论文方法一致性上属于“需要重大修订后再开工”（Major Revision Before Implementation）。**

本仓库可以采用 YADE-DEM 代替论文的 FEM RVE，开展“论文方法链的 DEM 适配研究”；但当前文档中把这种替换描述为可直接“保持论文工作流完整”，依据不足。论文的 PANN 并不是任意细观求解器上的通用应力代理，而是建立在以下前提上：

1. 材料响应属于**超弹性（hyperelasticity）**，存在应变能密度函数 (Psi)；
2. 应力由 (mathbf S=2,partialPsi/partialmathbf C) 重建；
3. 若使用不变量形式 (Psi(mathbf I,mathbf u))，则材料对称性必须预先已知，并且不能随参数 (mathbf u) 任意改变；
4. 每个参数化 RVE 必须已经具有代表性，使固定参数下的有效响应近似确定；论文明确指出非收敛/随机 VE 导致的随机能量响应不在该方法当前能力范围内。

因此，YADE 适配能否进入论文式 PANN，必须先通过“超弹性兼容性 + RVE 代表性 + 对称性”门禁。否则仍可做 DEM surrogate/UQ，但不能继续称为对论文 energy-based PANN 的直接复现。

---

## 2. 已确认与论文一致的部分

以下内容与论文原文基本一致，可保留：

- 周期边界条件、Hill–Mandel 条件和体积平均均匀化路线（§2.4）；
- PANN 输出应变能密度 (Psi)，通过自动微分重建应力（Eq. 6），并可进一步得到材料切线（Eq. 13）；
- 不确定参数 (mathbf u) 作为 PANN 的额外输入（Eq. 27）；
- 将总输入域分为不确定参数域 (U) 和机械域 (mathcal F)，分别采用 LHS 的 domain separation（§4.2.2）；
- 输入缩放到 ([-1,1])，并在 Eq. (6)/(13) 的导数中显式加入缩放链式法则；
- Example I：(U) 空间 50 个样本，每个机械域 LHS 100 点；PANN 结构 5→175→175→1，softplus 隐层；
- Example II：(U) 空间 50 个样本，每个 RVE 的机械域 1000 点，共 50,000 个训练点；PANN 结构 5→170→55→1；
- 训练集/验证集 90/10，超参搜索每个候选重复训练 5 次，论文测试 50 种结构；
- Monte Carlo 初始 (10^4) 样本、每次补 (2	imes10^3)，以连续 5 步 (q_{99}) 变化小于 0.5% 为停止条件；
- 论文 Example II 本身没有可行成本下的完整 FE² 数值参考解，因此其作用是展示完整框架，而不是提供 DEM 可直接对标的标准答案。

---

## 3. P0：开工前必须修正

### P0-1. Phase 1 的 Neo-Hookean 本构不是论文 Eq. (33)

当前计划写：

[
mathbf S=mu(mathbf 1-mathbf C^{-1})+lambdaln J,mathbf C^{-1}
]

这不是论文 Example I 使用的 Eq. (33)。论文明确采用 **modified Neo-Hookean law**，参数为

[
kappa=rac{E}{3(1-2
u)},qquad
eta=rac{E}{2(1+
u)}
]

并以论文 Eq. (33) 的应力表达式作为解析参考。

**要求：**

- Phase 1 必须直接按论文 Eq. (33) 实现，不得用另一个常见可压缩 Neo-Hooke 公式替代；
- 先对 Eq. (33) 做独立数值/自动微分一致性测试，再生成训练数据；
- 若保留其他 Neo-Hooke 形式，只能标记为附加工程测试，不能作为论文 Example I 的复现。

**影响：高。** 当前 M1 的“论文解析参考”基础需要先修正。

---

### P0-2. YADE DEM 必须先证明与 energy-based PANN 的超弹性前提兼容

论文 §2.3 明确限定本构为 hyperelasticity，并以

[
Psi(mathbf C,mathbf u),qquad
mathbf S=2rac{partialPsi}{partialmathbf C}
]

作为 PANN 的基本结构。

当前 Phase 2 计划采用双相颗粒 + `FrictMat`。普通摩擦接触可能产生滑移、耗散、接触网络重排和路径依赖，因此不能默认存在单值的 (Psi(mathbf C,mathbf u))。

这不是“DEM 与 FEM 不同”的一般问题，而是**是否满足论文 PANN 的数学前提**。

**必须新增 Phase 0 门禁：**

对若干代表性 (mathbf u) 和 (mathbf F) 路径，至少检查：

1. 加载–卸载闭合性；
2. 不同加载路径到同一最终 (mathbf F) 时，应力差异；
3. 循环加载后的残余应变/残余应力；
4. 接触滑移/摩擦耗散量；
5. 宏观功率/能量一致性（Hill–Mandel 数值检查）。

**判定：**

- 若响应在目标机械域内可近似视为可逆、路径无关，并满足能量一致性，可继续论文式 (Psi)-PANN；
- 若存在显著耗散/路径依赖，应停止“论文 energy-PANN + FrictMat”路线，改用能处理历史变量/耗散的 surrogate，并明确这已超出原论文方法。

---

### P0-3. 使用前三个 (mathbf C) 不变量之前必须验证 DEM RVE 的各向同性

论文 Example II 使用前三个不变量，是因为其 RVE 在收敛后按各向同性材料处理。论文 §4.2.1 和结论均明确指出：采用不变量形式时，材料对称性必须预先已知，且不能随参数化发生不受控变化。

随机颗粒 RVE 在有限尺寸、不同体积分数、不同粒径分布和不同 seed 下可能呈现统计各向异性。

**要求：**

- 在训练 PANN 前进行旋转等价/方向加载测试；
- 检查不同方向的等效刚度/应力响应差异；
- 验证对称性在整个 (mathbf u) 域内保持。

若不能证明近似各向同性，不得继续固定使用 (I_1,I_2,I_3) 的 3-invariant PANN；应回到论文 §4.2.1 所述物理信息更少的 (Psi(mathbf C,mathbf u)) 形式，或显式加入适当结构张量。

---

### P0-4. 当前 `PANN.stress(I, u)` 接口不足以实现论文 Eq. (6)

论文虽然将训练元组记为

[
D^q=((mathbf I^q,mathbf u^q),mathbf S^q)
]

但 Eq. (6) 实际为

[
mathbf S
=
2sum_alpha
rac{partialPsi}{partial I_alpha}
rac{partial I_alpha}{partialmathbf C}.
]

因此，完整应力张量重建需要当前 (mathbf C)（或可恢复 (mathbf C) 的 (mathbf F)），因为 (partial I_alpha/partialmathbf C) 依赖 (mathbf C)。

当前骨架：

`stress(I, u)` / `tangent(I, u)`

把这一依赖隐藏掉了。

**建议接口：**

- `energy(I, u)`
- `stress(C, u)` 或 `stress(F, u)`：内部计算 (I(C))，再按 Eq. (6) 重建 (S)
- `tangent(C, u)` 或 `tangent(F, u)`

**数据落盘建议：**

至少保存 `F, C, I, u, S` 或保存足以无歧义恢复 `C` 的等价数据。  
这不是改变论文训练变量，而是避免实现层丢失 Eq. (6)/(13) 所需的运动学信息。

---

### P0-5. RVE convergence 的“1000 样本”语义必须与机械域 LHS 分开

当前 `rve/convergence.py` 注释将：

- 固定 (mathbf F=mathbf 1+mathbf H, H_{ij}=0.1)
- “1000 mechanical samples”

写在一起，概念不一致。

论文 §5.2 明确将两件事分开：

1. 在固定规定变形状态下检查 RVE 有效量的收敛；
2. 对每个通过代表性检查的 RVE，再在机械域 (mathcal F) 内抽取 1000 个 LHS 点生成训练数据。

**要求：**

- 代码中把“RVE representativeness/convergence samples”和“mechanical LHS samples”拆成不同变量、函数和日志；
- 不要让 `N_MECH_SAMPLES=1000` 同时承担两种语义；
- 收敛检查必须体现“固定 (mathbf u)、固定机械状态、变化 realization/VE size 后响应对 realization 不敏感”的目的。

---

### P0-6. 收敛判据公式必须直接从 PDF 视觉核验后再编码

仓库当前统一写成：

[
Delta=rac{operatorname{std}(|mathbf S|)}
{operatorname{mean}(|mathbf S|)}
le 0.5%.
]

但出版社机器可读正文对 §5.2 该式的转录与上述形式不一致，而且转录出来的式子与“(Deltale0.5%)”的语义本身存在可疑之处。

因此这里属于**高风险公式转录点**。

**要求：**

- 开发前直接打开仓库原文 PDF，视觉核对 §5.2 / Fig. 10 前后的 (Delta) 原式；
- 在 `docs/method_notes.md` 中记录“论文原式 + 页码/公式位置”；
- 单元测试用手算样例锁定实现；
- 在完成视觉核验前，不应把仓库当前 `std/mean` 版本当作论文事实。

---

## 4. P1：允许工程适配，但必须收窄论文复现声明

### P1-1. “PANN/UQ 与细观求解器无关”表述过强

README 当前称 surrogate/UQ 层“microscale-agnostic, exactly as argued in §4.2”。

论文支持的是：在满足其物理条件和参数化条件时，PANN 可以作为参数化 RVE 的代理。论文同时明确给出超弹性、材料对称性和 RVE 代表性的限制。

**建议改为：**

> 本项目测试论文 PANN/UQ 方法在满足超弹性近似、RVE 代表性及材料对称性条件下向 YADE-DEM RVE 的适配性；DEM 适配不是论文已经证明的结论。

---

### P1-2. DEM 双相颗粒应称为“RVE analogue/adaptation”，不是论文混凝土 RVE 的严格复现

论文 Example II 是连续基体中的椭球夹杂，并以连续体超弹性 FE 求解。

当前计划的“硬颗粒 + 软颗粒 + 孔隙 + 接触”具有不同的物理含义。

**要求：**

- 报告和 README 使用“DEM heterogeneous RVE analogue / DEM adaptation”；
- 明确定义 YADE 中的 `vf`；
- 控制或至少记录 porosity、coordination number 等随 `vf` 的同步变化；
- 不把颗粒接触刚度参数直接命名为论文的 continuum `E_matrix`，除非完成物理映射/标定。

---

### P1-3. `vf↑ ⇒ 刚度/q99↑` 只能作为 sanity check，不能作为硬验收

论文 Example II 中该趋势的解释依赖于：

[
E_{	ext{matrix}} < E_{	ext{inclusion}}
]

以及其特定连续体 RVE 和宏观结构。

在 DEM 中，`vf` 的改变还可能同时改变孔隙率、接触网络和配位数。

因此该趋势可以做物理合理性检查，但不能单独证明“复现成功”，更不能作为失败即否决的硬门槛。

---

### P1-4. Example I 的论文 q99 误差不能用于材料点/小 patch 的直接验收

论文的 0.1% / 0.07% 是：

- plate-with-hole 宏观 FE BVP；
- 随机场 (E^{iprf})、(
u^{rf})；
- 随机位移；
- Eq. (32) 全结构节点最大主应力 (sigma_{char})；
- PANN 与解析本构两套宏观 UQ 结果

之间的 (q_{99}) 边界误差。

如果本仓库只做“材料点 UQ + 小 patch”，QoI 和模型已经不同。

**因此：**

- 材料级 Phase 1 应以应力、切线和导数一致性作为定量验收；
- 只有真正实现 plate-with-hole 宏观 BVP，并保持同类随机场/UQ/QoI 定义后，才可以把论文 0.1% / 0.07% 作为直接比较对象；
- 当前 M1 的 “q99 <1%” 若保留，应标注为**项目自定义指标**，而不是论文复现阈值。

---

### P1-5. 没有宏观 FE BVP 时，不应称为“完整 multiscale polymorphic UQ framework”

论文的完整 Example II 包含：

- 宏观 FE；
- RVE 参数随机场；
- 宏观位移随机变量；
- 几何缺陷区间；
- Karhunen–Loève 展开；
- MC + interval optimization；
- p-box；
- Eq. (32) 的结构级 QoI。

如果仓库最终只实现材料点/patch UQ，则可称：

> PANN + domain separation + polymorphic UQ 的材料级/局部 DEM 适配验证

而不能声称完整复现论文的多尺度结构 UQ。

---

## 5. 建议重新排列实施阶段

### Phase 0 — 论文方法与 DEM 适用性门禁（新增，最高优先级）

必须完成：

- 核对 Eq. (6)、Eq. (13)、Eq. (33)；
- 核对 §5.2 convergence (Delta) 原式；
- YADE `getStress()` 的应力符号、体积、单位和 Cauchy→2PK 转换测试；
- Hill–Mandel/power consistency；
- 加载–卸载/路径无关性/耗散测试；
- RVE 各向同性测试；
- 多 seed、多 VE size 的代表性测试。

**停止条件：**

若目标 DEM 域不能近似满足 energy-based hyperelastic response，则停止论文式 (Psi)-PANN DEM 扩展。

### Phase 1A — Example I 材料级严格复现

- 直接实现论文 Eq. (33)；
- 50 × 100 DoE；
- 5→175→175→1；
- 90/10；
- softplus；
- Eq. (6)/(13) + scaling chain rule；
- 对照解析 (S) 与 tangent。

这一阶段可以在没有 FEAP 的情况下完成，并应作为 PANN 数学实现的首个硬门槛。

### Phase 1B — Example I 宏观结构复现（可选但与论文 q99 对标的必要条件）

若希望引用论文 0.1% / 0.07%：

- 重建 plate-with-hole 宏观模型；
- 保留随机场与位移随机变量；
- 使用 Eq. (32) 结构级 QoI；
- 再比较 reference constitutive law 与 PANN 的 p-box/q99。

求解器不必须是 FEAP，但 BVP 与 QoI 必须具有可比性。

### Phase 2 — YADE DEM RVE 适配

仅在 Phase 0 通过后开展：

- 定义 DEM-specific (mathbf u)；
- 多 realization / 多 VE size 收敛；
- 确认材料对称性；
- 确认 stress measure mapping；
- 论文 60 mm RVE 尺寸不作为 YADE 必须值，由 DEM 自身收敛研究确定。

### Phase 3 — Domain-separated data generation

- pipeline pilot 10×100：允许，仅用于工程通路验证；
- 正式训练规模根据 learning curve 和误差收敛决定；
- 数据保留 `F/C/I/u/S`；
- 对每个 (mathbf u) 的 RVE 代表性证据与训练数据绑定记录。

### Phase 4 — PANN

优先先固定论文给出的结构作为 baseline：

- Example I：5→175→175→1；
- Example II analogue：5→170→55→1（仅在输入维度仍为 5 时）。

然后再做缩减版超参搜索。

这样可以把：

> “复现论文 PANN”

与

> “针对 YADE 重新调参”

清楚分开。

测试集 (S) 相对 L2 <5% 可以保留，但应标注为**本项目内部验收阈值，不是论文报告阈值**。

### Phase 5 — UQ

明确分两级：

- **材料级/patch UQ**：验证算法链可运行；
- **宏观结构 UQ**：只有这一层才能声称接近论文完整框架。

---

## 6. 建议的硬门槛矩阵

| Gate | 必须证明 | 通过后允许的声明 |
|---|---|---|
| G0 | Eq. 33 / Eq. 6 / Eq. 13 / convergence 公式转录准确 | “论文数学定义已正确实现” |
| G1 | DEM 路径无关/可逆性/能量一致性达到预设容差 | “DEM 可进入 energy-PANN 适配” |
| G2 | RVE 对 realization 不敏感，且对称性在 U 域内稳定 | “可使用确定性参数化 RVE 与 3-invariant PANN” |
| G3 | Example I 解析应力/切线验证通过 | “PANN 核心实现通过” |
| G4 | DEM held-out RVE stress 预测达到项目阈值 | “DEM-PANN surrogate 有效” |
| G5 | 材料级 UQ 跑通 | “材料级 polymorphic UQ workflow 已复现/适配” |
| G6 | 宏观 BVP + random fields + Eq.32 QoI 跑通 | “接近论文完整 multiscale polymorphic UQ framework” |

---

## 7. 当前计划中可直接接受的工程偏离

以下偏离本身不是问题，只要报告中明确：

- TensorFlow → PyTorch：可以；
- 50 架构 HPO → ~10 个候选：可以作为资源约束下的工程简化，但论文给定结构应保留为 baseline；
- 10×100 / 20×200 pilot：可以用于管线验证，不能替代正式精度/收敛证据；
- FEAP → 其他宏观 FE solver：可以，只要 BVP、QoI 和不确定性定义保持可比；
- 暂时不做宏观 FE：可以，但必须把最终结论收窄为材料级/局部框架验证。

---

## 8. 建议立即修改的文件

在开始实现算法前，建议下一次提交至少修订：

1. `docs/reproduction_plan.md`
   - 新增 Phase 0；
   - Phase 1 改为论文 Eq. (33)；
   - 移除材料点 q99 对论文 0.1%/0.07% 的直接验收；
   - 区分 RVE convergence samples 与 mechanical LHS；
   - 调整 DEM 适配声明。

2. `docs/method_notes.md`
   - 从 PDF 视觉核验并记录 convergence (Delta) 原式；
   - 明确论文的 hyperelasticity / material-symmetry / non-converged RVE 限制；
   - 明确 Example I/II 的宏观 QoI 边界。

3. `README.md`
   - 将“microscale-agnostic, exactly as argued”降级为“待验证的 DEM adaptation”；
   - 不再将 DEM 双相颗粒称为论文 Example II 的数值复现；
   - Quick start 在入口文件实际存在前标注为 planned。

4. `surrogate/pann.py`
   - 实现前先修正 stress/tangent 的 (mathbf C/mathbf F) 依赖接口。

5. `rve/convergence.py`
   - 在 PDF 核验 (Delta) 后再实现；
   - 拆分 representativeness sampling 和 mechanical sampling。

---

## 9. 最终审查判定

**可行，但必须先修订方法边界。**

推荐项目定位：

> **Harazin et al. PANN–polymorphic-UQ 方法的严格解析基准复现（Example I） + 面向 YADE-DEM RVE 的条件性方法适配研究。**

不建议当前定位：

> “用 FrictMat DEM 替换 FEM 后，论文完整方法天然保持不变。”

二者的差别在于：前者先验证论文方法成立所需的物理条件，再适配；后者把最关键的超弹性、RVE 代表性和材料对称性条件当成了默认成立。

**审查状态：REWORK REQUIRED。**  
建议先修订 `reproduction_plan.md` 与 `method_notes.md`，通过 Phase 0 设计审查后，再开始 Phase 1/2 的正式实现。
