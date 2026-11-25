param(
    [int]$RunSeconds = 12
)

$fwDir = "C:\XiaoZhi-PC\xiaozhi-esp32"
Write-Host "=== ЗАПУСК ВИРТУАЛЬНОГО СТЕНДА ESP32-S3 (QEMU) НА $RunSeconds СЕК ==="
Write-Host "Реальное устройство на COM6 НЕ затрагивается."

# Копируем боевой sdkconfig во временный sdkconfig.qemu с Quad PSRAM для QEMU
$sdkProd = Join-Path $fwDir "sdkconfig"
$sdkQemu = Join-Path $fwDir "sdkconfig.qemu"
if (-not (Test-Path $sdkProd)) {
    Show-StepResult -Success $false -Message "Не найден базовый sdkconfig. Сначала выполните сборку."
    exit 1
}

$cfgText = Get-Content -Path $sdkProd -Raw -Encoding UTF8
$cfgText = $cfgText -replace "CONFIG_SPIRAM_MODE_OCT=y", "# CONFIG_SPIRAM_MODE_OCT is not set`nCONFIG_SPIRAM_MODE_QUAD=y"
[System.IO.File]::WriteAllText($sdkQemu, $cfgText, (New-Object System.Text.UTF8Encoding($false)))

docker run --rm `
  -v "C:\XiaoZhi-PC\xiaozhi-esp32:/project" `
  -w /project `
  espressif/idf:release-v6.0 `
  bash -c "idf.py -B build_qemu -D SDKCONFIG=/project/sdkconfig.qemu build && \
           esptool.py --chip esp32s3 merge-bin -o /tmp/qemu_merged.bin -f raw --flash-mode dio --flash-freq 80m --flash-size 16MB 0x0 build_qemu/bootloader/bootloader.bin 0x8000 build_qemu/partition_table/partition-table.bin 0xd000 build_qemu/ota_data_initial.bin 0x20000 build_qemu/xiaozhi.bin 0x800000 build/generated_assets.bin && \
           dd if=/dev/zero bs=1M count=16 of=/tmp/qemu_flash.bin 2>/dev/null && \
           dd if=/tmp/qemu_merged.bin of=/tmp/qemu_flash.bin conv=notrunc 2>/dev/null && \
           echo '=== СТАРТ ВИРТУАЛЬНОЙ МАШИНЫ ESP32-S3 ===' && \
           timeout ${RunSeconds}s qemu-system-xtensa -nographic -machine esp32s3 -m 8M -drive file=/tmp/qemu_flash.bin,if=mtd,format=raw -global driver=timer.esp32s3.timg,property=wdt_disable,value=true; true"

$simOk = ($LASTEXITCODE -eq 0)
Remove-Item $sdkQemu -Force -ErrorAction SilentlyContinue
Show-StepResult -Success $simOk -Message "Симуляция прошивки в виртуальном стенде ESP32-S3 (QEMU) завершена"



