# Copyright (c) 2026 Курчицикий М.С (fseven89). All rights reserved.
# Project: XiaoZhi-PC (https://github.com)
import datetime, glob, json, os, re, subprocess, tempfile, zipfile
import psutil, requests, mss, serial, serial.tools.list_ports
from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

import dpapi_vault as _dpapi_vault
_dpapi_vault.load_dpapi_into_environ()
load_dotenv(r"C:\XiaoZhi-PC\.env", override=False)

BASE_DIR = r"C:\XiaoZhi-PC"
STATE_FILE = os.path.join(BASE_DIR, "state.json")
WORKSPACE_DIR = os.path.join(BASE_DIR, "workspace")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
BACKUPS_DIR = os.path.join(BASE_DIR, "backups")
AUDIT_FILE = os.path.join(LOGS_DIR, "johnny_audit.jsonl")

for d in (WORKSPACE_DIR, LOGS_DIR, BACKUPS_DIR):
    os.makedirs(d, exist_ok=True)

from redline_guard import RedLineGuard
_REDLINE = RedLineGuard(ttl_seconds=90)

mcp = MCPServer("Johnny-Silverhand-Hub-v3")

import base64 as _b64

def _encode_rfc2047(text: str) -> str:
    b64 = _b64.b64encode(text.encode("utf-8")).decode("ascii")
    return f"=?utf-8?b?{b64}?="


def _get_telegram_config() -> tuple[str, str, str]:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    api_base = os.getenv("TELEGRAM_API_BASE", "https://telegram.org").strip().rstrip("/")
    chat_id = os.getenv("TELEGRAM_ALLOWED_USER_ID", "").strip()
    if not chat_id:
        owner_file = os.path.join(LOGS_DIR, "tg_owner_id.txt")
        if os.path.exists(owner_file):
            try:
                chat_id = open(owner_file, "r", encoding="utf-8").read().strip()
            except Exception:
                pass
    return token, api_base, chat_id

def _send_via_telegram_text(text: str, screenshot_path: str = "") -> tuple[bool, str]:
    token, api_base, chat_id = _get_telegram_config()
    if not token or not chat_id:
        return False, "Telegram не настроен (нет токена или chat_id)"
    try:
        if screenshot_path and os.path.exists(screenshot_path):
            with open(screenshot_path, "rb") as img:
                r = requests.post(
                    f"{api_base}/bot{token}/sendPhoto",
                    data={"chat_id": chat_id, "caption": text[:1000]},
                    files={"photo": ("screen.png", img, "image/png")},
                    timeout=25
                )
        else:
            r = requests.post(
                f"{api_base}/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text[:4000]},
                timeout=15
            )
        if r.ok and r.json().get("ok"):
            return True, "Успешно отправлено в Telegram"
        return False, f"Telegram HTTP {r.status_code}: {r.text[:120]}"
    except Exception as e:
        return False, f"Сбой Telegram: {str(e)}"

def _send_via_telegram_doc(filename: str, content: str, caption: str) -> tuple[bool, str]:
    token, api_base, chat_id = _get_telegram_config()
    if not token or not chat_id:
        return False, "Telegram не настроен"
    try:
        r = requests.post(
            f"{api_base}/bot{token}/sendDocument",
            data={"chat_id": chat_id, "caption": caption[:1000]},
            files={"document": (filename, content.encode("utf-8"), "text/plain; charset=utf-8")},
            timeout=25
        )
        if r.ok and r.json().get("ok"):
            return True, f"Файл '{filename}' отправлен в Telegram."
        return False, f"Telegram Doc HTTP {r.status_code}: {r.text[:120]}"
    except Exception as e:
        return False, f"Сбой Telegram Doc: {str(e)}"

