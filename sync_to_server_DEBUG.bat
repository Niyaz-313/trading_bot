@echo off
REM Отладочная версия скрипта синхронизации
REM Логирует все действия в файл для диагностики

setlocal enabledelayedexpansion

REM Получаем путь к директории скрипта
set "SCRIPT_DIR=%~dp0"
set "LOG_FILE=%SCRIPT_DIR%sync_log.txt"

REM Очищаем старый лог
echo [%date% %time%] Запуск скрипта синхронизации > "%LOG_FILE%"
echo Текущая директория: %CD% >> "%LOG_FILE%"
echo Директория скрипта: %SCRIPT_DIR% >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

REM Переходим в директорию скрипта
cd /d "%SCRIPT_DIR%" 2>>"%LOG_FILE%"
if errorlevel 1 (
    echo ОШИБКА: Не удалось перейти в директорию скрипта >> "%LOG_FILE%"
    echo ОШИБКА: Не удалось перейти в директорию скрипта
    echo Путь: %SCRIPT_DIR%
    echo Лог сохранен в: %LOG_FILE%
    pause
    exit /b 1
)

echo Текущая директория после перехода: %CD% >> "%LOG_FILE%"

REM Проверяем наличие Git
echo Проверка Git... >> "%LOG_FILE%"
where git >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo ОШИБКА: Git не найден >> "%LOG_FILE%"
    echo.
    echo ========================================
    echo ОШИБКА: Git не установлен или не найден в PATH
    echo ========================================
    echo.
    echo Лог сохранен в: %LOG_FILE%
    echo.
    pause
    exit /b 1
)

REM Проверяем, что это Git репозиторий
if not exist ".git" (
    echo ОШИБКА: Папка .git не найдена >> "%LOG_FILE%"
    echo.
    echo ========================================
    echo ОШИБКА: Это не Git репозиторий
    echo ========================================
    echo.
    echo Текущая директория: %CD%
    echo Лог сохранен в: %LOG_FILE%
    echo.
    pause
    exit /b 1
)

echo Git репозиторий найден >> "%LOG_FILE%"

REM Выполняем команды Git
echo. >> "%LOG_FILE%"
echo [1/4] Проверка статуса Git... >> "%LOG_FILE%"
git status --short >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo ОШИБКА: git status failed >> "%LOG_FILE%"
    echo ОШИБКА: Не удалось проверить статус Git
    echo Лог сохранен в: %LOG_FILE%
    pause
    exit /b 1
)

echo. >> "%LOG_FILE%"
echo [2/4] Добавление файлов... >> "%LOG_FILE%"
git add . >> "%LOG_FILE%" 2>&1

echo. >> "%LOG_FILE%"
echo [3/4] Коммит... >> "%LOG_FILE%"
set "COMMIT_MSG=Auto-sync: %date% %time%"
git commit -m "%COMMIT_MSG%" >> "%LOG_FILE%" 2>&1

echo. >> "%LOG_FILE%"
echo [4/4] Отправка на сервер... >> "%LOG_FILE%"
git push origin main >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo ОШИБКА: git push failed >> "%LOG_FILE%"
    echo ОШИБКА: Не удалось отправить изменения
    echo Лог сохранен в: %LOG_FILE%
    pause
    exit /b 1
)

echo Успешно завершено >> "%LOG_FILE%"
echo.
echo ========================================
echo СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА УСПЕШНО!
echo ========================================
echo.
echo Лог сохранен в: %LOG_FILE%
echo.
pause

REM Отладочная версия скрипта синхронизации
REM Логирует все действия в файл для диагностики

setlocal enabledelayedexpansion

REM Получаем путь к директории скрипта
set "SCRIPT_DIR=%~dp0"
set "LOG_FILE=%SCRIPT_DIR%sync_log.txt"

REM Очищаем старый лог
echo [%date% %time%] Запуск скрипта синхронизации > "%LOG_FILE%"
echo Текущая директория: %CD% >> "%LOG_FILE%"
echo Директория скрипта: %SCRIPT_DIR% >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

REM Переходим в директорию скрипта
cd /d "%SCRIPT_DIR%" 2>>"%LOG_FILE%"
if errorlevel 1 (
    echo ОШИБКА: Не удалось перейти в директорию скрипта >> "%LOG_FILE%"
    echo ОШИБКА: Не удалось перейти в директорию скрипта
    echo Путь: %SCRIPT_DIR%
    echo Лог сохранен в: %LOG_FILE%
    pause
    exit /b 1
)

echo Текущая директория после перехода: %CD% >> "%LOG_FILE%"

