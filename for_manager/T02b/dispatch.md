---
schema: academic-project-task-dispatch/v1
task_id: "T02b"
title: "Phase 0 fallback：bonded/cohesive 接触重测 G1c（+G2a/G2b 信息性复测）"
parent_goal: "Harazin et al. CMAME 2026 方法复现：DEM-RVE 适用性门禁（v2 计划 Phase 0）"
assigned_role: "Experiment Engineer (YADE DEM)"
assignee: "pending"
priority: HIGH
dispatch_status: DISPATCHED
created_at: "2026-10-05"
depends_on: ["T02"]
---

# Task Dispatch: T02b - bonded 重测

## 1. 任务背景与核心目标
- **任务目标**：FrictMat 在 T02 中因摩擦滑移耗散 25% 被判 G1c NO-GO。
  按 v2 计划 fallback，用 bonded/cohesive 接触（YADE `CohFrictMat`）重测，
  消除颗粒间摩擦滑移耗散，检验 energy-PANN 的超弹性前提是否成立。
- **业务背景**：v2 计划 §3 Phase 0 fallback #1。若 bonded 仍失败，
  则转带历史变量的 surrogate 并声明超出原论文方法。

## 2. 输入依赖与先决条件
- **前置依赖任务**：T02（ACCEPTED，NO-GO）：`for_manager/T02/w1/handoff.md`
  必读（技术发现、门禁脚本用法、G2b 尺寸效应结论）。
- **输入物料路径**（只读）：
  - `rve/homogenize.py`、`rve/generate.py`、`rve/convergence.py`、
    `rve/tests/test_gates.py`（T02 交付物，main 上）
  - `for_manager/T02/w1/review.md`（已知问题：probe_F 插值 bug）
- **前置就绪检查**：`yadedaily -x rve/tests/test_stress_mapping.py` 在本 worktree 通过。

## 3. 写入范围与交付路径约束
- **Git 工作区**：
  - 隔离方式：`worktree`
  - 基线分支与 commit：`main` @ `4013e51`
  - 工作者专属分支：`worker/T02b-w1`
  - worktree 绝对路径：`/home/hatch/workspace/yade-rve-pann/.worktrees/T02b/w1`
- **工作者专属沙盒**：`for_worker/T02b/w1/`
- **正式文件直写授权**：
  - `rve/homogenize.py`（**先修 bug**：`probe_F` 从当前 hSize 而非参考 hSize 插值，
    参照 `test_gates.py::_probe_F_history` 的修正；T01/T02 用法均从 F=I 出发未触发，
    但本次多阶段路径必须修）
  - `rve/generate.py`（材料/引擎段：FrictMat → CohFrictMat，设 cohesion 使
    10% 压缩域内不断键；记录 cohesion 参数）
  - `rve/tests/test_gates.py`（按需小改：复用门禁；**新增断键计数记录**，
    若探针中有断键 → 损伤 → 路径相关，需在 verdict 中声明）
- **预期最终交付物**：上述文件 + `for_manager/T02b/w1/handoff.md`（GO/NO-GO 表）

## 4. 验收标准与完成定义 (DOD)
1. [ ] **probe_F bug 已修**：非参考态多阶段路径无突变（用 T02 的卸载路径回归验证）
2. [ ] **G1c 重测**（bonded，压缩/剪切域）：
   - 卸载残余 ‖S‖/E < 1e-3；路径无关相对差 < 5%；**耗散比 < 10%**（主判据）
   - 断键计数 = 0（若 >0，如实记录并评估对路径无关性的影响）
3. [ ] **G2a/G2b 信息性复测**：G2b 的 Δ≤0.5% 在 1000 颗粒下预期仍超标（尺寸效应，
   T02 已证）；复测只为确认 bonded 不恶化，不作生死判据——但数值必须如实报告
4. [ ] **自测命令**：`yadedaily -x rve/tests/test_gates.py` 退出码 0，打印门禁表
5. [ ] 交接件含 GO/NO-GO verdict + 与 T02(FrictMat) 的对比表

## 5. 已知陷阱与注意事项
- CohFrictMat 的 cohesion 参数需与 E_soft=1e7 Pa 量级协调：太大 packing 过硬、
  太小则压缩中拉断。先小规模试算再定参。
- T02 的 densify 两阶段应力伺服策略复用；bonded 下 jamming 行为可能不同，
  注意观察接触数–预应力曲线。
- 2 核机器：packing ≤1500 颗粒，总时长控制 ~30 分钟内。
- 不要修改 `for_user/`、看板、WORKLOG（只读）；不要 git commit/push。
