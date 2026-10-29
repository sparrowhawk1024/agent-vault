@echo off
setlocal enabledelayedexpansion

echo =======================================================
echo          AGENTVAULT FULL DASHBOARD LAUNCHER
echo =======================================================
echo.

cd /d "%~dp0"

echo [1/4] Starting local Anvil node (Chain ID 31337)...
start "AgentVault - Anvil Node" /min cmd /c "anvil --chain-id 31337 --port 8545"
timeout /t 3 /nobreak >nul

echo [2/4] Deploying PolicyVault & MockUSDC contracts...
cd contracts
forge script script/Deploy.s.sol --rpc-url http://127.0.0.1:8545 --broadcast
cd ..

echo [3/4] Starting FastAPI backend on http://127.0.0.1:8000...
start "AgentVault - FastAPI Backend" cmd /c ".venv\Scripts\python.exe -m uvicorn backend.app.main:app --port 8000 --host 127.0.0.1"
timeout /t 3 /nobreak >nul

echo [4/4] Starting Vite frontend on http://localhost:5173...
start "AgentVault - Vite Frontend" cmd /c "npm --prefix frontend run dev"
timeout /t 3 /nobreak >nul

echo.
echo Opening AgentVault Dashboard in default browser...
start http://localhost:5173

echo =======================================================
echo  AgentVault is running!
echo  - Frontend: http://localhost:5173
echo  - Backend API: http://127.0.0.1:8000/docs
echo  - Blockchain RPC: http://127.0.0.1:8545
echo =======================================================
echo.
pause

