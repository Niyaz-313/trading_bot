@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo Диагностика sandbox-аккаунтов T-Invest
echo ============================================
python list_sandbox_accounts.py
echo.
pause








