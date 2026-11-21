import json
import os
import re
import subprocess
import tempfile
import psutil
import requests
import mss
from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

load_dotenv(r"C:\XiaoZhi-PC\.env")

STATE_FILE = r"C:\XiaoZhi-PC\state.json"
WORKSPACE_DIR = r"C:\XiaoZhi-PC\workspace"
mcp = MCPServer("Johnny-Silverhand-Secure-Hub")

# === БЛОК БЕЗОПАСНОСТИ: ЧЕРНЫЙ СПИСОК ОПАСНЫХ ПАТТЕРНОВ ===
FORBIDDEN_PATTERNS = [
    r"rm\s+-rf", r"del\s+/s", r"rmdir", r"remove-item.*-recurse",
    r"format-", r"stop-computer", r"restart-computer", r"reg\s+delete",
    r"net\s+user", r"invoke-expression", r"\biex\b", r"\.env"
]

def _is_command_safe(cmd: str) -> tuple[bool, str]:
    cmd_lower = cmd.lower()
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, cmd_lower):
            return False, f"Заблокировано политикой безопасности (совпадение с запрещенным паттерном: {pattern})."
    return True, "OK"

# === БЛОК 1: СИСТЕМА 3 РЕЖИМОВ ===
MODES_CONFIG = {
    "combat": {
        "name": "Боевой / Нетраннер (Рабочий)",
        "rules": "Режим кодинга и администрирования. Сухо, технически точно, без воды. Используй инструменты ПК и Docker."
    },
    "companion": {
        "name": "Напарник / Инфо (Общение)",
        "rules": "Повседневное общение в стиле Джонни Сильверхенда: уверенно, с легкой харизмой и сарказмом, но по делу."
    },
    "entertainment": {
        "name": "Найт-Сити / Самурай (Развлекательный)",
        "rules": "Развлекательный режим. Харизма рокера из 2077, шутки, текстовые квесты по киберпанку, викторины."
    }
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
    """Переключает режим работы: 'combat' (рабочий), 'companion' (общение), 'entertainment' (развлекательный)."""
    mode = mode.lower().strip()
    if mode not in MODES_CONFIG:
        return f"Неизвестный режим '{mode}'. Доступны: combat, companion, entertainment."
    state = _load_state()
    state["mode"] = mode
    _save_state(state)
    info = MODES_CONFIG[mode]
    return f"Активирован режим: {info['name']}. Правила: {info['rules']}"

@mcp.tool()
def get_current_mode() -> str:
    """Возвращает текущий активный режим работы."""
    mode = _load_state().get("mode", "companion")
    info = MODES_CONFIG.get(mode, MODES_CONFIG["companion"])
    return f"Текущий режим: {info['name']} ({mode}). Правила: {info['rules']}"

# === БЛОК 2: БЕЗОПАСНОЕ УПРАВЛЕНИЕ ПК И DOCKER ===

@mcp.tool()
def run_safe_powershell(command: str) -> str:
    """Выполняет безопасную диагностическую команду PowerShell в изолированной папке workspace."""
    is_safe, reason = _is_command_safe(command)
    if not is_safe:
        return reason
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            cwd=WORKSPACE_DIR,
            capture_output=True, text=True, encoding="cp866", timeout=20
        )
        out = result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
        return out if out else "Команда выполнена."
    except Exception as e:
        return f"Ошибка выполнения: {str(e)}"

@mcp.tool()
def get_pc_telemetry() -> str:
    """Возвращает загрузку CPU, RAM и свободное место на диске C."""
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")
    return (
        f"CPU: {cpu}% | RAM: {ram.percent}% ({round(ram.used / 1024**3, 1)}/{round(ram.total / 1024**3, 1)} ГБ) | "
        f"Диск C свободно: {round(disk.free / 1024**3, 1)} ГБ"
    )

@mcp.tool()
def manage_docker(action: str, container_name: str = "") -> str:
    """Управляет Docker. action: 'ps', 'start', 'stop', 'logs'."""
    if container_name and not re.match(r"^[a-zA-Z0-9_.-]+$", container_name):
        return "Ошибка безопасности: недопустимое имя контейнера."
    cmd_map = {
        "ps": "docker ps -a --format 'table {{.Names}}\t{{.Status}}'",
        "start": f"docker start {container_name}",
        "stop": f"docker stop {container_name}",
        "logs": f"docker logs --tail 20 {container_name}"
    }
    if action not in cmd_map:
        return "Доступные действия: ps, start, stop, logs."
    return run_safe_powershell(cmd_map[action])

@mcp.tool()
def open_in_vscode(target_path: str = WORKSPACE_DIR) -> str:
    """Открывает папку или файл в VS Code (только внутри C:\\XiaoZhi-PC)."""
    abs_path = os.path.abspath(target_path)
    if not abs_path.startswith(r"C:\XiaoZhi-PC"):
        return "Доступ разрешен только к директории C:\\XiaoZhi-PC."
    subprocess.Popen(["code", abs_path], shell=True)
    return f"Открыто в VS Code: {abs_path}"

# === БЛОК 3: СВЯЗЬ СО СМАРТФОНОМ (3 ВАРИАНТА) ===

