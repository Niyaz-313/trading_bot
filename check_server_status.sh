#!/bin/bash
# Проверка статуса сервера после разрешения конфликтов

cd /home/botuser/trading_bot/trading_bot

echo "========================================="
echo "ПРОВЕРКА СТАТУСА СЕРВЕРА"
echo "========================================="
echo

# 1. Проверка Git статуса
echo "[1/5] Проверка Git статуса..."
git status --short
if [ $? -eq 0 ]; then
    echo "  ✓ Git статус OK"
else
    echo "  ✗ Проблемы с Git"
fi
echo

# 2. Проверка наличия audit-логов
echo "[2/5] Проверка audit-логов..."
if [ -f "audit_logs/trades_audit.jsonl" ]; then
    JSONL_SIZE=$(stat -c%s "audit_logs/trades_audit.jsonl" 2>/dev/null || echo "0")
    JSONL_LINES=$(wc -l < "audit_logs/trades_audit.jsonl" 2>/dev/null || echo "0")
    echo "  ✓ JSONL существует: $JSONL_SIZE байт, $JSONL_LINES строк"
else
    echo "  ✗ JSONL не найден"
fi

if [ -f "audit_logs/trades_audit.csv" ]; then
    CSV_SIZE=$(stat -c%s "audit_logs/trades_audit.csv" 2>/dev/null || echo "0")
    CSV_LINES=$(wc -l < "audit_logs/trades_audit.csv" 2>/dev/null || echo "0")
    echo "  ✓ CSV существует: $CSV_SIZE байт, $CSV_LINES строк"
else
    echo "  ✗ CSV не найден"
fi
echo

# 3. Проверка прав доступа
echo "[3/5] Проверка прав доступа..."
if [ -w "audit_logs/trades_audit.jsonl" ]; then
    echo "  ✓ JSONL записываемый"
else
    echo "  ✗ JSONL НЕ записываемый"
fi

if [ -w "audit_logs/trades_audit.csv" ]; then
    echo "  ✓ CSV записываемый"
else
    echo "  ✗ CSV НЕ записываемый"
fi
echo

# 4. Тест записи в audit-лог
echo "[4/5] Тест записи в audit-лог..."
if [ -f "test_audit_write.py" ]; then
    python test_audit_write.py
    if [ $? -eq 0 ]; then
        echo "  ✓ Тест записи пройден"
    else
        echo "  ✗ Тест записи провален"
    fi
else
    echo "  ⚠ test_audit_write.py не найден (это нормально, если не был загружен)"
fi
echo

# 5. Проверка статуса бота
echo "[5/5] Проверка статуса бота..."
if systemctl is-active --quiet trading-bot.service; then
    echo "  ✓ Бот работает (active)"
    systemctl status trading-bot.service --no-pager -l | head -10
elif systemctl is-enabled --quiet trading-bot.service; then
    echo "  ⚠ Бот не запущен, но включён в автозагрузку"
    echo "  Запуск: sudo systemctl start trading-bot.service"
else
    echo "  ⚠ Сервис не настроен"
fi
echo

# 6. Последние записи в audit-логе
echo "[6/6] Последние 3 записи в audit-логе (JSONL):"
if [ -f "audit_logs/trades_audit.jsonl" ]; then
    tail -3 "audit_logs/trades_audit.jsonl" | while read line; do
        if [ -n "$line" ]; then
            echo "  $line" | python -m json.tool 2>/dev/null | head -5 || echo "  $line"
        fi
    done
else
    echo "  ⚠ Файл не найден"
fi

echo
echo "========================================="
echo "ПРОВЕРКА ЗАВЕРШЕНА"
echo "========================================="




