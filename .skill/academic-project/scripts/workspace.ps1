param(
    [Parameter(Mandatory=$true)][ValidateSet("create","remove","list")] [string]$Action,
    [string]$Task,
    [string]$Base = "main"
)

$Repo = (git rev-parse --show-toplevel 2>$null)
if (-not $Repo) { throw "Not inside a Git repository." }

$Repo = (Resolve-Path $Repo).Path
$Root = Join-Path $Repo ".worktrees"

switch ($Action) {
    "create" {
        if (-not $Task) { throw "Task name required." }

        $Branch = "agent/$Task"
        $Path = Join-Path $Root $Task

        if (Test-Path $Path) { throw "Worktree already exists: $Path" }

        New-Item -ItemType Directory -Force $Root | Out-Null
        git worktree add -b $Branch $Path $Base
        if ($LASTEXITCODE) { exit $LASTEXITCODE }

        Write-Output "BRANCH=$Branch"
        Write-Output "WORKTREE=$Path"
    }

    "remove" {
        if (-not $Task) { throw "Task name required." }

        $Branch = "agent/$Task"
        $Path = Join-Path $Root $Task

        git worktree remove $Path
        if ($LASTEXITCODE) { exit $LASTEXITCODE }

        git branch -d $Branch 2>$null
    }

    "list" {
        git worktree list
    }
}
