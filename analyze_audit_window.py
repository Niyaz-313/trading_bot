import argparse
import csv
import datetime as dt
import json
import sys
from collections import defaultdict


def parse_ts_utc(s: str) -> dt.datetime | None:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    except Exception:
        return None


def parse_float(x):
    if x in (None, ""):
        return None
    try:
        return float(x)
    except Exception:
        return None


def main():
    # Windows-консоли иногда не UTF‑8 → защитимся
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    p = argparse.ArgumentParser(description="Analyze audit_logs/trades_audit.csv for a UTC window")
    p.add_argument("--csv", default="audit_logs/trades_audit.csv")
    p.add_argument("--start", required=True, help="UTC ISO timestamp, e.g. 2026-01-08T12:49:23Z")
    p.add_argument("--end", default="", help="UTC ISO timestamp, default=now")
    args = p.parse_args()

    start_utc = parse_ts_utc(args.start)
    if not start_utc:
        raise SystemExit(f"Bad --start: {args.start}")
    end_utc = parse_ts_utc(args.end) if args.end else dt.datetime.now(dt.timezone.utc)

    counts = defaultdict(int)
    counts_by_reason = defaultdict(int)
    pnl_by_reason = defaultdict(float)
    pnl_by_symbol = defaultdict(float)
    sells_by_symbol = defaultdict(int)
    wins_by_symbol = defaultdict(int)
    losses_by_symbol = defaultdict(int)

    equity_series: list[tuple[dt.datetime, float]] = []
    first_equity = None
    last_equity = None

    in_window_rows = 0
    trades_in_window = 0
    realized_pnl_found = 0

    with open(args.csv, encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            ts = parse_ts_utc(row.get("ts_utc") or "")
            if not ts:
                continue
            if ts < start_utc or ts > end_utc:
                continue

            in_window_rows += 1
            ev = (row.get("event") or "").strip()
            counts[ev] += 1

            eq = parse_float(row.get("equity"))
            if eq is not None and eq > 0:
                equity_series.append((ts, eq))
                if first_equity is None:
                    first_equity = eq
                last_equity = eq

            if ev != "trade":
                continue

            trades_in_window += 1
            sym = (row.get("symbol") or "").strip()
            reason = (row.get("reason") or "").strip() or "unknown"
            action = (row.get("action") or "").strip().upper()
            counts_by_reason[reason] += 1

            details_raw = row.get("details") or ""
            pnl = None
            if details_raw:
                try:
                    d = json.loads(details_raw)
                    pnl = d.get("pnl")
                except Exception:
                    pnl = None
            pnl = parse_float(pnl)

            # We treat realized pnl as meaningful primarily on SELL events
            if pnl is not None:
                realized_pnl_found += 1
                pnl_by_reason[reason] += pnl
                pnl_by_symbol[sym] += pnl
                if action == "SELL":
                    sells_by_symbol[sym] += 1
                    if pnl > 0:
                        wins_by_symbol[sym] += 1
                    elif pnl < 0:
                        losses_by_symbol[sym] += 1

    # Compute drawdown from equity series
    equity_series.sort(key=lambda x: x[0])
    max_dd = None
    if equity_series:
        peak = equity_series[0][1]
        trough = 0.0
        for _, eq in equity_series:
            if eq > peak:
                peak = eq
            dd = (eq - peak) / peak if peak else 0.0
            if dd < trough:
                trough = dd
        max_dd = trough * 100.0

    print(f"Window UTC: {start_utc.isoformat().replace('+00:00','Z')} -> {end_utc.isoformat().replace('+00:00','Z')}")
    print(f"Rows in window: {in_window_rows}")
    print("Events:", dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))))

    if first_equity is not None and last_equity is not None:
        print(f"Equity: {first_equity:.2f} → {last_equity:.2f}  Δ={last_equity-first_equity:+.2f}")
    else:
        print("Equity: (no equity samples in window)")

    if max_dd is not None:
        print(f"Max drawdown (from equity samples): {max_dd:.3f}%")

    print(f"Trades in window: {trades_in_window} (realized pnl found in details: {realized_pnl_found})")

    net_realized = sum(pnl_by_reason.values())
    print(f"Net realized P/L (sum(details.pnl)): {net_realized:+.2f}")

    if counts_by_reason:
        print("\nBy reason (count / pnl):")
        for reason in sorted(counts_by_reason.keys(), key=lambda r: (-counts_by_reason[r], r)):
            print(f"  {reason:12s}  {counts_by_reason[reason]:4d}  pnl={pnl_by_reason.get(reason,0.0):+.2f}")

    if pnl_by_symbol:
        print("\nTop symbols by realized P/L:")
        for sym, val in sorted(pnl_by_symbol.items(), key=lambda kv: kv[1], reverse=True)[:10]:
            print(f"  {sym:6s} pnl={val:+.2f}  sells={sells_by_symbol.get(sym,0)} win={wins_by_symbol.get(sym,0)} loss={losses_by_symbol.get(sym,0)}")

        print("\nWorst symbols by realized P/L:")
        for sym, val in sorted(pnl_by_symbol.items(), key=lambda kv: kv[1])[:10]:
            print(f"  {sym:6s} pnl={val:+.2f}  sells={sells_by_symbol.get(sym,0)} win={wins_by_symbol.get(sym,0)} loss={losses_by_symbol.get(sym,0)}")


