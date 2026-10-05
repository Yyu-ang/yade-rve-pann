---
schema: project-agent-contract/v2
primary_skill: academic-project
skill_version: 2.4.2
memory_root: auto
project_skill_root: .skill
local_skill_path: .skill/academic-project
legacy_memory_root: .paper-memory
mcp_governed_writes: off
---

# AGENTS.md - Project Agent Contract

本文件是本项目的统一维护契约。仅承载静态规则；动态进展由 `PROJECT_DASHBOARD.md`（面向用户）、`README.md`、`WORKLOG.md`（面向工程）和唯一项目记忆根目录共同维护。

---

## 1. 角色判定与分工权限（多 AI 协同路由）

进入项目后，AI 依据输入上下文判定自身角色，遵循权限边界：

| 角色类型 | 判定规则 | 写入权限与核心职责 |
| :--- | :--- | :--- |
| **独立维护者 / 管理员 (Maintainer/Admin)** | **默认模式**：未显式指定角色时；或明确指定为统筹者/管理员。 | 拥有全局维护权；负责任务分解与标准化派发（`for_manager/<task-id>/dispatch.md`）、子任务流转跟踪、独立验收、返工督促、正式交付、清理过时过程成果和最终封存。 |
| **任务工作者 (Worker / Specialist)** | 用户或统筹 AI 明确指定为工作者、子代理或专项执行角色。 | 全局看板、契约、日志、记忆只读；开工前须查验 `for_manager/<task-id>/dispatch.md`；过程产物/WIP 写入获派 `for_worker/<task-id>/<agent-id>/`；代码任务仅在派发单指定的独立 worktree/平台 checkout 内修改获准路径；直接修改正式源码/文稿必须有显式路径授权；完成或未完成均须在 `for_manager/<task-id>/<agent-id>/handoff.md` 落盘标准化交接件。 |

根目录 `for_user/`、`for_worker/`、`for_manager/` 是临时过程目录。`for_user/` 仅由管理员整理；`for_manager/<task-id>/dispatch.md` 为管理员任务指派单；工作者不得向 `for_user/` 写入未完成成果。`.worktrees/`（如使用）是本地代码 checkout 根，不是过程目录；不得放入上述三个目录，也不由 `project_closeout.py` 回收。项目最终交付后，管理员将正式成果移至项目正式目录/指定路径、归档必要证据，再按 closeout 清单处理三个临时目录。

---

## 2. 技能本地固化与调用约束

本项目在初始化时已将 `academic-project` 技能固化至根目录 `.skill/academic-project/`。
- **强制本地调用**：进入项目后，AI 优先读取并遵循本地 `.skill/academic-project/SKILL.md` 规范。
- **门禁脚本执行**：优先调用本地脚本：
  ```bash
  python ".skill/academic-project/scripts/project_preflight.py" --root "." --json
  python ".skill/academic-project/scripts/project_finish_check.py" --root "." --started-at <ts> --json
  ```
  若本地目录缺失，提示用户补齐或由初始化流程重建。

---

## 3. 启动协议 (Startup Protocol)

进入项目后，按序执行以下步骤：
1. **核验项目根目录**：确认处于项目顶层目录而非子文件夹。
2. **确认自身角色**：判定为管理员/独立维护者还是工作者。
3. **读取入口文件**：`AGENTS.md`、`PROJECT_DASHBOARD.md`、`README.md`（若存在）、`WORKLOG.md`。
4. **解析记忆根目录**：
   - 仅存在 `.project-memory/`：新结构模式；
   - 仅存在 `.paper-memory/`：旧版兼容模式；
   - 两者并存：停止写入并报告冲突；
   - 均不存在：按 `academic-project` 初始化流程处理。
5. **读取任务状态**：`<memory_root>/project_overview.md` 和 `<memory_root>/progress/current_status.md`。
6. **按需加载工作流**：根据当前任务挑选 ≤2 个相关 `workflow/` 文件。
7. **执行启动预检**：运行本地 `project_preflight.py`，确认返回 `ok: true`（退出码 0）。

---

## 4. 执行与写入边界

