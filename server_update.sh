#!/bin/bash
# Скрипт обновления бота на сервере
# Запускается автоматически через cron или вручную

set -e

# Правильный путь к проекту
PROJECT_DIR="/home/botuser/trading_bot/trading_bot"
cd "$PROJECT_DIR"

echo "========================================="
echo "ОБНОВЛЕНИЕ ТОРГОВОГО БОТА"
echo "========================================="
echo "Время: $(date)"
echo "Директория: $PROJECT_DIR"
echo

# Активировать виртуальное окружение
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "ОШИБКА: Виртуальное окружение не найдено в $PROJECT_DIR/venv"
    exit 1
fi

echo "[1/4] Обновление кода из Git..."

# Проверяем и исправляем remote URL, если он использует SSH
REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")
if [[ "$REMOTE_URL" == git@* ]]; then
    echo "Обнаружен SSH remote URL, переключаю на HTTPS..."
    # Преобразуем git@github.com:user/repo.git в https://github.com/user/repo.git
    HTTPS_URL=$(echo "$REMOTE_URL" | sed 's|git@github.com:|https://github.com/|' | sed 's|\.git$||')
    git remote set-url origin "${HTTPS_URL}.git"
    echo "Remote URL изменен на: $(git remote get-url origin)"
fi

# Проверяем глобальные настройки Git, которые могут переопределять URL
GIT_URL_REWRITE=$(git config --global --get url.ssh://git@github.com/.insteadof 2>/dev/null || echo "")
if [[ -n "$GIT_URL_REWRITE" ]]; then
    echo "Обнаружено правило переписывания URL в глобальной конфигурации Git"
    echo "Удаляю правило: url.ssh://git@github.com/.insteadof"
    git config --global --unset url.ssh://git@github.com/.insteadof 2>/dev/null || true
fi

# Сохраняем текущий коммит для сравнения
LOCAL_COMMIT_BEFORE=$(git rev-parse HEAD)

# Обновляем через git pull (работает с HTTPS, не требует SSH ключей)
# Используем явный HTTPS URL для гарантии
GIT_REMOTE_URL=$(git remote get-url origin)
if [[ "$GIT_REMOTE_URL" != https://* ]]; then
    echo "ОШИБКА: Remote URL все еще не HTTPS: $GIT_REMOTE_URL"
    exit 1
fi

echo "Используется remote URL: $GIT_REMOTE_URL"
git pull origin main 2>&1

# Проверяем, были ли изменения
LOCAL_COMMIT_AFTER=$(git rev-parse HEAD)

if [ "$LOCAL_COMMIT_BEFORE" != "$LOCAL_COMMIT_AFTER" ]; then
    echo "Обнаружены новые изменения, обновляю..."
    echo "Было: $LOCAL_COMMIT_BEFORE"
    echo "Стало: $LOCAL_COMMIT_AFTER"
    
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
    echo "Нет новых изменений (код уже актуален)"
fi


# Обновляем через git pull (работает с HTTPS, не требует SSH ключей)
# Используем явный HTTPS URL для гарантии
GIT_REMOTE_URL=$(git remote get-url origin)
if [[ "$GIT_REMOTE_URL" != https://* ]]; then
    echo "ОШИБКА: Remote URL все еще не HTTPS: $GIT_REMOTE_URL"
    exit 1
fi

echo "Используется remote URL: $GIT_REMOTE_URL"
git pull origin main 2>&1

# Проверяем, были ли изменения
LOCAL_COMMIT_AFTER=$(git rev-parse HEAD)

if [ "$LOCAL_COMMIT_BEFORE" != "$LOCAL_COMMIT_AFTER" ]; then
    echo "Обнаружены новые изменения, обновляю..."
    echo "Было: $LOCAL_COMMIT_BEFORE"
    echo "Стало: $LOCAL_COMMIT_AFTER"
    
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
    echo "Нет новых изменений (код уже актуален)"
fi
