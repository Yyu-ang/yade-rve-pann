---
name: "academic-project"
version: "2.4.2"
description: "启动、执行或收尾学术研究与软件开发项目（论文、代码、数据分析、实验、报告、PPT、数据集）。维护 AGENTS.md 契约、PROJECT_DASHBOARD 看板、.skill 本地固化副本、多 AI 协同分工、MCP 写入收口与纯净发布门禁。"
---

# 学术与工程项目维护规范 (Academic Project) v2.4.2
> **当前规范版本**：`v2.4.2` | **发布日期**：2026-09-30

本项目规范是学术研究与软件开发项目的统一维护入口：统筹项目契约 `AGENTS.md`、用户进展看板 `PROJECT_DASHBOARD.md`、工程日志 `WORKLOG.md`、唯一项目记忆根目录、本地固化技能 `.skill/academic-project/`、多 AI 协同权限隔离与自动化门禁脚本。

支持项目类型：学术论文（`paper`）、学位论文（`thesis`）、综述（`review_article`）、数据分析（`data_analysis`）、代码实验（`code_experiment`）、纯代码开发（`code_project`）、项目报告（`project_report`）、学术汇报（`academic_ppt`）及数据集构建（`dataset_build`）。

本文件掌管全生命周期的核心执行协议。门禁脚本、模板与参考工作流各自承载局部实现——任务触发时渐进式加载（Progressive Disclosure）。

---

## 1. 单一事实来源 (Single Source of Truth)

- **项目根目录 `AGENTS.md`**：静态维护契约。声明本技能、记忆模式、本地技能根目录、多 AI 角色分工与门禁脚本；仅承载静态规则，动态进展由看板与记忆库记录。
- **项目根目录 `PROJECT_DASHBOARD.md`**：**面向用户的进展与成果汇总看板**。唯一展示用户需求响应状态、阶段性交付物料链接与宏观里程碑时间线。
- **临时交付区**：根目录 `for_user/`、`for_worker/`、`for_manager/` 仅服务于多 AI 协作、验收和最终交接，是过程目录，不是长期成果目录。`for_user/` 暂存待正式交付的用户成果，`for_worker/` 暂存工作者产物与 WIP，`for_manager/` 保存工作者交接件和管理员复核件。
- **正式交付物**：验收后的成果必须进入项目正式目录或用户指定的最终路径（默认可使用 `08_交付/`）。最终交付完成后，维护者归档必要验收证据并清理三个临时交付区。
- **项目根目录 `WORKLOG.md`**：**面向工程与执行的技术工作日志**。记录具体命令、技术凭证、改动文件清单与技术阻塞。
- **动态状态事实来源**：由唯一项目记忆根目录（默认为 `.project-memory/`）持久化承载。会话上下文、临时摘要与口头承诺不作为项目状态凭证。
- **MCP 写入台账**（收口项目）：`<memory_root>/mcp_write_ledger.md` 是治理文件写入的凭证来源，由 academic-kanban MCP 独占追加，收尾门禁据此对账（§7.1）。
- **本地固化技能 `.skill/academic-project/`**：项目初始化时固化的执行本体，保障项目在脱离全局环境时自包含且版本确定。
- **门禁脚本**：项目结构与状态合规性的权威裁决器。

---

## 2. 多 AI 协同分工与写入权限规则

在多 Agent 并发协作或显式分工场景下，严格执行角色权限路由，消除文件写入冲突与日志污染。

### 2.1 角色判定协议 (Role Resolution)
进入项目后，AI 依序判定自身角色：
1. **显式指定优先**：用户指令或协调器明确指定身份（如“你是项目统筹者/管理员”或“你是负责绘图的工作者/子代理”），即刻绑定该角色。
2. **默认全权模式（单 AI 兜底）**：未显式指定角色时，默认承担 **项目维护者 (Maintainer/Admin)** 职责，全权负责推进任务、维护看板、追加工程日志并执行门禁。

