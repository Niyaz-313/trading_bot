@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo Отправка изменений на сервер
echo ========================================
echo.

echo [1/4] Добавление файлов в git...
git add tinvest_api.py broker_api.py main.py ИНСТРУКЦИЯ_ОБНОВЛЕНИЯ_ЛОГИРОВАНИЯ.md
if errorlevel 1 (
    echo ОШИБКА: не удалось добавить файлы
    pause
    exit /b 1
)
echo OK
echo.

echo [2/4] Создание коммита...
git commit -m "Улучшено логирование причин отказа размещения ордеров + проверка торговой сессии"
if errorlevel 1 (
    echo ПРЕДУПРЕЖДЕНИЕ: возможно, нет изменений для коммита
)
echo.

echo [3/4] Получение изменений с сервера...
git pull origin main --no-edit
if errorlevel 1 (
    echo ОШИБКА: не удалось получить изменения
    pause
    exit /b 1
)
echo.

echo [4/4] Отправка изменений на сервер...
git push origin main
if errorlevel 1 (
    echo ОШИБКА: не удалось отправить изменения
    pause
    exit /b 1
)
echo.

echo ========================================
echo ГОТОВО! Изменения отправлены на сервер
echo ========================================
echo.
echo Следующие шаги на сервере:
echo   1. cd /home/botuser/trading_bot/trading_bot
echo   2. ./server_update.sh
echo   3. sudo systemctl restart trading-bot.service
echo.
pause



