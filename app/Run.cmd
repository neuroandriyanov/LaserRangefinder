@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run first: powershell -ExecutionPolicy Bypass -File install.ps1
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m desktop_app %*
if errorlevel 1 pause