REM Проверяем наличие Git
echo Проверка Git... >> "%LOG_FILE%"
where git >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo ОШИБКА: Git не найден >> "%LOG_FILE%"
    echo.
    echo ========================================
    echo ОШИБКА: Git не установлен или не найден в PATH
    echo ========================================
    echo.
    echo Лог сохранен в: %LOG_FILE%
    echo.
    pause
    exit /b 1
)

REM Проверяем, что это Git репозиторий
if not exist ".git" (
    echo ОШИБКА: Папка .git не найдена >> "%LOG_FILE%"
    echo.
    echo ========================================
    echo ОШИБКА: Это не Git репозиторий
    echo ========================================
    echo.
    echo Текущая директория: %CD%
    echo Лог сохранен в: %LOG_FILE%
    echo.
    pause
    exit /b 1
)

echo Git репозиторий найден >> "%LOG_FILE%"

REM Выполняем команды Git
echo. >> "%LOG_FILE%"
echo [1/4] Проверка статуса Git... >> "%LOG_FILE%"
git status --short >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo ОШИБКА: git status failed >> "%LOG_FILE%"
    echo ОШИБКА: Не удалось проверить статус Git
    echo Лог сохранен в: %LOG_FILE%
    pause
    exit /b 1
)

echo. >> "%LOG_FILE%"
echo [2/4] Добавление файлов... >> "%LOG_FILE%"
git add . >> "%LOG_FILE%" 2>&1

echo. >> "%LOG_FILE%"
echo [3/4] Коммит... >> "%LOG_FILE%"
set "COMMIT_MSG=Auto-sync: %date% %time%"
git commit -m "%COMMIT_MSG%" >> "%LOG_FILE%" 2>&1

echo. >> "%LOG_FILE%"
echo [4/4] Отправка на сервер... >> "%LOG_FILE%"
git push origin main >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo ОШИБКА: git push failed >> "%LOG_FILE%"
    echo ОШИБКА: Не удалось отправить изменения
    echo Лог сохранен в: %LOG_FILE%
    pause
    exit /b 1
)

echo Успешно завершено >> "%LOG_FILE%"
echo.
echo ========================================
echo СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА УСПЕШНО!
echo ========================================
echo.
echo Лог сохранен в: %LOG_FILE%
echo.
pause

REM Отладочная версия скрипта синхронизации
REM Логирует все действия в файл для диагностики

setlocal enabledelayedexpansion

REM Получаем путь к директории скрипта
set "SCRIPT_DIR=%~dp0"
set "LOG_FILE=%SCRIPT_DIR%sync_log.txt"

REM Очищаем старый лог
echo [%date% %time%] Запуск скрипта синхронизации > "%LOG_FILE%"
echo Текущая директория: %CD% >> "%LOG_FILE%"
echo Директория скрипта: %SCRIPT_DIR% >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

REM Переходим в директорию скрипта
cd /d "%SCRIPT_DIR%" 2>>"%LOG_FILE%"
if errorlevel 1 (
    echo ОШИБКА: Не удалось перейти в директорию скрипта >> "%LOG_FILE%"
    echo ОШИБКА: Не удалось перейти в директорию скрипта
    echo Путь: %SCRIPT_DIR%
    echo Лог сохранен в: %LOG_FILE%
    pause
    exit /b 1
)

echo Текущая директория после перехода: %CD% >> "%LOG_FILE%"

REM Проверяем наличие Git
echo Проверка Git... >> "%LOG_FILE%"
where git >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo ОШИБКА: Git не найден >> "%LOG_FILE%"
    echo.
    echo ========================================
    echo ОШИБКА: Git не установлен или не найден в PATH
    echo ========================================
    echo.
    echo Лог сохранен в: %LOG_FILE%
    echo.
    pause
    exit /b 1
)

REM Проверяем, что это Git репозиторий
if not exist ".git" (
    echo ОШИБКА: Папка .git не найдена >> "%LOG_FILE%"
    echo.
    echo ========================================
    echo ОШИБКА: Это не Git репозиторий
    echo ========================================
    echo.
    echo Текущая директория: %CD%
    echo Лог сохранен в: %LOG_FILE%
    echo.
    pause
    exit /b 1
)

echo Git репозиторий найден >> "%LOG_FILE%"

REM Выполняем команды Git
echo. >> "%LOG_FILE%"
echo [1/4] Проверка статуса Git... >> "%LOG_FILE%"
git status --short >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo ОШИБКА: git status failed >> "%LOG_FILE%"
    echo ОШИБКА: Не удалось проверить статус Git
    echo Лог сохранен в: %LOG_FILE%
    pause
    exit /b 1
)