### 2.2 权限隔离矩阵 (Permission Matrix)
| 项目资产 / 操作 | 管理员 / 独立维护者 (Maintainer/Admin) | 任务工作者 (Worker / Specialist) |
| :--- | :---: | :---: |
| **`PROJECT_DASHBOARD.md`**（用户看板） | ✅ **唯一写入与维护权** | 🔒 严格只读 |
| **`AGENTS.md`**（项目契约） | ✅ 维护权限 | 🔒 严格只读 |
| **`WORKLOG.md`**（全局工程日志） | ✅ 汇总追加 | 🔒 严格只读 |
| **全局记忆骨架**（overview, milestones, decisions） | ✅ 统筹维护 | 🔒 严格只读 |
| **`for_manager/<task-id>/dispatch.md`**（子任务派发单） | ✅ **唯一写入与维护权** | ℹ️ **执行依据（严格只读）** |
| **指派任务交付产物**（代码、图表、指定章节文稿） | ✅ 统筹修改 | ✅ **仅限自身指派范围** |
| **`for_worker/<task-id>/<agent-id>/`**（过程产物/WIP） | ✅ 读取、验收、清理 | ✅ 仅写入获派任务目录；未完成内容仅标为 WIP |
| **`for_manager/<task-id>/<agent-id>/`**（交接与复核） | ✅ 写入复核件、归档 | ✅ 写入交接件；不得覆盖自己的原始交接 |
| **`for_user/`**（用户交付暂存区） | ✅ 唯一写入与整理权 | 🔒 只读；不得把未完成成果放入其中 |
| **局部工作者日志 (Worker Log)** | ℹ️ 审阅读取 | ✅ 写入指定工作流子目录下的局部日志 |
| **工作者交接件 (Worker Handoff)** | ℹ️ 核验、记录决策并归档 | ✅ **完成或未完成都必须落盘；未完成只交接，不交付成果** |
| **收尾门禁脚本** (`project_finish_check.py`) | ✅ 必须执行并通过验证 | ℹ️ 仅需自测交付物本身 |

> 当项目契约声明 `mcp_governed_writes: on` 时，本矩阵由 academic-kanban MCP 的角色工具组在写入时强制执行（§7.1），矩阵行即服务端路径白名单依据；`off` 时维持文字协定。

### 2.3 任务分解与派发契约 (Task Decomposition & Dispatch)
管理员拆解宏观需求时，必须在 `for_manager/<task-id>/dispatch.md` 落盘派发单（使用模板 `templates/project-agent/task_dispatch.md`），禁止口头模糊派工：
1. **拆解准则**：单一职责（如 `T01-data-clean`、`T02-baseline-exp`）、依赖显式化（声明前置 task_id）并指定专项角色。
2. **派发要素**：明确只读输入路径、非代码任务的过程沙盒 `for_worker/<task-id>/<worker-id>/`；代码任务按模板明确独立 checkout、基线、专属分支和资源方案；逐项列出正式文件直写授权（未列出者严格只读），以及**可执行的 DOD 验收命令与指标**（如 `pytest` 或自测脚本）。
3. **状态同步**：派发后在 `<memory_root>/progress/current_status.md`「子任务流转跟踪」表格登记该任务为 `DISPATCHED`。

### 2.4 工作者隔离工作区执行与标准化交接 (Worker Execution & Handoff)
工作者承接任务后，严格遵守以下纪律：
1. **先决核验**：开工前读取 `dispatch.md`，确认输入依赖齐备且沙盒路径明确；前置条件缺失立即汇报阻塞，禁止盲目开工。
2. **隔离工作区研发与实测**：代码任务仅在派发单指定的独立 worktree/平台 checkout 内修改获准路径；`for_worker/<task-id>/<worker-id>/` 只存过程材料、日志和 WIP，不是代码 checkout。非代码任务在获派的 `for_worker/` 子目录中作业。严格运行派发单指定的自测命令并保留真实输出，严禁向 `for_user/` 提交半成品。
3. **交接件落盘**：任务收尾时必须在 `for_manager/<task-id>/<worker-id>/handoff.md` 落盘标准化交接（使用模板 `templates/project-agent/worker_handoff.md`），并在最终回复注明状态：
   - `COMPLETED`：DOD 验收标准全部自测通过，列出真实成果路径与自测证据（管理员验收前不称为已接收成果）；
   - `INCOMPLETE_HANDOFF`：遇到阻塞或上下文受限，交付物填“无（仅交接）”，说明已完成项、阻塞原因、WIP/工作树路径及接续建议。已有 WIP 留在原过程沙盒；代码任务保留其 worktree 和分支供后续接手。

### 2.5 管理员独立复验、返工与接续闭环 (Review, Rework & Succession)
管理员不得仅凭工作者声明或 exit code 接收成果，须独立复测 DOD 与产物，在 `for_manager/<task-id>/<worker-id>/review.md`（使用模板 `templates/project-agent/manager_review.md`）记录裁决：
1. **裁决流转**：
   - `ACCEPTED`：验收通过。调用 `accept_deliverable` 迁入正式目录或 `for_user/`，清理该任务确认过时的 WIP（保留复现材料），更新用户看板与工程日志，激活下游依赖任务；
   - `REWORK_REQUIRED`：未达标。在 `review.md` 详述缺陷并置 `dispatch.md` 为 `REWORK`；工作者在原获准隔离工作区修复后提交递增版本 `handoff_v2.md`，管理员出具 `review_v2.md` 形成闭环；
   - `HANDOFF_ACCEPTED`：接收未完成交接。保留过程沙盒 WIP 与代码 worktree（如有），按需启动接续；
   - `CANCELLED`：需求调整终止。