- **实事求是**：以实测数据与观测结果为凭据，推论单独标出，不作为事实定论。
- **数据保护**：原始数据保持只读。重命名、清理或移动须出具方案并经确认后执行；例外仅限维护者清理确切任务目录 `for_worker/<task-id>/<agent-id>/` 内经核验已过时、重复的 AI 工作者产物，并在 `review.md` 记录路径与理由。
- **Git 授权**：日常只读检查状态与登记日志；实际提交与推送严格在用户显式指示后执行。
- **看板精炼**：`PROJECT_DASHBOARD.md` 聚焦需求闭环与成果物交付，执行琐碎细节留存 `WORKLOG.md`。
- **脱敏发布**：对外开源、投稿或匿名评审前，调用 `.skill/academic-project/scripts/project_release.py` 导出纯净版本。
- **状态与清理**：工作者必须标记 `COMPLETED` 或 `INCOMPLETE_HANDOFF`。未完成只写交接件，不交付半成品；管理员独立核验完成状态并及时清理该任务下已过时的 AI 产物。最终交付时按本地 `project_closeout.py` 流程回收三个临时目录。
- **MCP 写入收口**：本契约 `mcp_governed_writes: on` 时，治理与状态文件（看板、WORKLOG、本契约、记忆根核心、交接/复核件）只能经 academic-kanban MCP（固化于 `.skill/academic-project/mcp/`）的角色工具组写入（`--role maintainer|worker` 分别挂载）；MCP 不可用时允许直写，但须在 `WORKLOG.md` 逐文件记「未经 MCP 收口：<路径>；原因：<理由>」豁免行，收尾门禁将按台账对账；用户本人手改的文件由维护者核实后经 `human_edit` 登记豁免。本键允许升为 `on`，但受管工具拒绝 `on→off`，解除约束只能由用户直接编辑本契约。业务交付物直写不受限。取值 `off` 或缺失时全部沿用本契约既有条款。

---

## 5. 任务收尾协议（Closeout Protocol）

### 若为【工作者 (Worker)】：
保持全局看板、全局日志、契约与项目记忆只读。
1. **查验派发契约**：开工前查阅 `for_manager/<task-id>/dispatch.md`，确认输入依赖齐备、明确过程沙盒与代码 checkout 路径及 DOD 验收标准；
2. **隔离执行与自测**：代码任务在派发单指定的独立 worktree/平台 checkout 内修改获准路径；非代码过程材料、日志与 WIP 写入 `for_worker/<task-id>/<agent-id>/`。运行派发单指定的自测命令并保留真实输出；
3. **标准化交接**：任务结束时落盘 `for_manager/<task-id>/<agent-id>/handoff.md`（模板见 `.skill/academic-project/templates/project-agent/worker_handoff.md`；返工轮次递增为 `handoff_v2.md`），在最终回复注明状态：
   - `COMPLETED`：列明已验证的完整交付物路径与测试证据；
   - `INCOMPLETE_HANDOFF`：交付物填“无（仅交接）”，说明已完成项、阻塞原因、WIP/工作树路径及接续建议。
4. **纪律约束**：未完成时严禁提交半成品或写入 `for_user/`；被判 `REWORK_REQUIRED` 时在原获准隔离工作区修正并提交递增版本交接件。不得因交接或项目 closeout 自动删除 worktree/分支。

### 若为【管理员 / 独立维护者 (Maintainer/Admin)】：
负责分解任务、流转调度与成果验收：
1. **任务分解与派发**：将宏观需求拆解为具有明确边界的子任务，落盘 `for_manager/<task-id>/dispatch.md`，并在 `<memory_root>/progress/current_status.md` 登记子任务矩阵；
2. **核验工作者状态**：独立核对完成声明、验收标准、真实产物和自测证据，在对应 `for_manager/<task-id>/<agent-id>/review.md` 记录 `ACCEPTED`、`REWORK_REQUIRED`、`HANDOFF_ACCEPTED` 或 `CANCELLED`；
   - 判 `ACCEPTED`：使用 `accept_deliverable` 将合格成果迁入正式路径或 `for_user/`；
   - 判 `REWORK_REQUIRED`：列明缺陷并督促工作者返工，直至达标；
   - 判 `HANDOFF_ACCEPTED`：保留过程 WIP 与代码 worktree（如有）并按需指派接续工作者；
3. **面向用户**：更新根目录 `PROJECT_DASHBOARD.md`（需求状态、正式交付路径、简要里程碑）；
4. **面向工程**：更新根目录 `WORKLOG.md`（工程记录、验证命令与技术凭证）；
5. **底层台账**：按需更新 `<memory_root>/progress/current_status.md`、`requirements/requirements_log.md` 等；
6. **任务级清理**：验收后清理对应 `for_worker/` 子目录内确认已过时/重复的工作者产物，登记路径与理由；保留接续所需 WIP 和必要复现证据；
7. **运行门禁**：执行 `project_finish_check.py`。
   **完成标准**：脚本返回 `ok: true`（退出码 0），修改物料路径真实可读。若未通过，如实汇报失败原因与已验证事项，不声明完成。

项目最终交付时，先将 `for_user/` 内核验通过的成果放入正式交付路径，将必要交接/复核文件归档至 `<memory_root>/archive/agent-handoffs/`，再按根目录 `SKILL.md` §10.3 使用 `project_closeout.py` 预览并回收 `for_user/`、`for_worker/`、`for_manager/`。若使用 `.worktrees/`，须另行通过 `git worktree list` 清点并确认无活动工作者；closeout 不会处理此目录，任何移除须单独核验状态并获得授权，分支按独立授权处置。不得在仍有活动工作者或待复核任务时封存。
