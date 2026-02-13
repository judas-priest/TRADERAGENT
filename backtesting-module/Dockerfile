FROM python:3.11-slim

WORKDIR /app

# Install ccxt
RUN pip install --no-cache-dir ccxt

# Copy script
COPY scripts/download_historical_data.py /app/

# Create data directory
RUN mkdir -p /app/data/historical

CMD ["python", "download_historical_data.py", "--all", "--output-dir", "/app/data/historical"]
