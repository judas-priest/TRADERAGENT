# TRADERAGENT v2.0 — Unified Trading Algorithm

## 1. Философия

Текущая архитектура запускает стратегии как **независимые боты** — каждый со своим капиталом, рисками и логикой. Это работает для демо, но в продакшене создаёт проблемы:

- Стратегии конфликтуют на одной паре (Grid продаёт ↔ Trend Follower покупает)
- Капитал распределяется статически (60/30/10 в HYBRID) без учёта текущего режима
- Риск считается per-bot, а не по всему портфелю
- SMC дублирует анализ вместо того, чтобы усиливать другие стратегии

**Цель v2.0:** превратить "набор ботов" в **адаптивный торговый портфель** с единым мозгом.

---

## 2. Главный цикл (Master Loop)

```
┌─────────────────────────────────────────────────────────────────┐
│                    MASTER LOOP (каждые 60 сек)                  │
│                                                                 │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────────┐      │
│  │  Market   │───→│   Strategy   │───→│  Capital          │      │
│  │  Scanner  │    │   Router     │    │  Allocator        │      │
│  └──────────┘    └──────────────┘    └───────────────────┘      │
│       │                │                      │                  │
│       ▼                ▼                      ▼                  │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────────┐      │
│  │  Regime   │    │   SMC        │    │  Risk             │      │
│  │  Detector │    │   Filter     │    │  Aggregator       │      │
│  └──────────┘    └──────────────┘    └───────────────────┘      │
│                        │                      │                  │
│                        ▼                      ▼                  │
│                 ┌──────────────────────────────────┐             │
│                 │     STRATEGY EXECUTION LAYER      │             │
│                 │  Grid | DCA | Trend | Hybrid      │             │
│                 │     (каждые 1-5 сек внутри)       │             │
│                 └──────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

Ключевое отличие от текущей системы: **два уровня цикла**.

- **Master Loop (60 сек):** глобальный анализ, перераспределение капитала, выбор стратегий
- **Strategy Loop (1-5 сек):** исполнение выбранной стратегии на конкретной паре (как сейчас)

---

## 3. Market Scanner — Сканер рынка

### 3.1. Что анализируем

Для каждой торгуемой пары собираем:

```python
class MarketSnapshot:
    symbol: str               # "BTC/USDT"
    price: Decimal            # текущая цена
    adx_14: float             # ADX(14) — сила тренда
    adx_direction: str        # "bullish" | "bearish" | "neutral"
    atr_percent: float        # ATR(14) / price * 100 — волатильность в %
    ema_20: float             # EMA(20)
    ema_50: float             # EMA(50)
    rsi_14: float             # RSI(14)
    volume_ratio: float       # volume_24h / avg_volume_30d
    bb_width: float           # (upper - lower) / middle — ширина полос Боллинджера
    range_score: float        # 0-1, насколько цена в боковике (из MarketRegimeDetector)
```

### 3.2. Классификация режима

```
                    ADX
                     │
          ┌──────────┼──────────┐
          │          │          │
       < 20      20-30       > 30
     RANGING   TRANSITION   TRENDING
          │          │          │
          │          │    ┌─────┴─────┐
          │          │    │           │
          │          │  EMA20>50   EMA20<50
          │          │  BULL_TREND BEAR_TREND
          │          │
          │    ┌─────┴─────┐
          │  ATR < 2%   ATR >= 2%
          │  QUIET_     VOLATILE_
          │  TRANSITION TRANSITION
          │
    ┌─────┴─────┐
  ATR < 1%   ATR >= 1%
  TIGHT_     WIDE_
  RANGE      RANGE
```

**6 режимов рынка:**

| Режим | ADX | ATR | Описание |
|-------|-----|-----|----------|
| `TIGHT_RANGE` | < 20 | < 1% | Узкий боковик, идеальный для Grid |
| `WIDE_RANGE` | < 20 | >= 1% | Широкий боковик, Grid с расширенным диапазоном |
| `QUIET_TRANSITION` | 20-30 | < 2% | Слабый тренд формируется, осторожность |
| `VOLATILE_TRANSITION` | 20-30 | >= 2% | Высокая неопределённость, SMC-фильтр критичен |
| `BULL_TREND` | > 30 | — | Восходящий тренд, Trend Follower |
| `BEAR_TREND` | > 30 | — | Нисходящий тренд, DCA + Trend Follower (short) |

---

## 4. Strategy Router — Маршрутизатор стратегий

### 4.1. Матрица «Режим → Стратегия»

| Режим | Основная стратегия | Резервная | Запрещены |
|-------|-------------------|-----------|-----------|
| `TIGHT_RANGE` | Grid (arithmetic) | Hybrid | Trend Follower |
| `WIDE_RANGE` | Grid (geometric) | Hybrid | — |
| `QUIET_TRANSITION` | Hybrid (60% Grid, 40% DCA) | Grid | — |
| `VOLATILE_TRANSITION` | DCA (осторожный) | SMC standalone | Grid без фильтра |
| `BULL_TREND` | Trend Follower (long) | SMC standalone | Grid, DCA (long) |
| `BEAR_TREND` | DCA (accumulation) | Trend Follower (short) | Grid |

### 4.2. Правила переключения

```python
class StrategyRouter:
    # Минимальное время в одной стратегии (предотвращает флип-флоп)
    MIN_REGIME_DURATION = timedelta(hours=4)

    # Количество подтверждений для смены режима
    CONFIRMATION_CANDLES = 3  # 3 свечи подряд подтверждают новый режим

    # Гистерезис: порог переключения строже, чем порог удержания
    ADX_ENTER_TREND = 32     # войти в тренд при ADX > 32
    ADX_EXIT_TREND = 25      # выйти из тренда при ADX < 25
