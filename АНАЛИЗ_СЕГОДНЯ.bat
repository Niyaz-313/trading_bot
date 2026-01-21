@echo off
chcp 65001 >nul
echo Запуск анализа решений бота за сегодня...
python analyze_today_full.py > analysis_output.txt 2>&1
type analysis_output.txt
pause

