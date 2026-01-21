#!/usr/bin/env python3
"""Анализ сигналов покупки: сколько было, сколько принято, сколько исполнено"""
import json
from datetime import datetime, timedelta
from collections import defaultdict

AUDIT_LOG_PATH = "audit_logs/trades_audit.jsonl"

def analyze_buy_signals():
    """Анализ сигналов покупки за последние 24 часа"""
    
    # Статистика
    decisions = []
    buys = []
    skips = []
    errors = []
    
    # Период
    from datetime import timezone as tz
    cutoff = (datetime.now(tz.utc) - timedelta(hours=24)).isoformat().replace('+00:00', 'Z')
    
    try:
        with open(AUDIT_LOG_PATH, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except Exception as e:
                    errors.append(f"Line {line_num}: JSON parse error: {e}")
                    continue
                
                ts = event.get('ts_utc', '')
                if not ts or ts < cutoff:
                    continue
                
                event_type = event.get('event', '')
                
                if event_type == 'decision':
                    details = event.get('details', {})
                    strategy_should_buy = details.get('strategy_should_buy', False)
                    gates = details.get('gates', {})
                    
                    decisions.append({
                        'symbol': event.get('symbol', ''),
                        'ts': ts,
                        'confidence': event.get('confidence', 0),
                        'strategy_should_buy': strategy_should_buy,
                        'signal': event.get('signal', ''),
                        'buy_signals': event.get('buy_signals', 0),
                        'gates': gates,
                        'line': line_num
                    })
                
                elif event_type == 'trade':
                    if str(event.get('action', '')).upper() == 'BUY':
                        buys.append({
                            'symbol': event.get('symbol', ''),
                            'ts': ts,
                            'order_id': event.get('order', {}).get('order_id', '') if isinstance(event.get('order'), dict) else '',
                            'order_status': event.get('order', {}).get('status', '') if isinstance(event.get('order'), dict) else '',
                            'confidence': event.get('confidence', 0),
                            'line': line_num
                        })
                
                elif event_type == 'skip':
                    skips.append({
                        'symbol': event.get('symbol', ''),
                        'ts': ts,
                        'reason': event.get('skip_reason', 'unknown'),
                        'confidence': event.get('confidence', 0),
                        'line': line_num
                    })
    
    except FileNotFoundError:
        print(f"❌ Файл {AUDIT_LOG_PATH} не найден")
        return
    except Exception as e:
        print(f"❌ Ошибка чтения: {e}")
        return
    
    # Анализ
    print("=" * 80)
    print("📊 АНАЛИЗ СИГНАЛОВ ПОКУПКИ")
    print("=" * 80)
    print()
    
    print(f"📈 DECISION событий (анализ символов): {len(decisions)}")
    print(f"✅ BUY сделок: {len(buys)}")
    print(f"🚫 SKIP событий: {len(skips)}")
    print()
    
    # Анализ decisions
    strategy_approved = [d for d in decisions if d.get('strategy_should_buy')]
    print(f"🎯 Решений где strategy_should_buy=true: {len(strategy_approved)}")
    
    if strategy_approved:
        print(f"   Примеры:")
        for d in strategy_approved[:5]:
            print(f"   - {d['symbol']}: confidence={d['confidence']}, buy_signals={d['buy_signals']}, signal={d['signal']}")
    print()
    
    # Причины пропуска (skip reasons)
    skip_reasons = defaultdict(int)
    for s in skips:
        skip_reasons[s['reason']] += 1
    
    if skip_reasons:
        print("🚫 ПРИЧИНЫ ПРОПУСКА:")
        for reason, count in sorted(skip_reasons.items(), key=lambda x: x[1], reverse=True):
            print(f"   {reason:40s}: {count:4d}")
        print()
    
    # Gates analysis
    gates_failures = defaultdict(int)
    for d in decisions:
        if not d.get('strategy_should_buy'):
            continue
        gates = d.get('gates', {})
        for gate, value in gates.items():
            if not value:
                gates_failures[gate] += 1
    
    if gates_failures:
        print("🚪 БЛОКИРОВКИ ПО ГЕЙТАМ (для strategy_should_buy=true):")
        for gate, count in sorted(gates_failures.items(), key=lambda x: x[1], reverse=True):
            print(f"   {gate:40s}: {count:4d}")
        print()
    
    # Confidence анализ
    if decisions:
        confidences = [d.get('confidence', 0) for d in decisions if d.get('confidence') is not None]
        approved_conf = [d.get('confidence', 0) for d in strategy_approved if d.get('confidence') is not None]
        
        if confidences:
            print(f"📊 CONFIDENCE статистика:")
            print(f"   Все решения: min={min(confidences):.2f}, max={max(confidences):.2f}, avg={sum(confidences)/len(confidences):.2f}")
            if approved_conf:
                print(f"   Одобренные стратегией: min={min(approved_conf):.2f}, max={max(approved_conf):.2f}, avg={sum(approved_conf)/len(approved_conf):.2f}")
            print()
    
    # Сравнение: одобренные vs исполненные
    approved_symbols = {d['symbol']: d['ts'] for d in strategy_approved}
    executed_symbols = {b['symbol']: b['ts'] for b in buys}
    
    print("🔄 СРАВНЕНИЕ ОДОБРЕННЫХ VS ИСПОЛНЕННЫХ:")
    print(f"   Одобрено стратегией: {len(approved_symbols)}")
    print(f"   Исполнено (BUY): {len(executed_symbols)}")
    
    missed = set(approved_symbols.keys()) - set(executed_symbols.keys())
    if missed:
        print(f"   ⚠️ ПРОПУЩЕНО: {len(missed)} символов")
        print(f"      Примеры: {', '.join(list(missed)[:10])}")
        # Найдем почему они пропущены
        for symbol in list(missed)[:5]:
            symbol_skips = [s for s in skips if s['symbol'] == symbol and s['ts'] > approved_symbols[symbol]]
            if symbol_skips:
                print(f"      {symbol}: пропущено по причине '{symbol_skips[0]['reason']}'")
    else:
        print(f"   ✅ Все одобренные сигналы исполнены!")
    print()
    
    # Анализ order status
    if buys:
        order_statuses = defaultdict(int)
        for b in buys:
            status = b.get('order_status', 'unknown')
            order_statuses[status] += 1
        
        print("📦 СТАТУСЫ ОРДЕРОВ:")
        for status, count in sorted(order_statuses.items(), key=lambda x: x[1], reverse=True):
            print(f"   {status:20s}: {count}")
        print()
    
    # Ошибки
    if errors:
        print(f"⚠️ ОШИБКИ ПРИ ЧТЕНИИ ЛОГА: {len(errors)}")
        for err in errors[:5]:
            print(f"   {err}")
        print()
    
    # Итоговые метрики
    print("=" * 80)
    print("📈 ИТОГОВЫЕ МЕТРИКИ:")
    print("=" * 80)
    print(f"   Decision событий: {len(decisions)}")
    print(f"   Одобрено стратегией (should_buy=true): {len(strategy_approved)}")
    print(f"   Исполнено (BUY): {len(buys)}")
    print(f"   Пропущено (SKIP): {len(skips)}")
    if len(strategy_approved) > 0:
        execution_rate = len(executed_symbols) * 100 / len(strategy_approved)
        print(f"   📊 Execution rate: {execution_rate:.1f}% ({len(executed_symbols)}/{len(strategy_approved)})")
    print()

if __name__ == "__main__":
    analyze_buy_signals()

