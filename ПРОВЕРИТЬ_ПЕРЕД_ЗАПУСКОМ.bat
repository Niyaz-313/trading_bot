@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

echo ==============================================================
echo PREFLIGHT: проверка перед запуском main.py
echo ==============================================================
echo.

python preflight.py --history-period 1y

echo.
echo (Опционально) Проверка Telegram:
echo   python preflight.py --history-period 1y --telegram
echo.
pause






