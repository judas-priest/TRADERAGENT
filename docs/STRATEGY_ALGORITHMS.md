# TRADERAGENT: Алгоритмы работы стратегий

> Описание алгоритма каждой стратегии после запуска: какие параметры мониторит, с чем сравнивает, какие сигналы и кому выдаёт.
>
> **Обновлено:** 2026-02-23 | Соответствует реальному поведению кода (не только дизайну)

---

## 1. GRID (Сеточная стратегия)

**Идея:** Расставить сетку лимитных ордеров — покупки ниже текущей цены, продажи выше. При каждом исполнении ордера ставится встречный ордер с наценкой.

| Компонент | Что мониторит | С чем сравнивает | Сигнал / Действие | Куда передаёт |
|-----------|---------------|------------------|-------------------|---------------|
| **GridCalculator** | Текущая цена, ATR(14) | `upper_price`, `lower_price` (фиксированные или ATR × multiplier) | Рассчитывает N уровней (арифметические или геометрические) | → GridEngine |
| **GridEngine** | Список открытых ордеров на бирже | Сравнивает `active_orders` с `fetch_open_orders()` — если ордер пропал из списка, значит исполнен | **BUY fill** → создаёт SELL counter-order (цена + profit_per_grid), **SELL fill** → создаёт BUY counter-order (цена − profit_per_grid) | → Биржа (лимитный ордер), → Redis `ORDER_FILLED` |
| **GridRiskManager** | Позиция, баланс, цена, ADX | `max_drawdown_pct` (10%), `max_position_size`, `stop_loss_pct` (5%), `ADX > 25` (трендовый рынок) | `CONTINUE` / `PAUSE` / `STOP_LOSS` / `DEACTIVATE` (если тренд обнаружен — сетка неэффективна) | → GridEngine (блокировка новых ордеров) |
| **Price Monitor** | Текущая цена (каждые 5 сек) | Если Dynamic Grid и цена вышла за boundaries | **Rebalance**: отмена всех ордеров → пересчёт сетки → размещение новых | → Биржа, → Redis `GRID_REBALANCED` |
| **State Persistence** | Состояние (каждые 30 сек) | — | Сохраняет snapshot в PostgreSQL | → БД `bot_state_snapshots` |

> **Статус ордеров:** `ByBitDirectClient` возвращает CCXT-нормализованные статусы (`"closed"` вместо нативного Bybit `"filled"`). Нормализация происходит в `_normalize_order_status()` в `bot/api/bybit_direct_client.py`.

**Ключевые параметры по умолчанию:**

| Параметр | Значение | Описание |
|----------|----------|----------|
| `num_levels` | 15 | Количество уровней сетки |
| `profit_per_grid` | 0.5% | Наценка на каждый counter-order |
| `atr_multiplier` | 3.0 | Множитель ATR для границ сетки |
| `atr_period` | 14 | Период расчёта ATR |

**Volatility Presets:**

| Пресет | Уровней | Profit/grid | Для чего |
|--------|---------|-------------|----------|
| LOW | 20 | 0.2% | Стейблкоины, узкий диапазон |
| MEDIUM | 15 | 0.5% | BTC/ETH, стандартная волатильность |
| HIGH | 10 | 1.0% | Альткоины, высокая волатильность |

**Формулы расчёта уровней:**

```
Арифметическая сетка:
  step = (upper - lower) / (num_levels - 1)
  level[i] = lower + step × i

Геометрическая сетка:
  ratio = (upper / lower) ^ (1 / (num_levels - 1))
  level[i] = lower × ratio^i

ATR-границы:
  upper = current_price + ATR × atr_multiplier
  lower = current_price - ATR × atr_multiplier

Counter-order (после исполнения BUY):
  sell_price = filled_price × (1 + profit_per_grid)

Counter-order (после исполнения SELL):
  buy_price = filled_price × (1 - profit_per_grid)
```

---

## 2. DCA (Dollar Cost Averaging)

**Идея:** Входить в рынок на откате (oversold), усреднять позицию safety-ордерами при просадке, выходить по take profit или trailing stop.

