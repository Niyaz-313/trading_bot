@echo off
setlocal ENABLEEXTENSIONS
chcp 65001 >nul

cd /d "%~dp0"

echo ================================================================
echo ТЕСТ: свечи (T‑Invest) + метрики стратегии (backtest)
echo ================================================================
echo.

echo [1/3] Preflight (проверка токена/SDK/доступа/1 тикер истории)
python preflight.py --history-period 1y
if errorlevel 1 (
  echo.
  echo ОШИБКА: preflight не пройден. Исправьте проблему и повторите.
  pause
  exit /b 1
)

echo.
echo [2/3] Smoke-test свечей по всем SYMBOLS (live interval + 1d)
python historical_smoke_test.py --daily-period 2y
if errorlevel 1 (
  echo.
  echo ОШИБКА: не удалось получить свечи по части тикеров.
  pause
  exit /b 1
)

echo.
echo [3/3] Backtest (1d) для оценки стратегии
echo Используются переменные окружения из .env: BACKTEST_PERIOD/BACKTEST_STRATEGY
python backtest.py

echo.
echo Готово. Проверьте:
echo - вывод backtest (доходность/кол-во сделок/просадка)
echo - папку reports/ (сделки trades_*.csv)
pause
exit /b 0



