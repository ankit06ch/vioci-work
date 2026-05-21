# Vioci FastAPI API — production image (Render, Fly, Railway, etc.)
FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY schemagraph ./schemagraph
COPY server ./server

RUN pip install --no-cache-dir -e ".[web,cloud,google]"

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Render sets PORT; local default 8000
CMD ["sh", "-c", "uvicorn server.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
