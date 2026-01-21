"""
Append-only audit logger for trading actions.

Writes JSON Lines (one JSON object per line) to a file.
This file is meant to be durable and never overwritten by the application.
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional


@dataclass
class AuditLogger:
    path: str

    def __post_init__(self) -> None:
        # Ensure directory exists.
        d = os.path.dirname(self.path)
        if d:
            os.makedirs(d, exist_ok=True)

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def append(self, event: dict[str, Any]) -> None:
        """
        Append one audit event as JSONL.

        This method never truncates or rotates the file.
        """
        # Ensure required fields
        event = dict(event)
        event.setdefault("ts_utc", self._now_iso())

        line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        # Line-buffered append. This keeps the file append-only.
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


@dataclass
class CsvAuditLogger:
    """
    Append-only CSV audit logger (Excel-friendly).

    - Creates the file with header if it doesn't exist.
    - Never truncates or rotates the file.
    """

    path: str
    fieldnames: list[str]

    def __post_init__(self) -> None:
        d = os.path.dirname(self.path)
        if d:
            os.makedirs(d, exist_ok=True)

        if not os.path.exists(self.path) or os.path.getsize(self.path) == 0:
            with open(self.path, "a", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=self.fieldnames)
                w.writeheader()

    def append(self, row: dict[str, Any]) -> None:
        # Ensure stringable values for CSV
        out: dict[str, Any] = {}
        for k in self.fieldnames:
            v = row.get(k, "")
            if v is None:
                out[k] = ""
            elif isinstance(v, (dict, list)):
                out[k] = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
            else:
                out[k] = v

        with open(self.path, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=self.fieldnames)
            w.writerow(out)


def read_last_jsonl_events(
    path: str,
    limit: int = 10,
    predicate: Optional[Callable[[dict[str, Any]], bool]] = None,
    max_bytes: int = 2_000_000,
) -> list[dict[str, Any]]:
    """
    Read last JSONL events from a potentially large file.

    - Reads from file end in chunks to avoid loading whole file.
    - Returns newest-first list limited by `limit`.
    """
    if limit <= 0:
        return []
    if not os.path.exists(path):
        return []

    events: list[dict[str, Any]] = []
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            end = f.tell()
            pos = end
            buf = b""
            read_bytes = 0

            while pos > 0 and len(events) < limit and read_bytes < max_bytes:
                step = 65536 if pos >= 65536 else pos
                pos -= step
                f.seek(pos, os.SEEK_SET)
                chunk = f.read(step)
                read_bytes += len(chunk)
                buf = chunk + buf
                lines = buf.splitlines()
                # keep first partial line in buf (if any)
                buf = lines[0] if (lines and not buf.endswith(b"\n")) else b""

                # iterate from end (newest lines)
                for raw in reversed(lines[1:] if buf else lines):
                    if len(events) >= limit:
                        break
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        obj = json.loads(raw.decode("utf-8"))
                    except Exception:
                        continue
                    if predicate and not predicate(obj):
                        continue
                    events.append(obj)

            return events
    except Exception:
        return []


def compute_avg_cost_from_audit(
    path: str,
    max_bytes: int = 20_000_000,
) -> dict[str, dict[str, Any]]:
    """
    Compute average-cost basis per symbol from audit JSONL trade events.

    Uses a simple average cost method:
    - BUY: add shares and add cost = shares * price
    - SELL: reduce shares and reduce cost proportionally (by current average)

    Returns:
      { SYMBOL: { "shares": float, "avg_price": float, "cost": float, "last_buy_ts_utc": str } }
    """
    if not os.path.exists(path):
        return {}

    positions: dict[str, dict[str, Any]] = {}
    size = os.path.getsize(path)
    if size > max_bytes:
        # If file is huge, read the tail only (best-effort).
        # For full accuracy you can increase max_bytes.
        start_pos = max(0, size - max_bytes)
    else:
        start_pos = 0

    try:
        with open(path, "rb") as f:
            if start_pos:
                f.seek(start_pos, os.SEEK_SET)
                # align to next newline
                f.readline()

            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    e = json.loads(raw.decode("utf-8"))
                except Exception:
                    continue

                if e.get("event") != "trade":
                    continue

                sym = str(e.get("symbol") or "").upper().strip()
                action = str(e.get("action") or "").upper().strip()
                if not sym or action not in ("BUY", "SELL"):
                    continue

                price = safe_float(e.get("price")) or 0.0
                qty_lots = safe_float(e.get("qty_lots"))
                lot = safe_float(e.get("lot"))

                # shares traded
                shares = 0.0
                if qty_lots is not None and lot is not None and lot > 0:
                    shares = float(qty_lots) * float(lot)
                elif qty_lots is not None:
                    shares = float(qty_lots)
                if shares <= 0:
                    continue

                p = positions.setdefault(sym, {"shares": 0.0, "cost": 0.0, "avg_price": 0.0, "last_buy_ts_utc": ""})
                cur_sh = float(p["shares"])
                cur_cost = float(p["cost"])

                if action == "BUY":
                    add_cost = shares * price
                    cur_sh += shares
                    cur_cost += add_cost
                    p["shares"] = cur_sh
                    p["cost"] = cur_cost
                    p["avg_price"] = (cur_cost / cur_sh) if cur_sh > 0 else 0.0
                    p["last_buy_ts_utc"] = e.get("ts_utc", "") or p.get("last_buy_ts_utc", "")
                else:
                    # SELL: reduce by average-cost
                    if cur_sh <= 0:
                        continue
                    sell_sh = min(shares, cur_sh)
                    avg = (cur_cost / cur_sh) if cur_sh > 0 else 0.0
                    cur_sh -= sell_sh
                    cur_cost -= sell_sh * avg
                    if cur_sh <= 1e-9:
                        cur_sh = 0.0
                        cur_cost = 0.0
                    p["shares"] = cur_sh
                    p["cost"] = cur_cost
                    p["avg_price"] = (cur_cost / cur_sh) if cur_sh > 0 else 0.0

        # remove empty positions
        return {k: v for k, v in positions.items() if float(v.get("shares", 0.0) or 0.0) > 0}
    except Exception:
        return {}


