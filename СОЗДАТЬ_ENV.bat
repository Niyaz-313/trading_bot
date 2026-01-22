@echo off
chcp 65001 >nul
echo ========================================
echo Создание файла .env
echo ========================================
echo.

cd /d "%~dp0"

if exist ".env" (
    echo Файл .env уже существует!
    echo.
    set /p overwrite="Перезаписать? (Y/N): "
    if /i not "%overwrite%"=="Y" (
        echo Отменено.
        pause
        exit /b 0
    )
)

if exist "env_template.txt" (
    copy env_template.txt .env >nul
    echo Файл .env создан из шаблона env_template.txt
    echo.
    echo ВАЖНО: Откройте файл .env и заполните:
    echo   1. TELEGRAM_BOT_TOKEN - получите у @BotFather
    echo   2. TELEGRAM_CHAT_ID - получите у @userinfobot
    echo   3. TINVEST_TOKEN - получите в настройках Т-Инвестиций
    echo.
    echo Открыть файл .env в Блокноте? (Y/N)
    set /p open="> "
    if /i "%open%"=="Y" (
        notepad .env
    )
) else (
    echo Создание пустого файла .env...
    echo. > .env
    echo Файл .env создан.
    echo.
    echo Откройте файл .env и добавьте настройки.
    echo См. файл ИНСТРУКЦИЯ_ПО_ENV.md для подробностей.
    echo.
    notepad .env
)

echo.
pause




