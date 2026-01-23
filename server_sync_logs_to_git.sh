#!/bin/bash
# Скрипт автоматической синхронизации логов с Git на сервере
# Запускается через cron для автоматической отправки логов в репозиторий

set -e

# Правильный путь к проекту
PROJECT_DIR="/home/botuser/trading_bot/trading_bot"
cd "$PROJECT_DIR"

# Логирование действий скрипта
LOG_FILE="$PROJECT_DIR/logs/git_sync.log"
mkdir -p "$(dirname "$LOG_FILE")"

log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_message "========================================="
log_message "СИНХРОНИЗАЦИЯ ЛОГОВ С GIT"
log_message "========================================="

# Проверка, что мы в git репозитории
if [ ! -d ".git" ]; then
    log_message "ОШИБКА: .git не найден. Это не git репозиторий."
    exit 1
fi

# Настройка Git для автоматических коммитов
git config user.name "Trading Bot Server" || true
git config user.email "bot@server.local" || true

# Проверяем и исправляем remote URL, если он использует SSH
REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")
if [[ "$REMOTE_URL" == git@* ]]; then
    log_message "Обнаружен SSH remote URL, переключаю на HTTPS..."
    HTTPS_URL=$(echo "$REMOTE_URL" | sed 's|git@github.com:|https://github.com/|' | sed 's|\.git$||')
    git remote set-url origin "${HTTPS_URL}.git"
    log_message "Remote URL изменен на: $(git remote get-url origin)"
fi

# Получаем изменения с сервера перед отправкой (избегаем конфликтов)
log_message "[1/5] Получение изменений с сервера..."
git pull origin main --no-edit --no-rebase 2>&1 | tee -a "$LOG_FILE" || {
    log_message "ПРЕДУПРЕЖДЕНИЕ: git pull завершился с ошибкой (возможны конфликты)"
    # Пытаемся разрешить конфликты, оставляя версию сервера для логов
    if git status | grep -q "both modified.*audit_logs\|both modified.*logs"; then
        log_message "Разрешение конфликтов в логах (оставляем версию сервера)..."
        git checkout --theirs audit_logs/* logs/* 2>/dev/null || true
        git add audit_logs/* logs/* 2>/dev/null || true
        git commit -m "Auto-merge: keep server logs version" 2>/dev/null || true
    fi
}

# Проверяем, есть ли изменения для коммита
log_message "[2/5] Проверка изменений..."
CHANGED_FILES=$(git status --porcelain audit_logs/ logs/ 2>/dev/null | wc -l)

if [ "$CHANGED_FILES" -eq 0 ]; then
    log_message "Нет изменений в логах для коммита"
    exit 0
fi

log_message "Найдено изменений: $CHANGED_FILES файлов"

# Показываем, какие файлы изменились
log_message "[3/5] Измененные файлы:"
git status --porcelain audit_logs/ logs/ | head -10 | tee -a "$LOG_FILE"

# Добавляем только логи (не весь проект)
log_message "[4/5] Добавление логов в git..."
git add audit_logs/*.jsonl audit_logs/*.csv logs/*.log 2>/dev/null || {
    log_message "ПРЕДУПРЕЖДЕНИЕ: некоторые файлы не удалось добавить"
}

# Проверяем размер файлов перед коммитом
LARGE_FILES=$(find audit_logs logs -type f -size +50M 2>/dev/null | wc -l)
if [ "$LARGE_FILES" -gt 0 ]; then
    log_message "ПРЕДУПРЕЖДЕНИЕ: найдено $LARGE_FILES файлов размером >50MB"
    find audit_logs logs -type f -size +50M 2>/dev/null | tee -a "$LOG_FILE"
fi

# Создаем коммит
COMMIT_MSG="Auto-sync logs: $(date '+%Y-%m-%d %H:%M:%S MSK')"
log_message "[5/5] Создание коммита..."
git commit -m "$COMMIT_MSG" 2>&1 | tee -a "$LOG_FILE" || {
    log_message "ПРЕДУПРЕЖДЕНИЕ: коммит не создан (возможно, нет изменений после pull)"
    exit 0
}

# Отправляем изменения на сервер
log_message "Отправка изменений на сервер..."
git push origin main 2>&1 | tee -a "$LOG_FILE" || {
    log_message "ОШИБКА: не удалось отправить изменения"
    exit 1
}

log_message "========================================="
log_message "СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА УСПЕШНО"
log_message "========================================="

