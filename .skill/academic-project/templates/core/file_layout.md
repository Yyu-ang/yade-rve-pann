# 文件布局规则
> 冻结状态：[未确认 / 已冻结 YYYY-MM-DD]　（冻结前可与用户增删改，冻结后 AI 写入必须校验合规）

## 目录骨架（推荐，可调整）

```
00_管理/ 01_文献/ 02_数据/ 03_代码/ 04_实验/ 05_图表/ 06_稿件/ 07_评审/ 08_交付/ 99_归档/
```

## 多 AI 临时协作目录

- `for_user/`、`for_worker/`、`for_manager/` 是根目录预留的临时过程区，按任务和 AI 身份隔离；不得作为长期成果目录。
- 项目最终交付时，维护者按 closeout 清单迁移/归档正式成果与必要证据，再清理这三个目录。
- 正式交付成果进入 `08_交付/` 或用户指定的路径。

## Git worktree 开发目录

- 并行代码任务获准使用 Git worktree 时，项目内默认放在 `.worktrees/<task-id>/<worker-id>/`；它是代码 checkout，不是正式成果，也不是 `for_worker/` WIP。
- 创建前确保 `.worktrees/` 已被项目忽略规则排除；本机专用时优先使用 `.git/info/exclude`，团队共同约定时才更新项目 `.gitignore`。
- `.worktrees/` 不属于最终交付区或 closeout 清理对象；只可在核实工作树干净并获准后用 `git worktree remove` 回收。

## 命名规则
- 常规文件：`YYYYMMDD_主题_vN.ext`
- AI 生成的正式成果：进入上述指定子目录并带 `_AI` 标记，如 `20260902_基准对比_v1_AI.xlsx`。
- 多 AI 协作过程产物：只放入根目录 `for_worker/`、`for_manager/` 或暂存 `for_user/`，并按任务与身份隔离；这些过程目录在项目最终交付时回收。
- 项目根目录允许保留 `AGENTS.md`、`PROJECT_DASHBOARD.md`、`README.md`、`WORKLOG.md`、`.gitattributes`、`.skill/`、`.worktrees/`（仅限本地隔离 checkout）、唯一记忆目录及活动项目中的三个临时交付目录；其他正式产物进入冻结后的指定子目录。

## 调整记录
- [用户对骨架的增删改在此记录，注明日期]
