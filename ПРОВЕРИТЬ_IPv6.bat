@echo off
chcp 65001 > nul
echo ========================================
echo ПРОВЕРКА НАСТРОЕК IPv6
echo ========================================
echo.

echo [1/4] Проверка статуса IPv6 на адаптерах:
powershell -Command "Get-NetAdapterBinding | Where-Object {$_.ComponentID -eq 'ms_tcpip6'} | Select-Object Name, Enabled | Format-Table -AutoSize"

echo.
echo [2/4] Проверка IPv6 адресов:
powershell -Command "Get-NetIPAddress -AddressFamily IPv6 | Where-Object {$_.IPAddress -notlike 'fe80*' -and $_.IPAddress -notlike '::1'} | Select-Object InterfaceAlias, IPAddress | Format-Table -AutoSize"

echo.
echo [3/4] Тест ping IPv6 адреса сервера:
ping -6 2a03:6f00:a::1:a8f1 -n 4

echo.
echo [4/4] Проверка маршрутизации IPv6:
powershell -Command "Get-NetRoute -AddressFamily IPv6 | Select-Object -First 10 | Format-Table -AutoSize"

echo.
echo ========================================
echo ПРОВЕРКА ЗАВЕРШЕНА
echo ========================================
echo.
pause


