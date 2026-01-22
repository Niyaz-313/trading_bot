#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import sys
from datetime import datetime, timezone
from collections import defaultdict

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

audit_path = "audit_logs/trades_audit.jsonl"
today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

print("=" * 100)
print("АНАЛИЗ РЕШЕНИЙ БОТА ЗА СЕГОДНЯ")
print("=" * 100)
print(f"Период: с {today_start.strftime('%Y-%m-%d %H:%M:%S')} UTC")
print()

decisions = []
skips = []
trades = []

with open(audit_path, "r", encoding="utf-8") as f:
    for line in f:
        try:
            event = json.loads(line.strip())
            ts_str = event.get("ts_utc", "")
            if not ts_str:
                continue
            
            if ts_str.endswith("Z"):
                ts_str = ts_str[:-1] + "+00:00"
            event_dt = datetime.fromisoformat(ts_str)
            
            if event_dt < today_start:
                continue
            
            if event.get("event") == "decision":
                decisions.append(event)
            elif event.get("event") == "skip":
                skips.append(event)
            elif event.get("event") == "trade" and event.get("action") == "BUY":
                trades.append(event)
        except:
            continue

print(f"Решений: {len(decisions)}")
print(f"Пропусков: {len(skips)}")
print(f"Покупок: {len(trades)}")
print()

# Анализ решений с buy сигналами
buy_signals = [d for d in decisions if d.get("signal") == "buy"]
print(f"Решений с signal='buy': {len(buy_signals)}")

strategy_buy = [d for d in decisions if d.get("details", {}).get("strategy_should_buy") == True]
print(f"Решений с strategy_should_buy=true: {len(strategy_buy)}")
print()

# Анализ причин
if buy_signals:
    print("Случаи с signal='buy' но strategy_should_buy=false:")
    for d in buy_signals[:10]:
        sym = d.get("symbol", "")
        conf = float(d.get("confidence", 0) or 0)
        rsi = d.get("rsi")
        trend = d.get("trend", "")
        should_buy = d.get("details", {}).get("strategy_should_buy", False)
        print(f"  {sym}: conf={conf:.2f}, RSI={rsi}, trend={trend}, should_buy={should_buy}")
    print()

# Причины пропуска
skip_reasons = defaultdict(int)
for s in skips:
    reason = s.get("skip_reason", "unknown")
    skip_reasons[reason] += 1

if skip_reasons:
    print("Причины пропуска:")
    for r, c in sorted(skip_reasons.items(), key=lambda x: -x[1]):
        print(f"  {r}: {c}")
    print()

# Анализ решений не покупать
no_buy = [d for d in decisions if d.get("details", {}).get("strategy_should_buy") == False]
print(f"Решений 'не покупать': {len(no_buy)}")

# Причины отказа
reasons = defaultdict(int)
for d in no_buy:
    signal = d.get("signal", "")
    rsi = d.get("rsi")
    trend = d.get("trend", "")
    macd_hist = d.get("macd_hist")
    
    if signal == "sell":
        reasons["signal_sell"] += 1
    elif rsi and float(rsi) > 68:
        reasons["rsi_too_high"] += 1
    elif trend == "sideways" and macd_hist and float(macd_hist) < 0:
        reasons["sideways_negative_macd"] += 1
    elif trend == "down":
        reasons["trend_down"] += 1
    else:
        reasons["other"] += 1

print("Причины отказа:")
for r, c in sorted(reasons.items(), key=lambda x: -x[1]):
    print(f"  {r}: {c}")

print()
print("=" * 100)


