import datetime, glob, json, os, re, subprocess, tempfile, zipfile
import psutil, requests, mss, serial, serial.tools.list_ports
from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

load_dotenv(r"C:\XiaoZhi-PC\.env")

BASE_DIR = r"C:\XiaoZhi-PC"
STATE_FILE = os.path.join(BASE_DIR, "state.json")
WORKSPACE_DIR = os.path.join(BASE_DIR, "workspace")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
BACKUPS_DIR = os.path.join(BASE_DIR, "backups")
AUDIT_FILE = os.path.join(LOGS_DIR, "johnny_audit.jsonl")

for d in (WORKSPACE_DIR, LOGS_DIR, BACKUPS_DIR):
    os.makedirs(d, exist_ok=True)

mcp = MCPServer("Johnny-Silverhand-Hub-v3")

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

def _log_event(tool_name: str, args: dict, result: str):
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
                zf.write(full_p, arcname=os.path.relpath(full_p, BASE_DIR))
    all_bkp = sorted(glob.glob(os.path.join(BACKUPS_DIR, "backup_*.zip")))
    for old_bkp in all_bkp[:-20]:
        try:
            os.remove(old_bkp)
        except Exception:
            pass
    return os.path.basename(zip_path)

@mcp.tool()
def get_johnny_audit_log(limit: int = 10) -> str:
    """Р вЂ™Р С•Р В·Р Р†РЎР‚Р В°РЎвЂ°Р В°Р ВµРЎвЂљ Р С—Р С•РЎРѓР В»Р ВµР Т‘Р Р…Р С‘Р Вµ Р В·Р В°Р С—Р С‘РЎРѓР С‘ Р С‘Р В· Р В¶РЎС“РЎР‚Р Р…Р В°Р В»Р В° Р Т‘Р ВµР в„–РЎРѓРЎвЂљР Р†Р С‘Р в„– Р вЂќР В¶Р С•Р Р…Р Р…Р С‘."""
    if not os.path.exists(AUDIT_FILE):
        return "Р вЂ“РЎС“РЎР‚Р Р…Р В°Р В» Р Т‘Р ВµР в„–РЎРѓРЎвЂљР Р†Р С‘Р в„– Р С—Р С•Р С”Р В° Р С—РЎС“РЎРѓРЎвЂљ."
    with open(AUDIT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()[-limit:]
    return "\n".join(f"[{json.loads(l)['timestamp']}] ({json.loads(l)['mode']}) {json.loads(l)['tool']} -> {json.loads(l)['result'][:120]}" for l in lines)

@mcp.tool()
def rollback_last_backup() -> str:
    """Р вЂ™Р С•РЎРѓРЎРѓРЎвЂљР В°Р Р…Р В°Р Р†Р В»Р С‘Р Р†Р В°Р ВµРЎвЂљ РЎвЂћР В°Р в„–Р В»РЎвЂ№ Р С—РЎР‚Р С•Р ВµР С”РЎвЂљР В° Р С‘Р В· Р С—Р С•РЎРѓР В»Р ВµР Т‘Р Р…Р ВµР С–Р С• РЎР‚Р ВµР В·Р ВµРЎР‚Р Р†Р Р…Р С•Р С–Р С• Р В°РЎР‚РЎвЂ¦Р С‘Р Р†Р В°."""
    all_bkp = sorted(glob.glob(os.path.join(BACKUPS_DIR, "backup_*.zip")))
    if not all_bkp:
        return "Р В Р ВµР В·Р ВµРЎР‚Р Р†Р Р…РЎвЂ№Р Вµ Р С”Р С•Р С—Р С‘Р С‘ Р Р…Р Вµ Р Р…Р В°Р в„–Р Т‘Р ВµР Р…РЎвЂ№."
    latest = all_bkp[-1]
    with zipfile.ZipFile(latest, "r") as zf:
        zf.extractall(BASE_DIR)
    res = f"Р РЋР С‘РЎРѓРЎвЂљР ВµР СР В° Р С•РЎвЂљР С”Р В°РЎвЂЎР ВµР Р…Р В° Р С” Р С”Р С•Р С—Р С‘Р С‘: {os.path.basename(latest)}"
    _log_event("rollback_last_backup", {}, res)
    return res

FORBIDDEN_PATTERNS = [
    r"rm\s+-rf", r"del\s+/s", r"rmdir", r"remove-item.*-recurse",
    r"format-", r"stop-computer", r"restart-computer", r"reg\s+delete",
    r"net\s+user", r"invoke-expression", r"\biex\b", r"\.env(?!\.example)",
    r"bcdedit", r"diskpart", r"(^|\s)-e(nc|ncodedcommand)?(\s|$)", r"encodedcommand", r"frombase64string", r"downloadstring", r"pip\s+install", r"winget\s+install"
]

def _is_command_safe(cmd: str) -> tuple[bool, str]:
    cmd_lower = cmd.lower()
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, cmd_lower):
            return False, f"Р вЂ”Р В°Р В±Р В»Р С•Р С”Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С• Р С—Р С•Р В»Р С‘РЎвЂљР С‘Р С”Р С•Р в„– Р В±Р ВµР В·Р С•Р С—Р В°РЎРѓР Р…Р С•РЎРѓРЎвЂљР С‘: {pattern}"
    return True, "OK"

