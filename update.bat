@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ========================================================
echo   KON Media / KON Search -- Auto-Update
echo ========================================================
echo.
echo [1/3] Pulling latest commits from GitHub origin/main...
git pull origin main
if %ERRORLEVEL% neq 0 (
    echo.
    echo [Notice] Stashing local modifications and retrying pull...
    git stash
    git pull origin main
    git stash pop
)

echo.
echo [2/3] Building latest frontend bundle...
cd frontend
call npm run build
cd ..

echo.
echo [3/3] Successfully updated!
echo ========================================================
git log -1 --pretty=format:"Latest commit: %%h - %%s (%%cd)" --date=relative
echo.
echo ========================================================
echo.
pause
