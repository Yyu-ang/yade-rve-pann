# 论文图表清单与复现状态 — Harazin et al., CMAME 452 (2026) 118726

> 用户约束（2026-10-05）：复现论文时**尽可能复现论文中的图表结果**。
> 本清单是该约束的执行台账：每个图表标注类型、对应任务、复现状态与交付物要求。
> 诚实报告原则不变——凡是 analogue/adaptation，一律明确标注，不得冒充论文原图复现。

## 图表清单

| # | 图表 | 类型 | 对应任务/阶段 | 状态 | 备注 |
|---|------|------|---------------|------|------|
| Fig. 1 | p-box 示意图 | schematic | — | 豁免 | 无数据可复现 |
| Fig. 2 | 多尺度 BVP 示意图 | schematic | — | 豁免 | 无数据可复现 |
| Fig. 3 | FE2 vs PANN 流程图 | schematic | — | 豁免 | 无数据可复现 |
| Fig. 4 | 域分离示意图 | schematic | Phase 3 | 参考 | 实现域分离采样时的设计参照 |
| Fig. 5 | 算法流程图 | schematic | — | 豁免 | 无数据可复现 |
| Fig. 6 | plate-with-hole 几何 + 主应力场（示例 realization） | 几何数据 + 结果图 | T06（已完成） | ✅ analogue 已复现 | `figures/T06/fig6_analog.png`（2D 平面应力 analogue；形态与论文一致，应力集中在孔左右；绝对值差异源于示例取 v=0.69 m 中位值，见 T06 review） |
| Table 1 | Ex.I DoE 边界（E iprf / ν rf） | 数据表 | T04（已完成） | ✅ 已复现 | `figures/T04/table1_doe_bounds.csv` |
| Table 2 | Ex.I PANN 结构（5→175→175→1） | 数据表 | T04（已完成） | ✅ 已复现 | `figures/T04/table2_pann_arch.csv` |
| Fig. 7 | Ex.I p-box（σ_char，PANN vs 参考，q99 误差 0.1%/0.07%） | 结果图 | T08（pilot 完成，全量在跑） | **pilot 已出图** | `figures/T08/fig7_analog_pilot.png`（2D analogue；pilot：q99 相对误差 −0.15%/+0.13%，p-box 几乎重合）；全量（细网格+完整 MC 规则）完成后出终版 |
| Fig. 8 | Ex.II FE 模型 | schematic/mesh | — | 豁免 | FEM-specific |
| Table 3 | Ex.II 参数表 | 数据表 | — | 范围外 | 需 FEM RVE；DEM 轨道已关闭 |
| Fig. 9 | RVE 结构 + 不确定性 | 结果图 | Phase 2 | 已关闭 | DEM 轨道记为阴性结果关闭；FEM 不可用 |
| Fig. 10 | RVE 收敛测试（Δ vs realization） | 结果图 | T02/T02b（已完成） | ⚠️ analogue | 我方 DEM 门禁数据的同类图，**不是**论文 FEM 数据；标注为 adaptation |
| Fig. 11 | Ex.II p-box | 结果图 | — | 范围外 | 需完整框架（FEM RVE + 宏观 BVP） |
| Table 4 | Ex.II PANN 结构（5→170→55→1） | 数据表 | — | 参考 | 仅作 Phase 4 重调参时的参照 |

## 复现约束（硬性）

1. **凡 DOD 声称与论文某图表一致的任务，必须交付三件套**：
   - 生成脚本（任务 sandbox 或模块目录内，可独立重跑）；
   - 输出产物：PNG + 源数据 CSV，存放于 `figures/<task>/`；
   - 对照说明：论文值 vs 复现值、误差定义、随机种子。
2. **示意图（schematic）豁免**：Fig. 1–5、Fig. 8 无数据可复现，不强制。
3. **analogue 标注义务**：凡非论文原始设定下产生的同类图（如 Fig. 10 风格的 DEM 收敛图、
   材料点 UQ 的 CDF/区间图），文件名与图注必须含 `analog`/`adaptation` 字样，
   不得在报告中与论文原图并列比较。
4. **Fig. 7 / Fig. 11 的 p-box 声称仍被 Phase 1B（G6）门禁锁定**：
   在宏观 BVP + 随机场 + Eq.(32) QoI + 区间优化全部落地前，
   任何"接近论文 q99 精度"的表述均为违规。
5. 本清单随任务进展更新；新增任务派发时，dispatch 必须引用本清单中对应的图表编号。

## 当前可交付（Phase 1A，已生成）

- `figures/T04/table1_doe_bounds.csv` — Table 1 复现（论文值 vs 本仓库 DoE）
- `figures/T04/table2_pann_arch.csv` — Table 2 复现（论文值 vs `surrogate/pann.py`）
