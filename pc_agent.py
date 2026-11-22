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


def _redact_secrets(text: str) -> str:
    """Вырезает любые реальные значения секретов из .env перед выводом или записью в лог."""
    out = str(text)
    for var in ("LLM_API_KEY", "HA_TOKEN", "MCP_ENDPOINT", "PHONE_NTFY_TOPIC", "TELEGRAM_BOT_TOKEN"):
        val = os.getenv(var, "").strip()
        if val and len(val) > 6:
            out = out.replace(val, "[СКРЫТО]")
    return out


AI_AUDIT_FILE = os.path.join(LOGS_DIR, "ai_decisions_audit.jsonl")

def _log_ai_decision(engine: str, model: str, prompt: str, response: str, duration_sec: float, tokens: int = 0):
    entry = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "mode": _load_state().get("mode", "companion"),
        "engine": engine,
        "model": model,
        "duration_sec": round(duration_sec, 2),
        "tokens": tokens,
        "tokens_per_sec": round(tokens / duration_sec, 1) if duration_sec > 0 and tokens > 0 else 0,
        "prompt": _redact_secrets(prompt),
        "response": _redact_secrets(response)
    }
    try:
        with open(AI_AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + chr(10))
    except Exception:
        pass

def _log_event(tool_name: str, args: dict, result: str):
    entry = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "mode": _load_state().get("mode", "companion"),
        "tool": tool_name,
        "args": args,
        "result": _redact_secrets(str(result))[:1000]
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
    """Р В РІР‚в„ўР В РЎвЂўР В Р’В·Р В Р вЂ Р РЋР вЂљР В Р’В°Р РЋРІР‚В°Р В Р’В°Р В Р’ВµР РЋРІР‚С™ Р В РЎвЂ”Р В РЎвЂўР РЋР С“Р В Р’В»Р В Р’ВµР В РўвЂР В Р вЂ¦Р В РЎвЂР В Р’Вµ Р В Р’В·Р В Р’В°Р В РЎвЂ”Р В РЎвЂР РЋР С“Р В РЎвЂ Р В РЎвЂР В Р’В· Р В Р’В¶Р РЋРЎвЂњР РЋР вЂљР В Р вЂ¦Р В Р’В°Р В Р’В»Р В Р’В° Р В РўвЂР В Р’ВµР В РІвЂћвЂ“Р РЋР С“Р РЋРІР‚С™Р В Р вЂ Р В РЎвЂР В РІвЂћвЂ“ Р В РІР‚СњР В Р’В¶Р В РЎвЂўР В Р вЂ¦Р В Р вЂ¦Р В РЎвЂ."""
    if not os.path.exists(AUDIT_FILE):
        return "Р В РІР‚вЂњР РЋРЎвЂњР РЋР вЂљР В Р вЂ¦Р В Р’В°Р В Р’В» Р В РўвЂР В Р’ВµР В РІвЂћвЂ“Р РЋР С“Р РЋРІР‚С™Р В Р вЂ Р В РЎвЂР В РІвЂћвЂ“ Р В РЎвЂ”Р В РЎвЂўР В РЎвЂќР В Р’В° Р В РЎвЂ”Р РЋРЎвЂњР РЋР С“Р РЋРІР‚С™."
    with open(AUDIT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()[-limit:]
    return "\n".join(f"[{json.loads(l)['timestamp']}] ({json.loads(l)['mode']}) {json.loads(l)['tool']} -> {json.loads(l)['result'][:120]}" for l in lines)

@mcp.tool()
def rollback_last_backup() -> str:
    """Р В РІР‚в„ўР В РЎвЂўР РЋР С“Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р В Р вЂ¦Р В Р’В°Р В Р вЂ Р В Р’В»Р В РЎвЂР В Р вЂ Р В Р’В°Р В Р’ВµР РЋРІР‚С™ Р РЋРІР‚С›Р В Р’В°Р В РІвЂћвЂ“Р В Р’В»Р РЋРІР‚в„– Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР В Р’ВµР В РЎвЂќР РЋРІР‚С™Р В Р’В° Р В РЎвЂР В Р’В· Р В РЎвЂ”Р В РЎвЂўР РЋР С“Р В Р’В»Р В Р’ВµР В РўвЂР В Р вЂ¦Р В Р’ВµР В РЎвЂ“Р В РЎвЂў Р РЋР вЂљР В Р’ВµР В Р’В·Р В Р’ВµР РЋР вЂљР В Р вЂ Р В Р вЂ¦Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В Р’В°Р РЋР вЂљР РЋРІР‚В¦Р В РЎвЂР В Р вЂ Р В Р’В°."""
    all_bkp = sorted(glob.glob(os.path.join(BACKUPS_DIR, "backup_*.zip")))
    if not all_bkp:
        return "Р В Р’В Р В Р’ВµР В Р’В·Р В Р’ВµР РЋР вЂљР В Р вЂ Р В Р вЂ¦Р РЋРІР‚в„–Р В Р’Вµ Р В РЎвЂќР В РЎвЂўР В РЎвЂ”Р В РЎвЂР В РЎвЂ Р В Р вЂ¦Р В Р’Вµ Р В Р вЂ¦Р В Р’В°Р В РІвЂћвЂ“Р В РўвЂР В Р’ВµР В Р вЂ¦Р РЋРІР‚в„–."
    latest = all_bkp[-1]
    with zipfile.ZipFile(latest, "r") as zf:
        zf.extractall(BASE_DIR)
    res = f"Р В Р Р‹Р В РЎвЂР РЋР С“Р РЋРІР‚С™Р В Р’ВµР В РЎВР В Р’В° Р В РЎвЂўР РЋРІР‚С™Р В РЎвЂќР В Р’В°Р РЋРІР‚РЋР В Р’ВµР В Р вЂ¦Р В Р’В° Р В РЎвЂќ Р В РЎвЂќР В РЎвЂўР В РЎвЂ”Р В РЎвЂР В РЎвЂ: {os.path.basename(latest)}"
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
            return False, f"Р В РІР‚вЂќР В Р’В°Р В Р’В±Р В Р’В»Р В РЎвЂўР В РЎвЂќР В РЎвЂР РЋР вЂљР В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В РЎвЂ”Р В РЎвЂўР В Р’В»Р В РЎвЂР РЋРІР‚С™Р В РЎвЂР В РЎвЂќР В РЎвЂўР В РІвЂћвЂ“ Р В Р’В±Р В Р’ВµР В Р’В·Р В РЎвЂўР В РЎвЂ”Р В Р’В°Р РЋР С“Р В Р вЂ¦Р В РЎвЂўР РЋР С“Р РЋРІР‚С™Р В РЎвЂ: {pattern}"
    return True, "OK"

MODES_CONFIG = {
    "combat": {"name": "Р В РІР‚ВР В РЎвЂўР В Р’ВµР В Р вЂ Р В РЎвЂўР В РІвЂћвЂ“ / Р В РЎСљР В Р’ВµР РЋРІР‚С™Р РЋР вЂљР В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р В Р’ВµР РЋР вЂљ", "rules": "Р В Р Р‹Р РЋРЎвЂњР РЋРІР‚В¦Р В РЎвЂў, Р РЋРІР‚С™Р В Р’ВµР РЋРІР‚В¦Р В Р вЂ¦Р В РЎвЂР РЋРІР‚РЋР В Р’ВµР РЋР С“Р В РЎвЂќР В РЎвЂ Р РЋРІР‚С™Р В РЎвЂўР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂў, Р В Р’В±Р В Р’ВµР В Р’В· Р В Р вЂ Р В РЎвЂўР В РўвЂР РЋРІР‚в„–."},
    "companion": {"name": "Р В РЎСљР В Р’В°Р В РЎвЂ”Р В Р’В°Р РЋР вЂљР В Р вЂ¦Р В РЎвЂР В РЎвЂќ / Р В Р’ВР В Р вЂ¦Р РЋРІР‚С›Р В РЎвЂў", "rules": "Р В РўС’Р В Р’В°Р РЋР вЂљР В РЎвЂР В Р’В·Р В РЎВР В Р’В° Р В РІР‚СњР В Р’В¶Р В РЎвЂўР В Р вЂ¦Р В Р вЂ¦Р В РЎвЂ Р В Р Р‹Р В РЎвЂР В Р’В»Р РЋР Р‰Р В Р вЂ Р В Р’ВµР РЋР вЂљР РЋРІР‚В¦Р В Р’ВµР В Р вЂ¦Р В РўвЂР В Р’В°, Р В Р’В»Р В Р’ВµР В РЎвЂ“Р В РЎвЂќР В РЎвЂР В РІвЂћвЂ“ Р РЋР С“Р В Р’В°Р РЋР вЂљР В РЎвЂќР В Р’В°Р В Р’В·Р В РЎВ, Р В Р вЂ¦Р В РЎвЂў Р В РЎвЂ”Р В РЎвЂў Р В РўвЂР В Р’ВµР В Р’В»Р РЋРЎвЂњ."},
    "entertainment": {"name": "Р В РЎСљР В Р’В°Р В РІвЂћвЂ“Р РЋРІР‚С™-Р В Р Р‹Р В РЎвЂР РЋРІР‚С™Р В РЎвЂ / Р В Р Р‹Р В Р’В°Р В РЎВР РЋРЎвЂњР РЋР вЂљР В Р’В°Р В РІвЂћвЂ“", "rules": "Р В Р’В Р В Р’В°Р В Р’В·Р В Р вЂ Р В Р’В»Р В Р’ВµР В РЎвЂќР В Р’В°Р РЋРІР‚С™Р В Р’ВµР В Р’В»Р РЋР Р‰Р В Р вЂ¦Р РЋРІР‚в„–Р В РІвЂћвЂ“ Р РЋР вЂљР В Р’ВµР В Р’В¶Р В РЎвЂР В РЎВ, Р РЋРІвЂљВ¬Р РЋРЎвЂњР РЋРІР‚С™Р В РЎвЂќР В РЎвЂ, Р В РЎвЂќР В Р вЂ Р В Р’ВµР РЋР С“Р РЋРІР‚С™Р РЋРІР‚в„– Р В РЎвЂ”Р В РЎвЂў Р В РЎвЂќР В РЎвЂР В Р’В±Р В Р’ВµР РЋР вЂљР В РЎвЂ”Р В Р’В°Р В Р вЂ¦Р В РЎвЂќР РЋРЎвЂњ."}
}

@mcp.tool()
def switch_assistant_mode(mode: str) -> str:
    """Р В РЎСџР В Р’ВµР РЋР вЂљР В Р’ВµР В РЎвЂќР В Р’В»Р РЋР вЂ№Р РЋРІР‚РЋР В Р’В°Р В Р’ВµР РЋРІР‚С™ Р РЋР вЂљР В Р’ВµР В Р’В¶Р В РЎвЂР В РЎВ Р РЋР вЂљР В Р’В°Р В Р’В±Р В РЎвЂўР РЋРІР‚С™Р РЋРІР‚в„–: combat, companion, entertainment."""
    mode = mode.lower().strip()
    if mode not in MODES_CONFIG:
        return "Р В РІР‚СњР В РЎвЂўР РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В РЎвЂ”Р В Р вЂ¦Р РЋРІР‚в„– Р РЋР вЂљР В Р’ВµР В Р’В¶Р В РЎвЂР В РЎВР РЋРІР‚в„–: combat, companion, entertainment."
    state = _load_state()
    state["mode"] = mode
    _save_state(state)
    res = f"Р В РЎвЂ™Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР В Р вЂ Р В РЎвЂР РЋР вЂљР В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦ Р РЋР вЂљР В Р’ВµР В Р’В¶Р В РЎвЂР В РЎВ: {MODES_CONFIG[mode]['name']}."
    _log_event("switch_assistant_mode", {"mode": mode}, res)
    return res

@mcp.tool()
def run_safe_powershell(command: str) -> str:
    """Р В РІР‚в„ўР РЋРІР‚в„–Р В РЎвЂ”Р В РЎвЂўР В Р’В»Р В Р вЂ¦Р РЋР РЏР В Р’ВµР РЋРІР‚С™ Р В Р’В±Р В Р’ВµР В Р’В·Р В РЎвЂўР В РЎвЂ”Р В Р’В°Р РЋР С“Р В Р вЂ¦Р РЋРЎвЂњР РЋР вЂ№ Р В РЎвЂќР В РЎвЂўР В РЎВР В Р’В°Р В Р вЂ¦Р В РўвЂР РЋРЎвЂњ PowerShell Р РЋР С“ Р В РЎвЂ”Р РЋР вЂљР В Р’ВµР В РўвЂР В Р вЂ Р В Р’В°Р РЋР вЂљР В РЎвЂР РЋРІР‚С™Р В Р’ВµР В Р’В»Р РЋР Р‰Р В Р вЂ¦Р РЋРІР‚в„–Р В РЎВ Р В Р’В°Р В Р вЂ Р РЋРІР‚С™Р В РЎвЂў-Р В Р’В±Р РЋР РЉР В РЎвЂќР В Р’В°Р В РЎвЂ”Р В РЎвЂўР В РЎВ."""
    is_safe, reason = _is_command_safe(command)
    if not is_safe:
        _log_event("run_safe_powershell_BLOCKED", {"command": command}, reason)
        return reason
    bkp_name = _create_auto_backup("pre_ps")
    try:
        result = subprocess.run(["powershell", "-NoProfile", "-Command", command], cwd=WORKSPACE_DIR, capture_output=True, text=True, encoding="cp866", timeout=20)
        out = result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
        res = out if out else "Р В РЎв„ўР В РЎвЂўР В РЎВР В Р’В°Р В Р вЂ¦Р В РўвЂР В Р’В° Р В Р вЂ Р РЋРІР‚в„–Р В РЎвЂ”Р В РЎвЂўР В Р’В»Р В Р вЂ¦Р В Р’ВµР В Р вЂ¦Р В Р’В°."
    except Exception as e:
        res = f"Р В РЎвЂєР РЋРІвЂљВ¬Р В РЎвЂР В Р’В±Р В РЎвЂќР В Р’В°: {str(e)}"
    _log_event("run_safe_powershell", {"command": command, "backup": bkp_name}, res)
    return res

@mcp.tool()
def get_pc_telemetry() -> str:
    """Р В РІР‚в„ўР В РЎвЂўР В Р’В·Р В Р вЂ Р РЋР вЂљР В Р’В°Р РЋРІР‚В°Р В Р’В°Р В Р’ВµР РЋРІР‚С™ Р В Р’В·Р В Р’В°Р В РЎвЂ“Р РЋР вЂљР РЋРЎвЂњР В Р’В·Р В РЎвЂќР РЋРЎвЂњ CPU, RAM Р В РЎвЂ Р РЋР С“Р В Р вЂ Р В РЎвЂўР В Р’В±Р В РЎвЂўР В РўвЂР В Р вЂ¦Р В РЎвЂўР В Р’Вµ Р В РЎВР В Р’ВµР РЋР С“Р РЋРІР‚С™Р В РЎвЂў Р В Р вЂ¦Р В Р’В° Р В РўвЂР В РЎвЂР РЋР С“Р В РЎвЂќР В Р’Вµ C."""
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")
    res = f"CPU: {cpu}% | RAM: {ram.percent}% | Р В РІР‚СњР В РЎвЂР РЋР С“Р В РЎвЂќ C Р РЋР С“Р В Р вЂ Р В РЎвЂўР В Р’В±Р В РЎвЂўР В РўвЂР В Р вЂ¦Р В РЎвЂў: {round(disk.free / 1024**3, 1)} Р В РІР‚СљР В РІР‚В"
    _log_event("get_pc_telemetry", {}, res)
    return res

@mcp.tool()
def manage_docker(action: str, container_name: str = "") -> str:
    """Р В Р в‚¬Р В РЎвЂ”Р РЋР вЂљР В Р’В°Р В Р вЂ Р В Р’В»Р РЋР РЏР В Р’ВµР РЋРІР‚С™ Docker: ps, start, stop, logs."""
    if container_name and not re.match(r"^[a-zA-Z0-9_.-]+$", container_name):
        return "Р В РЎСљР В Р’ВµР В РўвЂР В РЎвЂўР В РЎвЂ”Р РЋРЎвЂњР РЋР С“Р РЋРІР‚С™Р В РЎвЂР В РЎВР В РЎвЂўР В Р’Вµ Р В РЎвЂР В РЎВР РЋР РЏ Р В РЎвЂќР В РЎвЂўР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР В РІвЂћвЂ“Р В Р вЂ¦Р В Р’ВµР РЋР вЂљР В Р’В°."
    cmd_map = {
        "ps": "docker ps -a --format 'table {{.Names}}\t{{.Status}}'",
        "start": f"docker start {container_name}",
        "stop": f"docker stop {container_name}",
        "logs": f"docker logs --tail 25 {container_name}"
    }
    if action not in cmd_map:
        return "Р В РІР‚СњР В РЎвЂўР РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В РЎвЂ”Р В Р вЂ¦Р РЋРІР‚в„–: ps, start, stop, logs."
    return run_safe_powershell(cmd_map[action])

@mcp.tool()
def open_in_vscode(target_path: str = WORKSPACE_DIR) -> str:
    """Р В РЎвЂєР РЋРІР‚С™Р В РЎвЂќР РЋР вЂљР РЋРІР‚в„–Р В Р вЂ Р В Р’В°Р В Р’ВµР РЋРІР‚С™ Р В РЎвЂ”Р В Р’В°Р В РЎвЂ”Р В РЎвЂќР РЋРЎвЂњ Р В РЎвЂР В Р’В»Р В РЎвЂ Р РЋРІР‚С›Р В Р’В°Р В РІвЂћвЂ“Р В Р’В» Р В Р вЂ  VS Code (Р РЋРІР‚С™Р В РЎвЂўР В Р’В»Р РЋР Р‰Р В РЎвЂќР В РЎвЂў Р В Р вЂ Р В Р вЂ¦Р РЋРЎвЂњР РЋРІР‚С™Р РЋР вЂљР В РЎвЂ C:\\XiaoZhi-PC)."""
    abs_path = os.path.abspath(target_path)
    if not abs_path.startswith(BASE_DIR):
        return "Р В РІР‚СњР В РЎвЂўР РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В РЎвЂ” Р РЋР вЂљР В Р’В°Р В Р’В·Р РЋР вЂљР В Р’ВµР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦ Р РЋРІР‚С™Р В РЎвЂўР В Р’В»Р РЋР Р‰Р В РЎвЂќР В РЎвЂў Р В РЎвЂќ C:\\XiaoZhi-PC."
    subprocess.Popen(["code", abs_path], shell=True)
    res = f"Р В РЎвЂєР РЋРІР‚С™Р В РЎвЂќР РЋР вЂљР РЋРІР‚в„–Р РЋРІР‚С™Р В РЎвЂў Р В Р вЂ  VS Code: {abs_path}"
    _log_event("open_in_vscode", {"target_path": abs_path}, res)
    return res

@mcp.tool()
def git_sync_project(commit_message: str = "Voice auto-sync via Johnny") -> str:
    """Р В РІР‚ВР В Р’ВµР В Р’В·Р В РЎвЂўР В РЎвЂ”Р В Р’В°Р РЋР С“Р В Р вЂ¦Р В РЎвЂў Р РЋРІР‚С›Р В РЎвЂР В РЎвЂќР РЋР С“Р В РЎвЂР РЋР вЂљР РЋРЎвЂњР В Р’ВµР РЋРІР‚С™ Р В РЎвЂ Р В РЎвЂўР РЋРІР‚С™Р В РЎвЂ”Р РЋР вЂљР В Р’В°Р В Р вЂ Р В Р’В»Р РЋР РЏР В Р’ВµР РЋРІР‚С™ Р РЋР вЂљР В Р’В°Р В Р’В·Р РЋР вЂљР В Р’ВµР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋРІР‚в„–Р В Р’Вµ Р РЋРІР‚С›Р В Р’В°Р В РІвЂћвЂ“Р В Р’В»Р РЋРІР‚в„– Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР В Р’ВµР В РЎвЂќР РЋРІР‚С™Р В Р’В° Р В Р вЂ¦Р В Р’В° GitHub."""
    safe_msg = re.sub(r"[\"'\`;$|&]", "", commit_message).strip() or "Voice auto-sync"
    cmd = f'git -C "{BASE_DIR}" add .gitignore .env.example README.md ROADMAP.md Dockerfile docker-compose.yml mcp_pipe.py pc_agent.py; git -C "{BASE_DIR}" commit -m "{safe_msg}"; git -C "{BASE_DIR}" push -u origin main'
    return run_safe_powershell(cmd)

@mcp.tool()
def search_workspace_docs(query: str) -> str:
    """Р В Р’ВР РЋРІР‚В°Р В Р’ВµР РЋРІР‚С™ Р В РЎвЂР В Р вЂ¦Р РЋРІР‚С›Р В РЎвЂўР РЋР вЂљР В РЎВР В Р’В°Р РЋРІР‚В Р В РЎвЂР РЋР вЂ№ Р В РЎвЂ”Р В РЎвЂў Р РЋРІР‚С™Р В Р’ВµР В РЎвЂќР РЋР С“Р РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р РЋРІР‚в„–Р В РЎВ Р РЋРІР‚С›Р В Р’В°Р В РІвЂћвЂ“Р В Р’В»Р В Р’В°Р В РЎВ Р В Р вЂ Р В Р вЂ¦Р РЋРЎвЂњР РЋРІР‚С™Р РЋР вЂљР В РЎвЂ C:\\XiaoZhi-PC\\workspace."""
    q = query.lower().strip()
    if not q:
        return "Р В Р в‚¬Р В РЎвЂќР В Р’В°Р В Р’В¶Р В РЎвЂР РЋРІР‚С™Р В Р’Вµ Р В РЎвЂ”Р В РЎвЂўР В РЎвЂР РЋР С“Р В РЎвЂќР В РЎвЂўР В Р вЂ Р РЋРІР‚в„–Р В РІвЂћвЂ“ Р В Р’В·Р В Р’В°Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋР С“."
    matches = []
    for root, _, files in os.walk(WORKSPACE_DIR):
        for fname in files:
            if fname.endswith((".txt", ".md", ".py", ".json", ".yaml", ".log")):
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        for idx, line in enumerate(f, 1):
                            if q in line.lower():
                                matches.append(f"{fname} (Р РЋР С“Р РЋРІР‚С™Р РЋР вЂљ. {idx}): {line.strip()[:120]}")
                except Exception:
                    pass
    res = "\n".join(matches[:15]) if matches else f"Р В Р Р‹Р В РЎвЂўР В Р вЂ Р В РЎвЂ”Р В Р’В°Р В РўвЂР В Р’ВµР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р В РЎвЂ”Р В РЎвЂў Р В Р’В·Р В Р’В°Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋР С“Р РЋРЎвЂњ '{query}' Р В Р вЂ¦Р В Р’Вµ Р В Р вЂ¦Р В Р’В°Р В РІвЂћвЂ“Р В РўвЂР В Р’ВµР В Р вЂ¦Р В РЎвЂў."
    _log_event("search_workspace_docs", {"query": query}, f"Р В РЎСљР В Р’В°Р В РІвЂћвЂ“Р В РўвЂР В Р’ВµР В Р вЂ¦Р В РЎвЂў: {len(matches)}")
    return res

@mcp.tool()
def phone_send_ntfy(message: str, attach_screenshot: bool = False) -> str:
    """Р В РЎвЂєР РЋРІР‚С™Р В РЎвЂ”Р РЋР вЂљР В Р’В°Р В Р вЂ Р В Р’В»Р РЋР РЏР В Р’ВµР РЋРІР‚С™ Р РЋРІР‚С™Р В Р’ВµР В РЎвЂќР РЋР С“Р РЋРІР‚С™ Р В РЎвЂР В Р’В»Р В РЎвЂ Р РЋР С“Р В РЎвЂќР РЋР вЂљР В РЎвЂР В Р вЂ¦Р РЋРІвЂљВ¬Р В РЎвЂўР РЋРІР‚С™ Р РЋР РЉР В РЎвЂќР РЋР вЂљР В Р’В°Р В Р вЂ¦Р В Р’В° Р В РЎСџР В РЎв„ў Р В Р вЂ¦Р В Р’В° Р РЋРІР‚С™Р В Р’ВµР В Р’В»Р В Р’ВµР РЋРІР‚С›Р В РЎвЂўР В Р вЂ¦ Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· ntfy.sh."""
    topic = os.getenv("PHONE_NTFY_TOPIC", "").strip()
    if not topic:
        return "Р В РЎв„ўР В Р’В°Р В Р вЂ¦Р В Р’В°Р В Р’В» ntfy Р В Р вЂ¦Р В Р’Вµ Р В Р вЂ¦Р В Р’В°Р РЋР С“Р РЋРІР‚С™Р РЋР вЂљР В РЎвЂўР В Р’ВµР В Р вЂ¦ Р В Р вЂ  .env."
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
        res = "Р В Р в‚¬Р РЋР С“Р В РЎвЂ”Р В Р’ВµР РЋРІвЂљВ¬Р В Р вЂ¦Р В РЎвЂў Р В РЎвЂўР РЋРІР‚С™Р В РЎвЂ”Р РЋР вЂљР В Р’В°Р В Р вЂ Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В РЎвЂў Р В Р вЂ¦Р В Р’В° Р РЋРІР‚С™Р В Р’ВµР В Р’В»Р В Р’ВµР РЋРІР‚С›Р В РЎвЂўР В Р вЂ¦ Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· ntfy." if resp.ok else f"Р В РЎвЂєР РЋРІвЂљВ¬Р В РЎвЂР В Р’В±Р В РЎвЂќР В Р’В° ntfy: {resp.status_code}"
    except Exception as e:
        res = f"Р В Р Р‹Р В Р’В±Р В РЎвЂўР В РІвЂћвЂ“ ntfy: {str(e)}"
    _log_event("phone_send_ntfy", {"message": message, "screenshot": attach_screenshot}, res)
    return res

@mcp.tool()
def pc_get_weather(city: str = "") -> str:
    """Р В РЎСџР В РЎвЂўР В Р’В»Р РЋРЎвЂњР РЋРІР‚РЋР В Р’В°Р В Р’ВµР РЋРІР‚С™ Р РЋРІР‚С™Р В Р’ВµР В РЎвЂќР РЋРЎвЂњР РЋРІР‚В°Р РЋРЎвЂњР РЋР вЂ№ Р В РЎвЂ”Р В РЎвЂўР В РЎвЂ“Р В РЎвЂўР В РўвЂР РЋРЎвЂњ Р В Р’В±Р В Р’ВµР В Р’В· API-Р В РЎвЂќР В Р’В»Р РЋР вЂ№Р РЋРІР‚РЋР В Р’ВµР В РІвЂћвЂ“."""
    target = city.strip() if city.strip() else os.getenv("DEFAULT_CITY", "Saint-Petersburg")
    url = "https://" + "wttr.in" + f"/{target}?format=3Р Р†Р Р‰Р’В©=ru"
    try:
        r = requests.get(url, timeout=8)
        res = r.text.strip() if r.ok else f"Р В РЎвЂєР РЋРІвЂљВ¬Р В РЎвЂР В Р’В±Р В РЎвЂќР В Р’В° Р В РЎвЂ”Р В РЎвЂўР В РЎвЂ“Р В РЎвЂўР В РўвЂР РЋРІР‚в„–: {r.status_code}"
    except Exception as e:
        res = f"Р В Р Р‹Р В Р’В±Р В РЎвЂўР В РІвЂћвЂ“ Р В РЎвЂ”Р В РЎвЂўР В РЎвЂ“Р В РЎвЂўР В РўвЂР РЋРІР‚в„–: {str(e)}"
    _log_event("pc_get_weather", {"city": target}, res)
    return res

@mcp.tool()
def manage_notes(action: str, text: str = "") -> str:
    """Р В Р в‚¬Р В РЎвЂ”Р РЋР вЂљР В Р’В°Р В Р вЂ Р В Р’В»Р РЋР РЏР В Р’ВµР РЋРІР‚С™ Р В Р’В·Р В Р’В°Р В РЎВР В Р’ВµР РЋРІР‚С™Р В РЎвЂќР В Р’В°Р В РЎВР В РЎвЂ: add, read, clear."""
    notes_file = os.path.join(WORKSPACE_DIR, "notes.md")
    if action == "add" and text.strip():
        with open(notes_file, "a", encoding="utf-8") as f:
            f.write(f"- {text.strip()}\n")
        res = f"Р В РІР‚вЂќР В Р’В°Р В РЎвЂ”Р В РЎвЂР РЋР С“Р В Р’В°Р В Р вЂ¦Р В РЎвЂў: {text.strip()}"
    elif action == "read":
        res = open(notes_file, "r", encoding="utf-8").read().strip() if os.path.exists(notes_file) else "Р В РІР‚вЂќР В Р’В°Р В РЎВР В Р’ВµР РЋРІР‚С™Р В РЎвЂўР В РЎвЂќ Р В Р вЂ¦Р В Р’ВµР РЋРІР‚С™."
    elif action == "clear":
        open(notes_file, "w", encoding="utf-8").close()
        res = "Р В РІР‚вЂќР В Р’В°Р В РЎВР В Р’ВµР РЋРІР‚С™Р В РЎвЂќР В РЎвЂ Р В РЎвЂўР РЋРІР‚РЋР В РЎвЂР РЋРІР‚В°Р В Р’ВµР В Р вЂ¦Р РЋРІР‚в„–."
    else:
        res = "Р В Р в‚¬Р В РЎвЂќР В Р’В°Р В Р’В¶Р В РЎвЂР РЋРІР‚С™Р В Р’Вµ action: add, read Р В РЎвЂР В Р’В»Р В РЎвЂ clear."
    _log_event("manage_notes", {"action": action}, res)
    return res

@mcp.tool()
def capture_esp32_logs(seconds: int = 10) -> str:
    """Р В Р Р‹Р РЋРІР‚РЋР В РЎвЂР РЋРІР‚С™Р РЋРІР‚в„–Р В Р вЂ Р В Р’В°Р В Р’ВµР РЋРІР‚С™ Р РЋР С“Р В РЎвЂР РЋР С“Р РЋРІР‚С™Р В Р’ВµР В РЎВР В Р вЂ¦Р РЋРІР‚в„–Р В Р’Вµ Р В Р’В»Р В РЎвЂўР В РЎвЂ“Р В РЎвЂ Р РЋР С“ Р В РЎвЂќР В РЎвЂўР В Р’В»Р В РЎвЂўР В Р вЂ¦Р В РЎвЂќР В РЎвЂ ESP32-S3 (COM6)."""
    ports = list(serial.tools.list_ports.comports())
    esp_port = next((p.device for p in ports if p.device == "COM6" or "usb" in (p.description or "").lower()), None)
    if not esp_port:
        return "COM-Р В РЎвЂ”Р В РЎвЂўР РЋР вЂљР РЋРІР‚С™ ESP32-S3 Р В Р вЂ¦Р В Р’Вµ Р В Р вЂ¦Р В Р’В°Р В РІвЂћвЂ“Р В РўвЂР В Р’ВµР В Р вЂ¦."
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
        res = f"Р В Р Р‹Р В Р вЂ¦Р РЋР РЏР РЋРІР‚С™Р В РЎвЂў {len(collected)} Р РЋР С“Р РЋРІР‚С™Р РЋР вЂљР В РЎвЂўР В РЎвЂќ Р РЋР С“ {esp_port}."
    except Exception as e:
        res = f"Р В РЎвЂєР РЋРІвЂљВ¬Р В РЎвЂР В Р’В±Р В РЎвЂќР В Р’В° Р РЋРІР‚РЋР РЋРІР‚С™Р В Р’ВµР В Р вЂ¦Р В РЎвЂР РЋР РЏ {esp_port}: {str(e)}"
    _log_event("capture_esp32_logs", {"port": esp_port}, res)
    return res

@mcp.tool()
def ha_list_devices() -> str:
    """Р В РІР‚в„ўР В РЎвЂўР В Р’В·Р В Р вЂ Р РЋР вЂљР В Р’В°Р РЋРІР‚В°Р В Р’В°Р В Р’ВµР РЋРІР‚С™ Р РЋР С“Р В РЎвЂ”Р В РЎвЂР РЋР С“Р В РЎвЂўР В РЎвЂќ Р В Р вЂ Р РЋР С“Р В Р’ВµР РЋРІР‚В¦ Р РЋРЎвЂњР РЋР С“Р РЋРІР‚С™Р РЋР вЂљР В РЎвЂўР В РІвЂћвЂ“Р РЋР С“Р РЋРІР‚С™Р В Р вЂ  Р РЋРЎвЂњР В РЎВР В Р вЂ¦Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В РўвЂР В РЎвЂўР В РЎВР В Р’В° Р В РЎвЂР В Р’В· Home Assistant."""
    ha_url = os.getenv("HA_URL", "http://" + "127.0.0.1" + ":8123").rstrip("/")
    ha_token = os.getenv("HA_TOKEN", "").strip()
    if not ha_token:
        return "HA_TOKEN Р В Р вЂ¦Р В Р’Вµ Р В Р’В·Р В Р’В°Р В РўвЂР В Р’В°Р В Р вЂ¦."
    try:
        headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}
        resp = requests.get(f"{ha_url}/api/states", headers=headers, timeout=8)
        devices = []
        for item in resp.json():
            eid = item.get("entity_id", "")
            if eid.startswith(("switch.", "light.", "climate.", "cover.", "sensor.", "vacuum.")):
                fname = item.get("attributes", {}).get("friendly_name", eid)
                devices.append(f"{fname} [{eid}]: {item.get('state')}")
        res = "\n".join(devices) if devices else "Р В Р в‚¬Р РЋР С“Р РЋРІР‚С™Р РЋР вЂљР В РЎвЂўР В РІвЂћвЂ“Р РЋР С“Р РЋРІР‚С™Р В Р вЂ Р В Р’В° Р В Р вЂ¦Р В Р’Вµ Р В Р вЂ¦Р В Р’В°Р В РІвЂћвЂ“Р В РўвЂР В Р’ВµР В Р вЂ¦Р РЋРІР‚в„–."
    except Exception as e:
        res = f"Р В РЎвЂєР РЋРІвЂљВ¬Р В РЎвЂР В Р’В±Р В РЎвЂќР В Р’В° HA: {str(e)}"
    _log_event("ha_list_devices", {}, f"Р В РЎСљР В Р’В°Р В РІвЂћвЂ“Р В РўвЂР В Р’ВµР В Р вЂ¦Р В РЎвЂў Р РЋРЎвЂњР РЋР С“Р РЋРІР‚С™Р РЋР вЂљР В РЎвЂўР В РІвЂћвЂ“Р РЋР С“Р РЋРІР‚С™Р В Р вЂ : {len(res.splitlines())}")
    return res

