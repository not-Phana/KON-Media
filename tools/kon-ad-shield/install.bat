@echo off
echo ========================================================
echo   KON Ad-Shield for YouTube Embed Player Installation
echo ========================================================
echo.
echo 1. Opening extension folder in Windows File Explorer...
start "" explorer "%~dp0"
echo.
echo 2. Opening Google Chrome extensions page...
start chrome://extensions/
echo.
echo ========================================================
echo HOW TO LOAD (Takes 10 seconds):
echo   a. Turn ON "Developer mode" (toggle in top right).
echo   b. Click "Load unpacked" (top left button).
echo   c. Select this folder:
echo      %~dp0
echo ========================================================
echo.
pause
