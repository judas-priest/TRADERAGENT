# Historical OHLCV Data — Справка

## Источник данных

**HuggingFace Dataset:** [linxy/CryptoCoin](https://huggingface.co/datasets/linxy/CryptoCoin)
**Данные Binance**, лицензия MIT

## Расположение на сервере

```
/home/hive/btc/data/historical/
```

**Общий объём:** 5.4 GB (450 CSV файлов)
**Дата скачивания:** 2026-02-14

## Доступные пары (45)

| # | Пара | # | Пара | # | Пара |
|---|------|---|------|---|------|
| 1 | 1INCHUSDT | 16 | ETCUSDT | 31 | RUNEUSDT |
| 2 | AAVEUSDT | 17 | ETHUSDT | 32 | SANDUSDT |
| 3 | ADAUSDT | 18 | FILUSDT | 33 | SHIBUSDT |
| 4 | ALGOUSDT | 19 | FTMUSDT | 34 | SNXUSDT |
| 5 | AVAXUSDT | 20 | FTTUSDT | 35 | SOLUSDT |
| 6 | BATUSDT | 21 | HBARUSDT | 36 | SUSHIUSDT |
| 7 | BCHUSDT | 22 | HNTUSDT | 37 | TRXUSDT |
| 8 | BNBUSDT | 23 | ICPUSDT | 38 | UNIUSDT |
| 9 | BTCUSDT | 24 | KSMUSDT | 39 | WAVESUSDT |
| 10 | CHZUSDT | 25 | LDOUSDT | 40 | XEMUSDT |
| 11 | COMPUSDT | 26 | LINKUSDT | 41 | XLMUSDT |
| 12 | CRVUSDT | 27 | LTCUSDT | 42 | XRPUSDT |
| 13 | DOGEUSDT | 28 | LUNAUSDT | 43 | YFIUSDT |
| 14 | DOTUSDT | 29 | MANAUSDT | 44 | ZILUSDT |
| 15 | EOSUSDT | 30 | MATICUSDT | 45 | ZRXUSDT |

## Доступные таймфреймы (10)

| Таймфрейм | Описание | Примерный размер файла |
|-----------|----------|------------------------|
| 5m | 5 минут | 40-116 MB |
| 15m | 15 минут | 15-40 MB |
| 30m | 30 минут | 8-20 MB |
| 1h | 1 час | 4-11 MB |
| 2h | 2 часа | 2-5 MB |
| 4h | 4 часа | 1-3 MB |
| 6h | 6 часов | 700K-2 MB |
| 8h | 8 часов | 500K-1.3 MB |
| 12h | 12 часов | 350K-900K |
| 1d | 1 день | 150K-420K |

**Недоступные таймфреймы:** 1m, 3m (отсутствуют в датасете)
**Недоступные пары:** MNTUSDT (отсутствует в датасете)

## Период данных

**С:** Август 2017
**По:** Февраль 2026
**Длительность:** ~8.5 лет

## Формат CSV

```
Open time,open,high,low,close,volume,Close time,Quote asset volume,Number of trades,Taker buy base asset volume,Taker buy quote asset volume,Ignore
2017-08-17 04:00:00,301.13,302.57,298.0,301.61,125.66877,2017-08-17 04:59:59.999,37684.804181,129,80.56377,24193.440789,0
```

**Колонки:**
1. `Open time` — время открытия свечи
2. `open` — цена открытия
3. `high` — максимальная цена
4. `low` — минимальная цена
5. `close` — цена закрытия
6. `volume` — объём в базовом активе
7. `Close time` — время закрытия свечи
8. `Quote asset volume` — объём в котировочном активе (USDT)
9. `Number of trades` — количество сделок
10. `Taker buy base asset volume` — объём покупок тейкеров (базовый)
11. `Taker buy quote asset volume` — объём покупок тейкеров (USDT)
12. `Ignore` — не используется

## Именование файлов

```
{PAIR}_{TIMEFRAME}.csv
```

Примеры:
- `BTCUSDT_1h.csv` — Bitcoin/USDT, часовые свечи
- `ETHUSDT_15m.csv` — Ethereum/USDT, 15-минутные свечи
- `SOLUSDT_1d.csv` — Solana/USDT, дневные свечи

## Как скачать заново

```bash
# Скачать один файл
curl -L -o data/historical/ETHUSDT_1h.csv \
  "https://huggingface.co/datasets/linxy/CryptoCoin/resolve/main/ETHUSDT_1h.csv"

# Скачать все файлы для одной пары
for TF in 5m 15m 30m 1h 2h 4h 6h 8h 12h 1d; do
  curl -sL -o "data/historical/ETHUSDT_${TF}.csv" \
    "https://huggingface.co/datasets/linxy/CryptoCoin/resolve/main/ETHUSDT_${TF}.csv" &
done
wait

# Скачать весь датасет (45 пар × 10 таймфреймов)
ALL_PAIRS="1INCHUSDT AAVEUSDT ADAUSDT ALGOUSDT AVAXUSDT BATUSDT BCHUSDT BNBUSDT BTCUSDT CHZUSDT COMPUSDT CRVUSDT DOGEUSDT DOTUSDT EOSUSDT ETCUSDT ETHUSDT FILUSDT FTMUSDT FTTUSDT HBARUSDT HNTUSDT ICPUSDT KSMUSDT LDOUSDT LINKUSDT LTCUSDT LUNAUSDT MANAUSDT MATICUSDT RUNEUSDT SANDUSDT SHIBUSDT SNXUSDT SOLUSDT SUSHIUSDT TRXUSDT UNIUSDT WAVESUSDT XEMUSDT XLMUSDT XRPUSDT YFIUSDT ZILUSDT ZRXUSDT"
for PAIR in $ALL_PAIRS; do
  for TF in 5m 15m 30m 1h 2h 4h 6h 8h 12h 1d; do
    curl -sL -o "data/historical/${PAIR}_${TF}.csv" \
      "https://huggingface.co/datasets/linxy/CryptoCoin/resolve/main/${PAIR}_${TF}.csv" &
  done
  wait  # ждём каждую пару, чтобы не перегрузить
done

# Через Python (datasets library)
pip install datasets
from datasets import load_dataset
dataset = load_dataset("linxy/CryptoCoin", data_files=["ETHUSDT_1h.csv"], split="train")
```

## Использование с бэктестингом

Данные совместимы с модулем бэктестинга (`backtesting-module/`).
Для интеграции потребуется адаптер, поскольку формат колонок отличается от текущего `CSVDataLoader`.