| Компонент | Что мониторит | С чем сравнивает | Сигнал / Действие | Куда передаёт |
|-----------|---------------|------------------|-------------------|---------------|
| **DCASignalGenerator** | EMA(12), EMA(26), ADX, RSI, BB lower/upper, Volume 24h | **Trend**: `ema_fast < ema_slow` + `ADX >= 20` (нисходящий тренд). **RSI**: `RSI < 35` (перепроданность). **BB**: `price <= bb_lower × 1.02`. **Volume**: `vol_24h / avg_vol >= 1.2`. Каждое условие имеет **вес** (Trend=3, Price=2, Indicators=2, Risk=1, Timing=1) | Считает **confluence score** = сумма_весов_пройденных / сумма_всех. Если `score >= 0.6` → `should_open = True` | → DCAEngine |
| **FalseSignalFilter** | Повторные сигналы, cooldown, spike | `min_confirmations` (нужно N подтверждений подряд), `cooldown` (сек с последнего отказа), `price_spike_%` | Фильтрует ложные срабатывания | → DCAEngine (блокировка входа) |
| **DCAPositionManager** | Текущая цена vs средняя цена позиции | **TP**: `avg_entry × (1 + tp_pct%)`. **SL**: `base_price × (1 - sl_pct%)`. **Safety Order**: `base_price × (1 - step% × level)` | **TP hit** → закрыть сделку. **SL hit** → закрыть с убытком. **SO triggered** → докупить (volume × multiplier^level), пересчитать avg_entry | → Биржа (market/limit), → Redis `DCA_TRIGGERED` / `TAKE_PROFIT_HIT` |
| **DCATrailingStop** | `highest_price_since_entry` (пик) | Активация: профит >= `activation_pct` (1.5%). Расстояние: `highest × (1 - distance_pct%)` | Если цена упала ниже trailing stop → закрыть позицию с профитом | → DCAEngine → Биржа |
| **DCARiskManager** | active_deals, daily_pnl, exposure, баланс | `max_concurrent_deals`, `max_daily_loss` ($500), `max_total_exposure`, `max_consecutive_losses` (5) | `CAN_TRADE` / `PAUSE` / `CLOSE_DEAL` / `CLOSE_ALL` | → DCAEngine (блокировка) |

**Система весов для confluence score:**

| Категория | Вес | Условие | Блокирующее? |
|-----------|-----|---------|--------------|
| TREND | 3 | `ema_fast < ema_slow` + `ADX >= 20` | Нет (scoring) |
| PRICE | 2 | Цена в допустимом диапазоне + близость к support (<=2%) | Нет (scoring) |
| INDICATORS | 2 | `RSI < 35` + `price <= bb_lower × 1.02` + `volume >= 1.2× avg` | Нет (scoring) |
| RISK | 1 | `active_deals < max`, `daily_pnl > -max_loss`, достаточный баланс | **Да** (блокирует) |
| TIMING | 1 | `elapsed >= min_seconds_between_deals` (120 сек) | **Да** (блокирует) |

**Формула confluence:** `score = sum(passed_weights) / sum(all_weights)`, порог: 0.6

**Формула Safety Orders:**

```
SO_price[L] = base_price × (1 - price_step_pct × L / 100)
SO_volume[L] = (base_order_volume × volume_multiplier^L) / SO_price[L]

Пример (Conservative):
  Base: $50 @ $40,000 = 0.00125 BTC
  SO-1: -1.5% = $39,400 → $75 (×1.5) → 0.0019 BTC
  SO-2: -3.0% = $38,800 → $97.5 (×1.95) → 0.0025 BTC
  SO-3: -4.5% = $38,200 → $127 (×2.54) → 0.0033 BTC
```

**Presets:**

| Пресет | Confluence | Safety Orders | TP | SL | Cooldown |
|--------|-----------|---------------|-----|-----|---------|
| Conservative | >= 0.7 | 3 | 2.0% | 8% | 300 сек |
| Moderate | >= 0.6 | 5 | 1.5% | 10% | 120 сек |
| Aggressive | >= 0.5 | 7 | 1.0% | 12% | 60 сек |

---

## 3. TREND FOLLOWER (Следование за трендом)

**Идея:** Определить фазу рынка (бычий/медвежий/боковик), войти на откате к EMA или от уровня поддержки/сопротивления, выходить по trailing stop или TP.

