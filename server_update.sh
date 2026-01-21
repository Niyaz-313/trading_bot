#!/bin/bash
# Скрипт обновления бота на сервере
# Запускается автоматически через cron или вручную

set -e

cd ~/trading_bot

echo "========================================="
echo "ОБНОВЛЕНИЕ ТОРГОВОГО БОТА"
echo "========================================="
echo "Время: $(date)"
echo

# Активировать виртуальное окружение
source venv/bin/activate

echo "[1/4] Обновление кода из Git..."
git fetch origin
if [ $(git rev-parse HEAD) != $(git rev-parse origin/main) ]; then
    echo "Обнаружены новые изменения, обновляю..."
    git pull origin main
    
    echo
    echo "[2/4] Обновление зависимостей..."
    pip install --upgrade pip
    pip install -r requirements.txt
    
    echo
    echo "[3/4] Перезапуск сервиса..."
    sudo systemctl restart trading-bot.service
    
    echo
    echo "[4/4] Проверка статуса..."
    sleep 3
    sudo systemctl status trading-bot.service --no-pager -l
    
    echo
    echo "========================================="
    echo "ОБНОВЛЕНИЕ ЗАВЕРШЕНО!"
    echo "========================================="
else
    echo "Нет новых изменений"
fi

