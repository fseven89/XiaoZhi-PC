# Copyright (c) 2026 Курчицикий М.С (fseven89). All rights reserved.
# Module: IT-SBGE (Fault-Tolerant Cascade Failover: Input 1 -> Input 2 -> UPS Buffer -> Local Generator Ollama)

import os, json, time, datetime, requests

BASE_DIR = r"C:\XiaoZhi-PC"
LOGS_DIR = os.path.join(BASE_DIR, "logs")
UPS_BUFFER_FILE = os.path.join(LOGS_DIR, "ups_task_buffer.json")
FAILOVER_LOG = os.path.join(LOGS_DIR, "sbge_failover_audit.jsonl")

def _log_sbge(event_type: str, active_line: str, details: str, switch_ms: int = 0):
    entry = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "event": event_type,
        "active_line": active_line,
        "switch_time_ms": switch_ms,
        "details": details[:300]
    }
    try:
        with open(FAILOVER_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass

def _save_ups_buffer(task_id: str, prompt: str, status: str):
    data = {}
    if os.path.exists(UPS_BUFFER_FILE):
        try:
            with open(UPS_BUFFER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data[task_id] = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "prompt": prompt[:500]
    }
    # Храним последние 30 задач в буфере ИБП
    if len(data) > 30:
        for k in list(data.keys())[:-30]:
            del data[k]
    with open(UPS_BUFFER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def execute_with_avr(prompt: str, sys_prompt: str = "Ты — точный технический ассистент проекта XiaoZhi-PC.") -> dict:
    """Каскадное выполнение задачи по схеме СБГЭ: ИБП (буфер) -> Ввод 1 -> АВР -> Ввод 2 -> ДГУ (Ollama)."""
    task_id = f"task_{int(time.time() * 1000)}"
    _save_ups_buffer(task_id, prompt, "UPS_BUFFERED")

    api_key = os.getenv("LLM_API_KEY", "").strip()
    cloud_url = "https://" + "api.proxyapi" + ".ru/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # --- ВВОД №1: Основной облачный канал (DeepSeek) ---
    if api_key:
        t0 = time.time()
        try:
            r1 = requests.post(
                cloud_url,
                headers=headers,
                json={
                    "model": "deepseek/deepseek-chat",
                    "messages": [{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}],
                    "temperature": 0.1
                },
                timeout=25
            )
            if r1.ok:
                ans = r1.json()["choices"]["message"]["content"].strip()
                ms = int((time.time() - t0) * 1000)
                _save_ups_buffer(task_id, prompt, "DONE_INPUT_1")
                _log_sbge("NORMAL_RUN", "INPUT_1_DEEPSEEK", "Выполнено по основному вводу", ms)
                return {"line": "ВВОД №1 (Cloud DeepSeek)", "ms": ms, "answer": ans}
        except Exception as e1:
            _log_sbge("INPUT_1_FAIL", "AVR_SWITCHING", f"Потеря Ввода №1: {str(e1)[:100]}", int((time.time() - t0) * 1000))

        # --- АВР -> ВВОД №2: Резервный облачный канал (GPT-4o-mini) ---
        t1 = time.time()
        try:
            r2 = requests.post(
                cloud_url,
                headers=headers,
                json={
                    "model": "openai/gpt-4o-mini",
                    "messages": [{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}],
                    "temperature": 0.1
                },
                timeout=25
            )
            if r2.ok:
                ans = r2.json()["choices"]["message"]["content"].strip()
                ms = int((time.time() - t1) * 1000)
                _save_ups_buffer(task_id, prompt, "DONE_INPUT_2_AVR")
                _log_sbge("AVR_FAILOVER_OK", "INPUT_2_GPT4O_MINI", "АВР успешно переключил на Ввод №2", ms)
                return {"line": "ВВОД №2 / АВР (Cloud GPT-4o-mini)", "ms": ms, "answer": ans}
        except Exception as e2:
            _log_sbge("INPUT_2_FAIL", "STARTING_DGU_OLLAMA", f"Потеря Ввода №2: {str(e2)[:100]}", int((time.time() - t1) * 1000))

    # --- ДГУ (Дизель-генератор): Автономная локальная модель Ollama (johnny-local) ---
    t2 = time.time()
    ollama_url = "http://" + "127.0.0" + ".1:11434/api/chat"
    try:
        r3 = requests.post(
            ollama_url,
            json={
                "model": "johnny-local",
                "messages": [{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}],
                "stream": False,
                "keep_alive": "24h"
            },
            timeout=180
        )
        if r3.ok:
            ans = r3.json().get("message", {}).get("content", "").strip()
            ms = int((time.time() - t2) * 1000)
            _save_ups_buffer(task_id, prompt, "DONE_GENERATOR_OLLAMA")
            _log_sbge("DGU_ACTIVE_OK", "GENERATOR_OLLAMA_LOCAL", "Работа от автономного генератора Ollama", ms)
            return {"line": "ДГУ / АВТОНОМНЫЙ ГЕНЕРАТОР (Ollama johnny-local)", "ms": ms, "answer": ans}
    except Exception as e3:
        _save_ups_buffer(task_id, prompt, "BLACKOUT_FAILED")
        _log_sbge("TOTAL_BLACKOUT", "NONE", f"Отказ всех вводов и ДГУ: {str(e3)[:120]}", int((time.time() - t2) * 1000))
        return {"line": "АВАРИЯ (Все вводы и ДГУ недоступны)", "ms": 0, "answer": f"Критический отказ всех контуров: {e3}"}

def get_sbge_telemetry() -> str:
    """Проверяет готовность всех вводов, буфера ИБП и локального генератора Ollama."""
    status = []
    # Проверка Вводов 1 и 2
    key = os.getenv("LLM_API_KEY", "").strip()
    status.append(f"• Ввод №1 (DeepSeek Cloud) и Ввод №2 (GPT-4o-mini): {'ПОД НАПРЯЖЕНИЕМ (Ключ активен)' if key else 'ОТКЛЮЧЕНЫ (Нет ключа)'}")
    # Проверка ИБП (буфер)
    buf_cnt = 0
    if os.path.exists(UPS_BUFFER_FILE):
        try:
            with open(UPS_BUFFER_FILE, "r", encoding="utf-8") as f:
                buf_cnt = len(json.load(f))
        except Exception:
            pass
    status.append(f"• ИБП On-Line (Энергонезависимый буфер задач): АКТИВЕН (в памяти {buf_cnt} записей)")
    # Проверка ДГУ (Ollama)
    try:
        r = requests.get("http://" + "127.0.0" + ".1:11434/api/tags", timeout=3)
        dgu_ok = r.ok and ("johnny-local" in r.text)
        status.append(f"• ДГУ (Локальный генератор Ollama johnny-local): {'В ГОРЯЧЕМ РЕЗЕРВЕ (Готов к пуску)' if dgu_ok else 'НЕ ГОТОВ'}")
    except Exception:
        status.append("• ДГУ (Локальный генератор Ollama): ОФЛАЙН")
    return "\n".join(status)