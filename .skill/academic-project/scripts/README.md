# `workspace.ps1` 用法

在目标 Git 仓库中运行脚本。`<skill-root>` 表示 `academic-project` 技能包目录。

```powershell
# 列出当前仓库的 worktree
& "<skill-root>\scripts\workspace.ps1" -Action list

# 从指定基线创建 worktree；省略 -Base 时默认使用 main
& "<skill-root>\scripts\workspace.ps1" -Action create -Task <task-worker-id> -Base <base-ref>

# 移除对应 worktree
& "<skill-root>\scripts\workspace.ps1" -Action remove -Task <task-worker-id>
```

`create` 会创建 `.worktrees/<Task>` 目录和 `agent/<Task>` 分支；`remove` 移除 worktree 后还会尝试删除同名分支。`Task` 应在创建与移除时保持一致。
