# KON Media / KON Search - Auto-Update Script (PowerShell)
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  KON Media / KON Search -- Auto-Update" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/3] Pulling latest commits from GitHub origin/main..." -ForegroundColor Yellow
try {
    git pull origin main
} catch {
    Write-Host "[Notice] Local changes detected. Stashing and retrying pull..." -ForegroundColor DarkYellow
    git stash
    git pull origin main
    git stash pop
}

Write-Host ""
Write-Host "[2/3] Building latest frontend bundle..." -ForegroundColor Yellow
Set-Location "$ScriptDir\frontend"
npm run build
Set-Location $ScriptDir

Write-Host ""
Write-Host "[3/3] Successfully updated to the latest version!" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
git log -1 --pretty=format:"Latest commit: %h - %s (%cd)" --date=relative
Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
