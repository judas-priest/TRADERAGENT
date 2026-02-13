# Исторические Данные

Эта папка содержит исторические данные для бэктестинга.

## Скачивание данных

Для скачивания исторических данных используйте Docker:

```bash
# Из корня backtesting-module
docker build -t historical-data-downloader .
docker run -v $(pwd)/data/historical:/app/data/historical historical-data-downloader
```

Или используйте существующий скрипт из основного репозитория:

```bash
# Из корня TRADERAGENT
python scripts/download_historical_data.py --all --output-dir backtesting-module/data/historical
```

## Структура данных

После скачивания здесь будут CSV файлы в подпапках binance/ и bybit/.

## Формат CSV

Каждый файл содержит OHLCV данные:
timestamp,datetime,open,high,low,close,volume
