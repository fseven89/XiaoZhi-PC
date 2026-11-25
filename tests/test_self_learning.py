import json
import self_learning_engine as sle


def test_self_learning_extracts_lessons(tmp_path, monkeypatch):
    fake_audit = tmp_path / "audit.jsonl"
    fake_lessons = tmp_path / "lessons.json"
    monkeypatch.setattr(sle, "LESSONS_FILE", fake_lessons)

    entries = [
        {"tool": "run_safe_powershell", "result": "Ошибка: [WinError 5] Отказано в доступе"},
        {"tool": "ntfy_listener", "result": "Read timed out after 15s"},
        {"tool": "get_pc_telemetry", "result": "CPU: 12%"}
    ]
    fake_audit.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in entries), encoding="utf-8")

    summary = sle.analyze_logs_and_learn(audit_path=fake_audit)
    assert "Цикл самообучения" in summary
    text = sle.format_lessons_summary()
    assert "WinError 5" in text or "timed out" in text


def test_battery_check_returns_valid_dict():
    st = sle.check_battery_and_eco_state(threshold_percent=20)
    assert "percent" in st
    assert "eco_triggered" in st
    assert isinstance(st["status"], str)