@mcp.tool()
def ha_control_device(entity_id: str, action: str) -> str:
    """Р В Р в‚¬Р В РЎвЂ”Р РЋР вЂљР В Р’В°Р В Р вЂ Р В Р’В»Р РЋР РЏР В Р’ВµР РЋРІР‚С™ Р РЋРЎвЂњР РЋР С“Р РЋРІР‚С™Р РЋР вЂљР В РЎвЂўР В РІвЂћвЂ“Р РЋР С“Р РЋРІР‚С™Р В Р вЂ Р В РЎвЂўР В РЎВ Р В Р вЂ  Home Assistant (turn_on, turn_off, toggle, start, return_to_base)."""
    ha_url = os.getenv("HA_URL", "http://" + "127.0.0.1" + ":8123").rstrip("/")
    ha_token = os.getenv("HA_TOKEN", "").strip()
    domain = entity_id.split(".")[0] if "." in entity_id else "homeassistant"
    try:
        headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}
        resp = requests.post(f"{ha_url}/api/services/{domain}/{action}", headers=headers, json={"entity_id": entity_id}, timeout=8)
        res = f"Р В РІР‚в„ўР РЋРІР‚в„–Р В РЎвЂ”Р В РЎвЂўР В Р’В»Р В Р вЂ¦Р В Р’ВµР В Р вЂ¦Р В РЎвЂў: {action} Р В РўвЂР В Р’В»Р РЋР РЏ {entity_id}." if resp.ok else f"Р В РЎвЂєР РЋРІвЂљВ¬Р В РЎвЂР В Р’В±Р В РЎвЂќР В Р’В°: {resp.status_code}"
    except Exception as e:
        res = f"Р В Р Р‹Р В Р’В±Р В РЎвЂўР В РІвЂћвЂ“ Р РЋРЎвЂњР В РЎвЂ”Р РЋР вЂљР В Р’В°Р В Р вЂ Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В РЎвЂР РЋР РЏ: {str(e)}"
    _log_event("ha_control_device", {"entity_id": entity_id, "action": action}, res)
    return res