MODES_CONFIG = {
    "combat": {"name": "Р вЂР С•Р ВµР Р†Р С•Р в„– / Р СњР ВµРЎвЂљРЎР‚Р В°Р Р…Р Р…Р ВµРЎР‚", "rules": "Р РЋРЎС“РЎвЂ¦Р С•, РЎвЂљР ВµРЎвЂ¦Р Р…Р С‘РЎвЂЎР ВµРЎРѓР С”Р С‘ РЎвЂљР С•РЎвЂЎР Р…Р С•, Р В±Р ВµР В· Р Р†Р С•Р Т‘РЎвЂ№."},
    "companion": {"name": "Р СњР В°Р С—Р В°РЎР‚Р Р…Р С‘Р С” / Р ВР Р…РЎвЂћР С•", "rules": "Р ТђР В°РЎР‚Р С‘Р В·Р СР В° Р вЂќР В¶Р С•Р Р…Р Р…Р С‘ Р РЋР С‘Р В»РЎРЉР Р†Р ВµРЎР‚РЎвЂ¦Р ВµР Р…Р Т‘Р В°, Р В»Р ВµР С–Р С”Р С‘Р в„– РЎРѓР В°РЎР‚Р С”Р В°Р В·Р С, Р Р…Р С• Р С—Р С• Р Т‘Р ВµР В»РЎС“."},
    "entertainment": {"name": "Р СњР В°Р в„–РЎвЂљ-Р РЋР С‘РЎвЂљР С‘ / Р РЋР В°Р СРЎС“РЎР‚Р В°Р в„–", "rules": "Р В Р В°Р В·Р Р†Р В»Р ВµР С”Р В°РЎвЂљР ВµР В»РЎРЉР Р…РЎвЂ№Р в„– РЎР‚Р ВµР В¶Р С‘Р С, РЎв‚¬РЎС“РЎвЂљР С”Р С‘, Р С”Р Р†Р ВµРЎРѓРЎвЂљРЎвЂ№ Р С—Р С• Р С”Р С‘Р В±Р ВµРЎР‚Р С—Р В°Р Р…Р С”РЎС“."}
}