| Компонент | Что мониторит | С чем сравнивает | Сигнал / Действие | Куда передаёт |
|-----------|---------------|------------------|-------------------|---------------|
| **MarketAnalyzer** | EMA(20), EMA(50), ATR(14), RSI(14) | **Bullish**: `EMA20 > EMA50` + `price > EMA20` + `divergence > 0.5%`. **Bearish**: обратно. **Sideways**: `divergence < 0.5%`. Сила тренда: STRONG (>=2%), WEAK (1-2%), NONE (<1%) | Определяет `MarketPhase` + `TrendStrength` | → EntryLogic |
| **EntryLogicAnalyzer** | Цена vs EMA(20), уровни support/resistance, RSI, Volume | **В тренде**: `price ~ EMA20 (+-1%)` + отскок (pullback). **В боковике**: `RSI пересёк 30 снизу` (LONG) или `RSI пересёк 70 сверху` (SHORT). **Breakout**: `цена > range_high` + `volume >= 1.5x avg`. **Фильтр**: `ATR > 5%` → отклонение | `EntrySignal` с `confidence` (0.6-0.85) и направлением LONG/SHORT | → PositionManager |
| **PositionManager** | Текущая цена vs entry, SL, TP | **TP/SL по ATR** (см. таблицу ниже). **Partial TP**: при 70% пути до TP → закрыть 50%. **Breakeven**: профит >= 1×ATR → SL = entry. **Trailing**: профит >= 1.5×ATR → SL = price - 0.5×ATR | Ордера на вход/выход + `ExitReason` (TP/SL/trailing/partial) | → Биржа, → Redis, → Trade Journal |
| **RiskManager** | Баланс, daily PnL, позиции, consecutive losses | `risk_per_trade` = 1% капитала, `max_daily_loss` = $500, `max_positions` = 20, `max_exposure` = 20% капитала. Если `consecutive_losses >= 3` → размер × 0.5 | Разрешение/запрет на вход + расчёт `position_size` | → EntryLogic (блокировка) |

**TP/SL множители по фазе рынка:**

| Фаза рынка | TP множитель (× ATR) | SL множитель (× ATR) |
|------------|----------------------|----------------------|
| Sideways | 1.2 | 0.7 |
| Weak Trend | 1.8 | 1.0 |
| Strong Trend | 2.5 | 1.0 |

**Пример (LONG, Strong Trend):**

```
Entry: 50,000 USDT, ATR: 500 USDT
TP = 50,000 + 2.5 × 500 = 51,250
SL = 50,000 - 1.0 × 500 = 49,500
Partial TP (70%): 50,000 + (51,250 - 50,000) × 0.70 = 50,875 → закрыть 50%
Breakeven: профит >= 500 → SL → 50,000
Trailing: профит >= 750 → SL = price - 250
```

**Условия входа по фазе:**

| Фаза | Паттерн | Условие | Confidence |
|------|---------|---------|------------|
| Bullish | Pullback к EMA20 | `price ~ EMA20 (+-1%)` + bounce + volume | 0.6-0.8 |
| Bullish | Bounce от support | `price ~ support` + bounce | 0.75 × strength |
| Bearish | Pullback к EMA20 | `price ~ EMA20` + rejection | 0.6-0.8 |
| Sideways | RSI oversold exit | `prev RSI < 30` → `curr RSI >= 30` | 0.7 |
| Sideways | RSI overbought exit | `prev RSI > 70` → `curr RSI <= 70` | 0.7 |
| Sideways | Range breakout | `price > range_high` + `volume >= 1.5× avg` | 0.85 |

---

## 4. HYBRID (Гибридная стратегия)

**Идея:** Grid и DCA работают одновременно. MarketRegimeDetector анализирует рынок и публикует рекомендации, но переключение стратегий через HybridStrategy.evaluate() в основном цикле **пока не реализовано** (архитектурный gap, запланирован к устранению).

> ⚠️ **Реальное поведение (2026-02-23):** В `_main_loop()` всегда вызываются оба движка — `_process_grid_orders()` и `_process_dca_logic()` — независимо от режима рынка. `MarketRegimeDetector` запускается в отдельном цикле каждые 60 сек, определяет режим и публикует его в Redis, но `get_strategy_recommendation()` не читается в основном цикле. `HybridStrategy.evaluate()` существует, но не вызывается.

| Компонент | Что мониторит | С чем сравнивает | Сигнал / Действие | Куда передаёт |
|-----------|---------------|------------------|-------------------|---------------|
| **MarketRegimeDetector** | ADX, ATR, EMA, Bollinger Bands (ширина), Volume | **SIDEWAYS**: `ADX < 25` + `range_score > 0.4`. **UPTREND/DOWNTREND**: `ADX >= 25` + `trend_score > 0.1`. **HIGH_VOLATILITY**: `BB_width > 6%` или `vol > 2× avg`. **TRANSITIONING**: промежуточное | Рекомендация стратегии + публикация в Redis | → Redis (не читается _main_loop) |
| **GridEngine** | Ордера сетки | Исполнение по цене | Counter-orders | → Биржа (всегда активен) |
| **DCAEngine** | Просадка от base_price | `trigger_percentage` (4%) | Safety orders, TP | → Биржа (всегда активен) |
| **HybridStrategy** | Текущий режим | ADX, GridRisk | `TransitionEvent` (задумано) | → **не подключён** к оркестратору |

