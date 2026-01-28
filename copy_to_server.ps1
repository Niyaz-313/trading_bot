# Скрипт для копирования файлов на сервер
# Использование: .\copy_to_server.ps1 [файл1] [файл2] ...

param(
    [Parameter(Mandatory=$false)]
    [string[]]$Files = @("main.py")
)

$SERVER_USER = "botuser"
# ЗАМЕНИТЕ на ваш IPv4 адрес сервера (например, "192.168.1.100")
# IPv4 адрес указывается БЕЗ квадратных скобок (в отличие от IPv6)
$SERVER_IP = "YOUR_IPv4_ADDRESS"
$SERVER_PATH = "~/trading_bot/"

# Проверка, что IPv4 адрес указан
if ($SERVER_IP -eq "YOUR_IPv4_ADDRESS") {
    Write-Host "ОШИБКА: Укажите IPv4 адрес сервера в переменной SERVER_IP!" -ForegroundColor Red
    Write-Host "Откройте файл copy_to_server.ps1 и замените YOUR_IPv4_ADDRESS на ваш IPv4 адрес" -ForegroundColor Yellow
    Write-Host "Пример: `$SERVER_IP = `"192.168.1.100`"" -ForegroundColor Yellow
    exit 1
}

# Проверяем наличие scp
$scpPath = $null
if (Get-Command scp -ErrorAction SilentlyContinue) {
    $scpPath = "scp"
} elseif (Test-Path "C:\Windows\System32\OpenSSH\scp.exe") {
    $scpPath = "C:\Windows\System32\OpenSSH\scp.exe"
} else {
    Write-Host "ОШИБКА: scp не найден!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Установите OpenSSH клиент:" -ForegroundColor Yellow
    Write-Host "1. Откройте PowerShell от имени администратора" -ForegroundColor Yellow
    Write-Host "2. Выполните: Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Или используйте WinSCP: https://winscp.net/" -ForegroundColor Yellow
    exit 1
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "КОПИРОВАНИЕ ФАЙЛОВ НА СЕРВЕР" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

foreach ($file in $Files) {
    if (-not (Test-Path $file)) {
        Write-Host "⚠ Предупреждение: Файл '$file' не найден, пропускаем..." -ForegroundColor Yellow
        continue
    }
    
    Write-Host "[$($Files.IndexOf($file) + 1)/$($Files.Count)] Копирование: $file" -ForegroundColor Green
    
    # IPv4 адрес указывается БЕЗ квадратных скобок (в отличие от IPv6)
    $target = "${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}"
    
    try {
        & $scpPath $file $target
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✓ Успешно скопирован: $file" -ForegroundColor Green
        } else {
            Write-Host "  ✗ Ошибка при копировании: $file" -ForegroundColor Red
        }
    } catch {
        Write-Host "  ✗ Ошибка: $_" -ForegroundColor Red
    }
    
    Write-Host ""
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ГОТОВО!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan



param(
    [Parameter(Mandatory=$false)]
    [string[]]$Files = @("main.py")
)

$SERVER_USER = "botuser"
# ЗАМЕНИТЕ на ваш IPv4 адрес сервера (например, "192.168.1.100")
# IPv4 адрес указывается БЕЗ квадратных скобок (в отличие от IPv6)
$SERVER_IP = "YOUR_IPv4_ADDRESS"
$SERVER_PATH = "~/trading_bot/"

# Проверка, что IPv4 адрес указан
if ($SERVER_IP -eq "YOUR_IPv4_ADDRESS") {
    Write-Host "ОШИБКА: Укажите IPv4 адрес сервера в переменной SERVER_IP!" -ForegroundColor Red
    Write-Host "Откройте файл copy_to_server.ps1 и замените YOUR_IPv4_ADDRESS на ваш IPv4 адрес" -ForegroundColor Yellow
    Write-Host "Пример: `$SERVER_IP = `"192.168.1.100`"" -ForegroundColor Yellow
    exit 1
}

