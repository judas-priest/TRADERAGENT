# TRADERAGENT — Сравнение архитектур: Live Bot vs Backtesting

> Дата: 2026-02-28
> Подробности: [architecture_bot.md](architecture_bot.md) | [architecture_backtest.md](architecture_backtest.md)

---

## 1. Краткое сравнение

| Аспект                    | Live Bot                              | Backtest                                  |
|---------------------------|---------------------------------------|-------------------------------------------|
| **Цель**                  | Реальная торговля 24/7                | Оценка стратегий на истории               |
| **Время**                 | Реальное (asyncio, 1s цикл)           | Ускоренное (итерация по свечам)           |
| **Источник данных**       | REST API биржи (каждые 5 сек)         | CSV-файлы (Parquet в планах)              |
| **Исполнение ордеров**    | Биржа (реальное / demo)               | MarketSimulator (in-memory)               |
| **Задержка исполнения**   | 1–5 сек (polling latency)             | 0 (мгновенный матчинг)                   |
| **Частичные исполнения**  | Да                                    | Нет (all-or-nothing)                      |
| **Параллелизм**           | asyncio (I/O-bound)                   | ProcessPoolExecutor (CPU-bound)           |
| **Персистентность**       | PostgreSQL (state snapshots)          | SQLite (jobs, presets) + JSON/CSV         |
| **Уведомления**           | Telegram, Redis events, Prometheus    | Нет (только файлы и логи)                |
| **Стратегии**             | Grid, DCA, TF, SMC, Hybrid            | Grid (prod), DCA+TF+SMC (dev)            |
| **Риск-менеджмент**       | Реальный, blocking (стоп бота)        | Симуляция, останавливает цикл             |

---

## 2. Жизненный цикл торгового цикла

### Live Bot (каждые 1 сек)

```
  Ticker API (5s)
       │
       ▼
  Проверить режим рынка (60s)
       │
       ▼
  Для каждой активной стратегии:
    ├─ [Grid] Сверить ордера с биржей
    ├─ [DCA]  Проверить trigger/TP по цене
    ├─ [TF]   fetch_ohlcv(1h) → analyze → signal?
    └─ [SMC]  fetch_ohlcv(4TF) → analyze → signal?
       │
       ▼ (если signal)
  RiskManager.check_trade()
       │
       ▼
  exchange.create_order() ──► БИРЖА (реальная / demo)
       │
       ▼
  Обновить локальное состояние
       │
       ▼
  Redis Pub/Sub → Telegram / Metrics
       │
       ▼
  Мониторинг позиций (TP/SL)
       │
       ▼
  save_state() (30s)
       │
       ▼
  sleep(1)
```

### Backtest (по каждой свече)

```
  CSV → DataFrame
       │
       ▼
  for каждой свечи:
    ├─ Sweep цен внутри свечи [open, low, high, close]
    │     │
    │     ▼
    │  MarketSimulator.set_price(price)
    │     │
    │     ▼
    │  _check_limit_orders()     ← мгновенный матчинг
    │     │
    │     ▼
    │  on_order_filled() → create_counter_order()
    │
    ├─ Рассчитать equity curve
    │
    └─ RiskManager.evaluate_risk()
          │
          ▼
       если STOP: break
       иначе: next candle

  Рассчитать метрики (Sharpe, Calmar, ...)
  → GridBacktestResult
```

---

## 3. Обработка ордеров: ключевые отличия

| Аспект                      | Live Bot                                      | Backtest                                        |
|-----------------------------|-----------------------------------------------|-------------------------------------------------|
| **Где исполняется**         | Bybit / другая биржа (HTTP)                   | MarketSimulator (память)                        |
| **Как определяется fill**   | Polling fetch_open_orders() + сравнение ID    | price crossing limit price (мгновенно)          |
| **Гранулярность цены**      | Одна цена в момент polling                    | 4 цены на свечу (O/L/H/C)                      |
| **Скольжение (slippage)**   | Реальное (market impact, bid-ask spread)      | Нет (идеальное исполнение)                      |
| **Комиссии**                | Реальные (maker/taker из конфига биржи)       | Симулированные (maker_fee, taker_fee)           |
| **Книга ордеров**           | Реальная биржевая                             | Виртуальная (только свои ордера)               |
| **Контр-ордера (grid)**     | Создаются после подтверждения fill с биржи    | Создаются сразу при crossed price               |

---

## 4. Источники данных

### Live Bot

```
exchange.fetch_ticker(symbol)   → текущая цена (каждые 5 сек)
exchange.fetch_ohlcv(TF, limit) → OHLCV для анализа (TF/SMC)
exchange.fetch_balance()        → доступный баланс
exchange.fetch_open_orders()    → для grid reconciliation
```

### Backtest

```
pd.read_csv(data/historical/{symbol}_{tf}.csv)
    → DataFrame [timestamp, open, high, low, close, volume]
    → Опционально: --last-candles N (последние N свечей)
    → Планируется: кэш в Parquet

MultiTimeframeData {m5, m15, h1, h4, d1}
    → разные CSV-файлы для каждого таймфрейма
```

---

## 5. Использование стратегий

### Обе системы используют один и тот же код стратегий

```
Bot/Backtest → BaseStrategy interface
                │
    ┌───────────┼───────────────────────────┐
    ▼           ▼           ▼               ▼
GridEngine  DCAEngine  TrendFollower    SMCStrategy
```

**Важно:** Grid-стратегия в backtest переиспользует:
- `bot/strategies/grid/grid_calculator.py` (через shim)
- `bot/strategies/grid/grid_order_manager.py` (через shim)

Это гарантирует, что бэктест и live-бот используют **идентичную логику расчёта** уровней и управления ордерами.