@mcp.tool()
def switch_assistant_mode(mode: str) -> str:
    """Р СџР ВµРЎР‚Р ВµР С”Р В»РЎР‹РЎвЂЎР В°Р ВµРЎвЂљ РЎР‚Р ВµР В¶Р С‘Р С РЎР‚Р В°Р В±Р С•РЎвЂљРЎвЂ№: combat, companion, entertainment."""
    mode = mode.lower().strip()
    if mode not in MODES_CONFIG:
        return "Р вЂќР С•РЎРѓРЎвЂљРЎС“Р С—Р Р…РЎвЂ№ РЎР‚Р ВµР В¶Р С‘Р СРЎвЂ№: combat, companion, entertainment."
    state = _load_state()
    state["mode"] = mode
    _save_state(state)
    res = f"Р С’Р С”РЎвЂљР С‘Р Р†Р С‘РЎР‚Р С•Р Р†Р В°Р Р… РЎР‚Р ВµР В¶Р С‘Р С: {MODES_CONFIG[mode]['name']}."
    _log_event("switch_assistant_mode", {"mode": mode}, res)
    return res

@mcp.tool()
def run_safe_powershell(command: str) -> str:
    """Р вЂ™РЎвЂ№Р С—Р С•Р В»Р Р…РЎРЏР ВµРЎвЂљ Р В±Р ВµР В·Р С•Р С—Р В°РЎРѓР Р…РЎС“РЎР‹ Р С”Р С•Р СР В°Р Р…Р Т‘РЎС“ PowerShell РЎРѓ Р С—РЎР‚Р ВµР Т‘Р Р†Р В°РЎР‚Р С‘РЎвЂљР ВµР В»РЎРЉР Р…РЎвЂ№Р С Р В°Р Р†РЎвЂљР С•-Р В±РЎРЊР С”Р В°Р С—Р С•Р С."""
    is_safe, reason = _is_command_safe(command)
    if not is_safe:
        _log_event("run_safe_powershell_BLOCKED", {"command": command}, reason)
        return reason
    bkp_name = _create_auto_backup("pre_ps")
    try:
        result = subprocess.run(["powershell", "-NoProfile", "-Command", command], cwd=WORKSPACE_DIR, capture_output=True, text=True, encoding="cp866", timeout=20)
        out = result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
        res = out if out else "Р С™Р С•Р СР В°Р Р…Р Т‘Р В° Р Р†РЎвЂ№Р С—Р С•Р В»Р Р…Р ВµР Р…Р В°."
    except Exception as e:
        res = f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В°: {str(e)}"
    _log_event("run_safe_powershell", {"command": command, "backup": bkp_name}, res)
    return res

@mcp.tool()
def get_pc_telemetry() -> str:
    """Р вЂ™Р С•Р В·Р Р†РЎР‚Р В°РЎвЂ°Р В°Р ВµРЎвЂљ Р В·Р В°Р С–РЎР‚РЎС“Р В·Р С”РЎС“ CPU, RAM Р С‘ РЎРѓР Р†Р С•Р В±Р С•Р Т‘Р Р…Р С•Р Вµ Р СР ВµРЎРѓРЎвЂљР С• Р Р…Р В° Р Т‘Р С‘РЎРѓР С”Р Вµ C."""
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")
    res = f"CPU: {cpu}% | RAM: {ram.percent}% | Р вЂќР С‘РЎРѓР С” C РЎРѓР Р†Р С•Р В±Р С•Р Т‘Р Р…Р С•: {round(disk.free / 1024**3, 1)} Р вЂњР вЂ"
    _log_event("get_pc_telemetry", {}, res)
    return res

