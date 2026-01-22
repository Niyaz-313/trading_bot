@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ========================================
echo СИНХРОНИЗАЦИЯ КОДА С СЕРВЕРОМ
echo ========================================
echo.

REM Получаем путь к директории скрипта
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Проверяем наличие Git
where git >nul 2>&1
if errorlevel 1 (
    echo ОШИБКА: Git не установлен или не найден в PATH
    echo Установите Git: https://git-scm.com/download/win
    pause
    exit /b 1
)

echo [1/4] Проверка изменений в Git...
git status --short
if errorlevel 1 (
    echo ОШИБКА: Не удалось проверить статус Git
    pause
    exit /b 1
)

echo.
echo [2/4] Добавление изменений в Git...
git add .
if errorlevel 1 (
    echo ОШИБКА: Не удалось добавить файлы в Git
    pause
    exit /b 1
)

set "COMMIT_MSG=Auto-sync: %date% %time%"
git commit -m "%COMMIT_MSG%"
if errorlevel 1 (
    echo Предупреждение: Нет изменений для коммита или ошибка коммита
)

echo.
echo [3/4] Получение изменений с сервера (GitHub/GitLab)...
git fetch origin
if errorlevel 1 (
    echo Предупреждение: Не удалось получить изменения с сервера
    echo Продолжаем попытку отправки...
)

REM Проверяем, есть ли изменения на сервере
git status -sb | findstr /C:"behind" >nul
if not errorlevel 1 (
    echo Обнаружены изменения на сервере, выполняем pull...
    git pull origin main --no-edit
    if errorlevel 1 (
        echo ОШИБКА: Не удалось объединить изменения с сервера
        echo Возможны конфликты. Разрешите их вручную:
        echo   1. Откройте репозиторий в Git GUI или IDE
        echo   2. Разрешите конфликты
        echo   3. Выполните: git add . ^&^& git commit -m "Merge conflicts resolved"
        echo   4. Запустите этот скрипт снова
        pause
        exit /b 1
    )
    echo Изменения с сервера успешно объединены
) else (
    echo Локальная ветка синхронизирована с сервером
)

echo.
echo [4/4] Отправка изменений на сервер (GitHub/GitLab)...
git push origin main
if errorlevel 1 (
    echo ОШИБКА: Не удалось отправить изменения на сервер
    echo Возможные причины:
    echo   1. На сервере есть новые изменения - попробуйте запустить скрипт снова
    echo   2. Нет доступа к репозиторию - проверьте логин/пароль
    echo   3. Неправильный URL репозитория - проверьте remote origin
    echo.
    echo Для принудительной отправки (ОПАСНО!):
    echo   git push origin main --force
    echo   (используйте только если уверены, что хотите перезаписать удаленные изменения)
    pause
    exit /b 1
)

echo.
echo ========================================
echo СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА УСПЕШНО!
echo ========================================
echo.
echo Следующие шаги:
echo   1. На сервере выполните: cd ~/trading_bot && ./update.sh
echo   2. Или дождитесь автоматического обновления (каждые 6 часов)
echo.
pause

