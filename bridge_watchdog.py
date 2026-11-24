import os, sys, time, subprocess, datetime, ctypes

BASE_DIR = r"C:\XiaoZhi-PC"
PYTHON_EXE = os.path.join(BASE_DIR, "venv", "Scripts", "pythonw.exe")
PIPE_SCRIPT = os.path.join(BASE_DIR, "mcp_pipe.py")
SERIAL_SCRIPT = os.path.join(BASE_DIR, "esp32_serial_logger.py")
INBOX_SCRIPT = os.path.join(BASE_DIR, "ntfy_inbox_listener.py")

# Системный мьютекс Windows: гарантирует, что работает строго ОДИН экземпляр Watchdog
mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\XiaoZhi_Johnny_Watchdog_Lock")
if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
    sys.exit(0)


def if proc_inbox is None or proc_inbox.poll() is not None:
            proc_inbox = subprocess.Popen([PYTHON_EXE, INBOX_SCRIPT], cwd=BASE_DIR)
        send_cloud_heartbeat():
    """Отправляет пульс на облачную VPS, если задан CLOUD_VPS_URL в .env (иначе спит без нагрузки)."""
    try:
        from dotenv import load_dotenv
        import requests
        load_dotenv(os.path.join(BASE_DIR, ".env"))
        vps_url = os.getenv("CLOUD_VPS_URL", "").strip().rstrip("/")
        if not vps_url:
            return
        secret = os.getenv("CLOUD_HEARTBEAT_SECRET", "johnny_sbge_2077").strip()
        requests.post(f"{vps_url}/heartbeat", headers={"X-SBGE-Token": secret}, timeout=4)
    except Exception:
        pass

def notify_startup():
    try:
        sys.path.insert(0, BASE_DIR)
        import pc_agent
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pc_agent.phone_send_ntfy(f"[{ts}] Мост Джонни (Single-Instance Watchdog) активен.", attach_screenshot=False)
    except Exception:
        pass

def main():
    notify_startup()
    proc_pipe = None
    proc_serial = None
    proc_inbox = None
    while True:
        if proc_pipe is None or proc_pipe.poll() is not None:
            proc_pipe = subprocess.Popen([PYTHON_EXE, PIPE_SCRIPT], cwd=BASE_DIR)
        if proc_serial is None or proc_serial.poll() is not None:
            proc_serial = subprocess.Popen([PYTHON_EXE, SERIAL_SCRIPT], cwd=BASE_DIR)
        if proc_inbox is None or proc_inbox.poll() is not None:
            proc_inbox = subprocess.Popen([PYTHON_EXE, INBOX_SCRIPT], cwd=BASE_DIR)
        send_cloud_heartbeat()
        time.sleep(15)

if __name__ == "__main__":
    main()