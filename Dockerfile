FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MEHR_HTTP_HOST=0.0.0.0 \
    MEHR_HTTP_PORT=8000 \
    MEHR_DB_PATH=/data/mehr_ai_studio.sqlite3

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir . \
    && useradd --system --uid 10001 --home-dir /app mehr \
    && mkdir -p /data \
    && chown -R 10001:10001 /app /data

USER 10001:10001
EXPOSE 8000
VOLUME ["/data"]

CMD ["mehr-ai-studio-http"]
