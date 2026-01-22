@echo off
chcp 65001 > nul
echo ========================================
echo ИСПРАВЛЕНИЕ ПРОБЛЕМЫ IPv6 В WINDOWS
echo ========================================
echo.
echo ВНИМАНИЕ: Этот скрипт требует прав администратора!
echo.
pause

echo.
echo [1/3] Проверка IPv6...
powershell -Command "Get-NetAdapterBinding | Where-Object {$_.ComponentID -eq 'ms_tcpip6'} | Select-Object Name, Enabled | Format-Table -AutoSize"

echo.
echo [2/3] Включение IPv6 для всех адаптеров...
powershell -Command "Get-NetAdapter | Enable-NetAdapterBinding -ComponentID ms_tcpip6"

echo.
echo [3/3] Перезапуск сетевых адаптеров...
powershell -Command "Restart-NetAdapter -Name '*'"

echo.
echo ========================================
echo ГОТОВО!
echo ========================================
echo.
echo Теперь попробуйте подключиться через WinSCP снова.
echo.
pause

