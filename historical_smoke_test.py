"""
Smoke-test для исторических данных:
- проверяет, что свечи по каждому тикеру реально получаются из T‑Invest
- печатает краткую сводку по диапазону дат/кол-ву свечей/дубликатам/пропускам
- (опционально) запускает backtest.py программно для оценки метрик стратегии

Ничего НЕ торгует и НЕ выставляет ордера.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

import pandas as pd

from config import (
    BROKER,
    SYMBOLS,
    TINVEST_SANDBOX,
    TINVEST_TOKEN,
    BAR_INTERVAL,
    HISTORY_LOOKBACK,
)


# Windows-консоли иногда не UTF‑8 → защитимся
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


@dataclass
class CandleCheckResult:
    symbol: str
    ok: bool
    interval: str
    period: str
    rows: int
    dt_from: str
    dt_to: str
    duplicates: int
    gaps: int
    error: str = ""


def _parse_symbols(s: str | None) -> list[str]:
    if not s:
        return list(SYMBOLS)
    return [x.strip().upper() for x in s.split(",") if x.strip()]


def _expected_step(interval: str) -> pd.Timedelta | None:
    i = (interval or "").strip().lower()
    if i.endswith("m"):
        try:
            mins = int(i[:-1])
            return pd.Timedelta(minutes=mins)
        except Exception:
            return None
    if i.endswith("h"):
        try:
            hours = int(i[:-1])
            return pd.Timedelta(hours=hours)
        except Exception:
            return None
    if i.endswith("d"):
        try:
            days = int(i[:-1])
            return pd.Timedelta(days=days)
        except Exception:
            return None
    if i == "1d":
        return pd.Timedelta(days=1)
    return None


def _count_gaps(idx: pd.DatetimeIndex, expected: pd.Timedelta | None) -> int:
    if expected is None:
        return 0
    if len(idx) < 3:
        return 0
    diffs = idx.to_series().diff().dropna()
    # “gap” = шаг больше чем 2x ожидаемого (на дневках будут выходные/праздники → там лучше не считать)
    if expected >= pd.Timedelta(days=1):
        return 0
    return int((diffs > expected * 2).sum())


def check_candles(
    api,
    symbol: str,
    *,
    period: str,
    interval: str,
) -> CandleCheckResult:
    try:
        df = api.get_historical_data(symbol, period=period, interval=interval)
        if df is None or df.empty:
            return CandleCheckResult(
                symbol=symbol,
                ok=False,
                interval=interval,
                period=period,
                rows=0,
                dt_from="",
                dt_to="",
                duplicates=0,
                gaps=0,
                error="empty",
            )

        if not isinstance(df.index, pd.DatetimeIndex):
            return CandleCheckResult(
                symbol=symbol,
                ok=False,
                interval=interval,
                period=period,
                rows=int(len(df)),
                dt_from="",
                dt_to="",
                duplicates=0,
                gaps=0,
                error="index_is_not_datetime",
            )

        # Базовые sanity-checks
        idx = df.index.sort_values()
        dup = int(idx.duplicated().sum())
        step = _expected_step(interval)
        gaps = _count_gaps(idx, step)

        dt_from = str(idx.min().to_pydatetime())
        dt_to = str(idx.max().to_pydatetime())

        return CandleCheckResult(
            symbol=symbol,
            ok=True,
            interval=interval,
            period=period,
            rows=int(len(df)),
            dt_from=dt_from,
            dt_to=dt_to,
            duplicates=dup,
            gaps=gaps,
        )
    except Exception as e:
        return CandleCheckResult(
            symbol=symbol,
            ok=False,
            interval=interval,
            period=period,
            rows=0,
            dt_from="",
            dt_to="",
            duplicates=0,
            gaps=0,
            error=str(e),
        )


def _print_table(rows: Iterable[CandleCheckResult]) -> None:
    rows = list(rows)
    ok_n = sum(1 for r in rows if r.ok)
    print("")
    print(f"Symbols OK: {ok_n} / {len(rows)}")
    print("")
    print("SYMBOL  OK  ROWS   FROM                       TO                         dup  gaps  err")
    print("-" * 110)
    for r in rows:
        err = (r.error or "")[:40]
        print(
            f"{r.symbol:6s}  "
            f"{('Y' if r.ok else 'N'):>2s}  "
            f"{r.rows:5d}  "
            f"{r.dt_from:24s}  "
            f"{r.dt_to:24s}  "
            f"{r.duplicates:3d}  "
            f"{r.gaps:4d}  "
            f"{err}"
        )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", default="", help="Comma-separated tickers (default: from .env/config)")
    p.add_argument("--period", default=str(HISTORY_LOOKBACK), help="Period for interval check (e.g. 5d/10d/1mo)")
    p.add_argument("--interval", default=str(BAR_INTERVAL), help="Candle interval (e.g. 5m/15m/1h/1d)")
    p.add_argument(
        "--daily-period",
        default=str(__import__("os").environ.get("BACKTEST_PERIOD", "2y")),
        help="Period for 1d history check (e.g. 1y/2y/all)",
    )
    p.add_argument("--run-backtest", action="store_true", help="Also run backtest after candle checks")
    p.add_argument(
        "--backtest-strategy",
        default=str(__import__("os").environ.get("BACKTEST_STRATEGY", "best")),
        help="hybrid/trend/mean/ensemble/all/best",
    )
    args = p.parse_args()

    print("=" * 80)
    print("HISTORICAL SMOKE TEST")
    print("=" * 80)
    print(f"UTC now: {datetime.now(timezone.utc).isoformat().replace('+00:00','Z')}")
    print(f"BROKER={BROKER}  sandbox={TINVEST_SANDBOX}")
    print(f"interval-check: interval={args.interval} period={args.period}")
    print(f"daily-check:    interval=1d period={args.daily_period}")

    if BROKER != "tinvest":
        print("✗ BROKER != tinvest. Этот тест рассчитан на T‑Invest.")
        return 2

    token_str = str(TINVEST_TOKEN or "").strip().lower()
    if not token_str or "your_" in token_str or "example" in token_str:
        print("✗ TINVEST_TOKEN не задан или содержит примерное значение.")
        return 2

    try:
        from tinvest_api import TInvestAPI
    except Exception as e:
        print(f"✗ Не удалось импортировать TInvestAPI: {e}")
        return 2

    api = TInvestAPI(sandbox=bool(TINVEST_SANDBOX))
    if not getattr(api, "client", None):
        print("✗ TInvestAPI не настроен (client=None). Проверьте SDK/токен.")
        return 2

    symbols = _parse_symbols(args.symbols)
    print(f"Symbols: {', '.join(symbols)}")

    # 1) Проверка свечей на live-интервале (BAR_INTERVAL)
    results_intraday: list[CandleCheckResult] = []
    for sym in symbols:
        results_intraday.append(check_candles(api, sym, period=str(args.period), interval=str(args.interval)))
    print("")
    print("### Candle check (live interval)")
    _print_table(results_intraday)

    # 2) Проверка дневных свечей (для backtest/метрик)
    results_daily: list[CandleCheckResult] = []
    for sym in symbols:
        results_daily.append(check_candles(api, sym, period=str(args.daily_period), interval="1d"))
    print("")
    print("### Candle check (1d)")
    _print_table(results_daily)

    if args.run_backtest:
        print("")
        print("=" * 80)
        print("BACKTEST (via backtest.py)")
        print("=" * 80)
        try:
            # backtest.py читает параметры из env (BACKTEST_PERIOD/BACKTEST_STRATEGY),
            # но мы можем временно подменить их через env vars для текущего процесса.
            import os

            os.environ["BACKTEST_PERIOD"] = str(args.daily_period)
            os.environ["BACKTEST_STRATEGY"] = str(args.backtest_strategy)

            from backtest import run_backtest

            run_backtest()
            return 0
        except Exception as e:
            print(f"✗ backtest failed: {e}")
            return 2

    print("")
    print("✓ Smoke-test complete (no backtest run).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


