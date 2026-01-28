@echo off
chcp 65001 >nul
echo ========================================
echo Тестирование стратегии на исторических данных
echo ========================================
echo.

cd /d "%~dp0"

python backtest.py

echo.
pause







