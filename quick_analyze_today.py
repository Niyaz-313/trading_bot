#!/usr/bin/env python3
import json
import sys
from datetime import datetime, timezone
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

audit_path = "audit_logs/trades_audit.jsonl"

# Сегодняшний день в UTC
now = datetime.now(timezone.utc)
today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

print("=" * 80)
print("АНАЛИЗ РЕШЕНИЙ БОТА ЗА СЕГОДНЯ")
print("=" * 80)
print(f"Период: с {today_start.strftime('%Y-%m-%d %H:%M:%S')} UTC")
print(f"Текущее время: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
print()

decisions = []
skips = []
trades = []

try:
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
                
                event_type = event.get("event", "")
                if event_type == "decision":
                    decisions.append(event)
                elif event_type == "skip":
                    skips.append(event)
                elif event_type == "trade" and event.get("action") == "BUY":
                    trades.append(event)
            except:
                continue
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)

print(f"Найдено событий:")
print(f"  - Решений (decision): {len(decisions)}")
print(f"  - Пропусков (skip): {len(skips)}")
print(f"  - Покупок (trade BUY): {len(trades)}")
print()

# Решения с BUY сигналами
buy_decisions = [d for d in decisions if d.get("details", {}).get("strategy_should_buy") == True]
print(f"Решений с сигналом BUY: {len(buy_decisions)}")
print()

# Причины пропуска
skip_reasons = defaultdict(int)
for skip in skips:
    reason = skip.get("skip_reason", "unknown")
    skip_reasons[reason] += 1

if skip_reasons:
    print("Причины пропуска:")
    for reason, count in sorted(skip_reasons.items(), key=lambda x: -x[1]):
        print(f"  {reason}: {count}")
    print()

# Упущенные возможности (упрощенно)
if buy_decisions:
    print("Символы с сигналами BUY:")
    for bd in buy_decisions[-10:]:  # Последние 10
        sym = bd.get("symbol", "")
        conf = float(bd.get("confidence", 0) or 0)
        rsi = bd.get("rsi")
        print(f"  {sym}: confidence={conf:.3f}, RSI={rsi}")

print()
print("=" * 80)