if __name__ == "__main__":
    main()




import datetime as dt
import json
import sys
from collections import defaultdict


def parse_ts_utc(s: str) -> dt.datetime | None:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    except Exception:
        return None


def parse_float(x):
    if x in (None, ""):
        return None
    try:
        return float(x)
    except Exception:
        return None


def main():
    # Windows-консоли иногда не UTF‑8 → защитимся
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    p = argparse.ArgumentParser(description="Analyze audit_logs/trades_audit.csv for a UTC window")
    p.add_argument("--csv", default="audit_logs/trades_audit.csv")
    p.add_argument("--start", required=True, help="UTC ISO timestamp, e.g. 2026-01-08T12:49:23Z")
    p.add_argument("--end", default="", help="UTC ISO timestamp, default=now")
    args = p.parse_args()

    start_utc = parse_ts_utc(args.start)
    if not start_utc:
        raise SystemExit(f"Bad --start: {args.start}")
    end_utc = parse_ts_utc(args.end) if args.end else dt.datetime.now(dt.timezone.utc)

    counts = defaultdict(int)
    counts_by_reason = defaultdict(int)
    pnl_by_reason = defaultdict(float)
    pnl_by_symbol = defaultdict(float)
    sells_by_symbol = defaultdict(int)
    wins_by_symbol = defaultdict(int)
    losses_by_symbol = defaultdict(int)

    equity_series: list[tuple[dt.datetime, float]] = []
    first_equity = None
    last_equity = None

    in_window_rows = 0
    trades_in_window = 0
    realized_pnl_found = 0

    with open(args.csv, encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            ts = parse_ts_utc(row.get("ts_utc") or "")
            if not ts:
                continue
            if ts < start_utc or ts > end_utc:
                continue

            in_window_rows += 1
            ev = (row.get("event") or "").strip()
            counts[ev] += 1

            eq = parse_float(row.get("equity"))
            if eq is not None and eq > 0:
                equity_series.append((ts, eq))
                if first_equity is None:
                    first_equity = eq
                last_equity = eq

            if ev != "trade":
                continue

            trades_in_window += 1
            sym = (row.get("symbol") or "").strip()
            reason = (row.get("reason") or "").strip() or "unknown"
            action = (row.get("action") or "").strip().upper()
            counts_by_reason[reason] += 1

            details_raw = row.get("details") or ""
            pnl = None
            if details_raw:
                try:
                    d = json.loads(details_raw)
                    pnl = d.get("pnl")
                except Exception:
                    pnl = None
            pnl = parse_float(pnl)

            # We treat realized pnl as meaningful primarily on SELL events
            if pnl is not None:
                realized_pnl_found += 1
                pnl_by_reason[reason] += pnl
                pnl_by_symbol[sym] += pnl
                if action == "SELL":
                    sells_by_symbol[sym] += 1
                    if pnl > 0:
                        wins_by_symbol[sym] += 1
                    elif pnl < 0:
                        losses_by_symbol[sym] += 1

    # Compute drawdown from equity series
    equity_series.sort(key=lambda x: x[0])
    max_dd = None
    if equity_series:
        peak = equity_series[0][1]
        trough = 0.0
        for _, eq in equity_series:
            if eq > peak:
                peak = eq
            dd = (eq - peak) / peak if peak else 0.0
            if dd < trough:
                trough = dd
        max_dd = trough * 100.0

    print(f"Window UTC: {start_utc.isoformat().replace('+00:00','Z')} -> {end_utc.isoformat().replace('+00:00','Z')}")
    print(f"Rows in window: {in_window_rows}")
    print("Events:", dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))))

    if first_equity is not None and last_equity is not None:
        print(f"Equity: {first_equity:.2f} → {last_equity:.2f}  Δ={last_equity-first_equity:+.2f}")
    else:
        print("Equity: (no equity samples in window)")

    if max_dd is not None:
        print(f"Max drawdown (from equity samples): {max_dd:.3f}%")

    print(f"Trades in window: {trades_in_window} (realized pnl found in details: {realized_pnl_found})")

    net_realized = sum(pnl_by_reason.values())
    print(f"Net realized P/L (sum(details.pnl)): {net_realized:+.2f}")

    if counts_by_reason:
        print("\nBy reason (count / pnl):")
        for reason in sorted(counts_by_reason.keys(), key=lambda r: (-counts_by_reason[r], r)):
            print(f"  {reason:12s}  {counts_by_reason[reason]:4d}  pnl={pnl_by_reason.get(reason,0.0):+.2f}")

    if pnl_by_symbol:
        print("\nTop symbols by realized P/L:")
        for sym, val in sorted(pnl_by_symbol.items(), key=lambda kv: kv[1], reverse=True)[:10]:
            print(f"  {sym:6s} pnl={val:+.2f}  sells={sells_by_symbol.get(sym,0)} win={wins_by_symbol.get(sym,0)} loss={losses_by_symbol.get(sym,0)}")

        print("\nWorst symbols by realized P/L:")
        for sym, val in sorted(pnl_by_symbol.items(), key=lambda kv: kv[1])[:10]:
            print(f"  {sym:6s} pnl={val:+.2f}  sells={sells_by_symbol.get(sym,0)} win={wins_by_symbol.get(sym,0)} loss={losses_by_symbol.get(sym,0)}")


