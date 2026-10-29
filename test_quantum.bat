@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe scripts\test_qpiai_quantum_connectivity.py
pause

