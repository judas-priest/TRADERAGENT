# Historical Data for Backtesting

Этот каталог содержит исторические OHLCV данные для backtesting стратегий.

## 📁 Структура данных

Файлы сохранены в формате CSV с следующей структурой:

```
{exchange}_{symbol}_{timeframe}.csv
```

**Примеры:**
- `binance_ETH_USDT_1d.csv` - Binance, ETH/USDT, дневные свечи
- `bybit_ETH_USDT_4h.csv` - Bybit, ETH/USDT, 4-часовые свечи

## 📊 Формат CSV

Каждый файл содержит следующие колонки:

| Колонка | Тип | Описание |
|---------|-----|----------|
| timestamp | int | Unix timestamp в миллисекундах |
| datetime | str | ISO 8601 дата и время |
| open | float | Цена открытия |
| high | float | Максимальная цена |
| low | float | Минимальная цена |
| close | float | Цена закрытия |
| volume | float | Объем торгов |

**Пример:**
```csv
timestamp,datetime,open,high,low,close,volume
1704067200000,2024-01-01T00:00:00,2267.89,2275.50,2265.12,2271.34,12345.67
```

## 🔄 Загрузка данных

### Использование скрипта

Скрипт `scripts/download_historical_data.py` позволяет загружать данные с бирж:

```bash
# Загрузить все данные (обе биржи, все timeframes) для ETH/USDT
python scripts/download_historical_data.py --all

# Загрузить данные только с Binance
python scripts/download_historical_data.py --exchange binance --symbol ETH/USDT

# Загрузить конкретные timeframes
python scripts/download_historical_data.py --exchange bybit --timeframes 1d,4h

# Указать период данных
python scripts/download_historical_data.py --start-date 2023-01-01 --end-date 2024-01-01

# Справка по параметрам
python scripts/download_historical_data.py --help
```

### Параметры скрипта

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `--symbol` | Торговая пара | ETH/USDT |
| `--exchange` | Биржа (binance/bybit/all) | all |
| `--timeframes` | Список timeframes | 1d,4h,1h,15m,5m |
| `--start-date` | Начальная дата (YYYY-MM-DD) | 6 месяцев назад |
| `--end-date` | Конечная дата (YYYY-MM-DD) | Сегодня |
| `--output-dir` | Директория для сохранения | data/historical |
| `--all` | Загрузить всё | - |

## 📚 Использование в backtesting

### Python пример

```python
import pandas as pd
from pathlib import Path

# Загрузить данные
data_file = Path("data/historical/binance_ETH_USDT_1h.csv")
df = pd.read_csv(data_file)

# Конвертировать timestamp в datetime
df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
df.set_index('datetime', inplace=True)

# Использовать для backtesting
print(f"Loaded {len(df)} candles")
print(f"Period: {df.index[0]} to {df.index[-1]}")
print(df.head())
```

### Интеграция с HistoricalDataProvider

```python
from bot.tests.backtesting.test_data import HistoricalDataProvider

provider = HistoricalDataProvider()

# Загрузить CSV данные
candles = provider.load_csv_data("data/historical/binance_ETH_USDT_1h.csv")

# Использовать в backtesting
for candle in candles:
    print(f"{candle['timestamp']}: {candle['close']}")
```

## 🎯 Доступные данные

После выполнения `python scripts/download_historical_data.py --all` будут доступны следующие файлы:

### Binance
- `binance_ETH_USDT_1d.csv` - дневные свечи
- `binance_ETH_USDT_4h.csv` - 4-часовые свечи
- `binance_ETH_USDT_1h.csv` - часовые свечи
- `binance_ETH_USDT_15m.csv` - 15-минутные свечи
- `binance_ETH_USDT_5m.csv` - 5-минутные свечи

### Bybit
- `bybit_ETH_USDT_1d.csv` - дневные свечи
- `bybit_ETH_USDT_4h.csv` - 4-часовые свечи
- `bybit_ETH_USDT_1h.csv` - часовые свечи
- `bybit_ETH_USDT_15m.csv` - 15-минутные свечи
- `bybit_ETH_USDT_5m.csv` - 5-минутные свечи

## ⚠️ Важные замечания

1. **Размер файлов**: Файлы с мелкими timeframes (5m, 15m) могут быть большими (несколько MB)
2. **Rate Limiting**: Скрипт соблюдает rate limits бирж для предотвращения блокировки
3. **Обновление данных**: Для обновления запустите скрипт снова - новые данные добавятся
4. **Git**: Файлы `.csv` добавлены в `.gitignore` - не коммитятся в репозиторий

## 🔧 Устранение проблем

### Ошибка "Exchange error"
- Проверьте доступность биржи
- Убедитесь что торговая пара существует
- Попробуйте указать меньший период данных

### Ошибка "Network error"
- Проверьте интернет-соединение
- Попробуйте позже (возможны временные проблемы на бирже)

### Пустые данные
- Некоторые биржи имеют ограничения на исторические данные
- Попробуйте указать более поздний start-date

## 📝 Ссылки

- [CCXT Documentation](https://docs.ccxt.com/)
- [Binance API](https://binance-docs.github.io/apidocs/)
- [Bybit API](https://bybit-exchange.github.io/docs/)
