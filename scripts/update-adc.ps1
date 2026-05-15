<#
.SYNOPSIS
    Pull latest AdCreatives master and restart the dashboard service.

.DESCRIPTION
    Intended to run on the always-on host PC. Resolves the repo root from this
    script's own location, so it works whether invoked from PowerShell, a Tailscale
    SSH session, or a desktop shortcut.

    Skips the service restart when there are no new commits to avoid interrupting
    active dashboard users. Surfaces pyproject.toml changes so you know when to
    re-run `pip install -e .`.

.EXAMPLE
    C:\AdCreatives\scripts\update-adc.ps1
#>

$ErrorActionPreference = "Stop"

$ScriptRoot  = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot    = Split-Path -Parent $ScriptRoot
$ServiceName = "AdCreativesDashboard"

Write-Host "AdCreatives update" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"
Write-Host ""

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "git not found on PATH." -ForegroundColor Red
    exit 1
}

Push-Location $RepoRoot
try {
    $beforeSha = git rev-parse HEAD
    Write-Host "Before:  $beforeSha"

    Write-Host "Pulling origin master..." -ForegroundColor Yellow
    git pull --ff-only origin master
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "git pull --ff-only failed." -ForegroundColor Red
        Write-Host "Probable cause: local changes on this PC diverged from master."
        Write-Host "Inspect with: git status; git log --oneline -5"
        exit 1
    }

    $afterSha = git rev-parse HEAD
    Write-Host "After:   $afterSha"
    Write-Host ""

    if ($beforeSha -eq $afterSha) {
        Write-Host "Already up to date. No restart needed." -ForegroundColor Green
        exit 0
    }

    # Warn on dependency-file changes that need a pip reinstall.
    $changedFiles = git diff --name-only $beforeSha $afterSha
    if ($changedFiles -match "pyproject\.toml") {
        Write-Host "NOTE: pyproject.toml changed. Dependencies may have shifted." -ForegroundColor Yellow
        Write-Host "Run this after the restart if anything breaks:"
        Write-Host "  cd $RepoRoot"
        Write-Host "  .\.venv\Scripts\Activate.ps1"
        Write-Host "  pip install -e ."
        Write-Host ""
    }

    if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
        Write-Host "nssm not found on PATH. Service not restarted." -ForegroundColor Red
        Write-Host "Code is updated, but the dashboard still runs the old version until restart."
        exit 1
    }

    Write-Host "Restarting $ServiceName..." -ForegroundColor Yellow
    nssm restart $ServiceName | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Service restart failed. Check: nssm status $ServiceName" -ForegroundColor Red
        exit 1
    }

    Start-Sleep -Seconds 2
    $status = (nssm status $ServiceName).Trim()
    Write-Host "Service status: $status" -ForegroundColor Green

    Write-Host ""
    Write-Host "Update complete." -ForegroundColor Green
}
finally {
    Pop-Location
}
