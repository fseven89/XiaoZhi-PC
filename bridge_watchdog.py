# === XIAOZHI ARMOR: KERNEL ATOMIC LOCK ===
import os as _os, sys as _sys, msvcrt as _msvcrt
from pathlib import Path as _Path

_LOCK_PATH = _Path(r"C:\XiaoZhi-PC\logs\watchdog.lock")
_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
_LOCK_FH = open(_LOCK_PATH, "w")
try:
    _msvcrt.locking(_LOCK_FH.fileno(), _msvcrt.LK_NBLCK, 1)
    _LOCK_FH.write(str(_os.getpid()))
    _LOCK_FH.flush()
except OSError:
    _sys.exit(0)
# === END KERNEL ATOMIC LOCK ===

# Copyright (c) 2026 Курчицикий М.С (fseven89). All rights reserved.
import os, sys, time, subprocess, datetime, ctypes, shutil

BASE_DIR = r"C:\XiaoZhi-PC"
PYTHON_EXE = os.path.join(BASE_DIR, "venv", "Scripts", "pythonw.exe")
PIPE_SCRIPT = os.path.join(BASE_DIR, "mcp_pipe.py")
SERIAL_SCRIPT = os.path.join(BASE_DIR, "esp32_serial_logger.py")
INBOX_SCRIPT = os.path.join(BASE_DIR, "ntfy_inbox_listener.py")

mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\XiaoZhi_Johnny_Watchdog_Lock")
if ctypes.windll.kernel32.GetLastError() == 183:
    sys.exit(0)


def ensure_ollama_running():
    """Проверяет доступность локального сервера Ollama (11434) и поднимает его при падении."""
    try:
        import urllib.request
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as resp:
            if resp.status == 200:
                return
    except Exception:
        pass

    ollama_bin = shutil.which("ollama")
    if not ollama_bin:
        local_app = os.getenv("LOCALAPPDATA", "")
        candidate = os.path.join(local_app, "Programs", "Ollama", "ollama.exe")
        if os.path.exists(candidate):
            ollama_bin = candidate

    if ollama_bin:
        try:
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            subprocess.Popen(
                [ollama_bin, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags
            )
        except Exception:
            pass


def send_cloud_heartbeat():
    try:
        from dotenv import load_dotenv
        import requests
        load_dotenv(os.path.join(BASE_DIR, ".env"))
        vps_url = os.getenv("CLOUD_VPS_URL", "").strip().rstrip("/")
        if not vps_url:
            return
        secret = os.getenv("CLOUD_HEARTBEAT_SECRET", "johnny_sbge_2077").strip()
        requests.post(f"{vps_url}/sbge-heartbeat", headers={"X-SBGE-Token": secret}, timeout=4)
    except Exception:
        pass


def notify_startup():
    try:
        sys.path.insert(0, BASE_DIR)
        import pc_agent
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pc_agent.phone_send_ntfy(
            f"[{ts}] Мост Джонни (Watchdog + Ollama Auto-Heal + Vision Inbox) активен.",
            attach_screenshot=False
        )
    except Exception:
        pass


def main():
    ensure_ollama_running()
    notify_startup()
    proc_pipe = None
    proc_serial = None
    proc_inbox = None
    while True:
        ensure_ollama_running()
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