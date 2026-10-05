---
schema: academic-project-worker-handoff/v1
task_id: "T05"
worker_id: "w1"
worker_status: INCOMPLETE_HANDOFF  # COMPLETED | INCOMPLETE_HANDOFF
---

# Worker Handoff — T05

## 指派目标与验收标准
- 目标：基于 T04 已验收的 PANN，在固定变形 F=diag(1.1,1,1) 下做材料级多态 UQ
  demo：① MC（N≥20000，seed 固定）传播 (E,ν) 不确定性到 S₁₁，输出均值/std/q99，
  与解析 Eq.(33) 参考对比 <3%；② 区间优化（多起点）求 S₁₁ 在 (E,ν) 区间上的
  min/max，与解析区间界对比 <3%。(E,ν) 不超出训练域 [2.5,3.5]e4×[0.21,0.39]。
- 验收标准（DOD，见 for_manager/T05/dispatch.md）：
  1. MC 均值/std/q99 与解析参考相对误差 < 3%
  2. 区间 min/max 与解析区间界相对误差 < 3%
  3. `/home/hatch/workspace/venvs/rve-pann/bin/python uq/tests/test_uq.py`
     退出码 0，打印 q99 与区间界及对比
  4. 交接件声明：材料点级 demo，不声称论文宏观 BVP 的 q99 精度

## 状态与已完成项
- **工作者状态**：`INCOMPLETE_HANDOFF`
- 已完成项：
  - `uq/material_uq.py`（新建）：MC 传播（common random numbers，N=20000，
    seed=20261005）+ 区间优化（160×160 网格 + torch L-BFGS 多起点抛光；
    解析参考用网格 + scipy L-BFGS-B 抛光）；向量化解析 Eq.(33) 与 T03
    `pk2_stress` 交叉验证 0.0 误差。
  - `uq/tests/test_uq.py`（新建）：自测脚本，含解析交叉验证、PANN 中心点
    sanity 检查（1.1%）、完整 DOD 门禁。
  - DOD 实测（F=diag(1.1,1,1)，单位 MPa）：
    - MC mean：PANN 3394.64 vs 解析 3376.77，rel **0.529%** ✓
    - MC std：PANN 641.28 vs 解析 639.14，rel **0.334%** ✓
    - MC q99：PANN 5069.51 vs 解析 5110.77，rel **0.807%** ✓
    - 区间 min：PANN 2219.80 vs 解析 2253.42，rel **1.492%** ✓
    - 区间 max：PANN 5236.00 vs 解析 5544.14，rel **5.558%** ✗（>3%）
  - 数值证据存档：`for_worker/T05/w1/uq_results.json`（全部统计量）。

## Git 工作区与资源交接
- 隔离方式：worktree
- 分支与基线 commit：`worker/T05-w1`，基线 `main @ 76bda73`（T04 已验收；
  worktree 创建时基线为 fb7e315，已 fast-forward 合并 main 纳入 T04 交付物）
- worktree 绝对路径：`/home/hatch/workspace/yade-rve-pann/.worktrees/T05/w1`
- 最终工作树状态：`?? uq/material_uq.py`，`?? uq/tests/test_uq.py`
  （仅派发单授权的新建文件；checkpoint 只读使用，未复制入 git）。未 commit，未 push。

## 交付物
- 无（仅交接）。`uq/material_uq.py` 与 `uq/tests/test_uq.py` 为已验证代码，
  但因 DOD 第 2 项未全过，按纪律不列为正式交付物。

## 自测与证据
- 命令：`cd /home/hatch/workspace/yade-rve-pann/.worktrees/T05/w1 && /home/hatch/workspace/venvs/rve-pann/bin/python uq/tests/test_uq.py`
- 实际结果：退出码 1（`AssertionError: DOD failed`，因区间 max 5.558% > 3%）；
  报告打印完整（见上表）；解析交叉验证通过（0.0）；PANN 中心点 sanity 通过。
- 补充验证：`for_worker/T05/w1/de_check.py` 用 scipy `differential_evolution`
  独立确认 PANN 在盒子上的全局 max = 5236.00 @ (E≈3.5e4, ν=0.39)——与主流程
  的 L-BFGS 多起点结果一致，排除优化遗漏。

## 未完成项、阻塞与接续步骤
- 未完成项：DOD 第 2 项（区间 max < 3%）未达成。
- 阻塞（根因分析，非工作者代码问题）：
  T04 已验收的 PANN 在定义域角点 (E=3.5e4, ν=0.39) 处系统性低估 S₁₁
  达 5.6%（四角点误差：−1.49%/−0.89%/−2.39%/**−5.56%**，随 ν→0.39 增大；
  κ=E/(3(1−2ν)) 在 ν→0.5 附近陡峭，NN 边界拟合不足）。解析与 PANN 的区间
  max 同在该角点取得，属代理本身的逐点边界误差（T04 测试集相对 L2=1.51%
  为平均指标，不约束角点最坏情况）。UQ 方法链（MC/区间优化/多起点）本身
  工作正常。
- 接续步骤（需管理员/用户决策）：
  1. 接受并记录该局限（q99 等主要 UQ 量均 <1%，方法演示成立），放宽区间
     max 的 DOD；
  2. 或退回 T04 做边界加权再训练（不在本任务授权内）；
  3. 或改用对代理更友好的 demo 变形（需声明，不建议——有 cherry-picking 之嫌）。
- WIP 路径：`/home/hatch/workspace/yade-rve-pann/for_worker/T05/w1/`
  （`uq_results.json`、`de_check.py`、`save_results.py`，过程材料）。

## 需管理员核验
- 复核 `for_worker/T05/w1/uq_results.json` 数值与上表一致。
- 裁决：接受局限 / 放宽 DOD / T04 再训练。
- 声明（DOD 第 4 项）：本 demo 为**材料点级** UQ 方法演示；论文的 0.1%/0.07%
  q99 精度属于 plate-with-hole 宏观 BVP，**不得**从本 demo 声称。
