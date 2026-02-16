# Multi-stage Dockerfile for TRADERAGENT Web Backend (FastAPI)

# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 webuser && \
    chown -R webuser:webuser /app

COPY --from=builder --chown=webuser:webuser /root/.local /home/webuser/.local

COPY --chown=webuser:webuser bot/ ./bot/
COPY --chown=webuser:webuser web/backend/ ./web/backend/
COPY --chown=webuser:webuser configs/ ./configs/

USER webuser

ENV PATH=/home/webuser/.local/bin:$PATH
ENV PYTHONPATH=/app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

CMD ["uvicorn", "web.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
