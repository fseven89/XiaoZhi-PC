param(
    [int]$Port = 8090,
    [int]$TimeoutSec = 120
)

$root = "C:\XiaoZhi-PC"
$fwDir = Join-Path $root "xiaozhi-esp32"
$binPath = Join-Path $fwDir "build\xiaozhi.bin"

Write-Host "=== 1. СБОРКА СВЕЖЕГО XIAOZHI.BIN ДЛЯ OTA ПО WI-FI ==="
docker run --rm `
  -v "C:\XiaoZhi-PC\xiaozhi-esp32:/project" `
  -w /project `
  espressif/idf:release-v6.0 `
  bash -c "ninja -C build all"

if (($LASTEXITCODE -ne 0) -or (-not (Test-Path $binPath))) {
    Show-StepResult -Success $false -Message "Ошибка сборки xiaozhi.bin для OTA"
    exit 1
}

# Определяем локальный IP ПК в сети 192.168.x.x
$localIp = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like "192.168.*" -and $_.PrefixOrigin -ne "WellKnown" } | Select-Object -First 1).IPAddress
$otaUrl = "http://${localIp}:${Port}/xiaozhi.bin"

Write-Host "`n=== 2. ЗАПУСК ЛОКАЛЬНОГО OTA-СЕРВЕРА НА $otaUrl ==="
Write-Host "Скажите Джонни: 'Обнови прошивку с $otaUrl' (или вызовите MCP self.upgrade_firmware)"
Write-Host "Сервер будет активен $TimeoutSec секунд..."

$pyServer = Join-Path $env:TEMP "xz_ota_http.py"
@"
import http.server, socketserver, threading, time, os
os.chdir(r"$fwDir\build")
handler = http.server.SimpleHTTPRequestHandler
httpd = socketserver.ThreadingTCPServer(("0.0.0.0", $Port), handler)
t = threading.Thread(target=httpd.serve_forever, daemon=True)
t.start()
time.sleep($TimeoutSec)
httpd.shutdown()
"@ | Set-Content -Path $pyServer -Encoding UTF8

& "$root\venv\Scripts\python.exe" $pyServer
Remove-Item $pyServer -ErrorAction SilentlyContinue
Show-StepResult -Success $true -Message "Сеанс локального OTA-сервера ($otaUrl) завершён"