def _transliterate_filename(name: str) -> str:
    ru_map = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya"
    }
    out = []
    for ch in name:
        low = ch.lower()
        if low in ru_map:
            tr = ru_map[low]
            out.append(tr.capitalize() if ch.isupper() else tr)
        elif ch.isascii() and (ch.isalnum() or ch in "._-"):
            out.append(ch)
        else:
            out.append("_")
    cleaned = re.sub(r"_+", "_", "".join(out)).strip("._ ")
    if not cleaned:
        return "johnny_file.txt"
    return "johnny_file" + cleaned if cleaned.startswith(".") else cleaned

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
    r"stop-computer", r"restart-computer", r"reg\s+delete",
    r"net\s+user", r"invoke-expression", r"\biex\b", r"\.env(?!\.example)", r"xiaozhi-esp32.*-Recurse",
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
    """Переключает режим работы Джонни: 'combat', 'companion' или 'entertainment'."""
    m = mode.lower().strip()
    if m not in ("combat", "companion", "entertainment"):
        return "Доступные режимы: combat, companion, entertainment."
    st = _load_state()
    st["mode"] = m
    _save_state(st)
    res = f"Active mode switched to: {m} ({MODES_CONFIG[m]['name']})."
    _log_event("switch_assistant_mode", {"mode": m}, res)
    return res