2. **接续机制 (Succession)**：接替未完成任务时，管理员在 `dispatch.md` 补充接续说明并将前任过程沙盒和代码 worktree（如有）设为只读参考；新工作者分配全新 `for_worker/<task-id>/<worker-2>/` 过程目录，代码任务另分配全新 worktree 与分支，保护前任证据不被覆盖。

### 2.6 并行代码任务的 Git worktree 与资源隔离

- 多 Agent 同时修改本地 Git 仓库时，必须为每个并发写入者分配独立分支和独立 worktree；仅指定“在不同分支工作”不够。执行平台已提供独立 checkout 时，先核验实际路径和分支，不要再嵌套建 worktree。
- 经用户授权创建项目内 worktree 时，默认使用 `<project-root>/.worktrees/<task-id>/<worker-id>/`，并先确认该目录被 `.git/info/exclude` 或项目忽略规则排除。`for_worker/` 是过程产物区，不得放置完整 worktree；不适用项目内路径时才改用同级路径并记录原因。
- 创建前记录根路径、脏状态、基线 commit、目标分支/路径，检查 `git worktree list`、所需磁盘空间及大型数据/依赖策略。新 worktree 不继承未提交或被忽略文件；不得为创建它而清理、覆盖或重置现有工作。
- worktree 共用 Git 对象库/历史，但会各自检出所需的跟踪文件；大型跟踪文件可能按工作树重复占用空间，未跟踪数据、`node_modules` 和构建缓存不会自动共享。先度量，再选择稀疏检出、外部只读数据、包管理器缓存或串行工作；不要共享可变源码、数据库、依赖目录或构建输出。
- 每项代码任务的派发单与交接件记录 worktree 绝对路径、分支、基线 commit 和资源隔离方案。未经授权不得删除 worktree、分支、提交或推送。
- 详细决策、资源盘点、稀疏检出与安全清理流程见 `references/git-worktree-resource-isolation.md`。

---

## 3. 启动协议 (Startup Protocol)

每次进入项目执行任务时，必须按顺序执行以下步骤。**完成标准**：根目录边界、自身角色、本地技能状态、记忆根路径、预检状态与读取清单全部确认。

1. **定位项目根目录**：核验项目根目录标识（根目录 `AGENTS.md` 或版本控制根），确认当前处于顶级工作区而非子文件夹。
2. **确认自身角色**：判定为管理员/独立维护者还是工作者。
3. **读取入口文件**：`AGENTS.md`（旧项目兼容 `agent.md`）、`PROJECT_DASHBOARD.md`、`README.md`（若存在）、`WORKLOG.md`。缺失 `AGENTS.md` 时执行 §5 初始化与兼容规范。
4. **解析唯一记忆根目录**：依据 §4 表格定位记忆根目录。
5. **执行项目预检门禁**：
   优先调用本地固化的预检脚本：
   ```bash
   python ".skill/academic-project/scripts/project_preflight.py" --root "." --json
   ```
   **完成标准**：脚本返回 `ok: true`，退出码为 0。若预检失败，立即汇报并停止结构性写入。
6. **按需加载任务状态**：读取 `project_overview.md`、`progress/current_status.md`、`WORKLOG.md`；按需调取 ≤2 个工作流文件；复杂任务调取 `decisions/decision_log.md`。仅在任务涉及特定技能时加载 `.skill/` 下的相关扩展。
7. **对齐陈述**：用 ≤10 行文字向用户陈述：项目名称、当前角色、阶段目标、近期成果、待决事项与本次任务读取范围。目标有歧义时先澄清再执行。

---

## 4. 唯一记忆根目录 (Sole Memory Root)

| 检测情况 | 处理动作 |
|---|---|
| 仅存在 `.project-memory/` | 标准新结构。正常读取与维护。 |
| 仅存在 `.paper-memory/` | 兼容旧结构：原地就地读取维护，不自动执行跨目录迁移。 |
| 两者均不存在 | 仅在用户明确启动新项目时执行初始化；否则报告缺失并等待指令。 |
| 两者同时存在 | 停止写入，报告记忆根冲突，等待用户决策。 |

新项目一律采用 `.project-memory/`。

---

## 5. 项目结构与初始化规范

### 5.1 根目录入口布局
```text
<project-root>/
├── AGENTS.md               # 静态项目维护契约（统一取代旧版 agent.md）
├── PROJECT_DASHBOARD.md    # 面向用户的进展与成果汇总看板（极简、窗口化）
├── README.md               # 面向公众/团队的项目基本说明
├── WORKLOG.md              # 面向工程与执行的技术工作日志
├── .gitattributes          # 声明 export-ignore 规则，公开发布时自动脱敏
├── .worktrees/             # 可选：本地隔离 checkout（必须按规则忽略）
├── for_user/               # 临时用户交付暂存区（最终交付后清理）
├── for_worker/             # 工作者产物/WIP 临时区（按任务与身份隔离）
├── for_manager/            # 工作者交接与管理员复核临时区
└── .skill/
    └── academic-project/   # 本地固化的本技能完整副本（初始化时自动克隆）
```

