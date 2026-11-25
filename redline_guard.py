import re
import time
import secrets
from pathlib import Path
from typing import Tuple, Optional, Dict

# Критические пути Windows и проекта XiaoZhi-PC
CRITICAL_PATHS = [
    r"c:\windows",
    r"c:\program files",
    r"c:\program files (x86)",
    r"c:\programdata",
    r"c:\users\justm\appdata",
    r"c:\xiaozhi-pc\firmware-backup",
    r"c:\xiaozhi-pc\.git",
    r"c:\xiaozhi-pc\.env",
    r"c:\xiaozhi-pc\venv",
    r"c:\xiaozhi-pc\pc_agent.py",
    r"c:\xiaozhi-pc\bridge_watchdog.py",
    r"c:\xiaozhi-pc\restore_factory_fw.ps1",
]

# Паттерны деструктивных команд (Точка невозврата)
DESTRUCTIVE_PATTERNS = [
    (r"(?:\bformat\s+[a-z]:|\bformat-volume\b|\bdiskpart\b|\bbcdedit\b|\bbootrec\b|\bmbr2gpt\b)", "Разрушение разделов диска или загрузчика Windows"),
    (r"\b(rm\s+-rf|rmdir\s+/s|rd\s+/s|del\s+/[fqs]+.*\*|remove-item\b.*-recurse)", "Рекурсивное принудительное удаление файлов"),
    (r"\b(reg\s+delete|remove-itemproperty)\b.*(hklm|system|currentcontrolset|winlogon)", "Удаление критических веток реестра Windows"),
    (r"\b(disable-netadapter|netsh\s+interface\s+set\s+interface.*disable)\b", "Отключение сетевых интерфейсов (потеря удалённого доступа)"),
    (r"\b(stop-service|sc\s+delete)\b.*(winmgmt|rpcss|dhcp|dnscache|mpssvc)", "Остановка или удаление системной службы Windows"),
    (r"\b(git\s+reset\s+--hard|git\s+clean\s+-fd|git\s+push\s+.*--force)\b", "Необратимый сброс или перезапись истории Git"),
    (r"\b(esptool.*erase_flash)\b", "Полная очистка Flash-памяти ESP32-S3"),
]

# Паттерны утечки секретов (DLP)
SECRET_PATTERNS = [
    (r"sk-[a-zA-Z0-9]{20,}", "API-ключ OpenAI / DeepSeek"),
    (r"ghp_[a-zA-Z0-9]{30,}|github_pat_[a-zA-Z0-9_]{30,}", "Персональный токен GitHub"),
    (r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b", "Токен Telegram-бота"),
    (r"-----BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY-----", "Приватный криптографический ключ"),
    (r"(DEEPSEEK_API_KEY|OPENAI_API_KEY|HA_TOKEN|TELEGRAM_BOT_TOKEN)\s*=\s*\S+", "Переменная окружения из .env"),
]


class RedLineGuard:
    """Анализатор точки невозврата и DLP-фильтр для энграммы Джонни."""

    def __init__(self, ttl_seconds: int = 90):
        self.ttl = ttl_seconds
        self._pending: Dict[str, dict] = {}

    def analyze_command(self, command: str) -> Tuple[str, str, Optional[str]]:
        """
        Возвращает кортеж: (status, reason, confirm_code)
        status: 'ALLOW' | 'POINT_OF_NO_RETURN' | 'DLP_BLOCK'
        """
        cmd_lower = command.lower().strip()

        # 1. Проверка на попытку слива секретов наружу
        for pattern, desc in SECRET_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return ("DLP_BLOCK", f"Обнаружена попытка передачи секрета ({desc}). Отправка заблокирована.", None)

        # 2. Проверка деструктивных команд и критических путей
        triggered_reasons = []
        for pattern, desc in DESTRUCTIVE_PATTERNS:
            if re.search(pattern, cmd_lower, re.IGNORECASE):
                triggered_reasons.append(desc)

        for cpath in CRITICAL_PATHS:
            if cpath in cmd_lower and any(w in cmd_lower for w in ["del", "rm", "remove", "erase", "clear", "move", "rename", ">"]):
                triggered_reasons.append(f"Затронут критический системный объект: {cpath}")

        if triggered_reasons:
            code = f"{secrets.randbelow(9000) + 1000}"
            reason_text = "; ".join(dict.fromkeys(triggered_reasons))
            self._pending[code] = {
                "command": command,
                "reason": reason_text,
                "expires_at": time.time() + self.ttl,
            }
            return ("POINT_OF_NO_RETURN", reason_text, code)

        return ("ALLOW", "Действие безопасно", None)

    def analyze_outbound_text(self, text: str) -> Tuple[bool, str]:
        """Проверка любого текста/файла перед отправкой в Telegram, ntfy или интернет."""
        for pattern, desc in SECRET_PATTERNS:
            if re.search(pattern, text):
                return (False, f"DLP-блокировка: в исходящих данных найден {desc}")
        return (True, "OK")

    def verify_confirmation(self, code: str) -> Optional[str]:
        """Подтверждение точки невозврата одноразовым кодом."""
        item = self._pending.pop(code.strip(), None)
        if not item:
            return None
        if time.time() > item["expires_at"]:
            return None
        return item["command"]

