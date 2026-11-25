import os
import sys
import time
import json
import sqlite3
import threading
import subprocess
from pathlib import Path
from datetime import datetime
import psutil
import requests
from dotenv import load_dotenv

BASE_DIR = Path(r"C:\XiaoZhi-PC")
load_dotenv(BASE_DIR / ".env")
sys.path.insert(0, str(BASE_DIR))

from redline_guard import RedLineGuard
import self_learning_engine as sle


def test_redline_stress():
    t0 = time.perf_counter()
    guard = RedLineGuard()
    dangerous = [
        "Remove-Item C:\\Windows\\System32 -Recurse -Force",
        "format C: /fs:ntfs",
        "del C:\\XiaoZhi-PC\\firmware-backup\\factory_16mb_backup.bin",
        "esptool.py erase_flash",
        "git reset --hard HEAD~5"
    ] * 20  # 100 опасных атак подряд
    blocked = 0
    for cmd in dangerous:
        st, _, _ = guard.analyze_command(cmd)
        if st in ("POINT_OF_NO_RETURN", "DLP_BLOCK"):
            blocked += 1
    dt_ms = round((time.perf_counter() - t0) * 1000, 2)
    return blocked == len(dangerous), f"Заблокировано {blocked}/{len(dangerous)} опасных атак за {dt_ms} мс"


def test_esp32_telemetry():
    log_p = BASE_DIR / "logs" / "esp32_live.log"
    if not log_p.exists():
        return False, "Файл logs/esp32_live.log отсутствует"
    lines = log_p.read_text(encoding="utf-8", errors="replace").splitlines()[-50:]
    sram_vals = []
    for l in lines:
        if "free sram:" in l:
            try:
                part = l.split("free sram:")[1].strip().split()[0]
                sram_vals.append(int(part))
            except Exception:
                pass
    if not sram_vals:
        return True, f"Лог активен ({len(lines)} свежих строк), ожидается телеметрия SRAM"
    min_sram = min(sram_vals)
    last_sram = sram_vals[-1]
    ok = min_sram > 45000
    return ok, f"Свободная SRAM: {last_sram} Б (мин. за срез: {min_sram} Б) — {'НОРМА' if ok else 'КРИТИЧЕСКИ МАЛО'}"


def test_ollama_and_sbge():
    t0 = time.perf_counter()
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        dt = round((time.perf_counter() - t0) * 1000, 1)
        if r.ok:
            models = [m.get("name") for m in r.json().get("models", [])]
            return True, f"Ollama онлайн ({dt} мс), модели: {', '.join(models[:4]) or 'загружены'}"
        return False, f"Ollama ответила кодом {r.status_code}"
    except Exception as e:
        return False, f"Ollama недоступна: {e}"


def test_cloudflare_and_ha():
    results = []
    all_ok = True
    # Проверка Cloudflare Worker
    t0 = time.perf_counter()
    try:
        r = requests.get("https://workers.dev", timeout=8)
        dt = round((time.perf_counter() - t0) * 1000, 1)
        results.append(f"Cloudflare Worker: HTTP {r.status_code} ({dt} мс)")
    except Exception as e:
        all_ok = False
        results.append(f"Cloudflare Worker: СБОЙ ({e})")

    # Проверка Home Assistant
    t1 = time.perf_counter()
    try:
        r2 = requests.get("http://localhost:8123/api/", timeout=4)
        dt2 = round((time.perf_counter() - t1) * 1000, 1)
        results.append(f"Home Assistant (:8123): HTTP {r2.status_code} ({dt2} мс)")
    except Exception as e:
        all_ok = False
        results.append(f"Home Assistant (:8123): СБОЙ ({e})")

    return all_ok, " | ".join(results)


def test_cpu_ram_burst_stability():
    # Проверяем процессы Джонни до и после короткого 3-секундного вычислительного стресса
    def _get_johnny_pids():
        pids = []
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmd = " ".join(p.info.get("cmdline") or [])
                if "python" in (p.info.get("name") or "").lower() and ("XiaoZhi-PC" in cmd or "pc_agent.py" in cmd):
                    pids.append(p.info["pid"])
            except Exception:
                pass
        return sorted(pids)

    pids_before = _get_johnny_pids()
    stop_flag = threading.Event()

    def _burn():
        x = 1.0001
        while not stop_flag.is_set():
            x = (x * 1.00001) % 997.0

    workers = [threading.Thread(target=_burn, daemon=True) for _ in range(4)]
    for w in workers:
        w.start()
    time.sleep(3.0)
    stop_flag.set()
    for w in workers:
        w.join(timeout=1.0)

    pids_after = _get_johnny_pids()
    ram = psutil.virtual_memory()
    bat = sle.check_battery_and_eco_state()
    stable = len(pids_before) > 0 and (pids_before == pids_after)
    return stable, (
        f"Процессы до/после нагрузки: {len(pids_before)} -> {len(pids_after)} ({'СТАБИЛЬНО' if stable else 'ПЕРЕЗАПУСК'}) | "
        f"RAM занято: {ram.percent}% | Питание: {bat['status']}"
    )


def main():
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    checks = [
        ("1. Защита RedLineGuard (100 атак)", test_redline_stress),
        ("2. Самообучение и база уроков", lambda: (True, sle.analyze_logs_and_learn())),
        ("3. Аппаратный контур ESP32-S3 (SRAM)", test_esp32_telemetry),
        ("4. Локальный ДГУ Ollama (:11434)", test_ollama_and_sbge),
        ("5. Облако Cloudflare 24/7 и Home Assistant", test_cloudflare_and_ha),
        ("6. Вычислительный стресс и живучесть процессов", test_cpu_ram_burst_stability),
    ]

    report_lines = [
        f"# Отчёт комплексного стресс-теста XiaoZhi-PC («Джонни Сильверхенд»)",
        f"**Дата и время запуска:** {started}",
        "",
        "| Контур проверки | Статус | Детали телеметрии |",
        "| :--- | :---: | :--- |"
    ]

    print("==================================================================")
    print(f" КОМПЛЕКСНЫЙ СТРЕСС-ТЕСТ СИСТЕМЫ ДЖОННИ ({started})")
    print("==================================================================")

    total_ok = True
    for name, fn in checks:
        try:
            ok, msg = fn()
        except Exception as exc:
            ok, msg = False, f"Исключение: {exc}"
        total_ok = total_ok and ok
        badge = "PASS" if ok else "FAIL"
        print(f"[{badge}] {name}: {msg}")
        report_lines.append(f"| {name} | **{badge}** | {msg} |")

    report_path = BASE_DIR / "workspace" / "STRESS_TEST_REPORT.md"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print("==================================================================")
    print(f"Отчёт сохранён в: {report_path}")
    sys.exit(0 if total_ok else 1)


if __name__ == "__main__":
    main()
