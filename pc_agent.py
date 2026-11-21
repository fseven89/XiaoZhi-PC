import os
import subprocess
from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

# Загружаем переменные окружения из .env
load_dotenv(r"C:\XiaoZhi-PC\.env")

# Инициализируем MCP-сервер для управления ноутбуком
mcp = MCPServer("Lenovo-PC-Assistant")

@mcp.tool()
def run_powershell(command: str) -> str:
    """Выполняет команду PowerShell на компьютере пользователя (проверка системы, управление Docker, запуск скриптов)."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            encoding="cp866",
            timeout=30
        )
        output = result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
        return output if output else "Команда выполнена успешно (без текстового вывода)."
    except Exception as e:
        return f"Ошибка выполнения команды: {str(e)}"

@mcp.tool()
def manage_docker(action: str, container_name: str = "") -> str:
    """Управляет Docker на ПК. action: 'ps' (список), 'start' (запуск), 'stop' (остановка), 'logs' (логи)."""
    cmd_map = {
        "ps": "docker ps -a --format 'table {{.Names}}\t{{.Status}}'",
        "start": f"docker start {container_name}",
        "stop": f"docker stop {container_name}",
        "logs": f"docker logs --tail 20 {container_name}"
    }
    if action not in cmd_map:
        return "Неизвестное действие. Доступны: ps, start, stop, logs."
    return run_powershell(cmd_map[action])

@mcp.tool()
def open_in_vscode(target_path: str = r"C:\XiaoZhi-PC") -> str:
    """Открывает указанную папку или файл в редакторе VS Code."""
    subprocess.Popen(["code", target_path], shell=True)
    return f"Открыто в VS Code: {target_path}"

if __name__ == "__main__":
    mcp.run(transport="stdio")


def get_system_info():
    
    