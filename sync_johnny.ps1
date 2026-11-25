param(
    [switch]$WithFirmware,
    [switch]$GitPush
)

$ErrorActionPreference = "Stop"
$root = "C:\XiaoZhi-PC"
Set-Location $root

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  ЕДИНАЯ СИНХРОНИЗАЦИЯ ПРОЕКТА XIAOZHI-PC (JOHNNY v4.0)   " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Валидация кода и автотесты
Write-Host "`n[1/5] Проверка синтаксиса и прогон pytest..." -ForegroundColor Yellow
& "$root\venv\Scripts\pytest.exe" -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERR] Тесты не пройдены! Синхронизация остановлена." -ForegroundColor Red
    exit 1
}

# 2. Ротация крупных логов (> 5 МБ)
Write-Host "[2/5] Проверка и ротация логов..." -ForegroundColor Yellow
Get-ChildItem "$root\logs\*.log" -ErrorAction SilentlyContinue | Where-Object { $_.Length -gt 5MB } | ForEach-Object {
    $archName = "$($_.FullName).$(Get-Date -Format 'yyyyMMdd_HHmmss').bak"
    Move-Item $_.FullName $archName -Force
    New-Item $_.FullName -ItemType File -Force | Out-Null
    Write-Host "  -> Ротирован крупный лог: $($_.Name)" -ForegroundColor DarkGray
}

# 3. Перезапуск фонового моста (чтобы pythonw подхватил свежий pc_agent.py)
Write-Host "[3/5] Синхронизация фоновых служб ПК (bridge_watchdog)..." -ForegroundColor Yellow
Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe' OR Name = 'python.exe'" | Where-Object {
    $_.CommandLine -match "bridge_watchdog|ntfy_inbox_listener|esp32_serial_logger"
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 1
Start-Process -FilePath "$root\venv\Scripts\pythonw.exe" -ArgumentList "$root\bridge_watchdog.py" -WorkingDirectory $root
Write-Host "  -> Службы перезапущены на актуальном коде." -ForegroundColor Green

# 4. Генерация единого актуального контекста (MASTER_CONTEXT.md)
Write-Host "[4/5] Сборка актуального слепка памяти (workspace\MASTER_CONTEXT.md)..." -ForegroundColor Yellow
$ctx = [System.Text.StringBuilder]::new()
$null = $ctx.AppendLine("# XIAOZHI-PC (ЭНГРАММА ДЖОННИ) — ЕДИНЫЙ СЛЕПОК КОНТЕКСТА")
$null = $ctx.AppendLine("Обновлено: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')`n")
if (Test-Path "$root\ARCHITECTURE.md") { $null = $ctx.AppendLine((Get-Content "$root\ARCHITECTURE.md" -Raw -Encoding UTF8) + "`n---`n") }
if (Test-Path "$root\HARDWARE_PASSPORT.md") { $null = $ctx.AppendLine((Get-Content "$root\HARDWARE_PASSPORT.md" -Raw -Encoding UTF8) + "`n---`n") }
if (Test-Path "$root\workspace\lessons_learned.json") {
    $null = $ctx.AppendLine("## АКТУАЛЬНЫЕ ПРАВИЛА САМООБУЧЕНИЯ (lessons_learned.json)`n```json")
    $null = $ctx.AppendLine((Get-Content "$root\workspace\lessons_learned.json" -Raw -Encoding UTF8))
    $null = $ctx.AppendLine("````n---`n")
}
if (Test-Path "$root\workspace\notes.md") {
    $null = $ctx.AppendLine("## ЗАМЕТКИ И ИДЕИ (notes.md, последние 50 строк)`n")
    $null = $ctx.AppendLine(((Get-Content "$root\workspace\notes.md" -Encoding UTF8 | Select-Object -Last 50) -join "`n"))
}
[System.IO.File]::WriteAllText("$root\workspace\MASTER_CONTEXT.md", $ctx.ToString(), [System.Text.UTF8Encoding]::new($false))

# 5. Сборка и OTA прошивки (если передан флаг -WithFirmware)
if ($WithFirmware) {
    Write-Host "[5/5] Запуск сборки и OTA прошивки ESP32-S3..." -ForegroundColor Yellow
    & "$root\ota_push_johnny.ps1"
} else {
    Write-Host "[5/5] Прошивка пропущена (для обновления платы запустите: .\sync_johnny.ps1 -WithFirmware)" -ForegroundColor DarkGray
}

if ($GitPush) {
    Write-Host "[GIT] Фиксация и отправка изменений в репозиторий..." -ForegroundColor Cyan
    git add -A
    git commit -m "chore(sync): auto-sync project state $(Get-Date -Format 'yyyy-MM-dd HH:mm')" 2>$null
    git push 2>$null
}

Write-Host "`n[ГОТОВО] Проект полностью синхронизирован!" -ForegroundColor Green