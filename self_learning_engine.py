import json
import datetime
from pathlib import Path
from collections import Counter
from typing import Dict, Any
import psutil

BASE_DIR = Path(r"C:\XiaoZhi-PC")
LOGS_DIR = BASE_DIR / "logs"
WORKSPACE_DIR = BASE_DIR / "workspace"
LESSONS_FILE = WORKSPACE_DIR / "lessons_learned.json"


def _load_lessons() -> Dict[str, Any]:
    if LESSONS_FILE.exists():
        try:
            return json.loads(LESSONS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "updated_at": None,
        "total_cycles": 0,
        "dialog_insights": [],
        "rules": [
            {
                "id": "rule_coreaudio_vol",
                "trigger": "Управление громкостью Windows",
                "lesson": "Не использовать SendKeys или COM MMSysAudio ([WinError 5]). Использовать MCP-инструмент set_system_volume_percent.",
                "hits": 1
            }
        ]
    }


def _save_lessons(data: Dict[str, Any]) -> None:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    LESSONS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def analyze_logs_and_learn(
    audit_path: Path = LOGS_DIR / "johnny_audit.jsonl",
    esp_log_path: Path = LOGS_DIR / "esp32_live.log"
) -> str:
    """Двухконтурное самообучение: анализирует сбои инструментов (audit.jsonl) и живые диалоги (esp32_live.log)."""
    data = _load_lessons()
    data["total_cycles"] = data.get("total_cycles", 0) + 1
    data.setdefault("dialog_insights", [])

    error_patterns = Counter()
    tool_stats = Counter()

    # Контур 1: Аудит вызовов MCP-инструментов
    if audit_path.exists():
        for raw in audit_path.read_text(encoding="utf-8", errors="replace").splitlines()[-350:]:
            try:
                rec = json.loads(raw)
                tool = rec.get("tool", "unknown")
                res = str(rec.get("result", ""))
                tool_stats[tool] += 1
                if any(k in res.lower() for k in ["ошибка", "error", "сбой", "timed out", "winerror", "denied", "blocked", "разрушение"]):
                    sig = f"{tool}: {res[:90]}"
                    error_patterns[sig] += 1
            except Exception:
                continue

    # Контур 2: Анализ живых диалогов и событий речи из esp32_live.log
    user_phrases = []
    abort_count = 0
    if esp_log_path.exists():
        for line in esp_log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-400:]:
            if "Application: >>" in line:
                phrase = line.split("Application: >>", 1)[1].strip()
                if phrase and phrase.lower() != "джонни":
                    user_phrases.append(phrase)
            elif "Application: Abort speaking" in line:
                abort_count += 1

    if abort_count >= 2:
        error_patterns[f"esp32_audio: Частые прерывания речи ({abort_count} раз)"] += abort_count

    existing_triggers = {r["trigger"] for r in data["rules"]}
    new_added = 0

    for sig, count in error_patterns.most_common(12):
        if sig not in existing_triggers:
            advice = "Проверить права доступа, таймаут или параметры вызова перед повтором."
            if "winerror 5" in sig.lower() or "отказано в доступе" in sig.lower():
                advice = "Использовать нативные Python/WinAPI инструменты вместо прямого запуска внешних скриптов."
            elif "timed out" in sig.lower():
                advice = "Увеличить таймаут ожидания или переключить задачу на резервную линию СБГЭ."
            elif "esp32_audio" in sig.lower():
                advice = "Повысить порог Wake Word до 0.48 и отключить DETECTION_IN_LISTENING."
            elif "blocked" in sig.lower() or "точка невозврата" in sig.lower():
                advice = "Запросить подтверждение пользователя по 4-значному коду перед опасным действием."

            data["rules"].append({
                "id": f"auto_{len(data['rules']) + 1}",
                "trigger": sig,
                "lesson": advice,
                "hits": count
            })
            existing_triggers.add(sig)
            new_added += 1

    if user_phrases:
        recent_topics = list(dict.fromkeys(user_phrases[-8:]))
        data["dialog_insights"] = recent_topics

    data["rules"] = data["rules"][-30:]
    _save_lessons(data)

    top_tools = ", ".join(f"{k}({v})" for k, v in tool_stats.most_common(5)) or "нет данных"
    return (
        f"Цикл самообучения v2.0 #{data['total_cycles']} завершён. "
        f"Новых правил: {new_added} (всего: {len(data['rules'])}), "
        f"проанализировано реплик диалога: {len(user_phrases)} (прерываний речи: {abort_count}). "
        f"Топ инструментов: {top_tools}."
    )


def format_lessons_summary(limit: int = 8) -> str:
    data = _load_lessons()
    rules = data.get("rules", [])[-limit:]
    lines = [f"Усвоенные уроки Джонни v2.0 (обновлено: {data.get('updated_at') or 'н/д'}):"]
    for r in rules:
        lines.append(f"- [{r['id']}] {r['trigger']} -> {r['lesson']} (повторов: {r.get('hits', 1)})")
    insights = data.get("dialog_insights", [])
    if insights:
        lines.append("\nНедавние темы живых диалогов:")
        for ph in insights[-5:]:
            lines.append(f"  * «{ph}»")
    return "\n".join(lines)


def check_battery_and_eco_state(threshold_percent: int = 25) -> Dict[str, Any]:
    bat = psutil.sensors_battery()
    if bat is None:
        return {"has_battery": False, "plugged": True, "percent": 100, "eco_triggered": False, "status": "Питание от сети (стационарный режим)"}

    eco_needed = (not bat.power_plugged) and (bat.percent <= threshold_percent)
    state_str = "От сети (зарядка)" if bat.power_plugged else f"От аккумулятора ({bat.percent}%)"
    if eco_needed:
        state_str += f" — ВНИМАНИЕ: заряд ниже {threshold_percent}%, активирован режим энергосбережения!"
    return {
        "has_battery": True,
        "plugged": bool(bat.power_plugged),
        "percent": int(bat.percent),
        "eco_triggered": eco_needed,
        "status": state_str
    }