@mcp.tool()
def run_safe_powershell(command: str) -> str:
    """Р В РІР‚в„ўР РЋРІР‚в„–Р В РЎвЂ”Р В РЎвЂўР В Р’В»Р В Р вЂ¦Р РЋР РЏР В Р’ВµР РЋРІР‚С™ Р В Р’В±Р В Р’ВµР В Р’В·Р В РЎвЂўР В РЎвЂ”Р В Р’В°Р РЋР С“Р В Р вЂ¦Р РЋРЎвЂњР РЋР вЂ№ Р В РЎвЂќР В РЎвЂўР В РЎВР В Р’В°Р В Р вЂ¦Р В РўвЂР РЋРЎвЂњ PowerShell Р РЋР С“ Р В РЎвЂ”Р РЋР вЂљР В Р’ВµР В РўвЂР В Р вЂ Р В Р’В°Р РЋР вЂљР В РЎвЂР РЋРІР‚С™Р В Р’ВµР В Р’В»Р РЋР Р‰Р В Р вЂ¦Р РЋРІР‚в„–Р В РЎВ Р В Р’В°Р В Р вЂ Р РЋРІР‚С™Р В РЎвЂў-Р В Р’В±Р РЋР РЉР В РЎвЂќР В Р’В°Р В РЎвЂ”Р В РЎвЂўР В РЎВ."""
    rl_status, rl_reason, rl_code = _REDLINE.analyze_command(command)
    if rl_status == "DLP_BLOCK":
        _log_event("run_safe_powershell_DLP_BLOCK", {"command": "[REDACTED]"}, rl_reason)
        return f"DLP-БЛОКИРОВКА: {rl_reason}"
    if rl_status == "POINT_OF_NO_RETURN":
        _log_event("run_safe_powershell_REDLINE", {"command": command, "code": rl_code}, rl_reason)
        return f"ТОЧКА НЕВОЗВРАТА! Риск: {rl_reason}. Для принудительного выполнения назови код подтверждения: {rl_code} (действует 90 сек)."
    is_safe, reason = _is_command_safe(command)
    if not is_safe:
        _log_event("run_safe_powershell_BLOCKED", {"command": command}, reason)
        return reason
    is_mutating = any(w in command.lower() for w in ["set-content", "out-file", "remove-item", "move-item", "copy-item", "new-item", "del ", "rm ", "docker ", "git ", ">"])
    bkp_name = _create_auto_backup("pre_ps") if is_mutating else "skipped_readonly"
    try:
        utf8_cmd = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; " + command
        result = subprocess.run(["powershell", "-NoProfile", "-Command", utf8_cmd], cwd=WORKSPACE_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
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
                                matches.append(f"{fname} (РЎРѓРЎвЂљРЎР‚. {idx}): {line.strip()[:120]}")
                except Exception:
                    pass
    res = "\n".join(matches[:15]) if matches else f"Р В Р Р‹Р В РЎвЂўР В Р вЂ Р В РЎвЂ”Р В Р’В°Р В РўвЂР В Р’ВµР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р В РЎвЂ”Р В РЎвЂў Р В Р’В·Р В Р’В°Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋР С“Р РЋРЎвЂњ '{query}' Р В Р вЂ¦Р В Р’Вµ Р В Р вЂ¦Р В Р’В°Р В РІвЂћвЂ“Р В РўвЂР В Р’ВµР В Р вЂ¦Р В РЎвЂў."
    _log_event("search_workspace_docs", {"query": query}, f"Р В РЎСљР В Р’В°Р В РІвЂћвЂ“Р В РўвЂР В Р’ВµР В Р вЂ¦Р В РЎвЂў: {len(matches)}")
    return res

@mcp.tool()
def phone_send_telegram(message: str, attach_screenshot: bool = False) -> str:
    """Отправляет текст или скриншот экрана ПК на телефон в Telegram (с авто-резервом на ntfy.sh)."""
    return phone_send_ntfy(message=message, attach_screenshot=attach_screenshot)

@mcp.tool()
def phone_send_ntfy(message: str, attach_screenshot: bool = False) -> str:
    """Отправляет текст или скриншот экрана ПК на телефон (основной канал: Telegram, резерв: ntfy.sh)."""
    dlp_ok, dlp_msg = _REDLINE.analyze_outbound_text(message)
    if not dlp_ok:
        _log_event("phone_send_DLP_BLOCK", {}, dlp_msg)
        return dlp_msg

    tmp_path = ""
    if attach_screenshot:
        with mss.mss() as sct:
            tmp_path = os.path.join(tempfile.gettempdir(), "xiaozhi_screen.png")
            sct.shot(output=tmp_path)

    try:
        # 1. Основной канал: Telegram (через Cloudflare Worker)
        tg_ok, tg_res = _send_via_telegram_text(message, tmp_path)
        if tg_ok:
            _log_event("phone_send_telegram", {"message": message[:80], "screenshot": attach_screenshot}, tg_res)
            return tg_res

        # 2. Резервный канал: ntfy.sh
        topic = os.getenv("PHONE_NTFY_TOPIC", "").strip()
        if not topic:
            res = f"{tg_res} (резерв ntfy не настроен)"
            _log_event("phone_send_failed", {"tg_err": tg_res}, res)
            return res

        ntfy_url = "https://" + "ntfy.sh" + f"/{topic}"
        if attach_screenshot and tmp_path:
            with open(tmp_path, "rb") as img:
                safe_msg = message.encode("latin-1", "ignore").decode("latin-1") or "Screenshot"
                resp = requests.put(ntfy_url, data=img, headers={"Filename": "screen.png", "Title": "Johnny PC Screen", "Message": safe_msg}, timeout=15)
        else:
            resp = requests.post(ntfy_url, data=message.encode("utf-8"), headers={"Title": "Johnny PC"}, timeout=10)
        res = f"Отправлено через резерв ntfy (Telegram недоступен: {tg_res[:60]})" if resp.ok else f"Ошибка обоих каналов (TG: {tg_res[:50]} | ntfy: {resp.status_code})"
    except Exception as e:
        res = f"Сбой отправки на телефон: {str(e)}"
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    _log_event("phone_send_ntfy_fallback", {"message": message[:80], "screenshot": attach_screenshot}, res)
    return res

@mcp.tool()
def pc_get_weather(city: str = "") -> str:
    """Р В РЎСџР В РЎвЂўР В Р’В»Р РЋРЎвЂњР РЋРІР‚РЋР В Р’В°Р В Р’ВµР РЋРІР‚С™ Р РЋРІР‚С™Р В Р’ВµР В РЎвЂќР РЋРЎвЂњР РЋРІР‚В°Р РЋРЎвЂњР РЋР вЂ№ Р В РЎвЂ”Р В РЎвЂўР В РЎвЂ“Р В РЎвЂўР В РўвЂР РЋРЎвЂњ Р В Р’В±Р В Р’ВµР В Р’В· API-Р В РЎвЂќР В Р’В»Р РЋР вЂ№Р РЋРІР‚РЋР В Р’ВµР В РІвЂћвЂ“."""
    target = city.strip() if city.strip() else os.getenv("DEFAULT_CITY", "Saint-Petersburg")
    url = "https://" + "wttr.in" + f"/{target}?format=3&lang=ru"
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
        res = f"File saved: {target_path} ({len(content)} bytes)."
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
        subprocess.Popen([__import__("sys").executable, target_path], cwd=WORKSPACE_DIR, creationflags=subprocess.CREATE_NEW_CONSOLE)
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
        "youtube": "https://youtube.com",
        "yandex": "https://" + "ya.ru",
        "music": "https://" + "music.yandex.ru",
        "github": "https://github.com",
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

def _gather_live_project_context() -> str:
    nl = chr(10)
    parts = []
    for doc in ["HARDWARE_PASSPORT.md", "ARCHITECTURE.md"]:
        p = os.path.join(BASE_DIR, doc)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                parts.append(f"=== {doc} ===" + nl + f.read()[:3500])
    live_log = os.path.join(LOGS_DIR, "esp32_live.log")
    if os.path.exists(live_log):
        with open(live_log, "r", encoding="utf-8", errors="ignore") as lf:
            tail = lf.readlines()[-25:]
            parts.append("=== ЖИВОЙ ЛОГ ESP32-S3 (esp32_live.log) ===" + nl + "".join(tail))
    return (nl + nl).join(parts)


def delegate_deep_task(goal: str, output_filename: str = "report.md", send_to_phone: bool = True) -> str:
    """Передает сложную аналитическую или творческую задачу модели Gemini 2.5 Pro с автоматическим сбором контекста проекта."""
    nl = chr(10)
    context_parts = []
    try:
        git_log = subprocess.check_output(["git", "-C", BASE_DIR, "log", "-n", "15", "--pretty=format:%ad | %s", "--date=short"], text=True, encoding="utf-8", errors="ignore")
        context_parts.append("=== ИСТОРИЯ КОММИТОВ GIT ===" + nl + git_log)
    except Exception:
        pass
    context_parts.append(_gather_live_project_context())
    for doc in ["README.md"]:
        p = os.path.join(BASE_DIR, doc)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8", errors="ignore") as df:
                context_parts.append(f"=== {doc} ===" + nl + df.read()[:3000])
    if os.path.exists(AUDIT_FILE):
        with open(AUDIT_FILE, "r", encoding="utf-8", errors="ignore") as af:
            lines = af.readlines()[-40:]
            context_parts.append("=== ПОСЛЕДНИЕ ДЕЙСТВИЯ В АУДИТ-ЛОГЕ ===" + nl + "".join(lines)[:4000])

    full_context = (nl + nl).join(context_parts)
    sys_prompt = "Ты — строгий технический аналитик проекта XiaoZhi-PC (Автор: Курчицикий М.С / fseven89). СТРОГИЙ ЗАПРЕТ НА ВЫДУМКИ: опирайся ТОЛЬКО на факты, которые буквально присутствуют в разделе ДАННЫЕ ПРОЕКТА. Категорически запрещено выдумывать события Windows, коды ошибок, имена функций или предлагать откатывать код без прямых доказательств. Если данных недостаточно, прямо напиши: НЕДОСТАТОЧНО ДАННЫХ. На основе реальных данных из Git, логов и архитектуры выполни задачу максимально подробно и увлекательно на русском языке."
    try:
        report_text = _call_gemini_proxy(sys_prompt, f"ЗАДАЧА: {goal}" + nl + nl + "ДАННЫЕ ПРОЕКТА:" + nl + full_context, 0.1)
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
    """Создает файл (текст, код, отчет) и отправляет на телефон в Telegram (резерв: ntfy.sh)."""
    dlp_ok, dlp_msg = _REDLINE.analyze_outbound_text(content)
    if not dlp_ok:
        _log_event("phone_send_document_DLP_BLOCK", {"filename": filename}, dlp_msg)
        return dlp_msg

    safe_name = os.path.basename(filename) or "note.txt"

    # 1. Основной канал: Telegram
    tg_ok, tg_res = _send_via_telegram_doc(safe_name, content, caption)
    if tg_ok:
        _log_event("phone_send_document_tg", {"filename": safe_name, "bytes": len(content)}, tg_res)
        return tg_res

    # 2. Резервный канал: ntfy.sh
    topic = os.getenv("PHONE_NTFY_TOPIC", "").strip()
    if not topic:
        return f"Ошибка Telegram ({tg_res}), резерв ntfy не настроен."
    from urllib.parse import quote
    ntfy_url = "https://" + "ntfy.sh" + f"/{topic}?message={quote(caption)}"
    try:
        ascii_name = _transliterate_filename(safe_name)
        resp = requests.put(
            ntfy_url,
            data=content.encode("utf-8"),
            headers={
                "Filename": ascii_name,
                "Title": _encode_rfc2047(f"Johnny File: {safe_name}")
            },
            timeout=15
        )
        res = f"Файл '{safe_name}' отправлен через резерв ntfy." if resp.ok else f"Ошибка ntfy: {resp.status_code}"
    except Exception as e:
        res = f"Сбой отправки файла: {str(e)}"
    _log_event("phone_send_document_fallback", {"filename": safe_name, "bytes": len(content)}, res)
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
    t_loc = time.time()
    loc_ans = ask_local_ollama(task_prompt, "johnny-local")
    dt_loc = round(time.time() - t_loc, 2)

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


@mcp.tool()
def read_esp32_live_logs(lines: int = 40) -> str:
    """Читает последние строки непрерывного журнала работы колонки XiaoZhi (Wi-Fi, WebSocket xiaozhi.me, ошибки платы)."""
    log_p = os.path.join(LOGS_DIR, "esp32_live.log")
    if not os.path.exists(log_p):
        return "Файл esp32_live.log пока пуст (убедитесь, что колонка подключена к COM6)."
    with open(log_p, "r", encoding="utf-8", errors="replace") as f:
        tail = f.readlines()[-min(lines, 150):]
    return "".join(tail) if tail else "Лог пуст."


# === КОНТУР ГАРАНТИРОВАННОГО ПИТАНИЯ ЗАДАЧ (ИТ-СБГЭ: АВР + ИБП + ДГУ) ===
import failover_power_grid as _sbge

@mcp.tool()
def get_it_sbge_status() -> str:
    """Показывает состояние всех линий резервирования ИТ-СБГЭ (Ввод 1, Ввод 2 АВР, буфер ИБП и локальный генератор Ollama)."""
    return _sbge.get_sbge_telemetry()

@mcp.tool()
def ask_johnny_resilient(task_prompt: str) -> str:
    """Выполняет задачу через каскад СБГЭ: ИБП (буфер) -> Ввод 1 -> АВР -> Ввод 2 -> ДГУ (локальная Ollama без интернета)."""
    res = _sbge.execute_with_avr(task_prompt)
    return f"[{res['line']} | {res['ms']} мс]" + chr(10) + res['answer']

# === МОДУЛЬ СВОДНОЙ АНАЛИТИКИ И МОНИТОРИНГА ===
import system_analytics as _sys_analytics

@mcp.tool()
def get_full_analytics_dashboard(send_to_phone: bool = False) -> str:
    """Формирует полную аналитику работы системы: статистику ИИ-моделей, переключения СБГЭ, здоровье SRAM платы ESP32-S3 и ресурсы ПК."""
    report = _sys_analytics.build_analytics_report()
    if send_to_phone:
        phone_send_document("analytics_report.txt", report, "Аналитика XiaoZhi-PC")
    return report


# === МУЛЬТИМОДАЛЬНЫЙ АНАЛИЗ ФОТО И ФАЙЛОВ С ТЕЛЕФОНА ===
import vision_inbox as _vision_inbox

@mcp.tool()
def analyze_latest_inbox_item(question: str = 'Сделай подробный технический анализ этого фото или файла.') -> str:
    """Анализирует самое свежее фото или файл, присланный с телефона в workspace/inbox."""
    return _vision_inbox.analyze_latest(question)


# === ТОЧКА НЕВОЗВРАТА И ТОЧНОЕ УПРАВЛЕНИЕ ГРОМКОСТЬЮ (V4.0) ===
@mcp.tool()
def confirm_redline_action(code: str) -> str:
    """Подтверждает и выполняет ранее заблокированную команду точки невозврата по 4-значному коду."""
    cmd = _REDLINE.verify_confirmation(code)
    if not cmd:
        return "Неверный или просроченный код подтверждения точки невозврата."
    bkp_name = _create_auto_backup("redline_confirmed")
    try:
        result = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], cwd=WORKSPACE_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        out = result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
        res = out if out else "Команда точки невозврата выполнена."
    except Exception as e:
        res = f"Ошибка выполнения: {str(e)}"
    _log_event("confirm_redline_action", {"code": code, "backup": bkp_name}, res)
    return res

