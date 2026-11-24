import os, time, datetime, serial

LOG_FILE = r"C:\XiaoZhi-PC\logs\esp32_live.log"
PAUSE_FLAG = r"C:\XiaoZhi-PC\logs\pause_com6.flag"
MAX_BYTES = 5 * 1024 * 1024  # Максимум 5 МБ

def trim_log():
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > MAX_BYTES:
        with open(LOG_FILE, "rb") as f:
            f.seek(-MAX_BYTES // 2, os.SEEK_END)
            tail = f.read()
        with open(LOG_FILE, "wb") as f:
            f.write(tail)

while True:
    if os.path.exists(PAUSE_FLAG):
        time.sleep(2)
        continue
    try:
        with serial.Serial("COM6", 115200, timeout=1) as ser:
            with open(LOG_FILE, "a", encoding="utf-8", errors="replace") as lf:
                lf.write(f"\n=== [{datetime.datetime.now().isoformat(timespec='seconds')}] Подключено к COM6 ===\n")
                lf.flush()
                while not os.path.exists(PAUSE_FLAG):
                    line = ser.readline().decode("utf-8", errors="replace").strip()
                    if line:
                        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        lf.write(f"[{ts}] {line}\n")
                        lf.flush()
                        trim_log()
    except Exception:
        time.sleep(5)