# Multi-stage Dockerfile for TRADERAGENT Bot

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app

# Copy Python dependencies from builder
COPY --from=builder --chown=botuser:botuser /root/.local /home/botuser/.local

# Copy application code
COPY --chown=botuser:botuser bot/ ./bot/
COPY --chown=botuser:botuser alembic/ ./alembic/
COPY --chown=botuser:botuser alembic.ini.example ./alembic.ini
COPY --chown=botuser:botuser configs/ ./configs/

# Switch to non-root user
USER botuser

# Add local bin to PATH
ENV PATH=/home/botuser/.local/bin:$PATH

# Set Python path
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import asyncio; from bot.database.manager import DatabaseManager; \
    asyncio.run(DatabaseManager('${DATABASE_URL}').health_check())" || exit 1

# Default command (can be overridden)
CMD ["python", "-m", "bot.main"]
