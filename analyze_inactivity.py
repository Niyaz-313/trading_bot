#!/usr/bin/env python3
"""
Анализ причин бездействия бота.

Анализирует логи с указанного времени и выявляет:
1. Почему нет покупок (какие фильтры блокируют)
2. Почему нет продаж (нет позиций или другие причины)
3. Рекомендации по исправлению
"""

import sys
import json
from datetime import datetime
from collections import defaultdict

# Настройка кодировки для Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def analyze_inactivity(log_path: str, start_time: str):
    """
    Анализирует логи с указанного времени.
    
    Args:
        log_path: Путь к trades_audit.jsonl
        start_time: UTC время начала анализа (формат: "2026-01-15T01:22:35Z")
    """
    print("=" * 80)
    print("АНАЛИЗ ПРИЧИН БЕЗДЕЙСТВИЯ БОТА")
    print("=" * 80)
    print(f"Начало анализа: {start_time}")
    print()
    
    # Парсим время начала
    try:
        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    except Exception:
        print(f"ERROR: Неверный формат времени: {start_time}")
        print("Ожидается формат: 2026-01-15T01:22:35Z")
        return
    
    # Читаем логи
    decisions = []
    skips = []
    trades = []
    
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    event = json.loads(line.strip())
                    ts_str = event.get("ts_utc", "")
                    if not ts_str:
                        continue
                    
                    try:
                        event_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    except Exception:
                        continue
                    
                    if event_dt < start_dt:
                        continue
                    
                    event_type = event.get("event", "")
                    
                    if event_type == "decision":
                        decisions.append(event)
                    elif event_type == "skip":
                        skips.append(event)
                    elif event_type == "trade":
                        trades.append(event)
                except Exception:
                    continue
    except FileNotFoundError:
        print(f"ERROR: Файл не найден: {log_path}")
        return
    
    print(f"Найдено событий:")
    print(f"  - Решений (decision): {len(decisions)}")
    print(f"  - Пропусков (skip): {len(skips)}")
    print(f"  - Сделок (trade): {len(trades)}")
    print()
    
    if len(trades) > 0:
        print("⚠️  ВНИМАНИЕ: Найдены сделки после указанного времени!")
        print("Возможно, проблема была временной или уже решена.")
        print()
    
    # Анализ решений
    print("-" * 80)
    print("АНАЛИЗ РЕШЕНИЙ (decision events)")
    print("-" * 80)
    
    buy_signals = [d for d in decisions if d.get("details", {}).get("strategy_should_buy") == True]
    sell_signals = [d for d in decisions if d.get("details", {}).get("strategy_should_sell") == True]
    hold_signals = [d for d in decisions if d.get("details", {}).get("strategy_should_buy") == False and d.get("details", {}).get("strategy_should_sell") == False]
    
    print(f"Сигналов BUY от стратегии: {len(buy_signals)}")
    print(f"Сигналов SELL от стратегии: {len(sell_signals)}")
    print(f"Сигналов HOLD (нет действий): {len(hold_signals)}")
    print()
    
    # Анализ confidence
    conf_values = [float(d.get("confidence", 0) or 0) for d in decisions]
    if conf_values:
        avg_conf = sum(conf_values) / len(conf_values)
        max_conf = max(conf_values)
        min_conf = min(conf_values)
        print(f"Confidence статистика:")
        print(f"  Средний: {avg_conf:.3f}")
        print(f"  Максимум: {max_conf:.3f}")
        print(f"  Минимум: {min_conf:.3f}")
        print()
    
    # Символы с BUY сигналами
    if buy_signals:
        print("Символы с сигналами BUY (но не куплены):")
        buy_by_symbol = defaultdict(list)
        for b in buy_signals:
            sym = b.get("symbol", "")
            buy_by_symbol[sym].append(b)
        
        for sym, events in buy_by_symbol.items():
            latest = events[-1]
            conf = float(latest.get("confidence", 0) or 0)
            rsi = latest.get("rsi")
            trend = latest.get("trend", "")
            macd_hist = latest.get("macd_hist", 0)
            print(f"  {sym}: confidence={conf:.2f}, RSI={rsi:.1f}, trend={trend}, macd_hist={macd_hist:.4f}")
        print()
    
    # Анализ пропусков
    print("-" * 80)
    print("АНАЛИЗ ПРОПУСКОВ (skip events)")
    print("-" * 80)
    
    skip_reasons = defaultdict(int)
    skip_details = defaultdict(list)
    
    for skip in skips:
        reason = skip.get("skip_reason", "unknown")
        skip_reasons[reason] += 1
        skip_details[reason].append(skip)
    
    if skip_reasons:
        print("Причины пропуска сделок:")
        for reason, count in sorted(skip_reasons.items(), key=lambda x: -x[1]):
            print(f"  {reason}: {count} раз(а)")
            
            # Показываем детали для важных причин
            if reason in ["rsi_too_high_for_buy", "low_macd_hist_atr_ratio", "sideways_negative_macd"]:
                examples = skip_details[reason][:3]
                for ex in examples:
                    sym = ex.get("symbol", "")
                    details = ex.get("details", {})
                    print(f"    Пример: {sym}")
                    for k, v in details.items():
                        print(f"      {k}: {v}")
        print()
    else:
        print("Нет событий пропуска (skip) - возможно, проблема в стратегии.")
        print()
    
    # Анализ открытых позиций
    print("-" * 80)
    print("АНАЛИЗ ОТКРЫТЫХ ПОЗИЦИЙ")
    print("-" * 80)
    
    if decisions:
        latest = decisions[-1]
        open_positions = latest.get("open_positions", 0)
        print(f"Открытых позиций: {open_positions}")
        
        if open_positions == 0:
            print("⚠️  Нет открытых позиций - поэтому нет продаж.")
            print("   Проблема в отсутствии покупок.")
        else:
            print(f"✓ Есть {open_positions} открытых позиций.")
            print("  Проверьте, почему нет сигналов SELL.")
        print()
    
    # Рекомендации
    print("-" * 80)
    print("РЕКОМЕНДАЦИИ")
    print("-" * 80)
    
    recommendations = []
    
    # Проверка фильтров
    if skip_reasons.get("rsi_too_high_for_buy", 0) > 0:
        recommendations.append(
            "🔧 Фильтр RSI_MAX_BUY=65 слишком строгий. "
            "Символы MTSS, IRAO, VTBR блокируются при RSI 65-68, хотя имеют хорошие сигналы. "
            "Рекомендация: увеличить RSI_MAX_BUY до 68 или снизить MACD_OVERRIDE_FOR_HIGH_RSI до 0.3"
        )
    
    if skip_reasons.get("low_macd_hist_atr_ratio", 0) > 0:
        recommendations.append(
            "🔧 Фильтр MIN_MACD_HIST_ATR_RATIO_BUY=-0.1 слишком строгий. "
            "RNFT блокируется при ratio=-0.12 (очень близко к порогу). "
            "Рекомендация: снизить до -0.15 или -0.2"
        )
    
    if len(buy_signals) == 0 and len(hold_signals) > 0:
        recommendations.append(
            "⚠️  Стратегия не генерирует сигналы BUY для большинства символов. "
            "Возможные причины:"
        )
        recommendations.append("   1. Рынок в боковом тренде (sideways) - стратегия не покупает")
        recommendations.append("   2. MIN_CONF_BUY=0.62 слишком высокий порог")
        recommendations.append("   3. Требования стратегии слишком строгие")
        recommendations.append("   Рекомендация: снизить MIN_CONF_BUY до 0.55-0.58")
    
    if len(hold_signals) > len(buy_signals) * 10:
        recommendations.append(
            "⚠️  Слишком много сигналов HOLD. "
            "Стратегия слишком консервативна. "
            "Рекомендация: проверить логику стратегии или снизить пороги confidence."
        )
    
    if not recommendations:
        recommendations.append("✓ Не найдено очевидных проблем. Проверьте логи стратегии.")
    
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec}")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    import os
    
    log_path = os.path.join("audit_logs", "trades_audit.jsonl")
    
    if len(sys.argv) > 1:
        start_time = sys.argv[1]
    else:
        start_time = "2026-01-15T01:22:35Z"
    
    analyze_inactivity(log_path, start_time)


