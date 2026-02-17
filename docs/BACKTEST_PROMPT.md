# TRADERAGENT — Промт для проведения бэктестов и подготовки пресетов

## Задача

Провести полное бэктестирование всех стратегий TRADERAGENT v2.0 на исторических данных, доступных на сервере `185.233.200.13`, и подготовить оптимизированные пресеты для интеграции в основной торговый бот.

### Порядок запуска

> **ВАЖНО:** Пары BTCUSDT и ETHUSDT исключены из тестирования.

1. **Пробный прогон** — сначала протестировать на 3 монетах: **YFI, ZIL, ZRX** (последние в списке). Цель — убедиться что пайплайн работает на сервере, оценить время и потребление RAM.
2. **Основной прогон** — после успешного пробного запустить на всех оставшихся 43 монетах (без BTC и ETH).

---

## Контекст

### Сервер
- **IP:** 185.233.200.13
- **SSH:** `ssh ai-agent@185.233.200.13`
- **CPU:** 4 ядра, **RAM:** 2 GB, **Disk:** 56 GB (40 GB свободно)
- **Python:** установлен в `/home/ai-agent/TRADERAGENT/`
- **Ограничения:** из-за 2 GB RAM обрабатывать монеты последовательно, освобождать память между символами (gc.collect()), использовать last_candles для ограничения объёма данных

### Исторические данные
- **Путь:** `/home/ai-agent/TRADERAGENT/data/historical/`
- **45 монет:** 1INCH, AAVE, ADA, ALGO, AVAX, BAT, BCH, BNB, BTC, CHZ, COMP, CRV, DOGE, DOT, EOS, ETC, ETH, FIL, FTM, FTT, HBAR, HNT, ICP, KSM, LDO, LINK, LTC, LUNA, MANA, MATIC, RUNE, SAND, SHIB, SNX, SOL, SUSHI, TRX, UNI, WAVES, XEM, XLM, XRP, YFI, ZIL, ZRX
- **10 таймфреймов каждый:** 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d
- **473 CSV файла, 5.4 GB**
- **Формат CSV:** `Open time, open, high, low, close, volume, Close time, Quote asset volume, Number of trades, ...`
- **Глубина данных:** BTC/ETH — ~74K свечей 1h (~8.5 лет), SOL — ~48K свечей (~5.5 лет)

### Система бэктестинга
- **Grid Backtesting System:** `bot/backtesting/grid/` — полный пайплайн: classify → optimize → stress test → export presets
- **DCA Backtester:** `bot/strategies/dca/dca_backtester.py` — симуляция DCA deals (base order + safety orders + trailing stop)
- **Готовый batch-скрипт:** `scripts/run_grid_backtest_all.py` — обрабатывает все 45 пар
- **Generic Backtesting Framework:** `bot/tests/backtesting/` — MultiTimeframeBacktestEngine для любых стратегий (TrendFollower, SMC)

### Стратегии бота
1. **Grid** — сеточная торговля (sideways markets)
2. **DCA** — усреднение на падении (downtrend)
3. **Hybrid** — Grid + DCA с переключением по ADX/market regime
4. **Trend Follower** — следование за трендом (EMA, ATR, RSI)
5. **SMC** — Smart Money Concepts (order blocks, liquidity, structure)

---

## Порядок выполнения

### Этап 1: Grid Backtesting (готовый пайплайн)

Это самый зрелый компонент — скрипт уже написан.