```

**Алгоритм переключения:**

1. Market Scanner определяет текущий режим каждые 60 секунд
2. Если новый режим != текущий → инкремент `confirmation_counter`
3. Если `confirmation_counter >= CONFIRMATION_CANDLES` → запрос на переключение
4. Проверяем `MIN_REGIME_DURATION` — прошло ли 4 часа с последнего переключения
5. Если да → **Graceful Transition**:
   - Новые ордера создаются по новой стратегии
   - Существующие позиции старой стратегии закрываются по правилам (TP/SL/trailing)
   - Не допускаем одновременное удержание противоположных позиций

---

## 5. SMC Enhancement Layer — Фильтр качества входов

**Ключевая идея:** SMC не работает как отдельная стратегия, а **повышает качество входов** всех остальных стратегий.

### 5.1. Как это работает

```
                    Сигнал от стратегии
                           │
                    ┌──────┴──────┐
                    │  SMC Filter  │
                    │              │
                    │  Проверяет:  │
                    │  • Order     │
                    │    Blocks    │
                    │  • Fair      │
                    │    Value     │
                    │    Gaps      │
                    │  • Liquidity │
                    │    Zones     │
                    └──────┬──────┘
                           │
                  ┌────────┼────────┐
                  │        │        │
              ENHANCED  NEUTRAL   REJECT
              (0.7-1.0) (0.4-0.7) (< 0.4)
                  │        │        │
            Полный    Уменьшенный  Отклонён
            размер    размер (50%)
```

### 5.2. Сценарии применения

**Grid + SMC:**
- Grid хочет поставить buy-ордер на уровне $95,000
- SMC видит Order Block в зоне $94,800-$95,200 → `ENHANCED` — полный размер ордера
- SMC видит ликвидность ниже $94,500 → `REJECT` — ордер на этом уровне пропускается

**DCA + SMC:**
- DCA хочет добавить safety order при падении на -3%
- SMC видит Fair Value Gap в этой зоне → `ENHANCED` — ордер размещается с полным объёмом
- SMC не видит поддержки → `NEUTRAL` → ордер уменьшается на 50%

**Trend Follower + SMC:**
- Trend Follower обнаружил пробой EMA(50) вверх
- SMC подтверждает: пробой произошёл из зоны Order Block → `ENHANCED`
- SMC видит: движение в зону ликвидности (ловушка) → `REJECT`

### 5.3. Параметры фильтра

```python
class SMCFilter:
    MIN_CONFIDENCE = 0.4          # Ниже = REJECT
    ENHANCED_THRESHOLD = 0.7      # Выше = ENHANCED
    NEUTRAL_SIZE_MULTIPLIER = 0.5 # Для NEUTRAL: 50% от нормального размера
    LOOKBACK_CANDLES = 100        # Глубина анализа для поиска зон
    TIMEFRAMES = ["1h", "4h"]     # Таймфреймы для мульти-ТФ анализа
```

---

## 6. Capital Allocator — Распределение капитала

### 6.1. Формула аллокации

В отличие от статического 60/30/10 в текущем HYBRID, v2.0 распределяет динамически:

```
Total Capital = $100,000

