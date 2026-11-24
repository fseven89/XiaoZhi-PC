import os, sys, time, subprocess, datetime

BASE_DIR = r"C:\XiaoZhi-PC"
PYTHON_EXE = os.path.join(BASE_DIR, "venv", "Scripts", "pythonw.exe")
PIPE_SCRIPT = os.path.join(BASE_DIR, "mcp_pipe.py")
SERIAL_SCRIPT = os.path.join(BASE_DIR, "esp32_serial_logger.py")
AUDIT_LOG = os.path.join(BASE_DIR, "logs", "johnny_audit.jsonl")

def notify_startup():
    try:
        sys.path.insert(0, BASE_DIR)
        import pc_agent
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pc_agent.phone_send_ntfy(f"[{ts}] Ноутбук и мост Джонни (XiaoZhi-MCP-Bridge) в сети и готовы к работе.", attach_screenshot=False)
    except Exception:
        pass

def main():
    notify_startup()
    proc_pipe = None
    proc_serial = None
    while True:
        # Следим за основным MCP-мостом к xiaozhi.me
        if proc_pipe is None or proc_pipe.poll() is not None:
            proc_pipe = subprocess.Popen([PYTHON_EXE, PIPE_SCRIPT], cwd=BASE_DIR)
        # Следим за 24/7 логгером платы COM6
        if proc_serial is None or proc_serial.poll() is not None:
            proc_serial = subprocess.Popen([PYTHON_EXE, SERIAL_SCRIPT], cwd=BASE_DIR)
        time.sleep(10)

if __name__ == "__main__":
    main()