### 5.2 核心记忆目录结构 (`.project-memory/`)
```text
.project-memory/
├── project_overview.md             # 项目基础信息、激活类型与关键渠道
├── file_registry.md                # 核心文件、数据与外部资源登记册
├── requirements/requirements_log.md # 用户需求底层完整台账
├── progress/
│   ├── milestones.md               # 项目关键里程碑
│   ├── current_status.md           # 内部状态快照、进行中任务与阻塞项
│   └── progress_log.md             # 可追踪进展记录（最新 30 条）
├── workflow/<project-type>/        # 各激活类型的具体工作流跟踪文件
├── decisions/decision_log.md       # 正式技术与架构决策 (ADR)
├── rules/file_layout.md            # 项目文件与子目录命名布局规则
├── git/commit_log.md               # Git 提交记录摘要
└── archive/                        # 归档历史日志与过期需求
```

### 5.3 本地技能固化与版本维护
1. **自动克隆固化**：运行 `project_init.py --apply` 初始化新项目时，自动将 `academic-project` 全量同步至根目录 `.skill/academic-project/`。
2. **优先本地调用**：进入项目后，AI 优先读取本地 `.skill/academic-project/SKILL.md`，门禁脚本优先调用 `.skill/academic-project/scripts/` 下的工具。
3. **版本比对与无损升级**：
   - 门禁脚本自动比对本地固化版本与全局最新版本；
   - 若本地版本落后，通过一键命令无损热升级：
     ```bash
     python "<academic-project>/scripts/project_init.py" --root "." --update-skill --apply
     ```
     该操作仅同步更新本地技能代码与模板；对未封存项目只补建缺失的三个临时交付目录及空 `.gitkeep`，不覆盖既有内容，也不改写项目记忆与契约文件。若项目已有 `.project-memory/project_closed.json` 或 `.paper-memory/project_closed.json`，升级时不重建临时目录。
4. **扩展项目技能**：自建扩展技能放置于根目录 `.skill/<skill-name>/`，禁止放入 `.project-memory/skills/` 产生竞争目录。
5. **重新激活封存项目**：仅在用户授权后运行 `python ".skill/academic-project/scripts/project_init.py" --root "." --reopen --apply`；随后更新 `progress/current_status.md` 并运行预检。

### 5.4 初始化门禁流程
**触发条件**：用户明确发起新项目，或未发现有效记忆根目录。  
初始化前步骤：
1. 检查根目录文件与历史格式；
2. 确认记忆根状态（缺失/冲突）；
3. **向用户展示拟创建的目录结构、文件清单、项目类型及写入范围**，并说明 `mcp_governed_writes` 收口开关的取值（默认 `off`；已部署 academic-kanban MCP 的项目可选 `on`）；
4. 获得用户确认后执行：
   ```bash
   python "<academic-project>/scripts/project_init.py" --root "<project-root>" --type <types> --apply
   ```
5. 初始化同时创建 `for_user/`、`for_worker/`、`for_manager/` 三个临时交付目录；完成后立即运行本地 `project_preflight.py` 验证，确认退出码为 0。

---

## 6. 用户进展汇总看板规范 (`PROJECT_DASHBOARD.md`)

看板专供用户在 30 秒内快速掌握项目全貌与交付状态，严格遵守字数上限与条目窗口化。

### 6.1 关切导向与职责划分
- **看板聚焦核心**：用户需求是否闭环、交付的具体产物路径、宏观项目阶段与关键里程碑时间线。
- **执行细节隔离**：AI 运行的脚本命令、调试日志、函数级改动与代码 diff 集中记录在 `WORKLOG.md` 或底层工程日志中，保持看板对用户的高度整洁。

### 6.2 容量与字数上限约束 (Brevity Limits)

> 收口项目（`mcp_governed_writes: on`）中，下列窗口与字数由 academic-kanban MCP 以代码强制：条数超限自动沉淀底账/归档，字数与字段超限拒写；非收口项目仍按条文自律。

1. **顶部状态快照**：仅保留 1 行（当前阶段 ≤20 字 + 状态指示灯 🟢/🟡/🔴 + 核心攻关方向 ≤30 字）。
2. **用户需求响应矩阵**：
   - **窗口期限制**：看板上**仅保留进行中及最近完成的 10 条**需求。更早记录自动沉淀至 `.project-memory/requirements/requirements_log.md` 底账中。
   - 单条需求描述：≤50 字（直指核心目标）。
   - 成果价值与自测说明：≤80 字（一句话阐明交付物效果或解决的问题）。
