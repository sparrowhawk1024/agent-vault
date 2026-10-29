# AgentVault Application Launcher for PowerShell
Set-Location $PSScriptRoot

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "          AGENTVAULT APPLICATION LAUNCHER" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[ERROR] Virtual environment not found at .venv\Scripts\python.exe." -ForegroundColor Red
    exit 1
}

& ".venv\Scripts\python.exe" "scripts\run_app.py"