if __name__ == "__main__":
    main()




import datetime as dt
import json
import sys
from collections import defaultdict


def parse_ts_utc(s: str) -> dt.datetime | None:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    except Exception:
        return None


def parse_float(x):
    if x in (None, ""):
        return None
    try:
        return float(x)
    except Exception:
        return None


def main():
    # Windows-консоли иногда не UTF‑8 → защитимся
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    p = argparse.ArgumentParser(description="Analyze audit_logs/trades_audit.csv for a UTC window")
    p.add_argument("--csv", default="audit_logs/trades_audit.csv")
    p.add_argument("--start", required=True, help="UTC ISO timestamp, e.g. 2026-01-08T12:49:23Z")
    p.add_argument("--end", default="", help="UTC ISO timestamp, default=now")
    args = p.parse_args()

    start_utc = parse_ts_utc(args.start)
    if not start_utc:
        raise SystemExit(f"Bad --start: {args.start}")
    end_utc = parse_ts_utc(args.end) if args.end else dt.datetime.now(dt.timezone.utc)

    counts = defaultdict(int)
    counts_by_reason = defaultdict(int)
    pnl_by_reason = defaultdict(float)
    pnl_by_symbol = defaultdict(float)
    sells_by_symbol = defaultdict(int)
    wins_by_symbol = defaultdict(int)
    losses_by_symbol = defaultdict(int)

    equity_series: list[tuple[dt.datetime, float]] = []
    first_equity = None
    last_equity = None

    in_window_rows = 0
    trades_in_window = 0
    realized_pnl_found = 0

    with open(args.csv, encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            ts = parse_ts_utc(row.get("ts_utc") or "")
            if not ts:
                continue
            if ts < start_utc or ts > end_utc:
                continue

            in_window_rows += 1
            ev = (row.get("event") or "").strip()
            counts[ev] += 1

            eq = parse_float(row.get("equity"))
            if eq is not None and eq > 0:
                equity_series.append((ts, eq))
                if first_equity is None:
                    first_equity = eq
                last_equity = eq

            if ev != "trade":
                continue

            trades_in_window += 1
            sym = (row.get("symbol") or "").strip()
            reason = (row.get("reason") or "").strip() or "unknown"
            action = (row.get("action") or "").strip().upper()
            counts_by_reason[reason] += 1

            details_raw = row.get("details") or ""
            pnl = None
            if details_raw:
                try:
                    d = json.loads(details_raw)
                    pnl = d.get("pnl")
                except Exception:
                    pnl = None
            pnl = parse_float(pnl)

            # We treat realized pnl as meaningful primarily on SELL events
            if pnl is not None:
                realized_pnl_found += 1
                pnl_by_reason[reason] += pnl
                pnl_by_symbol[sym] += pnl
                if action == "SELL":
                    sells_by_symbol[sym] += 1
                    if pnl > 0:
                        wins_by_symbol[sym] += 1
                    elif pnl < 0:
                        losses_by_symbol[sym] += 1

    # Compute drawdown from equity series
    equity_series.sort(key=lambda x: x[0])
    max_dd = None
    if equity_series:
        peak = equity_series[0][1]
        trough = 0.0
        for _, eq in equity_series:
            if eq > peak:
                peak = eq
            dd = (eq - peak) / peak if peak else 0.0
            if dd < trough:
                trough = dd
        max_dd = trough * 100.0

    print(f"Window UTC: {start_utc.isoformat().replace('+00:00','Z')} -> {end_utc.isoformat().replace('+00:00','Z')}")
    print(f"Rows in window: {in_window_rows}")
    print("Events:", dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))))

    if first_equity is not None and last_equity is not None:
        print(f"Equity: {first_equity:.2f} → {last_equity:.2f}  Δ={last_equity-first_equity:+.2f}")
    else:
        print("Equity: (no equity samples in window)")

    if max_dd is not None:
        print(f"Max drawdown (from equity samples): {max_dd:.3f}%")

    print(f"Trades in window: {trades_in_window} (realized pnl found in details: {realized_pnl_found})")

    net_realized = sum(pnl_by_reason.values())
    print(f"Net realized P/L (sum(details.pnl)): {net_realized:+.2f}")

    if counts_by_reason:
        print("\nBy reason (count / pnl):")
        for reason in sorted(counts_by_reason.keys(), key=lambda r: (-counts_by_reason[r], r)):
            print(f"  {reason:12s}  {counts_by_reason[reason]:4d}  pnl={pnl_by_reason.get(reason,0.0):+.2f}")

    if pnl_by_symbol:
        print("\nTop symbols by realized P/L:")
        for sym, val in sorted(pnl_by_symbol.items(), key=lambda kv: kv[1], reverse=True)[:10]:
            print(f"  {sym:6s} pnl={val:+.2f}  sells={sells_by_symbol.get(sym,0)} win={wins_by_symbol.get(sym,0)} loss={losses_by_symbol.get(sym,0)}")

        print("\nWorst symbols by realized P/L:")
        for sym, val in sorted(pnl_by_symbol.items(), key=lambda kv: kv[1])[:10]:
            print(f"  {sym:6s} pnl={val:+.2f}  sells={sells_by_symbol.get(sym,0)} win={wins_by_symbol.get(sym,0)} loss={losses_by_symbol.get(sym,0)}")


if __name__ == "__main__":
    main()