"""
Анализ причин бездействия бота.

Анализирует логи с указанного времени и выявляет:
1. Почему нет покупок (какие фильтры блокируют)
2. Почему нет продаж (нет позиций или другие причины)
3. Рекомендации по исправлению
"""

import sys
import json
from datetime import datetime
from collections import defaultdict

# Настройка кодировки для Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def analyze_inactivity(log_path: str, start_time: str):
    """
    Анализирует логи с указанного времени.
    
    Args:
        log_path: Путь к trades_audit.jsonl
        start_time: UTC время начала анализа (формат: "2026-01-15T01:22:35Z")
    """
    print("=" * 80)
    print("АНАЛИЗ ПРИЧИН БЕЗДЕЙСТВИЯ БОТА")
    print("=" * 80)
    print(f"Начало анализа: {start_time}")
    print()
    
    # Парсим время начала
    try:
        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    except Exception:
        print(f"ERROR: Неверный формат времени: {start_time}")
        print("Ожидается формат: 2026-01-15T01:22:35Z")
        return
    
    # Читаем логи
    decisions = []
    skips = []
    trades = []
    
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    event = json.loads(line.strip())
                    ts_str = event.get("ts_utc", "")
                    if not ts_str:
                        continue
                    
                    try:
                        event_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    except Exception:
                        continue
                    
                    if event_dt < start_dt:
                        continue
                    
                    event_type = event.get("event", "")
                    
                    if event_type == "decision":
                        decisions.append(event)
                    elif event_type == "skip":
                        skips.append(event)
                    elif event_type == "trade":
                        trades.append(event)
                except Exception:
                    continue
    except FileNotFoundError:
        print(f"ERROR: Файл не найден: {log_path}")
        return
    
    print(f"Найдено событий:")
    print(f"  - Решений (decision): {len(decisions)}")
    print(f"  - Пропусков (skip): {len(skips)}")
    print(f"  - Сделок (trade): {len(trades)}")
    print()
    
    if len(trades) > 0:
        print("⚠️  ВНИМАНИЕ: Найдены сделки после указанного времени!")
        print("Возможно, проблема была временной или уже решена.")
        print()
    
    # Анализ решений
    print("-" * 80)
    print("АНАЛИЗ РЕШЕНИЙ (decision events)")
    print("-" * 80)
    
    buy_signals = [d for d in decisions if d.get("details", {}).get("strategy_should_buy") == True]
    sell_signals = [d for d in decisions if d.get("details", {}).get("strategy_should_sell") == True]
    hold_signals = [d for d in decisions if d.get("details", {}).get("strategy_should_buy") == False and d.get("details", {}).get("strategy_should_sell") == False]
    
    print(f"Сигналов BUY от стратегии: {len(buy_signals)}")
    print(f"Сигналов SELL от стратегии: {len(sell_signals)}")
    print(f"Сигналов HOLD (нет действий): {len(hold_signals)}")
    print()
    
    # Анализ confidence
    conf_values = [float(d.get("confidence", 0) or 0) for d in decisions]
    if conf_values:
        avg_conf = sum(conf_values) / len(conf_values)
        max_conf = max(conf_values)
        min_conf = min(conf_values)
        print(f"Confidence статистика:")
        print(f"  Средний: {avg_conf:.3f}")
        print(f"  Максимум: {max_conf:.3f}")
        print(f"  Минимум: {min_conf:.3f}")
        print()
    
    # Символы с BUY сигналами
    if buy_signals:
        print("Символы с сигналами BUY (но не куплены):")
        buy_by_symbol = defaultdict(list)
        for b in buy_signals:
            sym = b.get("symbol", "")
            buy_by_symbol[sym].append(b)
        
        for sym, events in buy_by_symbol.items():
            latest = events[-1]
            conf = float(latest.get("confidence", 0) or 0)
            rsi = latest.get("rsi")
            trend = latest.get("trend", "")
            macd_hist = latest.get("macd_hist", 0)
            print(f"  {sym}: confidence={conf:.2f}, RSI={rsi:.1f}, trend={trend}, macd_hist={macd_hist:.4f}")
        print()
    
    # Анализ пропусков
    print("-" * 80)
    print("АНАЛИЗ ПРОПУСКОВ (skip events)")
    print("-" * 80)
    
    skip_reasons = defaultdict(int)
    skip_details = defaultdict(list)
    
    for skip in skips:
        reason = skip.get("skip_reason", "unknown")
        skip_reasons[reason] += 1
        skip_details[reason].append(skip)
    
    if skip_reasons:
        print("Причины пропуска сделок:")
        for reason, count in sorted(skip_reasons.items(), key=lambda x: -x[1]):
            print(f"  {reason}: {count} раз(а)")
            
            # Показываем детали для важных причин
            if reason in ["rsi_too_high_for_buy", "low_macd_hist_atr_ratio", "sideways_negative_macd"]:
                examples = skip_details[reason][:3]
                for ex in examples:
                    sym = ex.get("symbol", "")
                    details = ex.get("details", {})
                    print(f"    Пример: {sym}")
                    for k, v in details.items():
                        print(f"      {k}: {v}")
        print()
    else:
        print("Нет событий пропуска (skip) - возможно, проблема в стратегии.")
        print()
    
    # Анализ открытых позиций
    print("-" * 80)
    print("АНАЛИЗ ОТКРЫТЫХ ПОЗИЦИЙ")
    print("-" * 80)
    
    if decisions:
        latest = decisions[-1]
        open_positions = latest.get("open_positions", 0)
        print(f"Открытых позиций: {open_positions}")
        
        if open_positions == 0:
            print("⚠️  Нет открытых позиций - поэтому нет продаж.")
            print("   Проблема в отсутствии покупок.")
        else:
            print(f"✓ Есть {open_positions} открытых позиций.")
            print("  Проверьте, почему нет сигналов SELL.")
        print()
    
    # Рекомендации
    print("-" * 80)
    print("РЕКОМЕНДАЦИИ")
    print("-" * 80)
    
    recommendations = []
    
    # Проверка фильтров
    if skip_reasons.get("rsi_too_high_for_buy", 0) > 0:
        recommendations.append(
            "🔧 Фильтр RSI_MAX_BUY=65 слишком строгий. "
            "Символы MTSS, IRAO, VTBR блокируются при RSI 65-68, хотя имеют хорошие сигналы. "
            "Рекомендация: увеличить RSI_MAX_BUY до 68 или снизить MACD_OVERRIDE_FOR_HIGH_RSI до 0.3"
        )
    
    if skip_reasons.get("low_macd_hist_atr_ratio", 0) > 0:
        recommendations.append(
            "🔧 Фильтр MIN_MACD_HIST_ATR_RATIO_BUY=-0.1 слишком строгий. "
            "RNFT блокируется при ratio=-0.12 (очень близко к порогу). "
            "Рекомендация: снизить до -0.15 или -0.2"
        )
    
    if len(buy_signals) == 0 and len(hold_signals) > 0:
        recommendations.append(
            "⚠️  Стратегия не генерирует сигналы BUY для большинства символов. "
            "Возможные причины:"
        )
        recommendations.append("   1. Рынок в боковом тренде (sideways) - стратегия не покупает")
        recommendations.append("   2. MIN_CONF_BUY=0.62 слишком высокий порог")
        recommendations.append("   3. Требования стратегии слишком строгие")
        recommendations.append("   Рекомендация: снизить MIN_CONF_BUY до 0.55-0.58")
    
    if len(hold_signals) > len(buy_signals) * 10:
        recommendations.append(
            "⚠️  Слишком много сигналов HOLD. "
            "Стратегия слишком консервативна. "
            "Рекомендация: проверить логику стратегии или снизить пороги confidence."
        )
    
    if not recommendations:
        recommendations.append("✓ Не найдено очевидных проблем. Проверьте логи стратегии.")
    
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec}")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    import os
    
    log_path = os.path.join("audit_logs", "trades_audit.jsonl")
    
    if len(sys.argv) > 1:
        start_time = sys.argv[1]
    else:
        start_time = "2026-01-15T01:22:35Z"
    
    analyze_inactivity(log_path, start_time)