3. **核心阶段性成果陈列架**：
   - 仅陈列各分类最新有效物料（文稿、图表、代码、评测、数据，每类 ≤5 项；分类组缺失时首个条目自动建组）。
   - 格式：`- [成果物名称](相对路径): 一句话价值说明 (≤30字)`。
4. **工作里程碑时间线**：
   - 单条单行：`- **YYYY-MM-DD**：[事件] 达成/交付 [成果] (≤40字)`。
   - 仅保留最近 10 个关键节点。
5. **待用户决策事项**：
   - 仅保留未决议题，条目数 ≤3 条，每条 ≤60 字。

---

## 7. 证据与写入边界 (Evidence and Write Boundaries)

- **信息层级分明**：严格区隔用户原始要求、已验证事实、实现路径选择、候选推论及待核验事项。文件名、代码默认值与模型猜测不自动升格为用户要求或事实。
- **数据保护**：原始数据默认保持只读。批量重命名、删除、覆盖或外部写入须先向用户出具方案并获得确认。
- **工作者产物的窄范围清理授权**：维护者可在验收或接续确认后，清理准确任务路径 `for_worker/<task-id>/<agent-id>/` 中已过时、重复且由 AI 工作者生成的产物；须在管理员复核件记录文件路径、理由及保留/归档证据。不得触碰正式源码、原始数据、用户文件、其他任务目录或无法确认来源的文件。其他删除仍须另行确认。项目最终封存只可由 `project_closeout.py` 按逐文件清单执行。
- **凭据隔离**：密码、Token、Cookie 及私有个人数据严禁入库；配置与密钥依赖系统环境变量加载。
- **Git 操作受控**：日常仅只读检查状态与登记提交日志；实际 `git commit/push/tag` 严格在用户显式确认后执行。
- **统一版本管理**：项目默认随主项目 Git 仓库统一管理；公开发布、投稿或盲审时，调用 §11 脱敏发布机制。
- **交付状态约束**：工作者必须标明 `COMPLETED` 或 `INCOMPLETE_HANDOFF`。未完成时只交接、不交付；完成状态仍须经过管理员独立核验后才可接收。
- **临时区清理权限**：维护者按任务清理 `for_worker/` 内确认过时的 AI 产物；项目最终回收只处理三个指定临时目录，其他目录和文件沿用既有确认规则。

### 7.1 MCP 写入收口约束 (MCP Write Governance)

> 部署形态、工具面映射、台账 schema 与对账算法详见 `references/mcp-write-governance.md`（按需加载）。

