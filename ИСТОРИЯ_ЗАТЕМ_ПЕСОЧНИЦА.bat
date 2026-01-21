@echo off
setlocal ENABLEEXTENSIONS
chcp 65001 >nul

cd /d "%~dp0"

echo ================================================================
echo ПРОГОН: preset -> verify тикеров -> smoke-test свечей -> backtest -> запуск в песочнице
echo ================================================================
echo.

echo [0/4] Применяем preset в .env (с бэкапом, НЕ затирая токены/секреты)
python apply_env_preset.py --preset env_presets\AGGRESSIVE_QUALITY.env --env .env
if errorlevel 1 (
  echo.
  echo ОШИБКА: не удалось применить preset в .env
  pause
  exit /b 1
)

echo.
echo [1/4] Verify: тикеры резолвятся в инструменты (share/etf/currency/bond)
python verify_symbols.py
if errorlevel 1 (
  echo.
  echo ПРЕДУПРЕЖДЕНИЕ: часть тикеров не найдена. Смотрите вывод выше.
  echo Можно продолжить, но эти тикеры будут давать пустые свечи/пропуски.
)

echo.
echo [2/4] Preflight (проверка токена/SDK/доступа/1 тикер истории)
python preflight.py --history-period 1y
if errorlevel 1 (
  echo.
  echo ОШИБКА: preflight не пройден. Исправьте проблему и повторите.
  pause
  exit /b 1
)

echo.
echo [3/4] Smoke-test свечей по всем SYMBOLS (live interval + 1d)
python historical_smoke_test.py --daily-period 2y
if errorlevel 1 (
  echo.
  echo ОШИБКА: не удалось получить свечи по части тикеров.
  pause
  exit /b 1
)

echo.
echo [4/4] Backtest (1d) для оценки стратегии
echo Используются переменные окружения из .env: BACKTEST_PERIOD/BACKTEST_STRATEGY
python backtest.py

echo.
echo ================================================================
echo ГОТОВО: запускаем бота (песочница)
echo ================================================================
echo.
echo Для остановки: Ctrl+C
echo.
python main.py


