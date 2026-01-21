"""
Analyze audit_logs/trades_audit.jsonl for a given time window.

Usage examples (PowerShell/CMD):
  python analyze_audit_period.py --start "2026-01-04 05:49:15" --days 3 --tz Europe/Moscow
  python analyze_audit_period.py --start-utc "2026-01-04T02:49:18Z" --end-utc "2026-01-06T18:03:36Z"
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore


def parse_utc_iso(s: str) -> datetime:
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s).astimezone(timezone.utc)


def safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


@dataclass
class PositionState:
    shares: float = 0.0
    cost: float = 0.0  # total cost basis

    @property
    def avg(self) -> float:
        return self.cost / self.shares if self.shares > 0 else 0.0


def main() -> int:
    # Windows-консоли иногда не UTF‑8 → защитимся
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="audit_logs/trades_audit.jsonl")
    ap.add_argument("--start", default="")
    ap.add_argument("--days", type=int, default=0)
    ap.add_argument("--tz", default="Europe/Moscow")
    ap.add_argument("--start-utc", default="")
    ap.add_argument("--end-utc", default="")
    args = ap.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"ERROR: audit log not found: {path}")
        return 2

    if args.start_utc and args.end_utc:
        start_utc = parse_utc_iso(args.start_utc)
        end_utc = parse_utc_iso(args.end_utc)
    else:
        if not args.start or not args.days:
            print("ERROR: provide either --start-utc/--end-utc or --start/--days")
            return 2
        if ZoneInfo is None:
            print("ERROR: zoneinfo is not available. Install tzdata and use Python 3.9+.")
            return 2
        tz = ZoneInfo(args.tz)
        # Accept "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DD HH:MM:SS,ms"
        s = args.start.strip().replace(",", ".")
        start_local = datetime.fromisoformat(s)
        start_local = start_local.replace(tzinfo=tz)
        start_utc = start_local.astimezone(timezone.utc)
        end_utc = start_utc + timedelta(days=int(args.days))

    # Aggregates
    cycles: list[dict[str, Any]] = []
    skip_reasons: dict[str, int] = {}
    gates_block: dict[str, int] = {}
    decisions_total = 0
    decisions_buy_signal = 0
    decisions_sell_signal = 0
    decisions_buy_veto = 0
    decisions_sell_veto = 0
    buy_candidates = 0
    sell_candidates = 0
    buys = 0
    sells = 0
    sells_with_pnl = 0
    realized_pnl_sum = 0.0

    # Symbol-level stats (realized)
    sym_pnl: dict[str, float] = {}
    sym_sells: dict[str, int] = {}
    sym_wins: dict[str, int] = {}

    # Best-effort avg-cost tracker to compute missing SELL pnl
    pos: dict[str, PositionState] = {}

    # Exit reason stats
    exit_reason_count: dict[str, int] = {}
    exit_reason_pnl: dict[str, float] = {}
    exit_reason_symbol_count: dict[str, dict[str, int]] = {}
    exit_reason_symbol_pnl: dict[str, dict[str, float]] = {}

    # Store a few “interesting” examples to review signal correctness
    examples_buy_veto: list[dict[str, Any]] = []
    examples_gate_block: list[dict[str, Any]] = []

    def add_skip(reason: str):
        r = (reason or "unknown").strip()
        skip_reasons[r] = skip_reasons.get(r, 0) + 1

    def add_gate_block(name: str):
        gates_block[name] = gates_block.get(name, 0) + 1

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue

            ts = e.get("ts_utc") or ""
            if not ts:
                continue
            try:
                dt = parse_utc_iso(ts)
            except Exception:
                continue
            if dt < start_utc or dt >= end_utc:
                continue

            ev = str(e.get("event") or "")
            if ev == "cycle":
                cycles.append(e)
                continue

            if ev == "skip":
                add_skip(str(e.get("skip_reason") or ""))
                continue

            if ev == "decision":
                decisions_total += 1
                details = e.get("details") or {}
                gates = (details.get("gates") if isinstance(details, dict) else {}) or {}
                sig = str(e.get("signal") or "")
                if sig == "buy":
                    decisions_buy_signal += 1
                if sig == "sell":
                    decisions_sell_signal += 1

                should_buy = bool(details.get("strategy_should_buy")) if isinstance(details, dict) else False
                should_sell = bool(details.get("strategy_should_sell")) if isinstance(details, dict) else False

                if isinstance(gates, dict):
                    has_pos = bool(gates.get("has_position", False))
                    # candidates: strategy wants an action (pure strategy), but execution may be blocked
                    if should_buy and not has_pos:
                        buy_candidates += 1
                    if should_sell and has_pos:
                        sell_candidates += 1

                    if not gates.get("max_trades_ok", True):
                        add_gate_block("max_trades_per_day")
                        if should_buy:
                            examples_gate_block.append({"symbol": e.get("symbol"), "ts_utc": e.get("ts_utc"), "gate": "max_trades", "price": e.get("price")})
                    if not gates.get("max_open_positions_ok", True):
                        add_gate_block("max_open_positions")
                        if should_buy:
                            examples_gate_block.append({"symbol": e.get("symbol"), "ts_utc": e.get("ts_utc"), "gate": "max_open_positions", "price": e.get("price")})
                    if not gates.get("cooldown_ok", True):
                        add_gate_block("cooldown")
                        if should_buy:
                            examples_gate_block.append({"symbol": e.get("symbol"), "ts_utc": e.get("ts_utc"), "gate": "cooldown", "price": e.get("price")})
                    if not gates.get("allow_entries", True):
                        add_gate_block("entries_disabled")
                        if should_buy:
                            examples_gate_block.append({"symbol": e.get("symbol"), "ts_utc": e.get("ts_utc"), "gate": "entries_disabled", "price": e.get("price")})

                # Veto analysis: when raw indicator signal says buy/sell, but safety filters veto it
                if sig == "buy" and not should_buy:
                    decisions_buy_veto += 1
                    if len(examples_buy_veto) < 10:
                        examples_buy_veto.append({
                            "ts_utc": e.get("ts_utc"),
                            "symbol": e.get("symbol"),
                            "price": e.get("price"),
                            "rsi": e.get("rsi"),
                            "trend": e.get("trend"),
                            "macd_hist": e.get("macd_hist"),
                            "buy_signals": e.get("buy_signals"),
                            "confidence": e.get("confidence"),
                        })
                if sig == "sell" and not should_sell:
                    decisions_sell_veto += 1
                if isinstance(gates, dict):
                    pass
                continue

            if ev != "trade":
                continue

            sym = str(e.get("symbol") or "").upper().strip()
            action = str(e.get("action") or "").upper().strip()
            qty_lots = safe_float(e.get("qty_lots")) or 0.0
            lot = safe_float(e.get("lot")) or 1.0
            price = safe_float(e.get("price")) or 0.0
            shares = qty_lots * lot

            if action == "BUY":
                buys += 1
                if sym and shares > 0 and price > 0:
                    p = pos.setdefault(sym, PositionState())
                    p.shares += shares
                    p.cost += shares * price
                continue

            if action == "SELL":
                sells += 1
                details = e.get("details") or {}
                reason = str(e.get("reason") or "").strip() or "unknown"
                pnl = None
                if isinstance(details, dict):
                    pnl = safe_float(details.get("pnl"))
                if pnl is not None:
                    sells_with_pnl += 1
                    realized_pnl_sum += float(pnl)
                else:
                    # compute best-effort pnl using avg-cost
                    p = pos.get(sym)
                    if p and p.shares > 0 and shares > 0 and price > 0:
                        sell_sh = min(shares, p.shares)
                        pnl_calc = sell_sh * (price - p.avg)
                        realized_pnl_sum += float(pnl_calc)
                        pnl = float(pnl_calc)
                        p.shares -= sell_sh
                        p.cost -= sell_sh * p.avg
                        if p.shares <= 1e-9:
                            p.shares = 0.0
                            p.cost = 0.0

                if sym and pnl is not None:
                    sym_pnl[sym] = sym_pnl.get(sym, 0.0) + float(pnl)
                    sym_sells[sym] = sym_sells.get(sym, 0) + 1
                    if float(pnl) > 0:
                        sym_wins[sym] = sym_wins.get(sym, 0) + 1
                    exit_reason_count[reason] = exit_reason_count.get(reason, 0) + 1
                    exit_reason_pnl[reason] = exit_reason_pnl.get(reason, 0.0) + float(pnl)
                    exit_reason_symbol_count.setdefault(reason, {})
                    exit_reason_symbol_pnl.setdefault(reason, {})
                    exit_reason_symbol_count[reason][sym] = exit_reason_symbol_count[reason].get(sym, 0) + 1
                    exit_reason_symbol_pnl[reason][sym] = exit_reason_symbol_pnl[reason].get(sym, 0.0) + float(pnl)
                continue

    # Equity metrics
    cycles_sorted = sorted(cycles, key=lambda x: x.get("ts_utc", ""))
    start_eq = safe_float(cycles_sorted[0].get("equity")) if cycles_sorted else None
    end_eq = safe_float(cycles_sorted[-1].get("equity")) if cycles_sorted else None

    dd_max = None
    if cycles_sorted:
        peak = -1e18
        max_dd = 0.0
        for c in cycles_sorted:
            eq = safe_float(c.get("equity"))
            if eq is None:
                continue
            peak = max(peak, eq)
            if peak > 0:
                dd = (eq - peak) / peak
                max_dd = min(max_dd, dd)
        dd_max = max_dd

    print("=== ОТЧЁТ ПО АУДИТУ ЗА ПЕРИОД ===")
    print(f"Окно (UTC): {start_utc.isoformat().replace('+00:00','Z')}  ->  {end_utc.isoformat().replace('+00:00','Z')}")
    if start_eq is not None and end_eq is not None:
        delta = end_eq - start_eq
        pct = (delta / start_eq * 100.0) if start_eq else 0.0
        print(f"Equity: старт={start_eq:.2f}  конец={end_eq:.2f}  Δ={delta:.2f} ({pct:.3f}%)")
    if dd_max is not None:
        print(f"Макс. просадка (по пикам equity внутри периода): {dd_max*100:.3f}%")

    print("")
    print(f"Сделки: BUY={buys}, SELL={sells} (SELL с явным pnl={sells_with_pnl})")
    print(f"Реализованный P/L (best-effort по audit): {realized_pnl_sum:.2f} RUB")

    if sym_pnl:
        print("")
        print("Топ символов по реализованному P/L:")
        for sym, pnl in sorted(sym_pnl.items(), key=lambda kv: kv[1], reverse=True)[:10]:
            n = sym_sells.get(sym, 0)
            w = sym_wins.get(sym, 0)
            wr = (w / n * 100.0) if n else 0.0
            print(f"- {sym}: pnl={pnl:.2f} RUB, SELL={n}, winrate={wr:.1f}%")

    if exit_reason_count:
        print("")
        print("Результаты по причинам выхода (SELL reason):")
        for r, n in sorted(exit_reason_count.items(), key=lambda kv: kv[1], reverse=True):
            pnl = exit_reason_pnl.get(r, 0.0)
            avg = pnl / n if n else 0.0
            print(f"- {r}: сделок={n}, суммарно={pnl:.2f} RUB, среднее={avg:.2f} RUB")

        # Детализация: какие тикеры портят статистику (особенно stop_loss)
        for r in ["stop_loss", "take_profit", "signal"]:
            if r not in exit_reason_symbol_count:
                continue
            print("")
            print(f"Топ тикеров по причине выхода: {r}")
            items = []
            for sym, n in exit_reason_symbol_count.get(r, {}).items():
                pnl = exit_reason_symbol_pnl.get(r, {}).get(sym, 0.0)
                avg = pnl / n if n else 0.0
                items.append((sym, n, pnl, avg))
            # Для stop_loss сортируем по самому плохому pnl, для take_profit — по лучшему
            if r == "stop_loss":
                items.sort(key=lambda x: (x[2], x[1]))  # pnl asc
            else:
                items.sort(key=lambda x: (x[2], x[1]), reverse=True)
            for sym, n, pnl, avg in items[:10]:
                print(f"- {sym}: сделок={n}, суммарно={pnl:.2f} RUB, среднее={avg:.2f} RUB")

    if skip_reasons:
        print("")
        print("Топ причин пропусков (skip_reason):")
        for k, v in sorted(skip_reasons.items(), key=lambda kv: kv[1], reverse=True)[:10]:
            print(f"- {k}: {v}")

    if decisions_total:
        print("")
        print("Корректность принятия решений (на основе decision.*):")
        print(f"- decision событий: {decisions_total}")
        print(f"- сигнал BUY в индикаторах: {decisions_buy_signal}, из них veto фильтрами: {decisions_buy_veto}")
        print(f"- сигнал SELL в индикаторах: {decisions_sell_signal}, из них veto фильтрами: {decisions_sell_veto}")
        print(f"- кандидатов BUY (strategy_should_buy=true и позиции нет): {buy_candidates}")
        print(f"- кандидатов SELL (strategy_should_sell=true и позиция есть): {sell_candidates}")
        if gates_block:
            print("Топ блокировок по гейтам (из decision.details.gates):")
            for k, v in sorted(gates_block.items(), key=lambda kv: kv[1], reverse=True)[:10]:
                print(f"- {k}: {v}")
        if examples_buy_veto:
            print("")
            print("Примеры: индикаторы давали BUY, но фильтры запретили (veto) — первые 10:")
            for ex in examples_buy_veto[:10]:
                print(f"- {ex.get('ts_utc')}: {ex.get('symbol')} price={ex.get('price')} rsi={ex.get('rsi')} trend={ex.get('trend')} macd_hist={ex.get('macd_hist')}")
        if examples_gate_block:
            print("")
            print("Примеры: стратегия хотела BUY, но вход заблокирован гейтами — первые 10:")
            for ex in examples_gate_block[:10]:
                print(f"- {ex.get('ts_utc')}: {ex.get('symbol')} gate={ex.get('gate')} price={ex.get('price')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


