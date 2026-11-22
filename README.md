# XiaoZhi-PC: Голосовой ИИ-ассистент «Джонни Сильверхенд» (v2.0)

## Реализованный функционал
* **Устройство:** Умная колонка XiaoZhi AI (ESP32-S3 N16R8), порт диагностики COM6.
* **Безопасный хост-агент (pc_agent.py + mcp_pipe.py):**
  * Фоновый автозапуск через Планировщик задач Windows (XiaoZhi-MCP-Bridge).
  * Переключение 3 режимов (combat, companion, entertainment).
  * **Аудит и отказоустойчивость:** запись всех вызовов в logs/johnny_audit.jsonl, автоматический ZIP-бэкап перед командами PowerShell (ackups/) и откат (ollback_last_backup).
  * **Диагностика железа:** снятие системных логов ESP32-S3 по USB (capture_esp32_logs).
* **Умный дом (Home Assistant в Docker, порт 8123):**
  * Подключены устройства **eWeLink (Sonoff LAN)**, **MiHome (Xiaomi Miot / Xiaomi Home)**, **SmartLife (Tuya)**, включая аквариум Mijia, реле в гараже и робот-пылесос **Mi Robot Vacuum-Mop P**.
* **Docker-контур:** Изолированная песочница xiaozhi-docker-sandbox (с пробросом logs в режиме read-only), xiaozhi-homeassistant и профиль pn (xiaozhi-vpn-proxy).

## Следующие шаги (v3.0)
1. Интеграция сценариев для **Mi Band 10** (управление устройствами с браслета через вебхуки / Bluetooth).
2. Сборка кастомной прошивки ESP32-S3 (ESP-IDF): локальная активация на имя «Джонни» (Custom Wake Word) и интерфейс HUD Cyberpunk 2077.
