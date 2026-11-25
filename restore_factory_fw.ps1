$root = "C:\XiaoZhi-PC"
$pauseFlag = "$root\logs\pause_com6.flag"
$backupBin = "$root\firmware-backup\factory_16mb_backup.bin"

if (-not (Test-Path $backupBin)) {
    Show-StepResult -Success $false -Message "Заводской дамп factory_16mb_backup.bin не найден!"
    exit 1
}

New-Item -ItemType File -Path $pauseFlag -Force | Out-Null
Write-Host "Логгер COM6 поставлен на паузу. Ожидание 2 сек..."
Start-Sleep -Seconds 2

& "$root\venv\Scripts\esptool.exe" --chip esp32s3 --port COM6 --baud 921600 write_flash 0x0 $backupBin
$flashOk = ($LASTEXITCODE -eq 0)

Remove-Item $pauseFlag -Force -ErrorAction SilentlyContinue
Show-StepResult -Success $flashOk -Message "Восстановление заводской прошивки ESP32-S3 завершено"
