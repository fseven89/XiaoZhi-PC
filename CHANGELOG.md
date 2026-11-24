# История изменений проекта XiaoZhi-PC (v0.1 - v3.99.9)
**Автор:** Курчицикий М.С (`fseven89`)

## 1. Ранние этапы (v0.1 - v2.x)
### Хронологическая история создания проекта XiaoZhi-PC: от распаковки платы ESP32-S3 до интеграции умного дома и подготовки прошивки

---

#### **2026-11-21: Начало пути — распаковка и первые шаги**
Проект начался с распаковки умной колонки XiaoZhi AI на базе платы ESP32-S3 N16R8. Устройство было подключено к ПК через порт COM6, и сразу же был создан полный бэкап заводской прошивки (`firmware-backup/factory_16mb_backup.bin`). Это стало первым шагом к созданию энграммы Джонни Сильверхенда — голосового ИИ-ассистента с уникальной архитектурой.

В этот же день был создан **первый коммит** в Git, включающий базовый функционал: MCP-мост (`mcp_pipe.py`) и контроллер ПК (`pc_agent.py`). Эти инструменты стали основой для дальнейшего развития проекта. Также была добавлена документация в `README.md`, где описан паспорт проекта и его цели.

---

#### **2026-11-21: Интеграция Docker и умного дома**
Вечером того же дня проект получил мощный импульс благодаря интеграции Docker и умного дома. Были добавлены:
- **Docker-контейнеры**: `xiaozhi-docker-sandbox` для изоляции процессов и `xiaozhi-homeassistant` для управления умным домом.
- **Home Assistant**: Подключены устройства через eWeLink (Sonoff), MiHome (Xiaomi Miot) и SmartLife (Tuya). В частности, был добавлен пылесос Mi Robot Vacuum-Mop P.
- **Три режима работы**: combat (боевой), companion (компаньон) и entertainment (развлечение).

Также была реализована связь со смартфоном Poco F7 через ntfy.sh для отправки скриншотов и файлов без использования VPN.

---

#### **2026-11-22: Безопасность, аудит и автоматизация**
Утро следующего дня было посвящено улучшению безопасности и автоматизации:
- **Аудит-лог**: Добавлен файл `logs/johnny_audit.jsonl` для записи всех действий системы.
- **Автобэкапы**: Реализована функция автоматического создания резервных копий (`backups/`).
- **Фильтры безопасности**: Внедрены механизмы блокировки потенциально опасных команд, таких как доступ к `.env` или выполнение неавторизованных PowerShell-скриптов.

---

## 2. Полная хронология коммитов Git (v1.0 - v3.99.9)
- `ef54171` (2026-11-21): Initial commit: XiaoZhi MCP bridge and PC controller
- `5ffe657` (2026-11-21): Docs: add project passport in README.md
- `f03277e` (2026-11-21): Feat: add Docker sandbox, Home Assistant, 3 modes and phone bridges
- `6171079` (2026-11-22): Feat v2.0: add audit logging, auto-backups, ESP32 serial diagnostics and vacuum support
- `c6ffe5b` (2026-11-22): Feat v3.0: add workspace file tools, ntfy bridge, security filters and HA vacuum
- `7509eba` (2026-11-22): Release v3.0: secure workspace tools, ntfy phone bridge, audit logs and HA vacuum
- `d6e358c` (2026-11-22): Feat v3.5: add AI sub-agents, web search, PC voice TTS, emergency tools and firmware builder
- `cc5f90c` (2026-11-22): Docs & Feat: add ARCHITECTURE.md and developer tools
- `f5c56fc` (2026-11-22): Release v3.8: add Ollama llama3.1 offline agent, deep task delegation, dev tools and docs
- `b4d688a` (2026-11-22): Security v3.9: add automatic secret redaction in audit logs and final docs
- `12e1162` (2026-11-22): Feat v3.95: add full AI decision telemetry log and Ollama vs Cloud comparator
- `b337627` (2026-11-22): Feat v3.95: add johnny-local Ollama model, AI decision telemetry and comparator
- `349d4c0` (2026-11-24): Fix v3.96: clean UTF-8 responses and stabilize background bridge
- `c339a23` (2026-11-24): Feat v3.97: unified audit logging for all tools, 24/7 ESP32 serial logger and full mode access
- `66f867e` (2026-11-24): Release v3.99: add bridge watchdog, 24/7 ESP32 serial logger, unified audit and pytest suite
- `83c35a6` (2026-11-24): Test v3.99.1: all 4 unit tests passing and clean mode switching
- `7d4dd84` (2026-11-24): Fix v3.99.2: clean security policy message, 4/4 tests passing
- `7eae578` (2026-11-24): Test v3.99.4: 4/4 unit tests passing
- `3d258e0` (2026-11-24): Fix v3.99.5: enforce single-instance mutex in bridge_watchdog
- `0edd69c` (2026-11-24): Legal & Safety v3.99.6: add MIT License (M.S. Kurchitskiy / fseven89) and strict anti-hallucination guardrails
- `cf8b963` (2026-11-24): Feat v3.99.7: implement IT-SBGE cascade failover (Input 1 -> Input 2 AVR -> UPS Buffer -> Local Generator Ollama)
- `44ceee0` (2026-11-24): Fix v3.99.8: clean IT-SBGE f-string and choices index
- `7cd7f04` (2026-11-24): Feat v3.99.9: add dormant Cloud VPS failover sentinel & heartbeat hook
