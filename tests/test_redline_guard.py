import pytest
from redline_guard import RedLineGuard


def test_safe_command_allowed():
    guard = RedLineGuard()
    status, _, code = guard.analyze_command("Get-Process | Select-Object -First 5")
    assert status == "ALLOW"
    assert code is None


def test_destructive_windows_command_blocked():
    guard = RedLineGuard()
    status, reason, code = guard.analyze_command("Remove-Item C:\\Windows\\System32 -Recurse -Force")
    assert status == "POINT_OF_NO_RETURN"
    assert code is not None and len(code) == 4
    assert "Windows" in reason or "удаление" in reason.lower()


def test_project_backup_deletion_blocked():
    guard = RedLineGuard()
    status, _, code = guard.analyze_command("del C:\\XiaoZhi-PC\\firmware-backup\\factory_16mb_backup.bin")
    assert status == "POINT_OF_NO_RETURN"
    assert guard.verify_confirmation("0000") is None
    assert guard.verify_confirmation(code) == "del C:\\XiaoZhi-PC\\firmware-backup\\factory_16mb_backup.bin"


def test_secret_leak_blocked():
    guard = RedLineGuard()
    ok, msg = guard.analyze_outbound_text("Вот мой ключ: ghp_1234567890abcdef1234567890abcdef1234")
    assert ok is False
    assert "GitHub" in msg


def test_format_table_not_blocked_as_disk_format():
    guard = RedLineGuard()
    st, _, _ = guard.analyze_command("Get-ChildItem C:\\XiaoZhi-PC | Format-Table -AutoSize")
    assert st == "ALLOW"
