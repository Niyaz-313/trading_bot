@echo off
setlocal enabledelayedexpansion

REM Keep this file ASCII-only. Cyrillic/UTF-8 text in .bat can be mis-parsed by cmd.exe.

cd /d "%~dp0" 2>nul
if errorlevel 1 (
  echo ERROR: cannot cd to script directory
  echo PATH: %~dp0
  pause
  exit /b 1
)

echo ========================================
echo GIT SYNC (local -> origin/main)
echo ========================================
echo CWD: %CD%
echo.

where git >nul 2>&1
if errorlevel 1 (
  echo ERROR: git not found in PATH
  echo Install Git: https://git-scm.com/download/win
  pause
  exit /b 1
)

if not exist ".git" (
  echo ERROR: .git folder not found. This is not a git repo.
  echo CWD: %CD%
  pause
  exit /b 1
)

echo [1/5] git status
git status --short
if errorlevel 1 goto :fail
echo.

echo [2/5] git add -A
git add -A
if errorlevel 1 goto :fail
echo.

echo [3/5] git commit (if needed)
set "COMMIT_MSG=Auto-sync: %date% %time%"
git commit -m "%COMMIT_MSG%"
echo.

echo [4/5] git pull (avoid non-fast-forward)
git pull origin main --no-edit
if errorlevel 1 goto :fail
echo.

echo [5/5] git push
git push origin main
if errorlevel 1 goto :fail

echo.
echo ========================================
echo DONE
echo ========================================
echo Next on server:
echo   cd /home/botuser/trading_bot/trading_bot
echo   ./server_update.sh
echo.
pause
exit /b 0

:fail
echo.
echo ========================================
echo FAILED (errorlevel=%errorlevel%)
echo ========================================
pause
exit /b 1
