@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo Обновление SYMBOLS в .env
echo ========================================
echo.

if not exist ".env" (
  echo Файл .env не найден в папке проекта.
  echo Сначала создайте его: скопируйте env_template.txt в .env и заполните токены.
  echo.
  pause
  exit /b 1
)

python update_env_symbols.py

echo.
echo Готово. Откройте .env и проверьте строку SYMBOLS=
echo.
pause