```bash
ssh ai-agent@185.233.200.13
cd /home/ai-agent/TRADERAGENT

# Сначала синхронизировать последний код с dev-машины (если нужно)
git pull origin main

# Запустить Grid бэктест на всех 45 парах
# last-candles=4320 = ~6 месяцев 1h данных (экономит RAM)
# coarse-steps=3, fine-steps=3 — минимальная оптимизация для 2 GB RAM
python scripts/run_grid_backtest_all.py \
    --data-dir /home/ai-agent/TRADERAGENT/data/historical \
    --last-candles 4320 \
    --objective sharpe \
    --coarse-steps 3 \
    --fine-steps 3

# Если не хватает RAM — обрабатывать блоками по 10 монет:
python scripts/run_grid_backtest_all.py \
    --data-dir /home/ai-agent/TRADERAGENT/data/historical \
    --symbols BTC,ETH,SOL,BNB,ADA,DOT,LINK,AVAX,MATIC,UNI \
    --last-candles 4320 \
    --objective sharpe

# Повторить для оставшихся блоков
```

**Ожидаемый результат:**
- `data/backtest_results/batch_<timestamp>/summary.csv` — рейтинг всех пар
- `data/backtest_results/batch_<timestamp>/presets/*.yaml` — YAML пресеты для прибыльных пар
- JSON-отчёты по каждому символу с метриками: ROI, Sharpe, MaxDD, Cycles, Profit Factor

**Критерии отбора Grid-пресетов:**
- ROI > 0 (прибыльный)
- Sharpe > 0.5 (приемлемый risk-adjusted return)
- Max Drawdown < 15%
- Completed Cycles > 10
- Stress Test avg ROI > 0 (устойчивость к волатильности)

### Этап 2: DCA Backtesting

Написать скрипт `scripts/run_dca_backtest_all.py` по аналогии с grid, используя `DCABacktester`.

**Параметры для оптимизации:**
- `base_order_size`: [50, 100, 200]
- `safety_order_size`: [50, 100, 200]
- `max_safety_orders`: [3, 5, 8]
- `price_deviation_pct`: [1.0, 2.0, 3.0, 5.0] — % падения для каждого safety order
- `take_profit_pct`: [1.0, 2.0, 3.0, 5.0]
- `trailing_stop`: True/False + параметры trailing

**Данные:** использовать 1h свечи, брать close prices как `list[Decimal]`.

**Ключевая идея:** DCA работает лучше на DOWNTREND монетах. Сначала классифицировать монеты по тренду (price_change_pct за период), затем тестировать DCA на падающих и боковых монетах.

**Формат вывода DCA-пресетов:**
```yaml
symbol: ETHUSDT
strategy: dca
base_order_size: 100
safety_order_size: 100
max_safety_orders: 5
price_deviation_pct: 2.0
take_profit_pct: 3.0
trailing_stop:
  enabled: true
  activation_pct: 1.0
  callback_pct: 0.5
_backtest_metrics:
  total_trades: 42
  win_rate: 0.85
  avg_profit_pct: 2.3
  max_drawdown_pct: 8.5
```

### Этап 3: Trend Follower Backtesting

Использовать `MultiTimeframeBacktestEngine` из `bot/tests/backtesting/multi_tf_engine.py` c `TrendFollowerStrategy`.

**Параметры для оптимизации:**
- `ema_fast_period`: [10, 20, 30]
- `ema_slow_period`: [40, 50, 100]
- `atr_period`: [14, 20]
- `rsi_period`: [14]
- `risk_per_trade_pct`: [1.0, 2.0]
- `tp_atr_multiplier`: [2.0, 3.0, 4.0]
- `sl_atr_multiplier`: [1.0, 1.5, 2.0]

**Данные:** использовать 4h или 1d свечи (trend follower работает на старших таймфреймах).

**Фильтр монет:** тестировать на монетах с высоким ATR% и выраженным трендом (BTC, ETH, SOL, AVAX, FTM, RUNE, DOGE).

### Этап 4: Hybrid Preset Generation

На основе результатов Grid + DCA:
1. Для каждой монеты определить лучшую стратегию (Grid vs DCA) на основе market regime
2. Для sideways монет — использовать Grid-пресеты
3. Для trending монет — использовать DCA-пресеты или Trend Follower
4. Для Hybrid — скомбинировать: Grid-параметры + DCA-параметры + пороги переключения (ADX thresholds)

### Этап 5: Сборка итоговых конфигов