@mcp.tool()
def write_workspace_file(filename: str, content: str) -> str:
    """Р В РІР‚ВР В Р’ВµР В Р’В·Р В РЎвЂўР В РЎвЂ”Р В Р’В°Р РЋР С“Р В Р вЂ¦Р В РЎвЂў Р РЋР С“Р В РЎвЂўР В Р’В·Р В РўвЂР В Р’В°Р В Р’ВµР РЋРІР‚С™ Р В РЎвЂР В Р’В»Р В РЎвЂ Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В·Р В Р’В°Р В РЎвЂ”Р В РЎвЂР РЋР С“Р РЋРІР‚в„–Р В Р вЂ Р В Р’В°Р В Р’ВµР РЋРІР‚С™ Р РЋРІР‚С›Р В Р’В°Р В РІвЂћвЂ“Р В Р’В» Р В Р вЂ Р В Р вЂ¦Р РЋРЎвЂњР РЋРІР‚С™Р РЋР вЂљР В РЎвЂ Р В РЎвЂ”Р В Р’В°Р В РЎвЂ”Р В РЎвЂќР В РЎвЂ C:\\XiaoZhi-PC\\workspace."""
    safe_name = os.path.basename(filename)
    if not safe_name:
        return "Р В РЎСљР В Р’ВµР В РЎвЂќР В РЎвЂўР РЋР вЂљР РЋР вЂљР В Р’ВµР В РЎвЂќР РЋРІР‚С™Р В Р вЂ¦Р В РЎвЂўР В Р’Вµ Р В РЎвЂР В РЎВР РЋР РЏ Р РЋРІР‚С›Р В Р’В°Р В РІвЂћвЂ“Р В Р’В»Р В Р’В°."
    target_path = os.path.join(WORKSPACE_DIR, safe_name)
    _create_auto_backup("pre_write")
    try:
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
        res = f"Р В Р’В¤Р В Р’В°Р В РІвЂћвЂ“Р В Р’В» Р РЋРЎвЂњР РЋР С“Р В РЎвЂ”Р В Р’ВµР РЋРІвЂљВ¬Р В Р вЂ¦Р В РЎвЂў Р РЋР С“Р В РЎвЂўР РЋРІР‚В¦Р РЋР вЂљР В Р’В°Р В Р вЂ¦Р В Р’ВµР В Р вЂ¦: {target_path} ({len(content)} Р В Р’В±Р В Р’В°Р В РІвЂћвЂ“Р РЋРІР‚С™)."
    except Exception as e:
        res = f"Р В РЎвЂєР РЋРІвЂљВ¬Р В РЎвЂР В Р’В±Р В РЎвЂќР В Р’В° Р В Р’В·Р В Р’В°Р В РЎвЂ”Р В РЎвЂР РЋР С“Р В РЎвЂ Р РЋРІР‚С›Р В Р’В°Р В РІвЂћвЂ“Р В Р’В»Р В Р’В°: {str(e)}"
    _log_event("write_workspace_file", {"filename": safe_name, "bytes": len(content)}, res)
    return res

