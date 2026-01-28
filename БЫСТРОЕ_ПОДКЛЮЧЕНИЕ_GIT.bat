@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ========================================
echo БЫСТРОЕ ПОДКЛЮЧЕНИЕ GIT К СЕРВЕРУ
echo ========================================
echo.

REM Получаем IPv4 адрес сервера
set /p SERVER_IP="Введите IPv4 адрес сервера: "
if "%SERVER_IP%"=="" (
    echo ОШИБКА: IPv4 адрес не введен
    pause
    exit /b 1
)

echo.
echo IPv4 адрес сервера: %SERVER_IP%
echo.

REM Проверяем наличие Git
where git >nul 2>&1
if errorlevel 1 (
    echo ОШИБКА: Git не установлен
    echo Установите Git: https://git-scm.com/download/win
    pause
    exit /b 1
)

echo [1/3] Проверка Git репозитория...
cd /d "%~dp0"
git status >nul 2>&1
if errorlevel 1 (
    echo Git репозиторий не инициализирован. Инициализация...
    git init
    git branch -M main
)

echo.
echo [2/3] Проверка remote репозитория...
git remote -v >nul 2>&1
if errorlevel 1 (
    echo Remote репозиторий не настроен.
    set /p GIT_URL="Введите URL репозитория (например, https://github.com/Niyaz-313/trading_bot.git): "
    if not "!GIT_URL!"=="" (
        git remote add origin "!GIT_URL!"
    )
) else (
    echo Remote репозиторий настроен:
    git remote -v
)

echo.
echo [3/3] Отправка кода на GitHub...
echo.
echo ВАЖНО: Если репозиторий приватный, вам может потребоваться:
echo   1. Personal Access Token (вместо пароля)
echo   2. Или настроить SSH ключи
echo.
pause

git add .
git commit -m "Auto-sync: %date% %time%" 2>nul
git push origin main

if errorlevel 1 (
    echo.
    echo ОШИБКА при отправке на GitHub
    echo Проверьте:
    echo   1. Настроен ли remote origin
    echo   2. Есть ли доступ к репозиторию
    echo   3. Правильность URL репозитория
    pause
    exit /b 1
)

echo.
echo ========================================
echo КОД ОТПРАВЛЕН НА GITHUB!
echo ========================================
echo.
echo Теперь на сервере выполните:
echo   ssh botuser@%SERVER_IP%
echo   cd ~/trading_bot
echo   git pull origin main
echo.
pause

chcp 65001 > nul
setlocal enabledelayedexpansion

echo ========================================
echo БЫСТРОЕ ПОДКЛЮЧЕНИЕ GIT К СЕРВЕРУ
echo ========================================
echo.

REM Получаем IPv4 адрес сервера
set /p SERVER_IP="Введите IPv4 адрес сервера: "
if "%SERVER_IP%"=="" (
    echo ОШИБКА: IPv4 адрес не введен
    pause
    exit /b 1
)

echo.
echo IPv4 адрес сервера: %SERVER_IP%
echo.

REM Проверяем наличие Git
where git >nul 2>&1
if errorlevel 1 (
    echo ОШИБКА: Git не установлен
    echo Установите Git: https://git-scm.com/download/win
    pause
    exit /b 1
)

echo [1/3] Проверка Git репозитория...
cd /d "%~dp0"
git status >nul 2>&1
if errorlevel 1 (
    echo Git репозиторий не инициализирован. Инициализация...
    git init
    git branch -M main
)

echo.
echo [2/3] Проверка remote репозитория...
git remote -v >nul 2>&1
if errorlevel 1 (
    echo Remote репозиторий не настроен.
    set /p GIT_URL="Введите URL репозитория (например, https://github.com/Niyaz-313/trading_bot.git): "
    if not "!GIT_URL!"=="" (
        git remote add origin "!GIT_URL!"
    )
) else (
    echo Remote репозиторий настроен:
    git remote -v
)

echo.
echo [3/3] Отправка кода на GitHub...
echo.
echo ВАЖНО: Если репозиторий приватный, вам может потребоваться:
echo   1. Personal Access Token (вместо пароля)
echo   2. Или настроить SSH ключи
echo.
pause

git add .
git commit -m "Auto-sync: %date% %time%" 2>nul
git push origin main

if errorlevel 1 (
    echo.
    echo ОШИБКА при отправке на GitHub
    echo Проверьте:
    echo   1. Настроен ли remote origin
    echo   2. Есть ли доступ к репозиторию
    echo   3. Правильность URL репозитория
    pause
    exit /b 1
)

echo.
echo ========================================
echo КОД ОТПРАВЛЕН НА GITHUB!
echo ========================================
echo.
echo Теперь на сервере выполните:
echo   ssh botuser@%SERVER_IP%
echo   cd ~/trading_bot
echo   git pull origin main
echo.
pause

chcp 65001 > nul
setlocal enabledelayedexpansion

echo ========================================
echo БЫСТРОЕ ПОДКЛЮЧЕНИЕ GIT К СЕРВЕРУ
echo ========================================
echo.

REM Получаем IPv4 адрес сервера
set /p SERVER_IP="Введите IPv4 адрес сервера: "
if "%SERVER_IP%"=="" (
    echo ОШИБКА: IPv4 адрес не введен
    pause
    exit /b 1
)

echo.
echo IPv4 адрес сервера: %SERVER_IP%
echo.

REM Проверяем наличие Git
where git >nul 2>&1
if errorlevel 1 (
    echo ОШИБКА: Git не установлен
    echo Установите Git: https://git-scm.com/download/win
    pause
    exit /b 1
)

echo [1/3] Проверка Git репозитория...
cd /d "%~dp0"
git status >nul 2>&1
if errorlevel 1 (
    echo Git репозиторий не инициализирован. Инициализация...
    git init
    git branch -M main
)

echo.
echo [2/3] Проверка remote репозитория...
git remote -v >nul 2>&1
if errorlevel 1 (
    echo Remote репозиторий не настроен.
    set /p GIT_URL="Введите URL репозитория (например, https://github.com/Niyaz-313/trading_bot.git): "
    if not "!GIT_URL!"=="" (
        git remote add origin "!GIT_URL!"
    )
) else (
    echo Remote репозиторий настроен:
    git remote -v
)

echo.
echo [3/3] Отправка кода на GitHub...
echo.
echo ВАЖНО: Если репозиторий приватный, вам может потребоваться:
echo   1. Personal Access Token (вместо пароля)
echo   2. Или настроить SSH ключи
echo.
pause

git add .
git commit -m "Auto-sync: %date% %time%" 2>nul
git push origin main

if errorlevel 1 (
    echo.
    echo ОШИБКА при отправке на GitHub
    echo Проверьте:
    echo   1. Настроен ли remote origin
    echo   2. Есть ли доступ к репозиторию
    echo   3. Правильность URL репозитория
    pause
    exit /b 1
)

echo.
echo ========================================
echo КОД ОТПРАВЛЕН НА GITHUB!
echo ========================================
echo.
echo Теперь на сервере выполните:
echo   ssh botuser@%SERVER_IP%
echo   cd ~/trading_bot
echo   git pull origin main
echo.
pause