@mcp.tool()
def manage_docker(action: str, container_name: str = "") -> str:
    """Р Р€Р С—РЎР‚Р В°Р Р†Р В»РЎРЏР ВµРЎвЂљ Docker: ps, start, stop, logs."""
    if container_name and not re.match(r"^[a-zA-Z0-9_.-]+$", container_name):
        return "Р СњР ВµР Т‘Р С•Р С—РЎС“РЎРѓРЎвЂљР С‘Р СР С•Р Вµ Р С‘Р СРЎРЏ Р С”Р С•Р Р…РЎвЂљР ВµР в„–Р Р…Р ВµРЎР‚Р В°."
    cmd_map = {
        "ps": "docker ps -a --format 'table {{.Names}}\t{{.Status}}'",
        "start": f"docker start {container_name}",
        "stop": f"docker stop {container_name}",
        "logs": f"docker logs --tail 25 {container_name}"
    }
    if action not in cmd_map:
        return "Р вЂќР С•РЎРѓРЎвЂљРЎС“Р С—Р Р…РЎвЂ№: ps, start, stop, logs."
    return run_safe_powershell(cmd_map[action])

@mcp.tool()
def open_in_vscode(target_path: str = WORKSPACE_DIR) -> str:
    """Р С›РЎвЂљР С”РЎР‚РЎвЂ№Р Р†Р В°Р ВµРЎвЂљ Р С—Р В°Р С—Р С”РЎС“ Р С‘Р В»Р С‘ РЎвЂћР В°Р в„–Р В» Р Р† VS Code (РЎвЂљР С•Р В»РЎРЉР С”Р С• Р Р†Р Р…РЎС“РЎвЂљРЎР‚Р С‘ C:\\XiaoZhi-PC)."""
    abs_path = os.path.abspath(target_path)
    if not abs_path.startswith(BASE_DIR):
        return "Р вЂќР С•РЎРѓРЎвЂљРЎС“Р С— РЎР‚Р В°Р В·РЎР‚Р ВµРЎв‚¬Р ВµР Р… РЎвЂљР С•Р В»РЎРЉР С”Р С• Р С” C:\\XiaoZhi-PC."
    subprocess.Popen(["code", abs_path], shell=True)
    res = f"Р С›РЎвЂљР С”РЎР‚РЎвЂ№РЎвЂљР С• Р Р† VS Code: {abs_path}"
    _log_event("open_in_vscode", {"target_path": abs_path}, res)
    return res

@mcp.tool()
def git_sync_project(commit_message: str = "Voice auto-sync via Johnny") -> str:
    """Р вЂР ВµР В·Р С•Р С—Р В°РЎРѓР Р…Р С• РЎвЂћР С‘Р С”РЎРѓР С‘РЎР‚РЎС“Р ВµРЎвЂљ Р С‘ Р С•РЎвЂљР С—РЎР‚Р В°Р Р†Р В»РЎРЏР ВµРЎвЂљ РЎР‚Р В°Р В·РЎР‚Р ВµРЎв‚¬Р ВµР Р…Р Р…РЎвЂ№Р Вµ РЎвЂћР В°Р в„–Р В»РЎвЂ№ Р С—РЎР‚Р С•Р ВµР С”РЎвЂљР В° Р Р…Р В° GitHub."""
    safe_msg = re.sub(r"[\"'\`;$|&]", "", commit_message).strip() or "Voice auto-sync"
    cmd = f'git -C "{BASE_DIR}" add .gitignore .env.example README.md ROADMAP.md Dockerfile docker-compose.yml mcp_pipe.py pc_agent.py; git -C "{BASE_DIR}" commit -m "{safe_msg}"; git -C "{BASE_DIR}" push -u origin main'
    return run_safe_powershell(cmd)

