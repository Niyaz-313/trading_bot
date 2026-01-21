#!/usr/bin/env python3
"""
Анализ решений бота о покупке за сегодняшний день.

Анализирует:
1. Сколько решений "не покупать" было за день
2. Сколько из них обоснованные
3. Сколько решений об отказе покупки были убыточными (упущенные возможности)
4. Причины отказов и рекомендации по исправлению
"""

import sys
import json
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import Dict, List, Optional

# Настройка кодировки для Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


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
    # Используем локальное время для определения "сегодня"
    from zoneinfo import ZoneInfo
    try:
        local_tz = ZoneInfo("Europe/Moscow")  # Или другая локальная зона
    except:
        local_tz = timezone.utc
    
    now_local = datetime.now(local_tz)
    today_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    # Конвертируем в UTC
    today_start_utc = today_start_local.astimezone(timezone.utc).replace(tzinfo=timezone.utc)
    return today_start_utc


def analyze_buy_decisions(audit_path: str):
    """Анализирует решения о покупке за сегодня"""
    
    print("=" * 100)
    print("АНАЛИЗ РЕШЕНИЙ БОТА О ПОКУПКЕ ЗА СЕГОДНЯШНИЙ ДЕНЬ")
    print("=" * 100)
    print()
    
    today_start = get_today_start_utc()
    print(f"Анализируем период: с {today_start.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"Текущее время: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print()
    
    # Читаем события
    decisions = []  # decision events
    skips = []      # skip events
    trades = []     # trade events (BUY)
    market_data = []  # market events (для проверки цен)
    
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
                        trades.append(event)
                    elif event_type == "market":
                        market_data.append(event)
                except Exception as e:
                    print(f"⚠️  Ошибка парсинга строки {line_num}: {e}", file=sys.stderr)
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
    print(f"   - Покупок (trade BUY): {len(trades)}")
    print(f"   - Рыночных данных (market): {len(market_data)}")
    print()
    
    # Анализ решений с BUY сигналами
    print("-" * 100)
    print("АНАЛИЗ РЕШЕНИЙ С СИГНАЛАМИ BUY (но не куплено)")
    print("-" * 100)
    
    buy_decisions = []
    for d in decisions:
        details = d.get("details", {})
        if details.get("strategy_should_buy") == True:
            buy_decisions.append(d)
    
    print(f"Найдено решений с сигналом BUY от стратегии: {len(buy_decisions)}")
    print()
    
    if len(buy_decisions) == 0:
        print("⚠️  ВНИМАНИЕ: Стратегия не генерировала сигналы BUY за сегодня!")
        print("   Это может означать:")
        print("   1. Рынок в неблагоприятном состоянии (sideways, bear)")
        print("   2. Фильтры стратегии слишком строгие")
        print("   3. Все символы не проходят проверки стратегии")
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
        
        # Анализируем каждое решение
        for symbol, events in sorted(buy_by_symbol.items()):
            latest = events[-1]  # Последнее решение для символа
            conf = float(latest.get("confidence", 0) or 0)
            rsi = latest.get("rsi")
            trend = latest.get("trend", "")
            macd_hist = latest.get("macd_hist")
            price = latest.get("price")
            ts = latest.get("ts_utc", "")
            
            print(f"📈 {symbol}:")
            print(f"   Время: {ts}")
            print(f"   Confidence: {conf:.3f}")
            print(f"   RSI: {rsi}")
            print(f"   Trend: {trend}")
            print(f"   MACD_hist: {macd_hist}")
            print(f"   Цена: {price}")
            print(f"   Количество сигналов: {len(events)}")
            print()
    
    # Анализ пропусков (skip events)
    print("-" * 100)
    print("АНАЛИЗ ПРИЧИН ПРОПУСКА ПОКУПОК (skip events)")
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
            
            # Статистика по символам
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
                print(f"   Символы: {', '.join(sorted(symbols.keys()))}")
            if confidences:
                avg_conf = sum(confidences) / len(confidences)
                print(f"   Средний confidence: {avg_conf:.3f}")
            
            # Примеры
            examples = events[:3]
            for ex in examples:
                sym = ex.get("symbol", "")
                details = ex.get("details", {})
                print(f"   Пример ({sym}):")
                for k, v in list(details.items())[:5]:  # Первые 5 полей
                    print(f"      {k}: {v}")
            print()
    else:
        print("⚠️  Нет событий пропуска (skip) - возможно, проблема в стратегии или фильтрах.")
        print()
    
    # Анализ упущенных возможностей
    print("-" * 100)
    print("АНАЛИЗ УПУЩЕННЫХ ВОЗМОЖНОСТЕЙ")
    print("-" * 100)
    
    missed_opportunities = []
    
    # Для каждого решения с BUY сигналом проверяем, была ли бы прибыль
    for bd in buy_decisions:
        symbol = bd.get("symbol", "")
        decision_price = bd.get("price")
        decision_time = parse_timestamp(bd.get("ts_utc", ""))
        
        if not symbol or not decision_price or not decision_time:
            continue
        
        # Ищем последующие цены для этого символа
        future_prices = []
        for md in market_data:
            if md.get("symbol") == symbol:
                md_time = parse_timestamp(md.get("ts_utc", ""))
                if md_time and md_time > decision_time:
                    price = md.get("price")
                    if price:
                        future_prices.append((md_time, price))
        
        if future_prices:
            # Берем последнюю цену (текущую)
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
                    "confidence": float(bd.get("confidence", 0) or 0),
                    "skip_reason": None  # Найдем причину пропуска
                })
    
    # Ищем причины пропуска для упущенных возможностей
    for mo in missed_opportunities:
        sym = mo["symbol"]
        decision_time = mo["decision_time"]
        
        # Ищем ближайший skip для этого символа
        closest_skip = None
        min_time_diff = timedelta.max
        
        for skip in skips:
            if skip.get("symbol") == sym:
                skip_time = parse_timestamp(skip.get("ts_utc", ""))
                if skip_time:
                    time_diff = abs(skip_time - decision_time)
                    if time_diff < min_time_diff:
                        min_time_diff = time_diff
                        closest_skip = skip
        
        if closest_skip and min_time_diff < timedelta(hours=1):
            mo["skip_reason"] = closest_skip.get("skip_reason", "unknown")
    
    if missed_opportunities:
        print(f"⚠️  Найдено {len(missed_opportunities)} упущенных возможностей (была бы прибыль):")
        print()
        
        # Сортируем по упущенной прибыли
        missed_opportunities.sort(key=lambda x: -x["price_change_pct"])
        
        for mo in missed_opportunities:
            print(f"💰 {mo['symbol']}:")
            print(f"   Время решения: {mo['decision_time'].strftime('%Y-%m-%d %H:%M:%S')} UTC")
            print(f"   Цена решения: {mo['decision_price']:.2f}")
            print(f"   Текущая цена: {mo['current_price']:.2f}")
            print(f"   Упущенная прибыль: +{mo['price_change_pct']:.2f}%")
            print(f"   Confidence: {mo['confidence']:.3f}")
            if mo['skip_reason']:
                print(f"   Причина пропуска: {mo['skip_reason']}")
            print()
        
        # Статистика по причинам
        reasons_stats = defaultdict(list)
        for mo in missed_opportunities:
            reason = mo.get("skip_reason", "unknown")
            reasons_stats[reason].append(mo["price_change_pct"])
        
        print("📊 Статистика упущенной прибыли по причинам:")
        for reason, profits in sorted(reasons_stats.items(), key=lambda x: -sum(x[1])):
            avg_profit = sum(profits) / len(profits)
            max_profit = max(profits)
            print(f"   {reason}:")
            print(f"      Количество: {len(profits)}")
            print(f"      Средняя упущенная прибыль: {avg_profit:.2f}%")
            print(f"      Максимальная упущенная прибыль: {max_profit:.2f}%")
            print()
    else:
        print("✓ Не найдено упущенных возможностей (или нет данных о последующих ценах)")
        print()
    
    # Рекомендации
    print("-" * 100)
    print("РЕКОМЕНДАЦИИ ПО ИСПРАВЛЕНИЮ")
    print("-" * 100)
    
    recommendations = []
    
    # Анализ причин пропуска
    if skip_reasons.get("rsi_too_high_for_buy", 0) > 0:
        count = skip_reasons["rsi_too_high_for_buy"]
        recommendations.append(
            f"🔧 RSI_MAX_BUY слишком строгий ({count} пропусков). "
            "Рекомендация: увеличить RSI_MAX_BUY до 68-70 или снизить MACD_OVERRIDE_FOR_HIGH_RSI"
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
            "Рекомендация: разрешить покупки в sideways при сильной перепроданности (RSI < 30)"
        )
    
    if skip_reasons.get("low_confidence", 0) > 0:
        count = skip_reasons["low_confidence"]
        recommendations.append(
            f"🔧 MIN_CONF_BUY слишком высокий ({count} пропусков). "
            "Рекомендация: снизить MIN_CONF_BUY до 0.55-0.58"
        )
    
    if skip_reasons.get("max_positions_reached", 0) > 0:
        count = skip_reasons["max_positions_reached"]
        recommendations.append(
            f"ℹ️  Достигнут лимит открытых позиций ({count} пропусков). "
            "Это нормально, но можно увеличить MAX_OPEN_POSITIONS если нужно больше активности"
        )
    
    if skip_reasons.get("daily_loss_limit", 0) > 0:
        count = skip_reasons["daily_loss_limit"]
        recommendations.append(
            f"⚠️  Достигнут дневной лимит убытков ({count} пропусков). "
            "Это защита от больших потерь - проверьте текущие позиции"
        )
    
    if len(buy_decisions) == 0:
        recommendations.append(
            "⚠️  Стратегия не генерирует сигналы BUY. "
            "Возможные причины:"
        )
        recommendations.append("   1. Рынок в боковом/медвежьем тренде")
        recommendations.append("   2. Фильтры стратегии слишком строгие")
        recommendations.append("   3. Все символы не проходят проверки")
        recommendations.append("   Рекомендация: проверить логику стратегии или снизить пороги")
    
    if len(missed_opportunities) > 0:
        avg_missed = sum(mo["price_change_pct"] for mo in missed_opportunities) / len(missed_opportunities)
        recommendations.append(
            f"💰 Найдено {len(missed_opportunities)} упущенных возможностей "
            f"со средней прибылью {avg_missed:.2f}%. "
            "Рекомендация: ослабить фильтры, которые блокируют эти покупки"
        )
    
    if not recommendations:
        recommendations.append("✓ Не найдено очевидных проблем. Бот работает нормально.")
    
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec}")
    
    print()
    print("=" * 100)


if __name__ == "__main__":
    import os
    
    audit_path = os.path.join("audit_logs", "trades_audit.jsonl")
    
    if len(sys.argv) > 1:
        audit_path = sys.argv[1]
    
    if not os.path.exists(audit_path):
        print(f"❌ ERROR: Файл не найден: {audit_path}", file=sys.stderr)
        sys.exit(1)
    
    try:
        analyze_buy_decisions(audit_path)
    except Exception as e:
        print(f"❌ ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

