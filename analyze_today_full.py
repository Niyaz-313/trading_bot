#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Полный анализ решений бота за сегодняшний день
"""
import json
import sys
from datetime import datetime, timezone
from collections import defaultdict

# Настройка кодировки
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

audit_path = "audit_logs/trades_audit.jsonl"

# Сегодняшний день в UTC
now = datetime.now(timezone.utc)
today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

output_lines = []

def print_out(s):
    output_lines.append(s)
    print(s)

print_out("=" * 100)
print_out("АНАЛИЗ РЕШЕНИЙ БОТА О ПОКУПКЕ ЗА СЕГОДНЯШНИЙ ДЕНЬ")
print_out("=" * 100)
print_out(f"Период анализа: с {today_start.strftime('%Y-%m-%d %H:%M:%S')} UTC")
print_out(f"Текущее время: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
print_out("")

decisions = []
skips = []
trades_buy = []
cycles = []

try:
    with open(audit_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                event = json.loads(line.strip())
                ts_str = event.get("ts_utc", "")
                if not ts_str:
                    continue
                
                # Парсим timestamp
                if ts_str.endswith("Z"):
                    ts_str = ts_str[:-1] + "+00:00"
                try:
                    event_dt = datetime.fromisoformat(ts_str)
                except:
                    continue
                
                if event_dt < today_start:
                    continue
                
                event_type = event.get("event", "")
                if event_type == "decision":
                    decisions.append(event)
                elif event_type == "skip":
                    skips.append(event)
                elif event_type == "trade" and event.get("action") == "BUY":
                    trades_buy.append(event)
                elif event_type == "cycle":
                    cycles.append(event)
            except Exception as e:
                continue
except Exception as e:
    print_out(f"ERROR: {e}")
    sys.exit(1)

print_out(f"📊 СТАТИСТИКА СОБЫТИЙ:")
print_out(f"   - Решений (decision): {len(decisions)}")
print_out(f"   - Пропусков (skip): {len(skips)}")
print_out(f"   - Покупок (trade BUY): {len(trades_buy)}")
print_out(f"   - Циклов (cycle): {len(cycles)}")
print_out("")

# Анализ решений с BUY сигналами
buy_decisions = []
for d in decisions:
    details = d.get("details", {})
    if details.get("strategy_should_buy") == True:
        buy_decisions.append(d)

print_out("-" * 100)
print_out("АНАЛИЗ РЕШЕНИЙ С СИГНАЛАМИ BUY (но не куплено)")
print_out("-" * 100)
print_out(f"Найдено решений с сигналом BUY от стратегии: {len(buy_decisions)}")
print_out("")

if len(buy_decisions) == 0:
    print_out("⚠️  ВНИМАНИЕ: Стратегия НЕ генерировала сигналы BUY за сегодня!")
    print_out("   Это означает, что стратегия считает, что условия для покупки не подходят.")
    print_out("")
    
    # Анализируем почему нет сигналов
    symbols_analyzed = set()
    for d in decisions:
        sym = d.get("symbol", "")
        if sym:
            symbols_analyzed.add(sym)
    
    print_out(f"Символов проанализировано: {len(symbols_analyzed)}")
    print_out("")
    
    # Статистика по сигналам
    signal_stats = defaultdict(int)
    for d in decisions:
        details = d.get("details", {})
        should_buy = details.get("strategy_should_buy", False)
        should_sell = details.get("strategy_should_sell", False)
        if should_buy:
            signal_stats["buy"] += 1
        elif should_sell:
            signal_stats["sell"] += 1
        else:
            signal_stats["hold"] += 1
    
    print_out("Распределение сигналов стратегии:")
    print_out(f"   BUY: {signal_stats['buy']}")
    print_out(f"   SELL: {signal_stats['sell']}")
    print_out(f"   HOLD: {signal_stats['hold']}")
    print_out("")
    
    # Анализ confidence
    confidences = [float(d.get("confidence", 0) or 0) for d in decisions if d.get("confidence")]
    if confidences:
        avg_conf = sum(confidences) / len(confidences)
        max_conf = max(confidences)
        min_conf = min(confidences)
        print_out(f"Статистика confidence:")
        print_out(f"   Средний: {avg_conf:.3f}")
        print_out(f"   Максимум: {max_conf:.3f}")
        print_out(f"   Минимум: {min_conf:.3f}")
        print_out("")
else:
    # Группируем по символам
    buy_by_symbol = defaultdict(list)
    for bd in buy_decisions:
        sym = bd.get("symbol", "")
        if sym:
            buy_by_symbol[sym].append(bd)
    
    print_out(f"Символов с сигналами BUY: {len(buy_by_symbol)}")
    print_out("")
    
    for symbol, events in sorted(buy_by_symbol.items()):
        latest = events[-1]
        conf = float(latest.get("confidence", 0) or 0)
        rsi = latest.get("rsi")
        trend = latest.get("trend", "")
        price = latest.get("price")
        ts = latest.get("ts_utc", "")
        print_out(f"📈 {symbol}: confidence={conf:.3f}, RSI={rsi}, trend={trend}, price={price}, time={ts}")

print_out("")

# Анализ пропусков
print_out("-" * 100)
print_out("АНАЛИЗ ПРИЧИН ПРОПУСКА ПОКУПОК (skip events)")
print_out("-" * 100)

skip_reasons = defaultdict(int)
skip_by_reason = defaultdict(list)

for skip in skips:
    reason = skip.get("skip_reason", "unknown")
    skip_reasons[reason] += 1
    skip_by_reason[reason].append(skip)

if skip_reasons:
    print_out("Причины пропуска (по частоте):")
    for reason, count in sorted(skip_reasons.items(), key=lambda x: -x[1]):
        print_out(f"   {reason}: {count} раз(а)")
    print_out("")
    
    # Детальный анализ
    for reason, events in sorted(skip_by_reason.items(), key=lambda x: -len(x[1])):
        print_out(f"📋 {reason} ({len(events)} раз):")
        
        symbols = defaultdict(int)
        confidences = []
        for ev in events:
            sym = ev.get("symbol", "")
            if sym:
                symbols[sym] += 1
            conf = float(ev.get("confidence", 0) or 0)
            if conf > 0:
                confidences.append(conf)
        
        if symbols:
            print_out(f"   Затронутые символы: {', '.join(sorted(symbols.keys())[:10])}")
        if confidences:
            avg_conf = sum(confidences) / len(confidences)
            print_out(f"   Средний confidence: {avg_conf:.3f}")
        print_out("")
else:
    print_out("⚠️  Нет событий пропуска (skip) - возможно, проблема в стратегии.")
    print_out("")

# Рекомендации
print_out("-" * 100)
print_out("РЕКОМЕНДАЦИИ ПО ИСПРАВЛЕНИЮ")
print_out("-" * 100)

recommendations = []

if len(buy_decisions) == 0:
    recommendations.append("⚠️  Стратегия не генерирует сигналы BUY. Возможные причины:")
    recommendations.append("   1. Рынок в боковом/медвежьем тренде")
    recommendations.append("   2. Фильтры стратегии слишком строгие (RSI, MACD, trend)")
    recommendations.append("   3. Все символы не проходят проверки стратегии")
    recommendations.append("   Рекомендация: проверить логику стратегии или снизить пороги")

if skip_reasons.get("rsi_too_high_for_buy", 0) > 0:
    count = skip_reasons["rsi_too_high_for_buy"]
    recommendations.append(f"🔧 RSI_MAX_BUY слишком строгий ({count} пропусков). Рекомендация: увеличить до 68-70")

if skip_reasons.get("low_macd_hist_atr_ratio", 0) > 0:
    count = skip_reasons["low_macd_hist_atr_ratio"]
    recommendations.append(f"🔧 MIN_MACD_HIST_ATR_RATIO_BUY слишком строгий ({count} пропусков). Рекомендация: снизить до -0.15")

if skip_reasons.get("low_confidence", 0) > 0:
    count = skip_reasons["low_confidence"]
    recommendations.append(f"🔧 MIN_CONF_BUY слишком высокий ({count} пропусков). Рекомендация: снизить до 0.55-0.58")

if len(trades_buy) == 0:
    recommendations.append("💰 Нет покупок за сегодня. Проверьте:")
    recommendations.append("   1. ENABLE_TRADING=true в конфигурации")
    recommendations.append("   2. allow_entries=true (не заблокировано через Telegram)")
    recommendations.append("   3. Достаточно cash на счете")
    recommendations.append("   4. Не достигнут лимит MAX_OPEN_POSITIONS")

if not recommendations:
    recommendations.append("✓ Не найдено очевидных проблем.")

for i, rec in enumerate(recommendations, 1):
    print_out(f"{i}. {rec}")

print_out("")
print_out("=" * 100)

# Сохраняем в файл
try:
    with open("analysis_today_report.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    print_out("\n✓ Отчет сохранен в analysis_today_report.txt")
except Exception as e:
    print_out(f"\n⚠️  Не удалось сохранить отчет: {e}")

# -*- coding: utf-8 -*-
"""
Полный анализ решений бота за сегодняшний день
"""
import json
import sys
from datetime import datetime, timezone
from collections import defaultdict

# Настройка кодировки
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

audit_path = "audit_logs/trades_audit.jsonl"

# Сегодняшний день в UTC
now = datetime.now(timezone.utc)
today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

output_lines = []

def print_out(s):
    output_lines.append(s)
    print(s)

print_out("=" * 100)
print_out("АНАЛИЗ РЕШЕНИЙ БОТА О ПОКУПКЕ ЗА СЕГОДНЯШНИЙ ДЕНЬ")
print_out("=" * 100)
print_out(f"Период анализа: с {today_start.strftime('%Y-%m-%d %H:%M:%S')} UTC")
print_out(f"Текущее время: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
print_out("")

decisions = []
skips = []
trades_buy = []
cycles = []

try:
    with open(audit_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                event = json.loads(line.strip())
                ts_str = event.get("ts_utc", "")
                if not ts_str:
                    continue
                
                # Парсим timestamp
                if ts_str.endswith("Z"):
                    ts_str = ts_str[:-1] + "+00:00"
                try:
                    event_dt = datetime.fromisoformat(ts_str)
                except:
                    continue
                
                if event_dt < today_start:
                    continue
                
                event_type = event.get("event", "")
                if event_type == "decision":
                    decisions.append(event)
                elif event_type == "skip":
                    skips.append(event)
                elif event_type == "trade" and event.get("action") == "BUY":
                    trades_buy.append(event)
                elif event_type == "cycle":
                    cycles.append(event)
            except Exception as e:
                continue
except Exception as e:
    print_out(f"ERROR: {e}")
    sys.exit(1)

print_out(f"📊 СТАТИСТИКА СОБЫТИЙ:")
print_out(f"   - Решений (decision): {len(decisions)}")
print_out(f"   - Пропусков (skip): {len(skips)}")
print_out(f"   - Покупок (trade BUY): {len(trades_buy)}")
print_out(f"   - Циклов (cycle): {len(cycles)}")
print_out("")

# Анализ решений с BUY сигналами
buy_decisions = []
for d in decisions:
    details = d.get("details", {})
    if details.get("strategy_should_buy") == True:
        buy_decisions.append(d)

print_out("-" * 100)
print_out("АНАЛИЗ РЕШЕНИЙ С СИГНАЛАМИ BUY (но не куплено)")
print_out("-" * 100)
print_out(f"Найдено решений с сигналом BUY от стратегии: {len(buy_decisions)}")
print_out("")

if len(buy_decisions) == 0:
    print_out("⚠️  ВНИМАНИЕ: Стратегия НЕ генерировала сигналы BUY за сегодня!")
    print_out("   Это означает, что стратегия считает, что условия для покупки не подходят.")
    print_out("")
    
    # Анализируем почему нет сигналов
    symbols_analyzed = set()
    for d in decisions:
        sym = d.get("symbol", "")
        if sym:
            symbols_analyzed.add(sym)
    
    print_out(f"Символов проанализировано: {len(symbols_analyzed)}")
    print_out("")
    
    # Статистика по сигналам
    signal_stats = defaultdict(int)
    for d in decisions:
        details = d.get("details", {})
        should_buy = details.get("strategy_should_buy", False)
        should_sell = details.get("strategy_should_sell", False)
        if should_buy:
            signal_stats["buy"] += 1
        elif should_sell:
            signal_stats["sell"] += 1
        else:
            signal_stats["hold"] += 1
    
    print_out("Распределение сигналов стратегии:")
    print_out(f"   BUY: {signal_stats['buy']}")
    print_out(f"   SELL: {signal_stats['sell']}")
    print_out(f"   HOLD: {signal_stats['hold']}")
    print_out("")
    
    # Анализ confidence
    confidences = [float(d.get("confidence", 0) or 0) for d in decisions if d.get("confidence")]
    if confidences:
        avg_conf = sum(confidences) / len(confidences)
        max_conf = max(confidences)
        min_conf = min(confidences)
        print_out(f"Статистика confidence:")
        print_out(f"   Средний: {avg_conf:.3f}")
        print_out(f"   Максимум: {max_conf:.3f}")
        print_out(f"   Минимум: {min_conf:.3f}")
        print_out("")
else:
    # Группируем по символам
    buy_by_symbol = defaultdict(list)
    for bd in buy_decisions:
        sym = bd.get("symbol", "")
        if sym:
            buy_by_symbol[sym].append(bd)
    
    print_out(f"Символов с сигналами BUY: {len(buy_by_symbol)}")
    print_out("")
    
    for symbol, events in sorted(buy_by_symbol.items()):
        latest = events[-1]
        conf = float(latest.get("confidence", 0) or 0)
        rsi = latest.get("rsi")
        trend = latest.get("trend", "")
        price = latest.get("price")
        ts = latest.get("ts_utc", "")
        print_out(f"📈 {symbol}: confidence={conf:.3f}, RSI={rsi}, trend={trend}, price={price}, time={ts}")

print_out("")

# Анализ пропусков
print_out("-" * 100)
print_out("АНАЛИЗ ПРИЧИН ПРОПУСКА ПОКУПОК (skip events)")
print_out("-" * 100)

skip_reasons = defaultdict(int)
skip_by_reason = defaultdict(list)

for skip in skips:
    reason = skip.get("skip_reason", "unknown")
    skip_reasons[reason] += 1
    skip_by_reason[reason].append(skip)

if skip_reasons:
    print_out("Причины пропуска (по частоте):")
    for reason, count in sorted(skip_reasons.items(), key=lambda x: -x[1]):
        print_out(f"   {reason}: {count} раз(а)")
    print_out("")
    
    # Детальный анализ
    for reason, events in sorted(skip_by_reason.items(), key=lambda x: -len(x[1])):
        print_out(f"📋 {reason} ({len(events)} раз):")
        
        symbols = defaultdict(int)
        confidences = []
        for ev in events:
            sym = ev.get("symbol", "")
            if sym:
                symbols[sym] += 1
            conf = float(ev.get("confidence", 0) or 0)
            if conf > 0:
                confidences.append(conf)
        
        if symbols:
            print_out(f"   Затронутые символы: {', '.join(sorted(symbols.keys())[:10])}")
        if confidences:
            avg_conf = sum(confidences) / len(confidences)
            print_out(f"   Средний confidence: {avg_conf:.3f}")
        print_out("")
else:
    print_out("⚠️  Нет событий пропуска (skip) - возможно, проблема в стратегии.")
    print_out("")

# Рекомендации
print_out("-" * 100)
print_out("РЕКОМЕНДАЦИИ ПО ИСПРАВЛЕНИЮ")
print_out("-" * 100)

recommendations = []

if len(buy_decisions) == 0:
    recommendations.append("⚠️  Стратегия не генерирует сигналы BUY. Возможные причины:")
    recommendations.append("   1. Рынок в боковом/медвежьем тренде")
    recommendations.append("   2. Фильтры стратегии слишком строгие (RSI, MACD, trend)")
    recommendations.append("   3. Все символы не проходят проверки стратегии")
    recommendations.append("   Рекомендация: проверить логику стратегии или снизить пороги")

if skip_reasons.get("rsi_too_high_for_buy", 0) > 0:
    count = skip_reasons["rsi_too_high_for_buy"]
    recommendations.append(f"🔧 RSI_MAX_BUY слишком строгий ({count} пропусков). Рекомендация: увеличить до 68-70")

if skip_reasons.get("low_macd_hist_atr_ratio", 0) > 0:
    count = skip_reasons["low_macd_hist_atr_ratio"]
    recommendations.append(f"🔧 MIN_MACD_HIST_ATR_RATIO_BUY слишком строгий ({count} пропусков). Рекомендация: снизить до -0.15")

if skip_reasons.get("low_confidence", 0) > 0:
    count = skip_reasons["low_confidence"]
    recommendations.append(f"🔧 MIN_CONF_BUY слишком высокий ({count} пропусков). Рекомендация: снизить до 0.55-0.58")

if len(trades_buy) == 0:
    recommendations.append("💰 Нет покупок за сегодня. Проверьте:")
    recommendations.append("   1. ENABLE_TRADING=true в конфигурации")
    recommendations.append("   2. allow_entries=true (не заблокировано через Telegram)")
    recommendations.append("   3. Достаточно cash на счете")
    recommendations.append("   4. Не достигнут лимит MAX_OPEN_POSITIONS")

if not recommendations:
    recommendations.append("✓ Не найдено очевидных проблем.")

for i, rec in enumerate(recommendations, 1):
    print_out(f"{i}. {rec}")

print_out("")
print_out("=" * 100)

# Сохраняем в файл
try:
    with open("analysis_today_report.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    print_out("\n✓ Отчет сохранен в analysis_today_report.txt")
except Exception as e:
    print_out(f"\n⚠️  Не удалось сохранить отчет: {e}")

# -*- coding: utf-8 -*-
"""
Полный анализ решений бота за сегодняшний день
"""
import json
import sys
from datetime import datetime, timezone
from collections import defaultdict

# Настройка кодировки
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

audit_path = "audit_logs/trades_audit.jsonl"

# Сегодняшний день в UTC
now = datetime.now(timezone.utc)
today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

output_lines = []

def print_out(s):
    output_lines.append(s)
    print(s)

print_out("=" * 100)
print_out("АНАЛИЗ РЕШЕНИЙ БОТА О ПОКУПКЕ ЗА СЕГОДНЯШНИЙ ДЕНЬ")
print_out("=" * 100)
print_out(f"Период анализа: с {today_start.strftime('%Y-%m-%d %H:%M:%S')} UTC")
print_out(f"Текущее время: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
print_out("")

decisions = []
skips = []
trades_buy = []
cycles = []

try:
    with open(audit_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                event = json.loads(line.strip())
                ts_str = event.get("ts_utc", "")
                if not ts_str:
                    continue
                
                # Парсим timestamp
                if ts_str.endswith("Z"):
                    ts_str = ts_str[:-1] + "+00:00"
                try:
                    event_dt = datetime.fromisoformat(ts_str)
                except:
                    continue
                
                if event_dt < today_start:
                    continue
                
                event_type = event.get("event", "")
                if event_type == "decision":
                    decisions.append(event)
                elif event_type == "skip":
                    skips.append(event)
                elif event_type == "trade" and event.get("action") == "BUY":
                    trades_buy.append(event)
                elif event_type == "cycle":
                    cycles.append(event)
            except Exception as e:
                continue
except Exception as e:
    print_out(f"ERROR: {e}")
    sys.exit(1)

print_out(f"📊 СТАТИСТИКА СОБЫТИЙ:")
print_out(f"   - Решений (decision): {len(decisions)}")
print_out(f"   - Пропусков (skip): {len(skips)}")
print_out(f"   - Покупок (trade BUY): {len(trades_buy)}")
print_out(f"   - Циклов (cycle): {len(cycles)}")
print_out("")

# Анализ решений с BUY сигналами
buy_decisions = []
for d in decisions:
    details = d.get("details", {})
    if details.get("strategy_should_buy") == True:
        buy_decisions.append(d)

print_out("-" * 100)
print_out("АНАЛИЗ РЕШЕНИЙ С СИГНАЛАМИ BUY (но не куплено)")
print_out("-" * 100)
print_out(f"Найдено решений с сигналом BUY от стратегии: {len(buy_decisions)}")
print_out("")

if len(buy_decisions) == 0:
    print_out("⚠️  ВНИМАНИЕ: Стратегия НЕ генерировала сигналы BUY за сегодня!")
    print_out("   Это означает, что стратегия считает, что условия для покупки не подходят.")
    print_out("")
    
    # Анализируем почему нет сигналов
    symbols_analyzed = set()
    for d in decisions:
        sym = d.get("symbol", "")
        if sym:
            symbols_analyzed.add(sym)
    
    print_out(f"Символов проанализировано: {len(symbols_analyzed)}")
    print_out("")
    
    # Статистика по сигналам
    signal_stats = defaultdict(int)
    for d in decisions:
        details = d.get("details", {})
        should_buy = details.get("strategy_should_buy", False)
        should_sell = details.get("strategy_should_sell", False)
        if should_buy:
            signal_stats["buy"] += 1
        elif should_sell:
            signal_stats["sell"] += 1
        else:
            signal_stats["hold"] += 1
    
    print_out("Распределение сигналов стратегии:")
    print_out(f"   BUY: {signal_stats['buy']}")
    print_out(f"   SELL: {signal_stats['sell']}")
    print_out(f"   HOLD: {signal_stats['hold']}")
    print_out("")
    
    # Анализ confidence
    confidences = [float(d.get("confidence", 0) or 0) for d in decisions if d.get("confidence")]
    if confidences:
        avg_conf = sum(confidences) / len(confidences)
        max_conf = max(confidences)
        min_conf = min(confidences)
        print_out(f"Статистика confidence:")
        print_out(f"   Средний: {avg_conf:.3f}")
        print_out(f"   Максимум: {max_conf:.3f}")
        print_out(f"   Минимум: {min_conf:.3f}")
        print_out("")
else:
    # Группируем по символам
    buy_by_symbol = defaultdict(list)
    for bd in buy_decisions:
        sym = bd.get("symbol", "")
        if sym:
            buy_by_symbol[sym].append(bd)
    
    print_out(f"Символов с сигналами BUY: {len(buy_by_symbol)}")
    print_out("")
    
    for symbol, events in sorted(buy_by_symbol.items()):
        latest = events[-1]
        conf = float(latest.get("confidence", 0) or 0)
        rsi = latest.get("rsi")
        trend = latest.get("trend", "")
        price = latest.get("price")
        ts = latest.get("ts_utc", "")
        print_out(f"📈 {symbol}: confidence={conf:.3f}, RSI={rsi}, trend={trend}, price={price}, time={ts}")

print_out("")

# Анализ пропусков
print_out("-" * 100)
print_out("АНАЛИЗ ПРИЧИН ПРОПУСКА ПОКУПОК (skip events)")
print_out("-" * 100)

skip_reasons = defaultdict(int)
skip_by_reason = defaultdict(list)

for skip in skips:
    reason = skip.get("skip_reason", "unknown")
    skip_reasons[reason] += 1
    skip_by_reason[reason].append(skip)

if skip_reasons:
    print_out("Причины пропуска (по частоте):")
    for reason, count in sorted(skip_reasons.items(), key=lambda x: -x[1]):
        print_out(f"   {reason}: {count} раз(а)")
    print_out("")
    
    # Детальный анализ
    for reason, events in sorted(skip_by_reason.items(), key=lambda x: -len(x[1])):
        print_out(f"📋 {reason} ({len(events)} раз):")
        
        symbols = defaultdict(int)
        confidences = []
        for ev in events:
            sym = ev.get("symbol", "")
            if sym:
                symbols[sym] += 1
            conf = float(ev.get("confidence", 0) or 0)
            if conf > 0:
                confidences.append(conf)
        
        if symbols:
            print_out(f"   Затронутые символы: {', '.join(sorted(symbols.keys())[:10])}")
        if confidences:
            avg_conf = sum(confidences) / len(confidences)
            print_out(f"   Средний confidence: {avg_conf:.3f}")
        print_out("")
else:
    print_out("⚠️  Нет событий пропуска (skip) - возможно, проблема в стратегии.")
    print_out("")

# Рекомендации
print_out("-" * 100)
print_out("РЕКОМЕНДАЦИИ ПО ИСПРАВЛЕНИЮ")
print_out("-" * 100)

recommendations = []

if len(buy_decisions) == 0:
    recommendations.append("⚠️  Стратегия не генерирует сигналы BUY. Возможные причины:")
    recommendations.append("   1. Рынок в боковом/медвежьем тренде")
    recommendations.append("   2. Фильтры стратегии слишком строгие (RSI, MACD, trend)")
    recommendations.append("   3. Все символы не проходят проверки стратегии")
    recommendations.append("   Рекомендация: проверить логику стратегии или снизить пороги")

if skip_reasons.get("rsi_too_high_for_buy", 0) > 0:
    count = skip_reasons["rsi_too_high_for_buy"]
    recommendations.append(f"🔧 RSI_MAX_BUY слишком строгий ({count} пропусков). Рекомендация: увеличить до 68-70")

if skip_reasons.get("low_macd_hist_atr_ratio", 0) > 0:
    count = skip_reasons["low_macd_hist_atr_ratio"]
    recommendations.append(f"🔧 MIN_MACD_HIST_ATR_RATIO_BUY слишком строгий ({count} пропусков). Рекомендация: снизить до -0.15")

if skip_reasons.get("low_confidence", 0) > 0:
    count = skip_reasons["low_confidence"]
    recommendations.append(f"🔧 MIN_CONF_BUY слишком высокий ({count} пропусков). Рекомендация: снизить до 0.55-0.58")

if len(trades_buy) == 0:
    recommendations.append("💰 Нет покупок за сегодня. Проверьте:")
    recommendations.append("   1. ENABLE_TRADING=true в конфигурации")
    recommendations.append("   2. allow_entries=true (не заблокировано через Telegram)")
    recommendations.append("   3. Достаточно cash на счете")
    recommendations.append("   4. Не достигнут лимит MAX_OPEN_POSITIONS")

if not recommendations:
    recommendations.append("✓ Не найдено очевидных проблем.")

for i, rec in enumerate(recommendations, 1):
    print_out(f"{i}. {rec}")

print_out("")
print_out("=" * 100)

# Сохраняем в файл
try:
    with open("analysis_today_report.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    print_out("\n✓ Отчет сохранен в analysis_today_report.txt")
except Exception as e:
    print_out(f"\n⚠️  Не удалось сохранить отчет: {e}")