┌─────────────────────────────────────────┐
│              RESERVE (15%)               │  ← Всегда $15,000 — неприкосновенный запас
│              $15,000                     │
├─────────────────────────────────────────┤
│           ACTIVE POOL (85%)             │  ← $85,000 — распределяется между парами
│           $85,000                        │
│                                         │
│  Pair Allocation = ActivePool           │
│    × pair_weight                        │
│    × regime_confidence                  │
│    × performance_factor                 │
│                                         │
│  pair_weight:                           │
│    Top-5 по ликвидности = 15% каждая   │
│    Остальные = равномерно               │
│                                         │
│  regime_confidence:                     │
│    ADX > 40 (сильный тренд) = 1.0      │
│    ADX 30-40 = 0.8                      │
│    ADX 20-30 (переход) = 0.5           │
│    ADX < 20 (боковик) = 0.7            │
│                                         │
│  performance_factor:                    │
│    Win rate > 60% = 1.2                 │
│    Win rate 40-60% = 1.0               │
│    Win rate < 40% = 0.6                │
│    Win rate < 25% = 0.0 (отключение)   │
└─────────────────────────────────────────┘
```

### 6.2. Правила безопасности

- **Максимум на одну пару:** 25% от Active Pool ($21,250)
- **Максимум на одну стратегию:** 40% от Active Pool ($34,000)
- **Минимум Reserve:** 15% всегда (даже при просадке)
- **Ребалансировка:** каждые 4 часа (совпадает с MIN_REGIME_DURATION)
- **Emergency Halt:** если портфель упал на > 10% за сутки — все стратегии стоп

---

## 7. Risk Aggregator — Единый контроль рисков

### 7.1. Три уровня защиты

```
Level 1: Per-Trade Risk (на каждую сделку)
├── Max loss per trade: 1-2% от аллокации пары
├── Stop-loss обязателен (ATR-based)
└── Position size = risk_amount / distance_to_stop

Level 2: Per-Pair Risk (на каждую пару)
├── Max open positions: 1 (одна позиция на пару в любой момент)
├── Max daily loss per pair: 3% от аллокации пары
├── Cooldown после убыточной серии: 3 подряд → пауза 2 часа
└── Нельзя открыть противоположную позицию, пока текущая не закрыта

Level 3: Portfolio Risk (по всему портфелю)
├── Max total exposure: 70% от Total Capital
├── Max correlated exposure: 40% (BTC + ETH + коррелированные < 40%)
├── Daily portfolio loss limit: 5% → reduced mode (50% sizes)
├── Daily portfolio loss limit: 10% → emergency halt
├── Max simultaneous strategies: 3 per pair ecosystem
└── Drawdown > 15% от ATH → постепенное сокращение позиций
```

### 7.2. Корреляционная защита

```python
CORRELATION_GROUPS = {
    "btc_ecosystem": ["BTC/USDT", "WBTC/USDT"],
    "eth_ecosystem": ["ETH/USDT", "STETH/USDT"],
    "large_caps":    ["BNB/USDT", "SOL/USDT", "ADA/USDT"],
    "defi":          ["AAVE/USDT", "UNI/USDT", "LINK/USDT"],
    "memes":         ["DOGE/USDT", "SHIB/USDT", "PEPE/USDT"],
}

# Правило: суммарная экспозиция одной группы <= 30% Active Pool
```

---

## 8. Полный алгоритм — Пошагово

```
TRADERAGENT v2.0 Main Algorithm
================================

INIT:
  1. Загрузить конфиг (пары, капитал, параметры стратегий)
  2. Подключиться к бирже (ByBitDirectClient / ExchangeClient)
  3. Загрузить state snapshot из PostgreSQL (если есть)
  4. Reconcile: сверить открытые ордера/позиции с биржей
  5. Инициализировать SMC Filter (загрузить 100 свечей для каждого ТФ)
  6. Рассчитать начальный Capital Allocation
  7. Запустить Telegram notifier

MASTER LOOP (каждые 60 секунд):
  FOR each trading_pair:
    1. SCAN: Получить MarketSnapshot (ADX, ATR, EMA, RSI, volume, BB)
    2. CLASSIFY: Определить MarketRegime (6 режимов)
    3. ROUTE: Выбрать стратегию по матрице Режим→Стратегия
    4. CHECK TRANSITION:
       IF новая стратегия != текущая:
         IF confirmation_counter < 3: инкремент, продолжить текущую
         IF elapsed < 4 часов: продолжить текущую
         ELSE: Graceful Transition → запустить новую, закрыть старую
    5. ALLOCATE: Пересчитать капитал для пары
       (pair_weight × regime_confidence × performance_factor)
    6. RISK CHECK:
       IF daily_portfolio_loss > 10%: EMERGENCY HALT → exit loop
       IF daily_portfolio_loss > 5%: REDUCED MODE → halve all sizes
       IF pair_daily_loss > 3%: PAUSE pair → skip
       IF drawdown > 15%: reduce positions gradually

  REBALANCE (каждые 4 часа):
    - Пересчитать pair_weights по performance
    - Пересчитать correlation exposure
    - Убрать неэффективные пары (win_rate < 25%)
    - Логировать allocation snapshot

