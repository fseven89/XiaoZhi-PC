# XiaoZhi-PC: Энграмма «Джонни Сильверхенда» (v3.99.9)
**Автор:** Курчицикий М.С (\seven89\) | **Лицензия:** MIT (\LICENSE\)

## Реализованная архитектура (v3.99.9)
* **Устройство:** XiaoZhi AI (ESP32-S3 N16R8, \COOLKIT_XZ_02\, 1.54" ST7789 240x240, \COM6\). Дамп: \irmware-backup/factory_16mb_backup.bin\.
* **ИТ-СБГЭ (\ailover_power_grid.py\):** Каскад \Ввод 1 (DeepSeek) -> АВР -> Ввод 2 (GPT-4o-mini) -> ИБП (буфер задач) -> ДГУ (Ollama johnny-local)\.
* **Отказоустойчивость (\ridge_watchdog.py\ + \esp32_serial_logger.py\):** Защита мьютексом, 24/7 лог \COM6\, трёхуровневый аудит в \logs/\, авто-цензор секретов и запрет на выдумки ИИ.
* **Облачный задел (\cloud_sentinel.py\):** Готовый Docker-контур для будущей VPS 24/7 (\CLOUD_DEPLOY.md\).
* **Интеграции:** Home Assistant (порт \8123\), связь с Poco F7 без VPN (\
tfy.sh\), автотесты \pytest\.

Подробная летопись с \0.1\ — в файле \CHANGELOG.md\. Следующий шаг — **Этап v4.0 (прошивка ESP32-S3 и живой голос)**.