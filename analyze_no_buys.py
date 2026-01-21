#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Анализ причин отсутствия покупок бота
Исключает принудительные операции за последний час
"""
import json
import os
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter
from typing import Dict, List

def analyze_no_buys():
    """Анализ причин отсутствия покупок"""
    
    audit_file = "audit_logs/trades_audit.jsonl"
    if not os.path.exists(audit_file):
        print(f"Файл аудита не найден: {audit_file}")
        return
    
    now = datetime.now(timezone.utc)
    hour_ago = now - timedelta(hours=1)
    day_ago = now - timedelta(days=1)
    
    print("=" * 80)
    print("АНАЛИЗ ПРИЧИН ОТСУТСТВИЯ ПОКУПОК")
    print("=" * 80)
    print(f"Время анализа: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Исключаем принудительные операции после: {hour_ago.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()
    
    events = []
    with open(audit_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                event = json.loads(line.strip())
                events.append(event)
            except Exception:
                continue
    
    # Фильтруем события за последний день (исключая принудительные за последний час)
    recent_events = []
    forced_symbols = set()
    
    for event in events:
        ts_str = event.get('ts_utc', '')
        if not ts_str:
            continue
        
        try:
            # Парсим время
            if ts_str.endswith('Z'):
                ts_str = ts_str[:-1] + '+00:00'
            event_time = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            
            # Исключаем принудительные операции за последний час
            reason = event.get('reason', '')
            if event_time > hour_ago and reason in ['forced_buy', 'forced_sell']:
                symbol = event.get('symbol', '')
                if symbol:
                    forced_symbols.add(symbol)
                continue
            
            # Берем события за последний день
            if event_time > day_ago:
                recent_events.append(event)
        except Exception:
            continue
    
    print(f"Всего событий за последний день: {len(recent_events)}")
    print(f"Исключено принудительных операций за последний час: {len(forced_symbols)} символов")
    print()
    
    # Анализ событий
    trades = [e for e in recent_events if e.get('event') == 'trade' and e.get('action') == 'BUY']
    skips = [e for e in recent_events if e.get('event') == 'skip']
    decisions = [e for e in recent_events if e.get('event') == 'decision']
    
    print("=" * 80)
    print("СТАТИСТИКА СОБЫТИЙ")
    print("=" * 80)
    print(f"Покупок (BUY): {len(trades)}")
    print(f"Пропусков (skip): {len(skips)}")
    print(f"Решений (decision): {len(decisions)}")
    print()
    
    # Анализ причин пропусков
    skip_reasons = Counter()
    skip_by_symbol = defaultdict(list)
    
    for skip in skips:
        reason = skip.get('skip_reason', 'unknown')
        symbol = skip.get('symbol', 'unknown')
        skip_reasons[reason] += 1
        skip_by_symbol[symbol].append(reason)
    
    print("=" * 80)
    print("ПРИЧИНЫ ПРОПУСКОВ (TOP 20)")
    print("=" * 80)
    for reason, count in skip_reasons.most_common(20):
        print(f"  {reason}: {count}")
    print()
    
    # Анализ решений
    buy_decisions = [d for d in decisions if d.get('action') == 'BUY']
    no_buy_decisions = [d for d in decisions if d.get('action') != 'BUY' or d.get('should_buy') == False]
    
    print("=" * 80)
    print("АНАЛИЗ РЕШЕНИЙ")
    print("=" * 80)
    print(f"Решений на покупку: {len(buy_decisions)}")
    print(f"Решений НЕ покупать: {len(no_buy_decisions)}")
    print()
    
    # Анализ confidence в решениях
    confidences = []
    for decision in decisions:
        conf = decision.get('confidence')
        if conf is not None:
            try:
                confidences.append(float(conf))
            except Exception:
                pass
    
    if confidences:
        print(f"Средний confidence: {sum(confidences)/len(confidences):.3f}")
        print(f"Минимальный confidence: {min(confidences):.3f}")
        print(f"Максимальный confidence: {max(confidences):.3f}")
        print(f"Confidence >= 0.50: {sum(1 for c in confidences if c >= 0.50)}")
        print(f"Confidence >= 0.60: {sum(1 for c in confidences if c >= 0.60)}")
        print()
    
    # Анализ по символам
    print("=" * 80)
    print("ТОП СИМВОЛОВ ПО КОЛИЧЕСТВУ ПРОПУСКОВ")
    print("=" * 80)
    symbol_skip_counts = {sym: len(reasons) for sym, reasons in skip_by_symbol.items()}
    for symbol, count in sorted(symbol_skip_counts.items(), key=lambda x: x[1], reverse=True)[:20]:
        print(f"  {symbol}: {count} пропусков")
        reasons = Counter(skip_by_symbol[symbol])
        for reason, rcount in reasons.most_common(3):
            print(f"    - {reason}: {rcount}")
    print()
    
    # Анализ последних решений
    print("=" * 80)
    print("ПОСЛЕДНИЕ 10 РЕШЕНИЙ")
    print("=" * 80)
    sorted_decisions = sorted(decisions, key=lambda x: x.get('ts_utc', ''), reverse=True)[:10]
    for decision in sorted_decisions:
        symbol = decision.get('symbol', 'unknown')
        action = decision.get('action', 'unknown')
        conf = decision.get('confidence', 0)
        should_buy = decision.get('should_buy', False)
        ts = decision.get('ts_utc', '')[:19]
        print(f"  {ts} | {symbol:10s} | action={action:4s} | should_buy={should_buy:5s} | conf={conf:.3f}")
    print()
    
    # Рекомендации
    print("=" * 80)
    print("РЕКОМЕНДАЦИИ ДЛЯ УВЕЛИЧЕНИЯ КОЛИЧЕСТВА СДЕЛОК")
    print("=" * 80)
    
    if len(trades) < 10:
        print("⚠ Проблема: Меньше 10 сделок за день")
        print()
        print("Рекомендации:")
        
        if skip_reasons.get('low_confidence', 0) > 0:
            print(f"  1. Снизить MIN_CONF_BUY (сейчас много пропусков из-за низкого confidence: {skip_reasons['low_confidence']})")
        
        if skip_reasons.get('instrument_not_tradeable', 0) > 0:
            print(f"  2. Проверить доступность инструментов (пропусков из-за недоступности: {skip_reasons['instrument_not_tradeable']})")
        
        if skip_reasons.get('max_positions_reached', 0) > 0:
            print(f"  3. Увеличить MAX_OPEN_POSITIONS или уменьшить время удержания позиций")
        
        if skip_reasons.get('cooldown', 0) > 0:
            print(f"  4. Уменьшить SYMBOL_COOLDOWN_MIN для более частых сделок")
        
        if skip_reasons.get('max_trades_per_day', 0) > 0:
            print(f"  5. Увеличить MAX_TRADES_PER_DAY (сейчас лимит достигнут: {skip_reasons['max_trades_per_day']})")
        
        if skip_reasons.get('daily_loss_limit', 0) > 0:
            print(f"  6. Проверить DAILY_LOSS_LIMIT_PCT (достигнут лимит убытков)")
        
        if skip_reasons.get('position_too_expensive', 0) > 0:
            print(f"  7. Увеличить MAX_POSITION_VALUE_PCT или INITIAL_CAPITAL")
        
        if len(confidences) > 0 and sum(1 for c in confidences if c >= 0.50) < len(confidences) * 0.3:
            print(f"  8. Снизить MIN_CONF_BUY до 0.45-0.50 (сейчас только {sum(1 for c in confidences if c >= 0.50)/len(confidences)*100:.1f}% сигналов проходят порог)")
        
        print()
        print("Для достижения 10+ сделок в день рекомендуется:")
        print("  - MIN_CONF_BUY = 0.45-0.50")
        print("  - MAX_TRADES_PER_DAY = 30-50")
        print("  - MAX_OPEN_POSITIONS = 8-10")
        print("  - SYMBOL_COOLDOWN_MIN = 5-10")
        print("  - RSI_MAX_BUY = 70-75 (более либеральный)")
        print("  - MIN_MACD_HIST_ATR_RATIO_BUY = -0.2 (более либеральный)")
    else:
        print("✓ Количество сделок достаточное")
    
    print("=" * 80)

if __name__ == "__main__":
    analyze_no_buys()

