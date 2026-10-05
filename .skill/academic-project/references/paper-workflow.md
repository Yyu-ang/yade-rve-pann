# 论文项目参考流程

本文件是 `academic-project` 的 `paper` 类型参考流程。它吸收原 `academic-paper-project` 的论文维护要求，但不再作为独立技能调用。

## 1. 适用范围

当项目涉及以下任一内容时读取本文件：

- 学术论文、会议论文或期刊论文；
- 学位论文、学位论文中的独立研究章节；
- 综述、系统综述或文献计量论文；
- 论文投稿、审稿回复、修改和定稿归档。

数据分析、代码实验和项目报告可以作为同一项目的并行类型存在。论文流程不取代这些类型，而是引用它们的结果。

## 2. 论文生命周期

```text
选题与研究问题
  ↓
文献调研与研究空白
  ↓
方法、数据和实验设计
  ↓
实验/分析执行与结果登记
  ↓
论文结构与写作
  ↓
投稿、审稿和回复
  ↓
版本修改与一致性核验
  ↓
定稿、材料归档和可复现性检查
```

每次阶段切换都要更新项目状态；不因产生一份草稿就宣称研究结论已验证。

## 3. 选题与研究问题

使用 `workflow/paper/topic_selection.md` 记录：

- 核心研究问题和子问题；
- 研究对象、边界和不研究的内容；
- 预期创新点/贡献点及其证据状态；
- 技术、数据、时间和伦理可行性；
- 与已有研究的关系；
- 选题决策、依据和影响。

选题阶段必须区分：

- 用户明确提出的研究目标；
- 助手整理出的候选表述；
- 尚未由文献或数据支持的假设。

没有明确边界时，先澄清研究问题、目标产出和评价标准，再建立实验或写作计划。

## 4. 文献调研

使用 `workflow/paper/literature_review.md` 记录：

- 核心文献的完整书目信息；
- 文献来源、研究对象、方法和主要结论；
- 与当前项目的具体关系；
- 研究空白和争议点；
- 按主题组织的综述笔记；
- 待读文献队列及优先级。

文献结论必须保留出处。不得仅凭标题、摘要片段或模型记忆写成已经核验的事实。引用、数据、方法和实验结果分别登记，不把检索结果直接当成研究结论。

## 5. 方法、数据和实验

使用 `workflow/paper/experiments.md` 记录：

- 研究设计和参数配置；
- 数据集来源、范围、版本、筛选和排除规则；
- 标签、特征、单位和评价指标；
- 基线、对照组、数据切分和随机性；
- 每次实验的时间、代码版本、关键参数和输出路径；
- 失败实验、失败原因和避免重复的教训；
- 结果表格、图表路径和可复核证据。

实验记录必须区分：

- 原始运行输出；
- 统计或可视化结果；
- 对结果的解释；
- 尚未验证的机制假设；
- 可以写入论文的结论。

没有明确字段语义、单位、样本边界或评价口径时，不启动论文级结论写作。

## 6. 写作维护

使用 `workflow/paper/writing_progress.md` 记录：

- 各章节状态：未开始、进行中、初稿完成、已修改、已定稿；
- 字数和最近修改时间；
- 待写内容、写作阻塞和待确认事项；
- 图表文件路径、插入状态和正文引用状态；
- 需要与实验、数据或参考文献同步的内容。

写作时：

1. 先读取当前章节状态和对应实验/文献证据；
2. 保留作者已确认的事实、术语、引用和不确定性；
3. 不把候选解释写成确定性结论；
4. 写入前检查文件命名、版本和输出位置；
5. 完成后更新写作进度和根目录 `WORKLOG.md`。

## 7. 投稿与审稿回复

投稿后使用 `workflow/paper/review_response.md` 记录：

- 投稿、返修和回复截止日期；
- 审稿人意见原文或可追溯摘录；
- 意见类型、严重程度和回复策略；
- 修改位置、具体修改内容和状态；
- 需要补充的分析、实验或引用；
- 回复信与论文版本的一致性。

回复审稿意见时，不得声称已经完成尚未运行的实验，也不得把“计划修改”写成“已修改”。

## 8. 版本修改与定稿

使用 `workflow/paper/revision_log.md` 记录：

- 版本号、日期和变更概述；
- 变更原因：审稿意见、自我修订、合作者建议或错误修正；
- 章节、图表、公式、数据和代码的联动影响；
- 需要重新核验的统计量、引用和交叉引用；
- 当前版本的可复现性和归档状态。

