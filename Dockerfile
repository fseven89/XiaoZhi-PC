FROM python:3.12-slim

# Создаем непривилегированного пользователя для безопасности
RUN useradd -m -u 1000 appuser
WORKDIR /app

RUN pip install --no-cache-dir websockets python-dotenv mcp requests

USER appuser
CMD ["python", "-c", "import time; print('XiaoZhi Docker Sandbox активен и защищен'); time.sleep(31536000)"]
