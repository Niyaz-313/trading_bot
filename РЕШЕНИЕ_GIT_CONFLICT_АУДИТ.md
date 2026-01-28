# Решение конфликта Git с audit-логами на сервере

## Проблема
При `git pull` Git блокирует merge, потому что локальные audit-логи и логи изменились на сервере.

## Решение 1: Stash + Pull + Restore (рекомендуется)

```bash
cd /home/botuser/trading_bot/trading_bot

# 1. Сохранить локальные изменения
git stash push -m "Server audit logs before pull"

# 2. Получить изменения из Git
git pull origin main

# 3. Восстановить локальные изменения (они добавятся поверх)
git stash pop

# 4. Если есть конфликты в логах - разрешить их, оставив оба набора данных
# (audit-логи append-only, можно просто объединить)
```

## Решение 2: Отбросить локальные изменения в логах (если не критично)

```bash
cd /home/botuser/trading_bot/trading_bot

# Отбросить изменения только в логах (они генерируются заново)
git checkout -- logs/trading_bot.log

# Для audit-логов лучше использовать stash (Решение 1)
# или вручную объединить данные
```

## Решение 3: Использовать стратегию merge (предпочитать удалённую версию)

```bash
cd /home/botuser/trading_bot/trading_bot

# Сохранить локальные audit-логи в backup
cp audit_logs/trades_audit.jsonl audit_logs/trades_audit.jsonl.server_backup
cp audit_logs/trades_audit.csv audit_logs/trades_audit.csv.server_backup

# Отбросить локальные изменения
git checkout -- audit_logs/trades_audit.jsonl audit_logs/trades_audit.csv logs/trading_bot.log

# Pull
git pull origin main

# Восстановить server-данные (append к новым файлам)
# Это нужно делать вручную, объединяя строки
```

## Автоматический скрипт для сервера

Создайте файл `server_pull_safe.sh`:

```bash
#!/bin/bash
cd /home/botuser/trading_bot/trading_bot

# Backup
echo "Creating backup..."
cp audit_logs/trades_audit.jsonl audit_logs/trades_audit.jsonl.backup_$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
cp audit_logs/trades_audit.csv audit_logs/trades_audit.csv.backup_$(date +%Y%m%d_%H%M%S) 2>/dev/null || true

# Stash
echo "Stashing local changes..."
git stash push -m "Auto-stash before pull $(date +%Y%m%d_%H%M%S)" audit_logs/ logs/ 2>/dev/null || true

# Pull
echo "Pulling from remote..."
git pull origin main

# Restore (если нужно)
if [ -n "$(git stash list)" ]; then
    echo "Restoring stashed changes..."
    git stash pop || echo "Warning: stash pop had conflicts, check manually"
fi

echo "Done!"
```

## Рекомендация

**Используйте Решение 1** - оно безопаснее всего сохраняет данные.

Если конфликты возникают часто, рассмотрите:
- Ротацию audit-логов (архивировать старые)
- Исключение логов из Git (вернуть в .gitignore)
- Использование Git LFS для больших файлов


## Проблема
При `git pull` Git блокирует merge, потому что локальные audit-логи и логи изменились на сервере.

## Решение 1: Stash + Pull + Restore (рекомендуется)

```bash
cd /home/botuser/trading_bot/trading_bot

# 1. Сохранить локальные изменения
git stash push -m "Server audit logs before pull"

# 2. Получить изменения из Git
git pull origin main

# 3. Восстановить локальные изменения (они добавятся поверх)
git stash pop

# 4. Если есть конфликты в логах - разрешить их, оставив оба набора данных
# (audit-логи append-only, можно просто объединить)
```

## Решение 2: Отбросить локальные изменения в логах (если не критично)

```bash
cd /home/botuser/trading_bot/trading_bot

# Отбросить изменения только в логах (они генерируются заново)
git checkout -- logs/trading_bot.log

# Для audit-логов лучше использовать stash (Решение 1)
# или вручную объединить данные
```

## Решение 3: Использовать стратегию merge (предпочитать удалённую версию)

```bash
cd /home/botuser/trading_bot/trading_bot

# Сохранить локальные audit-логи в backup
cp audit_logs/trades_audit.jsonl audit_logs/trades_audit.jsonl.server_backup
cp audit_logs/trades_audit.csv audit_logs/trades_audit.csv.server_backup

# Отбросить локальные изменения
git checkout -- audit_logs/trades_audit.jsonl audit_logs/trades_audit.csv logs/trading_bot.log

# Pull
git pull origin main

# Восстановить server-данные (append к новым файлам)
# Это нужно делать вручную, объединяя строки
```

## Автоматический скрипт для сервера

Создайте файл `server_pull_safe.sh`:

```bash
#!/bin/bash
cd /home/botuser/trading_bot/trading_bot

# Backup
echo "Creating backup..."
cp audit_logs/trades_audit.jsonl audit_logs/trades_audit.jsonl.backup_$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
cp audit_logs/trades_audit.csv audit_logs/trades_audit.csv.backup_$(date +%Y%m%d_%H%M%S) 2>/dev/null || true

# Stash
echo "Stashing local changes..."
git stash push -m "Auto-stash before pull $(date +%Y%m%d_%H%M%S)" audit_logs/ logs/ 2>/dev/null || true

# Pull
echo "Pulling from remote..."
git pull origin main

# Restore (если нужно)
if [ -n "$(git stash list)" ]; then
    echo "Restoring stashed changes..."
    git stash pop || echo "Warning: stash pop had conflicts, check manually"
fi

echo "Done!"
```

## Рекомендация

**Используйте Решение 1** - оно безопаснее всего сохраняет данные.

Если конфликты возникают часто, рассмотрите:
- Ротацию audit-логов (архивировать старые)
- Исключение логов из Git (вернуть в .gitignore)
- Использование Git LFS для больших файлов