@mcp.tool()
def launch_workspace_script(filename: str) -> str:
    """Р В РІР‚вЂќР В Р’В°Р В РЎвЂ”Р РЋРЎвЂњР РЋР С“Р В РЎвЂќР В Р’В°Р В Р’ВµР РЋРІР‚С™ Python-Р РЋР С“Р В РЎвЂќР РЋР вЂљР В РЎвЂР В РЎвЂ”Р РЋРІР‚С™ Р В РЎвЂР В Р’В· Р В РЎвЂ”Р В Р’В°Р В РЎвЂ”Р В РЎвЂќР В РЎвЂ workspace Р В Р вЂ  Р В РЎвЂўР РЋРІР‚С™Р В РўвЂР В Р’ВµР В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂўР В РЎВ Р В РЎвЂўР В РЎвЂќР В Р вЂ¦Р В Р’Вµ Р В Р’В±Р В Р’ВµР В Р’В· Р В Р’В±Р В Р’В»Р В РЎвЂўР В РЎвЂќР В РЎвЂР РЋР вЂљР В РЎвЂўР В Р вЂ Р В РЎвЂќР В РЎвЂ Р В Р’В°Р В РЎвЂ“Р В Р’ВµР В Р вЂ¦Р РЋРІР‚С™Р В Р’В°."""
    safe_name = os.path.basename(filename)
    target_path = os.path.join(WORKSPACE_DIR, safe_name)
    if not os.path.exists(target_path):
        return f"Р В Р’В¤Р В Р’В°Р В РІвЂћвЂ“Р В Р’В» {safe_name} Р В Р вЂ¦Р В Р’Вµ Р В Р вЂ¦Р В Р’В°Р В РІвЂћвЂ“Р В РўвЂР В Р’ВµР В Р вЂ¦ Р В Р вЂ  workspace."
    try:
        subprocess.Popen([r"C:\Python315\python.exe", target_path], cwd=WORKSPACE_DIR, creationflags=subprocess.CREATE_NEW_CONSOLE)
        res = f"Р В Р Р‹Р В РЎвЂќР РЋР вЂљР В РЎвЂР В РЎвЂ”Р РЋРІР‚С™ {safe_name} Р В Р’В·Р В Р’В°Р В РЎвЂ”Р РЋРЎвЂњР РЋРІР‚В°Р В Р’ВµР В Р вЂ¦ Р В Р вЂ  Р В РЎвЂўР РЋРІР‚С™Р В РўвЂР В Р’ВµР В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂўР В РЎВ Р В РЎвЂўР В РЎвЂќР В Р вЂ¦Р В Р’Вµ."
    except Exception as e:
        res = f"Р В РЎвЂєР РЋРІвЂљВ¬Р В РЎвЂР В Р’В±Р В РЎвЂќР В Р’В° Р В Р’В·Р В Р’В°Р В РЎвЂ”Р РЋРЎвЂњР РЋР С“Р В РЎвЂќР В Р’В°: {str(e)}"
    _log_event("launch_workspace_script", {"filename": safe_name}, res)
    return res
