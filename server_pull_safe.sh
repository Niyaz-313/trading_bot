#!/bin/bash
# Безопасный git pull с сохранением audit-логов на сервере

cd /home/botuser/trading_bot/trading_bot

echo "========================================="
echo "БЕЗОПАСНЫЙ GIT PULL (с сохранением логов)"
echo "========================================="
echo "Время: $(date)"
echo

# 1. Backup audit-логов
echo "[1/5] Создание backup audit-логов..."
BACKUP_DIR="audit_logs/backups"
mkdir -p "$BACKUP_DIR" 2>/dev/null || true

if [ -f "audit_logs/trades_audit.jsonl" ]; then
    cp audit_logs/trades_audit.jsonl "$BACKUP_DIR/trades_audit.jsonl.backup_$(date +%Y%m%d_%H%M%S)" 2>/dev/null || true
    echo "  ✓ JSONL backup создан"
fi

if [ -f "audit_logs/trades_audit.csv" ]; then
    cp audit_logs/trades_audit.csv "$BACKUP_DIR/trades_audit.csv.backup_$(date +%Y%m%d_%H%M%S)" 2>/dev/null || true
    echo "  ✓ CSV backup создан"
fi

# 2. Stash локальные изменения
echo
echo "[2/5] Сохранение локальных изменений (stash)..."
git stash push -m "Server audit logs before pull $(date +%Y%m%d_%H%M%S)" audit_logs/ logs/ 2>/dev/null
if [ $? -eq 0 ]; then
    echo "  ✓ Изменения сохранены в stash"
else
    echo "  ℹ Нет изменений для stash (это нормально)"
fi

# 3. Pull
echo
echo "[3/5] Получение изменений из Git..."
git pull origin main
if [ $? -ne 0 ]; then
    echo "  ✗ ОШИБКА: git pull не удался"
    echo "  Попробуйте вручную: git pull origin main"
    exit 1
fi
echo "  ✓ Pull успешен"

# 4. Restore stash (если есть)
echo
echo "[4/5] Восстановление локальных изменений..."
if [ -n "$(git stash list | head -1)" ]; then
    git stash pop 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "  ✓ Локальные изменения восстановлены"
    else
        echo "  ⚠ Конфликты при восстановлении stash"
        echo "  Проверьте вручную: git stash list"
        echo "  Для просмотра: git stash show -p"
    fi
else
    echo "  ℹ Нет stash для восстановления"
fi

# 5. Проверка целостности
echo
echo "[5/5] Проверка целостности audit-логов..."
if [ -f "audit_logs/trades_audit.jsonl" ]; then
    JSONL_SIZE=$(stat -f%z "audit_logs/trades_audit.jsonl" 2>/dev/null || stat -c%s "audit_logs/trades_audit.jsonl" 2>/dev/null || echo "0")
    echo "  JSONL размер: $JSONL_SIZE байт"
fi

if [ -f "audit_logs/trades_audit.csv" ]; then
    CSV_SIZE=$(stat -f%z "audit_logs/trades_audit.csv" 2>/dev/null || stat -c%s "audit_logs/trades_audit.csv" 2>/dev/null || echo "0")
    echo "  CSV размер: $CSV_SIZE байт"
fi

echo
echo "========================================="
echo "ЗАВЕРШЕНО"
echo "========================================="
echo
echo "Следующие шаги:"
echo "  1. Проверьте логи: tail -f logs/trading_bot.log"
echo "  2. Если нужно перезапустить бота: sudo systemctl restart trading-bot.service"
echo "  3. Backup файлы находятся в: audit_logs/backups/"

# Безопасный git pull с сохранением audit-логов на сервере

cd /home/botuser/trading_bot/trading_bot

echo "========================================="
echo "БЕЗОПАСНЫЙ GIT PULL (с сохранением логов)"
echo "========================================="
echo "Время: $(date)"
echo

# 1. Backup audit-логов
echo "[1/5] Создание backup audit-логов..."
BACKUP_DIR="audit_logs/backups"
mkdir -p "$BACKUP_DIR" 2>/dev/null || true

if [ -f "audit_logs/trades_audit.jsonl" ]; then
    cp audit_logs/trades_audit.jsonl "$BACKUP_DIR/trades_audit.jsonl.backup_$(date +%Y%m%d_%H%M%S)" 2>/dev/null || true
    echo "  ✓ JSONL backup создан"
fi

if [ -f "audit_logs/trades_audit.csv" ]; then
    cp audit_logs/trades_audit.csv "$BACKUP_DIR/trades_audit.csv.backup_$(date +%Y%m%d_%H%M%S)" 2>/dev/null || true
    echo "  ✓ CSV backup создан"
fi

# 2. Stash локальные изменения
echo
echo "[2/5] Сохранение локальных изменений (stash)..."
git stash push -m "Server audit logs before pull $(date +%Y%m%d_%H%M%S)" audit_logs/ logs/ 2>/dev/null
if [ $? -eq 0 ]; then
    echo "  ✓ Изменения сохранены в stash"
else
    echo "  ℹ Нет изменений для stash (это нормально)"
fi

# 3. Pull
echo
echo "[3/5] Получение изменений из Git..."
git pull origin main
if [ $? -ne 0 ]; then
    echo "  ✗ ОШИБКА: git pull не удался"
    echo "  Попробуйте вручную: git pull origin main"
    exit 1
fi
echo "  ✓ Pull успешен"

# 4. Restore stash (если есть)
echo
echo "[4/5] Восстановление локальных изменений..."
if [ -n "$(git stash list | head -1)" ]; then
    git stash pop 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "  ✓ Локальные изменения восстановлены"
    else
        echo "  ⚠ Конфликты при восстановлении stash"
        echo "  Проверьте вручную: git stash list"
        echo "  Для просмотра: git stash show -p"
    fi
else
    echo "  ℹ Нет stash для восстановления"
fi

# 5. Проверка целостности
echo
echo "[5/5] Проверка целостности audit-логов..."
if [ -f "audit_logs/trades_audit.jsonl" ]; then
    JSONL_SIZE=$(stat -f%z "audit_logs/trades_audit.jsonl" 2>/dev/null || stat -c%s "audit_logs/trades_audit.jsonl" 2>/dev/null || echo "0")
    echo "  JSONL размер: $JSONL_SIZE байт"
fi

if [ -f "audit_logs/trades_audit.csv" ]; then
    CSV_SIZE=$(stat -f%z "audit_logs/trades_audit.csv" 2>/dev/null || stat -c%s "audit_logs/trades_audit.csv" 2>/dev/null || echo "0")
    echo "  CSV размер: $CSV_SIZE байт"
fi

echo
echo "========================================="
echo "ЗАВЕРШЕНО"
echo "========================================="
echo
echo "Следующие шаги:"
echo "  1. Проверьте логи: tail -f logs/trading_bot.log"
echo "  2. Если нужно перезапустить бота: sudo systemctl restart trading-bot.service"
echo "  3. Backup файлы находятся в: audit_logs/backups/"




