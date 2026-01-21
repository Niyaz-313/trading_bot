@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ========================================
echo РЕЗЕРВНОЕ КОПИРОВАНИЕ С СЕРВЕРА
echo ========================================
echo.

REM Настройки
set "SERVER_USER=botuser"
set "SERVER_IP=ваш_сервер_ip"
set "BACKUP_DIR=C:\Backups\TradingBot"
set "DATE_STR=%date:~-4,4%%date:~-7,2%%date:~-10,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "DATE_STR=!DATE_STR: =0!"

REM Создаем директорию для бэкапов
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

echo [1/3] Копирование audit_logs...
scp -r %SERVER_USER%@%SERVER_IP%:~/trading_bot/audit_logs "%BACKUP_DIR%\audit_logs_%DATE_STR%"
if errorlevel 1 (
    echo ОШИБКА: Не удалось скопировать audit_logs
    echo Убедитесь, что:
    echo   1. SSH ключи настроены
    echo   2. Сервер доступен
    echo   3. Путь к директории правильный
    pause
    exit /b 1
)

echo.
echo [2/3] Копирование state...
scp -r %SERVER_USER%@%SERVER_IP%:~/trading_bot/state "%BACKUP_DIR%\state_%DATE_STR%"
if errorlevel 1 (
    echo Предупреждение: Не удалось скопировать state (возможно, директория не существует)
)

echo.
echo [3/3] Копирование логов...
scp -r %SERVER_USER%@%SERVER_IP%:~/trading_bot/logs "%BACKUP_DIR%\logs_%DATE_STR%"
if errorlevel 1 (
    echo Предупреждение: Не удалось скопировать logs (возможно, директория не существует)
)

echo.
echo ========================================
echo РЕЗЕРВНОЕ КОПИРОВАНИЕ ЗАВЕРШЕНО!
echo ========================================
echo.
echo Бэкапы сохранены в: %BACKUP_DIR%
echo.
pause

