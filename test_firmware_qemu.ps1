param(
    [int]$Seconds = 12
)

$fwDir = "C:\XiaoZhi-PC\xiaozhi-esp32"
Write-Host "=== 1. СБОРКА ВИРТУАЛЬНОГО ОБРАЗА FLASH (16MB) ДЛЯ ESP32-S3 QEMU ===" -ForegroundColor Cyan

docker run --rm -v "${fwDir}:/project" -w /project espressif/idf:release-v6.0 bash -c "
    esptool --chip esp32s3 merge-bin -o build/qemu_flash.bin --pad-to-size 16MB \
        0x0 build/bootloader/bootloader.bin \
        0x8000 build/partition_table/partition-table.bin \
        0xd000 build/ota_data_initial.bin \
        0x20000 build/xiaozhi.bin && \
    echo '=== 2. ЗАПУСК ПРОШИВКИ В ВИРТУАЛЬНОМ ESP32-S3 QEMU ($Seconds сек) ===' && \
    timeout -s INT ${Seconds}s qemu-system-xtensa \
        -nographic \
        -machine esp32s3 \
        -m 8M \
        -global driver=esp32s3.psram,property=size,value=8388608 \
        -global driver=esp32s3.psram,property=mode,value=octal \
        -drive file=build/qemu_flash.bin,if=mtd,format=raw \
        -nic user,model=open_eth \
        -serial mon:stdio || true
"

Write-Host "`n[OK] Виртуальный прогон ESP32-S3 QEMU завершён!" -ForegroundColor Green