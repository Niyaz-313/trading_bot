@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

python analyze_reports.py

echo.
echo Готово. Сводка сохранена в:
echo   reports\summary_by_symbol_strategy.csv
echo   reports\summary_by_symbol_best.csv
pause