@mcp.tool()
def search_workspace_docs(query: str) -> str:
    """Р ВРЎвЂ°Р ВµРЎвЂљ Р С‘Р Р…РЎвЂћР С•РЎР‚Р СР В°РЎвЂ Р С‘РЎР‹ Р С—Р С• РЎвЂљР ВµР С”РЎРѓРЎвЂљР С•Р Р†РЎвЂ№Р С РЎвЂћР В°Р в„–Р В»Р В°Р С Р Р†Р Р…РЎС“РЎвЂљРЎР‚Р С‘ C:\\XiaoZhi-PC\\workspace."""
    q = query.lower().strip()
    if not q:
        return "Р Р€Р С”Р В°Р В¶Р С‘РЎвЂљР Вµ Р С—Р С•Р С‘РЎРѓР С”Р С•Р Р†РЎвЂ№Р в„– Р В·Р В°Р С—РЎР‚Р С•РЎРѓ."
    matches = []
    for root, _, files in os.walk(WORKSPACE_DIR):
        for fname in files:
            if fname.endswith((".txt", ".md", ".py", ".json", ".yaml", ".log")):
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        for idx, line in enumerate(f, 1):
                            if q in line.lower():
                                matches.append(f"{fname} (РЎРѓРЎвЂљРЎР‚. {idx}): {line.strip()[:120]}")
                except Exception:
                    pass
    res = "\n".join(matches[:15]) if matches else f"Р РЋР С•Р Р†Р С—Р В°Р Т‘Р ВµР Р…Р С‘Р в„– Р С—Р С• Р В·Р В°Р С—РЎР‚Р С•РЎРѓРЎС“ '{query}' Р Р…Р Вµ Р Р…Р В°Р в„–Р Т‘Р ВµР Р…Р С•."
    _log_event("search_workspace_docs", {"query": query}, f"Р СњР В°Р в„–Р Т‘Р ВµР Р…Р С•: {len(matches)}")
    return res

@mcp.tool()
def phone_send_ntfy(message: str, attach_screenshot: bool = False) -> str:
    """Р С›РЎвЂљР С—РЎР‚Р В°Р Р†Р В»РЎРЏР ВµРЎвЂљ РЎвЂљР ВµР С”РЎРѓРЎвЂљ Р С‘Р В»Р С‘ РЎРѓР С”РЎР‚Р С‘Р Р…РЎв‚¬Р С•РЎвЂљ РЎРЊР С”РЎР‚Р В°Р Р…Р В° Р СџР С™ Р Р…Р В° РЎвЂљР ВµР В»Р ВµРЎвЂћР С•Р Р… РЎвЂЎР ВµРЎР‚Р ВµР В· ntfy.sh."""
    topic = os.getenv("PHONE_NTFY_TOPIC", "").strip()
    if not topic:
        return "Р С™Р В°Р Р…Р В°Р В» ntfy Р Р…Р Вµ Р Р…Р В°РЎРѓРЎвЂљРЎР‚Р С•Р ВµР Р… Р Р† .env."
    ntfy_url = "https://" + "ntfy.sh" + f"/{topic}"
    try:
        if attach_screenshot:
            with mss.mss() as sct:
                tmp_path = os.path.join(tempfile.gettempdir(), "xiaozhi_screen.png")
                sct.shot(output=tmp_path)
            with open(tmp_path, "rb") as img:
                safe_msg = message.encode("latin-1", "ignore").decode("latin-1") or "Screenshot"
                resp = requests.put(ntfy_url, data=img, headers={"Filename": "screen.png", "Title": "Johnny PC Screen", "Message": safe_msg}, timeout=15)
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        else:
            resp = requests.post(ntfy_url, data=message.encode("utf-8"), headers={"Title": "Johnny PC"}, timeout=10)
        res = "Р Р€РЎРѓР С—Р ВµРЎв‚¬Р Р…Р С• Р С•РЎвЂљР С—РЎР‚Р В°Р Р†Р В»Р ВµР Р…Р С• Р Р…Р В° РЎвЂљР ВµР В»Р ВµРЎвЂћР С•Р Р… РЎвЂЎР ВµРЎР‚Р ВµР В· ntfy." if resp.ok else f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° ntfy: {resp.status_code}"
    except Exception as e:
        res = f"Р РЋР В±Р С•Р в„– ntfy: {str(e)}"
    _log_event("phone_send_ntfy", {"message": message, "screenshot": attach_screenshot}, res)
    return res

