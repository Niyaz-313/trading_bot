"""
Дневные метрики equity по audit_logs/trades_audit.csv:
- start/peak/trough/end equity по каждой дате в заданном окне
- uplift_max (макс рост от старта), drawdown_max (макс падение от пика)

Пример:
  python analyze_day_metrics.py --start 2026-01-12T01:49:43Z --end 2026-01-13T19:30:43Z --tz Europe/Moscow
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from collections import defaultdict

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore


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


def main() -> int:
    # Windows-консоли иногда не UTF‑8 → защитимся
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="audit_logs/trades_audit.csv")
    ap.add_argument("--start", required=True, help="UTC ISO, e.g. 2026-01-12T01:49:43Z")
    ap.add_argument("--end", required=True, help="UTC ISO, e.g. 2026-01-13T19:30:43Z")
    ap.add_argument("--tz", default="Europe/Moscow")
    args = ap.parse_args()

    start_utc = parse_ts_utc(args.start)
    end_utc = parse_ts_utc(args.end)
    if not start_utc or not end_utc:
        raise SystemExit("Bad --start/--end")
    if ZoneInfo is None:
        raise SystemExit("zoneinfo is not available")
    tz = ZoneInfo(args.tz)

    series_by_day: dict[str, list[tuple[dt.datetime, float]]] = defaultdict(list)

    with open(args.csv, encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            ts = parse_ts_utc(row.get("ts_utc") or "")
            if not ts:
                continue
            if ts < start_utc or ts > end_utc:
                continue
            eq = parse_float(row.get("equity"))
            if eq is None or eq <= 0:
                continue
            loc = ts.astimezone(tz)
            day = loc.date().isoformat()
            series_by_day[day].append((ts, float(eq)))

    print("=" * 80)
    print("DAILY EQUITY METRICS (from audit)")
    print("=" * 80)
    print(f"Window UTC: {args.start} -> {args.end}")
    print(f"TZ: {args.tz}")
    print("")

    if not series_by_day:
        print("No equity samples in window.")
        return 2

    for day in sorted(series_by_day.keys()):
        s = sorted(series_by_day[day], key=lambda x: x[0])
        start = s[0][1]
        end = s[-1][1]
        peak = max(v for _, v in s)
        trough = min(v for _, v in s)
        uplift_max = (peak - start) / start * 100.0 if start > 0 else 0.0
        dd_max = (trough - peak) / peak * 100.0 if peak > 0 else 0.0  # negative %
        day_change = (end - start) / start * 100.0 if start > 0 else 0.0
        print(f"{day}: start={start:.2f} peak={peak:.2f} trough={trough:.2f} end={end:.2f}")
        print(f"      Δ(end-start)={day_change:+.3f}%  uplift_max={uplift_max:+.3f}%  max_drawdown={dd_max:.3f}%")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())




Дневные метрики equity по audit_logs/trades_audit.csv:
- start/peak/trough/end equity по каждой дате в заданном окне
- uplift_max (макс рост от старта), drawdown_max (макс падение от пика)

Пример:
  python analyze_day_metrics.py --start 2026-01-12T01:49:43Z --end 2026-01-13T19:30:43Z --tz Europe/Moscow
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from collections import defaultdict

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore


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


def main() -> int:
    # Windows-консоли иногда не UTF‑8 → защитимся
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="audit_logs/trades_audit.csv")
    ap.add_argument("--start", required=True, help="UTC ISO, e.g. 2026-01-12T01:49:43Z")
    ap.add_argument("--end", required=True, help="UTC ISO, e.g. 2026-01-13T19:30:43Z")
    ap.add_argument("--tz", default="Europe/Moscow")
    args = ap.parse_args()

    start_utc = parse_ts_utc(args.start)
    end_utc = parse_ts_utc(args.end)
    if not start_utc or not end_utc:
        raise SystemExit("Bad --start/--end")
    if ZoneInfo is None:
        raise SystemExit("zoneinfo is not available")
    tz = ZoneInfo(args.tz)

    series_by_day: dict[str, list[tuple[dt.datetime, float]]] = defaultdict(list)

    with open(args.csv, encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            ts = parse_ts_utc(row.get("ts_utc") or "")
            if not ts:
                continue
            if ts < start_utc or ts > end_utc:
                continue
            eq = parse_float(row.get("equity"))
            if eq is None or eq <= 0:
                continue
            loc = ts.astimezone(tz)
            day = loc.date().isoformat()
            series_by_day[day].append((ts, float(eq)))

    print("=" * 80)
    print("DAILY EQUITY METRICS (from audit)")
    print("=" * 80)
    print(f"Window UTC: {args.start} -> {args.end}")
    print(f"TZ: {args.tz}")
    print("")

    if not series_by_day:
        print("No equity samples in window.")
        return 2

    for day in sorted(series_by_day.keys()):
        s = sorted(series_by_day[day], key=lambda x: x[0])
        start = s[0][1]
        end = s[-1][1]
        peak = max(v for _, v in s)
        trough = min(v for _, v in s)
        uplift_max = (peak - start) / start * 100.0 if start > 0 else 0.0
        dd_max = (trough - peak) / peak * 100.0 if peak > 0 else 0.0  # negative %
        day_change = (end - start) / start * 100.0 if start > 0 else 0.0
        print(f"{day}: start={start:.2f} peak={peak:.2f} trough={trough:.2f} end={end:.2f}")
        print(f"      Δ(end-start)={day_change:+.3f}%  uplift_max={uplift_max:+.3f}%  max_drawdown={dd_max:.3f}%")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())




Дневные метрики equity по audit_logs/trades_audit.csv:
- start/peak/trough/end equity по каждой дате в заданном окне
- uplift_max (макс рост от старта), drawdown_max (макс падение от пика)

Пример:
  python analyze_day_metrics.py --start 2026-01-12T01:49:43Z --end 2026-01-13T19:30:43Z --tz Europe/Moscow
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from collections import defaultdict

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore


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


def main() -> int:
    # Windows-консоли иногда не UTF‑8 → защитимся
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="audit_logs/trades_audit.csv")
    ap.add_argument("--start", required=True, help="UTC ISO, e.g. 2026-01-12T01:49:43Z")
    ap.add_argument("--end", required=True, help="UTC ISO, e.g. 2026-01-13T19:30:43Z")
    ap.add_argument("--tz", default="Europe/Moscow")
    args = ap.parse_args()

    start_utc = parse_ts_utc(args.start)
    end_utc = parse_ts_utc(args.end)
    if not start_utc or not end_utc:
        raise SystemExit("Bad --start/--end")
    if ZoneInfo is None:
        raise SystemExit("zoneinfo is not available")
    tz = ZoneInfo(args.tz)

    series_by_day: dict[str, list[tuple[dt.datetime, float]]] = defaultdict(list)

    with open(args.csv, encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            ts = parse_ts_utc(row.get("ts_utc") or "")
            if not ts:
                continue
            if ts < start_utc or ts > end_utc:
                continue
            eq = parse_float(row.get("equity"))
            if eq is None or eq <= 0:
                continue
            loc = ts.astimezone(tz)
            day = loc.date().isoformat()
            series_by_day[day].append((ts, float(eq)))

    print("=" * 80)
    print("DAILY EQUITY METRICS (from audit)")
    print("=" * 80)
    print(f"Window UTC: {args.start} -> {args.end}")
    print(f"TZ: {args.tz}")
    print("")

    if not series_by_day:
        print("No equity samples in window.")
        return 2

    for day in sorted(series_by_day.keys()):
        s = sorted(series_by_day[day], key=lambda x: x[0])
        start = s[0][1]
        end = s[-1][1]
        peak = max(v for _, v in s)
        trough = min(v for _, v in s)
        uplift_max = (peak - start) / start * 100.0 if start > 0 else 0.0
        dd_max = (trough - peak) / peak * 100.0 if peak > 0 else 0.0  # negative %
        day_change = (end - start) / start * 100.0 if start > 0 else 0.0
        print(f"{day}: start={start:.2f} peak={peak:.2f} trough={trough:.2f} end={end:.2f}")
        print(f"      Δ(end-start)={day_change:+.3f}%  uplift_max={uplift_max:+.3f}%  max_drawdown={dd_max:.3f}%")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())








