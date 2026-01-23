@echo off
chcp 65001 >nul
echo ========================================
echo Committing report changes
echo ========================================

cd /d "%~dp0"

echo [1/4] git status
git status

echo.
echo [2/4] git add
git add main.py
git add ИЗМЕНЕНИЯ_ОТЧЕТ_TELEGRAM.md
git add test_day_report.py

echo.
echo [3/4] git commit
git commit -m "Add symbol details to Telegram day report

- Added detailed breakdown by symbol in get_day_report_text
- Shows buy/sell operations with times and prices
- Calculates realized P/L per symbol
- Uses average-cost method for P/L calculation"

echo.
echo [4/4] git pull (avoid conflicts)
git pull origin main

echo.
echo [5/5] git push
git push origin main

echo.
echo ========================================
echo DONE
echo ========================================
echo Next on server: cd /home/botuser/trading_bot/trading_bot && ./server_update.sh
pause

