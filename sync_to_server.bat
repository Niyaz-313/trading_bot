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

echo [1/3] Проверка изменений в Git...
git status --short
if errorlevel 1 (
    echo ОШИБКА: Не удалось проверить статус Git
    pause
    exit /b 1
)

echo.
echo [2/3] Добавление изменений в Git...
git add .
if errorlevel 1 (
    echo ОШИБКА: Не удалось добавить файлы в Git
    pause
    exit /b 1
)

echo.
echo [3/3] Отправка изменений на сервер (GitHub/GitLab)...
set "COMMIT_MSG=Auto-sync: %date% %time%"
git commit -m "%COMMIT_MSG%"
if errorlevel 1 (
    echo Предупреждение: Нет изменений для коммита или ошибка коммита
)

git push origin main
if errorlevel 1 (
    echo ОШИБКА: Не удалось отправить изменения на сервер
    echo Проверьте:
    echo   1. Настроен ли remote origin
    echo   2. Есть ли доступ к репозиторию
    echo   3. Правильность URL репозитория
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