# Проверяем наличие scp
$scpPath = $null
if (Get-Command scp -ErrorAction SilentlyContinue) {
    $scpPath = "scp"
} elseif (Test-Path "C:\Windows\System32\OpenSSH\scp.exe") {
    $scpPath = "C:\Windows\System32\OpenSSH\scp.exe"
} else {
    Write-Host "ОШИБКА: scp не найден!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Установите OpenSSH клиент:" -ForegroundColor Yellow
    Write-Host "1. Откройте PowerShell от имени администратора" -ForegroundColor Yellow
    Write-Host "2. Выполните: Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Или используйте WinSCP: https://winscp.net/" -ForegroundColor Yellow
    exit 1
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "КОПИРОВАНИЕ ФАЙЛОВ НА СЕРВЕР" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

foreach ($file in $Files) {
    if (-not (Test-Path $file)) {
        Write-Host "⚠ Предупреждение: Файл '$file' не найден, пропускаем..." -ForegroundColor Yellow
        continue
    }
    
    Write-Host "[$($Files.IndexOf($file) + 1)/$($Files.Count)] Копирование: $file" -ForegroundColor Green
    
    # IPv4 адрес указывается БЕЗ квадратных скобок (в отличие от IPv6)
    $target = "${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}"
    
    try {
        & $scpPath $file $target
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✓ Успешно скопирован: $file" -ForegroundColor Green
        } else {
            Write-Host "  ✗ Ошибка при копировании: $file" -ForegroundColor Red
        }
    } catch {
        Write-Host "  ✗ Ошибка: $_" -ForegroundColor Red
    }
    
    Write-Host ""
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ГОТОВО!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan



param(
    [Parameter(Mandatory=$false)]
    [string[]]$Files = @("main.py")
)

$SERVER_USER = "botuser"
# ЗАМЕНИТЕ на ваш IPv4 адрес сервера (например, "192.168.1.100")
# IPv4 адрес указывается БЕЗ квадратных скобок (в отличие от IPv6)
$SERVER_IP = "YOUR_IPv4_ADDRESS"
$SERVER_PATH = "~/trading_bot/"

# Проверка, что IPv4 адрес указан
if ($SERVER_IP -eq "YOUR_IPv4_ADDRESS") {
    Write-Host "ОШИБКА: Укажите IPv4 адрес сервера в переменной SERVER_IP!" -ForegroundColor Red
    Write-Host "Откройте файл copy_to_server.ps1 и замените YOUR_IPv4_ADDRESS на ваш IPv4 адрес" -ForegroundColor Yellow
    Write-Host "Пример: `$SERVER_IP = `"192.168.1.100`"" -ForegroundColor Yellow
    exit 1
}

# Проверяем наличие scp
$scpPath = $null
if (Get-Command scp -ErrorAction SilentlyContinue) {
    $scpPath = "scp"
} elseif (Test-Path "C:\Windows\System32\OpenSSH\scp.exe") {
    $scpPath = "C:\Windows\System32\OpenSSH\scp.exe"
} else {
    Write-Host "ОШИБКА: scp не найден!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Установите OpenSSH клиент:" -ForegroundColor Yellow
    Write-Host "1. Откройте PowerShell от имени администратора" -ForegroundColor Yellow
    Write-Host "2. Выполните: Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Или используйте WinSCP: https://winscp.net/" -ForegroundColor Yellow
    exit 1
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "КОПИРОВАНИЕ ФАЙЛОВ НА СЕРВЕР" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

foreach ($file in $Files) {
    if (-not (Test-Path $file)) {
        Write-Host "⚠ Предупреждение: Файл '$file' не найден, пропускаем..." -ForegroundColor Yellow
        continue
    }
    
    Write-Host "[$($Files.IndexOf($file) + 1)/$($Files.Count)] Копирование: $file" -ForegroundColor Green
    
    # IPv4 адрес указывается БЕЗ квадратных скобок (в отличие от IPv6)
    $target = "${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}"
    
    try {
        & $scpPath $file $target
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✓ Успешно скопирован: $file" -ForegroundColor Green
        } else {
            Write-Host "  ✗ Ошибка при копировании: $file" -ForegroundColor Red
        }
    } catch {
        Write-Host "  ✗ Ошибка: $_" -ForegroundColor Red
    }
    
    Write-Host ""
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ГОТОВО!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

