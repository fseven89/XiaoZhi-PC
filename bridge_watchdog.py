import os, sys, time, subprocess, datetime, ctypes

BASE_DIR = r"C:\XiaoZhi-PC"
PYTHON_EXE = os.path.join(BASE_DIR, "venv", "Scripts", "pythonw.exe")
PIPE_SCRIPT = os.path.join(BASE_DIR, "mcp_pipe.py")
SERIAL_SCRIPT = os.path.join(BASE_DIR, "esp32_serial_logger.py")

# Системный мьютекс Windows: гарантирует, что работает строго ОДИН экземпляр Watchdog
mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\XiaoZhi_Johnny_Watchdog_Lock")
if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
    sys.exit(0)

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
    while True:
        if proc_pipe is None or proc_pipe.poll() is not None:
            proc_pipe = subprocess.Popen([PYTHON_EXE, PIPE_SCRIPT], cwd=BASE_DIR)
        if proc_serial is None or proc_serial.poll() is not None:
            proc_serial = subprocess.Popen([PYTHON_EXE, SERIAL_SCRIPT], cwd=BASE_DIR)
        time.sleep(10)

if __name__ == "__main__":
    main()