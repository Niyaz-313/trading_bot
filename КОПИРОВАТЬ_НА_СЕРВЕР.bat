@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ========================================
echo КОПИРОВАНИЕ ФАЙЛОВ НА СЕРВЕР
echo ========================================
echo.

REM Проверяем наличие PowerShell
where powershell >nul 2>&1
if errorlevel 1 (
    echo ОШИБКА: PowerShell не найден
    pause
    exit /b 1
)

REM Запускаем PowerShell скрипт
powershell -ExecutionPolicy Bypass -File "%~dp0copy_to_server.ps1" %*

if errorlevel 1 (
    echo.
    echo ОШИБКА при выполнении скрипта
    pause
    exit /b 1
)

echo.
pause

