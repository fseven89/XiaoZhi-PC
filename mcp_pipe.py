import asyncio
import logging
import os
import sys
import websockets
from dotenv import load_dotenv

# Настройка логирования для контроля подключения
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("XiaoZhi-MCP-Pipe")

# Загружаем переменные из .env
load_dotenv(r"C:\XiaoZhi-PC\.env")

async def pipe_stdin_to_ws(proc, ws):
    """Читает ответы от локального MCP-сервера (pc_agent.py) и отправляет в XiaoZhi."""
    try:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            message = line.decode("utf-8", errors="replace").strip()
            if message:
                await ws.send(message)
    except Exception as e:
        logger.error(f"Ошибка отправки в WebSocket: {e}")

async def pipe_ws_to_stdout(proc, ws):
    """Принимает команды от XiaoZhi и передает их в локальный MCP-сервер."""
    try:
        async for message in ws:
            if isinstance(message, bytes):
                message = message.decode("utf-8", errors="replace")
            proc.stdin.write((message + "\n").encode("utf-8"))
            await proc.stdin.drain()
    except websockets.exceptions.ConnectionClosed:
        logger.warning("Соединение с сервером XiaoZhi закрыто.")
    except Exception as e:
        logger.error(f"Ошибка приема из WebSocket: {e}")

async def run_bridge(target_script: str):
    """Запускает дочерний MCP-скрипт и держит постоянный туннель с автопереподключением."""
    endpoint = os.getenv("XIAOZHI_MCP_ENDPOINT", "").strip()
    if not endpoint.startswith("wss://"):
        logger.error("Неверный формат XIAOZHI_MCP_ENDPOINT в файле .env! Должен начинаться с wss://")
        return

    while True:
        proc = None
        try:
            logger.info("Подключение к облаку XiaoZhi...")
            async with websockets.connect(endpoint, ping_interval=20, ping_timeout=20) as ws:
                logger.info("[OK] Успешно подключено к XiaoZhi! Ожидание голосовых команд...")
                
                # Запускаем pc_agent.py через текущий интерпретатор Python из venv
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, target_script,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=sys.stderr
                )

                # Запускаем двусторонний обмен данными
                await asyncio.gather(
                    pipe_stdin_to_ws(proc, ws),
                    pipe_ws_to_stdout(proc, ws)
                )
        except Exception as e:
            logger.error(f"Сбой соединения: {e}. Повтор через 5 секунд...")
        finally:
            if proc and proc.returncode is None:
                proc.terminate()
                await proc.wait()
        
        await asyncio.sleep(5)

if __name__ == "__main__":
    script = sys.argv[1] if len(sys.argv) > 1 else "pc_agent.py"
    try:
        asyncio.run(run_bridge(script))
    except KeyboardInterrupt:
        logger.info("Мост остановлен пользователем.")