定稿前至少核验：

- 正文数字与结果文件一致；
- 图表编号、正文引用和文件路径一致；
- 参考文献引用完整；
- 方法、数据、代码和补充材料版本一致；
- 审稿意见均有可追溯处理状态；
- 未验证内容没有被写成最终结论。

## 9. 与统一项目记忆的映射

### 新结构

```text
.project-memory/
├── project_overview.md
├── progress/current_status.md
├── progress/progress_log.md
├── requirements/requirements_log.md
├── decisions/decision_log.md
└── workflow/paper/
    ├── topic_selection.md
    ├── literature_review.md
    ├── experiments.md
    ├── writing_progress.md
    ├── review_response.md
    └── revision_log.md
```

### legacy 结构

```text
.paper-memory/
├── project_overview.md
├── progress/current_status.md
├── progress/progress_log.md
├── decisions/decision_log.md
├── workflow/
│   ├── topic_selection.md
│   ├── literature_review.md
│   ├── experiments.md
│   ├── writing_progress.md
│   ├── review_response.md
│   └── revision_log.md
└── git_summaries/commit_log.md
```

legacy 项目沿用原路径；不因使用本参考流程而创建 `.project-memory`。

## 10. 论文项目的维护门禁

工作开始前：

- 读取 `AGENTS.md`、`PROJECT_DASHBOARD.md`、项目总览、当前状态和 `WORKLOG.md`；
- 运行 `project_preflight.py`；
- 确认当前论文阶段和本次任务影响范围。

工作结束前：

- 更新至少一个受影响的论文 workflow 文件或明确说明本次无阶段状态变化；
- 管理员角色更新面向用户的 `PROJECT_DASHBOARD.md` 与工程 `WORKLOG.md`；工作者角色提交标准化交接汇报；
- 需要时同步 `current_status.md`、`progress_log.md`、`decision_log.md`；
- 运行 `project_finish_check.py`；
- 报告已验证证据、未验证主张和遗留阻塞。

## 11. 项目级 WikiSkill

论文项目只有在出现可重复的文献、实验、写作、审稿或归档模式时才创建项目级 WikiSkill。其路径为：

```text
<project-root>/.skill/<skill-name>/wikiskill/
```

原有 `.paper-memory/wikiskill/` 只在 legacy 项目中兼容读取。不得同时创建一套等价的 `.project-memory/skills/`，也不得把一次性论文笔记自动升级为全局技能。

## 12. thesis 差异

thesis 共享 §3-6 流程，以下环节独立。注意 workflow 文件按类型作用域：本节所称"共享"指流程方法，落盘路径一律在 `workflow/thesis/` 自己的目录内（如 `writing_progress.md` 未随类型实例化时，可经 `workflow_update` 按需创建，收口工具仅放行本项目已激活类型）。

### 12.1 开题

`workflow/thesis/topic_selection.md`。除一般选题要素外记录章节结构设想、开题时间/材料/评审结论、开题意见与修改（关联 `decision_log.md`）。

### 12.2 章节进度

`workflow/thesis/chapter_progress.md` 代替或补充 `writing_progress.md`，逐章跟踪状态、字数、目标字数和导师意见。

### 12.3 盲审

`workflow/thesis/blind_review.md`。对应论文审稿回复（§7），评审来源为盲审专家。记录意见摘要、回复策略、修改落点和一致性核验。

### 12.4 答辩准备

`workflow/thesis/defense_prep.md`。答辩日期、形式、核心贡献、预设问答、证据位置和材料清单。期刊论文无此环节。

## 13. review_article 差异

review_article 共享 §6-8 写作/审稿/版本流程，前期方法学独立：

### 13.1 检索策略

`workflow/review_article/search_strategy.md`。数据库、检索式、时间范围、纳入/排除标准和命中数。综述的“实验设计”即检索策略。

### 13.2 文献矩阵

`workflow/review_article/literature_matrix.md`。行=文献，列=对比维度；维度定稿后不随意改变。与 `literature_review.md` 互补。

### 13.3 写作与大纲

`workflow/review_article/outline.md` + `writing.md`。综述先定大纲和主题分组，按主题展开——与论文的顺序写作不同。

### 13.4 维护更新

`workflow/review_article/maintenance.md`。综述发表后可能需定期更新检索和结论。
