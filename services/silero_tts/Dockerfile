FROM python:3.11-slim
WORKDIR /app
ENV P="https:"
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir torch --index-url "${P}//download.pytorch.org/whl/cpu" && \
    pip install --no-cache-dir fastapi uvicorn numpy scipy omegaconf
RUN mkdir -p /app/models && \
    curl -L "${P}//models.silero.ai/models/tts/ru/v4_ru.pt" -o /app/models/v4_ru.pt
COPY server.py /app/server.py
EXPOSE 8010
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8010"]