- **开关**：项目契约 frontmatter `mcp_governed_writes: on` 时启用收口模式；键缺失或为 `off`（含全部 v2.1.x 存量项目）时行为与旧版完全一致，门禁零变化。新项目初始化时应向用户说明并询问选择；外部用户与零 MCP 环境默认 `off`，本技能完整流程不依赖任何 MCP。
- **收口范围**：治理与状态文件的写入必须经 academic-kanban MCP 工具完成——`PROJECT_DASHBOARD.md`、`WORKLOG.md`、`AGENTS.md`（contract_update）、`.project-memory/` 核心文件（`file_registry.md` 与 `git/commit_log.md` 除外）、`workflow/<type>/` 跟踪文件、以及验收成果迁移（accept_deliverable）。业务交付物（代码、文稿、图表、数据脚本）与全部读取操作不收口。**交接件与复核件（for_manager/）：有 MCP 的角色应当工具写入（获得字段与路径校验），无 MCP 的 worker 直写不判对账违规**——其纪律由 §2.3 与管理员 `review_write` 核验兜底。
- **获取与部署**：服务器源码随本技能发布，初始化时固化进 `.skill/academic-project/mcp/`（`server.py` + `kanban_mcp/`），项目内即用，无需另找仓库；唯一额外依赖是 PyPI 包 `mcp>=2.2,<3`。**必须安装在一个明确指定的 Python 环境中，宿主配置的 `command` 写该解释器绝对路径**（PATH 上的裸 `python` 通常没有 SDK）。接线与故障排查用 `python -E .skill/academic-project/mcp/server.py --doctor --root .` 自检。门禁与初始化脚本保持零依赖，不受此影响。
- **角色挂载**：MCP 以 stdio 按项目启动：`python -E .skill/academic-project/mcp/server.py --root <项目根> --role maintainer|worker`（宿主在项目目录启动进程时 `--root` 可缺省取当前目录）。需要常驻/多宿主共享同一进程时可改用 HTTP 形态：`--transport streamable-http --host 127.0.0.1 --port <N>`，端点为 `http://127.0.0.1:<N>/mcp`；仍是一个进程对应一个（项目, 角色）组合，只允许回环地址绑定（服务对治理文件有写权限，拒绝公网暴露）。进程即权限边界：worker 会话只暴露 `handoff_write`；maintainer 会话挂载维护者工具组（14 个）并允许收窄使用 worker 工具，共 15 个工具。业务层对维护者工具二次校验启动角色，直接 import 库绕不过。调用中的 `actor` 自报仅记入台账，不放大权限。
- **内容门禁**：看板窗口（需求 10 条、里程碑 10 条、待决策 3 条）、progress_log 30 条、需求底账 100 条等条数规则由服务器自动沉淀或归档（沉淀去向底账/记忆层/季度归档，不静默丢弃；本次写入所在行受沉淀保护）；§6.2 字数与 §2.3 字段校验失败、日期非 `YYYY-MM-DD`、单行字段含换行、交付物料路径不存在时拒写并返回原因，AI 须修正后重发。拒写返回 `{"ok": false, "error": …}` 且协议层不置错——**调用方必须解析 `ok` 字段，不得以"工具调用没报错"当作写入成功**。
- **台账与对账**：每次成功写入由 MCP 向 `<memory_root>/mcp_write_ledger.md` 追加一行 JSON（时间戳、角色、工具、目标路径与**各目标写入后的内容哈希 `sha`**；`sig` 字段预留升级位）。`on` 项目收尾门禁 `project_finish_check.py` 将任务窗口内治理文件的 mtime+内容哈希与台账及 WORKLOG 豁免行对账：先合规写入、后又偷改同一文件同样判违规。**基线宽限**：台账首条记录之前的变更（项目骨架、开关启用前的手改）与零台账项目只告警不判错，收口自第一笔 MCP 写入起硬执法。`--started-at` 接受 Unix 秒或 `YYYY-MM-DD HH:MM`。
- **人工编辑豁免**：对账不区分作者；用户本人手改治理文件后，维护者须经核实，再调用 `human_edit` 登记豁免行（注明「人工编辑」与背书人）；`human_edit` 拒绝 `AGENTS.md` 与 `WORKLOG.md` 自身，且不得用于为 AI 自己的绕道直写洗白。**豁免只覆盖登记前已发生的变更**；之后再改同一文件必须重新登记。
- **开关单向锁定**：`mcp_governed_writes` 允许经受管工具由 `off` 升为 `on`，**任何受管工具路径（含 contract_update 的 replace）都拒绝 `on→off`**——解除约束只能由用户本人直接编辑契约；AI 也不得代用户改写该键，降级操作应在 WORKLOG 注明系用户亲手所为。
- **降级**：MCP 不可用（服务未启动、宿主未挂载、worker 子代理无 MCP）时允许直写，但须在 `WORKLOG.md` 逐文件记一行「`未经 MCP 收口：<相对路径>；原因：<理由>`」作为对账豁免凭证。宣布降级前先用宿主同款解释器运行 `python -E .skill/academic-project/mcp/server.py --doctor --root .` 自检并如实粘贴结果；`on` 项目里未经验证就习惯性声明不可用，属于收口漂移，收尾门禁会对全窗口零台账发出警告。**门禁脚本与初始化流程永不依赖 MCP 可达性**：MCP 缺席不得导致任何既有门禁失败。

---

## 8. 项目类型路由 (Type Routing)

工作流参考文件按需渐进式加载（Progressive Disclosure），不进行全量载入：

| 项目类型 | 入口参考与模板 | 适用场景说明 |
|---|---|---|
| `paper`, `thesis`, `review_article` | `references/paper-workflow.md` | 论文全生命周期：选题、调研、实验、写作、审稿；包含学位论文与综述特有差异。 |
| `data_analysis` | `templates/workflow/data_analysis/` | 探索性数据分析、统计检验、特征工程与分析报告。 |
| `code_experiment` | `templates/workflow/code_experiment/` | 紧密配合科研问题、对比消融的实验型代码。 |
| `code_project` | `references/code-project-workflow.md` + `templates/workflow/code_project/` | 常规软件、开源库、CLI 工具、Web 服务与自动化组件开发；无学术论文写作环节。 |
| `project_report` | `templates/workflow/project_report/` | 课题结题、阶段汇报或技术调研报告。 |
| `academic_ppt` | `templates/workflow/academic_ppt/` | 学术汇报幻灯片：叙事提纲、逐字稿、排版与演练反馈。 |
| `dataset_build` | `templates/workflow/dataset_build/` | 数据集构建、清洗标注规范、元数据与基准划分。 |

---

## 9. 项目级技能与 WikiSkill 演进

路径：`<project-root>/.skill/<skill-name>/SKILL.md`（及可选 `wikiskill/`）。

