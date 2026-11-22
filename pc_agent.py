import datetime
import glob
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
import psutil
import requests
import mss
import serial
import serial.tools.list_ports
from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

load_dotenv(r"C:\XiaoZhi-PC\.env")

BASE_DIR = r"C:\XiaoZhi-PC"
STATE_FILE = os.path.join(BASE_DIR, "state.json")
WORKSPACE_DIR = os.path.join(BASE_DIR, "workspace")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
BACKUPS_DIR = os.path.join(BASE_DIR, "backups")
AUDIT_FILE = os.path.join(LOGS_DIR, "johnny_audit.jsonl")

os.makedirs(WORKSPACE_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(BACKUPS_DIR, exist_ok=True)

mcp = MCPServer("Johnny-Silverhand-Audited-Hub")

# === СИСТЕМА АУДИТА И БЭКАПОВ ===

def _log_event(tool_name: str, args: dict, result: str):
    """Записывает каждое действие Джонни в структурированный лог для анализа."""
    entry = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "mode": _load_state().get("mode", "companion"),
        "tool": tool_name,
        "args": args,
        "result": str(result)[:1000]
    }
    try:
        with open(AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass

def _create_auto_backup(reason: str = "auto") -> str:
    """Создает ZIP-бэкап кода и настроек (исключая .env, venv и тяжелые папки)."""
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = os.path.join(BACKUPS_DIR, f"backup_{ts}_{reason}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in ["pc_agent.py", "mcp_pipe.py", "docker-compose.yml", "Dockerfile", "state.json", "README.md"]:
            fpath = os.path.join(BASE_DIR, fname)
            if os.path.exists(fpath):
                zf.write(fpath, arcname=fname)
        for root, _, files in os.walk(WORKSPACE_DIR):
            for file in files:
                full_p = os.path.join(root, file)
                rel_p = os.path.relpath(full_p, BASE_DIR)
                zf.write(full_p, arcname=rel_p)
    # Храним только последние 20 бэкапов
    all_bkp = sorted(glob.glob(os.path.join(BACKUPS_DIR, "backup_*.zip")))
    for old_bkp in all_bkp[:-20]:
        try:
            os.remove(old_bkp)
        except Exception:
            pass
    return os.path.basename(zip_path)

@mcp.tool()
def get_johnny_audit_log(limit: int = 10) -> str:
    """Возвращает последние записи из журнала действий Джонни для анализа."""
    if not os.path.exists(AUDIT_FILE):
        return "Журнал действий пока пуст."
    with open(AUDIT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()[-limit:]
    out = []
    for line in lines:
        d = json.loads(line)
        out.append(f"[{d['timestamp']}] ({d['mode']}) {d['tool']} {d['args']} -> {d['result'][:120]}")
    res = "\n".join(out)
    return res

@mcp.tool()
def create_manual_backup(label: str = "manual") -> str:
    """Создает резервную копию проекта и рабочей папки вручную."""
    safe_label = re.sub(r"[^a-zA-Z0-9_-]", "", label) or "manual"
    bname = _create_auto_backup(safe_label)
    res = f"Создан бэкап: {bname}"
    _log_event("create_manual_backup", {"label": label}, res)
    return res

@mcp.tool()
def rollback_last_backup() -> str:
    """Восстанавливает файлы проекта и workspace из последнего резервного архива."""
    all_bkp = sorted(glob.glob(os.path.join(BACKUPS_DIR, "backup_*.zip")))
    if not all_bkp:
        return "Резервные копии не найдены."
    latest = all_bkp[-1]
    with zipfile.ZipFile(latest, "r") as zf:
        zf.extractall(BASE_DIR)
    res = f"Система успешно откачена к копии: {os.path.basename(latest)}"
    _log_event("rollback_last_backup", {}, res)
    return res

# === ДИАГНОСТИКА ПЛАТЫ ESP32-S3 ПО USB ===

@mcp.tool()
def capture_esp32_logs(seconds: int = 10) -> str:
    """Считывает системные логи с подключенной по USB колонки ESP32-S3 и сохраняет в logs/esp32_serial.log."""
    ports = list(serial.tools.list_ports.comports())
    esp_port = None
    for p in ports:
        desc = (p.description or "").lower()
        if "usb" in desc or p.device == "COM6":
            esp_port = p.device
            break
    if not esp_port and ports:
        esp_port = ports.device
    if not esp_port:
        return "COM-порт колонки ESP32-S3 не найден. Подключите устройство кабелем Type-C к ноутбуку."

    log_path = os.path.join(LOGS_DIR, "esp32_serial.log")
    collected = []
    try:
        with serial.Serial(esp_port, 115200, timeout=1) as ser:
            end_time = datetime.datetime.now() + datetime.timedelta(seconds=min(seconds, 30))
            while datetime.datetime.now() < end_time:
                line = ser.readline().decode("utf-8", errors="replace").strip()
                if line:
                    collected.append(line)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n--- Сессия {datetime.datetime.now().isoformat()} ({esp_port}) ---\n" + "\n".join(collected) + "\n")
        
        # Ищем маркеры причин перезагрузки
        crash_lines = [l for l in collected if any(w in l.lower() for w in ["rst:", "panic", "guru", "brownout", "error", "assert", "wdt"])]
        summary = f"Снято {len(collected)} строк с {esp_port} (сохранено в logs/esp32_serial.log)."
        if crash_lines:
            summary += "\nОбнаружены критические маркеры:\n" + "\n".join(crash_lines[-10:])
        _log_event("capture_esp32_logs", {"port": esp_port, "seconds": seconds}, summary)
        return summary
    except Exception as e:
        err = f"Ошибка чтения порта {esp_port}: {str(e)}"
        _log_event("capture_esp32_logs", {"port": esp_port}, err)
        return err

# === РЕЖИМЫ И БЕЗОПАСНЫЙ POWERSHELL ===

FORBIDDEN_PATTERNS = [
    r"rm\s+-rf", r"del\s+/s", r"rmdir", r"remove-item.*-recurse",
    r"format-", r"stop-computer", r"restart-computer", r"reg\s+delete",
    r"net\s+user", r"invoke-expression", r"\biex\b", r"\.env", r"bcdedit", r"diskpart"
]

def _is_command_safe(cmd: str) -> tuple[bool, str]:
    cmd_lower = cmd.lower()
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, cmd_lower):
            return False, f"Заблокировано политикой безопасности: {pattern}"
    return True, "OK"

MODES_CONFIG = {
    "combat": {"name": "Боевой / Нетраннер", "rules": "Сухо, технически точно, без воды."},
    "companion": {"name": "Напарник / Инфо", "rules": "Харизма Джонни Сильверхенда, легкий сарказм, но по делу."},
    "entertainment": {"name": "Найт-Сити / Самурай", "rules": "Развлекательный режим, шутки, квесты по киберпанку."}
}

def _load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"mode": os.getenv("DEFAULT_MODE", "companion")}

def _save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

@mcp.tool()
def switch_assistant_mode(mode: str) -> str:
    """Переключает режим работы: 'combat', 'companion', 'entertainment'."""
    mode = mode.lower().strip()
    if mode not in MODES_CONFIG:
        return "Доступны режимы: combat, companion, entertainment."
    state = _load_state()
    state["mode"] = mode
    _save_state(state)
    res = f"Активирован режим: {MODES_CONFIG[mode]['name']}."
    _log_event("switch_assistant_mode", {"mode": mode}, res)
    return res

@mcp.tool()
def run_safe_powershell(command: str) -> str:
    """Выполняет безопасную команду PowerShell с предварительным авто-бэкапом и записью в аудит-лог."""
    is_safe, reason = _is_command_safe(command)
    if not is_safe:
        _log_event("run_safe_powershell_BLOCKED", {"command": command}, reason)
        return reason
    
    # Автоматический бэкап перед выполнением любой команды
    bkp_name = _create_auto_backup("pre_ps")
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            cwd=WORKSPACE_DIR, capture_output=True, text=True, encoding="cp866", timeout=20
        )
        out = result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
        res = out if out else "Команда выполнена."
    except Exception as e:
        res = f"Ошибка: {str(e)}"
    
    _log_event("run_safe_powershell", {"command": command, "backup": bkp_name}, res)
    return res

