#!/bin/bash
# Скрипт создания systemd сервиса для бота
# Запустите на сервере после настройки окружения

set -e

echo "========================================="
echo "СОЗДАНИЕ SYSTEMD СЕРВИСА"
echo "========================================="
echo

# Получаем путь к домашней директории пользователя
USER_HOME=$(eval echo ~$USER)
BOT_DIR="$USER_HOME/trading_bot"

# Проверяем, что директория существует
if [ ! -d "$BOT_DIR" ]; then
    echo "ОШИБКА: Директория $BOT_DIR не найдена"
    exit 1
fi

# Проверяем, что main.py существует
if [ ! -f "$BOT_DIR/main.py" ]; then
    echo "ОШИБКА: Файл $BOT_DIR/main.py не найден"
    exit 1
fi

# Проверяем, что venv существует
if [ ! -d "$BOT_DIR/venv" ]; then
    echo "ОШИБКА: Виртуальное окружение $BOT_DIR/venv не найдено"
    exit 1
fi

# Создаем директорию для логов
mkdir -p "$BOT_DIR/logs"

# Создаем файл сервиса
SERVICE_FILE="/etc/systemd/system/trading-bot.service"

echo "Создание файла сервиса: $SERVICE_FILE"
sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=Trading Bot Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$BOT_DIR
Environment="PATH=$BOT_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$BOT_DIR/venv/bin/python $BOT_DIR/main.py
Restart=always
RestartSec=10
StandardOutput=append:$BOT_DIR/logs/bot_output.log
StandardError=append:$BOT_DIR/logs/bot_error.log

[Install]
WantedBy=multi-user.target
EOF

echo
echo "Перезагрузка systemd..."
sudo systemctl daemon-reload

echo
echo "Включение автозапуска..."
sudo systemctl enable trading-bot.service

echo
echo "========================================="
echo "СЕРВИС СОЗДАН УСПЕШНО!"
echo "========================================="
echo
echo "Для запуска выполните:"
echo "  sudo systemctl start trading-bot.service"
echo
echo "Для проверки статуса:"
echo "  sudo systemctl status trading-bot.service"
echo
echo "Для просмотра логов:"
echo "  sudo journalctl -u trading-bot.service -f"
echo


