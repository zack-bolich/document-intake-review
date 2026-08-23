[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)]
    [ValidateSet('codex', 'codex-cloud', 'claude', 'devin')]
    [string]$Agent,

    [Parameter(Mandatory)]
    [ValidateRange(1, 999999)]
    [int]$Issue,

    [Parameter(Mandatory)]
    [ValidatePattern('^[a-z0-9]+(?:-[a-z0-9]+)*$')]
    [string]$Slug,

    [string]$Base = 'origin/main'
)

$ErrorActionPreference = 'Stop'

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$repositoryName = Split-Path $repositoryRoot -Leaf
$parentDirectory = Split-Path $repositoryRoot -Parent
$branch = "agent/$Agent/$Issue-$Slug"
$worktreePath = Join-Path $parentDirectory "$repositoryName-$Agent-$Issue-$Slug"

git -C $repositoryRoot rev-parse --is-inside-work-tree | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Not a Git repository: $repositoryRoot"
}

git -C $repositoryRoot show-ref --verify --quiet "refs/heads/$branch"
if ($LASTEXITCODE -eq 0) {
    throw "Local branch already exists: $branch"
}

if (Test-Path -LiteralPath $worktreePath) {
    throw "Worktree path already exists: $worktreePath"
}

if ($PSCmdlet.ShouldProcess($worktreePath, "Create branch $branch from $Base")) {
    if ($Base -eq 'origin/main') {
        git -C $repositoryRoot fetch origin main
        if ($LASTEXITCODE -ne 0) {
            throw 'Failed to refresh origin/main.'
        }
    }

    git -C $repositoryRoot rev-parse --verify "$Base^{commit}" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Base revision does not exist locally: $Base."
    }

    git -C $repositoryRoot worktree add -b $branch $worktreePath $Base
    if ($LASTEXITCODE -ne 0) {
        throw 'git worktree add failed.'
    }

    Write-Output "Created worktree: $worktreePath"
    Write-Output "Created branch:   $branch"
    Write-Output "Open this directory in the assigned agent and give it GitHub issue #$Issue."
}
