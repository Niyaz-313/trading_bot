#!/bin/bash
# Разрешение конфликтов в audit-логах (объединение обеих версий)

cd /home/botuser/trading_bot/trading_bot

echo "========================================="
echo "РАЗРЕШЕНИЕ КОНФЛИКТОВ В AUDIT-ЛОГАХ"
echo "========================================="
echo

# 1. JSONL - объединить обе версии
if [ -f "audit_logs/trades_audit.jsonl" ]; then
    echo "[1/3] Разрешение конфликта в JSONL..."
    
    # Создать backup
    cp audit_logs/trades_audit.jsonl audit_logs/trades_audit.jsonl.conflict_backup
    
    # Взять версию из stash (локальная, серверная)
    git show stash@{0}:audit_logs/trades_audit.jsonl > audit_logs/trades_audit.jsonl.stash 2>/dev/null || true
    
    # Взять текущую версию (удалённая)
    git show HEAD:audit_logs/trades_audit.jsonl > audit_logs/trades_audit.jsonl.head 2>/dev/null || true
    
    # Объединить: сначала удалённая, потом локальная (append-only)
    if [ -f "audit_logs/trades_audit.jsonl.head" ]; then
        cat audit_logs/trades_audit.jsonl.head > audit_logs/trades_audit.jsonl.merged
    else
        touch audit_logs/trades_audit.jsonl.merged
    fi
    
    if [ -f "audit_logs/trades_audit.jsonl.stash" ]; then
        # Добавить только новые строки (которые не были в head)
        if [ -f "audit_logs/trades_audit.jsonl.head" ]; then
            comm -13 <(sort audit_logs/trades_audit.jsonl.head) <(sort audit_logs/trades_audit.jsonl.stash) >> audit_logs/trades_audit.jsonl.merged 2>/dev/null || cat audit_logs/trades_audit.jsonl.stash >> audit_logs/trades_audit.jsonl.merged
        else
            cat audit_logs/trades_audit.jsonl.stash >> audit_logs/trades_audit.jsonl.merged
        fi
    fi
    
    # Заменить конфликтный файл объединённой версией
    mv audit_logs/trades_audit.jsonl.merged audit_logs/trades_audit.jsonl
    
    # Очистить временные файлы
    rm -f audit_logs/trades_audit.jsonl.stash audit_logs/trades_audit.jsonl.head
    
    echo "  ✓ JSONL объединён"
fi

# 2. CSV - объединить обе версии
if [ -f "audit_logs/trades_audit.csv" ]; then
    echo "[2/3] Разрешение конфликта в CSV..."
    
    # Создать backup
    cp audit_logs/trades_audit.csv audit_logs/trades_audit.csv.conflict_backup
    
    # Взять версию из stash
    git show stash@{0}:audit_logs/trades_audit.csv > audit_logs/trades_audit.csv.stash 2>/dev/null || true
    
    # Взять текущую версию
    git show HEAD:audit_logs/trades_audit.csv > audit_logs/trades_audit.csv.head 2>/dev/null || true
    
    # Объединить: header + данные из обеих версий
    if [ -f "audit_logs/trades_audit.csv.head" ]; then
        # Взять header из head
        head -1 audit_logs/trades_audit.csv.head > audit_logs/trades_audit.csv.merged
        
        # Добавить данные из head (без header)
        tail -n +2 audit_logs/trades_audit.csv.head >> audit_logs/trades_audit.csv.merged 2>/dev/null || true
    else
        # Если head нет, взять header из stash
        if [ -f "audit_logs/trades_audit.csv.stash" ]; then
            head -1 audit_logs/trades_audit.csv.stash > audit_logs/trades_audit.csv.merged
        fi
    fi
    
    # Добавить данные из stash (без header, только новые строки)
    if [ -f "audit_logs/trades_audit.csv.stash" ]; then
        tail -n +2 audit_logs/trades_audit.csv.stash >> audit_logs/trades_audit.csv.merged 2>/dev/null || true
    fi
    
    # Заменить конфликтный файл
    mv audit_logs/trades_audit.csv.merged audit_logs/trades_audit.csv
    
    # Очистить временные файлы
    rm -f audit_logs/trades_audit.csv.stash audit_logs/trades_audit.csv.head
    
    echo "  ✓ CSV объединён"
fi

# 3. logs/trading_bot.log - взять более свежую версию
if [ -f "logs/trading_bot.log" ]; then
    echo "[3/3] Разрешение конфликта в trading_bot.log..."
    
    # Создать backup
    cp logs/trading_bot.log logs/trading_bot.log.conflict_backup
    
    # Взять версию из stash
    git show stash@{0}:logs/trading_bot.log > logs/trading_bot.log.stash 2>/dev/null || true
    
    # Взять текущую версию
    git show HEAD:logs/trading_bot.log > logs/trading_bot.log.head 2>/dev/null || true
    
    # Объединить (append-only)
    if [ -f "logs/trading_bot.log.head" ]; then
        cat logs/trading_bot.log.head > logs/trading_bot.log.merged
    else
        touch logs/trading_bot.log.merged
    fi
    
    if [ -f "logs/trading_bot.log.stash" ]; then
        cat logs/trading_bot.log.stash >> logs/trading_bot.log.merged
    fi
    
    mv logs/trading_bot.log.merged logs/trading_bot.log
    
    rm -f logs/trading_bot.log.stash logs/trading_bot.log.head
    
    echo "  ✓ trading_bot.log объединён"
fi

# 4. Отметить конфликты как разрешённые
echo
echo "[4/4] Отметка конфликтов как разрешённых..."
git add audit_logs/trades_audit.jsonl audit_logs/trades_audit.csv logs/trading_bot.log

echo
echo "========================================="
echo "КОНФЛИКТЫ РАЗРЕШЕНЫ"
echo "========================================="
echo
echo "Следующий шаг:"
echo "  git commit -m 'Merge: объединены audit-логи с сервера'"
echo
echo "Backup файлы сохранены:"
echo "  - audit_logs/trades_audit.jsonl.conflict_backup"
echo "  - audit_logs/trades_audit.csv.conflict_backup"
echo "  - logs/trading_bot.log.conflict_backup"

