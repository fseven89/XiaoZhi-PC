# XiaoZhi-PC: Энграмма «Джонни Сильверхенда» (v4.1)

**Автор:** Курчицикий М.С (`fseven89`) | **Лицензия:** MIT (`LICENSE`)

## Актуальная архитектура (v4.1)

- **Аппаратная платформа:** XiaoZhi AI (`COOLKIT_XZ_02`, ESP32-S3 N16R8, дисплей ST7789 240×240, UART `COM6`). Резервный заводской дамп: `firmware-backup/factory_16mb_backup.bin`.
- **Интерфейс прошивки (`Relic HUD v4.1`):** кастомный оверлей `lv_layer_top()` и палитра Cyberpunk 2077 (`#0A0508`, `#FF2A3C`, `#FCEE09`, `#08232C`), волновой спектроанализатор голоса и динамический статус чипа (`RELIC // SYNC`, `RELIC // SCAN`, `JOHNNY // LIVE`). Свободная внутренняя SRAM: **~150.8 КБ**.
- **Локальный живой голос (`Silero TTS v4_ru`):** автономный Docker-микросервис `xiaozhi-silero-tts` (`127.0.0.1:8010`, голос `eugene`/`aidar`), подключённый через MCP-инструмент `speak_johnny_voice` с резервом на Windows SAPI.
- **ИТ-СБГЭ (`failover_power_grid.py`):** каскад гарантированного выполнения задач `Ввод 1 (DeepSeek) -> АВР -> Ввод 2 (GPT-4o-mini) -> ИБП (буфер) -> ДГУ (локальная Ollama johnny-local на :11434)`.
- **Отказоустойчивость и OTA 24/7 (`bridge_watchdog.py`):** защита мьютексом, автоподъём Ollama и Silero TTS, непрерывный лог `COM6` (`esp32_serial_logger.py`), постоянный локальный HTTP-сервер беспроводной прошивки (`0.0.0.0:8090` -> `logs/ota_server.log`).
- **Безопасность (`dpapi_vault.py` + `redline_guard.py`):** шифрование секретов в `vault.dpapi` через нативный **Windows DPAPI (`CurrentUser`)**, DLP-цензор исходящего трафика и подтверждение критических команд по коду.
- **Интеграции:** Home Assistant (`127.0.0.1:8123`, управление светом и сброс расходников Viomi V7), двусторонняя связь и Vision Inbox со смартфоном Poco F7 через `ntfy.sh` (`RFC-2047`), облачный мониторинг Cloudflare Worker + KV (`cloud_sentinel.py`), автотесты `pytest`.

Подробная техническая документация: [`ARCHITECTURE.md`](ARCHITECTURE.md) | Паспорт железа: [`HARDWARE_PASSPORT.md`](HARDWARE_PASSPORT.md) | Летопись изменений: [`CHANGELOG.md`](CHANGELOG.md).