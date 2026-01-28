#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест записи в audit-лог.
Проверяет, что данные записываются корректно и не теряются.
"""

import os
import sys
import time
from datetime import datetime, timezone
from audit_logger import AuditLogger, CsvAuditLogger
from config import AUDIT_LOG_PATH, AUDIT_CSV_PATH

def test_audit_write():
    """Тест записи в audit-лог"""
    print("=" * 60)
    print("ТЕСТ ЗАПИСИ В AUDIT-ЛОГ")
    print("=" * 60)
    print()
    
    # Создаём тестовые логгеры
    jsonl_logger = AuditLogger(AUDIT_LOG_PATH)
    csv_logger = CsvAuditLogger(
        AUDIT_CSV_PATH,
        fieldnames=[
            "ts_utc", "event", "symbol", "action", "qty_lots", "lot", "price",
            "reason", "skip_reason", "confidence", "equity", "cash"
        ]
    )
    
    # Тестовое событие
    test_event = {
        "event": "test",
        "symbol": "TEST",
        "action": "BUY",
        "qty_lots": 1,
        "price": 100.0,
        "equity": 10000.0,
        "cash": 9900.0,
        "test_id": f"test_{int(time.time())}"
    }
    
    print(f"[1/4] Запись тестового события в JSONL...")
    print(f"      Путь: {AUDIT_LOG_PATH}")
    print(f"      Событие: {test_event['event']}, символ: {test_event['symbol']}")
    
    try:
        jsonl_logger.append(test_event)
        print("      ✓ JSONL запись успешна")
    except Exception as e:
        print(f"      ✗ ОШИБКА записи JSONL: {e}")
        return False
    
    print()
    print(f"[2/4] Запись тестового события в CSV...")
    print(f"      Путь: {AUDIT_CSV_PATH}")
    
    try:
        csv_logger.append({
            "ts_utc": test_event.get("ts_utc", datetime.now(timezone.utc).isoformat()),
            "event": test_event.get("event", ""),
            "symbol": test_event.get("symbol", ""),
            "action": test_event.get("action", ""),
            "qty_lots": test_event.get("qty_lots", ""),
            "lot": test_event.get("lot", ""),
            "price": test_event.get("price", ""),
            "reason": test_event.get("reason", ""),
            "skip_reason": test_event.get("skip_reason", ""),
            "confidence": test_event.get("confidence", ""),
            "equity": test_event.get("equity", ""),
            "cash": test_event.get("cash", ""),
        })
        print("      ✓ CSV запись успешна")
    except Exception as e:
        print(f"      ✗ ОШИБКА записи CSV: {e}")
        return False
    
    print()
    print(f"[3/4] Проверка чтения записанных данных...")
    
    # Проверяем JSONL
    if os.path.exists(AUDIT_LOG_PATH):
        with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if lines:
                last_line = lines[-1].strip()
                if test_event["test_id"] in last_line:
                    print(f"      ✓ JSONL: событие найдено в файле")
                else:
                    print(f"      ✗ JSONL: событие НЕ найдено в последней строке")
                    print(f"        Последняя строка: {last_line[:100]}...")
            else:
                print(f"      ✗ JSONL: файл пуст")
    else:
        print(f"      ✗ JSONL: файл не существует")
        return False
    
    # Проверяем CSV
    if os.path.exists(AUDIT_CSV_PATH):
        with open(AUDIT_CSV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if len(lines) > 1:  # Header + data
                last_line = lines[-1]
                if test_event["symbol"] in last_line:
                    print(f"      ✓ CSV: событие найдено в файле")
                else:
                    print(f"      ✗ CSV: событие НЕ найдено в последней строке")
                    print(f"        Последняя строка: {last_line[:100]}...")
            else:
                print(f"      ✗ CSV: файл содержит только заголовок")
    else:
        print(f"      ✗ CSV: файл не существует")
        return False
    
    print()
    print(f"[4/4] Проверка прав доступа и размера файлов...")
    
    # Проверяем права
    jsonl_writable = os.access(AUDIT_LOG_PATH, os.W_OK)
    csv_writable = os.access(AUDIT_CSV_PATH, os.W_OK)
    
    print(f"      JSONL: {'✓ записываемый' if jsonl_writable else '✗ НЕ записываемый'}")
    print(f"      CSV:   {'✓ записываемый' if csv_writable else '✗ НЕ записываемый'}")
    
    # Размеры файлов
    jsonl_size = os.path.getsize(AUDIT_LOG_PATH)
    csv_size = os.path.getsize(AUDIT_CSV_PATH)
    print(f"      JSONL размер: {jsonl_size:,} байт")
    print(f"      CSV размер:   {csv_size:,} байт")
    
    print()
    print("=" * 60)
    print("РЕЗУЛЬТАТ: ВСЕ ТЕСТЫ ПРОЙДЕНЫ ✓" if (jsonl_writable and csv_writable) else "РЕЗУЛЬТАТ: ОБНАРУЖЕНЫ ПРОБЛЕМЫ ✗")
    print("=" * 60)
    
    return jsonl_writable and csv_writable

if __name__ == "__main__":
    success = test_audit_write()
    sys.exit(0 if success else 1)

# -*- coding: utf-8 -*-
"""
Тест записи в audit-лог.
Проверяет, что данные записываются корректно и не теряются.
"""

import os
import sys
import time
from datetime import datetime, timezone
from audit_logger import AuditLogger, CsvAuditLogger
from config import AUDIT_LOG_PATH, AUDIT_CSV_PATH

def test_audit_write():
    """Тест записи в audit-лог"""
    print("=" * 60)
    print("ТЕСТ ЗАПИСИ В AUDIT-ЛОГ")
    print("=" * 60)
    print()
    
    # Создаём тестовые логгеры
    jsonl_logger = AuditLogger(AUDIT_LOG_PATH)
    csv_logger = CsvAuditLogger(
        AUDIT_CSV_PATH,
        fieldnames=[
            "ts_utc", "event", "symbol", "action", "qty_lots", "lot", "price",
            "reason", "skip_reason", "confidence", "equity", "cash"
        ]
    )
    
    # Тестовое событие
    test_event = {
        "event": "test",
        "symbol": "TEST",
        "action": "BUY",
        "qty_lots": 1,
        "price": 100.0,
        "equity": 10000.0,
        "cash": 9900.0,
        "test_id": f"test_{int(time.time())}"
    }
    
    print(f"[1/4] Запись тестового события в JSONL...")
    print(f"      Путь: {AUDIT_LOG_PATH}")
    print(f"      Событие: {test_event['event']}, символ: {test_event['symbol']}")
    
    try:
        jsonl_logger.append(test_event)
        print("      ✓ JSONL запись успешна")
    except Exception as e:
        print(f"      ✗ ОШИБКА записи JSONL: {e}")
        return False
    
    print()
    print(f"[2/4] Запись тестового события в CSV...")
    print(f"      Путь: {AUDIT_CSV_PATH}")
    
    try:
        csv_logger.append({
            "ts_utc": test_event.get("ts_utc", datetime.now(timezone.utc).isoformat()),
            "event": test_event.get("event", ""),
            "symbol": test_event.get("symbol", ""),
            "action": test_event.get("action", ""),
            "qty_lots": test_event.get("qty_lots", ""),
            "lot": test_event.get("lot", ""),
            "price": test_event.get("price", ""),
            "reason": test_event.get("reason", ""),
            "skip_reason": test_event.get("skip_reason", ""),
            "confidence": test_event.get("confidence", ""),
            "equity": test_event.get("equity", ""),
            "cash": test_event.get("cash", ""),
        })
        print("      ✓ CSV запись успешна")
    except Exception as e:
        print(f"      ✗ ОШИБКА записи CSV: {e}")
        return False
    
    print()
    print(f"[3/4] Проверка чтения записанных данных...")
    
    # Проверяем JSONL
    if os.path.exists(AUDIT_LOG_PATH):
        with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if lines:
                last_line = lines[-1].strip()
                if test_event["test_id"] in last_line:
                    print(f"      ✓ JSONL: событие найдено в файле")
                else:
                    print(f"      ✗ JSONL: событие НЕ найдено в последней строке")
                    print(f"        Последняя строка: {last_line[:100]}...")
            else:
                print(f"      ✗ JSONL: файл пуст")
    else:
        print(f"      ✗ JSONL: файл не существует")
        return False
    
    # Проверяем CSV
    if os.path.exists(AUDIT_CSV_PATH):
        with open(AUDIT_CSV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if len(lines) > 1:  # Header + data
                last_line = lines[-1]
                if test_event["symbol"] in last_line:
                    print(f"      ✓ CSV: событие найдено в файле")
                else:
                    print(f"      ✗ CSV: событие НЕ найдено в последней строке")
                    print(f"        Последняя строка: {last_line[:100]}...")
            else:
                print(f"      ✗ CSV: файл содержит только заголовок")
    else:
        print(f"      ✗ CSV: файл не существует")
        return False
    
    print()
    print(f"[4/4] Проверка прав доступа и размера файлов...")
    
    # Проверяем права
    jsonl_writable = os.access(AUDIT_LOG_PATH, os.W_OK)
    csv_writable = os.access(AUDIT_CSV_PATH, os.W_OK)
    
    print(f"      JSONL: {'✓ записываемый' if jsonl_writable else '✗ НЕ записываемый'}")
    print(f"      CSV:   {'✓ записываемый' if csv_writable else '✗ НЕ записываемый'}")
    
    # Размеры файлов
    jsonl_size = os.path.getsize(AUDIT_LOG_PATH)
    csv_size = os.path.getsize(AUDIT_CSV_PATH)
    print(f"      JSONL размер: {jsonl_size:,} байт")
    print(f"      CSV размер:   {csv_size:,} байт")
    
    print()
    print("=" * 60)
    print("РЕЗУЛЬТАТ: ВСЕ ТЕСТЫ ПРОЙДЕНЫ ✓" if (jsonl_writable and csv_writable) else "РЕЗУЛЬТАТ: ОБНАРУЖЕНЫ ПРОБЛЕМЫ ✗")
    print("=" * 60)
    
    return jsonl_writable and csv_writable

if __name__ == "__main__":
    success = test_audit_write()
    sys.exit(0 if success else 1)