"""
Анализ причин бездействия бота.

Анализирует логи с указанного времени и выявляет:
1. Почему нет покупок (какие фильтры блокируют)
2. Почему нет продаж (нет позиций или другие причины)
3. Рекомендации по исправлению
"""

import sys
import json
from datetime import datetime
from collections import defaultdict

# Настройка кодировки для Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def analyze_inactivity(log_path: str, start_time: str):
    """
    Анализирует логи с указанного времени.
    
    Args:
        log_path: Путь к trades_audit.jsonl
        start_time: UTC время начала анализа (формат: "2026-01-15T01:22:35Z")
    """
    print("=" * 80)
    print("АНАЛИЗ ПРИЧИН БЕЗДЕЙСТВИЯ БОТА")
    print("=" * 80)
    print(f"Начало анализа: {start_time}")
    print()
    
    # Парсим время начала
    try:
        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    except Exception:
        print(f"ERROR: Неверный формат времени: {start_time}")
        print("Ожидается формат: 2026-01-15T01:22:35Z")
        return
    
    # Читаем логи
    decisions = []
    skips = []
    trades = []
    
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    event = json.loads(line.strip())
                    ts_str = event.get("ts_utc", "")
                    if not ts_str:
                        continue
                    
                    try:
                        event_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    except Exception:
                        continue
                    
                    if event_dt < start_dt:
                        continue
                    
                    event_type = event.get("event", "")
                    
                    if event_type == "decision":
                        decisions.append(event)
                    elif event_type == "skip":
                        skips.append(event)
                    elif event_type == "trade":
                        trades.append(event)
                except Exception:
                    continue
    except FileNotFoundError:
        print(f"ERROR: Файл не найден: {log_path}")
        return
    
    print(f"Найдено событий:")
    print(f"  - Решений (decision): {len(decisions)}")
    print(f"  - Пропусков (skip): {len(skips)}")
    print(f"  - Сделок (trade): {len(trades)}")
    print()
    
    if len(trades) > 0:
        print("⚠️  ВНИМАНИЕ: Найдены сделки после указанного времени!")
        print("Возможно, проблема была временной или уже решена.")
        print()
    
    # Анализ решений
    print("-" * 80)
    print("АНАЛИЗ РЕШЕНИЙ (decision events)")
    print("-" * 80)
    
    buy_signals = [d for d in decisions if d.get("details", {}).get("strategy_should_buy") == True]
    sell_signals = [d for d in decisions if d.get("details", {}).get("strategy_should_sell") == True]
    hold_signals = [d for d in decisions if d.get("details", {}).get("strategy_should_buy") == False and d.get("details", {}).get("strategy_should_sell") == False]
    
    print(f"Сигналов BUY от стратегии: {len(buy_signals)}")
    print(f"Сигналов SELL от стратегии: {len(sell_signals)}")
    print(f"Сигналов HOLD (нет действий): {len(hold_signals)}")
    print()
    
    # Анализ confidence
    conf_values = [float(d.get("confidence", 0) or 0) for d in decisions]
    if conf_values:
        avg_conf = sum(conf_values) / len(conf_values)
        max_conf = max(conf_values)
        min_conf = min(conf_values)
        print(f"Confidence статистика:")
        print(f"  Средний: {avg_conf:.3f}")
        print(f"  Максимум: {max_conf:.3f}")
        print(f"  Минимум: {min_conf:.3f}")
        print()
    
    # Символы с BUY сигналами
    if buy_signals:
        print("Символы с сигналами BUY (но не куплены):")
        buy_by_symbol = defaultdict(list)
        for b in buy_signals:
            sym = b.get("symbol", "")
            buy_by_symbol[sym].append(b)
        
        for sym, events in buy_by_symbol.items():
            latest = events[-1]
            conf = float(latest.get("confidence", 0) or 0)
            rsi = latest.get("rsi")
            trend = latest.get("trend", "")
            macd_hist = latest.get("macd_hist", 0)
            print(f"  {sym}: confidence={conf:.2f}, RSI={rsi:.1f}, trend={trend}, macd_hist={macd_hist:.4f}")
        print()
    
    # Анализ пропусков
    print("-" * 80)
    print("АНАЛИЗ ПРОПУСКОВ (skip events)")
    print("-" * 80)
    
    skip_reasons = defaultdict(int)
    skip_details = defaultdict(list)
    
    for skip in skips:
        reason = skip.get("skip_reason", "unknown")
        skip_reasons[reason] += 1
        skip_details[reason].append(skip)
    
    if skip_reasons:
        print("Причины пропуска сделок:")
        for reason, count in sorted(skip_reasons.items(), key=lambda x: -x[1]):
            print(f"  {reason}: {count} раз(а)")
            
            # Показываем детали для важных причин
            if reason in ["rsi_too_high_for_buy", "low_macd_hist_atr_ratio", "sideways_negative_macd"]:
                examples = skip_details[reason][:3]
                for ex in examples:
                    sym = ex.get("symbol", "")
                    details = ex.get("details", {})
                    print(f"    Пример: {sym}")
                    for k, v in details.items():
                        print(f"      {k}: {v}")
        print()
    else:
        print("Нет событий пропуска (skip) - возможно, проблема в стратегии.")
        print()
    
    # Анализ открытых позиций
    print("-" * 80)
    print("АНАЛИЗ ОТКРЫТЫХ ПОЗИЦИЙ")
    print("-" * 80)
    
    if decisions:
        latest = decisions[-1]
        open_positions = latest.get("open_positions", 0)
        print(f"Открытых позиций: {open_positions}")
        
        if open_positions == 0:
            print("⚠️  Нет открытых позиций - поэтому нет продаж.")
            print("   Проблема в отсутствии покупок.")
        else:
            print(f"✓ Есть {open_positions} открытых позиций.")
            print("  Проверьте, почему нет сигналов SELL.")
        print()
    
    # Рекомендации
    print("-" * 80)
    print("РЕКОМЕНДАЦИИ")
    print("-" * 80)
    
    recommendations = []
    
    # Проверка фильтров
    if skip_reasons.get("rsi_too_high_for_buy", 0) > 0:
        recommendations.append(
            "🔧 Фильтр RSI_MAX_BUY=65 слишком строгий. "
            "Символы MTSS, IRAO, VTBR блокируются при RSI 65-68, хотя имеют хорошие сигналы. "
            "Рекомендация: увеличить RSI_MAX_BUY до 68 или снизить MACD_OVERRIDE_FOR_HIGH_RSI до 0.3"
        )
    
    if skip_reasons.get("low_macd_hist_atr_ratio", 0) > 0:
        recommendations.append(
            "🔧 Фильтр MIN_MACD_HIST_ATR_RATIO_BUY=-0.1 слишком строгий. "
            "RNFT блокируется при ratio=-0.12 (очень близко к порогу). "
            "Рекомендация: снизить до -0.15 или -0.2"
        )
    
    if len(buy_signals) == 0 and len(hold_signals) > 0:
        recommendations.append(
            "⚠️  Стратегия не генерирует сигналы BUY для большинства символов. "
            "Возможные причины:"
        )
        recommendations.append("   1. Рынок в боковом тренде (sideways) - стратегия не покупает")
        recommendations.append("   2. MIN_CONF_BUY=0.62 слишком высокий порог")
        recommendations.append("   3. Требования стратегии слишком строгие")
        recommendations.append("   Рекомендация: снизить MIN_CONF_BUY до 0.55-0.58")
    
    if len(hold_signals) > len(buy_signals) * 10:
        recommendations.append(
            "⚠️  Слишком много сигналов HOLD. "
            "Стратегия слишком консервативна. "
            "Рекомендация: проверить логику стратегии или снизить пороги confidence."
        )
    
    if not recommendations:
        recommendations.append("✓ Не найдено очевидных проблем. Проверьте логи стратегии.")
    
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec}")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    import os
    
    log_path = os.path.join("audit_logs", "trades_audit.jsonl")
    
    if len(sys.argv) > 1:
        start_time = sys.argv[1]
    else:
        start_time = "2026-01-15T01:22:35Z"
    
    analyze_inactivity(log_path, start_time)






