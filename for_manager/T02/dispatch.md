---
schema: academic-project-task-dispatch/v1
task_id: "T02"
title: "Phase 0 G1c/G2：DEM 超弹性兼容性 + 各向同性 + 代表性门禁"
parent_goal: "Harazin et al. CMAME 2026 方法复现：DEM-RVE 适用性门禁（v2 计划 Phase 0）"
assigned_role: "Experiment Engineer (YADE DEM)"
assignee: "pending"
priority: HIGH
dispatch_status: DISPATCHED
created_at: "2026-10-05"
depends_on: ["T01"]
---

# Task Dispatch: T02 - DEM 门禁测试（G1c/G2）

## 1. 任务背景与核心目标
- **任务目标**：判定 YADE DEM（FrictMat 双相 packing，周期单胞）能否进入论文式
  energy-PANN 路线。测试：G1c 超弹性兼容性（加载–卸载闭合、路径无关、耗散占比）、
  G2a 各向同性（旋转等价）、G2b 代表性（多 seed/多尺寸，Δ 定义见下）。
  输出每门的 GO/NO-GO verdict + 数值证据。
- **业务背景**：v2 计划 §3 Phase 0。这是整个 DEM 适配的生死门禁：
  任一门禁失败 → 停止 energy-PANN 路线（备选 bonded 接触重测，仍失败则改用
  历史变量 surrogate 并声明超出论文方法）。

## 2. 输入依赖与先决条件
- **前置依赖任务**：T01（ACCEPTED）：`rve/homogenize.py` 已验证
  （`cauchy_to_pk2`、机器精度的 Hill-Mandel；见 `for_manager/T01/w1/review.md`）。
- **输入物料路径**（只读）：
  - `rve/homogenize.py`（T01 交付物，含 `probe_F` 仿射修正）
  - `docs/reproduction_plan_review_2026-10-05.md` §3（Phase 0 门禁表）
  - `for_manager/T01/w1/handoff.md`（技术发现：getStress 符号、densify 策略必读）
- **前置就绪检查**：`yadedaily -x rve/tests/test_stress_mapping.py` 在本 worktree 通过。

## 3. 写入范围与交付路径约束
- **Git 工作区**：
  - 隔离方式：`worktree`
  - 基线分支与 commit：`main` @ `d1858a5`（已含 T01 交付物）
  - 工作者专属分支：`worker/T02-w1`
  - worktree 绝对路径：`/home/hatch/workspace/yade-rve-pann/.worktrees/T02/w1`
- **工作者专属沙盒**：`for_worker/T02/w1/`
- **正式文件直写授权**：
  - `rve/generate.py`（实现 packing 生成；T01 的 densify/affine 经验必须复用）
  - `rve/convergence.py`（实现代表性测试；Δ 采用 §1.2 定义
    Δ=std(‖S̄‖)/mean(‖S̄‖)≤0.5%，收敛抽样与机械 LHS 变量分离，P0-5）
  - `rve/tests/test_gates.py`（新建：门禁自测脚本）
- **预期最终交付物**：上述三个文件 + `for_manager/T02/w1/handoff.md`（含 GO/NO-GO 表）

## 4. 验收标准与完成定义 (DOD)
1. [ ] **G1c 超弹性兼容性**（FrictMat，压缩/剪切域；**已知 tensionless，不测拉伸可逆性**）：
   - 加载–卸载闭合：压缩至 F=diag(0.9,1,1) 后卸载回 F=I，残余 ‖S‖/E < 1e-3 且残余应变小
   - 路径无关：两条不同路径到同一终态 F，应力相对差 < 5%
   - 耗散占比：摩擦耗散能 / 外力功 < 10%（目标域内）
   - 任一项超标 → 该门记 NO-GO（并如实报告数值，不得放宽容差）
2. [ ] **G2a 各向同性**：x/y/z 三方向单轴压缩响应，等效刚度相对差 < 10%
3. [ ] **G2b 代表性**：固定 **u** 下 ≥5 seeds，Δ=std(‖S̄‖)/mean(‖S̄‖) ≤ 0.5%（§1.2 定义）
4. [ ] **自测命令**：`yadedaily -x rve/tests/test_gates.py` 退出码 0，打印门禁表
5. [ ] 交接件含 GO/NO-GO verdict（每门一行： verdict + 关键数值 + 判定依据）

## 5. 已知陷阱与注意事项
- T01 发现：densify 到 ~1200 接触即停；零压长弛豫会团聚开裂；改 hSize 必须仿射携带颗粒。
- FrictMat 无黏结 → 拉伸 S≈0 是物理正确，不要当 bug 修；门禁只在压缩/剪切域判定。
- 2 核机器：packing ≤1500 颗粒，seed 数/路径数控制总时长在 ~30 分钟内。
- 不要修改 `for_user/`、看板、WORKLOG（只读）；不要 git commit/push。
