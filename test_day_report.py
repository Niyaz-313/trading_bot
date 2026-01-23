#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест метода get_day_report_text с детализацией по символам
"""

import os
import sys
from datetime import datetime, date
from zoneinfo import ZoneInfo

# Добавляем путь к модулям
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from main import TradingBot
    from config import LOCAL_TIMEZONE
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    sys.exit(1)

def test_day_report():
    """Тестирует метод get_day_report_text"""
    print("Тестирование метода get_day_report_text...")
    print("=" * 80)
    
    # Создаем экземпляр бота
    try:
        bot = TradingBot()
    except Exception as e:
        print(f"Ошибка создания бота: {e}")
        print("Проверьте настройки в .env файле")
        return False
    
    # Тестируем отчет за сегодня
    today = datetime.now(ZoneInfo(LOCAL_TIMEZONE)).date()
    today_str = today.isoformat()
    
    print(f"\nГенерация отчета за {today_str}...")
    try:
        report = bot.get_day_report_text(today_str)
        print("\n" + "=" * 80)
        print("ОТЧЕТ:")
        print("=" * 80)
        print(report)
        print("=" * 80)
        
        # Проверяем наличие детализации по символам
        if "*Детализация по символам:*" in report:
            print("\n✅ Детализация по символам найдена в отчете!")
        else:
            print("\n⚠️ Детализация по символам не найдена (возможно, нет сделок за сегодня)")
        
        # Проверяем наличие основных метрик
        checks = [
            ("Equity старт" in report or "Equity конец" in report, "Метрики equity"),
            ("Реализованный P/L" in report, "Реализованный P/L"),
            ("Сделок:" in report, "Количество сделок"),
        ]
        
        print("\nПроверка наличия ключевых элементов:")
        all_ok = True
        for check, name in checks:
            if check:
                print(f"  ✅ {name}")
            else:
                print(f"  ❌ {name} - НЕ НАЙДЕНО")
                all_ok = False
        
        if all_ok:
            print("\n✅ Все проверки пройдены!")
            return True
        else:
            print("\n⚠️ Некоторые проверки не пройдены")
            return False
            
    except Exception as e:
        print(f"\n❌ Ошибка при генерации отчета: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_day_report()
    sys.exit(0 if success else 1)