echo. >> "%LOG_FILE%"
echo [2/4] Добавление файлов... >> "%LOG_FILE%"
git add . >> "%LOG_FILE%" 2>&1

echo. >> "%LOG_FILE%"
echo [3/4] Коммит... >> "%LOG_FILE%"
set "COMMIT_MSG=Auto-sync: %date% %time%"
git commit -m "%COMMIT_MSG%" >> "%LOG_FILE%" 2>&1

echo. >> "%LOG_FILE%"
echo [4/4] Отправка на сервер... >> "%LOG_FILE%"
git push origin main >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo ОШИБКА: git push failed >> "%LOG_FILE%"
    echo ОШИБКА: Не удалось отправить изменения
    echo Лог сохранен в: %LOG_FILE%
    pause
    exit /b 1
)

echo Успешно завершено >> "%LOG_FILE%"
echo.
echo ========================================
echo СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА УСПЕШНО!
echo ========================================
echo.
echo Лог сохранен в: %LOG_FILE%
echo.
pause

REM Отладочная версия скрипта синхронизации
REM Логирует все действия в файл для диагностики

setlocal enabledelayedexpansion

REM Получаем путь к директории скрипта
set "SCRIPT_DIR=%~dp0"
set "LOG_FILE=%SCRIPT_DIR%sync_log.txt"

REM Очищаем старый лог
echo [%date% %time%] Запуск скрипта синхронизации > "%LOG_FILE%"
echo Текущая директория: %CD% >> "%LOG_FILE%"
echo Директория скрипта: %SCRIPT_DIR% >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

REM Переходим в директорию скрипта
cd /d "%SCRIPT_DIR%" 2>>"%LOG_FILE%"
if errorlevel 1 (
    echo ОШИБКА: Не удалось перейти в директорию скрипта >> "%LOG_FILE%"
    echo ОШИБКА: Не удалось перейти в директорию скрипта
    echo Путь: %SCRIPT_DIR%
    echo Лог сохранен в: %LOG_FILE%
    pause
    exit /b 1
)

echo Текущая директория после перехода: %CD% >> "%LOG_FILE%"

REM Проверяем наличие Git
echo Проверка Git... >> "%LOG_FILE%"
where git >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo ОШИБКА: Git не найден >> "%LOG_FILE%"
    echo.
    echo ========================================
    echo ОШИБКА: Git не установлен или не найден в PATH
    echo ========================================
    echo.
    echo Лог сохранен в: %LOG_FILE%
    echo.
    pause
    exit /b 1
)

REM Проверяем, что это Git репозиторий
if not exist ".git" (
    echo ОШИБКА: Папка .git не найдена >> "%LOG_FILE%"
    echo.
    echo ========================================
    echo ОШИБКА: Это не Git репозиторий
    echo ========================================
    echo.
    echo Текущая директория: %CD%
    echo Лог сохранен в: %LOG_FILE%
    echo.
    pause
    exit /b 1
)

echo Git репозиторий найден >> "%LOG_FILE%"

REM Выполняем команды Git
echo. >> "%LOG_FILE%"
echo [1/4] Проверка статуса Git... >> "%LOG_FILE%"
git status --short >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo ОШИБКА: git status failed >> "%LOG_FILE%"
    echo ОШИБКА: Не удалось проверить статус Git
    echo Лог сохранен в: %LOG_FILE%
    pause
    exit /b 1
)

echo. >> "%LOG_FILE%"
echo [2/4] Добавление файлов... >> "%LOG_FILE%"
git add . >> "%LOG_FILE%" 2>&1

echo. >> "%LOG_FILE%"
echo [3/4] Коммит... >> "%LOG_FILE%"
set "COMMIT_MSG=Auto-sync: %date% %time%"
git commit -m "%COMMIT_MSG%" >> "%LOG_FILE%" 2>&1

echo. >> "%LOG_FILE%"
echo [4/4] Отправка на сервер... >> "%LOG_FILE%"
git push origin main >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo ОШИБКА: git push failed >> "%LOG_FILE%"
    echo ОШИБКА: Не удалось отправить изменения
    echo Лог сохранен в: %LOG_FILE%
    pause
    exit /b 1
)

echo Успешно завершено >> "%LOG_FILE%"
echo.
echo ========================================
echo СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА УСПЕШНО!
echo ========================================
echo.
echo Лог сохранен в: %LOG_FILE%
echo.
pause




