# Multi-stage Dockerfile for grid backtesting service
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir --prefix=/install .


FROM python:3.12-slim

WORKDIR /app

# Copy installed packages
COPY --from=builder /install /usr/local

# Copy source
COPY src/ src/

# Create data and logs directories
RUN mkdir -p data logs

# Non-root user
RUN useradd -m -r backtester && chown -R backtester:backtester /app
USER backtester

# Environment defaults
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO
ENV HOST=0.0.0.0
ENV PORT=8100
ENV DATA_DIR=data
ENV LOG_DIR=logs

EXPOSE 8100

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8100/health')" || exit 1

CMD ["uvicorn", "grid_backtester.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8100"]
