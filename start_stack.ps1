# AgentVault Full-Stack Startup Script
$PSScriptRoot = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition
if (-not $PSScriptRoot) { $PSScriptRoot = (Get-Location).Path }

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   Starting AgentVault Full Stack" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Locate Foundry binaries
$anvilBin = "$env:USERPROFILE\.foundry\bin\anvil.exe"
$forgeBin = "$env:USERPROFILE\.foundry\bin\forge.exe"
if (-not (Test-Path $anvilBin)) { $anvilBin = "anvil" }
if (-not (Test-Path $forgeBin)) { $forgeBin = "forge" }

# 1. Start Anvil
Write-Host "`n[1/3] Starting Anvil local EVM node on port 8545..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& '$anvilBin' --chain-id 31337 --port 8545"
Start-Sleep -Seconds 3

# 2. Deploy Smart Contracts
Write-Host "`n[Deploy] Deploying AgentVault smart contracts..." -ForegroundColor Yellow
$deployRes = & $forgeBin script script/Deploy.s.sol --rpc-url http://127.0.0.1:8545 --broadcast --root "$PSScriptRoot\contracts"
Write-Host "Contracts deployed successfully." -ForegroundColor Green

# 3. Start FastAPI Backend
Write-Host "`n[2/3] Starting FastAPI backend on http://127.0.0.1:8000..." -ForegroundColor Yellow
$backendCmd = "cd '$PSScriptRoot'; .\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --port 8000 --reload"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd
Start-Sleep -Seconds 3

# 4. Start React Frontend
Write-Host "`n[3/3] Starting React Vite frontend on http://localhost:5173..." -ForegroundColor Yellow
$frontendCmd = "cd '$PSScriptRoot\frontend'; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd
Start-Sleep -Seconds 2

Write-Host "`n==========================================" -ForegroundColor Green
Write-Host "   AgentVault is LIVE!" -ForegroundColor Green
Write-Host "   Frontend: http://localhost:5173" -ForegroundColor Cyan
Write-Host "   Backend API: http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Green
