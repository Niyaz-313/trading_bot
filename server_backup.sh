#!/bin/bash
# Скрипт резервного копирования на сервере
# Запускается автоматически через cron

set -e

BACKUP_DIR=~/backups/trading_bot
DATE=$(date +%Y%m%d_%H%M%S)
LOG_FILE=~/trading_bot/logs/backup.log

mkdir -p $BACKUP_DIR
mkdir -p ~/trading_bot/logs

echo "=========================================" >> $LOG_FILE
echo "Резервное копирование: $(date)" >> $LOG_FILE
echo "=========================================" >> $LOG_FILE

cd ~/trading_bot

# Резервная копия важных данных
echo "[1/3] Копирование audit_logs..." >> $LOG_FILE
if [ -d "audit_logs" ]; then
    tar -czf $BACKUP_DIR/audit_$DATE.tar.gz audit_logs/ 2>>$LOG_FILE
    echo "  ✓ audit_logs сохранен" >> $LOG_FILE
else
    echo "  ⚠ audit_logs не найден" >> $LOG_FILE
fi

echo "[2/3] Копирование state..." >> $LOG_FILE
if [ -d "state" ]; then
    tar -czf $BACKUP_DIR/state_$DATE.tar.gz state/ 2>>$LOG_FILE
    echo "  ✓ state сохранен" >> $LOG_FILE
else
    echo "  ⚠ state не найден" >> $LOG_FILE
fi

echo "[3/3] Копирование .env..." >> $LOG_FILE
if [ -f ".env" ]; then
    cp .env $BACKUP_DIR/.env_$DATE 2>>$LOG_FILE
    echo "  ✓ .env сохранен" >> $LOG_FILE
else
    echo "  ⚠ .env не найден" >> $LOG_FILE
fi

# Удалить старые бэкапы (старше 30 дней)
echo "Очистка старых бэкапов..." >> $LOG_FILE
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete 2>>$LOG_FILE
find $BACKUP_DIR -name ".env_*" -mtime +30 -delete 2>>$LOG_FILE

echo "Резервное копирование завершено: $DATE" >> $LOG_FILE
echo "" >> $LOG_FILE

# Показать размер бэкапов
echo "Размер бэкапов:" >> $LOG_FILE
du -sh $BACKUP_DIR >> $LOG_FILE