@mcp.tool()
def set_system_volume_percent(percent: int = 10) -> str:
    """Устанавливает системную громкость Windows точно на заданный процент (0-100) через нативный CoreAudio API."""
    lvl = max(0, min(100, int(percent)))
    ps_script = f"""
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioEndpointVolume {{
    int RegisterControlChangeNotify(IntPtr pNotify);
    int UnregisterControlChangeNotify(IntPtr pNotify);
    int GetChannelCount(out uint pnChannelCount);
    int SetMasterVolumeLevel(float fLevelDB, Guid pguidEventContext);
    int SetMasterVolumeLevelScalar(float fLevel, Guid pguidEventContext);
    int GetMasterVolumeLevel(out float pfLevelDB);
    int GetMasterVolumeLevelScalar(out float pfLevel);
}}
[Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDevice {{
    int Activate(ref Guid iid, int dwClsCtx, IntPtr pActivationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
}}
[Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDeviceEnumerator {{
    int EnumAudioEndpoints(int dataFlow, int dwStateMask, out IntPtr ppDevices);
    int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice ppEndpoint);
}}
[ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")] class MMDeviceEnumerator {{}}
public class CoreAudioVol {{
    public static void Set(float val) {{
        var enumerator = new MMDeviceEnumerator() as IMMDeviceEnumerator;
        IMMDevice dev;
        enumerator.GetDefaultAudioEndpoint(0, 1, out dev);
        Guid iid = typeof(IAudioEndpointVolume).GUID;
        object o;
        dev.Activate(ref iid, 1, IntPtr.Zero, out o);
        var epv = (IAudioEndpointVolume)o;
        epv.SetMasterVolumeLevelScalar(val, Guid.Empty);
    }}
}}
"@ -ErrorAction SilentlyContinue
[CoreAudioVol]::Set({lvl / 100.0})
Write-Output "OK:{lvl}"
"""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
        res = f"Громкость Windows установлена точно на {lvl}%." if r.returncode == 0 else f"Ошибка CoreAudio: {r.stderr.strip()}"
    except Exception as e:
        res = f"Сбой управления громкостью: {str(e)}"
    _log_event("set_system_volume_percent", {"percent": lvl}, res)
    return res


