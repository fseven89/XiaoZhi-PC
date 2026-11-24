# Copyright (c) 2026 Курчицикий М.С (fseven89). All rights reserved.
# Module: System Telemetry & AI/Hardware Analytics Dashboard

import os, json, re, shutil, datetime
from collections import Counter

BASE_DIR = r"C:\XiaoZhi-PC"
LOGS_DIR = os.path.join(BASE_DIR, "logs")

def build_analytics_report() -> str:
    lines = [f"=== СВОДНАЯ АНАЛИТИКА И МОНИТОРИНГ XIAOZHI-PC ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}) ==="]

    # 1. Анализ вызовов инструментов (johnny_audit.jsonl)
    audit_p = os.path.join(LOGS_DIR, "johnny_audit.jsonl")
    if os.path.exists(audit_p):
        tools = Counter()
        errors = 0
        total_calls = 0
        with open(audit_p, "r", encoding="utf-8", errors="replace") as f:
            for row in f:
                try:
                    d = json.loads(row)
                    total_calls += 1
                    t_name = d.get("tool", "unknown")
                    tools[t_name] += 1
                    if "_ERROR" in t_name or "ошибка" in str(d.get("result", "")).lower():
                        errors += 1
                except Exception:
                    pass
        top_str = ", ".join([f"{k} ({v})" for k, v in tools.most_common(5)])
        lines.append(f"\n[1. Активность агента]: Всего вызовов: {total_calls} | Ошибок: {errors}")
        lines.append(f"   Топ инструментов: {top_str}")

    # 2. Аналитика ИТ-СБГЭ и ИИ-моделей (sbge_failover_audit.jsonl + ai_decisions_audit.jsonl)
    sbge_p = os.path.join(LOGS_DIR, "sbge_failover_audit.jsonl")
    ai_p = os.path.join(LOGS_DIR, "ai_decisions_audit.jsonl")
    engines = Counter()
    durations = []
    if os.path.exists(ai_p):
        with open(ai_p, "r", encoding="utf-8", errors="replace") as f:
            for row in f:
                try:
                    d = json.loads(row)
                    engines[d.get("model", "unknown")] += 1
                    if d.get("duration_sec"):
                        durations.append(float(d["duration_sec"]))
                except Exception:
                    pass
    avr_switches = 0
    if os.path.exists(sbge_p):
        with open(sbge_p, "r", encoding="utf-8", errors="replace") as f:
            for row in f:
                if "AVR_FAILOVER" in row or "DGU_ACTIVE" in row:
                    avr_switches += 1
    avg_dt = round(sum(durations) / len(durations), 2) if durations else 0
    lines.append(f"\n[2. ИТ-СБГЭ и Нейросети]: Переключений АВР/ДГУ: {avr_switches} | Среднее время ответа ИИ: {avg_dt} сек.")
    if engines:
        lines.append(f"   Нагрузка по моделям: {dict(engines)}")

    # 3. Здоровье платы ESP32-S3 (esp32_live.log)
    esp_p = os.path.join(LOGS_DIR, "esp32_live.log")
    if os.path.exists(esp_p):
        sram_vals = []
        bat_levels = []
        wifi_drops = 0
        with open(esp_p, "r", encoding="utf-8", errors="replace") as f:
            for row in f.readlines()[-1000:]:
                m_sram = re.search(r"minimal sram:\s*(\d+)", row)
                if m_sram:
                    sram_vals.append(int(m_sram.group(1)))
                m_bat = re.search(r"level:\s*(\d+)", row)
                if m_bat:
                    bat_levels.append(int(m_bat.group(1)))
                if "disconnect" in row.lower() or "wifi_err" in row.lower():
                    wifi_drops += 1
        min_sram = min(sram_vals) if sram_vals else "н/д"
        last_bat = bat_levels[-1] if bat_levels else "н/д"
        lines.append(f"\n[3. Телеметрия платы ESP32-S3]: Мин. свободная SRAM: {min_sram} байт | Заряд АКБ: {last_bat}% | Сбоев Wi-Fi: {wifi_drops}")

    # 4. Ресурсы диска и бэкапы
    total, used, free = shutil.disk_usage("C:\\")
    free_gb = round(free / (1024**3), 1)
    backups_cnt = len(os.listdir(os.path.join(BASE_DIR, "backups"))) if os.path.exists(os.path.join(BASE_DIR, "backups")) else 0
    lines.append(f"\n[4. Хост и страховка]: Свободно на диске C: {free_gb} ГБ | ZIP-бэкапов в архиве: {backups_cnt}")

    return "\n".join(lines)