# === СИСТЕМНЫЙ ПУЛЬТ ПК (БРАУЗЕР, БУФЕР ОБМЕНА, СЕТЬ, ПИТАНИЕ) ===

@mcp.tool()
def open_website(target: str) -> str:
    """Открывает сайт в браузере Windows. Поддерживает имена ('youtube', 'yandex', 'github', 'ha', 'xiaozhi') или полный URL."""
    import webbrowser
    aliases = {
        "youtube": "https://" + "://youtube.com",
        "yandex": "https://" + "ya.ru",
        "music": "https://" + "music.yandex.ru",
        "github": "https://" + "://github.com",
        "ha": "http://" + "127.0.0.1:8123",
        "xiaozhi": "https://" + "xiaozhi.me"
    }
    key = target.lower().strip()
    url = aliases.get(key, target.strip())
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    webbrowser.open(url)
    res = f"Открыто в браузере: {url}"
    _log_event("open_website", {"url": url}, res)
    return res

@mcp.tool()
def clipboard_manager(action: str, text: str = "") -> str:
    """Работает с буфером обмена Windows: 'read' (прочитать) или 'write' (записать текст)."""
    import pyperclip
    if action == "read":
        content = pyperclip.paste()
        res = f"В буфере обмена: {content[:500]}" if content else "Буфер обмена пуст."
    elif action == "write":
        pyperclip.copy(text)
        res = f"Скопировано в буфер обмена ({len(text)} симв.)."
    else:
        res = "Укажите action: 'read' или 'write'."
    _log_event("clipboard_manager", {"action": action}, res)
    return res

