# 当前状态快照
> 更新于：2026-10-05 17:10 +08:00

**阶段**：v2 计划生效；T01/T02/T03 已验收。Phase 0 对 FrictMat DEM 判 NO-GO；
用户决策：执行 bonded fallback（T02b）。分析轨道 T04 继续。

**进行中**：
- T02b：bonded（CohFrictMat）重测 G1c（worker 执行中）
- T05：材料级 UQ demo（worker 执行中）

**子任务流转跟踪**：
| 任务 ID | 简要目标 | 专项角色 | 负责人 | 状态 | 依赖 | 派发单路径 | 交付物/交接件 |
| :--- | :--- | :--- | :---: | :--- | :--- | :--- | :--- |
| T01 | Phase 0 G1a/G1b：getStress→S 映射 + Hill-Mandel | Experiment Engineer (DEM) | worker-t01-w1 | ACCEPTED | — | `for_manager/T01/dispatch.md` | `rve/homogenize.py` + `rve/tests/` + `for_manager/T01/w1/review.md` |
| T02 | Phase 0 G1c/G2：DEM 门禁（FrictMat 判 NO-GO） | Experiment Engineer (DEM) | worker-t02-w1 | ACCEPTED | T01 | `for_manager/T02/dispatch.md` | `rve/generate.py` + `rve/convergence.py` + `rve/tests/test_gates.py` + `for_manager/T02/w1/review.md` |
| T03 | Phase 1A-1：Eq.(33) 精确实现 + 一致性测试 | Experiment Engineer | worker-t03-w1 | ACCEPTED | — | `for_manager/T03/dispatch.md` | `examples/ex1_neohooke/` + `for_manager/T03/w1/review.md` |
| T04 | Phase 1A-2/3：PANN + DoE + 训练（测试 L2=1.51%<5%） | Experiment Engineer | worker-t04-w1 | ACCEPTED | T03 | `for_manager/T04/dispatch.md` | `surrogate/pann.py` + `surrogate/train_pann.py` + `surrogate/tests/` + `for_manager/T04/w1/review.md` |
| T02b | Phase 0 fallback：bonded（CohFrictMat）重测 G1c | Experiment Engineer (DEM) | worker-t02b-w1 | DISPATCHED | T02 | `for_manager/T02b/dispatch.md` | 待交接 |
| T05 | Phase 1A-4：UQ demo（MC q99 + 区间） | Experiment Engineer | worker-t05-w1 | DISPATCHED | T04 | `for_manager/T05/dispatch.md` | 待交接 |

**待办**（按优先级）：
1. [ ] 验收 T01/T03（独立复测 DOD），ACCEPTED 后派发 T02/T04。
2. [ ] T02 出 GO/NO-GO 门禁 verdict；若 NO-GO，启动 bonded-contact 备选评估。
3. [ ] T04/T05 完成后进入 Phase 2（DEM RVE 适配）与报告。
4. [ ] torch 环境已重建于 `~/workspace/venvs/rve-pann`（仓库外），供 T04 使用。

**阻塞/风险**：
- 2 核 + 内存紧张：DEM 任务（T01/T02）与重任务串行，前台只并行轻量 numpy 任务（T03）。
- 论文基于 FEM，本仓库 DEM 适配须过 Phase 0 门禁；DEM 数值不与论文 FEM 对标（design.md 已定）。
