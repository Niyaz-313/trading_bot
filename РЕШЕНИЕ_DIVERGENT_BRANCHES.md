# Решение проблемы divergent branches

## Проблема
Git не может автоматически объединить ветки, потому что:
- На сервере есть локальный коммит (merge commit)
- В удалённом репозитории есть новые коммиты

## Решение 1: Merge (рекомендуется)

```bash
cd /home/botuser/trading_bot/trading_bot

# Сделать merge
git pull origin main --no-rebase

# Если будут конфликты - разрешить их (см. предыдущие инструкции)
# Затем:
git add .
git commit -m "Merge: объединены изменения"
```

## Решение 2: Rebase (более чистая история)

```bash
cd /home/botuser/trading_bot/trading_bot

# Сделать rebase
git pull origin main --rebase

# Если будут конфликты:
# 1. Разрешить конфликты вручную
# 2. git add .
# 3. git rebase --continue
```

## Решение 3: Сначала запушить локальный коммит

```bash
cd /home/botuser/trading_bot/trading_bot

# Запушить локальный merge commit
git push origin main

# Если будет rejected (потому что удалённая ветка впереди):
# Тогда используйте Решение 1 или 2
```

## Быстрое решение (merge)

```bash
cd /home/botuser/trading_bot/trading_bot
git pull origin main --no-rebase
```

Если конфликтов нет - готово!
Если есть конфликты - разрешите их как раньше (stash или checkout --theirs для логов).



