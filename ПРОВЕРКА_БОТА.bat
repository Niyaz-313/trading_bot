@echo off
chcp 65001 > nul

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo Запуск проверки работоспособности бота...
python check_bot_health.py

if %errorlevel% equ 0 (
    echo.
    echo Все проверки пройдены успешно.
) else (
    echo.
    echo Обнаружены проблемы.
)

pause

chcp 65001 > nul

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo Запуск проверки работоспособности бота...
python check_bot_health.py

if %errorlevel% equ 0 (
    echo.
    echo Все проверки пройдены успешно.
) else (
    echo.
    echo Обнаружены проблемы.
)

pause

chcp 65001 > nul

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo Запуск проверки работоспособности бота...
python check_bot_health.py

if %errorlevel% equ 0 (
    echo.
    echo Все проверки пройдены успешно.
) else (
    echo.
    echo Обнаружены проблемы.
)

pause





