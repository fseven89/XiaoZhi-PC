# XiaoZhi-PC: Голосовой ИИ-ассистент «Джонни Сильверхенд» (v3.5)

## Реализованный функционал
* **Устройство:** Умная колонка XiaoZhi AI (ESP32-S3 N16R8, OEM COOLKIT_XZ_02, дисплей 1.54" ST7789 240x240, порт COM6). Снят полный заводской бэкап irmware-backup/factory_16mb_backup.bin.
* **Фоновый MCP-мост (pc_agent.py + mcp_pipe.py):** 27+ инструментов с фильтром безопасности, автобэкапами (ackups/), аудит-логом (logs/johnny_audit.jsonl), переключением 3 режимов (combat, companion, entertainment), суб-агентом программистом (sk_coder_pro на Gemini 2.5 Pro), веб-поиском (web_search_info), управлением сайтами/буфером/сетью ПК, озвучкой через динамики ПК (speak_johnny_pc) и аварийным пультом (emote_access_control, system_self_heal).
* **Связь со смартфоном (Poco F7):** Отправка скриншотов и файлов без VPN через 
tfy.sh.
* **Умный дом (Home Assistant в Docker, порт 8123):** Подключены **eWeLink (Sonoff)**, **MiHome (Xiaomi Miot + Xiaomi Home)**, **SmartLife (Tuya)** — реле гаража, аквариум Mijia и пылесос **Mi Robot Vacuum-Mop P**.
* **Docker-контур:** xiaozhi-docker-sandbox, xiaozhi-homeassistant, профиль pn и профиль irmware (espressif/idf:release-v5.3). Ограничение памяти WSL2 зафиксировано в .wslconfig.

## Следующий этап (v4.0 — Сборка прошивки ESP32-S3)
1. Конфигурация платы (xingzhi-cube-1.54tft-wifi / 1.54tft-wifi) в xiaozhi-esp32 с активацией на имя «Джонни» (Custom Wake Word) и темой HUD Cyberpunk 2077.
2. Сборка прошивки в Docker (xiaozhi-idf-builder) и заливка на COM6.
3. Развертывание локального сервера с клонированием голоса Ильи Бледного (FishSpeech / RVC).
