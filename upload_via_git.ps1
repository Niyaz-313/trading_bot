# Скрипт для загрузки файлов через Git
# Использование: .\upload_via_git.ps1 [файл1] [файл2] ...

param(
    [Parameter(Mandatory=$false)]
    [string[]]$Files = @("main.py")
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ЗАГРУЗКА ФАЙЛОВ ЧЕРЕЗ GIT" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Проверяем наличие Git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "ОШИБКА: Git не установлен!" -ForegroundColor Red
    Write-Host "Установите Git: https://git-scm.com/download/win" -ForegroundColor Yellow
    exit 1
}

# Проверяем, что мы в Git репозитории
$gitRoot = git rev-parse --show-toplevel 2>$null
if (-not $gitRoot) {
    Write-Host "ОШИБКА: Текущая директория не является Git репозиторием!" -ForegroundColor Red
    Write-Host "Инициализируйте репозиторий: git init" -ForegroundColor Yellow
    exit 1
}

Write-Host "Git репозиторий: $gitRoot" -ForegroundColor Green
Write-Host ""

# Добавляем файлы
foreach ($file in $Files) {
    if (-not (Test-Path $file)) {
        Write-Host "⚠ Предупреждение: Файл '$file' не найден, пропускаем..." -ForegroundColor Yellow
        continue
    }
    
    Write-Host "Добавление в Git: $file" -ForegroundColor Green
    git add $file
}

Write-Host ""
Write-Host "Создание коммита..." -ForegroundColor Green
$commitMessage = "Update: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
git commit -m $commitMessage

if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠ Предупреждение: Не удалось создать коммит (возможно, нет изменений)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Отправка на сервер (GitHub/GitLab)..." -ForegroundColor Green
git push

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "✓ ФАЙЛЫ УСПЕШНО ОТПРАВЛЕНЫ!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Теперь на сервере выполните:" -ForegroundColor Yellow
    Write-Host "  cd ~/trading_bot" -ForegroundColor Yellow
    Write-Host "  git pull" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "✗ ОШИБКА при отправке на сервер" -ForegroundColor Red
    Write-Host "Проверьте:" -ForegroundColor Yellow
    Write-Host "  1. Настроен ли remote origin (git remote -v)" -ForegroundColor Yellow
    Write-Host "  2. Есть ли доступ к репозиторию" -ForegroundColor Yellow
    Write-Host "  3. Правильность URL репозитория" -ForegroundColor Yellow
}

# Использование: .\upload_via_git.ps1 [файл1] [файл2] ...

param(
    [Parameter(Mandatory=$false)]
    [string[]]$Files = @("main.py")
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ЗАГРУЗКА ФАЙЛОВ ЧЕРЕЗ GIT" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Проверяем наличие Git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "ОШИБКА: Git не установлен!" -ForegroundColor Red
    Write-Host "Установите Git: https://git-scm.com/download/win" -ForegroundColor Yellow
    exit 1
}

# Проверяем, что мы в Git репозитории
$gitRoot = git rev-parse --show-toplevel 2>$null
if (-not $gitRoot) {
    Write-Host "ОШИБКА: Текущая директория не является Git репозиторием!" -ForegroundColor Red
    Write-Host "Инициализируйте репозиторий: git init" -ForegroundColor Yellow
    exit 1
}

Write-Host "Git репозиторий: $gitRoot" -ForegroundColor Green
Write-Host ""

# Добавляем файлы
foreach ($file in $Files) {
    if (-not (Test-Path $file)) {
        Write-Host "⚠ Предупреждение: Файл '$file' не найден, пропускаем..." -ForegroundColor Yellow
        continue
    }
    
    Write-Host "Добавление в Git: $file" -ForegroundColor Green
    git add $file
}

Write-Host ""
Write-Host "Создание коммита..." -ForegroundColor Green
$commitMessage = "Update: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
git commit -m $commitMessage

if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠ Предупреждение: Не удалось создать коммит (возможно, нет изменений)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Отправка на сервер (GitHub/GitLab)..." -ForegroundColor Green
git push

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "✓ ФАЙЛЫ УСПЕШНО ОТПРАВЛЕНЫ!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Теперь на сервере выполните:" -ForegroundColor Yellow
    Write-Host "  cd ~/trading_bot" -ForegroundColor Yellow
    Write-Host "  git pull" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "✗ ОШИБКА при отправке на сервер" -ForegroundColor Red
    Write-Host "Проверьте:" -ForegroundColor Yellow
    Write-Host "  1. Настроен ли remote origin (git remote -v)" -ForegroundColor Yellow
    Write-Host "  2. Есть ли доступ к репозиторию" -ForegroundColor Yellow
    Write-Host "  3. Правильность URL репозитория" -ForegroundColor Yellow
}

# Использование: .\upload_via_git.ps1 [файл1] [файл2] ...

param(
    [Parameter(Mandatory=$false)]
    [string[]]$Files = @("main.py")
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ЗАГРУЗКА ФАЙЛОВ ЧЕРЕЗ GIT" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Проверяем наличие Git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "ОШИБКА: Git не установлен!" -ForegroundColor Red
    Write-Host "Установите Git: https://git-scm.com/download/win" -ForegroundColor Yellow
    exit 1
}

# Проверяем, что мы в Git репозитории
$gitRoot = git rev-parse --show-toplevel 2>$null
if (-not $gitRoot) {
    Write-Host "ОШИБКА: Текущая директория не является Git репозиторием!" -ForegroundColor Red
    Write-Host "Инициализируйте репозиторий: git init" -ForegroundColor Yellow
    exit 1
}

Write-Host "Git репозиторий: $gitRoot" -ForegroundColor Green
Write-Host ""

# Добавляем файлы
foreach ($file in $Files) {
    if (-not (Test-Path $file)) {
        Write-Host "⚠ Предупреждение: Файл '$file' не найден, пропускаем..." -ForegroundColor Yellow
        continue
    }
    
    Write-Host "Добавление в Git: $file" -ForegroundColor Green
    git add $file
}

Write-Host ""
Write-Host "Создание коммита..." -ForegroundColor Green
$commitMessage = "Update: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
git commit -m $commitMessage

if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠ Предупреждение: Не удалось создать коммит (возможно, нет изменений)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Отправка на сервер (GitHub/GitLab)..." -ForegroundColor Green
git push

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "✓ ФАЙЛЫ УСПЕШНО ОТПРАВЛЕНЫ!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Теперь на сервере выполните:" -ForegroundColor Yellow
    Write-Host "  cd ~/trading_bot" -ForegroundColor Yellow
    Write-Host "  git pull" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "✗ ОШИБКА при отправке на сервер" -ForegroundColor Red
    Write-Host "Проверьте:" -ForegroundColor Yellow
    Write-Host "  1. Настроен ли remote origin (git remote -v)" -ForegroundColor Yellow
    Write-Host "  2. Есть ли доступ к репозиторию" -ForegroundColor Yellow
    Write-Host "  3. Правильность URL репозитория" -ForegroundColor Yellow
}





