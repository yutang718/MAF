# syntax=docker/dockerfile:1
# Single image: React frontend (built) + FastAPI backend serving both API and static files.

# ---------- Stage 1: build frontend ----------
FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY frontend-react/package.json frontend-react/package-lock.json ./
RUN npm ci
COPY frontend-react/ ./
RUN npm run build

# ---------- Stage 2: backend runtime ----------
FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY app/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install torch --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple && \
    pip install -r requirements.txt && \
    python -m spacy download en_core_web_sm

COPY app/ .

# Frontend build output served by FastAPI (see main.py)
COPY --from=frontend-build /frontend/dist /app/static

RUN mkdir -p logs config/pii config/islamic model_cache

ENV HF_HOME=/app/model_cache \
    STATIC_DIR=/app/static

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
