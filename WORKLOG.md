# WORKLOG（工程与执行工作日志）

> **定位**：记录工程动作、验证证据、改动范围与技术阻塞。需求状态见 `PROJECT_DASHBOARD.md`。

## [2026-10-05 15:25 +08:00] 克隆仓库并初始化学术项目管理结构

- **用户目标**：在 `E:\EX_library\code` 下建立独立仓库工作目录，拉取远端已有文件，安装学术管理技能并推送远端，供后续 AI 继续开发。
- **远端基线**：`https://github.com/Yyu-ang/yade-rve-pann`，默认分支 `main`；克隆时 HEAD 为 `43a83722662516902fe618df8fd73ca1da65a162`。远端为 private。
- **本地路径**：`E:\EX_library\code\yade-rve-pann`。
- **远端同步**：首次克隆后发现 `origin/main` 新增提交 `6d17aafb6846ae5dec8b28d09d0c64eac6b255c9`；经路径冲突检查无重叠后已 `merge --ff-only`，现本地基线与 `origin/main` 一致。新增的 `docs/reproduction_plan.md` 已读取并纳入项目交接。
- **远端已有环境文件**：该提交还跟踪约 520 个 `.venv/` 路径；本次保持原样，不执行环境代码，也不将其纳入本次暂存差异。
- **执行动作**：保留远端 README、方法说明及源码；按用户确认的 `code_experiment` 类型固化 `academic-project` v2.4.2，建立项目契约、状态看板、记忆骨架和协作目录；治理收口设为 `off`。
- **验证证据**：本地 `project_preflight.py --json` 与 `project_finish_check.py --json` 均返回 `ok: true`；本地技能版本与项目版本均为 `2.4.2`；初始化创建 119 个文件，原有 `README.md` 未覆盖；远端快进后 `main` 与 `origin/main` 同指向 `6d17aafb6846ae5dec8b28d09d0c64eac6b255c9`。
- **代码范围**：本次未修改算法源码，不运行数值实验；计算代码验证留给后续开发任务。
- **发布状态**：用户已授权推送 `main`；将只暂存本次新建的管理结构，不包含远端原有的 `.venv/` 或源码变更；推送后读回核验。
- **下一步**：复核精确暂存文件清单与敏感信息，提交并推送 `main`；后续开发按 `docs/reproduction_plan.md` 从解析 Example I 开始。
- **关联文件**：`AGENTS.md`、`PROJECT_DASHBOARD.md`、`.skill/academic-project/`、`.project-memory/`。

## [2026-10-05 15:43 +08:00] 移除误提交的 .venv/

- **背景**：`6d17aaf` 提交时 `git add -A` 误将 `.venv/`（519 个文件，约 1.1GB，torch CPU 环境）纳入跟踪；用户指示移除。
- **执行动作**：`git rm -r --cached .venv`（519 路径）+ `.gitignore` 追加 `.venv/` + 删除本地 `.venv/` 目录。
- **验证**：`git status` 确认 519 D + 1 M；`git ls-files | grep -c "^\.venv/"` 应为 0（提交后复核）。
- **后续影响**：Phase 1 需要 torch 时重建环境，位置改到仓库外（如 `~/workspace/venvs/`），不再进仓库。
