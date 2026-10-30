@echo off
setlocal
title KON Media - Personal Desktop Media Workspace

echo ====================================================
echo             KON MEDIA - STARTING WORKSPACE
echo ====================================================
echo.

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found at .venv\Scripts\python.exe
    echo Please run setup first.
    pause
    exit /b 1
)

echo [INFO] Starting KON Media local backend service on 127.0.0.1:8899...
echo [INFO] Media files will save to: %CD%\downloads\
echo [INFO] Press Ctrl+C in this window to stop the application.
echo.

if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" (
    start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --app="http://127.0.0.1:8899" --window-size=1240,840
) else (
    start "" "http://127.0.0.1:8899"
)
".venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8899

pause
