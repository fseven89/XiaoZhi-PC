# Архитектура системы: «XiaoZhi-PC: Энграмма Джонни Сильверхенда»

## 1. Общая схема взаимодействия (Диаграмма потоков)

``text
[ ГОЛОСОВОЙ ТЕРМИНАЛ ]                   [ ОБЛАКО XIAOZHI.ME ]
  Колонка XiaoZhi AI  <--- WebSocket --->  Маршрутизация ИИ и речи
  (ESP32-S3, COM6)                         (Роль Джонни: 3 режима)
         │                                           │
         │ (USB Serial: логи и прошивка)             │ (WSS MCP Endpoint)
         ▼                                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    ХОСТ-МАШИНА: WINDOWS (C:\XiaoZhi-PC)              │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  ФОНОВЫЙ МОСТ: mcp_pipe.py <---> pc_agent.py (31 инструмент)   │  │
│  │  (Автозапуск через Планировщик задач: pythonw.exe)             │  │
│  └────┬──────────────────┬──────────────────┬──────────────────┬──┘  │
│       │                  │                  │                  │     │
│       ▼                  ▼                  ▼                  ▼     │
│  [БЕЗОПАСНОСТЬ]     [РАЗРАБОТКА]       [МУЛЬТИАГЕНТЫ]    [СИСТЕМА ПК]│
│  • Фильтр команд    • VS Code (goto)   • Gemini 2.5 Pro   • Браузер  │
│  • Аудит-лог JSONL  • Чтение кода      • Веб-поиск DDGS   • Буфер    │
│  • ZIP-бэкапы       • Git Auto-Sync    • Озвучка ПК       • Сеть/Сон │
└───────┼──────────────────┼──────────────────┼──────────────────┼─────┘
        │                  │                  │                  │
        ▼                  ▼                  ▼                  ▼
┌───────────────────────────────┐  ┌───────────────────┐  ┌────────────┐
│     DOCKER DESKTOP (WSL2)     │  │   СМАРТФОН И ЧАСЫ │  │  УМНЫЙ ДОМ │
│                               │  │                   │  │  (Локально)│
│ • xiaozhi-homeassistant:8123  │  │ • Poco F7 (ntfy)  │  │ • eWeLink  │
│ • xiaozhi-docker-sandbox      │  │   Скриншоты/Файлы │  │ • MiHome   │
│ • xiaozhi-idf-builder (ESP32) │  │ • Mi Band 10      │  │ • Tuya     │
│ • xiaozhi-vpn-proxy (пауза)   │  │   (Вебхуки HA)    │  │ • Пылесос  │
└───────────────────────────────┘  └───────────────────┘  └────────────┘
``

## 2. Структура файлов и директорий (C:\XiaoZhi-PC)

``text
C:\XiaoZhi-PC\
├── .env                    # [СЕКРЕТЫ] Токены API, HA_TOKEN, PHONE_NTFY_TOPIC (защищен NTFS + .gitignore)
├── .env.example            # Шаблон переменных окружения для GitHub
├── .gitignore              # Жесткий фильтр исключения секретов, логов, бэкапов и SDK
├── ARCHITECTURE.md         # Архитектурная схема и сводка инструментов
├── README.md               # Документация проекта (выгружается на GitHub: fseven89/XiaoZhi-PC)
├── Dockerfile              # Образ изолированной Python-песочницы
├── docker-compose.yml      # Оркестрация контейнеров (sandbox, homeassistant, vpn, firmware)
├── mcp_pipe.py             # Сетевой мост WebSocket <-> Stdio к облаку xiaozhi.me
├── pc_agent.py             # Ядро системы: 31 MCP-инструмент, аудит, бэкапы и субагенты
├── state.json              # Текущее состояние (активный режим: combat / companion / entertainment)
│
├── workspace\              # [ЛОКАЛЬНО] Рабочая папка для скриптов, игр и заметок (notes.md)
├── logs\                   # [ЛОКАЛЬНО] Журнал действий (johnny_audit.jsonl) и логи платы (COM6)
├── backups\                # [ЛОКАЛЬНО] Автоматические ZIP-снимки перед выполнением команд (20 шт.)
├── ha-config\              # [ЛОКАЛЬНО] База и интеграции Home Assistant (Sonoff, Xiaomi, Tuya)
├── vpn-config\             # [ЛОКАЛЬНО] Конфигурация шлюза sing-box (профиль vpn)
├── firmware-backup\        # [ЛОКАЛЬНО] Заводской 16-МБ дамп колонки (factory_16mb_backup.bin)
└── xiaozhi-esp32\          # [ЛОКАЛЬНО] Исходный код прошивки ESP32-S3 для кастомизации
``

## 3. Сводка 31 инструмента Джонни по категориям

1. **Режимы и Безопасность (4):** switch_assistant_mode, get_johnny_audit_log, create_manual_backup, ollback_last_backup.
2. **Разработка и Git (6):** ead_project_file, write_workspace_file, launch_workspace_script, open_in_vscode, scode_open_file, git_sync_project.
3. **Docker и Прошивка ESP32 (4):** manage_docker, docker_exec_sandbox, docker_build_firmware, capture_esp32_logs.
4. **ИИ-субагенты и Поиск (3):** sk_coder_pro (Gemini 2.5 Pro), web_search_info (DDGS), search_workspace_docs.
5. **Умный дом Home Assistant (2):** ha_list_devices, ha_control_device (гараж, аквариум Mijia, робот-пылесос).
6. **Смартфон Poco F7 (2):** phone_send_ntfy (текст и скриншоты), phone_send_document (файлы).
7. **Управление ПК и Аварийный пульт (11):** un_safe_powershell, get_pc_telemetry, open_website, clipboard_manager, scan_local_network, pc_power_control, emote_access_control (AnyDesk/RustDesk), system_self_heal, pc_get_weather, manage_notes, speak_johnny_pc.
