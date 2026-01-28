@echo off
chcp 65001 > nul

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo Запуск скрипта принудительной покупки всех символов...
python force_buy_all_symbols.py

if %errorlevel% equ 0 (
    echo.
    echo Операция завершена успешно.
) else (
    echo.
    echo Операция завершена с ошибками.
)

pause


set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo Запуск скрипта принудительной покупки всех символов...
python force_buy_all_symbols.py

if %errorlevel% equ 0 (
    echo.
    echo Операция завершена успешно.
) else (
    echo.
    echo Операция завершена с ошибками.
)

pause


set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo Запуск скрипта принудительной покупки всех символов...
python force_buy_all_symbols.py

if %errorlevel% equ 0 (
    echo.
    echo Операция завершена успешно.
) else (
    echo.
    echo Операция завершена с ошибками.
)

pause
