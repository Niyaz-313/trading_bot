"""
Проверка тикеров SYMBOLS через T‑Invest:
- резолвится ли тикер в инструмент (share/etf/currency/bond)
- какой lot/trading_status/флаги доступности
- (опционально) получаются ли свечи за небольшой период

Пример:
  python verify_symbols.py
  python verify_symbols.py --symbols "SBER,GLDRUB_TOM,USD000UTSTOM" --check-candles --interval 15m --period 10d
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import sys

from broker_api import BrokerAPI
from config import BROKER, SYMBOLS, TINVEST_SANDBOX


DEFAULT_EXTRA = [
    # Нефть/энерго (доп.)
    "BANE",
    "BANEP",
    "RNFT",
    "TATNP",
    # Драгметаллы/металлы (доп.)
    "SELG",
    "UGLD",
    "LNZL",
    # Валюта/драгметаллы как currency-инструменты (реально доступны в sandbox по instruments.currencies())
    "USD000UTSTOM",
    "CNYRUB_TOM",
    "GLDRUB_TOM",
    "SLVRUB_TOM",
    "PLTRUB_TOM",
    "PLDRUB_TOM",
]


def _parse_symbols(s: str | None) -> list[str]:
    if not s:
        base = list(SYMBOLS)
        # добавим extra, чтобы проверить новые категории
        out = []
        seen = set()
        for x in (base + DEFAULT_EXTRA):
            u = str(x).strip().upper()
            if u and u not in seen:
                out.append(u)
                seen.add(u)
        return out
    return [x.strip().upper() for x in s.split(",") if x.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="", help="Comma-separated tickers (default: SYMBOLS + extras)")
    ap.add_argument("--check-candles", action="store_true", help="Also fetch candles for each symbol")
    ap.add_argument("--interval", default="15m", help="Candle interval for check (e.g. 5m/15m/1h/1d)")
    ap.add_argument("--period", default="10d", help="Period for candle check (e.g. 5d/10d/1mo/1y)")
    args = ap.parse_args()

    symbols = _parse_symbols(args.symbols)
    api = BrokerAPI(paper_trading=(TINVEST_SANDBOX if BROKER == "tinvest" else True))

    # Windows-консоли иногда не UTF‑8 → защитимся
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=" * 90)
    print("VERIFY SYMBOLS (T-Invest)")
    print("=" * 90)
    print(f"now: {datetime.now(timezone.utc).isoformat().replace('+00:00','Z')}")
    print(f"BROKER={BROKER} sandbox={TINVEST_SANDBOX}")
    print(f"symbols: {', '.join(symbols)}")
    print()

    ok = 0
    bad = 0

    header = ["SYMBOL", "FOUND", "TYPE", "LOT", "TRADING_STATUS", "API_OK", "BUY_OK", "SELL_OK"]
    if args.check_candles:
        header += ["CANDLES", "FROM", "TO"]
    print("  ".join(h.ljust(14) for h in header))
    print("-" * 90)

    for sym in symbols:
        ins = api.get_instrument_details(sym)
        if not ins:
            bad += 1
            row = [sym, "N", "", "", "", "", "", ""]
            if args.check_candles:
                row += ["", "", ""]
            print("  ".join(str(x).ljust(14) for x in row))
            continue

        ok += 1
        row = [
            sym,
            "Y",
            str(ins.get("instrument_type") or ""),
            str(ins.get("lot") or ""),
            str(ins.get("trading_status") or ""),
            str(ins.get("api_trade_available_flag")),
            str(ins.get("buy_available_flag")),
            str(ins.get("sell_available_flag")),
        ]

        if args.check_candles:
            try:
                df = api.get_historical_data(sym, period=str(args.period), interval=str(args.interval))
            except Exception:
                df = None
            if df is None or getattr(df, "empty", True):
                row += ["0", "", ""]
            else:
                try:
                    dt_from = str(df.index.min())
                    dt_to = str(df.index.max())
                    rows = int(len(df))
                except Exception:
                    dt_from, dt_to, rows = "", "", 0
                row += [str(rows), dt_from, dt_to]

        print("  ".join(str(x).ljust(14) for x in row))

    print("-" * 90)
    print(f"FOUND: {ok} / {len(symbols)}   NOT FOUND: {bad}")
    return 0 if bad == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())