@mcp.tool()
def get_pc_telemetry() -> str:
    """Возвращает загрузку CPU, RAM и свободное место на диске C."""
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")
    res = f"CPU: {cpu}% | RAM: {ram.percent}% | Диск C свободно: {round(disk.free / 1024**3, 1)} ГБ"
    _log_event("get_pc_telemetry", {}, res)
    return res

@mcp.tool()
def manage_docker(action: str, container_name: str = "") -> str:
    """Управляет Docker: 'ps', 'start', 'stop', 'logs'."""
    if container_name and not re.match(r"^[a-zA-Z0-9_.-]+$", container_name):
        return "Недопустимое имя контейнера."
    cmd_map = {
        "ps": "docker ps -a --format 'table {{.Names}}\t{{.Status}}'",
        "start": f"docker start {container_name}",
        "stop": f"docker stop {container_name}",
"logs": f"docker logs --tail 25 {container_name}"
}
if action not in cmd_map:
return "Доступны: ps, start, stop, logs."
return run_safe_powershell(cmd_map[action])
@mcp.tool()
def open_in_vscode(target_path: str = WORKSPACE_DIR) -> str:
"""Открывает папку или файл в VS Code (только внутри C:\XiaoZhi-PC)."""
abs_path = os.path.abspath(target_path)
if not abs_path.startswith(BASE_DIR):
return "Доступ разрешен только к C:\XiaoZhi-PC."
subprocess.Popen(["code", abs_path], shell=True)
res = f"Открыто в VS Code: {abs_path}"
_log_event("open_in_vscode", {"target_path": abs_path}, res)
return res
@mcp.tool()
def get_weather(city: str = "") -> str:
"""Получает текущую погоду без API-ключей."""
target = city.strip() if city.strip() else os.getenv("DEFAULT_CITY", "Saint-Petersburg")
url = "https://" + "wttr.in" + f"/{target}?format=3〈=ru"
try:
r = requests.get(url, timeout=8)
res = r.text.strip() if r.ok else f"Ошибка погоды: {r.status_code}"
except Exception as e:
res = f"Сбой погоды: {str(e)}"
_log_event("get_weather", {"city": target}, res)
return res
@mcp.tool()
def manage_notes(action: str, text: str = "") -> str:
"""Управляет заметками: 'add', 'read', 'clear'."""
notes_file = os.path.join(WORKSPACE_DIR, "notes.md")
if action == "add" and text.strip():
with open(notes_file, "a", encoding="utf-8") as f:
f.write(f"- {text.strip()}\n")
res = f"Записано: {text.strip()}"
elif action == "read":
res = open(notes_file, "r", encoding="utf-8").read().strip() if os.path.exists(notes_file) else "Заметок нет."
elif action == "clear":
open(notes_file, "w", encoding="utf-8").close()
res = "Заметки очищены."
else:
res = "Укажите action: add, read или clear."
_log_event("manage_notes", {"action": action}, res)
return res
@mcp.tool()
def ha_list_devices() -> str:
"""Возвращает список всех устройств умного дома из Home Assistant."""
ha_url = os.getenv("HA_URL", "http://" + "127.0.0.1" + ":8123").rstrip("/")
ha_token = os.getenv("HA_TOKEN", "").strip()
if not ha_token:
return "HA_TOKEN не задан."
try:
headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}
resp = requests.get(f"{ha_url}/api/states", headers=headers, timeout=8)
devices = []
for item in resp.json():
eid = item.get("entity_id", "")
if eid.startswith(("switch.", "light.", "climate.", "cover.", "sensor.", "vacuum.")):
fname = item.get("attributes", {}).get("friendly_name", eid)
devices.append(f"{fname} [{eid}]: {item.get('state')}")
res = "\n".join(devices) if devices else "Устройства не найдены."
except Exception as e:
res = f"Ошибка HA: {str(e)}"
_log_event("ha_list_devices", {}, f"Найдено устройств: {len(res.splitlines())}")
return res
@mcp.tool()
def ha_control_device(entity_id: str, action: str) -> str:
"""Управляет устройством в Home Assistant (turn_on, turn_off, toggle, start, return_to_base)."""
ha_url = os.getenv("HA_URL", "http://" + "127.0.0.1" + ":8123").rstrip("/")
ha_token = os.getenv("HA_TOKEN", "").strip()
domain = entity_id.split(".") if "." in entity_id else "homeassistant"
try:
headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}
resp = requests.post(f"{ha_url}/api/services/{domain}/{action}", headers=headers, json={"entity_id": entity_id}, timeout=8)
res = f"Выполнено: {action} для {entity_id}." if resp.ok else f"Ошибка: {resp.status_code}"
except Exception as e:
res = f"Сбой управления: {str(e)}"
_log_event("ha_control_device", {"entity_id": entity_id, "action": action}, res)
return res
if name == "main":
mcp.run(transport="stdio")

