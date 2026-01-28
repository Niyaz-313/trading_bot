#!/bin/bash
# Полная проверка здоровья бота на сервере

cd /home/botuser/trading_bot/trading_bot

echo "========================================="
echo "ПОЛНАЯ ПРОВЕРКА ЗДОРОВЬЯ БОТА"
echo "========================================="
echo

# 1. Статус systemd
echo "[1/6] Статус systemd сервиса..."
sudo systemctl status trading-bot.service --no-pager -l | head -15
echo

# 2. Проверка свежести audit-логов
echo "[2/6] Проверка свежести audit-логов..."
if [ -f "audit_logs/trades_audit.jsonl" ]; then
    JSONL_SIZE=$(stat -c%s "audit_logs/trades_audit.jsonl" 2>/dev/null || echo "0")
    JSONL_MTIME=$(stat -c%Y "audit_logs/trades_audit.jsonl" 2>/dev/null || echo "0")
    NOW=$(date +%s)
    JSONL_AGE=$(( (NOW - JSONL_MTIME) / 60 ))
    
    echo "  JSONL: $JSONL_SIZE байт, изменён $JSONL_AGE минут назад"
    
    # Последнее событие
    LAST_EVENT=$(tail -1 "audit_logs/trades_audit.jsonl" 2>/dev/null | python3 -c "import sys, json; e=json.load(sys.stdin); print(e.get('ts_utc', ''))" 2>/dev/null || echo "")
    if [ -n "$LAST_EVENT" ]; then
        echo "  Последнее событие: $LAST_EVENT"
    fi
else
    echo "  ✗ JSONL файл не найден"
fi

if [ -f "audit_logs/trades_audit.csv" ]; then
    CSV_SIZE=$(stat -c%s "audit_logs/trades_audit.csv" 2>/dev/null || echo "0")
    CSV_MTIME=$(stat -c%Y "audit_logs/trades_audit.csv" 2>/dev/null || echo "0")
    CSV_AGE=$(( (NOW - CSV_MTIME) / 60 ))
    echo "  CSV: $CSV_SIZE байт, изменён $CSV_AGE минут назад"
else
    echo "  ✗ CSV файл не найден"
fi
echo

# 3. Проверка логов на ошибки
echo "[3/6] Проверка логов на ошибки..."
if [ -f "logs/trading_bot.log" ]; then
    LOG_SIZE=$(stat -c%s "logs/trading_bot.log" 2>/dev/null || echo "0")
    LOG_MTIME=$(stat -c%Y "logs/trading_bot.log" 2>/dev/null || echo "0")
    LOG_AGE=$(( (NOW - LOG_MTIME) / 60 ))
    echo "  trading_bot.log: $LOG_SIZE байт, изменён $LOG_AGE минут назад"
    
    ERROR_COUNT=$(tail -100 "logs/trading_bot.log" 2>/dev/null | grep -i "error\|critical" | wc -l)
    if [ "$ERROR_COUNT" -gt 0 ]; then
        echo "  ⚠ Найдено ошибок в последних 100 строках: $ERROR_COUNT"
        echo "  Последние ошибки:"
        tail -100 "logs/trading_bot.log" 2>/dev/null | grep -i "error\|critical" | tail -5
    else
        echo "  ✓ Ошибок не найдено"
    fi
else
    echo "  ✗ Лог файл не найден"
fi
echo

# 4. Проверка решений и сделок
echo "[4/6] Проверка решений и сделок за последний час..."
if [ -f "audit_logs/trades_audit.jsonl" ]; then
    python3 check_bot_health_full.py 2>/dev/null || echo "  ⚠ Не удалось запустить Python скрипт"
fi
echo

# 5. Проверка активности бота
echo "[5/6] Проверка активности бота..."
CYCLE_COUNT=$(tail -1000 "audit_logs/trades_audit.jsonl" 2>/dev/null | grep -c '"event":"cycle"' || echo "0")
TRADE_COUNT=$(tail -1000 "audit_logs/trades_audit.jsonl" 2>/dev/null | grep -c '"event":"trade"' || echo "0")
DECISION_COUNT=$(tail -1000 "audit_logs/trades_audit.jsonl" 2>/dev/null | grep -c '"event":"decision"' || echo "0")

echo "  В последних 1000 событиях:"
echo "    - Циклов (cycle): $CYCLE_COUNT"
echo "    - Решений (decision): $DECISION_COUNT"
echo "    - Сделок (trade): $TRADE_COUNT"
echo

# 6. Итоговая диагностика
echo "[6/6] Итоговая диагностика..."
if [ "$LOG_AGE" -gt 15 ]; then
    echo "  ⚠ ВНИМАНИЕ: Лог не обновлялся $LOG_AGE минут - бот может быть остановлен"
fi

if [ "$CYCLE_COUNT" -eq 0 ]; then
    echo "  ⚠ ВНИМАНИЕ: Нет циклов в последних 1000 событиях"
fi

if [ "$ERROR_COUNT" -gt 0 ]; then
    echo "  ⚠ ВНИМАНИЕ: Найдены ошибки в логах"
fi

if [ "$LOG_AGE" -le 5 ] && [ "$CYCLE_COUNT" -gt 0 ] && [ "$ERROR_COUNT" -eq 0 ]; then
    echo "  ✓ Бот работает нормально"
fi

echo
echo "========================================="
echo "ПРОВЕРКА ЗАВЕРШЕНА"
echo "========================================="




