# XiaoZhi-PC: Энграмма «Джонни Сильверхенда» (v3.8)

## Архитектура и реализованные модули
* **Устройство:** Умная колонка XiaoZhi AI (ESP32-S3 N16R8, OEM COOLKIT_XZ_02, дисплей 1.54" ST7789 240x240, порт COM6). Заводской 16-МБ бэкап сохранён в irmware-backup/factory_16mb_backup.bin.
* **Гибридный ИИ-контур (33+ MCP-инструмента в pc_agent.py):**
  * **Голосовой шлюз (mcp_pipe.py):** 3 режима работы (combat, companion, entertainment), аудит-лог (logs/johnny_audit.jsonl), авто-бэкапы (ackups/).
  * **Глубокий аналитик (delegate_deep_task) и кодер (sk_coder_pro):** делегирование сложных отчётов и разработки через ProxyAPI (deepseek/deepseek-chat / openai/gpt-4o-mini).
  * **Локальный офлайн-мозг (sk_local_ollama):** автономная модель llama3.1:8b на GPU/CPU ноутбука (ответ за ~2.2 сек без интернета).
  * **Инструменты разработчика и ПК:** чтение кода, управление VS Code (--goto), изолированный запуск в Docker-песочнице, фоновая сборка прошивки, веб-поиск (ddgs), браузер, буфер обмена, сканер сети и аварийный пульт (RustDesk + system_self_heal).
* **Связь со смартфоном (Poco F7):** отправка скриншотов и готовых документов без VPN через 
tfy.sh.
* **Умный дом (Home Assistant, порт 8123):** eWeLink (Sonoff), MiHome (Xiaomi Miot + Xiaomi Home), SmartLife (Tuya) — гараж, аквариум Mijia и робот-пылесос **Mi Robot Vacuum-Mop P**.

## Следующий этап (v4.0 — Финал)
1. Проработка живого нейросетевого голоса Джонни (Silero TTS / клонирование тембра Ильи Бледного из Cyberpunk 2077).
2. Конфигурация платы (xingzhi-cube-1.54tft-wifi / 1.54tft-wifi) в xiaozhi-esp32 (слово активации «Джонни» + палитра Cyberpunk 2077) и сборка в Docker (xiaozhi-idf-builder).


## Авторские права и лицензия
* **Автор проекта:** Курчицикий М.С (`fseven89`)
* **Лицензия:** MIT License (см. файл `LICENSE`). Все права на архитектуру, скрипты и кастомные модули принадлежат автору.
