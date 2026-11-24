# Архитектура проекта XiaoZhi-PC («Энграмма Джонни Сильверхенда»)
**Версия:** 4.0-rc5 (Программная и облачная база ПК завершена) -> 4.0 (Прошивка ESP32-S3 и Голос)
**Автор:** Курчицикий М.С (fseven89) | **Лицензия:** MIT (LICENSE)

## 1. Общая топология системы (Гибридная СБГЭ 24/7)
* **Аппаратный терминал:** XiaoZhi AI (ESP32-S3 N16R8, COOLKIT_XZ_02, 1.54 ST7789, Simplex, COM6 -> logs/esp32_live.log).
* **Бесплатный облачный узел (Cloudflare 24/7):** Worker blue-pond-f7d4.justmiker.workers.dev + KV (SBGE_KV) + Cron (1 мин) — приём пульса /sbge-heartbeat, тревоги в ntfy.sh при потере связи >2 мин и HTTPS-шлюз без VPN для Telegram Bot API.
* **Двусторонний шлюз и Vision AI (ntfy_inbox_listener.py + vision_inbox.py):** Приём фото/файлов со смартфона Poco F7 через ntfy (..._in), Telegram (@Xiaohzi_PC_bridge_bot) и локальный Wi-Fi (:8787) с мультимодальным разбором.
* **Домашний вычислительный узел (C:\XiaoZhi-PC):** bridge_watchdog.py (Single-Instance Mutex), mcp_pipe.py, pc_agent.py (37+ MCP-инструментов), ИТ-СБГЭ (failover_power_grid.py: DeepSeek -> АВР -> GPT-4o-mini -> ИБП буфер -> ДГУ Ollama johnny-local), аналитика (system_analytics.py).
* **Контейнеры Docker (WSL2):** xiaozhi-homeassistant (:8123), xiaozhi-docker-sandbox, xiaozhi-idf-builder (ESP-IDF v5.3) и спящий задел под VPS (CLOUD_DEPLOY.md).

## 2. Дорожная карта на Этап v4.0+
* **[v4.0 — Прошивка ESP32-S3]:** Сборка под плату xingzhi-cube-1.54tft-wifi, слово активации «Джонни» (ESP-SR), палитра LVGL Cyberpunk 2077, встроенная C++ подсистема JohnnySubsystem (BLE-радар Mi Band 10 / Poco F7, управление экраном, прямые вебхуки).
* **[v4.0 — Живой голос]:** Офлайн-движок Silero TTS и клонирование голоса Ильи Бледного (FishSpeech / F5-TTS).
* **[v4.1 — Инфраструктура]:** Cloudflare Tunnel (cloudflared), ротация ключей .env, аппаратный Mini-UPS 12V/5V.
