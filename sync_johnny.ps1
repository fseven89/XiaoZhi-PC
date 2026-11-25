param(
    [switch]$GitPush,
    [string]$CommitMsg = "Sync Johnny v4.1: UTF-8 fix, Telegram primary, BLE radar, no deep sleep"
)

$ErrorActionPreference = "Stop"
$root = "C:\XiaoZhi-PC"
$py = "$root\venv\Scripts\python.exe"
$pytest = "$root\venv\Scripts\pytest.exe"
$pythonw = "$root\venv\Scripts\pythonw.exe"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  ЕДИНАЯ СИНХРОНИЗАЦИЯ ПРОЕКТА XIAOZHI-PC (JOHNNY v4.1)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

Write-Host "`n[1/5] Проверка синтаксиса и прогон pytest..." -ForegroundColor Yellow
& $py -m py_compile "$root\pc_agent.py" "$root\bridge_watchdog.py" "$root\ntfy_inbox_listener.py" "$root\dpapi_vault.py" "$root\redline_guard.py"
& $pytest -q "$root\tests"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERR] Тесты не пройдены! Синхронизация остановлена." -ForegroundColor Red
    exit 1
}

Write-Host "`n[2/5] Перезапуск фонового моста (bridge_watchdog.py)..." -ForegroundColor Yellow
Get-CimInstance Win32_Process | Where-Object {
    ($_.Name -match "python") -and ($_.CommandLine -match "bridge_watchdog|mcp_pipe|ntfy_inbox_listener|esp32_serial_logger")
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 1
Start-Process -FilePath $pythonw -ArgumentList "$root\bridge_watchdog.py" -WorkingDirectory $root
Write-Host "[OK] bridge_watchdog.py перезапущен (включая локальный OTA-сервер :8090)." -ForegroundColor Green

Write-Host "`n[3/5] Сборка единого слепка памяти (workspace\MASTER_CONTEXT.md)..." -ForegroundColor Yellow
$ctx = New-Object System.Text.StringBuilder
$null = $ctx.AppendLine("# XIAOZHI-PC (ЭНГРАММА ДЖОННИ) — ЕДИНЫЙ СЛЕПОК КОНТЕКСТА")
$null = $ctx.AppendLine("Обновлено: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')`n")

if (Test-Path "$root\DEV_RULES.md") { $null = $ctx.AppendLine((Get-Content "$root\DEV_RULES.md" -Raw -Encoding UTF8) + "`n---`n") }
if (Test-Path "$root\workspace\ROADMAP_V42_IDEAS.md") { $null = $ctx.AppendLine((Get-Content "$root\workspace\ROADMAP_V42_IDEAS.md" -Raw -Encoding UTF8) + "`n---`n") }
if (Test-Path "$root\ARCHITECTURE.md") { $null = $ctx.AppendLine((Get-Content "$root\ARCHITECTURE.md" -Raw -Encoding UTF8) + "`n---`n") }
if (Test-Path "$root\HARDWARE_PASSPORT.md") { $null = $ctx.AppendLine((Get-Content "$root\HARDWARE_PASSPORT.md" -Raw -Encoding UTF8) + "`n---`n") }

if (Test-Path "$root\workspace\lessons_learned.json") {
    $null = $ctx.AppendLine("## ПРАВИЛА САМООБУЧЕНИЯ (lessons_learned.json)`n```json")
    $null = $ctx.AppendLine((Get-Content "C:\XiaoZhi-PC\workspace\lessons_learned.json" -Raw -Encoding UTF8))
    $null = $ctx.AppendLine("````n---`n")
}

if (Test-Path "$root\workspace\notes.md") {
    $null = $ctx.AppendLine("## ЗАМЕТКИ И ИДЕИ (notes.md, последние 80 строк)")
    $notesTail = (Get-Content "$root\workspace\notes.md" -Tail 80 -Encoding UTF8) -join "`n"
    $null = $ctx.AppendLine($notesTail + "`n---`n")
}

[System.IO.File]::WriteAllText("$root\workspace\MASTER_CONTEXT.md", $ctx.ToString(), [System.Text.UTF8Encoding]::new($false))
Write-Host "[OK] Слепок сохранён: C:\XiaoZhi-PC\workspace\MASTER_CONTEXT.md" -ForegroundColor Green

if ($GitPush) {
    Write-Host "`n[4/5] Фиксация и отправка изменений на GitHub..." -ForegroundColor Yellow
    Set-Location $root
    git add DEV_RULES.md ARCHITECTURE.md HARDWARE_PASSPORT.md pc_agent.py bridge_watchdog.py sync_johnny.ps1 tests/test_pc_agent.py workspace/ROADMAP_V42_IDEAS.md
    git commit -m $CommitMsg 2>$null
    git push origin main
} else {
    Write-Host "`n[4/5] GitHub Push пропущен (запустите с флагом -GitPush для отправки в облако)." -ForegroundColor DarkGray
}

Write-Host "`n[5/5] СИНХРОНИЗАЦИЯ УСПЕШНО ЗАВЕРШЕНА!" -ForegroundColor Green