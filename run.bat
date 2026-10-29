@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo =======================================================
echo          AGENTVAULT APPLICATION LAUNCHER
echo =======================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found at .venv\Scripts\python.exe.
    pause
    exit /b 1
)

.venv\Scripts\python.exe scripts\run_app.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] AgentVault encountered an issue (Exit Code: %ERRORLEVEL%).
    pause
)