@mcp.tool()
def phone_send_telegram(message: str, attach_screenshot: bool = False) -> str:
    """Канал 1 (Telegram): Отправляет текст или скриншот экрана ПК на телефон."""
    token = os.getenv("PHONE_TG_BOT_TOKEN", "").strip()
    chat_id = os.getenv("PHONE_TG_CHAT_ID", "").strip()
    if not token or not chat_id:
        return "Telegram не настроен в .env."
    tg_api = "https://" + "api.telegram.org" + "/bot"
    try:
        if attach_screenshot:
            with mss.mss() as sct:
                tmp_path = os.path.join(tempfile.gettempdir(), "xiaozhi_screen.png")
                sct.shot(output=tmp_path)
            with open(tmp_path, "rb") as img:
                resp = requests.post(f"{tg_api}{token}/sendPhoto", data={"chat_id": chat_id, "caption": message}, files={"photo": img}, timeout=15)
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        else:
            resp = requests.post(f"{tg_api}{token}/sendMessage", json={"chat_id": chat_id, "text": message}, timeout=10)
        return "Отправлено в Telegram." if resp.ok else f"Ошибка Telegram: {resp.status_code}"
    except Exception as e:
        return f"Сбой Telegram: {str(e)}"

@mcp.tool()
def phone_trigger_wifi_webhook(action_name: str, payload: str = "") -> str:
    """Канал 2 (Локальный Wi-Fi MacroDroid): Вызывает триггер на телефоне."""
    base_url = os.getenv("PHONE_MACRODROID_URL", "").strip()
    if not base_url:
        return "MacroDroid не настроен в .env."
    try:
        resp = requests.get(f"{base_url.rstrip('/')}/{action_name}", params={"data": payload}, timeout=5)
        return f"Сигнал '{action_name}' отправлен по Wi-Fi."
    except Exception as e:
        return f"Телефон недоступен в сети: {str(e)}"

@mcp.tool()
def phone_adb_command(adb_args: str) -> str:
    """Канал 3 (ADB по Wi-Fi): Безопасные команды статуса телефона."""
    adb_addr = os.getenv("PHONE_ADB_ADDRESS", "").strip()
    if not adb_addr:
        return "ADB не настроен в .env."
    if any(bad in adb_args.lower() for bad in ["rm ", "wipe", "format", "uninstall"]):
        return "Команда заблокирована политикой безопасности."
    return run_safe_powershell(f"adb connect {adb_addr}; adb -s {adb_addr} {adb_args}")

# === БЛОК 4: БЕСПЛАТНЫЕ РЕСУРСЫ, ЗАМЕТКИ, МЕДИА И УМНЫЙ ДОМ ===

@mcp.tool()
def get_weather(city: str = "") -> str:
    """Получает текущую погоду и краткий прогноз без API-ключей (по умолчанию Санкт-Петербург)."""
    target_city = city.strip() if city.strip() else os.getenv("DEFAULT_CITY", "Saint-Petersburg")
    weather_url = "https://" + "wttr.in" + f"/{target_city}?format=3&lang=ru"
    try:
        resp = requests.get(weather_url, timeout=8)
        return resp.text.strip() if resp.ok else f"Не удалось получить погоду (код {resp.status_code})."
    except Exception as e:
        return f"Ошибка сервиса погоды: {str(e)}"

@mcp.tool()
def manage_notes(action: str, text: str = "") -> str:
    """Управляет голосовыми заметками в workspace/notes.md. action: 'add' (добавить), 'read' (прочитать), 'clear' (очистить)."""
    notes_file = os.path.join(WORKSPACE_DIR, "notes.md")
    if action == "add":
        if not text.strip():
            return "Пустая заметка не добавлена."
        with open(notes_file, "a", encoding="utf-8") as f:
            f.write(f"- {text.strip()}\n")
        return f"Записано в заметки: {text.strip()}"
    elif action == "read":
        if not os.path.exists(notes_file):
            return "Список заметок пока пуст."
        with open(notes_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
        return content if content else "Список заметок пуст."
    elif action == "clear":
        with open(notes_file, "w", encoding="utf-8") as f:
            f.write("")
        return "Заметки очищены."
    return "Доступные действия: add, read, clear."

@mcp.tool()
def media_control(command: str) -> str:
    """Управляет звуком и медиаплеером Windows. Доступно: 'vol_up', 'vol_down', 'mute', 'play_pause', 'next'."""
    key_codes = {
        "vol_up": 175,
        "vol_down": 174,
        "mute": 173,
        "play_pause": 179,
        "next": 176
    }
    if command not in key_codes:
        return "Доступные команды: vol_up, vol_down, mute, play_pause, next."
    code_num = key_codes[command]
    ps_cmd = f"$wsh = New-Object -ComObject WScript.Shell; $wsh.SendKeys([char]{code_num})"
    return run_safe_powershell(ps_cmd)

@mcp.tool()
def smart_home_control(device_name: str, state: str) -> str:
    """Управляет устройствами умного дома (eWeLink / SmartLife) через вебхук. state: 'on' или 'off'."""
    hook_url = os.getenv("SMART_HOME_WEBHOOK_URL", "").strip()
    if not hook_url:
        return f"Шлюз умного дома не настроен в .env (SMART_HOME_WEBHOOK_URL). Запрос для '{device_name}' -> '{state}' зафиксирован."
    try:
        resp = requests.post(hook_url, json={"device": device_name, "state": state}, timeout=5)
        return f"Устройство '{device_name}' переключено в '{state}'." if resp.ok else f"Ошибка умного дома: {resp.status_code}"
    except Exception as e:
        return f"Сбой связи с умным домом: {str(e)}"
if __name__ == "__main__":
    mcp.run(transport="stdio")