@mcp.tool()
def scan_local_network() -> str:
    """Показывает активные устройства в локальной домашней сети Wi-Fi (IP и MAC-адреса)."""
    return run_safe_powershell("arp -a | Select-String 'dynamic|динамический'")

@mcp.tool()
def pc_power_control(action: str, minutes: int = 30) -> str:
    """Управляет экраном и таймером сна ПК: 'lock' (блокировка), 'sleep_timer' (сон через N мин), 'cancel_timer' (отмена)."""
    if action == "lock":
        return run_safe_powershell("rundll32.exe user32.dll,LockWorkStation")
    elif action == "sleep_timer":
        sec = max(60, int(minutes) * 60)
        return run_safe_powershell(f"shutdown /s /t {sec}")
    elif action == "cancel_timer":
        return run_safe_powershell("shutdown /a")
    return "Доступные действия: lock, sleep_timer, cancel_timer."


def _call_gemini_proxy(sys_prompt: str, user_prompt: str, temp: float = 0.3) -> str:
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key:
        return "Ошибка: LLM_API_KEY не задан в .env."
    url = "https://" + "api.proxyapi" + ".ru/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    for model_name in ["deepseek/deepseek-chat", "openai/gpt-4o-mini"]:
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temp
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        if resp.ok:
            return resp.json()["choices"][0]["message"]["content"].strip()
    raise RuntimeError(f"ProxyAPI ({resp.status_code}): {resp.text[:200]}")

