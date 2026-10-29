@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python virtual environment not found at .venv\Scripts\python.exe.
    echo Please ensure the virtual environment is set up.
    pause
    exit /b 1
)

.venv\Scripts\python.exe scripts\run_all.py %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] AgentVault master runner encountered an issue (Exit Code: %ERRORLEVEL%).
    pause
)