STRATEGY LOOP (каждые 1-5 секунд, per pair):
  1. Получить текущую цену
  2. Выполнить логику выбранной стратегии:
     - Grid: проверить заполнение уровней, разместить counter-orders
     - DCA: проверить confluence score, добавить safety orders
     - Trend Follower: проверить EMA crossover, управлять trailing stop
     - Hybrid: внутренний Grid/DCA роутинг по ADX
  3. SMC FILTER: каждый сигнал проходит через SMC Enhancement Layer
     - ENHANCED → полный размер
     - NEUTRAL → 50% размера
     - REJECT → сигнал отклонён
  4. Разместить/отменить ордера на бирже
  5. Обновить state в памяти
  6. Publish event в Redis

STATE PERSISTENCE (каждые 30 секунд):
  - Snapshot всех engine states → PostgreSQL
  - При crash → restart → reconcile → resume

SHUTDOWN:
  1. Отменить все pending ордера (опционально, по конфигу)
  2. Финальный state snapshot
  3. Telegram notification
  4. Graceful exit
```

---

## 9. Пример работы на реальном сценарии

### Сценарий: BTC падает после роста

```
Время 00:00 — BTC $100,000, ADX=15, ATR=0.8%
  Режим: TIGHT_RANGE
  Стратегия: GRID (arithmetic, 15 уровней)
  Аллокация: $17,000 (20% Active Pool)
  Grid работает: покупает на $99,500, продаёт на $100,500

Время 06:00 — BTC $99,000, ADX=22, ATR=1.5%
  Режим: QUIET_TRANSITION (первое определение)
  confirmation_counter = 1 (нужно 3)
  Стратегия: остаётся GRID

Время 08:00 — BTC $98,000, ADX=28, ATR=2.1%
  confirmation_counter = 3, прошло 8 часов > 4 часов
  Режим: VOLATILE_TRANSITION → ADX растёт, EMA20 < EMA50
  → Graceful Transition: Grid закрывает ордера
  Стратегия: DCA (осторожный) + SMC Filter
  Аллокация: $12,750 (regime_confidence=0.5 снижает)

Время 12:00 — BTC $95,000, ADX=35
  Режим: BEAR_TREND
  Стратегия: DCA (accumulation) — уже активна, продолжаем
  DCA добавляет safety order #2 (-5% от входа)
  SMC видит Fair Value Gap на $94,500 → ENHANCED → полный объём

Время 20:00 — BTC $93,000, ADX=42
  Сильный нисходящий тренд
  DCA: safety order #3 (-8%)
  SMC Filter: Order Block на $92,000 → подтверждает зону поддержки
  Аллокация увеличена: regime_confidence=1.0 (ADX>40)

Время +2 дня — BTC $97,000, ADX=18
  Разворот! ADX падает, цена растёт
  confirmation_counter: 3 подряд WIDE_RANGE
  → Graceful Transition: DCA фиксирует прибыль (TP hit)
  Стратегия: Grid (geometric) — новый цикл
  DCA PnL: +$1,200 (4 safety orders, средняя $95,500, TP $97,000)
```

---

## 10. Отличия от текущей архитектуры

| Аспект | Текущая система | TRADERAGENT v2.0 |
|--------|----------------|-------------------|
| Координация | Боты независимы | Master Loop управляет всеми |
| Выбор стратегии | Статический конфиг | Динамический по режиму рынка |
| Капитал | Фиксированный per-bot | Динамическая аллокация |
| SMC | Отдельная стратегия | Фильтр для всех стратегий |
| Риск | Per-bot limits | 3-уровневый: trade → pair → portfolio |
| Переключение | Только в HYBRID (Grid↔DCA) | Глобальное переключение любых стратегий |
| Корреляция | Не учитывается | Группы корреляции с лимитами |
| Ребалансировка | Нет | Каждые 4 часа по performance |

---

## 11. Компоненты для реализации

### Новые модули

```
bot/
├── coordinator/
│   ├── master_loop.py          # Главный цикл (60 сек)
│   ├── market_scanner.py       # Сбор MarketSnapshot
│   ├── regime_classifier.py    # 6 режимов рынка
│   ├── strategy_router.py      # Матрица Режим→Стратегия
│   ├── capital_allocator.py    # Динамическое распределение
│   └── risk_aggregator.py      # Портфельный риск
├── filters/
│   └── smc_filter.py           # SMC Enhancement Layer
```

### Изменения в существующих модулях

- `BotOrchestrator` → делегирует решения `MasterLoop`
- `BaseStrategy` → добавить метод `accept_smc_filter(signal, smc_score)`
- `RiskManager` → расширить до portfolio-level
- `StatePersistence` → сохранять regime history и allocation snapshots
