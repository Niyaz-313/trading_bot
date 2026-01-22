#!/usr/bin/env python3
"""
Анализ производительности символов на основе Symbol Tracker.

Показывает:
1. Топ-10 лучших символов по win_rate
2. Топ-5 худших символов
3. Символы с "горячей" или "холодной" серией
4. Рекомендации по настройкам

Использование:
    python analyze_symbol_performance.py
"""

import sys
import os
import json
from datetime import datetime

# Настройка кодировки для Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Загружаем Symbol Tracker
try:
    from symbol_tracker import get_symbol_tracker
except ImportError:
    print("ERROR: Не удалось импортировать symbol_tracker.py")
    sys.exit(1)


def main():
    state_path = os.getenv("SYMBOL_TRACKER_STATE_PATH", "state/symbol_performance.json")
    
    print("=" * 70)
    print("АНАЛИЗ ПРОИЗВОДИТЕЛЬНОСТИ СИМВОЛОВ")
    print("=" * 70)
    print(f"State file: {state_path}")
    print()
    
    tracker = get_symbol_tracker(state_path)
    all_stats = tracker.get_all_stats()
    
    if not all_stats:
        print("Нет данных о производительности символов.")
        print("Данные появятся после того, как бот совершит несколько сделок.")
        return
    
    # Фильтруем символы с достаточным количеством сделок
    active_stats = [s for s in all_stats if s["recent_trades"] >= 2]
    all_trades_count = sum(s["recent_trades"] for s in all_stats)
    
    print(f"Всего символов с данными: {len(all_stats)}")
    print(f"Всего сделок за период: {all_trades_count}")
    print()
    
    # Сортируем по win_rate
    sorted_by_winrate = sorted(active_stats, key=lambda x: (x["win_rate"], x["avg_pnl"]), reverse=True)
    
    print("-" * 70)
    print("TOP-10 ЛУЧШИХ СИМВОЛОВ (по win_rate)")
    print("-" * 70)
    print(f"{'Symbol':<12} {'Win Rate':>10} {'Avg PnL':>12} {'Trades':>8} {'Streak':>8} {'Risk Factor':>12}")
    print("-" * 70)
    
    for i, s in enumerate(sorted_by_winrate[:10], 1):
        streak_str = f"+{s['streak']}" if s['streak'] > 0 else str(s['streak'])
        print(f"{s['symbol']:<12} {s['win_rate']*100:>9.1f}% {s['avg_pnl']:>12.2f} {s['recent_trades']:>8} {streak_str:>8} {s['risk_factor']:>12.2f}")
    
    print()
    print("-" * 70)
    print("TOP-5 ХУДШИХ СИМВОЛОВ (для внесения в NOISY_SYMBOLS)")
    print("-" * 70)
    
    worst = sorted_by_winrate[-5:][::-1] if len(sorted_by_winrate) >= 5 else sorted_by_winrate[::-1]
    
    for s in worst:
        streak_str = f"+{s['streak']}" if s['streak'] > 0 else str(s['streak'])
        status = "ЗАБЛОКИРОВАН" if s['win_rate'] < 0.25 and s['recent_trades'] >= 5 else ""
        print(f"{s['symbol']:<12} {s['win_rate']*100:>9.1f}% {s['avg_pnl']:>12.2f} {s['recent_trades']:>8} {streak_str:>8} {status}")
    
    print()
    
    # Символы на победной/проигрышной серии
    hot_streak = [s for s in all_stats if s["streak"] >= 3]
    cold_streak = [s for s in all_stats if s["streak"] <= -3]
    
    if hot_streak:
        print("-" * 70)
        print("ГОРЯЧАЯ СЕРИЯ (streak >= 3) - увеличен размер позиции")
        print("-" * 70)
        for s in hot_streak:
            print(f"  {s['symbol']}: {s['streak']} побед подряд, risk_factor={s['risk_factor']:.2f}")
    
    if cold_streak:
        print("-" * 70)
        print("ХОЛОДНАЯ СЕРИЯ (streak <= -3) - уменьшен размер позиции")
        print("-" * 70)
        for s in cold_streak:
            print(f"  {s['symbol']}: {abs(s['streak'])} убытков подряд, risk_factor={s['risk_factor']:.2f}")
    
    print()
    print("-" * 70)
    print("РЕКОМЕНДАЦИИ")
    print("-" * 70)
    
    # Формируем рекомендации
    very_bad = [s['symbol'] for s in all_stats if s['win_rate'] < 0.35 and s['recent_trades'] >= 3]
    if very_bad:
        print(f"Добавить в NOISY_SYMBOLS: {','.join(very_bad)}")
    
    very_good = [s['symbol'] for s in all_stats if s['win_rate'] > 0.65 and s['recent_trades'] >= 3]
    if very_good:
        print(f"Хорошие символы (можно убрать из NOISY_SYMBOLS): {','.join(very_good)}")
    
    # Общая статистика
    total_pnl = sum(s['total_pnl'] for s in all_stats)
    print()
    print(f"Общий P/L по всем символам: {total_pnl:+.2f} RUB")
    
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()



