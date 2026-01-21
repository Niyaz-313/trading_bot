#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Анализ причин низкого количества сделок с 15:00 19.01.2026
"""
import json
import os
from datetime import datetime, timezone
from collections import defaultdict, Counter
from typing import Dict, List

def analyze_low_trades():
    """Анализ причин низкого количества сделок"""
    
    audit_file = "audit_logs/trades_audit.jsonl"
    if not os.path.exists(audit_file):
        print(f"Файл аудита не найден: {audit_file}")
        return
    
    # Время начала анализа: 15:00 19.01.2026 МСК = 12:00 UTC
    start_time = datetime(2026, 1, 19, 12, 0, 0, tzinfo=timezone.utc)
    
    print("=" * 80)
    print("АНАЛИЗ ПРИЧИН НИЗКОГО КОЛИЧЕСТВА СДЕЛОК")
    print("=" * 80)
    print(f"Период: с {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')} (15:00 МСК 19.01.2026)")
    print()
    
    events = []
    with open(audit_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                event = json.loads(line.strip())
                events.append(event)
            except Exception:
                continue
    
    # Фильтруем события после указанного времени
    recent_events = []
    for event in events:
        ts_str = event.get('ts_utc', '')
        if not ts_str:
            continue
        
        try:
            if ts_str.endswith('Z'):
                ts_str = ts_str[:-1] + '+00:00'
            event_time = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            
            if event_time >= start_time:
                recent_events.append(event)
        except Exception:
            continue
    
    print(f"Всего событий с {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}: {len(recent_events)}")
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
    skip_details = defaultdict(list)
    
    for skip in skips:
        reason = skip.get('skip_reason', 'unknown')
        symbol = skip.get('symbol', 'unknown')
        skip_reasons[reason] += 1
        skip_by_symbol[symbol].append(reason)
        
        # Собираем детали для анализа
        details = skip.get('details', {})
        if details:
            skip_details[reason].append(details)
    
    print("=" * 80)
    print("ПРИЧИНЫ ПРОПУСКОВ (TOP 20)")
    print("=" * 80)
    for reason, count in skip_reasons.most_common(20):
        print(f"  {reason}: {count}")
    print()
    
    # Анализ решений
    buy_decisions = [d for d in decisions if d.get('action') == 'BUY' and d.get('should_buy') == True]
    no_buy_decisions = [d for d in decisions if d.get('action') != 'BUY' or d.get('should_buy') == False]
    
    print("=" * 80)
    print("АНАЛИЗ РЕШЕНИЙ")
    print("=" * 80)
    print(f"Решений на покупку (should_buy=True): {len(buy_decisions)}")
    print(f"Решений НЕ покупать (should_buy=False или action != BUY): {len(no_buy_decisions)}")
    print()
    
    # Анализ confidence в решениях
    confidences = []
    low_conf_decisions = []
    for decision in decisions:
        conf = decision.get('confidence')
        if conf is not None:
            try:
                conf_val = float(conf)
                confidences.append(conf_val)
                if conf_val < 0.45:
                    low_conf_decisions.append(decision)
            except Exception:
                pass
    
    if confidences:
        print(f"Средний confidence: {sum(confidences)/len(confidences):.3f}")
        print(f"Минимальный confidence: {min(confidences):.3f}")
        print(f"Максимальный confidence: {max(confidences):.3f}")
        print(f"Confidence >= 0.45: {sum(1 for c in confidences if c >= 0.45)}")
        print(f"Confidence >= 0.50: {sum(1 for c in confidences if c >= 0.50)}")
        print(f"Confidence >= 0.60: {sum(1 for c in confidences if c >= 0.60)}")
        print()
    
    # Анализ блокировок по gates
    gates_blocked = Counter()
    for decision in decisions:
        gates = decision.get('gates', {})
        if isinstance(gates, dict):
            for gate_name, gate_ok in gates.items():
                if gate_ok == False:
                    gates_blocked[gate_name] += 1
    
    if gates_blocked:
        print("=" * 80)
        print("БЛОКИРОВКИ ПО GATES")
        print("=" * 80)
        for gate, count in gates_blocked.most_common():
            print(f"  {gate}: {count}")
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
    print("ПОСЛЕДНИЕ 20 РЕШЕНИЙ")
    print("=" * 80)
    sorted_decisions = sorted(decisions, key=lambda x: x.get('ts_utc', ''), reverse=True)[:20]
    for decision in sorted_decisions:
        symbol = decision.get('symbol', 'unknown')
        action = decision.get('action', 'unknown')
        conf = decision.get('confidence', 0)
        should_buy = decision.get('should_buy', False)
        ts = decision.get('ts_utc', '')[:19]
        gates = decision.get('gates', {})
        gates_ok = all(gates.values()) if isinstance(gates, dict) else True
        print(f"  {ts} | {symbol:10s} | action={action:4s} | should_buy={should_buy:5s} | conf={conf:.3f} | gates_ok={gates_ok}")
    print()
    
    # Детальный анализ пропусков по причинам
    print("=" * 80)
    print("ДЕТАЛЬНЫЙ АНАЛИЗ ПРОПУСКОВ")
    print("=" * 80)
    
    # Анализ low_confidence
    if skip_reasons.get('low_confidence', 0) > 0:
        low_conf_skips = [s for s in skips if s.get('skip_reason') == 'low_confidence']
        confs = [float(s.get('confidence', 0)) for s in low_conf_skips if s.get('confidence')]
        if confs:
            print(f"low_confidence: {len(confs)} пропусков")
            print(f"  Средний confidence: {sum(confs)/len(confs):.3f}")
            print(f"  Минимальный: {min(confs):.3f}")
            print(f"  Максимальный: {max(confs):.3f}")
            print()
    
    # Анализ strategy_should_buy_false
    if skip_reasons.get('strategy_should_buy_false', 0) > 0:
        strategy_skips = [s for s in skips if s.get('skip_reason') == 'strategy_should_buy_false']
        print(f"strategy_should_buy_false: {len(strategy_skips)} пропусков")
        # Анализируем детали
        strategy_details = [s.get('details', {}) for s in strategy_skips]
        failed_rules = Counter()
        for detail in strategy_details:
            if isinstance(detail, dict):
                rule = detail.get('rule', 'unknown')
                failed_rules[rule] += 1
        if failed_rules:
            print("  Блокировки по правилам:")
            for rule, count in failed_rules.most_common():
                print(f"    - {rule}: {count}")
        print()
    
    # Рекомендации
    print("=" * 80)
    print("РЕКОМЕНДАЦИИ ДЛЯ УВЕЛИЧЕНИЯ КОЛИЧЕСТВА СДЕЛОК")
    print("=" * 80)
    
    recommendations = []
    
    if len(trades) < 10:
        recommendations.append("⚠ Проблема: Меньше 10 сделок за период")
        recommendations.append("")
        
        if skip_reasons.get('low_confidence', 0) > 0:
            recommendations.append(f"1. Снизить MIN_CONF_BUY (сейчас {skip_reasons['low_confidence']} пропусков из-за низкого confidence)")
        
        if skip_reasons.get('strategy_should_buy_false', 0) > 0:
            recommendations.append(f"2. Ослабить фильтры стратегии (сейчас {skip_reasons['strategy_should_buy_false']} пропусков)")
            if failed_rules:
                top_rule = failed_rules.most_common(1)[0]
                recommendations.append(f"   Наиболее частая блокировка: {top_rule[0]} ({top_rule[1]} раз)")
        
        if skip_reasons.get('max_positions_reached', 0) > 0:
            recommendations.append(f"3. Увеличить MAX_OPEN_POSITIONS (сейчас {skip_reasons['max_positions_reached']} пропусков)")
        
        if skip_reasons.get('cooldown', 0) > 0:
            recommendations.append(f"4. Уменьшить SYMBOL_COOLDOWN_MIN (сейчас {skip_reasons['cooldown']} пропусков)")
        
        if skip_reasons.get('max_trades_per_day', 0) > 0:
            recommendations.append(f"5. Увеличить MAX_TRADES_PER_DAY (сейчас {skip_reasons['max_trades_per_day']} пропусков)")
        
        if gates_blocked.get('max_open_positions_ok', 0) > 0:
            recommendations.append(f"6. Увеличить MAX_OPEN_POSITIONS (блокировок: {gates_blocked['max_open_positions_ok']})")
        
        if gates_blocked.get('max_trades_ok', 0) > 0:
            recommendations.append(f"7. Увеличить MAX_TRADES_PER_DAY (блокировок: {gates_blocked['max_trades_ok']})")
        
        if len(confidences) > 0:
            conf_45 = sum(1 for c in confidences if c >= 0.45)
            conf_50 = sum(1 for c in confidences if c >= 0.50)
            pct_45 = conf_45 / len(confidences) * 100 if confidences else 0
            pct_50 = conf_50 / len(confidences) * 100 if confidences else 0
            recommendations.append(f"8. Только {pct_45:.1f}% сигналов имеют confidence >= 0.45, {pct_50:.1f}% >= 0.50")
            if pct_45 < 30:
                recommendations.append("   Рекомендация: снизить MIN_CONF_BUY до 0.40-0.42")
    
    for rec in recommendations:
        print(rec)
    
    print("=" * 80)

if __name__ == "__main__":
    analyze_low_trades()

