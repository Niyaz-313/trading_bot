#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Полная проверка здоровья бота:
- Свежесть логов и audit-данных
- Работа бота
- Принятие решений
- Ошибки
"""

import os
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

MSK = timezone(timedelta(hours=3))
NOW_MSK = datetime.now(MSK)
NOW_UTC = datetime.now(timezone.utc)

print("=" * 70)
print("ПОЛНАЯ ПРОВЕРКА ЗДОРОВЬЯ БОТА")
print("=" * 70)
print(f"Время проверки (MSK): {NOW_MSK.strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Пути к файлам
BASE_DIR = Path(__file__).parent
AUDIT_JSONL = BASE_DIR / "audit_logs" / "trades_audit.jsonl"
AUDIT_CSV = BASE_DIR / "audit_logs" / "trades_audit.csv"
LOG_FILE = BASE_DIR / "logs" / "trading_bot.log"
ERROR_LOG = BASE_DIR / "logs" / "bot_error.log"

# ==========================================
# 1. ПРОВЕРКА СВЕЖЕСТИ AUDIT-ЛОГОВ
# ==========================================
print("[1/6] ПРОВЕРКА СВЕЖЕСТИ AUDIT-ЛОГОВ")
print("-" * 70)

if AUDIT_JSONL.exists():
    jsonl_size = AUDIT_JSONL.stat().st_size
    jsonl_mtime = datetime.fromtimestamp(AUDIT_JSONL.stat().st_mtime, tz=MSK)
    jsonl_age_min = (NOW_MSK - jsonl_mtime).total_seconds() / 60
    
    # Читаем последние 5 строк
    with open(AUDIT_JSONL, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        last_lines = lines[-5:] if len(lines) >= 5 else lines
    
    last_event_time = None
    if last_lines:
        try:
            last_line = last_lines[-1].strip()
            if last_line:
                event = json.loads(last_line)
                ts_utc = event.get('ts_utc', '')
                if ts_utc:
                    last_event_time = datetime.fromisoformat(ts_utc.replace('Z', '+00:00'))
                    last_event_time_msk = last_event_time.astimezone(MSK)
                    age_min = (NOW_MSK - last_event_time_msk).total_seconds() / 60
                    print(f"  ✓ JSONL: {jsonl_size:,} байт")
                    print(f"    Последнее событие: {last_event_time_msk.strftime('%Y-%m-%d %H:%M:%S')} MSK")
                    print(f"    Возраст последнего события: {age_min:.1f} минут")
                    if age_min > 10:
                        print(f"    ⚠ ВНИМАНИЕ: Последнее событие было более 10 минут назад!")
                    else:
                        print(f"    ✓ Данные свежие")
        except Exception as e:
            print(f"  ⚠ Ошибка чтения последнего события: {e}")
    
    # Подсчитываем события за последний час
    events_last_hour = 0
    events_today = 0
    trades_last_hour = 0
    trades_today = 0
    cycles_last_hour = 0
    decisions_last_hour = 0
    
    try:
        with open(AUDIT_JSONL, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    ts_utc = event.get('ts_utc', '')
                    if ts_utc:
                        event_time = datetime.fromisoformat(ts_utc.replace('Z', '+00:00'))
                        event_time_msk = event_time.astimezone(MSK)
                        
                        # За последний час
                        if (NOW_MSK - event_time_msk).total_seconds() < 3600:
                            events_last_hour += 1
                            if event.get('event') == 'trade':
                                trades_last_hour += 1
                            elif event.get('event') == 'cycle':
                                cycles_last_hour += 1
                            elif event.get('event') == 'decision':
                                decisions_last_hour += 1
                        
                        # За сегодня
                        if event_time_msk.date() == NOW_MSK.date():
                            events_today += 1
                            if event.get('event') == 'trade':
                                trades_today += 1
                except Exception:
                    continue
    except Exception as e:
        print(f"  ⚠ Ошибка подсчёта событий: {e}")
    
    print(f"    Событий за последний час: {events_last_hour}")
    print(f"      - циклов (cycle): {cycles_last_hour}")
    print(f"      - решений (decision): {decisions_last_hour}")
    print(f"      - сделок (trade): {trades_last_hour}")
    print(f"    Событий за сегодня: {events_today} (сделок: {trades_today})")
else:
    print(f"  ✗ JSONL файл не найден: {AUDIT_JSONL}")

if AUDIT_CSV.exists():
    csv_size = AUDIT_CSV.stat().st_size
    csv_mtime = datetime.fromtimestamp(AUDIT_CSV.stat().st_mtime, tz=MSK)
    csv_age_min = (NOW_MSK - csv_mtime).total_seconds() / 60
    print(f"  ✓ CSV: {csv_size:,} байт, изменён {csv_age_min:.1f} минут назад")
else:
    print(f"  ✗ CSV файл не найден: {AUDIT_CSV}")

print()

# ==========================================
# 2. ПРОВЕРКА ЛОГОВ
# ==========================================
print("[2/6] ПРОВЕРКА ЛОГОВ")
print("-" * 70)

if LOG_FILE.exists():
    log_size = LOG_FILE.stat().st_size
    log_mtime = datetime.fromtimestamp(LOG_FILE.stat().st_mtime, tz=MSK)
    log_age_min = (NOW_MSK - log_mtime).total_seconds() / 60
    
    print(f"  ✓ trading_bot.log: {log_size:,} байт, изменён {log_age_min:.1f} минут назад")
    
    # Читаем последние 50 строк и ищем ошибки
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        last_lines = lines[-50:] if len(lines) >= 50 else lines
    
    errors = []
    warnings = []
    for line in last_lines:
        if 'ERROR' in line or 'CRITICAL' in line:
            errors.append(line.strip())
        elif 'WARNING' in line:
            warnings.append(line.strip())
    
    if errors:
        print(f"  ⚠ Найдено ошибок в последних 50 строках: {len(errors)}")
        print("    Последние ошибки:")
        for err in errors[-5:]:
            print(f"      - {err[:100]}...")
    else:
        print(f"  ✓ Ошибок в последних 50 строках не найдено")
    
    if warnings:
        print(f"  ⚠ Найдено предупреждений: {len(warnings)}")
else:
    print(f"  ✗ Лог файл не найден: {LOG_FILE}")

if ERROR_LOG.exists():
    error_size = ERROR_LOG.stat().st_size
    if error_size > 0:
        print(f"  ⚠ bot_error.log: {error_size:,} байт (есть ошибки!)")
    else:
        print(f"  ✓ bot_error.log: пуст")
else:
    print(f"  ℹ bot_error.log не найден (это нормально, если нет ошибок)")

print()

# ==========================================
# 3. ПРОВЕРКА РЕШЕНИЙ О ПОКУПКЕ/ПРОДАЖЕ
# ==========================================
print("[3/6] ПРОВЕРКА РЕШЕНИЙ О ПОКУПКЕ/ПРОДАЖЕ")
print("-" * 70)

if AUDIT_JSONL.exists():
    decisions_buy = []
    decisions_sell = []
    trades_buy = []
    trades_sell = []
    
    try:
        with open(AUDIT_JSONL, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    ts_utc = event.get('ts_utc', '')
                    if not ts_utc:
                        continue
                    event_time = datetime.fromisoformat(ts_utc.replace('Z', '+00:00'))
                    event_time_msk = event_time.astimezone(MSK)
                    
                    # За последний час
                    if (NOW_MSK - event_time_msk).total_seconds() < 3600:
                        evt = event.get('event')
                        if evt == 'decision':
                            signal = event.get('signal', '')
                            if signal == 'buy':
                                decisions_buy.append((event_time_msk, event.get('symbol', 'N/A')))
                            elif signal == 'sell':
                                decisions_sell.append((event_time_msk, event.get('symbol', 'N/A')))
                        elif evt == 'trade':
                            action = event.get('action', '').upper()
                            if action == 'BUY':
                                trades_buy.append((event_time_msk, event.get('symbol', 'N/A')))
                            elif action == 'SELL':
                                trades_sell.append((event_time_msk, event.get('symbol', 'N/A')))
                except Exception:
                    continue
    except Exception as e:
        print(f"  ⚠ Ошибка чтения решений: {e}")
    
    print(f"  Решения за последний час:")
    print(f"    - BUY сигналов: {len(decisions_buy)}")
    if decisions_buy:
        print(f"      Последние:")
        for dt, sym in decisions_buy[-3:]:
            print(f"        {dt.strftime('%H:%M:%S')} - {sym}")
    print(f"    - SELL сигналов: {len(decisions_sell)}")
    if decisions_sell:
        print(f"      Последние:")
        for dt, sym in decisions_sell[-3:]:
            print(f"        {dt.strftime('%H:%M:%S')} - {sym}")
    
    print(f"  Сделки за последний час:")
    print(f"    - BUY: {len(trades_buy)}")
    if trades_buy:
        print(f"      Последние:")
        for dt, sym in trades_buy[-3:]:
            print(f"        {dt.strftime('%H:%M:%S')} - {sym}")
    print(f"    - SELL: {len(trades_sell)}")
    if trades_sell:
        print(f"      Последние:")
        for dt, sym in trades_sell[-3:]:
            print(f"        {dt.strftime('%H:%M:%S')} - {sym}")
    
    if len(decisions_buy) > 0 and len(trades_buy) == 0:
        print(f"  ⚠ ВНИМАНИЕ: Есть BUY сигналы, но нет сделок (возможно, блокируются фильтрами)")
    if len(decisions_sell) > 0 and len(trades_sell) == 0:
        print(f"  ⚠ ВНИМАНИЕ: Есть SELL сигналы, но нет сделок")

print()

# ==========================================
# 4. ПРОВЕРКА ОШИБОК В AUDIT-ЛОГЕ
# ==========================================
print("[4/6] ПРОВЕРКА ОШИБОК В AUDIT-ЛОГЕ")
print("-" * 70)

if AUDIT_JSONL.exists():
    skip_reasons = {}
    errors_found = []
    
    try:
        with open(AUDIT_JSONL, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    ts_utc = event.get('ts_utc', '')
                    if not ts_utc:
                        continue
                    event_time = datetime.fromisoformat(ts_utc.replace('Z', '+00:00'))
                    event_time_msk = event_time.astimezone(MSK)
                    
                    # За последний час
                    if (NOW_MSK - event_time_msk).total_seconds() < 3600:
                        if event.get('event') == 'skip':
                            reason = event.get('skip_reason', 'unknown')
                            skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
                except Exception:
                    continue
    except Exception as e:
        print(f"  ⚠ Ошибка чтения: {e}")
    
    if skip_reasons:
        print(f"  Причины пропуска за последний час:")
        for reason, count in sorted(skip_reasons.items(), key=lambda x: -x[1]):
            print(f"    - {reason}: {count} раз")
    else:
        print(f"  ✓ Пропусков за последний час нет")

print()

# ==========================================
# 5. ПРОВЕРКА СТАТУСА БОТА (systemd)
# ==========================================
print("[5/6] ПРОВЕРКА СТАТУСА БОТА (systemd)")
print("-" * 70)
print("  ℹ Для проверки статуса systemd выполните на сервере:")
print("    sudo systemctl status trading-bot.service --no-pager -l | head -20")
print()

# ==========================================
# 6. ИТОГОВАЯ ДИАГНОСТИКА
# ==========================================
print("[6/6] ИТОГОВАЯ ДИАГНОСТИКА")
print("-" * 70)

issues = []
warnings_list = []

# Проверка свежести данных
if AUDIT_JSONL.exists():
    if last_event_time:
        age_min = (NOW_MSK - last_event_time.astimezone(MSK)).total_seconds() / 60
        if age_min > 15:
            issues.append(f"Последнее событие в audit-логе было {age_min:.1f} минут назад (бот может быть остановлен)")

# Проверка активности
if cycles_last_hour == 0:
    issues.append("Нет циклов (cycle) за последний час - бот может быть остановлен")
elif cycles_last_hour < 5:
    warnings_list.append(f"Мало циклов за час: {cycles_last_hour} (ожидается ~12 при интервале 5 минут)")

# Проверка ошибок
if errors:
    issues.append(f"Найдено {len(errors)} ошибок в логах за последние 50 строк")

if issues:
    print("  ✗ ПРОБЛЕМЫ:")
    for issue in issues:
        print(f"    - {issue}")
else:
    print("  ✓ Критических проблем не обнаружено")

if warnings_list:
    print("  ⚠ ПРЕДУПРЕЖДЕНИЯ:")
    for warn in warnings_list:
        print(f"    - {warn}")

print()
print("=" * 70)
print("ПРОВЕРКА ЗАВЕРШЕНА")
print("=" * 70)



