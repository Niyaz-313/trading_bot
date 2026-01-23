#!/bin/bash
# Скрипт установки cron задачи для автоматической синхронизации логов

set -e

PROJECT_DIR="/home/botuser/trading_bot/trading_bot"
SYNC_SCRIPT="$PROJECT_DIR/server_sync_logs_to_git.sh"

echo "========================================="
echo "УСТАНОВКА АВТОМАТИЧЕСКОЙ СИНХРОНИЗАЦИИ ЛОГОВ"
echo "========================================="

# Проверка существования скрипта
if [ ! -f "$SYNC_SCRIPT" ]; then
    echo "ОШИБКА: Скрипт $SYNC_SCRIPT не найден"
    exit 1
fi

# Даем права на выполнение
chmod +x "$SYNC_SCRIPT"
echo "✓ Права на выполнение установлены"

# Создаем cron задачу (каждый час в 5 минут)
CRON_JOB="5 * * * * cd $PROJECT_DIR && $SYNC_SCRIPT >> $PROJECT_DIR/logs/cron_sync.log 2>&1"

# Проверяем, не установлена ли уже эта задача
if crontab -l 2>/dev/null | grep -q "server_sync_logs_to_git.sh"; then
    echo "⚠️  Cron задача уже установлена"
    echo "Текущие задачи:"
    crontab -l | grep "server_sync_logs_to_git.sh"
else
    # Добавляем задачу в crontab
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "✓ Cron задача добавлена: каждый час в 5 минут"
fi

echo ""
echo "========================================="
echo "УСТАНОВКА ЗАВЕРШЕНА"
echo "========================================="
echo ""
echo "Текущие cron задачи:"
crontab -l | grep -E "server_sync|sync_logs" || echo "(нет задач синхронизации)"
echo ""
echo "Для проверки логов синхронизации:"
echo "  tail -f $PROJECT_DIR/logs/git_sync.log"
echo ""
echo "Для ручного запуска синхронизации:"
echo "  $SYNC_SCRIPT"

