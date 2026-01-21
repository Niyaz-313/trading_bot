"""
Поиск инструментов по подстроке тикера/названия через T‑Invest (official SDK).

Зачем: валюта/драгметаллы/ETF могут иметь тикеры, отличающиеся от "ожидаемых".
Скрипт помогает быстро найти реальные tickers/FIGI.

Примеры:
  python search_instruments.py --type currency --query EUR
  python search_instruments.py --type currency --query RUB
  python search_instruments.py --type etf --query GOLD
  python search_instruments.py --type etf --query GLD
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from config import BROKER, TINVEST_SANDBOX, TINVEST_TOKEN


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", default="all", choices=["all", "share", "etf", "currency", "bond"], help="Instrument type to search")
    ap.add_argument("--query", required=True, help="Substring to search in ticker/name (case-insensitive)")
    ap.add_argument("--limit", type=int, default=50, help="Max results to print")
    args = ap.parse_args()

    # Windows-консоли иногда не UTF‑8 → защитимся
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if BROKER != "tinvest":
        raise SystemExit("BROKER must be tinvest for this script")
    if not TINVEST_TOKEN:
        raise SystemExit("TINVEST_TOKEN is empty")

    try:
        from tinvest_api import TInvestAPI  # type: ignore
    except Exception as e:
        raise SystemExit(f"Cannot import TInvestAPI: {e}")

    api = TInvestAPI(sandbox=bool(TINVEST_SANDBOX))
    if not getattr(api, "client", None):
        raise SystemExit("TInvestAPI not initialized (client=None)")

    if getattr(api, "TINVEST_SDK_TYPE", "official") != "official":
        # В tinvest_api.py это глобальная константа, но проверим безопасно
        pass

    q = str(args.query).strip().upper()
    if not q:
        raise SystemExit("query is empty")

    # Подключимся напрямую к official client через внутренний helper
    if not hasattr(api, "_create_official_client"):
        raise SystemExit("TInvestAPI has no _create_official_client()")

    def match(it) -> bool:
        t = str(getattr(it, "ticker", "") or "").upper()
        n = str(getattr(it, "name", "") or "").upper()
        return (q in t) or (q in n)

    def pack(it, typ: str) -> str:
        ticker = str(getattr(it, "ticker", "") or "")
        name = str(getattr(it, "name", "") or "")
        figi = str(getattr(it, "figi", "") or "")
        lot = getattr(it, "lot", None)
        try:
            lot_i = int(lot) if lot is not None else 1
        except Exception:
            lot_i = 1
        cur = str(getattr(it, "currency", "") or "")
        st = getattr(it, "trading_status", None)
        st_s = str(st) if st is not None else ""
        return f"{ticker:14}  {typ:8}  lot={lot_i:<4}  cur={cur:4}  status={st_s:12}  figi={figi}  name={name}"

    printed = 0
    print("=" * 110)
    print("SEARCH INSTRUMENTS (T-Invest)")
    print("=" * 110)
    print(f"utc: {datetime.now(timezone.utc).isoformat().replace('+00:00','Z')}")
    print(f"sandbox: {TINVEST_SANDBOX}")
    print(f"type: {args.type}  query: {args.query}")
    print("-" * 110)

    try:
        with api._create_official_client() as client:  # type: ignore
            targets = []
            if args.type in ("all", "share"):
                targets.append(("share", lambda: client.instruments.shares()))
            if args.type in ("all", "etf"):
                targets.append(("etf", lambda: client.instruments.etfs()))
            if args.type in ("all", "currency"):
                targets.append(("currency", lambda: client.instruments.currencies()))
            if args.type in ("all", "bond"):
                targets.append(("bond", lambda: client.instruments.bonds()))

            for typ, fn in targets:
                try:
                    resp = fn()
                except Exception:
                    continue
                for it in getattr(resp, "instruments", []) or []:
                    if not match(it):
                        continue
                    print(pack(it, typ))
                    printed += 1
                    if printed >= int(args.limit):
                        print("-" * 110)
                        print(f"limit reached: {printed}")
                        return 0
    except Exception as e:
        raise SystemExit(f"search failed: {e}")

    print("-" * 110)
    print(f"found: {printed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


