#!/usr/bin/env python3
"""Анализ активности бота за последние 24 часа"""
import json
import sys
from datetime import datetime, timedelta
from collections import defaultdict
from zoneinfo import ZoneInfo

AUDIT_LOG_PATH = "audit_logs/trades_audit.jsonl"

def analyze_last_24h():
    """Анализ событий за последние 24 часа"""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat().replace('+00:00', 'Z')
    
    events = defaultdict(int)
    skip_reasons = defaultdict(int)
    decision_signals = defaultdict(int)
    confidences = []
    trades = []
    symbols_checked = set()
    
    last_trade_time = None
    last_cycle_time = None
    
    try:
        with open(AUDIT_LOG_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except Exception:
                    continue
                
                ts = event.get('ts_utc', '')
                if not ts or ts < cutoff:
                    continue
                
                event_type = event.get('event', 'unknown')
                events[event_type] += 1
                
                if event_type == 'trade':
                    trades.append(event)
                    last_trade_time = ts
                elif event_type == 'cycle':
                    last_cycle_time = ts
                elif event_type == 'skip':
                    reason = event.get('skip_reason', 'unknown')
                    skip_reasons[reason] += 1
                elif event_type == 'decision':
                    symbol = event.get('symbol', '')
                    if symbol:
                        symbols_checked.add(symbol)
                    signal = event.get('signal', 'hold')
                    decision_signals[signal] += 1
                    conf = event.get('confidence')
                    if conf is not None:
                        try:
                            confidences.append(float(conf))
                        except:
                            pass
    
    except FileNotFoundError:
        print(f"❌ Файл {AUDIT_LOG_PATH} не найден")
        return
    except Exception as e:
        print(f"❌ Ошибка чтения лога: {e}")
        return
    
    # Вывод результатов
    print("=" * 80)
    print("📊 АНАЛИЗ АКТИВНОСТИ БОТА ЗА ПОСЛЕДНИЕ 24 ЧАСА")
    print("=" * 80)
    print()
    
    print("🔢 СТАТИСТИКА СОБЫТИЙ:")
    for event_type, count in sorted(events.items(), key=lambda x: x[1], reverse=True):
        print(f"  {event_type:20s}: {count:5d}")
    print()
    
    total_events = sum(events.values())
    if total_events == 0:
        print("⚠️  НЕТ ДАННЫХ за последние 24 часа")
        return
    
    # Анализ сделок
    print("💰 СДЕЛКИ:")
    buy_count = sum(1 for t in trades if str(t.get('action', '')).upper() == 'BUY')
    sell_count = sum(1 for t in trades if str(t.get('action', '')).upper() == 'SELL')
    print(f"  Покупок (BUY):  {buy_count}")
    print(f"  Продаж (SELL):  {sell_count}")
    print(f"  Всего сделок:   {len(trades)}")
    if last_trade_time:
        try:
            dt = datetime.fromisoformat(last_trade_time.replace('Z', '+00:00'))
            print(f"  Последняя сделка: {dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        except:
            print(f"  Последняя сделка: {last_trade_time}")
    print()
    
    # Анализ решений
    print("🎯 СИГНАЛЫ СТРАТЕГИИ (decision events):")
    for signal, count in sorted(decision_signals.items(), key=lambda x: x[1], reverse=True):
        print(f"  {signal:10s}: {count:5d}")
    print()
    
    if confidences:
        avg_conf = sum(confidences) / len(confidences)
        max_conf = max(confidences)
        min_conf = min(confidences)
        print(f"  Уверенность (confidence):")
        print(f"    Средняя: {avg_conf:.2f}")
        print(f"    Максимальная: {max_conf:.2f}")
        print(f"    Минимальная: {min_conf:.2f}")
        print(f"    Всего решений: {len(confidences)}")
        print()
        
        # Подсчет сигналов с confidence >= 0.5
        high_conf = sum(1 for c in confidences if c >= 0.5)
        print(f"  Сигналов с confidence >= 0.5: {high_conf} ({high_conf*100/len(confidences):.1f}%)")
        print(f"  Сигналов с confidence >= 0.6: {sum(1 for c in confidences if c >= 0.6)} ({sum(1 for c in confidences if c >= 0.6)*100/len(confidences):.1f}%)")
        print()
    
    # Анализ пропусков
    if skip_reasons:
        print("🚫 ПРИЧИНЫ ПРОПУСКА СДЕЛОК (skip events):")
        sorted_reasons = sorted(skip_reasons.items(), key=lambda x: x[1], reverse=True)
        for reason, count in sorted_reasons[:15]:
            print(f"  {reason:50s}: {count:5d} ({count*100/sum(skip_reasons.values()):.1f}%)")
        print()
    
    print(f"📈 ПРОВЕРЕНО СИМВОЛОВ: {len(symbols_checked)}")
    if symbols_checked:
        print(f"  Примеры: {', '.join(list(symbols_checked)[:10])}")
    print()
    
    # Последний цикл
    if last_cycle_time:
        try:
            dt = datetime.fromisoformat(last_cycle_time.replace('Z', '+00:00'))
            print(f"🔄 Последний цикл: {dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            hours_ago = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
            print(f"   {hours_ago:.1f} часов назад")
        except:
            pass
    print()
    
    # Диагностика проблем
    print("=" * 80)
    print("🔍 ДИАГНОСТИКА ПРОБЛЕМ:")
    print("=" * 80)
    print()
    
    issues = []
    
    if len(trades) == 0:
        issues.append("❌ КРИТИЧНО: Нет сделок за 24 часа!")
    elif len(trades) < 5:
        issues.append(f"⚠️  МАЛО СДЕЛОК: Всего {len(trades)} сделок за 24 часа")
    
    if events.get('decision', 0) == 0:
        issues.append("❌ КРИТИЧНО: Нет decision событий (бот не анализирует рынок?)")
    
    if skip_reasons:
        total_skips = sum(skip_reasons.values())
        if total_skips > events.get('decision', 0) * 0.9:
            issues.append(f"⚠️  МНОГО ПРОПУСКОВ: {total_skips} пропусков при {events.get('decision', 0)} решений")
    
    if confidences:
        high_conf_count = sum(1 for c in confidences if c >= 0.5)
        if high_conf_count > 0 and buy_count == 0:
            issues.append(f"⚠️  ЕСТЬ ХОРОШИЕ СИГНАЛЫ НО НЕТ ПОКУПОК: {high_conf_count} решений с confidence >= 0.5, но 0 покупок")
    
    if not issues:
        print("✅ Критических проблем не обнаружено")
    else:
        for issue in issues:
            print(issue)
    
    print()

if __name__ == "__main__":
    analyze_last_24h()




