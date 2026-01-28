#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Комплексный анализ решений бота о покупке за сегодняшний день

Анализирует:
1. Сколько решений "не покупать" было за день
2. Сколько из них обоснованные
3. Сколько решений об отказе покупки были убыточными (упущенные возможности)
4. Причины отказов и рекомендации по исправлению
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

# Настройка кодировки
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

audit_path = "audit_logs/trades_audit.jsonl"

def parse_timestamp(ts_str: str) -> Optional[datetime]:
    """Парсит timestamp из строки"""
    try:
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"
        return datetime.fromisoformat(ts_str)
    except Exception:
        return None

def get_today_start_utc() -> datetime:
    """Получает начало сегодняшнего дня в UTC"""
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)

def analyze_buy_decisions():
    """Полный анализ решений о покупке за сегодня"""
    
    print("=" * 100)
    print("КОМПЛЕКСНЫЙ АНАЛИЗ РЕШЕНИЙ БОТА О ПОКУПКЕ ЗА СЕГОДНЯШНИЙ ДЕНЬ")
    print("=" * 100)
    print()
    
    today_start = get_today_start_utc()
    print(f"Период анализа: с {today_start.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"Текущее время: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print()
    
    # Читаем события
    decisions = []
    skips = []
    trades_buy = []
    cycles = []
    market_data = []
    
    try:
        with open(audit_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    event = json.loads(line.strip())
                    ts_str = event.get("ts_utc", "")
                    if not ts_str:
                        continue
                    
                    event_dt = parse_timestamp(ts_str)
                    if not event_dt or event_dt < today_start:
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
                    elif event_type == "market":
                        market_data.append(event)
                except Exception as e:
                    continue
    except FileNotFoundError:
        print(f"❌ ERROR: Файл не найден: {audit_path}")
        return
    except Exception as e:
        print(f"❌ ERROR: Ошибка чтения файла: {e}")
        return
    
    print(f"📊 СТАТИСТИКА СОБЫТИЙ:")
    print(f"   - Решений (decision): {len(decisions)}")
    print(f"   - Пропусков (skip): {len(skips)}")
    print(f"   - Покупок (trade BUY): {len(trades_buy)}")
    print(f"   - Циклов (cycle): {len(cycles)}")
    print(f"   - Рыночных данных (market): {len(market_data)}")
    print()
    
    # 1. АНАЛИЗ РЕШЕНИЙ С СИГНАЛАМИ BUY (но не куплено)
    print("-" * 100)
    print("1. АНАЛИЗ РЕШЕНИЙ С СИГНАЛАМИ BUY (но не куплено)")
    print("-" * 100)
    
    buy_decisions = []
    for d in decisions:
        details = d.get("details", {})
        signal = d.get("signal", "")
        if signal == "buy" or details.get("strategy_should_buy") == True:
            buy_decisions.append(d)
    
    print(f"Найдено решений с сигналом BUY: {len(buy_decisions)}")
    print()
    
    if len(buy_decisions) == 0:
        print("⚠️  ВНИМАНИЕ: Стратегия НЕ генерировала сигналы BUY за сегодня!")
        print("   Все решения имеют signal='hold' или strategy_should_buy=false")
        print()
    else:
        # Группируем по символам
        buy_by_symbol = defaultdict(list)
        for bd in buy_decisions:
            sym = bd.get("symbol", "")
            if sym:
                buy_by_symbol[sym].append(bd)
        
        print(f"Символов с сигналами BUY: {len(buy_by_symbol)}")
        print()
        
        for symbol, events in sorted(buy_by_symbol.items()):
            latest = events[-1]
            signal = latest.get("signal", "")
            conf = float(latest.get("confidence", 0) or 0)
            rsi = latest.get("rsi")
            trend = latest.get("trend", "")
            macd_hist = latest.get("macd_hist")
            price = latest.get("price")
            buy_signals = latest.get("buy_signals", 0)
            strategy_should_buy = latest.get("details", {}).get("strategy_should_buy", False)
            ts = latest.get("ts_utc", "")
            
            print(f"📈 {symbol}:")
            print(f"   Время: {ts}")
            print(f"   Signal: {signal}")
            print(f"   Strategy should_buy: {strategy_should_buy}")
            print(f"   Confidence: {conf:.3f}")
            print(f"   Buy signals: {buy_signals}")
            print(f"   RSI: {rsi}")
            print(f"   Trend: {trend}")
            print(f"   MACD_hist: {macd_hist}")
            print(f"   Цена: {price}")
            print(f"   Количество событий: {len(events)}")
            print()
    
    # 2. АНАЛИЗ ПРИЧИН ПРОПУСКА
    print("-" * 100)
    print("2. АНАЛИЗ ПРИЧИН ПРОПУСКА ПОКУПОК (skip events)")
    print("-" * 100)
    
    skip_reasons = defaultdict(int)
    skip_by_reason = defaultdict(list)
    
    for skip in skips:
        reason = skip.get("skip_reason", "unknown")
        skip_reasons[reason] += 1
        skip_by_reason[reason].append(skip)
    
    if skip_reasons:
        print("Причины пропуска (по частоте):")
        for reason, count in sorted(skip_reasons.items(), key=lambda x: -x[1]):
            print(f"   {reason}: {count} раз(а)")
        print()
        
        # Детальный анализ каждой причины
        for reason, events in sorted(skip_by_reason.items(), key=lambda x: -len(x[1])):
            print(f"📋 {reason} ({len(events)} раз):")
            
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
                print(f"   Затронутые символы: {', '.join(sorted(symbols.keys())[:10])}")
            if confidences:
                avg_conf = sum(confidences) / len(confidences)
                print(f"   Средний confidence: {avg_conf:.3f}")
            print()
    else:
        print("⚠️  Нет событий пропуска (skip) - проблема на уровне стратегии.")
        print()
    
    # 3. АНАЛИЗ РЕШЕНИЙ "НЕ ПОКУПАТЬ"
    print("-" * 100)
    print("3. АНАЛИЗ РЕШЕНИЙ 'НЕ ПОКУПАТЬ'")
    print("-" * 100)
    
    no_buy_decisions = []
    for d in decisions:
        details = d.get("details", {})
        if details.get("strategy_should_buy") == False:
            no_buy_decisions.append(d)
    
    print(f"Всего решений 'не покупать': {len(no_buy_decisions)}")
    print()
    
    # Анализ причин отказа
    refusal_reasons = defaultdict(int)
    refusal_by_reason = defaultdict(list)
    
    for d in no_buy_decisions:
        signal = d.get("signal", "")
        rsi = d.get("rsi")
        trend = d.get("trend", "")
        macd_hist = d.get("macd_hist")
        conf = float(d.get("confidence", 0) or 0)
        
        # Определяем причину отказа
        reason = "unknown"
        if signal == "sell":
            reason = "signal_sell"
        elif signal == "hold":
            if rsi is not None:
                if float(rsi) > 68:
                    reason = "rsi_too_high"
                elif float(rsi) < 30:
                    reason = "rsi_oversold_but_blocked"
            if trend == "sideways" and macd_hist is not None and float(macd_hist) < 0:
                reason = "sideways_negative_macd"
            elif trend == "down":
                reason = "trend_down"
            elif macd_hist is not None and float(macd_hist) < 0:
                reason = "negative_macd_hist"
            elif conf < 0.6:
                reason = "low_confidence"
            else:
                reason = "hold_no_reason"
        
        refusal_reasons[reason] += 1
        refusal_by_reason[reason].append(d)
    
    print("Причины отказа от покупки:")
    for reason, count in sorted(refusal_reasons.items(), key=lambda x: -x[1]):
        print(f"   {reason}: {count} раз(а)")
    print()
    
    # 4. АНАЛИЗ УПУЩЕННЫХ ВОЗМОЖНОСТЕЙ
    print("-" * 100)
    print("4. АНАЛИЗ УПУЩЕННЫХ ВОЗМОЖНОСТЕЙ (была бы прибыль)")
    print("-" * 100)
    
    missed_opportunities = []
    
    # Для каждого решения с хорошим сигналом проверяем последующие цены
    potential_buys = []
    for d in decisions:
        signal = d.get("signal", "")
        conf = float(d.get("confidence", 0) or 0)
        buy_signals = d.get("buy_signals", 0)
        rsi = d.get("rsi")
        
        # Критерии потенциально хорошей покупки
        if (signal == "buy" or 
            (conf > 0.7) or 
            (buy_signals >= 3) or 
            (rsi is not None and float(rsi) < 35 and conf > 0.5)):
            potential_buys.append(d)
    
    print(f"Найдено потенциально хороших сигналов: {len(potential_buys)}")
    print()
    
    # Проверяем упущенные возможности
    for pb in potential_buys:
        symbol = pb.get("symbol", "")
        decision_price = pb.get("price")
        decision_time = parse_timestamp(pb.get("ts_utc", ""))
        
        if not symbol or not decision_price or not decision_time:
            continue
        
        # Ищем последующие цены
        future_prices = []
        for md in market_data:
            if md.get("symbol") == symbol:
                md_time = parse_timestamp(md.get("ts_utc", ""))
                if md_time and md_time > decision_time:
                    price = md.get("price")
                    if price:
                        future_prices.append((md_time, price))
        
        # Также ищем в последующих решениях
        for d in decisions:
            if d.get("symbol") == symbol:
                d_time = parse_timestamp(d.get("ts_utc", ""))
                if d_time and d_time > decision_time:
                    price = d.get("price")
                    if price:
                        future_prices.append((d_time, price))
        
        if future_prices:
            # Берем последнюю цену
            latest_time, latest_price = max(future_prices, key=lambda x: x[0])
            price_change_pct = ((latest_price - decision_price) / decision_price) * 100
            
            if price_change_pct > 0:
                # Была бы прибыль
                missed_opportunities.append({
                    "symbol": symbol,
                    "decision_time": decision_time,
                    "decision_price": decision_price,
                    "current_price": latest_price,
                    "price_change_pct": price_change_pct,
                    "confidence": float(pb.get("confidence", 0) or 0),
                    "buy_signals": pb.get("buy_signals", 0),
                    "rsi": pb.get("rsi"),
                    "trend": pb.get("trend", ""),
                    "strategy_should_buy": pb.get("details", {}).get("strategy_should_buy", False),
                })
    
    if missed_opportunities:
        print(f"⚠️  Найдено {len(missed_opportunities)} упущенных возможностей:")
        print()
        
        # Сортируем по упущенной прибыли
        missed_opportunities.sort(key=lambda x: -x["price_change_pct"])
        
        for mo in missed_opportunities:
            print(f"💰 {mo['symbol']}:")
            print(f"   Время: {mo['decision_time'].strftime('%Y-%m-%d %H:%M:%S')} UTC")
            print(f"   Цена решения: {mo['decision_price']:.2f}")
            print(f"   Текущая цена: {mo['current_price']:.2f}")
            print(f"   Упущенная прибыль: +{mo['price_change_pct']:.2f}%")
            print(f"   Confidence: {mo['confidence']:.3f}")
            print(f"   Buy signals: {mo['buy_signals']}")
            print(f"   RSI: {mo['rsi']}")
            print(f"   Trend: {mo['trend']}")
            print(f"   Strategy should_buy: {mo['strategy_should_buy']}")
            print()
        
        # Статистика
        total_missed = sum(mo["price_change_pct"] for mo in missed_opportunities)
        avg_missed = total_missed / len(missed_opportunities)
        max_missed = max(mo["price_change_pct"] for mo in missed_opportunities)
        
        print(f"📊 Статистика упущенной прибыли:")
        print(f"   Всего возможностей: {len(missed_opportunities)}")
        print(f"   Средняя упущенная прибыль: {avg_missed:.2f}%")
        print(f"   Максимальная упущенная прибыль: {max_missed:.2f}%")
        print()
    else:
        print("✓ Не найдено упущенных возможностей (или нет данных о последующих ценах)")
        print()
    
    # 5. РЕКОМЕНДАЦИИ
    print("-" * 100)
    print("5. РЕКОМЕНДАЦИИ ПО ИСПРАВЛЕНИЮ")
    print("-" * 100)
    
    recommendations = []
    
    # Анализ на основе данных
    if len(buy_decisions) == 0:
        recommendations.append(
            "⚠️  КРИТИЧНО: Стратегия не генерирует сигналы BUY. "
            "Проверьте логику should_buy() в trading_strategy.py"
        )
    
    # Проверяем случаи с высоким confidence, но strategy_should_buy=false
    high_conf_blocked = [d for d in decisions 
                        if float(d.get("confidence", 0) or 0) > 0.7 
                        and d.get("details", {}).get("strategy_should_buy") == False]
    
    if high_conf_blocked:
        recommendations.append(
            f"🔧 Найдено {len(high_conf_blocked)} решений с высоким confidence (>0.7), "
            "но strategy_should_buy=false. Проверьте фильтры в should_buy()"
        )
    
    # Анализ пропусков
    if skip_reasons.get("rsi_too_high_for_buy", 0) > 0:
        count = skip_reasons["rsi_too_high_for_buy"]
        recommendations.append(
            f"🔧 RSI_MAX_BUY слишком строгий ({count} пропусков). "
            "Рекомендация: увеличить до 70-72"
        )
    
    if skip_reasons.get("low_macd_hist_atr_ratio", 0) > 0:
        count = skip_reasons["low_macd_hist_atr_ratio"]
        recommendations.append(
            f"🔧 MIN_MACD_HIST_ATR_RATIO_BUY слишком строгий ({count} пропусков). "
            "Рекомендация: снизить до -0.15 или -0.2"
        )
    
    if skip_reasons.get("sideways_negative_macd", 0) > 0:
        count = skip_reasons["sideways_negative_macd"]
        recommendations.append(
            f"🔧 BLOCK_SIDEWAYS_NEGATIVE_MACD блокирует покупки ({count} пропусков). "
            "Рекомендация: разрешить при RSI < 30 или confidence > 0.8"
        )
    
    # Анализ упущенных возможностей
    if missed_opportunities:
        avg_missed = sum(mo["price_change_pct"] for mo in missed_opportunities) / len(missed_opportunities)
        recommendations.append(
            f"💰 Найдено {len(missed_opportunities)} упущенных возможностей "
            f"со средней прибылью {avg_missed:.2f}%. "
            "Рекомендация: ослабить фильтры, которые блокируют эти покупки"
        )
    
    # Анализ причин отказа
    if refusal_reasons.get("sideways_negative_macd", 0) > 0:
        count = refusal_reasons["sideways_negative_macd"]
        recommendations.append(
            f"🔧 Фильтр 'sideways + negative MACD' блокирует {count} решений. "
            "Рекомендация: разрешить при сильной перепроданности (RSI < 30)"
        )
    
    if refusal_reasons.get("rsi_oversold_but_blocked", 0) > 0:
        count = refusal_reasons["rsi_oversold_but_blocked"]
        recommendations.append(
            f"🔧 Найдено {count} случаев с RSI < 30, но покупка заблокирована. "
            "Рекомендация: разрешить покупки при сильной перепроданности независимо от других фильтров"
        )
    
    if not recommendations:
        recommendations.append("✓ Не найдено очевидных проблем.")
    
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec}")
    
    print()
    print("=" * 100)
    
    # Сохраняем отчет
    try:
        with open("analysis_report_today.txt", "w", encoding="utf-8") as f:
            f.write("=" * 100 + "\n")
            f.write("ОТЧЕТ АНАЛИЗА РЕШЕНИЙ БОТА ЗА СЕГОДНЯ\n")
            f.write("=" * 100 + "\n\n")
            f.write(f"Период: {today_start.strftime('%Y-%m-%d')}\n")
            f.write(f"Решений: {len(decisions)}\n")
            f.write(f"Пропусков: {len(skips)}\n")
            f.write(f"Покупок: {len(trades_buy)}\n")
            f.write(f"Упущенных возможностей: {len(missed_opportunities)}\n")
            if missed_opportunities:
                avg = sum(mo["price_change_pct"] for mo in missed_opportunities) / len(missed_opportunities)
                f.write(f"Средняя упущенная прибыль: {avg:.2f}%\n")
        print("✓ Отчет сохранен в analysis_report_today.txt")
    except Exception as e:
        print(f"⚠️  Не удалось сохранить отчет: {e}")

if __name__ == "__main__":
    try:
        analyze_buy_decisions()
    except Exception as e:
        print(f"❌ ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

# -*- coding: utf-8 -*-
"""
Комплексный анализ решений бота о покупке за сегодняшний день

Анализирует:
1. Сколько решений "не покупать" было за день
2. Сколько из них обоснованные
3. Сколько решений об отказе покупки были убыточными (упущенные возможности)
4. Причины отказов и рекомендации по исправлению
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

# Настройка кодировки
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

audit_path = "audit_logs/trades_audit.jsonl"

def parse_timestamp(ts_str: str) -> Optional[datetime]:
    """Парсит timestamp из строки"""
    try:
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"
        return datetime.fromisoformat(ts_str)
    except Exception:
        return None

def get_today_start_utc() -> datetime:
    """Получает начало сегодняшнего дня в UTC"""
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)

def analyze_buy_decisions():
    """Полный анализ решений о покупке за сегодня"""
    
    print("=" * 100)
    print("КОМПЛЕКСНЫЙ АНАЛИЗ РЕШЕНИЙ БОТА О ПОКУПКЕ ЗА СЕГОДНЯШНИЙ ДЕНЬ")
    print("=" * 100)
    print()
    
    today_start = get_today_start_utc()
    print(f"Период анализа: с {today_start.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"Текущее время: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print()
    
    # Читаем события
    decisions = []
    skips = []
    trades_buy = []
    cycles = []
    market_data = []
    
    try:
        with open(audit_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    event = json.loads(line.strip())
                    ts_str = event.get("ts_utc", "")
                    if not ts_str:
                        continue
                    
                    event_dt = parse_timestamp(ts_str)
                    if not event_dt or event_dt < today_start:
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
                    elif event_type == "market":
                        market_data.append(event)
                except Exception as e:
                    continue
    except FileNotFoundError:
        print(f"❌ ERROR: Файл не найден: {audit_path}")
        return
    except Exception as e:
        print(f"❌ ERROR: Ошибка чтения файла: {e}")
        return
    
    print(f"📊 СТАТИСТИКА СОБЫТИЙ:")
    print(f"   - Решений (decision): {len(decisions)}")
    print(f"   - Пропусков (skip): {len(skips)}")
    print(f"   - Покупок (trade BUY): {len(trades_buy)}")
    print(f"   - Циклов (cycle): {len(cycles)}")
    print(f"   - Рыночных данных (market): {len(market_data)}")
    print()
    
    # 1. АНАЛИЗ РЕШЕНИЙ С СИГНАЛАМИ BUY (но не куплено)
    print("-" * 100)
    print("1. АНАЛИЗ РЕШЕНИЙ С СИГНАЛАМИ BUY (но не куплено)")
    print("-" * 100)
    
    buy_decisions = []
    for d in decisions:
        details = d.get("details", {})
        signal = d.get("signal", "")
        if signal == "buy" or details.get("strategy_should_buy") == True:
            buy_decisions.append(d)
    
    print(f"Найдено решений с сигналом BUY: {len(buy_decisions)}")
    print()
    
    if len(buy_decisions) == 0:
        print("⚠️  ВНИМАНИЕ: Стратегия НЕ генерировала сигналы BUY за сегодня!")
        print("   Все решения имеют signal='hold' или strategy_should_buy=false")
        print()
    else:
        # Группируем по символам
        buy_by_symbol = defaultdict(list)
        for bd in buy_decisions:
            sym = bd.get("symbol", "")
            if sym:
                buy_by_symbol[sym].append(bd)
        
        print(f"Символов с сигналами BUY: {len(buy_by_symbol)}")
        print()
        
        for symbol, events in sorted(buy_by_symbol.items()):
            latest = events[-1]
            signal = latest.get("signal", "")
            conf = float(latest.get("confidence", 0) or 0)
            rsi = latest.get("rsi")
            trend = latest.get("trend", "")
            macd_hist = latest.get("macd_hist")
            price = latest.get("price")
            buy_signals = latest.get("buy_signals", 0)
            strategy_should_buy = latest.get("details", {}).get("strategy_should_buy", False)
            ts = latest.get("ts_utc", "")
            
            print(f"📈 {symbol}:")
            print(f"   Время: {ts}")
            print(f"   Signal: {signal}")
            print(f"   Strategy should_buy: {strategy_should_buy}")
            print(f"   Confidence: {conf:.3f}")
            print(f"   Buy signals: {buy_signals}")
            print(f"   RSI: {rsi}")
            print(f"   Trend: {trend}")
            print(f"   MACD_hist: {macd_hist}")
            print(f"   Цена: {price}")
            print(f"   Количество событий: {len(events)}")
            print()
    
    # 2. АНАЛИЗ ПРИЧИН ПРОПУСКА
    print("-" * 100)
    print("2. АНАЛИЗ ПРИЧИН ПРОПУСКА ПОКУПОК (skip events)")
    print("-" * 100)
    
    skip_reasons = defaultdict(int)
    skip_by_reason = defaultdict(list)
    
    for skip in skips:
        reason = skip.get("skip_reason", "unknown")
        skip_reasons[reason] += 1
        skip_by_reason[reason].append(skip)
    
    if skip_reasons:
        print("Причины пропуска (по частоте):")
        for reason, count in sorted(skip_reasons.items(), key=lambda x: -x[1]):
            print(f"   {reason}: {count} раз(а)")
        print()
        
        # Детальный анализ каждой причины
        for reason, events in sorted(skip_by_reason.items(), key=lambda x: -len(x[1])):
            print(f"📋 {reason} ({len(events)} раз):")
            
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
                print(f"   Затронутые символы: {', '.join(sorted(symbols.keys())[:10])}")
            if confidences:
                avg_conf = sum(confidences) / len(confidences)
                print(f"   Средний confidence: {avg_conf:.3f}")
            print()
    else:
        print("⚠️  Нет событий пропуска (skip) - проблема на уровне стратегии.")
        print()
    
    # 3. АНАЛИЗ РЕШЕНИЙ "НЕ ПОКУПАТЬ"
    print("-" * 100)
    print("3. АНАЛИЗ РЕШЕНИЙ 'НЕ ПОКУПАТЬ'")
    print("-" * 100)
    
    no_buy_decisions = []
    for d in decisions:
        details = d.get("details", {})
        if details.get("strategy_should_buy") == False:
            no_buy_decisions.append(d)
    
    print(f"Всего решений 'не покупать': {len(no_buy_decisions)}")
    print()
    
    # Анализ причин отказа
    refusal_reasons = defaultdict(int)
    refusal_by_reason = defaultdict(list)
    
    for d in no_buy_decisions:
        signal = d.get("signal", "")
        rsi = d.get("rsi")
        trend = d.get("trend", "")
        macd_hist = d.get("macd_hist")
        conf = float(d.get("confidence", 0) or 0)
        
        # Определяем причину отказа
        reason = "unknown"
        if signal == "sell":
            reason = "signal_sell"
        elif signal == "hold":
            if rsi is not None:
                if float(rsi) > 68:
                    reason = "rsi_too_high"
                elif float(rsi) < 30:
                    reason = "rsi_oversold_but_blocked"
            if trend == "sideways" and macd_hist is not None and float(macd_hist) < 0:
                reason = "sideways_negative_macd"
            elif trend == "down":
                reason = "trend_down"
            elif macd_hist is not None and float(macd_hist) < 0:
                reason = "negative_macd_hist"
            elif conf < 0.6:
                reason = "low_confidence"
            else:
                reason = "hold_no_reason"
        
        refusal_reasons[reason] += 1
        refusal_by_reason[reason].append(d)
    
    print("Причины отказа от покупки:")
    for reason, count in sorted(refusal_reasons.items(), key=lambda x: -x[1]):
        print(f"   {reason}: {count} раз(а)")
    print()
    
    # 4. АНАЛИЗ УПУЩЕННЫХ ВОЗМОЖНОСТЕЙ
    print("-" * 100)
    print("4. АНАЛИЗ УПУЩЕННЫХ ВОЗМОЖНОСТЕЙ (была бы прибыль)")
    print("-" * 100)
    
    missed_opportunities = []
    
    # Для каждого решения с хорошим сигналом проверяем последующие цены
    potential_buys = []
    for d in decisions:
        signal = d.get("signal", "")
        conf = float(d.get("confidence", 0) or 0)
        buy_signals = d.get("buy_signals", 0)
        rsi = d.get("rsi")
        
        # Критерии потенциально хорошей покупки
        if (signal == "buy" or 
            (conf > 0.7) or 
            (buy_signals >= 3) or 
            (rsi is not None and float(rsi) < 35 and conf > 0.5)):
            potential_buys.append(d)
    
    print(f"Найдено потенциально хороших сигналов: {len(potential_buys)}")
    print()
    
    # Проверяем упущенные возможности
    for pb in potential_buys:
        symbol = pb.get("symbol", "")
        decision_price = pb.get("price")
        decision_time = parse_timestamp(pb.get("ts_utc", ""))
        
        if not symbol or not decision_price or not decision_time:
            continue
        
        # Ищем последующие цены
        future_prices = []
        for md in market_data:
            if md.get("symbol") == symbol:
                md_time = parse_timestamp(md.get("ts_utc", ""))
                if md_time and md_time > decision_time:
                    price = md.get("price")
                    if price:
                        future_prices.append((md_time, price))
        
        # Также ищем в последующих решениях
        for d in decisions:
            if d.get("symbol") == symbol:
                d_time = parse_timestamp(d.get("ts_utc", ""))
                if d_time and d_time > decision_time:
                    price = d.get("price")
                    if price:
                        future_prices.append((d_time, price))
        
        if future_prices:
            # Берем последнюю цену
            latest_time, latest_price = max(future_prices, key=lambda x: x[0])
            price_change_pct = ((latest_price - decision_price) / decision_price) * 100
            
            if price_change_pct > 0:
                # Была бы прибыль
                missed_opportunities.append({
                    "symbol": symbol,
                    "decision_time": decision_time,
                    "decision_price": decision_price,
                    "current_price": latest_price,
                    "price_change_pct": price_change_pct,
                    "confidence": float(pb.get("confidence", 0) or 0),
                    "buy_signals": pb.get("buy_signals", 0),
                    "rsi": pb.get("rsi"),
                    "trend": pb.get("trend", ""),
                    "strategy_should_buy": pb.get("details", {}).get("strategy_should_buy", False),
                })
    
    if missed_opportunities:
        print(f"⚠️  Найдено {len(missed_opportunities)} упущенных возможностей:")
        print()
        
        # Сортируем по упущенной прибыли
        missed_opportunities.sort(key=lambda x: -x["price_change_pct"])
        
        for mo in missed_opportunities:
            print(f"💰 {mo['symbol']}:")
            print(f"   Время: {mo['decision_time'].strftime('%Y-%m-%d %H:%M:%S')} UTC")
            print(f"   Цена решения: {mo['decision_price']:.2f}")
            print(f"   Текущая цена: {mo['current_price']:.2f}")
            print(f"   Упущенная прибыль: +{mo['price_change_pct']:.2f}%")
            print(f"   Confidence: {mo['confidence']:.3f}")
            print(f"   Buy signals: {mo['buy_signals']}")
            print(f"   RSI: {mo['rsi']}")
            print(f"   Trend: {mo['trend']}")
            print(f"   Strategy should_buy: {mo['strategy_should_buy']}")
            print()
        
        # Статистика
        total_missed = sum(mo["price_change_pct"] for mo in missed_opportunities)
        avg_missed = total_missed / len(missed_opportunities)
        max_missed = max(mo["price_change_pct"] for mo in missed_opportunities)
        
        print(f"📊 Статистика упущенной прибыли:")
        print(f"   Всего возможностей: {len(missed_opportunities)}")
        print(f"   Средняя упущенная прибыль: {avg_missed:.2f}%")
        print(f"   Максимальная упущенная прибыль: {max_missed:.2f}%")
        print()
    else:
        print("✓ Не найдено упущенных возможностей (или нет данных о последующих ценах)")
        print()
    
    # 5. РЕКОМЕНДАЦИИ
    print("-" * 100)
    print("5. РЕКОМЕНДАЦИИ ПО ИСПРАВЛЕНИЮ")
    print("-" * 100)
    
    recommendations = []
    
    # Анализ на основе данных
    if len(buy_decisions) == 0:
        recommendations.append(
            "⚠️  КРИТИЧНО: Стратегия не генерирует сигналы BUY. "
            "Проверьте логику should_buy() в trading_strategy.py"
        )
    
    # Проверяем случаи с высоким confidence, но strategy_should_buy=false
    high_conf_blocked = [d for d in decisions 
                        if float(d.get("confidence", 0) or 0) > 0.7 
                        and d.get("details", {}).get("strategy_should_buy") == False]
    
    if high_conf_blocked:
        recommendations.append(
            f"🔧 Найдено {len(high_conf_blocked)} решений с высоким confidence (>0.7), "
            "но strategy_should_buy=false. Проверьте фильтры в should_buy()"
        )
    
    # Анализ пропусков
    if skip_reasons.get("rsi_too_high_for_buy", 0) > 0:
        count = skip_reasons["rsi_too_high_for_buy"]
        recommendations.append(
            f"🔧 RSI_MAX_BUY слишком строгий ({count} пропусков). "
            "Рекомендация: увеличить до 70-72"
        )
    
    if skip_reasons.get("low_macd_hist_atr_ratio", 0) > 0:
        count = skip_reasons["low_macd_hist_atr_ratio"]
        recommendations.append(
            f"🔧 MIN_MACD_HIST_ATR_RATIO_BUY слишком строгий ({count} пропусков). "
            "Рекомендация: снизить до -0.15 или -0.2"
        )
    
    if skip_reasons.get("sideways_negative_macd", 0) > 0:
        count = skip_reasons["sideways_negative_macd"]
        recommendations.append(
            f"🔧 BLOCK_SIDEWAYS_NEGATIVE_MACD блокирует покупки ({count} пропусков). "
            "Рекомендация: разрешить при RSI < 30 или confidence > 0.8"
        )
    
    # Анализ упущенных возможностей
    if missed_opportunities:
        avg_missed = sum(mo["price_change_pct"] for mo in missed_opportunities) / len(missed_opportunities)
        recommendations.append(
            f"💰 Найдено {len(missed_opportunities)} упущенных возможностей "
            f"со средней прибылью {avg_missed:.2f}%. "
            "Рекомендация: ослабить фильтры, которые блокируют эти покупки"
        )
    
    # Анализ причин отказа
    if refusal_reasons.get("sideways_negative_macd", 0) > 0:
        count = refusal_reasons["sideways_negative_macd"]
        recommendations.append(
            f"🔧 Фильтр 'sideways + negative MACD' блокирует {count} решений. "
            "Рекомендация: разрешить при сильной перепроданности (RSI < 30)"
        )
    
    if refusal_reasons.get("rsi_oversold_but_blocked", 0) > 0:
        count = refusal_reasons["rsi_oversold_but_blocked"]
        recommendations.append(
            f"🔧 Найдено {count} случаев с RSI < 30, но покупка заблокирована. "
            "Рекомендация: разрешить покупки при сильной перепроданности независимо от других фильтров"
        )
    
    if not recommendations:
        recommendations.append("✓ Не найдено очевидных проблем.")
    
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec}")
    
    print()
    print("=" * 100)
    
    # Сохраняем отчет
    try:
        with open("analysis_report_today.txt", "w", encoding="utf-8") as f:
            f.write("=" * 100 + "\n")
            f.write("ОТЧЕТ АНАЛИЗА РЕШЕНИЙ БОТА ЗА СЕГОДНЯ\n")
            f.write("=" * 100 + "\n\n")
            f.write(f"Период: {today_start.strftime('%Y-%m-%d')}\n")
            f.write(f"Решений: {len(decisions)}\n")
            f.write(f"Пропусков: {len(skips)}\n")
            f.write(f"Покупок: {len(trades_buy)}\n")
            f.write(f"Упущенных возможностей: {len(missed_opportunities)}\n")
            if missed_opportunities:
                avg = sum(mo["price_change_pct"] for mo in missed_opportunities) / len(missed_opportunities)
                f.write(f"Средняя упущенная прибыль: {avg:.2f}%\n")
        print("✓ Отчет сохранен в analysis_report_today.txt")
    except Exception as e:
        print(f"⚠️  Не удалось сохранить отчет: {e}")

if __name__ == "__main__":
    try:
        analyze_buy_decisions()
    except Exception as e:
        print(f"❌ ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

# -*- coding: utf-8 -*-
"""
Комплексный анализ решений бота о покупке за сегодняшний день

Анализирует:
1. Сколько решений "не покупать" было за день
2. Сколько из них обоснованные
3. Сколько решений об отказе покупки были убыточными (упущенные возможности)
4. Причины отказов и рекомендации по исправлению
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

# Настройка кодировки
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

audit_path = "audit_logs/trades_audit.jsonl"

def parse_timestamp(ts_str: str) -> Optional[datetime]:
    """Парсит timestamp из строки"""
    try:
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"
        return datetime.fromisoformat(ts_str)
    except Exception:
        return None

def get_today_start_utc() -> datetime:
    """Получает начало сегодняшнего дня в UTC"""
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)

def analyze_buy_decisions():
    """Полный анализ решений о покупке за сегодня"""
    
    print("=" * 100)
    print("КОМПЛЕКСНЫЙ АНАЛИЗ РЕШЕНИЙ БОТА О ПОКУПКЕ ЗА СЕГОДНЯШНИЙ ДЕНЬ")
    print("=" * 100)
    print()
    
    today_start = get_today_start_utc()
    print(f"Период анализа: с {today_start.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"Текущее время: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print()
    
    # Читаем события
    decisions = []
    skips = []
    trades_buy = []
    cycles = []
    market_data = []
    
    try:
        with open(audit_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    event = json.loads(line.strip())
                    ts_str = event.get("ts_utc", "")
                    if not ts_str:
                        continue
                    
                    event_dt = parse_timestamp(ts_str)
                    if not event_dt or event_dt < today_start:
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
                    elif event_type == "market":
                        market_data.append(event)
                except Exception as e:
                    continue
    except FileNotFoundError:
        print(f"❌ ERROR: Файл не найден: {audit_path}")
        return
    except Exception as e:
        print(f"❌ ERROR: Ошибка чтения файла: {e}")
        return
    
    print(f"📊 СТАТИСТИКА СОБЫТИЙ:")
    print(f"   - Решений (decision): {len(decisions)}")
    print(f"   - Пропусков (skip): {len(skips)}")
    print(f"   - Покупок (trade BUY): {len(trades_buy)}")
    print(f"   - Циклов (cycle): {len(cycles)}")
    print(f"   - Рыночных данных (market): {len(market_data)}")
    print()
    
    # 1. АНАЛИЗ РЕШЕНИЙ С СИГНАЛАМИ BUY (но не куплено)
    print("-" * 100)
    print("1. АНАЛИЗ РЕШЕНИЙ С СИГНАЛАМИ BUY (но не куплено)")
    print("-" * 100)
    
    buy_decisions = []
    for d in decisions:
        details = d.get("details", {})
        signal = d.get("signal", "")
        if signal == "buy" or details.get("strategy_should_buy") == True:
            buy_decisions.append(d)
    
    print(f"Найдено решений с сигналом BUY: {len(buy_decisions)}")
    print()
    
    if len(buy_decisions) == 0:
        print("⚠️  ВНИМАНИЕ: Стратегия НЕ генерировала сигналы BUY за сегодня!")
        print("   Все решения имеют signal='hold' или strategy_should_buy=false")
        print()
    else:
        # Группируем по символам
        buy_by_symbol = defaultdict(list)
        for bd in buy_decisions:
            sym = bd.get("symbol", "")
            if sym:
                buy_by_symbol[sym].append(bd)
        
        print(f"Символов с сигналами BUY: {len(buy_by_symbol)}")
        print()
        
        for symbol, events in sorted(buy_by_symbol.items()):
            latest = events[-1]
            signal = latest.get("signal", "")
            conf = float(latest.get("confidence", 0) or 0)
            rsi = latest.get("rsi")
            trend = latest.get("trend", "")
            macd_hist = latest.get("macd_hist")
            price = latest.get("price")
            buy_signals = latest.get("buy_signals", 0)
            strategy_should_buy = latest.get("details", {}).get("strategy_should_buy", False)
            ts = latest.get("ts_utc", "")
            
            print(f"📈 {symbol}:")
            print(f"   Время: {ts}")
            print(f"   Signal: {signal}")
            print(f"   Strategy should_buy: {strategy_should_buy}")
            print(f"   Confidence: {conf:.3f}")
            print(f"   Buy signals: {buy_signals}")
            print(f"   RSI: {rsi}")
            print(f"   Trend: {trend}")
            print(f"   MACD_hist: {macd_hist}")
            print(f"   Цена: {price}")
            print(f"   Количество событий: {len(events)}")
            print()
    
    # 2. АНАЛИЗ ПРИЧИН ПРОПУСКА
    print("-" * 100)
    print("2. АНАЛИЗ ПРИЧИН ПРОПУСКА ПОКУПОК (skip events)")
    print("-" * 100)
    
    skip_reasons = defaultdict(int)
    skip_by_reason = defaultdict(list)
    
    for skip in skips:
        reason = skip.get("skip_reason", "unknown")
        skip_reasons[reason] += 1
        skip_by_reason[reason].append(skip)
    
    if skip_reasons:
        print("Причины пропуска (по частоте):")
        for reason, count in sorted(skip_reasons.items(), key=lambda x: -x[1]):
            print(f"   {reason}: {count} раз(а)")
        print()
        
        # Детальный анализ каждой причины
        for reason, events in sorted(skip_by_reason.items(), key=lambda x: -len(x[1])):
            print(f"📋 {reason} ({len(events)} раз):")
            
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
                print(f"   Затронутые символы: {', '.join(sorted(symbols.keys())[:10])}")
            if confidences:
                avg_conf = sum(confidences) / len(confidences)
                print(f"   Средний confidence: {avg_conf:.3f}")
            print()
    else:
        print("⚠️  Нет событий пропуска (skip) - проблема на уровне стратегии.")
        print()
    
    # 3. АНАЛИЗ РЕШЕНИЙ "НЕ ПОКУПАТЬ"
    print("-" * 100)
    print("3. АНАЛИЗ РЕШЕНИЙ 'НЕ ПОКУПАТЬ'")
    print("-" * 100)
    
    no_buy_decisions = []
    for d in decisions:
        details = d.get("details", {})
        if details.get("strategy_should_buy") == False:
            no_buy_decisions.append(d)
    
    print(f"Всего решений 'не покупать': {len(no_buy_decisions)}")
    print()
    
    # Анализ причин отказа
    refusal_reasons = defaultdict(int)
    refusal_by_reason = defaultdict(list)
    
    for d in no_buy_decisions:
        signal = d.get("signal", "")
        rsi = d.get("rsi")
        trend = d.get("trend", "")
        macd_hist = d.get("macd_hist")
        conf = float(d.get("confidence", 0) or 0)
        
        # Определяем причину отказа
        reason = "unknown"
        if signal == "sell":
            reason = "signal_sell"
        elif signal == "hold":
            if rsi is not None:
                if float(rsi) > 68:
                    reason = "rsi_too_high"
                elif float(rsi) < 30:
                    reason = "rsi_oversold_but_blocked"
            if trend == "sideways" and macd_hist is not None and float(macd_hist) < 0:
                reason = "sideways_negative_macd"
            elif trend == "down":
                reason = "trend_down"
            elif macd_hist is not None and float(macd_hist) < 0:
                reason = "negative_macd_hist"
            elif conf < 0.6:
                reason = "low_confidence"
            else:
                reason = "hold_no_reason"
        
        refusal_reasons[reason] += 1
        refusal_by_reason[reason].append(d)
    
    print("Причины отказа от покупки:")
    for reason, count in sorted(refusal_reasons.items(), key=lambda x: -x[1]):
        print(f"   {reason}: {count} раз(а)")
    print()
    
    # 4. АНАЛИЗ УПУЩЕННЫХ ВОЗМОЖНОСТЕЙ
    print("-" * 100)
    print("4. АНАЛИЗ УПУЩЕННЫХ ВОЗМОЖНОСТЕЙ (была бы прибыль)")
    print("-" * 100)
    
    missed_opportunities = []
    
    # Для каждого решения с хорошим сигналом проверяем последующие цены
    potential_buys = []
    for d in decisions:
        signal = d.get("signal", "")
        conf = float(d.get("confidence", 0) or 0)
        buy_signals = d.get("buy_signals", 0)
        rsi = d.get("rsi")
        
        # Критерии потенциально хорошей покупки
        if (signal == "buy" or 
            (conf > 0.7) or 
            (buy_signals >= 3) or 
            (rsi is not None and float(rsi) < 35 and conf > 0.5)):
            potential_buys.append(d)
    
    print(f"Найдено потенциально хороших сигналов: {len(potential_buys)}")
    print()
    
    # Проверяем упущенные возможности
    for pb in potential_buys:
        symbol = pb.get("symbol", "")
        decision_price = pb.get("price")
        decision_time = parse_timestamp(pb.get("ts_utc", ""))
        
        if not symbol or not decision_price or not decision_time:
            continue
        
        # Ищем последующие цены
        future_prices = []
        for md in market_data:
            if md.get("symbol") == symbol:
                md_time = parse_timestamp(md.get("ts_utc", ""))
                if md_time and md_time > decision_time:
                    price = md.get("price")
                    if price:
                        future_prices.append((md_time, price))
        
        # Также ищем в последующих решениях
        for d in decisions:
            if d.get("symbol") == symbol:
                d_time = parse_timestamp(d.get("ts_utc", ""))
                if d_time and d_time > decision_time:
                    price = d.get("price")
                    if price:
                        future_prices.append((d_time, price))
        
        if future_prices:
            # Берем последнюю цену
            latest_time, latest_price = max(future_prices, key=lambda x: x[0])
            price_change_pct = ((latest_price - decision_price) / decision_price) * 100
            
            if price_change_pct > 0:
                # Была бы прибыль
                missed_opportunities.append({
                    "symbol": symbol,
                    "decision_time": decision_time,
                    "decision_price": decision_price,
                    "current_price": latest_price,
                    "price_change_pct": price_change_pct,
                    "confidence": float(pb.get("confidence", 0) or 0),
                    "buy_signals": pb.get("buy_signals", 0),
                    "rsi": pb.get("rsi"),
                    "trend": pb.get("trend", ""),
                    "strategy_should_buy": pb.get("details", {}).get("strategy_should_buy", False),
                })
    
    if missed_opportunities:
        print(f"⚠️  Найдено {len(missed_opportunities)} упущенных возможностей:")
        print()
        
        # Сортируем по упущенной прибыли
        missed_opportunities.sort(key=lambda x: -x["price_change_pct"])
        
        for mo in missed_opportunities:
            print(f"💰 {mo['symbol']}:")
            print(f"   Время: {mo['decision_time'].strftime('%Y-%m-%d %H:%M:%S')} UTC")
            print(f"   Цена решения: {mo['decision_price']:.2f}")
            print(f"   Текущая цена: {mo['current_price']:.2f}")
            print(f"   Упущенная прибыль: +{mo['price_change_pct']:.2f}%")
            print(f"   Confidence: {mo['confidence']:.3f}")
            print(f"   Buy signals: {mo['buy_signals']}")
            print(f"   RSI: {mo['rsi']}")
            print(f"   Trend: {mo['trend']}")
            print(f"   Strategy should_buy: {mo['strategy_should_buy']}")
            print()
        
        # Статистика
        total_missed = sum(mo["price_change_pct"] for mo in missed_opportunities)
        avg_missed = total_missed / len(missed_opportunities)
        max_missed = max(mo["price_change_pct"] for mo in missed_opportunities)
        
        print(f"📊 Статистика упущенной прибыли:")
        print(f"   Всего возможностей: {len(missed_opportunities)}")
        print(f"   Средняя упущенная прибыль: {avg_missed:.2f}%")
        print(f"   Максимальная упущенная прибыль: {max_missed:.2f}%")
        print()
    else:
        print("✓ Не найдено упущенных возможностей (или нет данных о последующих ценах)")
        print()
    
    # 5. РЕКОМЕНДАЦИИ
    print("-" * 100)
    print("5. РЕКОМЕНДАЦИИ ПО ИСПРАВЛЕНИЮ")
    print("-" * 100)
    
    recommendations = []
    
    # Анализ на основе данных
    if len(buy_decisions) == 0:
        recommendations.append(
            "⚠️  КРИТИЧНО: Стратегия не генерирует сигналы BUY. "
            "Проверьте логику should_buy() в trading_strategy.py"
        )
    
    # Проверяем случаи с высоким confidence, но strategy_should_buy=false
    high_conf_blocked = [d for d in decisions 
                        if float(d.get("confidence", 0) or 0) > 0.7 
                        and d.get("details", {}).get("strategy_should_buy") == False]
    
    if high_conf_blocked:
        recommendations.append(
            f"🔧 Найдено {len(high_conf_blocked)} решений с высоким confidence (>0.7), "
            "но strategy_should_buy=false. Проверьте фильтры в should_buy()"
        )
    
    # Анализ пропусков
    if skip_reasons.get("rsi_too_high_for_buy", 0) > 0:
        count = skip_reasons["rsi_too_high_for_buy"]
        recommendations.append(
            f"🔧 RSI_MAX_BUY слишком строгий ({count} пропусков). "
            "Рекомендация: увеличить до 70-72"
        )
    
    if skip_reasons.get("low_macd_hist_atr_ratio", 0) > 0:
        count = skip_reasons["low_macd_hist_atr_ratio"]
        recommendations.append(
            f"🔧 MIN_MACD_HIST_ATR_RATIO_BUY слишком строгий ({count} пропусков). "
            "Рекомендация: снизить до -0.15 или -0.2"
        )
    
    if skip_reasons.get("sideways_negative_macd", 0) > 0:
        count = skip_reasons["sideways_negative_macd"]
        recommendations.append(
            f"🔧 BLOCK_SIDEWAYS_NEGATIVE_MACD блокирует покупки ({count} пропусков). "
            "Рекомендация: разрешить при RSI < 30 или confidence > 0.8"
        )
    
    # Анализ упущенных возможностей
    if missed_opportunities:
        avg_missed = sum(mo["price_change_pct"] for mo in missed_opportunities) / len(missed_opportunities)
        recommendations.append(
            f"💰 Найдено {len(missed_opportunities)} упущенных возможностей "
            f"со средней прибылью {avg_missed:.2f}%. "
            "Рекомендация: ослабить фильтры, которые блокируют эти покупки"
        )
    
    # Анализ причин отказа
    if refusal_reasons.get("sideways_negative_macd", 0) > 0:
        count = refusal_reasons["sideways_negative_macd"]
        recommendations.append(
            f"🔧 Фильтр 'sideways + negative MACD' блокирует {count} решений. "
            "Рекомендация: разрешить при сильной перепроданности (RSI < 30)"
        )
    
    if refusal_reasons.get("rsi_oversold_but_blocked", 0) > 0:
        count = refusal_reasons["rsi_oversold_but_blocked"]
        recommendations.append(
            f"🔧 Найдено {count} случаев с RSI < 30, но покупка заблокирована. "
            "Рекомендация: разрешить покупки при сильной перепроданности независимо от других фильтров"
        )
    
    if not recommendations:
        recommendations.append("✓ Не найдено очевидных проблем.")
    
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec}")
    
    print()
    print("=" * 100)
    
    # Сохраняем отчет
    try:
        with open("analysis_report_today.txt", "w", encoding="utf-8") as f:
            f.write("=" * 100 + "\n")
            f.write("ОТЧЕТ АНАЛИЗА РЕШЕНИЙ БОТА ЗА СЕГОДНЯ\n")
            f.write("=" * 100 + "\n\n")
            f.write(f"Период: {today_start.strftime('%Y-%m-%d')}\n")
            f.write(f"Решений: {len(decisions)}\n")
            f.write(f"Пропусков: {len(skips)}\n")
            f.write(f"Покупок: {len(trades_buy)}\n")
            f.write(f"Упущенных возможностей: {len(missed_opportunities)}\n")
            if missed_opportunities:
                avg = sum(mo["price_change_pct"] for mo in missed_opportunities) / len(missed_opportunities)
                f.write(f"Средняя упущенная прибыль: {avg:.2f}%\n")
        print("✓ Отчет сохранен в analysis_report_today.txt")
    except Exception as e:
        print(f"⚠️  Не удалось сохранить отчет: {e}")

if __name__ == "__main__":
    try:
        analyze_buy_decisions()
    except Exception as e:
        print(f"❌ ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)




