FROM python:3.12-slim

WORKDIR /app

# yt-dlp benefits from ca-certificates; keep image small
RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates curl \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY Procfile runtime.txt ./

RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/app/data/cache.db \
    PORT=8000

EXPOSE 8000

# Render injects $PORT — bind all interfaces for the platform proxy
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
