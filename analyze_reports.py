"""
Агрегатор результатов бэктеста по CSV из папки reports/.

Читает файлы формата:
  reports/trades_<SYMBOL>_<STRATEGY>.csv
и строит сводку по:
  - суммарный P/L
  - количество BUY/SELL
  - winrate по SELL
  - P/L по причинам выхода (stop_loss/take_profit/signal/прочее)

Выводит таблицу в консоль и сохраняет:
  reports/summary_by_symbol_strategy.csv
  reports/summary_by_symbol_best.csv
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd


def _safe_float(x, default: float = 0.0) -> float:
    try:
        if pd.isna(x):
            return default
        return float(x)
    except Exception:
        return default


@dataclass
class Row:
    symbol: str
    strategy: str
    trades: int
    buys: int
    sells: int
    pnl_sum: float
    wins: int
    losses: int
    winrate_pct: float
    pnl_stop: float
    pnl_take: float
    pnl_signal: float
    pnl_other: float


def main() -> int:
    reports_dir = Path("reports")
    if not reports_dir.exists():
        print("Папка reports/ не найдена.")
        return 2

    files = sorted(reports_dir.glob("trades_*_*.csv"))
    if not files:
        print("В папке reports/ нет файлов trades_<SYMBOL>_<STRATEGY>.csv")
        return 3

    rows: List[Row] = []
    for fp in files:
        # trades_<SYMBOL>_<STRATEGY>.csv
        name = fp.stem
        parts = name.split("_")
        if len(parts) < 3:
            continue
        symbol = parts[1].strip().upper()
        strategy = "_".join(parts[2:]).strip().lower()

        try:
            df = pd.read_csv(fp)
        except Exception:
            continue

        if df.empty:
            continue

        # нормализуем
        df["action"] = df.get("action", "").astype(str).str.upper()
        df["reason"] = df.get("reason", "").astype(str).str.lower()
        df["pnl"] = df.get("pnl", 0.0).apply(_safe_float)

        trades = int(len(df))
        buys = int((df["action"] == "BUY").sum())
        sells = int((df["action"] == "SELL").sum())

        sell_df = df[df["action"] == "SELL"].copy()
        pnl_sum = float(sell_df["pnl"].sum()) if not sell_df.empty else 0.0
        wins = int((sell_df["pnl"] > 0).sum()) if not sell_df.empty else 0
        losses = int((sell_df["pnl"] < 0).sum()) if not sell_df.empty else 0
        winrate_pct = float(wins / max(1, (wins + losses)) * 100.0) if (wins + losses) > 0 else 0.0

        def pnl_reason(r: str) -> float:
            s = sell_df[sell_df["reason"] == r]["pnl"].sum()
            return float(s) if not pd.isna(s) else 0.0

        pnl_stop = pnl_reason("stop_loss")
        pnl_take = pnl_reason("take_profit")
        pnl_signal = pnl_reason("signal")
        pnl_other = float(sell_df[~sell_df["reason"].isin(["stop_loss", "take_profit", "signal"])]["pnl"].sum()) if not sell_df.empty else 0.0

        rows.append(
            Row(
                symbol=symbol,
                strategy=strategy,
                trades=trades,
                buys=buys,
                sells=sells,
                pnl_sum=pnl_sum,
                wins=wins,
                losses=losses,
                winrate_pct=winrate_pct,
                pnl_stop=pnl_stop,
                pnl_take=pnl_take,
                pnl_signal=pnl_signal,
                pnl_other=pnl_other,
            )
        )

    if not rows:
        print("Не удалось прочитать данные из reports/.")
        return 4

    out = pd.DataFrame([r.__dict__ for r in rows])
    out = out.sort_values(["symbol", "pnl_sum"], ascending=[True, False]).reset_index(drop=True)

    # Best-per-symbol по pnl_sum
    best_rows = []
    for sym, g in out.groupby("symbol", dropna=False):
        g2 = g.sort_values(["pnl_sum", "sells"], ascending=[False, False]).head(1)
        best_rows.append(g2)
    best = pd.concat(best_rows, ignore_index=True).sort_values("pnl_sum", ascending=False).reset_index(drop=True)

    # Печать в консоль
    pd.set_option("display.max_rows", 200)
    pd.set_option("display.max_columns", 200)
    pd.set_option("display.width", 200)

    print("=== SUMMARY: по symbol+strategy (sorted by symbol, best pnl first) ===")
    print(out[[
        "symbol","strategy","pnl_sum","trades","buys","sells","winrate_pct","pnl_stop","pnl_take","pnl_signal","pnl_other"
    ]].to_string(index=False))

    print("\n=== BEST: по символу (лучший strategy по pnl_sum) ===")
    print(best[[
        "symbol","strategy","pnl_sum","sells","winrate_pct","pnl_stop","pnl_take","pnl_signal"
    ]].to_string(index=False))

    # Сохранение
    out_path = reports_dir / "summary_by_symbol_strategy.csv"
    best_path = reports_dir / "summary_by_symbol_best.csv"
    out.to_csv(out_path, index=False, encoding="utf-8")
    best.to_csv(best_path, index=False, encoding="utf-8")
    print(f"\nСохранено:\n- {out_path}\n- {best_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())





