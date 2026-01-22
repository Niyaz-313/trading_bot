#!/bin/bash
# Скрипт первоначальной настройки сервера
# Запустите на сервере после подключения

set -e

echo "========================================="
echo "НАСТРОЙКА СЕРВЕРА ДЛЯ ТОРГОВОГО БОТА"
echo "========================================="
echo

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Проверка, что скрипт запущен не от root
if [ "$EUID" -eq 0 ]; then 
    echo -e "${RED}ОШИБКА: Не запускайте скрипт от root!${NC}"
    echo "Создайте пользователя: adduser botuser"
    echo "Затем запустите скрипт от этого пользователя"
    exit 1
fi

echo "[1/6] Обновление системы..."
sudo apt update && sudo apt upgrade -y

echo
echo "[2/6] Установка Python и зависимостей..."
sudo apt install -y python3.11 python3.11-venv python3-pip git curl htop

echo
echo "[3/6] Установка дополнительных зависимостей..."
sudo apt install -y build-essential libssl-dev libffi-dev python3-dev

echo
echo "[4/6] Создание рабочей директории..."
mkdir -p ~/trading_bot
cd ~/trading_bot

echo
echo "[5/6] Настройка Git (если еще не настроен)..."
if [ ! -f ~/.gitconfig ]; then
    read -p "Введите ваше имя для Git: " git_name
    read -p "Введите ваш email для Git: " git_email
    git config --global user.name "$git_name"
    git config --global user.email "$git_email"
fi

echo
echo "[6/6] Создание директорий для логов и данных..."
mkdir -p ~/trading_bot/logs
mkdir -p ~/trading_bot/audit_logs
mkdir -p ~/trading_bot/state
mkdir -p ~/trading_bot/data_cache
mkdir -p ~/backups/trading_bot

echo
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}НАСТРОЙКА ЗАВЕРШЕНА!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo
echo "Следующие шаги:"
echo "1. Клонируйте репозиторий:"
echo "   cd ~/trading_bot"
echo "   git clone https://github.com/ваш_username/trading_bot.git ."
echo
echo "2. Создайте виртуальное окружение:"
echo "   python3.11 -m venv venv"
echo "   source venv/bin/activate"
echo
echo "3. Установите зависимости:"
echo "   pip install --upgrade pip"
echo "   pip install -r requirements.txt"
echo
echo "4. Скопируйте .env файл с локальной машины:"
echo "   scp .env botuser@сервер:~/trading_bot/.env"
echo
echo "5. Создайте systemd сервис (см. инструкцию)"
echo