**Классификация режимов (detector работает, но не влияет на торговлю):**

| Режим | Условие | Рекомендуемая стратегия |
|-------|---------|------------------------|
| SIDEWAYS | `ADX < 25`, `range_score > 0.4` | GRID |
| UPTREND (weak) | `ADX 25-35`, `trend > +0.1` | HYBRID |
| UPTREND (strong) | `ADX > 35`, `trend > +0.1` | TREND_FOLLOWER |
| DOWNTREND (weak) | `ADX 20-35`, `trend < -0.1` | HYBRID |
| DOWNTREND (strong) | `ADX > 35`, `trend < -0.1` | DCA |
| HIGH_VOLATILITY | `BB_width > 6%` или `vol > 2× avg` | REDUCE_EXPOSURE |
| TRANSITIONING | Промежуточное состояние | HOLD |

---

## 5. SMC (Smart Money Concepts)

**Идея:** Торговля по институциональным зонам ликвидности — Order Blocks (OB) и Fair Value Gaps (FVG) — с подтверждением price action паттернами на младшем таймфрейме.

| Компонент | Что мониторит | С чем сравнивает | Сигнал / Действие | Куда передаёт |
|-----------|---------------|------------------|-------------------|---------------|
| **MarketStructure (H4)** | Swing Highs/Lows (5 свечей слева и справа) | **BOS** (Break of Structure): пробой хая/лоя ПО тренду → продолжение. **CHoCH** (Change of Character): пробой ПРОТИВ тренда → разворот. Тренд: `last_high > prev_high AND last_low > prev_low` = BULLISH | Определяет BULLISH / BEARISH / RANGING + список structure breaks | → ConfluenceZones |
| **ConfluenceZones (H1)** | Order Blocks, Fair Value Gaps | **OB**: последняя свеча противоположного цвета перед structure break. **FVG**: gap между `candle[0].high` и `candle[2].low`. Зоны оцениваются по `strength_score` (0-100): timeframe bonus + volume + size + свежесть - касания | Список активных зон с координатами (high, low) и direction | → EntrySignals |
| **EntrySignals (M15)** | Паттерны: Engulfing, Pin Bar, Inside Bar | **Engulfing**: тело поглощает предыдущее, quality >= 50. **Pin Bar**: фитиль > 60%, тело < 40%. **Inside Bar**: текущая внутри предыдущей. **+ Confluence**: паттерн в зоне OB/FVG. **+ R:R >= 2.5** | `SMCSignal` с `confidence` = 40% quality + 30% confluence + 20% trend alignment + 10% R:R bonus. Мин. >= 0.6 | → PositionManager |
| **SMCAdapter** | Сигнал от EntrySignals | **Stale filter**: если `abs(entry_price - current_price) / current_price > 2%` — сигнал отклоняется | Актуальный сигнал → открытие позиции | → BotOrchestrator |
| **PositionManager** | Текущая цена vs entry/SL/TP, MFE/MAE | **SL**: за стороной OB/паттерна. **TP**: `entry + (entry - SL) × R:R`. **Breakeven**: при 1:1 R:R → SL = entry. **Trailing**: от swing point + 0.5% буфер. **Kelly Criterion** (>= 10 сделок) | Ордера на вход/выход, размер позиции (2% или Kelly) | → Биржа, → Redis, → Telegram |

**Мультитаймфреймовый анализ:**

| Таймфрейм | Роль | Что анализирует |
|-----------|------|-----------------|
| D1 (Daily) | Глобальный тренд | Направление рынка |
| H4 (4 часа) | Структура рынка | Swing points, BOS/CHoCH |
| H1 (1 час) | Зоны ликвидности | Order Blocks, Fair Value Gaps |
| M15 (15 мин) | Точка входа | Price action паттерны |

**Формула confidence:**

```
confidence = 0.40 × pattern_quality     (качество паттерна, 0-100 → 0-1)
           + 0.30 × confluence_score    (совпадение с OB/FVG зонами)
           + 0.20 × trend_alignment     (1.0 если по тренду, 0.5 если против)
           + 0.10 × rr_bonus            (бонус за R:R выше минимума)

Минимальный порог: confidence >= 0.6
```

**Фильтр устаревших сигналов (stale signal filter):**

```
Если |signal.entry_price - current_price| / current_price > 2%:
    → сигнал отклоняется (warning: smc_signal_stale)
    → Order Block мог быть сформирован при другой цене

Причина: SMC кэширует Order Blocks между итерациями.
         При резком движении цены сигнал на вход уже неактуален,
         и TP мог бы сработать сразу после открытия позиции.
```

