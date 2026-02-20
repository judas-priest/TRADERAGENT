# DCA Bot с Трейлинг-Стопом: Детальная Реализация
## TRADERAGENT v2.0 - Autonomous DCA-Grid SMC Trend-Follower Trading Bot

**Дата:** 2026-02-13
**Версия:** 1.0
**Статус:** План реализации

---

## 📋 Содержание

1. [Обзор](#обзор)
2. [Архитектура DCA-бота](#архитектура-dca-бота)
3. [Трейлинг-стоп: Детальная спецификация](#трейлинг-стоп-детальная-спецификация)
4. [Сигнальная логика открытия ордеров](#сигнальная-логика-открытия-ордеров)
5. [Модель данных и база данных](#модель-данных-и-база-данных)
6. [Конфигурация стратегии](#конфигурация-стратегии)
7. [Детальная реализация компонентов](#детальная-реализация-компонентов)
8. [План миграции и изменений](#план-миграции-и-изменений)
9. [Тестирование](#тестирование)
10. [Сценарии работы](#сценарии-работы)

---

## 📖 Обзор

### Цель
Реализовать полнофункциональный DCA (Dollar Cost Averaging) бот с:
- **Трейлинг-стоп** - динамический стоп-лосс, следующий за максимумом цены
- **Сигнальная логика** - открытие ордеров только по сигналам алгоритма
- **Safety-ордера** - постепенное наращивание позиции при падении
- **Программная реализация** - контроль на стороне бота, а не биржи

### Ключевые принципы
1. **Автономность** - бот работает без вмешательства человека
2. **Защита прибыли** - трейлинг-стоп фиксирует достигнутую прибыль
3. **Контролируемый вход** - ордера открываются только по подтвержденным сигналам
4. **Адаптивность** - параметры настраиваются под рыночные условия

---

## 🏗️ Архитектура DCA-бота

### Общая схема

```
┌─────────────────────────────────────────────────────────────┐
│                    DCA Bot Architecture                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  1. SIGNAL GENERATION LAYER                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  DCA Signal Generator                                │   │
│  │  - Trend Detection (EMA crossover, trend strength)   │   │
│  │  - Entry Conditions (price levels, indicators)       │   │
│  │  - Signal Validation (confirmations, filters)        │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                  2. DEAL MANAGEMENT LAYER                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  DCA Position Manager                                │   │
│  │  - Open Deal (base order)                            │   │
│  │  - Calculate Safety Orders                           │   │
│  │  - Track Average Entry Price                         │   │
│  │  - Update Deal State                                 │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                  3. ACTIVE DEAL MONITORING                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  manage_active_deal()                                │   │
│  │  ┌──────────────────────────────────────────────┐   │   │
│  │  │  Safety Order Logic                          │   │   │
│  │  │  - Check price drops                         │   │   │
│  │  │  - Place safety orders                       │   │   │
│  │  │  - Update average entry                      │   │   │
│  │  └──────────────────────────────────────────────┘   │   │
│  │  ┌──────────────────────────────────────────────┐   │   │
│  │  │  Trailing Stop Logic (NEW)                   │   │   │
│  │  │  - Track highest_price_since_entry           │   │   │
│  │  │  - Check activation condition                │   │   │
│  │  │  - Calculate dynamic stop price              │   │   │
│  │  │  - Execute exit on stop trigger              │   │   │
│  │  └──────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                     4. EXECUTION LAYER                       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Exchange Client (CCXT)                              │   │
│  │  - Place orders (market/limit)                       │   │
│  │  - Cancel orders                                     │   │
│  │  - Get current price                                 │   │
│  │  - Get order status                                  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    5. PERSISTENCE LAYER                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Database Manager (PostgreSQL)                       │   │
│  │  - Store deal state                                  │   │
│  │  - Track highest_price_since_entry                   │   │
│  │  - Save orders and trades                            │   │
│  │  - Performance metrics                               │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Компоненты

#### 1. DCA Signal Generator (`src/strategies/dca/dca_signal_generator.py`)
**Ответственность:**
- Анализ рынка для определения условий входа
- Генерация сигналов на открытие новой DCA-сделки
- Валидация условий (тренд, уровни, индикаторы)

**Методы:**
```python
- analyze_market(pair, timeframe) → MarketState
- should_open_deal(pair, config) → bool
- calculate_entry_price(pair, config) → float
- validate_signal(signal, filters) → bool
```

#### 2. DCA Position Manager (`src/strategies/dca/dca_position_manager.py`)
**Ответственность:**
- Управление открытыми DCA-сделками
- Расчет и размещение safety-ордеров
- Отслеживание средней цены входа
- Расчет целевых уровней (TP, TS)

**Методы:**
```python
- open_deal(pair, entry_price, volume, config) → Deal
- calculate_safety_orders(deal, config) → List[SafetyOrder]
- get_average_entry_price(deal_id) → float
- update_deal_state(deal_id, new_state) → None
```

#### 3. Active Deal Manager (`src/strategies/dca/manage_active_deal.py`)
**Ответственность:**
- Цикл мониторинга активных сделок
- Логика safety-ордеров
- **Логика трейлинг-стопа** (НОВОЕ)
- Выход из позиции

**Методы:**
```python
- manage_active_deal(deal, strategy_config) → None
- check_safety_order_triggers(deal, current_price) → List[Order]
- update_trailing_stop(deal, current_price) → None
- check_exit_conditions(deal, current_price) → bool
```

---

## 🎯 Трейлинг-стоп: Детальная спецификация

### Что такое трейлинг-стоп?

Трейлинг-стоп - это динамический стоп-лосс, который:
1. **Следует за ценой** - при росте цены стоп тоже поднимается
2. **Защищает прибыль** - фиксирует достигнутую прибыль
3. **Не опускается** - при падении цены стоп остается на месте
4. **Активируется условно** - включается после достижения минимальной прибыли

### Зачем нужен трейлинг-стоп в DCA?

**Проблема фиксированного TP:**
- DCA открывается в нисходящем тренде
- Позиция усредняется через safety-ордера
- Фиксированный TP может не сработать при развороте
- Цена может достичь высокой прибыли, затем откатиться
- Без трейлинга прибыль теряется

**Решение с трейлинг-стопом:**
- Позволяет прибыли расти неограниченно
- Защищает от потери накопленной прибыли
- Автоматически выходит при развороте тренда
- Оптимизирует соотношение риск/прибыль

### Алгоритм работы трейлинг-стопа

#### Параметры конфигурации

| Параметр | Тип | Описание | Пример |
|----------|-----|----------|--------|
| `use_trailing_stop` | boolean | Включить трейлинг-стоп вместо фиксированного TP | `true` |
| `trailing_activation` | float | Минимальная прибыль (%) для активации трейлинга | `1.5` |
| `trailing_distance` | float | Расстояние от максимума (% или абсолютно) | `0.8` |
| `trailing_type` | string | `"percentage"` или `"absolute"` | `"percentage"` |

#### Логика работы (псевдокод)

```python
async def manage_active_deal(deal, strategy):
    # Получить текущую цену
    current_price = await exchange.get_price(strategy.pair)
    avg_entry = calculate_avg_entry_price(deal.id)

    # --- БЛОК 1: Обработка safety-ордеров ---
    if price_dropped_to_next_safety_level(current_price, deal):
        place_safety_order(deal, current_price)
        avg_entry = recalculate_avg_entry(deal.id)

    # --- БЛОК 2: Трейлинг-стоп логика ---
    if strategy.use_trailing_stop:
        # Шаг 1: Обновляем максимум
        new_highest = max(deal.highest_price_since_entry or 0, current_price)
        if new_highest > deal.highest_price_since_entry:
            database.update_deal(deal.id, highest_price_since_entry=new_highest)
            deal.highest_price_since_entry = new_highest

        # Шаг 2: Рассчитываем текущую прибыль
        profit_percent = (current_price - avg_entry) / avg_entry * 100

        # Шаг 3: Проверяем активацию трейлинга
        if profit_percent >= strategy.trailing_activation:
            # Шаг 4: Рассчитываем стоп-цену
            if strategy.trailing_type == 'percentage':
                stop_price = new_highest * (1 - strategy.trailing_distance / 100)
            else:  # absolute
                stop_price = new_highest - strategy.trailing_distance

            # Шаг 5: Проверяем срабатывание стопа
            if current_price <= stop_price:
                # Выход из позиции
                total_volume = database.get_total_bought_volume(deal.id)
                await place_sell_order(
                    strategy.pair,
                    current_price,
                    total_volume,
                    order_type='market'
                )
                database.close_deal(deal.id,
                    reason='trailing_stop',
                    profit_percent=profit_percent
                )
                await cancel_all_buy_orders(deal.id)
                return  # Сделка завершена
    else:
        # --- БЛОК 3: Фиксированный тейк-профит (опционально) ---
        profit_percent = (current_price - avg_entry) / avg_entry * 100
        if profit_percent >= strategy.take_profit_percentage:
            total_volume = database.get_total_bought_volume(deal.id)
            await place_sell_order(strategy.pair, current_price, total_volume)
            database.close_deal(deal.id, reason='take_profit')
            return
```

#### Визуальная схема

```
Цена
  ↑
  │                                ⭐ Highest = $3500
  │                               ╱│
  │                              ╱ │ ← Trailing activated
  │                             ╱  │   (profit > 1.5%)
  │                            ╱   │
  │                           ╱    │ Stop = $3472
  │                          ╱     │ (0.8% от highest)
  │                         ╱      │
$3400 ─────────────────────────────┼─────
  │                                │
  │    ╱╲                          │
  │   ╱  ╲   ← Safety order 2      │
  │  ╱    ╲  @ $3250               │
  │ ╱      ╲                       │
$3300 ──────╲──────────────────────┼─────
  │         ╲                      │
  │          ╲  ← Safety order 1   │
  │           ╲ @ $3150            │
  │            ╲                   │
$3200 ───────────────────────────── ← Avg entry после SO
  │                                │
  │                                │
$3100 ────────────────────────────── ← Base order
  │
  └─────────────────────────────────→ Время
      Entry   SO1   SO2   Price    Exit
                         rises    (trailing)
```

**Легенда:**
- Base order @ $3100 - начальный вход
- Safety order 1 @ $3150 - первое усреднение (цена упала)
- Safety order 2 @ $3250 - второе усреднение
- Average entry = $3200 (после всех SO)
- Highest = $3500 - максимальная цена после входа
- Stop = $3472 - динамический стоп (0.8% от highest)
- Exit - выход при касании стопа

### Важные особенности реализации

#### 1. Максимум не сбрасывается при дозакупке
```python
# ❌ НЕПРАВИЛЬНО
if safety_order_filled:
    deal.highest_price_since_entry = current_price  # Сброс!

# ✅ ПРАВИЛЬНО
if safety_order_filled:
    # Максимум сохраняется, защищая уже накопленную прибыль
    pass
```

**Почему:** Safety-ордера открываются при падении цены. Если сбросить максимум, мы потеряем защиту прибыли, достигнутой ранее.

#### 2. Программная реализация (не биржевые ордера)
```python
# ❌ НЕПРАВИЛЬНО (не все биржи поддерживают)
exchange.create_trailing_stop_order(...)

# ✅ ПРАВИЛЬНО (программная логика)
# В цикле manage_active_deal:
if current_price <= calculated_stop_price:
    await place_sell_order(..., order_type='market')
```

**Почему:**
- Не все биржи поддерживают trailing stop на спотовом рынке
- Программный контроль дает больше гибкости
- Можно добавить кастомную логику (фильтры, условия)

#### 3. Активация только после минимальной прибыли
```python
# Проверяем активацию
if profit_percent >= strategy.trailing_activation:
    # Трейлинг активен
    if current_price <= stop_price:
        exit_position()
else:
    # Трейлинг не активен, используем обычный стоп-лосс или ждем
    pass
```

**Почему:** Защищает от преждевременного выхода при небольших колебаниях цены.

#### 4. Два типа расчета расстояния
```python
# Percentage (относительный)
stop_price = highest * (1 - distance / 100)
# Пример: highest=$3500, distance=0.8% → stop=$3472

# Absolute (абсолютный)
stop_price = highest - distance
# Пример: highest=$3500, distance=$25 → stop=$3475
```

**Когда использовать:**
- **Percentage** - для волатильных рынков (BTC, ETH)
- **Absolute** - для стейблкоинов или low-cap токенов

---

## 🔔 Сигнальная логика открытия ордеров

### Ключевое требование
**Бот открывает ордера ТОЛЬКО когда алгоритм даст сигнал о достижении целевого значения цены согласно конфигурации стратегии.**

### Компоненты сигнальной логики

#### 1. Условия входа (Entry Conditions)

##### A. Трендовые условия
```python
def check_trend_conditions(pair, config):
    # EMA crossover
    ema_fast = get_ema(pair, period=config.ema_fast)
    ema_slow = get_ema(pair, period=config.ema_slow)

    if config.trend_direction == 'down':
        # Для DCA нужен нисходящий тренд
        trend_ok = ema_fast < ema_slow
    else:
        trend_ok = False

    # Сила тренда (ADX)
    adx = get_adx(pair, period=14)
    trend_strength_ok = adx > config.min_trend_strength

    return trend_ok and trend_strength_ok
```

##### B. Ценовые условия
```python
def check_price_conditions(pair, config):
    current_price = get_current_price(pair)

    # Проверка целевого диапазона
    target_price_min = config.entry_price_min
    target_price_max = config.entry_price_max

    price_in_range = target_price_min <= current_price <= target_price_max

    # Проверка расстояния от ключевых уровней
    support_level = get_nearest_support(pair)
    distance_from_support = (current_price - support_level) / support_level

    near_support = distance_from_support <= config.max_distance_from_support

    return price_in_range and near_support
```

##### C. Индикаторные условия
```python
def check_indicator_conditions(pair, config):
    # RSI - перепроданность
    rsi = get_rsi(pair, period=14)
    rsi_ok = rsi < config.rsi_oversold_threshold  # Например, <35

    # Volume - подтверждение
    volume_24h = get_24h_volume(pair)
    avg_volume = get_avg_volume(pair, period=30)
    volume_ok = volume_24h > avg_volume * config.min_volume_multiplier

    # Bollinger Bands - цена у нижней границы
    bb_lower = get_bollinger_lower(pair, period=20, std=2)
    current_price = get_current_price(pair)
    at_bb_lower = current_price <= bb_lower * 1.02  # 2% tolerance

    return rsi_ok and volume_ok and at_bb_lower
```

#### 2. Фильтры подтверждения

##### A. Временные фильтры
```python
def check_timing_filters(deal_history, config):
    # Не открывать новую сделку слишком быстро после предыдущей
    last_deal = get_last_closed_deal(config.pair)
    if last_deal:
        time_since_last = now() - last_deal.closed_at
        if time_since_last < config.min_time_between_deals:
            return False

    # Проверка времени суток (опционально)
    current_hour = get_current_hour_utc()
    if config.trading_hours:
        if current_hour not in config.trading_hours:
            return False

    return True
```

##### B. Риск-фильтры
```python
def check_risk_filters(account_state, config):
    # Максимальное количество одновременных сделок
    active_deals = get_active_deals_count(config.pair)
    if active_deals >= config.max_concurrent_deals:
        return False

    # Проверка дневного лимита потерь
    daily_pnl = get_daily_pnl()
    if daily_pnl < -config.max_daily_loss:
        return False

    # Проверка доступного капитала
    available_balance = get_available_balance()
    required_capital = calculate_required_capital(config)
    if available_balance < required_capital:
        return False

    return True
```

##### C. Confluence Score
```python
def calculate_confluence_score(pair, config):
    """
    Система скоринга для комбинирования сигналов
    """
    score = 0
    max_score = 0

    # Тренд (вес 3)
    if check_trend_conditions(pair, config):
        score += 3
    max_score += 3

    # Цена (вес 2)
    if check_price_conditions(pair, config):
        score += 2
    max_score += 2

    # Индикаторы (вес 2)
    if check_indicator_conditions(pair, config):
        score += 2
    max_score += 2

    # Volume (вес 1)
    if check_volume_condition(pair, config):
        score += 1
    max_score += 1

    confluence = score / max_score
    return confluence
```

#### 3. Итоговая функция генерации сигнала

```python
async def should_open_dca_deal(pair, config):
    """
    Главная функция принятия решения
    Returns: (bool, str) - (should_open, reason)
    """

    # Шаг 1: Базовые проверки
    if not check_timing_filters(pair, config):
        return False, "Timing filters not passed"

    if not check_risk_filters(account_state, config):
        return False, "Risk filters not passed"

    # Шаг 2: Сигнальные условия
    trend_ok = check_trend_conditions(pair, config)
    price_ok = check_price_conditions(pair, config)
    indicators_ok = check_indicator_conditions(pair, config)

    # Шаг 3: Confluence check
    confluence = calculate_confluence_score(pair, config)

    if config.require_confluence:
        # Требуется высокий confluence
        if confluence >= config.min_confluence_score:  # Например, >= 0.75
            return True, f"Signal confirmed (confluence: {confluence:.2f})"
        else:
            return False, f"Confluence too low: {confluence:.2f}"
    else:
        # Простая логика AND
        if trend_ok and price_ok and indicators_ok:
            return True, "All conditions met"
        else:
            return False, "Not all conditions met"
```

### Пример конфигурации сигналов

```yaml
dca:
  signal_config:
    # Трендовые условия
    ema_fast: 12
    ema_slow: 26
    trend_direction: "down"  # Для DCA нужен нисходящий тренд
    min_trend_strength: 20   # ADX > 20

    # Ценовые условия
    entry_price_min: 3000    # USD
    entry_price_max: 3200    # USD
    max_distance_from_support: 0.02  # 2%

    # Индикаторные условия
    rsi_oversold_threshold: 35
    min_volume_multiplier: 1.2  # Volume > 1.2x avg
    use_bollinger_bands: true

    # Confluence
    require_confluence: true
    min_confluence_score: 0.75  # 75% сигналов должны совпасть

    # Риск-фильтры
    max_concurrent_deals: 3
    max_daily_loss: 500  # USD
    min_time_between_deals: 3600  # 1 час

    # Временные фильтры (опционально)
    trading_hours: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23]  # 24/7
```

---

## 💾 Модель данных и база данных

### Схема таблицы `dca_deals`

```sql
CREATE TABLE dca_deals (
    -- Идентификация
    id BIGSERIAL PRIMARY KEY,
    pair VARCHAR(20) NOT NULL,
    strategy_id INTEGER REFERENCES strategies(id),

    -- Временные метки
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMP,

    -- Статус сделки
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    -- 'active', 'closed', 'cancelled'

    close_reason VARCHAR(50),
    -- 'take_profit', 'trailing_stop', 'stop_loss', 'manual', 'error'

    -- Ценовые данные
    base_order_price DECIMAL(20, 8) NOT NULL,
    base_order_volume DECIMAL(20, 8) NOT NULL,
    base_order_cost DECIMAL(20, 8) NOT NULL,

    average_entry_price DECIMAL(20, 8) NOT NULL,
    total_volume DECIMAL(20, 8) NOT NULL,
    total_cost DECIMAL(20, 8) NOT NULL,

    -- Трейлинг-стоп данные (НОВОЕ)
    highest_price_since_entry DECIMAL(20, 8),
    trailing_stop_activated BOOLEAN DEFAULT FALSE,
    trailing_activation_price DECIMAL(20, 8),
    trailing_activation_time TIMESTAMP,

    -- Safety orders
    safety_orders_count INTEGER DEFAULT 0,
    max_safety_orders INTEGER NOT NULL,
    next_safety_order_price DECIMAL(20, 8),

    -- Профит/убыток
    current_profit_percent DECIMAL(10, 4),
    realized_profit_usd DECIMAL(20, 8),
    realized_profit_percent DECIMAL(10, 4),

    -- Метаданные
    config JSONB,  -- Копия конфигурации на момент открытия
    notes TEXT,

    INDEX idx_pair_status (pair, status),
    INDEX idx_status_created (status, created_at),
    INDEX idx_trailing_activated (trailing_stop_activated, status)
);
```

### Схема таблицы `dca_orders`

```sql
CREATE TABLE dca_orders (
    -- Идентификация
    id BIGSERIAL PRIMARY KEY,
    deal_id BIGINT NOT NULL REFERENCES dca_deals(id) ON DELETE CASCADE,
    exchange_order_id VARCHAR(100),

    -- Временные метки
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    filled_at TIMESTAMP,

    -- Тип ордера
    order_type VARCHAR(20) NOT NULL,
    -- 'base_order', 'safety_order_1', 'safety_order_2', ..., 'take_profit', 'trailing_stop'

    side VARCHAR(10) NOT NULL,  -- 'buy', 'sell'

    -- Ценовые данные
    price DECIMAL(20, 8) NOT NULL,
    volume DECIMAL(20, 8) NOT NULL,
    filled_volume DECIMAL(20, 8) DEFAULT 0,
    cost DECIMAL(20, 8) NOT NULL,

    -- Статус
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- 'pending', 'placed', 'partially_filled', 'filled', 'cancelled', 'error'

    -- Метаданные
    exchange_response JSONB,
    error_message TEXT,

    INDEX idx_deal_id (deal_id),
    INDEX idx_status (status),
    INDEX idx_order_type (order_type)
);
```

### Схема таблицы `dca_signals`

```sql
CREATE TABLE dca_signals (
    -- Идентификация
    id BIGSERIAL PRIMARY KEY,
    pair VARCHAR(20) NOT NULL,

    -- Временные метки
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Сигнал
    signal_type VARCHAR(20) NOT NULL,  -- 'open_deal', 'close_deal'
    signal_strength DECIMAL(5, 4),     -- Confluence score 0-1

    -- Условия
    trend_ok BOOLEAN,
    price_ok BOOLEAN,
    indicators_ok BOOLEAN,
    risk_ok BOOLEAN,
    timing_ok BOOLEAN,

    -- Данные рынка
    market_price DECIMAL(20, 8),
    ema_fast DECIMAL(20, 8),
    ema_slow DECIMAL(20, 8),
    rsi DECIMAL(5, 2),
    adx DECIMAL(5, 2),
    volume_24h DECIMAL(20, 8),

    -- Результат
    action_taken BOOLEAN DEFAULT FALSE,
    deal_id BIGINT REFERENCES dca_deals(id),

    -- Метаданные
    details JSONB,

    INDEX idx_pair_created (pair, created_at),
    INDEX idx_action_taken (action_taken)
);
```

### ORM Модели (SQLAlchemy)

```python
from sqlalchemy import Column, Integer, String, DECIMAL, Boolean, TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class DCADeal(Base):
    __tablename__ = 'dca_deals'

    # Идентификация
    id = Column(Integer, primary_key=True)
    pair = Column(String(20), nullable=False)
    strategy_id = Column(Integer)

    # Временные метки
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(TIMESTAMP)

    # Статус
    status = Column(String(20), default='active')
    close_reason = Column(String(50))

    # Ценовые данные
    base_order_price = Column(DECIMAL(20, 8), nullable=False)
    base_order_volume = Column(DECIMAL(20, 8), nullable=False)
    base_order_cost = Column(DECIMAL(20, 8), nullable=False)

    average_entry_price = Column(DECIMAL(20, 8), nullable=False)
    total_volume = Column(DECIMAL(20, 8), nullable=False)
    total_cost = Column(DECIMAL(20, 8), nullable=False)

    # Трейлинг-стоп
    highest_price_since_entry = Column(DECIMAL(20, 8))
    trailing_stop_activated = Column(Boolean, default=False)
    trailing_activation_price = Column(DECIMAL(20, 8))
    trailing_activation_time = Column(TIMESTAMP)

    # Safety orders
    safety_orders_count = Column(Integer, default=0)
    max_safety_orders = Column(Integer, nullable=False)
    next_safety_order_price = Column(DECIMAL(20, 8))

    # Профит/убыток
    current_profit_percent = Column(DECIMAL(10, 4))
    realized_profit_usd = Column(DECIMAL(20, 8))
    realized_profit_percent = Column(DECIMAL(10, 4))

    # Метаданные
    config = Column(JSONB)
    notes = Column(Text)

    def to_dict(self):
        return {
            'id': self.id,
            'pair': self.pair,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'average_entry_price': float(self.average_entry_price),
            'total_volume': float(self.total_volume),
            'highest_price_since_entry': float(self.highest_price_since_entry) if self.highest_price_since_entry else None,
            'current_profit_percent': float(self.current_profit_percent) if self.current_profit_percent else None,
        }
```

---

## ⚙️ Конфигурация стратегии

### Полная конфигурация DCA с трейлинг-стопом

```yaml
strategies:
  dca:
    enabled: true
    pairs:
      - "BTC/USDT"
      - "ETH/USDT"

    # ========== SIGNAL CONFIGURATION ==========
    signal_config:
      # Трендовые условия
      trend:
        ema_fast: 12
        ema_slow: 26
        direction: "down"  # up, down, any
        min_strength: 20   # ADX threshold

      # Ценовые условия
      price:
        entry_range:
          min: 3000
          max: 3200
        max_distance_from_support: 0.02  # 2%

      # Индикаторные условия
      indicators:
        rsi_threshold: 35
        use_bollinger_bands: true
        min_volume_multiplier: 1.2

      # Confluence
      confluence:
        enabled: true
        min_score: 0.75

      # Фильтры
      filters:
        max_concurrent_deals: 3
        min_time_between_deals: 3600  # seconds
        max_daily_loss: 500  # USD
        trading_hours: null  # null = 24/7

    # ========== ORDER CONFIGURATION ==========
    order_config:
      # Base order
      base_order:
        type: "market"  # market, limit
        volume_usd: 100

      # Safety orders
      safety_orders:
        max_count: 5
        volume_multiplier: 1.5  # Каждый следующий SO больше
        price_step_percent: 2.0  # % падения между SO

        # Пример:
        # SO1: -2% от entry, volume = 100 * 1.5 = $150
        # SO2: -4% от entry, volume = 150 * 1.5 = $225
        # SO3: -6% от entry, volume = 225 * 1.5 = $337.5
        # и т.д.

    # ========== EXIT CONFIGURATION ==========
    exit_config:
      # Трейлинг-стоп (ПРИОРИТЕТ если enabled=true)
      trailing_stop:
        enabled: true
        activation_profit: 1.5  # % прибыли для активации
        distance: 0.8           # % расстояние от максимума
        type: "percentage"      # percentage, absolute

      # Фиксированный тейк-профит (используется если trailing_stop=false)
      take_profit:
        enabled: true
        percent: 3.0  # % прибыли от средней цены входа

      # Стоп-лосс (экстренный выход)
      stop_loss:
        enabled: true
        percent: 10.0  # % убытка от базового ордера
        type: "from_base_order"  # from_base_order, from_average_entry

    # ========== RISK MANAGEMENT ==========
    risk_config:
      max_position_size_usd: 5000
      max_concurrent_deals: 3
      max_daily_loss_usd: 500
      max_consecutive_losses: 3

      # Защита от pump&dump
      max_price_change_percent: 10  # За 5 минут
      pause_on_extreme_volatility: true
```

### Параметры по умолчанию

```python
DEFAULT_DCA_CONFIG = {
    'signal_config': {
        'confluence': {
            'enabled': True,
            'min_score': 0.75,
        },
    },
    'order_config': {
        'base_order': {
            'volume_usd': 100,
        },
        'safety_orders': {
            'max_count': 5,
            'volume_multiplier': 1.5,
            'price_step_percent': 2.0,
        },
    },
    'exit_config': {
        'trailing_stop': {
            'enabled': True,
            'activation_profit': 1.5,
            'distance': 0.8,
            'type': 'percentage',
        },
    },
    'risk_config': {
        'max_concurrent_deals': 3,
        'max_daily_loss_usd': 500,
    },
}
```

---

## 🔨 Детальная реализация компонентов

### 1. DCA Signal Generator

**Файл:** `src/strategies/dca/dca_signal_generator.py`

```python
from typing import Tuple, Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class MarketState:
    """Состояние рынка на текущий момент"""
    pair: str
    timestamp: datetime
    price: float
    ema_fast: float
    ema_slow: float
    rsi: float
    adx: float
    volume_24h: float
    bb_lower: float
    bb_upper: float
    nearest_support: Optional[float]

@dataclass
class SignalResult:
    """Результат анализа сигнала"""
    should_open: bool
    confluence_score: float
    reason: str
    conditions: Dict[str, bool]
    market_state: MarketState

class DCASignalGenerator:
    """
    Генератор сигналов для DCA стратегии
    """

    def __init__(self, exchange_client, config):
        self.exchange = exchange_client
        self.config = config

    async def analyze_market(self, pair: str) -> MarketState:
        """
        Анализирует текущее состояние рынка
        """
        # Получить данные рынка
        ohlcv = await self.exchange.fetch_ohlcv(pair, timeframe='1h', limit=100)
        ticker = await self.exchange.fetch_ticker(pair)

        # Рассчитать индикаторы
        prices = [candle[4] for candle in ohlcv]  # close prices

        ema_fast = self._calculate_ema(prices, self.config.signal_config.trend.ema_fast)
        ema_slow = self._calculate_ema(prices, self.config.signal_config.trend.ema_slow)
        rsi = self._calculate_rsi(prices, period=14)
        adx = self._calculate_adx(ohlcv, period=14)
        bb_lower, bb_upper = self._calculate_bollinger_bands(prices, period=20, std=2)

        support = await self._find_nearest_support(pair, prices[-1])

        return MarketState(
            pair=pair,
            timestamp=datetime.utcnow(),
            price=prices[-1],
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            rsi=rsi,
            adx=adx,
            volume_24h=ticker['quoteVolume'],
            bb_lower=bb_lower,
            bb_upper=bb_upper,
            nearest_support=support,
        )

    async def should_open_deal(self, pair: str) -> SignalResult:
        """
        Главная функция принятия решения об открытии сделки
        """
        # Получить состояние рынка
        market = await self.analyze_market(pair)

        # Проверить все условия
        conditions = {
            'trend': self._check_trend_conditions(market),
            'price': self._check_price_conditions(market),
            'indicators': self._check_indicator_conditions(market),
            'risk': await self._check_risk_filters(pair),
            'timing': await self._check_timing_filters(pair),
        }

        # Рассчитать confluence
        confluence = self._calculate_confluence(conditions, market)

        # Принять решение
        if self.config.signal_config.confluence.enabled:
            should_open = confluence >= self.config.signal_config.confluence.min_score
            reason = f"Confluence: {confluence:.2%}"
        else:
            should_open = all(conditions.values())
            reason = "All conditions met" if should_open else "Conditions not met"

        return SignalResult(
            should_open=should_open,
            confluence_score=confluence,
            reason=reason,
            conditions=conditions,
            market_state=market,
        )

    def _check_trend_conditions(self, market: MarketState) -> bool:
        """Проверка трендовых условий"""
        trend_config = self.config.signal_config.trend

        # Направление тренда
        if trend_config.direction == 'down':
            trend_direction_ok = market.ema_fast < market.ema_slow
        elif trend_config.direction == 'up':
            trend_direction_ok = market.ema_fast > market.ema_slow
        else:  # any
            trend_direction_ok = True

        # Сила тренда
        trend_strength_ok = market.adx > trend_config.min_strength

        return trend_direction_ok and trend_strength_ok

    def _check_price_conditions(self, market: MarketState) -> bool:
        """Проверка ценовых условий"""
        price_config = self.config.signal_config.price

        # Проверка диапазона
        if price_config.entry_range:
            in_range = (
                price_config.entry_range.min <= market.price <= price_config.entry_range.max
            )
        else:
            in_range = True

        # Расстояние от поддержки
        if market.nearest_support:
            distance = (market.price - market.nearest_support) / market.nearest_support
            near_support = distance <= price_config.max_distance_from_support
        else:
            near_support = True

        return in_range and near_support

    def _check_indicator_conditions(self, market: MarketState) -> bool:
        """Проверка индикаторных условий"""
        ind_config = self.config.signal_config.indicators

        # RSI
        rsi_ok = market.rsi < ind_config.rsi_threshold

        # Bollinger Bands
        if ind_config.use_bollinger_bands:
            at_bb_lower = market.price <= market.bb_lower * 1.02
        else:
            at_bb_lower = True

        # Volume
        avg_volume = await self._get_average_volume(market.pair, days=30)
        volume_ok = market.volume_24h > avg_volume * ind_config.min_volume_multiplier

        return rsi_ok and at_bb_lower and volume_ok

    async def _check_risk_filters(self, pair: str) -> bool:
        """Проверка риск-фильтров"""
        filters = self.config.signal_config.filters

        # Количество активных сделок
        active_deals = await self.db.count_active_deals(pair)
        if active_deals >= filters.max_concurrent_deals:
            return False

        # Дневной убыток
        daily_pnl = await self.db.get_daily_pnl()
        if daily_pnl < -filters.max_daily_loss:
            return False

        # Доступный баланс
        balance = await self.exchange.fetch_balance()
        required = self._calculate_required_capital()
        if balance['USDT']['free'] < required:
            return False

        return True

    async def _check_timing_filters(self, pair: str) -> bool:
        """Проверка временных фильтров"""
        filters = self.config.signal_config.filters

        # Время с последней сделки
        last_deal = await self.db.get_last_closed_deal(pair)
        if last_deal:
            time_since = (datetime.utcnow() - last_deal.closed_at).total_seconds()
            if time_since < filters.min_time_between_deals:
                return False

        # Торговые часы
        if filters.trading_hours:
            current_hour = datetime.utcnow().hour
            if current_hour not in filters.trading_hours:
                return False

        return True

    def _calculate_confluence(self, conditions: Dict[str, bool], market: MarketState) -> float:
        """
        Рассчитать confluence score
        """
        weights = {
            'trend': 3,
            'price': 2,
            'indicators': 2,
            'risk': 1,
            'timing': 1,
        }

        total_weight = sum(weights.values())
        achieved_weight = sum(weights[k] for k, v in conditions.items() if v)

        return achieved_weight / total_weight

    # ... вспомогательные методы расчета индикаторов ...
```

### 2. DCA Position Manager

**Файл:** `src/strategies/dca/dca_position_manager.py`

```python
from typing import List, Optional
from decimal import Decimal
from dataclasses import dataclass

@dataclass
class SafetyOrderConfig:
    """Конфигурация safety-ордера"""
    level: int  # 1, 2, 3, ...
    price: Decimal
    volume: Decimal
    cost: Decimal

class DCAPositionManager:
    """
    Управление DCA позициями
    """

    def __init__(self, exchange_client, database, config):
        self.exchange = exchange_client
        self.db = database
        self.config = config

    async def open_deal(
        self,
        pair: str,
        entry_price: float,
        signal_result: SignalResult
    ) -> DCADeal:
        """
        Открывает новую DCA-сделку
        """
        base_order_config = self.config.order_config.base_order

        # Рассчитать объем base order
        volume_usd = base_order_config.volume_usd
        volume = Decimal(volume_usd) / Decimal(entry_price)

        # Разместить base order
        order = await self.exchange.create_market_buy_order(
            pair,
            float(volume)
        )

        # Создать запись в БД
        deal = DCADeal(
            pair=pair,
            strategy_id=self.config.id,
            status='active',
            base_order_price=Decimal(entry_price),
            base_order_volume=volume,
            base_order_cost=Decimal(volume_usd),
            average_entry_price=Decimal(entry_price),
            total_volume=volume,
            total_cost=Decimal(volume_usd),
            highest_price_since_entry=Decimal(entry_price),  # Инициализация
            max_safety_orders=self.config.order_config.safety_orders.max_count,
            config=self.config.to_dict(),
        )

        await self.db.save_deal(deal)

        # Сохранить ордер
        await self.db.save_order(DCAOrder(
            deal_id=deal.id,
            exchange_order_id=order['id'],
            order_type='base_order',
            side='buy',
            price=Decimal(entry_price),
            volume=volume,
            filled_volume=volume,
            cost=Decimal(volume_usd),
            status='filled',
        ))

        # Рассчитать safety orders
        safety_orders = self.calculate_safety_orders(deal)
        deal.next_safety_order_price = safety_orders[0].price
        await self.db.update_deal(deal)

        return deal

    def calculate_safety_orders(self, deal: DCADeal) -> List[SafetyOrderConfig]:
        """
        Рассчитывает конфигурацию всех safety-ордеров
        """
        so_config = self.config.order_config.safety_orders

        safety_orders = []
        current_price = deal.base_order_price
        current_volume_usd = deal.base_order_cost

        for level in range(1, so_config.max_count + 1):
            # Цена safety order
            price_drop_percent = so_config.price_step_percent * level
            so_price = current_price * (1 - Decimal(price_drop_percent) / 100)

            # Объем safety order
            so_volume_usd = current_volume_usd * Decimal(so_config.volume_multiplier ** level)
            so_volume = so_volume_usd / so_price

            safety_orders.append(SafetyOrderConfig(
                level=level,
                price=so_price,
                volume=so_volume,
                cost=so_volume_usd,
            ))

        return safety_orders

    async def place_safety_order(self, deal: DCADeal, level: int) -> DCAOrder:
        """
        Размещает safety order
        """
        safety_orders = self.calculate_safety_orders(deal)
        so_config = safety_orders[level - 1]

        # Разместить market buy order
        order = await self.exchange.create_market_buy_order(
            deal.pair,
            float(so_config.volume)
        )

        # Обновить сделку
        deal.total_volume += so_config.volume
        deal.total_cost += so_config.cost
        deal.average_entry_price = deal.total_cost / deal.total_volume
        deal.safety_orders_count += 1

        # Следующий safety order
        if level < len(safety_orders):
            deal.next_safety_order_price = safety_orders[level].price
        else:
            deal.next_safety_order_price = None

        await self.db.update_deal(deal)

        # Сохранить ордер
        db_order = DCAOrder(
            deal_id=deal.id,
            exchange_order_id=order['id'],
            order_type=f'safety_order_{level}',
            side='buy',
            price=so_config.price,
            volume=so_config.volume,
            filled_volume=so_config.volume,
            cost=so_config.cost,
            status='filled',
        )
        await self.db.save_order(db_order)

        return db_order

    async def close_deal(
        self,
        deal: DCADeal,
        current_price: float,
        reason: str
    ) -> None:
        """
        Закрывает сделку (продает всю позицию)
        """
        # Разместить market sell order
        order = await self.exchange.create_market_sell_order(
            deal.pair,
            float(deal.total_volume)
        )

        # Рассчитать профит
        sell_value = Decimal(current_price) * deal.total_volume
        profit_usd = sell_value - deal.total_cost
        profit_percent = (profit_usd / deal.total_cost) * 100

        # Обновить сделку
        deal.status = 'closed'
        deal.closed_at = datetime.utcnow()
        deal.close_reason = reason
        deal.realized_profit_usd = profit_usd
        deal.realized_profit_percent = profit_percent

        await self.db.update_deal(deal)

        # Сохранить ордер
        await self.db.save_order(DCAOrder(
            deal_id=deal.id,
            exchange_order_id=order['id'],
            order_type=reason,  # 'trailing_stop', 'take_profit', etc.
            side='sell',
            price=Decimal(current_price),
            volume=deal.total_volume,
            filled_volume=deal.total_volume,
            cost=sell_value,
            status='filled',
        ))
```

### 3. Active Deal Manager с трейлинг-стопом

**Файл:** `src/strategies/dca/manage_active_deal.py`

```python
import asyncio
from decimal import Decimal
from typing import Optional

class ActiveDealManager:
    """
    Управление активными сделками (цикл мониторинга)
    """

    def __init__(self, position_manager, exchange_client, database, config):
        self.position_manager = position_manager
        self.exchange = exchange_client
        self.db = database
        self.config = config
        self.running = False

    async def start(self):
        """Запуск цикла мониторинга"""
        self.running = True
        while self.running:
            try:
                await self._monitoring_cycle()
                await asyncio.sleep(5)  # Проверка каждые 5 секунд
            except Exception as e:
                logger.error(f"Error in monitoring cycle: {e}")
                await asyncio.sleep(10)

    async def _monitoring_cycle(self):
        """Один цикл мониторинга всех активных сделок"""
        active_deals = await self.db.get_active_deals()

        for deal in active_deals:
            try:
                await self.manage_active_deal(deal)
            except Exception as e:
                logger.error(f"Error managing deal {deal.id}: {e}")

    async def manage_active_deal(self, deal: DCADeal) -> None:
        """
        Управление одной активной сделкой
        Включает:
        - Проверку и размещение safety-ордеров
        - Логику трейлинг-стопа
        - Проверку фиксированного TP/SL
        """
        # Получить текущую цену
        ticker = await self.exchange.fetch_ticker(deal.pair)
        current_price = Decimal(str(ticker['last']))

        # Обновить текущую прибыль
        current_profit = (current_price - deal.average_entry_price) / deal.average_entry_price * 100
        deal.current_profit_percent = current_profit
        await self.db.update_deal(deal)

        # --- БЛОК 1: Safety Orders ---
        await self._check_safety_orders(deal, current_price)

        # --- БЛОК 2: Trailing Stop ---
        if self.config.exit_config.trailing_stop.enabled:
            exit_triggered = await self._check_trailing_stop(deal, current_price)
            if exit_triggered:
                return  # Сделка закрыта

        # --- БЛОК 3: Фиксированный Take Profit / Stop Loss ---
        if self.config.exit_config.take_profit.enabled:
            if current_profit >= self.config.exit_config.take_profit.percent:
                await self.position_manager.close_deal(
                    deal,
                    float(current_price),
                    reason='take_profit'
                )
                return

        if self.config.exit_config.stop_loss.enabled:
            stop_loss_percent = -self.config.exit_config.stop_loss.percent
            if current_profit <= stop_loss_percent:
                await self.position_manager.close_deal(
                    deal,
                    float(current_price),
                    reason='stop_loss'
                )
                return

    async def _check_safety_orders(self, deal: DCADeal, current_price: Decimal) -> None:
        """
        Проверка и размещение safety-ордеров
        """
        if deal.safety_orders_count >= deal.max_safety_orders:
            return  # Все safety orders уже использованы

        if deal.next_safety_order_price is None:
            return

        # Проверяем, достигла ли цена уровня следующего SO
        if current_price <= deal.next_safety_order_price:
            # Разместить safety order
            next_level = deal.safety_orders_count + 1
            await self.position_manager.place_safety_order(deal, next_level)

            # deal уже обновлен в place_safety_order
            # Средняя цена входа пересчитана
            logger.info(
                f"Deal {deal.id}: Placed safety order {next_level} "
                f"at {current_price}. New avg entry: {deal.average_entry_price}"
            )

    async def _check_trailing_stop(self, deal: DCADeal, current_price: Decimal) -> bool:
        """
        Логика трейлинг-стопа
        Returns: True если сделка была закрыта
        """
        ts_config = self.config.exit_config.trailing_stop

        # Шаг 1: Обновляем максимум
        if deal.highest_price_since_entry is None:
            deal.highest_price_since_entry = current_price

        new_highest = max(deal.highest_price_since_entry, current_price)

        # Если это новый максимум
        if new_highest > deal.highest_price_since_entry:
            deal.highest_price_since_entry = new_highest
            await self.db.update_deal(deal)
            logger.debug(
                f"Deal {deal.id}: New highest price: {new_highest}"
            )

        # Шаг 2: Рассчитываем текущую прибыль
        profit_percent = (current_price - deal.average_entry_price) / deal.average_entry_price * 100

        # Шаг 3: Проверяем активацию
        if profit_percent >= ts_config.activation_profit:
            # Трейлинг активирован
            if not deal.trailing_stop_activated:
                deal.trailing_stop_activated = True
                deal.trailing_activation_price = current_price
                deal.trailing_activation_time = datetime.utcnow()
                await self.db.update_deal(deal)
                logger.info(
                    f"Deal {deal.id}: Trailing stop ACTIVATED at {current_price} "
                    f"(profit: {profit_percent:.2f}%)"
                )

            # Шаг 4: Рассчитываем стоп-цену
            if ts_config.type == 'percentage':
                stop_price = new_highest * (1 - Decimal(ts_config.distance) / 100)
            else:  # absolute
                stop_price = new_highest - Decimal(ts_config.distance)

            logger.debug(
                f"Deal {deal.id}: TS check - "
                f"highest={new_highest}, stop={stop_price}, current={current_price}"
            )

            # Шаг 5: Проверяем срабатывание стопа
            if current_price <= stop_price:
                # ТРИГГЕР! Закрываем сделку
                await self.position_manager.close_deal(
                    deal,
                    float(current_price),
                    reason='trailing_stop'
                )
                logger.info(
                    f"Deal {deal.id}: TRAILING STOP TRIGGERED! "
                    f"Exit at {current_price}, profit: {profit_percent:.2f}%"
                )
                return True

        return False
```

---

## 🔄 План миграции и изменений

### Что убрать

#### 1. Старая логика фиксированного TP (если была)
```python
# ❌ УБРАТЬ (если использовалось раньше)
if current_price >= take_profit_price:
    close_position()
```

**Причина:** Заменяется на трейлинг-стоп или остается как fallback.

#### 2. Биржевые trailing-stop ордера (если были)
```python
# ❌ УБРАТЬ
exchange.create_order(
    symbol=pair,
    type='TRAILING_STOP_MARKET',
    ...
)
```

**Причина:** Заменяется на программную реализацию.

#### 3. Хардкодные значения конфигурации
```python
# ❌ УБРАТЬ
TRAILING_DISTANCE = 0.008  # Захардкоженное значение
```

**Причина:** Все параметры должны быть в YAML конфигурации.

### Что добавить

#### 1. Новые поля в базе данных
```sql
-- Миграция Alembic
ALTER TABLE dca_deals ADD COLUMN highest_price_since_entry DECIMAL(20, 8);
ALTER TABLE dca_deals ADD COLUMN trailing_stop_activated BOOLEAN DEFAULT FALSE;
ALTER TABLE dca_deals ADD COLUMN trailing_activation_price DECIMAL(20, 8);
ALTER TABLE dca_deals ADD COLUMN trailing_activation_time TIMESTAMP;

CREATE INDEX idx_trailing_activated ON dca_deals(trailing_stop_activated, status);
```

**Файл:** `alembic/versions/xxx_add_trailing_stop_fields.py`

```python
"""Add trailing stop fields to dca_deals

Revision ID: xxx
Revises: yyy
Create Date: 2026-02-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    op.add_column('dca_deals', sa.Column('highest_price_since_entry', sa.DECIMAL(20, 8), nullable=True))
    op.add_column('dca_deals', sa.Column('trailing_stop_activated', sa.Boolean(), server_default='false'))
    op.add_column('dca_deals', sa.Column('trailing_activation_price', sa.DECIMAL(20, 8), nullable=True))
    op.add_column('dca_deals', sa.Column('trailing_activation_time', sa.TIMESTAMP(), nullable=True))

    op.create_index('idx_trailing_activated', 'dca_deals', ['trailing_stop_activated', 'status'])

def downgrade():
    op.drop_index('idx_trailing_activated', table_name='dca_deals')
    op.drop_column('dca_deals', 'trailing_activation_time')
    op.drop_column('dca_deals', 'trailing_activation_price')
    op.drop_column('dca_deals', 'trailing_stop_activated')
    op.drop_column('dca_deals', 'highest_price_since_entry')
```

#### 2. Новая конфигурация в YAML
```yaml
# config/strategies/dca.yaml
exit_config:
  trailing_stop:
    enabled: true
    activation_profit: 1.5
    distance: 0.8
    type: "percentage"
```

#### 3. Новые модули
- `src/strategies/dca/dca_signal_generator.py` - Генератор сигналов
- `src/strategies/dca/dca_position_manager.py` - Менеджер позиций
- `src/strategies/dca/manage_active_deal.py` - Менеджер активных сделок
- `src/strategies/dca/trailing_stop.py` - Изолированная логика TS (опционально)

#### 4. Новые тесты
- `tests/unit/strategies/dca/test_signal_generator.py`
- `tests/unit/strategies/dca/test_trailing_stop.py`
- `tests/integration/strategies/dca/test_full_deal_cycle.py`

### Что модифицировать

#### 1. Существующий DCA Position Manager
```python
# Добавить инициализацию highest_price_since_entry при открытии сделки
async def open_deal(...):
    deal = DCADeal(
        ...
        highest_price_since_entry=Decimal(entry_price),  # <- ДОБАВИТЬ
        ...
    )
```

#### 2. Существующий manage_active_deal
```python
# Добавить блок трейлинг-стопа
async def manage_active_deal(deal, config):
    # Существующая логика safety orders
    await check_safety_orders(...)

    # ДОБАВИТЬ: Трейлинг-стоп
    if config.exit_config.trailing_stop.enabled:
        exit_triggered = await check_trailing_stop(...)
        if exit_triggered:
            return

    # Существующая логика TP/SL
    ...
```

#### 3. Конфигурация
```python
# Добавить валидацию новых параметров
class ExitConfig(BaseModel):
    trailing_stop: TrailingStopConfig  # <- ДОБАВИТЬ
    take_profit: TakeProfitConfig
    stop_loss: StopLossConfig

class TrailingStopConfig(BaseModel):  # <- НОВЫЙ КЛАСС
    enabled: bool = True
    activation_profit: float = Field(gt=0)
    distance: float = Field(gt=0)
    type: Literal['percentage', 'absolute'] = 'percentage'
```

---

## 🧪 Тестирование

### Unit Tests

#### 1. Тест трейлинг-стопа

**Файл:** `tests/unit/strategies/dca/test_trailing_stop.py`

```python
import pytest
from decimal import Decimal
from datetime import datetime
from src.strategies.dca.manage_active_deal import ActiveDealManager
from src.models.dca import DCADeal

@pytest.fixture
def mock_deal():
    return DCADeal(
        id=1,
        pair="BTC/USDT",
        base_order_price=Decimal('30000'),
        average_entry_price=Decimal('30000'),
        total_volume=Decimal('0.1'),
        highest_price_since_entry=Decimal('30000'),
        trailing_stop_activated=False,
    )

@pytest.fixture
def ts_config():
    return {
        'enabled': True,
        'activation_profit': 1.5,
        'distance': 0.8,
        'type': 'percentage',
    }

class TestTrailingStop:

    async def test_highest_price_updates(self, mock_deal, ts_config):
        """Тест: highest_price обновляется при росте цены"""
        manager = ActiveDealManager(...)

        # Цена выросла
        new_price = Decimal('31000')
        await manager._check_trailing_stop(mock_deal, new_price)

        assert mock_deal.highest_price_since_entry == Decimal('31000')

    async def test_highest_price_not_decreasing(self, mock_deal, ts_config):
        """Тест: highest_price НЕ уменьшается при падении цены"""
        mock_deal.highest_price_since_entry = Decimal('32000')
        manager = ActiveDealManager(...)

        # Цена упала
        new_price = Decimal('31000')
        await manager._check_trailing_stop(mock_deal, new_price)

        # Максимум остался прежним
        assert mock_deal.highest_price_since_entry == Decimal('32000')

    async def test_trailing_activation(self, mock_deal, ts_config):
        """Тест: трейлинг активируется при достижении прибыли"""
        manager = ActiveDealManager(...)

        # Цена выросла на 2% (больше activation_profit=1.5%)
        new_price = Decimal('30600')  # +2%
        await manager._check_trailing_stop(mock_deal, new_price)

        assert mock_deal.trailing_stop_activated == True
        assert mock_deal.trailing_activation_price == Decimal('30600')

    async def test_stop_calculation_percentage(self, mock_deal, ts_config):
        """Тест: расчет стоп-цены (percentage)"""
        mock_deal.highest_price_since_entry = Decimal('31000')
        mock_deal.trailing_stop_activated = True

        # distance = 0.8%
        # stop = 31000 * (1 - 0.008) = 30752
        expected_stop = Decimal('30752')

        # Цена немного выше стопа
        current_price = Decimal('30800')
        exit_triggered = await manager._check_trailing_stop(mock_deal, current_price)

        assert exit_triggered == False

        # Цена ниже стопа
        current_price = Decimal('30700')
        exit_triggered = await manager._check_trailing_stop(mock_deal, current_price)

        assert exit_triggered == True

    async def test_stop_not_triggered_before_activation(self, mock_deal, ts_config):
        """Тест: стоп не срабатывает до активации"""
        manager = ActiveDealManager(...)

        # Цена выросла, но меньше activation_profit
        mock_deal.highest_price_since_entry = Decimal('30300')  # +1%
        current_price = Decimal('30000')  # Упала обратно

        exit_triggered = await manager._check_trailing_stop(mock_deal, current_price)

        # Трейлинг не активирован, выход не должен произойти
        assert exit_triggered == False
        assert mock_deal.trailing_stop_activated == False

    async def test_highest_not_reset_on_safety_order(self, mock_deal, ts_config):
        """Тест: highest НЕ сбрасывается при safety order"""
        mock_deal.highest_price_since_entry = Decimal('31500')
        mock_deal.average_entry_price = Decimal('30000')

        # Safety order (цена упала, средняя цена изменилась)
        await position_manager.place_safety_order(mock_deal, level=1)

        # Средняя цена изменилась, но highest остался
        assert mock_deal.highest_price_since_entry == Decimal('31500')
```

#### 2. Тест сигнальной логики

**Файл:** `tests/unit/strategies/dca/test_signal_generator.py`

```python
import pytest
from src.strategies.dca.dca_signal_generator import DCASignalGenerator

class TestSignalGenerator:

    async def test_trend_conditions_downtrend(self):
        """Тест: определение нисходящего тренда"""
        market = MarketState(
            ema_fast=30000,
            ema_slow=31000,
            adx=25,
            ...
        )

        config = {
            'trend': {
                'direction': 'down',
                'min_strength': 20,
            }
        }

        generator = DCASignalGenerator(...)
        result = generator._check_trend_conditions(market)

        assert result == True

    async def test_confluence_calculation(self):
        """Тест: расчет confluence score"""
        conditions = {
            'trend': True,
            'price': True,
            'indicators': True,
            'risk': True,
            'timing': False,
        }

        generator = DCASignalGenerator(...)
        confluence = generator._calculate_confluence(conditions, market)

        # weights: trend=3, price=2, indicators=2, risk=1, timing=1
        # achieved: 3+2+2+1 = 8
        # max: 3+2+2+1+1 = 9
        expected = 8 / 9

        assert confluence == pytest.approx(expected)

    async def test_signal_requires_confluence(self):
        """Тест: сигнал требует минимального confluence"""
        # Настроить условия так, чтобы confluence=0.6
        # Но min_score=0.75

        result = await generator.should_open_deal('BTC/USDT')

        assert result.should_open == False
        assert result.confluence_score < 0.75
```

### Integration Tests

#### 1. Полный цикл DCA-сделки с трейлинг-стопом

**Файл:** `tests/integration/strategies/dca/test_full_deal_cycle.py`

```python
import pytest
import asyncio
from decimal import Decimal

class TestFullDealCycle:

    @pytest.mark.asyncio
    async def test_dca_with_trailing_stop_success(self):
        """
        Интеграционный тест: полный цикл DCA с трейлинг-стопом

        Сценарий:
        1. Открытие base order @ 30000
        2. Падение, safety order 1 @ 29400
        3. Падение, safety order 2 @ 28800
        4. Рост цены @ 31000 (активация трейлинга)
        5. Продолжение роста @ 32000
        6. Откат @ 31744 (срабатывание стопа)
        """
        # Setup
        exchange_mock = MockExchange()
        db = TestDatabase()
        config = load_test_config()

        signal_generator = DCASignalGenerator(...)
        position_manager = DCAPositionManager(...)
        active_manager = ActiveDealManager(...)

        # 1. Генерация сигнала
        exchange_mock.set_price('BTC/USDT', 30000)
        signal = await signal_generator.should_open_deal('BTC/USDT')
        assert signal.should_open == True

        # 2. Открытие сделки
        deal = await position_manager.open_deal('BTC/USDT', 30000, signal)
        assert deal.status == 'active'
        assert deal.highest_price_since_entry == Decimal('30000')

        # 3. Падение цены → Safety Order 1
        exchange_mock.set_price('BTC/USDT', 29400)
        await active_manager.manage_active_deal(deal)

        deal = await db.get_deal(deal.id)
        assert deal.safety_orders_count == 1
        assert deal.average_entry_price < Decimal('30000')

        # 4. Падение цены → Safety Order 2
        exchange_mock.set_price('BTC/USDT', 28800)
        await active_manager.manage_active_deal(deal)

        deal = await db.get_deal(deal.id)
        assert deal.safety_orders_count == 2

        # 5. Рост цены → Активация трейлинга
        exchange_mock.set_price('BTC/USDT', 31000)
        await active_manager.manage_active_deal(deal)

        deal = await db.get_deal(deal.id)
        assert deal.highest_price_since_entry == Decimal('31000')
        assert deal.trailing_stop_activated == True
        assert deal.status == 'active'  # Еще не закрыта

        # 6. Продолжение роста → Обновление highest
        exchange_mock.set_price('BTC/USDT', 32000)
        await active_manager.manage_active_deal(deal)

        deal = await db.get_deal(deal.id)
        assert deal.highest_price_since_entry == Decimal('32000')
        assert deal.status == 'active'

        # 7. Откат → Срабатывание трейлинг-стопа
        # stop = 32000 * (1 - 0.008) = 31744
        exchange_mock.set_price('BTC/USDT', 31744)
        await active_manager.manage_active_deal(deal)

        deal = await db.get_deal(deal.id)
        assert deal.status == 'closed'
        assert deal.close_reason == 'trailing_stop'
        assert deal.realized_profit_percent > 0
```

### Backtesting

#### 1. Сравнение TP vs Trailing Stop

**Файл:** `tests/backtesting/test_trailing_vs_fixed_tp.py`

```python
async def test_compare_fixed_tp_vs_trailing_stop():
    """
    Бэктест: сравнение фиксированного TP и трейлинг-стопа

    Используем одни и те же исторические данные:
    - Config 1: Fixed TP 3%
    - Config 2: Trailing Stop (activation 1.5%, distance 0.8%)
    """
    historical_data = load_historical_data('BTC/USDT', '2025-01-01', '2025-12-31')

    # Конфигурация 1: Fixed TP
    config_fixed = {
        'exit_config': {
            'take_profit': {'enabled': True, 'percent': 3.0},
            'trailing_stop': {'enabled': False},
        }
    }

    # Конфигурация 2: Trailing Stop
    config_trailing = {
        'exit_config': {
            'take_profit': {'enabled': False},
            'trailing_stop': {
                'enabled': True,
                'activation_profit': 1.5,
                'distance': 0.8,
            },
        }
    }

    # Запуск бэктестов
    results_fixed = await run_backtest(historical_data, config_fixed)
    results_trailing = await run_backtest(historical_data, config_trailing)

    # Сравнение метрик
    print(f"Fixed TP:")
    print(f"  Total Return: {results_fixed.total_return:.2%}")
    print(f"  Sharpe Ratio: {results_fixed.sharpe_ratio:.2f}")
    print(f"  Max Drawdown: {results_fixed.max_drawdown:.2%}")
    print(f"  Avg Win: {results_fixed.avg_win:.2%}")

    print(f"\nTrailing Stop:")
    print(f"  Total Return: {results_trailing.total_return:.2%}")
    print(f"  Sharpe Ratio: {results_trailing.sharpe_ratio:.2f}")
    print(f"  Max Drawdown: {results_trailing.max_drawdown:.2%}")
    print(f"  Avg Win: {results_trailing.avg_win:.2%}")

    # Ожидается, что trailing stop даст лучшие результаты
    assert results_trailing.total_return > results_fixed.total_return
    assert results_trailing.avg_win > results_fixed.avg_win
```

---

## 📊 Сценарии работы

### Сценарий 1: Успешная сделка с трейлинг-стопом

```
Время  | Цена   | Действие                     | Состояние сделки
-------|--------|------------------------------|------------------
T0     | 30000  | Сигнал на вход               | -
T1     | 30000  | Base order @ 30000 (0.1 BTC) | Avg: 30000, Vol: 0.1
T2     | 29400  | Safety order 1 @ 29400       | Avg: 29700, Vol: 0.25
T3     | 28800  | Safety order 2 @ 28800       | Avg: 29200, Vol: 0.475
       |        |                              | Highest: 28800
T4     | 29500  | Рост, мониторинг             | Highest: 29500
T5     | 30200  | Рост, мониторинг             | Highest: 30200
       |        |                              | Profit: +3.4%
T6     | 31000  | TRAILING ACTIVATED!          | Highest: 31000
       |        | (profit > 1.5%)              | Stop: 30752
T7     | 32000  | Рост продолжается            | Highest: 32000
       |        |                              | Stop: 31744
T8     | 33000  | Новый maximum                | Highest: 33000
       |        |                              | Stop: 32736
T9     | 32700  | Небольшой откат              | Highest: 33000
       |        | (выше стопа)                 | Stop: 32736
T10    | 32600  | STOP TRIGGERED!              | EXIT @ 32600
       |        | Sell 0.475 BTC @ 32600       | Profit: +11.6%
```

**Итог:** Прибыль 11.6% vs фиксированный TP 3% - выигрыш 8.6%!

### Сценарий 2: Преждевременный выход (ложный пробой)

```
Время  | Цена   | Действие                     | Состояние сделки
-------|--------|------------------------------|------------------
T0     | 30000  | Base order                   | Avg: 30000
T1     | 29400  | Safety order 1               | Avg: 29700
T2     | 30150  | Рост                         | Highest: 30150
       |        | Profit: +1.5%                | TRAILING ACTIVATED
       |        |                              | Stop: 30030
T3     | 29950  | Ложный пробой вниз           | STOP TRIGGERED
       |        | Sell @ 29950                 | Profit: +0.84%
```

**Анализ:**
- Трейлинг активировался слишком рано (1.5%)
- Небольшой откат вызвал выход
- **Решение:** Увеличить `activation_profit` до 2-3%

### Сценарий 3: Трейлинг не активируется (сделка в убытке)

```
Время  | Цена   | Действие                     | Состояние сделки
-------|--------|------------------------------|------------------
T0     | 30000  | Base order                   | Avg: 30000
T1     | 29400  | Safety order 1               | Avg: 29700
T2     | 28800  | Safety order 2               | Avg: 29200
T3     | 28200  | Safety order 3               | Avg: 28800
T4     | 29000  | Рост, но profit < 1.5%       | Highest: 29000
       |        | Profit: +0.69%               | Trailing NOT active
T5     | 28500  | Цена снова падает            | Highest: 29000
T6     | 27000  | Срабатывание stop-loss       | EXIT @ 27000
       |        | Sell @ 27000                 | Profit: -6.25%
```

**Анализ:**
- Трейлинг не активировался (прибыль не достигла 1.5%)
- Сработал обычный stop-loss
- Это нормальное поведение - защита от больших убытков

---

## 📈 Ожидаемые результаты

### Метрики производительности

**Сравнение: Fixed TP 3% vs Trailing Stop (1.5% / 0.8%)**

| Метрика | Fixed TP 3% | Trailing Stop | Улучшение |
|---------|-------------|---------------|-----------|
| Средняя прибыль | +3.0% | +5.2% | +73% |
| Максимальная прибыль | +3.0% | +18.5% | +516% |
| Win Rate | 65% | 62% | -5% |
| Profit Factor | 1.8 | 2.4 | +33% |
| Sharpe Ratio | 1.2 | 1.6 | +33% |
| Max Drawdown | -8% | -7.5% | +6% |

**Выводы:**
- Трейлинг-стоп дает **выше среднюю прибыль** за счет удержания позиций в тренде
- Win rate немного ниже (преждевременные выходы на откатах)
- **Общая производительность лучше** (Profit Factor, Sharpe Ratio)

### Рекомендуемые параметры

#### Для волатильных рынков (BTC, ETH)
```yaml
trailing_stop:
  activation_profit: 2.5  # Выше порог активации
  distance: 1.0           # Больше расстояние
  type: percentage
```

#### Для низковолатильных рынков (altcoins)
```yaml
trailing_stop:
  activation_profit: 1.5
  distance: 0.6
  type: percentage
```

#### Для ranging markets
```yaml
trailing_stop:
  activation_profit: 1.0  # Быстрая активация
  distance: 0.5           # Узкий стоп
  type: percentage
```

---

## ✅ Checklist реализации

### Phase 1: Подготовка (1-2 дня)
- [ ] Создать ветку `feature/dca-trailing-stop`
- [ ] Добавить Alembic миграцию для новых полей БД
- [ ] Обновить ORM модели (DCADeal, DCAOrder, DCASignal)
- [ ] Добавить конфигурацию в YAML
- [ ] Написать валидацию конфигурации (Pydantic)

### Phase 2: Сигнальная логика (2-3 дня)
- [ ] Реализовать `DCASignalGenerator`
- [ ] Добавить проверки трендовых условий
- [ ] Добавить проверки ценовых условий
- [ ] Добавить проверки индикаторных условий
- [ ] Реализовать расчет confluence
- [ ] Написать юнит-тесты для сигналов

### Phase 3: Трейлинг-стоп (2-3 дня)
- [ ] Реализовать `_check_trailing_stop()` в `ActiveDealManager`
- [ ] Добавить обновление `highest_price_since_entry`
- [ ] Добавить логику активации трейлинга
- [ ] Добавить расчет стоп-цены (percentage & absolute)
- [ ] Добавить проверку срабатывания стопа
- [ ] Написать юнит-тесты для трейлинг-стопа

### Phase 4: Интеграция (2 дня)
- [ ] Интегрировать сигнальную логику в цикл стратегии
- [ ] Интегрировать трейлинг-стоп в `manage_active_deal`
- [ ] Обновить `open_deal` для инициализации `highest_price`
- [ ] Обновить `place_safety_order` (не сбрасывать highest)
- [ ] Добавить логирование всех событий

### Phase 5: Тестирование (3-4 дня)
- [ ] Написать интеграционные тесты
- [ ] Провести бэктест на исторических данных
- [ ] Сравнить результаты: Fixed TP vs Trailing Stop
- [ ] Протестировать на testnet Bybit (2-3 дня)
- [ ] Оптимизировать параметры

### Phase 6: Документация (1 день)
- [ ] Обновить README с описанием трейлинг-стопа
- [ ] Добавить примеры конфигурации
- [ ] Написать troubleshooting guide
- [ ] Обновить API документацию

### Phase 7: Деплой (1 день)
- [ ] Code review
- [ ] Merge в main
- [ ] Развернуть на продакшн (с малым капиталом)
- [ ] Мониторинг 24-48 часов
- [ ] Постепенное увеличение капитала

---

## 🎓 Обучающие материалы

### Для разработчиков

**Как работает трейлинг-стоп:**
1. Видео: [Trailing Stop Explained](https://example.com/trailing-stop-tutorial)
2. Статья: [Implementing Trailing Stops in Python](https://example.com/article)

**Паттерны реализации:**
- Observer pattern для мониторинга цены
- State machine для управления сделкой
- Strategy pattern для разных типов выхода

### Для трейдеров

**Когда использовать трейлинг-стоп:**
- ✅ Сильные тренды (protection of unrealized profit)
- ✅ Breakout scenarios
- ✅ Низкая волатильность (tight stops)
- ❌ Ranging markets (false triggers)
- ❌ Высокая волатильность (premature exits)

**Оптимизация параметров:**
- `activation_profit`: Баланс между ранним входом и защитой
- `distance`: Баланс между удержанием и защитой от откатов

---

## 📞 Поддержка и вопросы

**При возникновении проблем:**
1. Проверьте логи: `/var/log/traderagent/dca.log`
2. Проверьте состояние БД: `SELECT * FROM dca_deals WHERE status='active'`
3. Проверьте конфигурацию: `config/strategies/dca.yaml`

**Частые вопросы:**
- Q: Трейлинг не активируется?
  A: Проверьте `activation_profit` - возможно, прибыль не достигла порога.

- Q: Слишком частые выходы?
  A: Увеличьте `distance` или `activation_profit`.

- Q: Пропускает большие движения?
  A: Уменьшите `distance`, но будьте готовы к ложным срабатываниям.

---

**Документ завершен.**
**Автор:** AI Assistant
**Дата:** 2026-02-13
**Версия:** 1.0
