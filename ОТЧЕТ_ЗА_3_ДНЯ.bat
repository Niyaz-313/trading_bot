@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

REM Анализ 3 дней с точки старта из логов (локальное время Москвы по умолчанию)
python analyze_audit_period.py --start "2026-01-04 05:49:15" --days 3 --tz Europe/Moscow

echo.
echo Готово.
echo.
echo Если нужно — запустите с другими датами:
echo   python analyze_audit_period.py --start "ГГГГ-ММ-ДД ЧЧ:ММ:СС" --days N --tz Europe/Moscow
echo.
echo Или укажите точные границы в UTC:
echo   python analyze_audit_period.py --start-utc "YYYY-MM-DDTHH:MM:SSZ" --end-utc "YYYY-MM-DDTHH:MM:SSZ"
pause


