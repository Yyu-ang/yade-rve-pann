# 核心模板与目标路径映射

| 模板文件 (Template) | 目标路径 (在 `<memory_root>/` 下) | 说明 |
|:--|:--|:--|
| `project_overview.md` | `project_overview.md` | 项目基础信息与类型声明 |
| `file_registry.md` | `file_registry.md` | 核心文件与外部资源登记册 |
| `current_status.md` | `progress/current_status.md` | 内部状态快照、进行中任务与阻塞项 |
| `progress_log.md` | `progress/progress_log.md` | 可追踪进展历史记录（保留最近 30 条） |
| `milestones.md` | `progress/milestones.md` | 项目里程碑登记表 |
| `decision_log.md` | `decisions/decision_log.md` | 正式架构与技术决策记录 (ADR) |
| `requirements_log.md` | `requirements/requirements_log.md` | 用户需求底层历史日志（新结构模式） |
| `file_layout.md` | `rules/file_layout.md` | 项目文件与目录命名布局规则 |
| `commit_log.md` | `git/commit_log.md` | Git 提交摘要（兼容模式位于 `git_summaries/`） |
| `gitignore.md` | `.gitignore` | 记忆层大文件忽略规则（复制时重命名） |

标准映射定义见 `scripts/project_check_common.py::TEMPLATE_MAP`。