# === МОДУЛЬ САМООБУЧЕНИЯ И КОНТРОЛЯ ЭНЕРГОЭФФЕКТИВНОСТИ (V4.0) ===
import self_learning_engine as _sle

@mcp.tool()
def run_self_reflection() -> str:
    """Анализирует свежие логи и сбои системы, пополняя базу усвоенных уроков Джонни."""
    res = _sle.analyze_logs_and_learn()
    _log_event("run_self_reflection", {}, res)
    return res

@mcp.tool()
def get_learned_lessons(limit: int = 8) -> str:
    """Показывает список усвоенных уроков и правил предотвращения ошибок."""
    return _sle.format_lessons_summary(limit=limit)

@mcp.tool()
def check_laptop_power_eco(threshold_percent: int = 25) -> str:
    """Проверяет заряд батареи ноутбука и активирует энергосберегающий контур при разряде."""
    st = _sle.check_battery_and_eco_state(threshold_percent=threshold_percent)
    if st.get("eco_triggered"):
        try:
            phone_send_ntfy(f"ВНИМАНИЕ: Ноутбук на батарее ({st['percent']}%). Перевожу Джонни в энергосберегающий режим.")
        except Exception:
            pass
    _log_event("check_laptop_power_eco", {"threshold": threshold_percent}, st["status"])
    return st["status"]