# === ЧАСТЬ 2: ЖИВОЙ ВЕБ-ПОИСК И СУБ-АГЕНТ ПРОГРАММИСТ (GEMINI 2.5 PRO) ===

@mcp.tool()
def web_search_info(query: str, max_results: int = 4) -> str:
    """Ищет актуальную информацию в интернете в реальном времени (новости, факты, документация, цены)."""
    try:
        from ddgs import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=min(max_results, 6)):
                results.append(f"- {r.get('title')}: {r.get('body')} ({r.get('href')})")
        res = "\n".join(results) if results else f"По запросу '{query}' ничего не найдено."
    except Exception as e:
        res = f"Ошибка веб-поиска: {str(e)}"
    _log_event("web_search_info", {"query": query}, f"Результатов: {len(res.splitlines())}")
    return res

@mcp.tool()
def ask_coder_pro(task_description: str, save_to_filename: str = "") -> str:
    """Передает сложную задачу программирования суб-агенту Gemini 2.5 Pro и сохраняет код в workspace."""
    sys_msg = "Ты — элитный Python-разработчик. Напиши полный, рабочий код. Если нужно сохранить файл — выведи ТОЛЬКО чистый код без markdown-оберток."
    try:
        answer = _call_gemini_proxy(sys_msg, task_description, 0.2)
        answer = re.sub(r"^```[a-zA-Z]*\n", "", answer)
        answer = re.sub(r"\n```$", "", answer)
        if save_to_filename.strip():
            save_res = write_workspace_file(save_to_filename.strip(), answer)
            res = f"Суб-агент Gemini 2.5 Pro выполнил задачу. {save_res}"
        else:
            res = answer[:1500]
    except Exception as e:
        res = f"Сбой суб-агента кодера: {str(e)}"
    _log_event("ask_coder_pro", {"task": task_description[:80], "file": save_to_filename}, res[:200])
    return res