Собрать из лучших пресетов production-ready конфиг `configs/production_presets.yaml`:

```yaml
# Автоматически сгенерировано бэктестом <дата>
# Топ-10 прибыльных Grid-пар
grid_presets:
  - symbol: ETHUSDT
    grid_levels: 15
    profit_per_grid: 0.005
    spacing: arithmetic
    # ... из YAML пресета

# Топ-5 DCA-пар
dca_presets:
  - symbol: BTCUSDT
    base_order_size: 100
    # ...

# Hybrid конфиги (Grid + DCA)
hybrid_presets:
  - symbol: BTCUSDT
    grid: { ... }
    dca: { ... }
    breakout_adx_threshold: 25.0
    return_adx_threshold: 20.0

# Trend Follower конфиги
trend_presets:
  - symbol: SOLUSDT
    ema_fast: 20
    ema_slow: 50
    # ...
```

---

## Ограничения по ресурсам сервера (2 GB RAM)

1. **Обрабатывать монеты строго последовательно**, не параллельно
2. **last_candles=4320** (6 месяцев) — для первого прохода. Если RAM хватает, можно увеличить до 8760 (1 год)
3. **gc.collect()** после каждого символа (уже есть в скрипте)
4. **coarse_steps=3, fine_steps=3** — минимальная оптимизация. Для финального прохода на топ-10 парах можно увеличить до 5
5. **Мониторить RAM:** `free -h` между блоками
6. **Использовать screen/tmux** — бэктест всех 45 пар может занять 1-3 часа
7. **Не запускать бота одновременно с бэктестом** — остановить Docker контейнер если запущен

---

## Проверка результатов

После завершения всех этапов:

1. Убедиться что все YAML пресеты валидны:
```bash
python -c "
import yaml
from pathlib import Path
for f in Path('data/backtest_results').rglob('*.yaml'):
    try:
        yaml.safe_load(f.read_text())
        print(f'OK: {f.name}')
    except Exception as e:
        print(f'FAIL: {f.name}: {e}')
"
```

2. Проверить что пресеты загружаются в GridStrategyConfig:
```bash
python -c "
from bot.strategies.grid.grid_config import GridStrategyConfig
config = GridStrategyConfig.from_yaml_file('data/backtest_results/batch_.../presets/ETHUSDT.yaml')
print(config)
"
```

3. Обновить `configs/phase7_demo.yaml` с лучшими параметрами для demo-trading

---

## Ожидаемые артефакты

| Артефакт | Путь | Описание |
|----------|------|----------|
| Grid summary CSV | `data/backtest_results/batch_*/summary.csv` | Рейтинг 45 пар по ROI/Sharpe |
| Grid YAML presets | `data/backtest_results/batch_*/presets/*.yaml` | Пресеты для прибыльных Grid-пар |
| Grid JSON reports | `data/backtest_results/batch_*/*_report.json` | Полные отчёты с метриками |
| DCA presets | `data/backtest_results/dca_*/presets/*.yaml` | Пресеты для DCA-пар |
| TF presets | `data/backtest_results/tf_*/presets/*.yaml` | Пресеты для Trend Follower |
| Production config | `configs/production_presets.yaml` | Итоговый конфиг для бота |
| Backtest report | `docs/BACKTEST_REPORT.md` | Сводный отчёт с результатами |

---

## Примечания

- **LUNA, FTT** — delisted/crashed монеты. Результаты бэктеста будут некорректны из-за обнуления цены. Исключить из итоговых пресетов.
- **5m/15m данные** — слишком гранулярные для 2 GB RAM на полном периоде. Использовать 1h минимум.
- **Sharpe ratio** в GridBacktestSimulator hardcoded для hourly candles (8760 periods/year). При использовании других таймфреймов Sharpe будет некорректен — нужно пересчитывать.
- **amount_per_grid** не оптимизируется в текущем GridOptimizer — задаётся фиксированно в base_config. Для production подбирать вручную исходя из баланса.