@mcp.tool()

@mcp.tool()
def run_full_system_audit(send_to_phone: bool = True) -> str:
    """Выполняет полный системный аудит всех узлов проекта XiaoZhi-PC (v4.1) и терминала ESP32-S3, формирует срез телеметрии, сравнивает Ollama vs DeepSeek и отправляет итоговый отчёт пользователю."""
    nl = chr(10)
    reflection = run_self_reflection()
    telemetry_bundle = (nl + nl).join([
        "=== 1. САМООБУЧЕНИЕ И УРОКИ ===" + nl + reflection,
        "=== 2. АНАЛИТИЧЕСКИЙ ДАШБОРД ===" + nl + get_full_analytics_dashboard(send_to_phone=False),
        "=== 3. ТЕЛЕМЕТРИЯ ПК И БАТАРЕЯ ===" + nl + get_pc_telemetry() + nl + check_laptop_power_eco(),
        "=== 4. КОНТУР ГАРАНТИРОВАННОГО ПИТАНИЯ ИТ-СБГЭ ===" + nl + get_it_sbge_status(),
        "=== 5. DOCKER-КОНТЕЙНЕРЫ ===" + nl + manage_docker("ps"),
        "=== 6. ЖИВОЙ ЛОГ ПЛАТЫ ESP32-S3 (COM6) ===" + nl + read_esp32_live_logs(80),
        "=== 7. ЖУРНАЛ ДЕЙСТВИЙ ДЖОННИ ===" + nl + get_johnny_audit_log(25),
        "=== 8. УМНЫЙ ДОМ (HOME ASSISTANT) ===" + nl + ha_list_devices()
    ])
    write_workspace_file("live_telemetry_snapshot.txt", telemetry_bundle)

    goal = (
        "Ты — строгий технический эксперт проекта XiaoZhi-PC (v4.1). На основе свежего среза из 8 контуров "
        "сделай глубокий технический аудит состояния сервера XiaoZhi-PC и терминала ESP32-S3: "
        "1) стабильность памяти SRAM/PSRAM и беспроводной связи; "
        "2) работоспособность Docker-сервисов, OTA (:8090), Silero TTS (:8010) и Ollama (:11434); "
        "3) безопасность (DPAPI Vault, RedLineGuard) и интеграции с Home Assistant; "
        "4) конкретные приоритетные шаги модернизации для версии v4.2."
    )
    cmp_res = compare_ai_brains(goal, send_to_phone=False)
    deep_res = delegate_deep_task(goal, output_filename="full_system_audit_v41.md", send_to_phone=send_to_phone)
    res = f"Полный системный аудит завершён.{nl}- Срез 8 контуров: workspace/live_telemetry_snapshot.txt{nl}- {cmp_res}{nl}- {deep_res}"
    _log_event("run_full_system_audit", {"send_to_phone": send_to_phone}, res)
    return res