---

## 6. Риск-менеджмент

| Параметр               | Live Bot                              | Backtest                              |
|------------------------|---------------------------------------|---------------------------------------|
| **max_position_size**  | Блокирует ордер в реальном времени    | Не применяется (нет динамики баланса) |
| **max_daily_loss**     | Реальный, сброс в UTC midnight        | Не применяется                        |
| **stop_loss_pct**      | Portfolio-level (emergency_stop)      | Per-simulation (break loop)           |
| **max_drawdown_pct**   | Часть portfolio stop-loss             | Явная остановка симуляции             |
| **take_profit_pct**    | По каждой стратегии (TP по позиции)   | По всей симуляции (total PnL target)  |
| **Последствие**        | emergency_stop() → бот встаёт        | break → return result с stopped=True  |

---

## 7. Параллелизм

### Live Bot — asyncio (I/O-bound)
```
asyncio.create_task(_main_loop)       ← ждёт ответа биржи
asyncio.create_task(_price_monitor)   ← ждёт HTTP
asyncio.create_task(_regime_monitor)  ← ждёт HTTP + вычисления
asyncio.create_task(health_monitor)   ← проверки
```
- Все задачи в одном event loop (GIL не проблема: 99% времени — ожидание I/O)

### Backtest — ProcessPoolExecutor (CPU-bound)
```
ProcessPoolExecutor(max_workers=14)
    └─ Каждый воркер: независимый процесс, независимый GIL
    └─ _run_single_trial(config_dict, candles_dict) → dict
    └─ as_completed(futures): собираем результаты по мере готовности
```
- Несколько процессов обходят GIL (CPU-intensive математика)
- Checkpoint: resume при падении / перезапуске

---

## 8. Архитектурный долг и расхождения

### Проблема 1: MarketRegimeDetector не подключён в live-боте

```
Live Bot:
  MarketRegimeDetector.detect_market_regime(df) → регулярно вызывается
  MarketRegimeDetector._current_regime            ← НИКОГДА НЕ ЧИТАЕТСЯ
  _main_loop НЕ использует get_strategy_recommendation()

Backtest (multi-strategy):
  MultiTimeframeBacktestEngine.enable_regime_filter = True
  → if strategy_type not in REGIME_ALLOWED[regime]: skip signal  ← РАБОТАЕТ

Следствие: live-бот не адаптируется к рынку, хотя детектор работает.
```

### Проблема 2: Слипаж не моделируется в бэктесте

```
Backtest: цена исполнения = цена в книге ордеров (ideal fill)
Live Bot: цена исполнения ≠ запрошенная (bid-ask spread, market impact)

Следствие: реальные результаты хуже бэктестовых,
особенно для рыночных ордеров и низколиквидных пар.
```

### Проблема 3: Polling vs Price Sweep

```
Live Bot:
  - Проверка ордеров раз в секунду
  - Ордер мог исполниться и вернуться до следующей проверки

Backtest:
  - 4 ценовых точки на свечу (OHLC)
  - Ордера внутри high-low диапазона исполняются детерминированно

Следствие: бэктест может переоценить количество циклов grid
(цена могла "не дойти" до уровня в реальности).
```

### Проблема 4: Различия в SMC конфигурации

```
Live Bot:  конфиг из YAML (swing_length = дефолт бота)
Backtest:  opt-grid тестирует другие диапазоны swing_length

Следствие: SMC в бэктесте показывает negative Sharpe,
но это может быть артефакт конфига, а не самой стратегии.
```

---

## 9. Что нужно синхронизировать (Roadmap)

| Задача                                              | Приоритет |
|-----------------------------------------------------|-----------|
| Подключить MarketRegimeDetector к _main_loop        | HIGH      |
| Добавить slippage model в GridBacktestSimulator     | MEDIUM    |
| Унифицировать SMC параметры (бот ↔ backtest)        | HIGH      |
| Включить enable_regime_filter в backtest pipeline   | MEDIUM    |
| Добавить Bayesian optimization для Phase 2          | HIGH      |
| Скачать 7 недостающих пар (NEAR, APT, PEPE, ...)    | MEDIUM    |
| Кэш индикаторов в Parquet (ускорение optimization)  | MEDIUM    |

---

## 10. Диаграмма общей архитектуры

```
                    TRADERAGENT
                        │
         ┌──────────────┴──────────────┐
         │                             │
    LIVE BOT                     BACKTEST
    bot/main.py              services/backtesting/
         │                    scripts/run_*
         │
    BotOrchestrator
    ├─ _main_loop (1s)
    ├─ _price_monitor (5s)        ┌── GridBacktestSystem
    ├─ _regime_monitor (60s)      ├── GridBacktestSimulator
    └─ health_monitor (30s)       │   ├── MarketSimulator
                                  │   ├── GridOrderManager
    Strategies (shared code)      │   └── GridRiskManager
    ├── GridEngine ──────────────►│── GridOptimizer
    ├── DCAEngine                 ├── CoinClusterizer
    ├── TrendFollower             └── GridBacktestReporter
    └── SMCStrategy
                                  MultiTimeframeBacktestEngine
    Exchange Clients              ├─ DCABacktester
    ├── ByBitDirectClient         ├── ParameterOptimizer
    └── ExchangeAPIClient (CCXT)  ├── StressTester
                                  ├── WalkForwardAnalysis
    Infrastructure                └── MonteCarloAnalysis
    ├── PostgreSQL (state)
    ├── Redis (events)            Storage
    ├── Prometheus (metrics)      ├── SQLite (jobs, presets)
    └── Telegram (alerts)        └── JSON/CSV (results)
```