@mcp.tool()
def pc_get_weather(city: str = "") -> str:
    """Р СџР С•Р В»РЎС“РЎвЂЎР В°Р ВµРЎвЂљ РЎвЂљР ВµР С”РЎС“РЎвЂ°РЎС“РЎР‹ Р С—Р С•Р С–Р С•Р Т‘РЎС“ Р В±Р ВµР В· API-Р С”Р В»РЎР‹РЎвЂЎР ВµР в„–."""
    target = city.strip() if city.strip() else os.getenv("DEFAULT_CITY", "Saint-Petersburg")
    url = "https://" + "wttr.in" + f"/{target}?format=3РІРЉВ©=ru"
    try:
        r = requests.get(url, timeout=8)
        res = r.text.strip() if r.ok else f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р С—Р С•Р С–Р С•Р Т‘РЎвЂ№: {r.status_code}"
    except Exception as e:
        res = f"Р РЋР В±Р С•Р в„– Р С—Р С•Р С–Р С•Р Т‘РЎвЂ№: {str(e)}"
    _log_event("pc_get_weather", {"city": target}, res)
    return res

@mcp.tool()
def manage_notes(action: str, text: str = "") -> str:
    """Р Р€Р С—РЎР‚Р В°Р Р†Р В»РЎРЏР ВµРЎвЂљ Р В·Р В°Р СР ВµРЎвЂљР С”Р В°Р СР С‘: add, read, clear."""
    notes_file = os.path.join(WORKSPACE_DIR, "notes.md")
    if action == "add" and text.strip():
        with open(notes_file, "a", encoding="utf-8") as f:
            f.write(f"- {text.strip()}\n")
        res = f"Р вЂ”Р В°Р С—Р С‘РЎРѓР В°Р Р…Р С•: {text.strip()}"
    elif action == "read":
        res = open(notes_file, "r", encoding="utf-8").read().strip() if os.path.exists(notes_file) else "Р вЂ”Р В°Р СР ВµРЎвЂљР С•Р С” Р Р…Р ВµРЎвЂљ."
    elif action == "clear":
        open(notes_file, "w", encoding="utf-8").close()
        res = "Р вЂ”Р В°Р СР ВµРЎвЂљР С”Р С‘ Р С•РЎвЂЎР С‘РЎвЂ°Р ВµР Р…РЎвЂ№."
    else:
        res = "Р Р€Р С”Р В°Р В¶Р С‘РЎвЂљР Вµ action: add, read Р С‘Р В»Р С‘ clear."
    _log_event("manage_notes", {"action": action}, res)
    return res

@mcp.tool()
def capture_esp32_logs(seconds: int = 10) -> str:
    """Р РЋРЎвЂЎР С‘РЎвЂљРЎвЂ№Р Р†Р В°Р ВµРЎвЂљ РЎРѓР С‘РЎРѓРЎвЂљР ВµР СР Р…РЎвЂ№Р Вµ Р В»Р С•Р С–Р С‘ РЎРѓ Р С”Р С•Р В»Р С•Р Р…Р С”Р С‘ ESP32-S3 (COM6)."""
    ports = list(serial.tools.list_ports.comports())
    esp_port = next((p.device for p in ports if p.device == "COM6" or "usb" in (p.description or "").lower()), None)
    if not esp_port:
        return "COM-Р С—Р С•РЎР‚РЎвЂљ ESP32-S3 Р Р…Р Вµ Р Р…Р В°Р в„–Р Т‘Р ВµР Р…."
    log_path = os.path.join(LOGS_DIR, "esp32_serial.log")
    collected = []
    try:
        with serial.Serial(esp_port, 115200, timeout=1) as ser:
            end_t = datetime.datetime.now() + datetime.timedelta(seconds=min(seconds, 30))
            while datetime.datetime.now() < end_t:
                line = ser.readline().decode("utf-8", errors="replace").strip()
                if line:
                    collected.append(line)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n--- {datetime.datetime.now().isoformat()} ---\n" + "\n".join(collected) + "\n")
        res = f"Р РЋР Р…РЎРЏРЎвЂљР С• {len(collected)} РЎРѓРЎвЂљРЎР‚Р С•Р С” РЎРѓ {esp_port}."
    except Exception as e:
        res = f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° РЎвЂЎРЎвЂљР ВµР Р…Р С‘РЎРЏ {esp_port}: {str(e)}"
    _log_event("capture_esp32_logs", {"port": esp_port}, res)
    return res