1. 根目录 `.skill/` 可除固化的 `academic-project` 外为空。
2. 仅在任务直接相关时加载扩展技能，不全量扫描原始追踪。
3. 仅在沉淀高复用价值的排错或实施模式时，或用户明确要求时建立 WikiSkill。
4. 演进闭环：`原始执行追踪 (Raw trace) → Wiki 模式 (Wiki Pattern) → 候选技能 (Candidate Skill) → 可执行门禁验证 (Executable gate)`。
5. 规则仲裁：项目技能若与全局规则冲突，全局规则优先。

---

## 10. 任务收尾协议 (Closeout Protocol)

在结束任何一轮任务前，AI 依据自身角色完成收尾：

### 10.1 若为【工作者角色 (Worker)】
1. 保持全局看板与契约文件只读。
2. 自测修改的业务代码或文稿，确认功能与格式合规。
3. 在 `for_manager/<task-id>/<agent-id>/handoff.md` 落盘符合 §2.3 的交接件，并在最终回复注明 `COMPLETED` 或 `INCOMPLETE_HANDOFF`。未完成只交接，不交付半成品。

### 10.2 若为【管理员 / 独立维护者 (Admin/Maintainer)】

> `mcp_governed_writes: on` 的项目，下列 1 中的全部治理文件写入须经 academic-kanban MCP 维护者工具组完成（§7.1）。

1. **分级更新**：
   - **无项目改动**（纯咨询/审阅）：运行 `project_finish_check.py --no-project-change`。
   - **有项目改动**：
     - **面向用户**：按精简规范更新根目录 `PROJECT_DASHBOARD.md`；
     - **面向工程**：更新根目录 `WORKLOG.md`；
     - **状态与阻塞**：更新 `<memory_root>/progress/current_status.md`；
     - **可追踪进展**：更新 `<memory_root>/progress/progress_log.md`；
     - **重大决策**：更新 `<memory_root>/decisions/decision_log.md`；
     - **工作流细节**：更新对应的 `workflow/<type>/` 文件。
2. **执行收尾门禁检查**：
   运行本地门禁脚本：
   ```bash
   python ".skill/academic-project/scripts/project_finish_check.py" --root "." --started-at <unix_ts> --json
   ```
3. **完成标准**：受影响文件更新完毕，门禁脚本输出 `ok: true`（退出码 0），变更物料路径真实可查。若检查未通过，如实汇报失败原因与已验证事项，严禁在门禁未通过时声明完成。

### 10.3 项目最终交付与临时目录回收
项目最终交付（不是普通任务收尾）时，维护者必须：
1. 确认所有工作者均已停止写入；核验所有 `COMPLETED` 结果，处理完所有 `INCOMPLETE_HANDOFF`（接续完成或明确取消），不存在待复核/返工中的任务。
2. 若使用 `.worktrees/`，通过 `git worktree list` 清点并确认无活动工作者；该目录不属于三个临时目录，`project_closeout.py` 不会处理它。任何移除都须单独核验状态并取得授权，分支按独立授权处置。
3. 将已验收的 `for_user/` 文件移至正式项目目录（如 `08_交付/`）或用户指定路径；对不再交付的暂存文件逐项填写 `user_discard` 与理由；将必要的工作者交接件与管理员复核件归档到 `<memory_root>/archive/agent-handoffs/`；对 `for_worker/` 材料逐项决定归档或清理，并记录理由。同步更新项目状态与必要的 `WORKLOG.md` 记录。不得让清理脚本替代内容验收。
4. 复制 `templates/project-agent/closeout_manifest.json` 至 `for_manager/closeout_manifest.json` 并填写完整处置清单；工作者成果须关联 `task_id`、`worker_id`、`owner_role: worker` 和已验收状态，维护者成果标记 `owner_role: maintainer`。旧 `.paper-memory/` 项目须将归档目标前缀改为 `.paper-memory/archive/`。随后运行本地 `project_closeout.py --root .` 预览。默认 dry-run 会检查状态、源/目标路径、文件覆盖和处置清单完整性。
5. 维护者核对预览清单并获得本次清理授权后，运行 `project_closeout.py --root . --apply`。脚本仅按清单迁移/归档已核验文件、清理明确标记的过时工作者产物、保存收尾凭证，并移除三个临时交付目录；不会触碰其范围外文件。
6. 运行 `project_preflight.py` 与 `project_finish_check.py --root . --started-at <unix_ts>` 复核封存状态：正式成果及归档凭证存在，三个临时目录已移除，`<memory_root>/project_closed.json` 指向有效收尾凭证。

项目仍在进行时不得运行最终回收。若封存后重新启动项目，先由维护者按用户授权解除封存、恢复临时目录并记录重启，再开始协作。

---

## 11. 纯净公开发布与脱敏交付协议 (Public Release Protocol)

