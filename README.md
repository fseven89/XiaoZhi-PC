# XiaoZhi-PC: Голосовой ИИ-ассистент «Джонни Сильверхенд» + Управление ПК и Умным домом

## Архитектура и текущий статус
* **Устройство:** Умная колонка XiaoZhi AI (ESP32-S3 N16R8), привязанная к облачной консоли xiaozhi.me.
* **Хост-агент (Windows):** Фоновая задача Планировщика (XiaoZhi-MCP-Bridge через pythonw.exe). Скрипт pc_agent.py обеспечивает переключение 3 режимов (combat, companion, entertainment), безопасный PowerShell, телеметрию ПК, управление Docker, погоду, заметки, медиа и 3 канала связи со смартфоном.
* **Docker Desktop:** Запущены изолированная песочница xiaozhi-docker-sandbox, сервер умного дома xiaozhi-homeassistant (порт 8123) и подготовлен профиль pn (xiaozhi-vpn-proxy).
* **IDE:** VS Code (Continue) настроен на Gemini 2.5 Flash/Pro и автодополнение DeepSeek через ProxyAPI.

## Следующие шаги
1. Настроить аккаунт и интеграции SmartLife / eWeLink в Home Assistant (http://localhost:8123), вписать HA_TOKEN в .env.
2. Собрать кастомную прошивку ESP32-S3 (ESP-IDF): активация на слово «Джонни» и интерфейс HUD Cyberpunk 2077.