@mcp.tool()
def ha_list_devices() -> str:
    """Р вЂ™Р С•Р В·Р Р†РЎР‚Р В°РЎвЂ°Р В°Р ВµРЎвЂљ РЎРѓР С—Р С‘РЎРѓР С•Р С” Р Р†РЎРѓР ВµРЎвЂ¦ РЎС“РЎРѓРЎвЂљРЎР‚Р С•Р в„–РЎРѓРЎвЂљР Р† РЎС“Р СР Р…Р С•Р С–Р С• Р Т‘Р С•Р СР В° Р С‘Р В· Home Assistant."""
    ha_url = os.getenv("HA_URL", "http://" + "127.0.0.1" + ":8123").rstrip("/")
    ha_token = os.getenv("HA_TOKEN", "").strip()
    if not ha_token:
        return "HA_TOKEN Р Р…Р Вµ Р В·Р В°Р Т‘Р В°Р Р…."
    try:
        headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}
        resp = requests.get(f"{ha_url}/api/states", headers=headers, timeout=8)
        devices = []
        for item in resp.json():
            eid = item.get("entity_id", "")
            if eid.startswith(("switch.", "light.", "climate.", "cover.", "sensor.", "vacuum.")):
                fname = item.get("attributes", {}).get("friendly_name", eid)
                devices.append(f"{fname} [{eid}]: {item.get('state')}")
        res = "\n".join(devices) if devices else "Р Р€РЎРѓРЎвЂљРЎР‚Р С•Р в„–РЎРѓРЎвЂљР Р†Р В° Р Р…Р Вµ Р Р…Р В°Р в„–Р Т‘Р ВµР Р…РЎвЂ№."
    except Exception as e:
        res = f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° HA: {str(e)}"
    _log_event("ha_list_devices", {}, f"Р СњР В°Р в„–Р Т‘Р ВµР Р…Р С• РЎС“РЎРѓРЎвЂљРЎР‚Р С•Р в„–РЎРѓРЎвЂљР Р†: {len(res.splitlines())}")
    return res

@mcp.tool()
def ha_control_device(entity_id: str, action: str) -> str:
    """Р Р€Р С—РЎР‚Р В°Р Р†Р В»РЎРЏР ВµРЎвЂљ РЎС“РЎРѓРЎвЂљРЎР‚Р С•Р в„–РЎРѓРЎвЂљР Р†Р С•Р С Р Р† Home Assistant (turn_on, turn_off, toggle, start, return_to_base)."""
    ha_url = os.getenv("HA_URL", "http://" + "127.0.0.1" + ":8123").rstrip("/")
    ha_token = os.getenv("HA_TOKEN", "").strip()
    domain = entity_id.split(".")[0] if "." in entity_id else "homeassistant"
    try:
        headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}
        resp = requests.post(f"{ha_url}/api/services/{domain}/{action}", headers=headers, json={"entity_id": entity_id}, timeout=8)
        res = f"Р вЂ™РЎвЂ№Р С—Р С•Р В»Р Р…Р ВµР Р…Р С•: {action} Р Т‘Р В»РЎРЏ {entity_id}." if resp.ok else f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В°: {resp.status_code}"
    except Exception as e:
        res = f"Р РЋР В±Р С•Р в„– РЎС“Р С—РЎР‚Р В°Р Р†Р В»Р ВµР Р…Р С‘РЎРЏ: {str(e)}"
    _log_event("ha_control_device", {"entity_id": entity_id, "action": action}, res)
    return res

