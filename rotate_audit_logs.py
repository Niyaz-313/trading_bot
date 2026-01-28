from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


BASE_DIR = Path(__file__).resolve().parent
AUDIT_DIR = BASE_DIR / "audit_logs"
JSONL_PATH = AUDIT_DIR / "trades_audit.jsonl"
CSV_PATH = AUDIT_DIR / "trades_audit.csv"


def _parse_ts_utc(value: str) -> datetime | None:
    if not value:
        return None
    v = value.strip()
    if not v:
        return None
    try:
        if v.endswith("Z"):
            v = v[:-1] + "+00:00"
        return datetime.fromisoformat(v).astimezone(timezone.utc)
    except Exception:
        return None


def _get_cutoff(days: int) -> datetime:
    now_utc = datetime.now(timezone.utc)
    return now_utc - timedelta(days=int(days))


def _rotate_jsonl(path: Path, cutoff: datetime) -> None:
    if not path.exists():
        return

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    kept = 0
    total = 0

    with path.open("r", encoding="utf-8") as src, tmp_path.open(
        "w", encoding="utf-8"
    ) as dst:
        for line in src:
            total += 1
            line = line.rstrip("\n")
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except Exception:
                dst.write(line + "\n")
                kept += 1
                continue

            ts_raw = obj.get("ts_utc") or obj.get("ts") or ""
            ts = _parse_ts_utc(str(ts_raw))
            if ts is None or ts >= cutoff:
                dst.write(json.dumps(obj, ensure_ascii=False) + "\n")
                kept += 1

    tmp_path.replace(path)
    print(f"[JSONL] {path.name}: всего={total}, осталось={kept}, удалено={total - kept}")


def _rotate_csv(path: Path, cutoff: datetime) -> None:
    if not path.exists():
        return

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    kept = 0
    total = 0

    with path.open("r", encoding="utf-8", newline="") as src, tmp_path.open(
        "w", encoding="utf-8", newline=""
    ) as dst:
        reader = csv.DictReader(src)
        fieldnames: Iterable[str] = reader.fieldnames or []
        writer = csv.DictWriter(dst, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()

        for row in reader:
            total += 1
            ts_raw = row.get("ts_utc") or row.get("ts") or ""
            ts = _parse_ts_utc(str(ts_raw))
            if ts is None or ts >= cutoff:
                writer.writerow(row)
                kept += 1

    tmp_path.replace(path)
    print(f"[CSV] {path.name}: всего={total}, осталось={kept}, удалено={total - kept}")


def main() -> None:
    days = int(os.getenv("LOG_RETENTION_DAYS", "14"))
    cutoff = _get_cutoff(days)
    print(f"Ротация audit-로그ов: сохраняем только записи за последние {days} дней")
    print(f"Граница по времени (UTC): {cutoff.isoformat()}")

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    _rotate_jsonl(JSONL_PATH, cutoff)
    _rotate_csv(CSV_PATH, cutoff)


if __name__ == "__main__":
    main()