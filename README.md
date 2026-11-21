# XiaoZhi-PC: Голосовой ИИ-ассистент XiaoZhi + Управление ПК (Windows)

## 1. Архитектура и окружение
* **Устройство:** Умная колонка **XiaoZhi AI** (ESP32-S3 N16R8, дисплей 1.54"), привязанная к облачной консоли xiaozhi.me.
* **ПК (Хост):** Windows, Python 3.15.2, Docker Desktop, VS Code, Git.
* **Сеть и API (РФ, без VPN):** ProxyAPI (https://proxyapi.ru для Gemini 2.5 Flash/Pro и /openai/v1 для DeepSeek), резервный прямой DeepSeek API.

## 2. Структура проекта
* .env — локальное хранилище ключей и токенов (исключено из Git).
* .env.example — безопасный шаблон переменных окружения.
* mcp_pipe.py — асинхронный WebSocket-мост между локальным stdio MCP-сервером и облаком xiaozhi.me.
* pc_agent.py — локальный MCP-сервер (mcp 2.x), предоставляющий колонке инструменты:
  1. un_powershell(command) — выполнение команд PowerShell.
  2. manage_docker(action, container_name) — управление контейнерами Docker.
  3. open_in_vscode(target_path) — открытие файлов и папок в VS Code.

## 3. Автоматизация
* Настроена фоновая задача XiaoZhi-MCP-Bridge в Планировщике задач Windows (запуск через pythonw.exe без окна консоли при входе в систему).
* Настроено расширение **Continue** в VS Code на работу с Gemini 2.5 и автодополнение DeepSeek.