@mcp.tool()
def speak_johnny_voice(text: str, speaker: str = "eugene") -> str:
    """Озвучивает текст фирменным локальным голосом Silero TTS v4_ru (eugene/aidar) через динамики ПК с резервом на Windows SAPI."""
    clean_txt = text.strip()
    if not clean_txt:
        return "Пустой текст для озвучки."
    try:
        import io, sounddevice as sd, scipy.io.wavfile as wavfile
        resp = requests.post(
            "http://localhost:8010/tts",
            json={"text": clean_txt, "speaker": speaker, "sample_rate": 24000},
            timeout=15
        )
        if resp.ok and resp.content:
            sr, data = wavfile.read(io.BytesIO(resp.content))
            sd.play(data, sr)
            sd.wait()
            res = f"Озвучено голосом Silero ({speaker}): {clean_txt[:60]}"
            _log_event("speak_johnny_voice", {"speaker": speaker, "len": len(clean_txt)}, res)
            return res
    except Exception as e:
        _log_event("speak_johnny_voice_fallback", {"err": str(e)}, "Переход на SAPI")
    res = _speak_offline_windows_sapi(clean_txt)
    _log_event("speak_johnny_voice", {"speaker": "sapi_fallback"}, res)
    return res


def _speak_offline_windows_sapi(text: str) -> str:
    clean_txt = text.replace('"', ' ').replace("'", " ").replace("`", " ").strip()
    ps_tts = f'Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Rate = 1; $s.Speak("{clean_txt}");'
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps_tts], capture_output=True, text=True, timeout=30)
    return "Озвучено локальным голосовым синтезатором ПК." if r.returncode == 0 else f"Ошибка SAPI: {r.stderr.strip()}"

if __name__ == "__main__":
    mcp.run(transport="stdio")