# === ГЛУБОКИЙ АНАЛИТИК ПРОЕКТА (ДЕЛЕГИРОВАНИЕ В GEMINI 2.5 PRO) ===

@mcp.tool()
def delegate_deep_task(goal: str, output_filename: str = "report.md", send_to_phone: bool = True) -> str:
    """Передает сложную аналитическую или творческую задачу модели Gemini 2.5 Pro с автоматическим сбором контекста проекта."""
    nl = chr(10)
    context_parts = []
    try:
        git_log = subprocess.check_output(["git", "-C", BASE_DIR, "log", "-n", "15", "--pretty=format:%ad | %s", "--date=short"], text=True, encoding="utf-8", errors="ignore")
        context_parts.append("=== ИСТОРИЯ КОММИТОВ GIT ===" + nl + git_log)
    except Exception:
        pass
    for doc in ["README.md", "ARCHITECTURE.md"]:
        p = os.path.join(BASE_DIR, doc)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8", errors="ignore") as df:
                context_parts.append(f"=== {doc} ===" + nl + df.read()[:3000])
    if os.path.exists(AUDIT_FILE):
        with open(AUDIT_FILE, "r", encoding="utf-8", errors="ignore") as af:
            lines = af.readlines()[-40:]
            context_parts.append("=== ПОСЛЕДНИЕ ДЕЙСТВИЯ В АУДИТ-ЛОГЕ ===" + nl + "".join(lines)[:4000])

    full_context = (nl + nl).join(context_parts)
    sys_prompt = "Ты — цифровой конструктор и хроникер проекта XiaoZhi-PC (энграмма Джонни Сильверхенда). На основе реальных данных из Git, логов и архитектуры выполни задачу максимально подробно и увлекательно на русском языке."
    try:
        report_text = _call_gemini_proxy(sys_prompt, f"ЗАДАЧА: {goal}" + nl + nl + "ДАННЫЕ ПРОЕКТА:" + nl + full_context, 0.4)
        safe_name = os.path.basename(output_filename) or "report.md"
        save_res = write_workspace_file(safe_name, report_text)
        phone_res = " " + phone_send_document(safe_name, report_text, f"Отчет от Джонни: {safe_name}") if send_to_phone else ""
        res = f"Глубокая задача выполнена. {save_res}{phone_res}"
    except Exception as e:
        res = f"Сбой глубокого анализа: {str(e)}"
    _log_event("delegate_deep_task", {"goal": goal[:80], "file": output_filename}, res)
    return res


@mcp.tool()
def phone_send_document(filename: str, content: str, caption: str = "Файл от Джонни") -> str:
    """Создает файл (текст, код, список, отчет) и отправляет его прямо на телефон пользователя через ntfy."""
    topic = os.getenv("PHONE_NTFY_TOPIC", "").strip()
    if not topic:
        return "Канал ntfy не настроен в .env."
    safe_name = os.path.basename(filename) or "note.txt"
    from urllib.parse import quote
    ntfy_url = "https://" + "ntfy.sh" + f"/{topic}?message={quote(caption)}"
    try:
        resp = requests.put(
            ntfy_url,
            data=content.encode("utf-8"),
            headers={"Filename": safe_name, "Title": f"Johnny File: {safe_name}"},
            timeout=15
        )
        res = f"Файл '{safe_name}' успешно отправлен на телефон." if resp.ok else f"Ошибка ntfy: {resp.status_code}"
    except Exception as e:
        res = f"Сбой отправки файла: {str(e)}"
    _log_event("phone_send_document", {"filename": safe_name, "bytes": len(content)}, res)
    return res


# === ЛОКАЛЬНЫЙ ИИ-АГЕНТ (OLLAMA JOHNNY-LOCAL + ПОЛНАЯ ТЕЛЕМЕТРИЯ) ===

@mcp.tool()
def ask_local_ollama(prompt: str, model: str = "johnny-local") -> str:
    """Обращается к локальной настроенной нейросети johnny-local (Ollama) с полной фиксацией хода рассуждений и скорости в ai_decisions_audit.jsonl."""
    import time
    url = "http://" + "127.0.0" + ".1:11434/api/chat"
    t0 = time.time()
    try:
        resp = requests.post(
            url,
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "keep_alive": "24h"
            },
            timeout=180
        )
        dt = time.time() - t0
        if not resp.ok:
            return f"Ошибка Ollama ({resp.status_code}): {resp.text[:150]}"
        data = resp.json()
        answer = data.get("message", {}).get("content", "").strip()
        eval_count = data.get("eval_count", 0)
        _log_ai_decision("ollama_local", model, prompt, answer, dt, eval_count)
        res = answer if answer else "Локальная модель вернула пустой ответ."
    except Exception as e:
        res = f"Локальный сервер Ollama недоступен: {str(e)}"
    _log_event("ask_local_ollama", {"model": model, "prompt": prompt[:60]}, res[:200])
    return res

@mcp.tool()
def compare_ai_brains(task_prompt: str, send_to_phone: bool = False) -> str:
    """Прогоняет одну задачу через локальную Ollama (johnny-local) и облачный ProxyAPI (DeepSeek), сравнивает скорость и решения, сохраняя отчёт в workspace/ai_comparison.md."""
    import time
    nl = chr(10)
    # 1. Локальный ответ
    t_loc = time.time()
    loc_ans = ask_local_ollama(task_prompt, "johnny-local")
    dt_loc = round(time.time() - t_loc, 2)

    # 2. Облачный ответ
    t_cld = time.time()
    try:
        cld_ans = _call_gemini_proxy("Ты — технический эксперт. Ответь структурированно на русском языке.", task_prompt, 0.3)
    except Exception as e:
        cld_ans = f"Ошибка облака: {e}"
    dt_cld = round(time.time() - t_cld, 2)
    _log_ai_decision("proxyapi_cloud", "deepseek-chat", task_prompt, cld_ans, dt_cld, 0)

    report = (
        f"# Сравнительный анализ ИИ-решений{nl}"
        f"**Задача:** {task_prompt}{nl}{nl}"
        f"## 1. Локальный модуль Ollama (`johnny-local`) — {dt_loc} сек.{nl}{loc_ans}{nl}{nl}"
        f"---{nl}{nl}"
        f"## 2. Облачный модуль ProxyAPI (`deepseek-chat`) — {dt_cld} сек.{nl}{cld_ans}{nl}"
    )
    save_msg = write_workspace_file("ai_comparison.md", report)
    if send_to_phone:
        phone_send_document("ai_comparison.md", report, "Сравнение Ollama vs Cloud")
    return f"Сравнение завершено (Локально: {dt_loc}с | Облако: {dt_cld}с). {save_msg}"

if __name__ == "__main__":
    mcp.run(transport="stdio")