@mcp.tool()
def write_workspace_file(filename: str, content: str) -> str:
    """Р вЂР ВµР В·Р С•Р С—Р В°РЎРѓР Р…Р С• РЎРѓР С•Р В·Р Т‘Р В°Р ВµРЎвЂљ Р С‘Р В»Р С‘ Р С—Р ВµРЎР‚Р ВµР В·Р В°Р С—Р С‘РЎРѓРЎвЂ№Р Р†Р В°Р ВµРЎвЂљ РЎвЂћР В°Р в„–Р В» Р Р†Р Р…РЎС“РЎвЂљРЎР‚Р С‘ Р С—Р В°Р С—Р С”Р С‘ C:\\XiaoZhi-PC\\workspace."""
    safe_name = os.path.basename(filename)
    if not safe_name:
        return "Р СњР ВµР С”Р С•РЎР‚РЎР‚Р ВµР С”РЎвЂљР Р…Р С•Р Вµ Р С‘Р СРЎРЏ РЎвЂћР В°Р в„–Р В»Р В°."
    target_path = os.path.join(WORKSPACE_DIR, safe_name)
    _create_auto_backup("pre_write")
    try:
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
        res = f"Р В¤Р В°Р в„–Р В» РЎС“РЎРѓР С—Р ВµРЎв‚¬Р Р…Р С• РЎРѓР С•РЎвЂ¦РЎР‚Р В°Р Р…Р ВµР Р…: {target_path} ({len(content)} Р В±Р В°Р в„–РЎвЂљ)."
    except Exception as e:
        res = f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р В·Р В°Р С—Р С‘РЎРѓР С‘ РЎвЂћР В°Р в„–Р В»Р В°: {str(e)}"
    _log_event("write_workspace_file", {"filename": safe_name, "bytes": len(content)}, res)
    return res

@mcp.tool()
def launch_workspace_script(filename: str) -> str:
    """Р вЂ”Р В°Р С—РЎС“РЎРѓР С”Р В°Р ВµРЎвЂљ Python-РЎРѓР С”РЎР‚Р С‘Р С—РЎвЂљ Р С‘Р В· Р С—Р В°Р С—Р С”Р С‘ workspace Р Р† Р С•РЎвЂљР Т‘Р ВµР В»РЎРЉР Р…Р С•Р С Р С•Р С”Р Р…Р Вµ Р В±Р ВµР В· Р В±Р В»Р С•Р С”Р С‘РЎР‚Р С•Р Р†Р С”Р С‘ Р В°Р С–Р ВµР Р…РЎвЂљР В°."""
    safe_name = os.path.basename(filename)
    target_path = os.path.join(WORKSPACE_DIR, safe_name)
    if not os.path.exists(target_path):
        return f"Р В¤Р В°Р в„–Р В» {safe_name} Р Р…Р Вµ Р Р…Р В°Р в„–Р Т‘Р ВµР Р… Р Р† workspace."
    try:
        subprocess.Popen([r"C:\Python315\python.exe", target_path], cwd=WORKSPACE_DIR, creationflags=subprocess.CREATE_NEW_CONSOLE)
        res = f"Р РЋР С”РЎР‚Р С‘Р С—РЎвЂљ {safe_name} Р В·Р В°Р С—РЎС“РЎвЂ°Р ВµР Р… Р Р† Р С•РЎвЂљР Т‘Р ВµР В»РЎРЉР Р…Р С•Р С Р С•Р С”Р Р…Р Вµ."
    except Exception as e:
        res = f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р В·Р В°Р С—РЎС“РЎРѓР С”Р В°: {str(e)}"
    _log_event("launch_workspace_script", {"filename": safe_name}, res)
    return res
if __name__ == "__main__":
    mcp.run(transport="stdio")





