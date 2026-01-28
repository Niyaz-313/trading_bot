@echo off
setlocal ENABLEEXTENSIONS

cd /d "%~dp0"
if errorlevel 1 (
  echo ERROR: cannot cd to script directory
  pause
  exit /b 1
)

echo ================================================================
echo TEST: Historical data (T-Invest) + Strategy metrics (backtest)
echo ================================================================
echo.

echo [1/3] Preflight check (token/SDK/access/1 ticker history)
if exist preflight.py (
  python preflight.py --history-period 1y
  if errorlevel 1 (
    echo.
    echo ERROR: preflight failed. Fix the issue and retry.
    pause
    exit /b 1
  )
) else (
  echo WARNING: preflight.py not found, skipping...
)

echo.
echo [2/3] Smoke-test candles for all SYMBOLS (live interval + 1d)
if exist historical_smoke_test.py (
  python historical_smoke_test.py --daily-period 2y
  if errorlevel 1 (
    echo.
    echo ERROR: failed to get candles for some tickers.
    pause
    exit /b 1
  )
) else (
  echo WARNING: historical_smoke_test.py not found, skipping...
)

echo.
echo [3/3] Backtest (1d) for strategy evaluation
echo Using environment variables from .env: BACKTEST_PERIOD/BACKTEST_STRATEGY
if exist backtest.py (
  python backtest.py
  if errorlevel 1 (
    echo.
    echo ERROR: backtest failed.
    pause
    exit /b 1
  )
) else (
  echo ERROR: backtest.py not found!
  pause
  exit /b 1
)

echo.
echo Done. Check:
echo - backtest output (returns/trades/drawdown)
echo - reports/ folder (trades trades_*.csv)
pause
exit /b 0