当项目需要面向开源社区、期刊提审代码复现（如 Nature/IEEE/Elsevier Code Availability）、Zenodo 归档或双盲匿名评审时，采用脱敏发布机制。

### 11.1 一键发布工具 (`scripts/project_release.py`)
在项目根目录下调用本地发布脚本：

1. **生成纯净发布分支（非侵入式，不污染当前工作区）**：
   ```bash
   # 预览将被剥离的内部文件与公开文件
   python ".skill/academic-project/scripts/project_release.py" --branch release
   
   # 正式提交并打上版本标签
   python ".skill/academic-project/scripts/project_release.py" --branch release --tag v1.0.0 --apply
   ```
   **实现原理**：通过底层 Git Plumbing 树对象构建，自动剔除 `.project-memory/`、`.skill/`、`.worktrees/`、`for_user/`、`for_worker/`、`for_manager/`、`AGENTS.md`、`WORKLOG.md`、`PROJECT_DASHBOARD.md` 及临时调试文件，直接提交到独立的 `release` 或 `public` 分支，当前开发工作区与主分支保持原样。

2. **导出纯净 ZIP 或脱敏文件夹**：
   ```bash
   # 导出 ZIP 包（供期刊系统或云盘上传）
   python ".skill/academic-project/scripts/project_release.py" --export-zip ./release_v1.0.0.zip --apply
   
   # 导出干净文件夹
   python ".skill/academic-project/scripts/project_release.py" --export-dir ./clean_export --apply
   ```

### 11.2 Git 原生归档机制 (`.gitattributes`)
初始化时根目录已预置 `.gitattributes`，声明了所有内部记忆与管理文件的 `export-ignore` 属性。直接执行原生命令：
```bash
git archive HEAD -o publication_clean.zip
```
解压后即为 100% 纯净的公开物料。

---

## 12. 辅助门禁工具一览

所有工具均支持 `--version` 查询（当前 `v2.4.2`）：

| 工具 / 脚本 | 职责定位与核心参数 |
|---|---|
| `scripts/project_preflight.py` | 启动结构门禁。校验根目录、AGENTS.md、WORKLOG.md、PROJECT_DASHBOARD.md、唯一记忆根、UTF-8 编码与本地技能固化及版本比对；解析 `mcp_governed_writes` 开关并在结果中报告收口模式。失败返回非零。 |
| `scripts/project_finish_check.py` | 收尾校验门禁。复核结构，配合 `--started-at` 校验 WORKLOG.md 修改时间戳，提示看板更新状态；`mcp_governed_writes: on` 的项目额外执行 MCP 写入台账对账（§7.1）。`--no-project-change` 跳过增量校验。 |
| `scripts/project_init.py` | 脚手架生成与升级工具。`--type` 初始化完整结构；`--update-skill --apply` 同步技能并为活动项目补建临时目录；`--reopen --apply` 经授权恢复已封存项目。 |
| `scripts/project_release.py` | 公开发布与脱敏工具。`--branch` 生成纯净分支，`--export-zip` 导出脱敏压缩包，`--export-dir` 导出脱敏目录。 |
| `scripts/project_closeout.py` | 项目最终交付与临时区回收。默认 dry-run 校验状态和逐文件处置清单；`--apply` 按清单迁移/归档/清理三个过程目录，并写入封存凭证。 |
| `scripts/project_check_common.py` | 底层共用校验逻辑、版本定义 (`SKILL_VERSION`)、`TEMPLATE_MAP` 映射与合法项目类型定义。 |
| `mcp/server.py` | academic-kanban 收口服务器（随技能固化分发，§7.1）。`--doctor` 接线自检，`--version` 查询；需 `mcp>=2.2,<3`。 |

---

## 13. 兼容性与演进边界

- **契约规范统一**：项目根契约全面统一为 `AGENTS.md`。存量 `agent.md` 检出时自动发出重命名升级提示。
- **职责边界划分**：`academic-project` 负责项目记忆架构、契约标准、本地技能固化与门禁管理；外部编排技能负责流程调度与外部调用。若遇记忆结构冲突，以本规范为准。
- **类型隔离原则**：`code_project` 专用于纯软件工程；`code_experiment` 仅在代码与科研实验设计、学术结论深度绑定时使用，保持界限清晰。
- **操作安全边界**：不自动批量删除项目文件、不私自拷贝外部未知数据、不自动迁移记忆根目录、不私自执行 Git 提交推送。仅授权维护者清理精确 `for_worker/<task-id>/<agent-id>/` 内确认过时的 AI 工作者产物，以及经用户确认/授权并由 `project_closeout.py` 清单约束的三个临时过程目录；其他删除沿用显式确认规则。
- **规范演进流程**：修改本规范前，须在沙盒副本中验证门禁与升级测试，测试通过后再合并发布。