**Паттерны входа:**

| Паттерн | Условие | Качество (формула) |
|---------|---------|-------------------|
| Bullish Engulfing | `curr_close > curr_open`, тело покрывает предыдущее | 40×(body_ratio) + 30×(body_dominance) + 30×(volume_ratio) |
| Bearish Engulfing | `curr_close < curr_open`, тело покрывает предыдущее | Аналогично |
| Bullish Pin Bar | Нижний фитиль > 60% диапазона, тело < 40% | 40×(wick/body) + 40×(wick_dominance) + 20×(position) |
| Bearish Pin Bar | Верхний фитиль > 60%, тело < 40% | Аналогично |
| Inside Bar | `curr_high <= prev_high AND curr_low >= prev_low` | 50 + 30×(compression) + 20×(mother_bar_size) |

**Kelly Criterion (Position Sizing):**

```
kelly_f = (p × b - q) / b
  p = win_rate
  b = avg_win / avg_loss
  q = 1 - p

Применяется quarter Kelly: kelly_pct = kelly_f × 0.25
Ограничения: от 0.5% до 10% капитала
Если < 10 сделок в истории → фиксированные 2% риска
```

---

## Общий Data Flow (все стратегии)

```
Биржа (OHLCV, Orders)
    |
    v
BotOrchestrator._main_loop() --- каждые 1-5 сек
    |
    |-> Grid:  _process_grid_orders()     ->  Проверка исполнения ордеров
    |-> DCA:   _process_dca_logic()       ->  Проверка TP/SL/safety orders
    |-> SMC:   _process_smc_logic()       ->  TP/SL каждую сек, OHLCV-анализ каждые 300 сек
    |-> TF:    _process_trend_follower()  ->  Entry/exit signals
    |
    | (параллельно, каждые 60 сек)
    |-> _regime_monitor_loop()  ->  MarketRegimeDetector  ->  Redis (не влияет на торговлю)
    |
    v
+----------------+    +----------------+    +----------------+
|  ByBit API     |    | Redis PubSub   |    |  PostgreSQL    |
| (ордера)       |    | (события)      |    | (состояние)    |
+----------------+    +-------+--------+    +----------------+
                              |
                      +-------v--------+
                      | Telegram Bot   |
                      | (уведомления)  |
                      +----------------+
```

---

## Нормализация статусов ордеров

`ByBitDirectClient` нормализует все статусы ордеров к CCXT-совместимым значениям:

| Bybit (native) | CCXT (normalized) | Описание |
|----------------|-------------------|----------|
| `"Filled"` | `"closed"` | Ордер исполнен |
| `"New"` | `"open"` | Ордер активен |
| `"PartiallyFilled"` | `"open"` | Частично исполнен |
| `"Cancelled"` | `"cancelled"` | Отменён |
| `"Rejected"` | `"rejected"` | Отклонён |

Функция `_normalize_order_status()` в `bot/api/bybit_direct_client.py` применяется в `fetch_open_orders()`, `fetch_order()`, `fetch_closed_orders()`.

---

## Сводная таблица стратегий

| Параметр | Grid | DCA | Trend Follower | Hybrid | SMC |
|----------|------|-----|----------------|--------|-----|
| **Тип рынка** | Боковик (range) | Нисходящий тренд | Любой тренд | Grid+DCA всегда | Любой (институц.) |
| **Таймфреймы** | 1 | 1 | 1 | 1 | 4 (D1, H4, H1, M15) |
| **Тип ордеров** | Limit | Market + Limit (SO) | Limit (вход), Market (выход) | Limit + Market | Limit/Market |
| **Ключевой индикатор** | ATR, цена | EMA, RSI, BB, Volume | EMA, ATR, RSI | ADX, BB width | Swing Points, OB, FVG |
| **Вход** | Автоматический (сетка) | Confluence score >= 0.6 | Pullback/Breakout + volume | Grid + DCA параллельно | Паттерн + зона + R:R >= 2.5 |
| **Выход** | Counter-order (наценка) | TP / SL / Trailing | TP / SL / Trailing / Partial | Grid + DCA параллельно | TP / SL / Trailing / Kelly |
| **Риск-менеджмент** | Drawdown 10%, SL 5% | Daily loss $500, 5 consecutive | 1% risk, 20% exposure | По каждому движку | 2% risk, Kelly Criterion |
| **Макс. позиций** | 25 ордеров | Max concurrent deals | 20 | 25 + deals | 3 сигнала |

---

*Документ отражает реальное поведение кода TRADERAGENT v2.0 по состоянию на 2026-02-23*

*Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>*
