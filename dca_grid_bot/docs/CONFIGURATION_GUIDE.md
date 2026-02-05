# Руководство по конфигурации DCA-Grid Bot

**Версия:** 1.0
**Дата:** 2026-02-05

---

## Обзор

Конфигурация бота хранится в YAML файлах. Это позволяет:
- Легко редактировать параметры без изменения кода
- Использовать версионирование конфигураций
- Создавать разные профили для разных стратегий

**Файлы конфигурации:**
- `bot_config.example.yaml` - Полная конфигурация со всеми опциями
- `bot_config.simple.yaml` - Упрощенная конфигурация для начинающих
- `bot_config.yaml` - Ваша рабочая конфигурация (не коммитится в git)

---

## Быстрый старт

### 1. Скопируйте пример конфигурации

```bash
cp config/bot_config.simple.yaml config/bot_config.yaml
```

### 2. Отредактируйте основные параметры

```yaml
bot:
  name: "my_bot"                           # Уникальное имя

exchange:
  name: "binance"
  testnet: true                            # ВСЕГДА начинайте с testnet!

trading:
  symbol: "BTC/USDT"

capital:
  total: 1000.0                            # Начните с малого!
```

### 3. Настройте переменные окружения

Создайте файл `.env`:

```bash
# Exchange API (testnet keys)
BINANCE_API_KEY=your_testnet_api_key
BINANCE_API_SECRET=your_testnet_api_secret

# Encryption
SECRET_KEY=your_generated_secret_key

# Database
DATABASE_URL=postgresql://user:pass@localhost/dca_grid_bot

# Redis
REDIS_URL=redis://localhost:6379/0

# Telegram (optional)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

---

## Секции конфигурации

### 1. Bot Identification

```yaml
bot:
  name: "btc_usdt_hybrid_bot_1"
  description: "My trading bot"
```

**Параметры:**
- `name` - Уникальное имя бота (используется в БД и логах)
- `description` - Описание (опционально)

---

### 2. Exchange Settings

```yaml
exchange:
  name: "binance"                          # binance, bybit, okx
  type: "spot"                             # spot (futures пока не поддерживается)
  testnet: false

  api_key: "${BINANCE_API_KEY}"
  api_secret: "${BINANCE_API_SECRET}"

  rate_limit:
    enabled: true
    requests_per_minute: 1000
```

**Важно:**
- ⚠️ **Всегда** начинайте с `testnet: true`
- ⚠️ **Никогда** не храните API ключи в конфиге напрямую - используйте env переменные
- ✅ Включайте `rate_limit` для избежания бана

**Получение testnet ключей:**
- Binance: https://testnet.binance.vision
- Bybit: https://testnet.bybit.com

---

### 3. Trading Pair

```yaml
trading:
  symbol: "BTC/USDT"
  base_currency: "BTC"
  quote_currency: "USDT"
```

**Рекомендации:**
- Начните с ликвидных пар: BTC/USDT, ETH/USDT
- Проверьте минимальный объем ордера на бирже

---

### 4. Capital Management

```yaml
capital:
  total: 10000.0                           # В quote currency (USDT)

  allocation:
    grid: 60.0                             # 60% на сетку
    dca: 30.0                              # 30% на DCA
    reserve: 10.0                          # 10% резерв
```

**Распределение капитала:**
- `grid` - Капитал для сеточной торговли
- `dca` - Капитал для усреднения
- `reserve` - Резерв (для комиссий, непредвиденных ситуаций)

**Сумма должна = 100%**

**Рекомендации:**
- Для Grid-focused: grid=70%, dca=20%, reserve=10%
- Для DCA-focused: grid=40%, dca=50%, reserve=10%
- Для Balanced (hybrid): grid=60%, dca=30%, reserve=10%

---

### 5. Strategy Type

```yaml
strategy:
  type: "hybrid"                           # grid, dca, или hybrid
  hybrid_variant: "grid_with_dca_insurance"
```

**Типы стратегий:**

1. **`grid`** - Только сеточная торговля
   - Для бокового тренда
   - Постоянная прибыль от колебаний

2. **`dca`** - Только усреднение
   - Для нисходящего тренда с ожиданием роста
   - Накопление позиции

3. **`hybrid`** - Комбинация Grid + DCA
   - Универсальная стратегия
   - Защита от просадок

**Варианты hybrid:**

- `grid_with_dca_insurance` - Сетка работает, DCA активируется при пробое вниз (рекомендуется)
- `parallel` - Grid и DCA работают независимо
- `adaptive` - Динамическая сетка с микро-DCA

---

### 6. Grid Trading Configuration

```yaml
grid:
  enabled: true

  price_range:
    lower_bound: 40000.0
    upper_bound: 50000.0

  levels:
    count: 20
    distribution: "arithmetic"             # arithmetic или geometric

  order_size:
    type: "fixed"
    amount: 0.001

  orders:
    type: "limit"
    post_only: true

  behavior:
    take_profit_percent: 0.5
```

#### Price Range

**Как определить границы:**

1. **Анализ текущей цены:**
   - Если BTC = 45000, можно использовать:
     - lower: 40000 (-11%)
     - upper: 50000 (+11%)

2. **На основе волатильности:**
   - Посмотрите диапазон за последние 30 дней
   - Используйте ±10-20% от текущей

3. **Поддержка/Сопротивление:**
   - Используйте технический анализ

**Рекомендации:**
- ⚠️ Слишком узкий диапазон → частые пробои
- ⚠️ Слишком широкий диапазон → редкие сделки

#### Grid Levels

**Count (количество уровней):**
- Меньше уровней (5-10): больше прибыли на уровень, реже сделки
- Больше уровней (20-50): меньше прибыли, чаще сделки

**Distribution:**
- `arithmetic` - Равномерное распределение (рекомендуется)
  - 40000, 40500, 41000, 41500...
- `geometric` - Процентное распределение
  - 40000, 40800 (+2%), 41616 (+2%)...

#### Order Size

**Типы:**

1. **`fixed`** - Фиксированное количество (рекомендуется)
   ```yaml
   type: "fixed"
   amount: 0.001                          # 0.001 BTC на каждый уровень
   ```

2. **`percentage`** - Процент от выделенного капитала
   ```yaml
   type: "percentage"
   percent_of_allocated: 5.0              # 5% на каждый уровень
   ```

3. **`martingale`** - Увеличение с каждым уровнем (ОПАСНО!)
   ```yaml
   type: "martingale"
   amount: 0.001
   martingale_multiplier: 1.5
   ```

**Расчет amount:**
```python
grid_capital = total_capital * grid_allocation / 100
amount = grid_capital / (levels * average_price)

# Пример:
# total = 10000 USDT
# grid_allocation = 60%
# levels = 20
# avg_price = 45000
grid_capital = 10000 * 0.6 = 6000 USDT
amount = 6000 / (20 * 45000) = 0.00667 BTC
```

#### Orders

```yaml
orders:
  type: "limit"                            # Всегда используйте limit
  time_in_force: "GTC"                     # Good-Till-Cancel
  post_only: true                          # Только maker (меньше комиссии)
```

**Post-only важно!**
- Гарантирует статус maker
- Binance maker: 0.075% vs taker: 0.1%
- На 10000 USDT экономия: 2.5 USDT

---

### 7. DCA Configuration

```yaml
dca:
  enabled: true

  trigger:
    type: "price_drop"
    price_drop_percent: 3.0

  steps:
    max_steps: 5
    step_percent: 3.0
    progression: "fixed"
    amount_per_step: 0.002

  exit:
    type: "take_profit"
    take_profit_percent: 5.0
```

#### Trigger

**Когда активируется DCA:**

```yaml
trigger:
  type: "price_drop"
  price_drop_percent: 3.0
  reference_price: "grid_lower_bound"
```

**Типы триггеров:**
- `price_drop` - При падении цены на X% ниже reference
- `time_based` - По времени (например, каждую неделю)
- `manual` - Ручная активация

**Reference price:**
- `grid_lower_bound` - От нижней границы сетки (рекомендуется)
- `last_buy` - От последней покупки
- `average_entry` - От средней цены входа

**Пример:**
```
Grid lower bound = 40000
price_drop_percent = 3%
Trigger price = 40000 * 0.97 = 38800

Если цена < 38800 → активируется DCA
```

#### Steps

```yaml
steps:
  max_steps: 5                             # Максимум 5 шагов
  step_percent: 3.0                        # Каждые 3% вниз
  progression: "fixed"                     # Фиксированный объем
  amount_per_step: 0.002                   # 0.002 BTC на шаг
```

**Progression types:**

1. **`fixed`** - Одинаковый объем (рекомендуется)
   ```
   Step 1: 0.002 BTC
   Step 2: 0.002 BTC
   Step 3: 0.002 BTC
   ```

2. **`increasing`** - Увеличивающийся
   ```yaml
   progression: "increasing"
   increase_factor: 1.5

   Step 1: 0.002 BTC
   Step 2: 0.003 BTC (0.002 * 1.5)
   Step 3: 0.0045 BTC (0.003 * 1.5)
   ```

3. **`martingale`** - Удвоение (ОЧЕНЬ ОПАСНО!)
   ```yaml
   progression: "martingale"
   martingale_multiplier: 2.0

   Step 1: 0.002 BTC
   Step 2: 0.004 BTC
   Step 3: 0.008 BTC
   ```

**Расчет DCA шагов:**
```
Trigger price = 38800
Step 1: 38800 * 0.97 = 37636
Step 2: 37636 * 0.97 = 36507
Step 3: 36507 * 0.97 = 35412
Step 4: 35412 * 0.97 = 34350
Step 5: 34350 * 0.97 = 33320
```

#### Exit Strategy

**Take Profit:**
```yaml
exit:
  type: "take_profit"
  take_profit_percent: 5.0
```

После всех DCA покупок:
- Рассчитывается средняя цена входа
- Целевая цена = avg_entry * (1 + take_profit_percent/100)
- При достижении цели → закрыть всю DCA позицию

**Пример:**
```
DCA Step 1: Buy 0.002 BTC @ 38000
DCA Step 2: Buy 0.002 BTC @ 36000
DCA Step 3: Buy 0.002 BTC @ 34000

Total: 0.006 BTC
Average entry: (38000 + 36000 + 34000) / 3 = 36000
Take profit (5%): 36000 * 1.05 = 37800

→ Продать 0.006 BTC когда цена = 37800
```

---

### 8. Risk Management

```yaml
risk:
  stop_loss:
    enabled: true
    type: "portfolio"
    percent: 15.0
    action: "close_all"

  take_profit:
    enabled: true
    percent: 30.0

  drawdown:
    max_drawdown_percent: 20.0

  position:
    max_position_size: 0.1
    max_open_orders: 50

  balance:
    min_balance_percent: 5.0
```

#### Stop Loss

**Portfolio stop-loss:**
```yaml
stop_loss:
  type: "portfolio"
  percent: 15.0
```

Если общий капитал падает на 15% от начального:
```
Initial capital: 10000 USDT
Stop loss trigger: 10000 * 0.85 = 8500 USDT
```

**Actions:**
- `close_all` - Закрыть все позиции, отменить ордера
- `pause` - Остановить бота, оставить ордера
- `emergency_stop` - Немедленная остановка

#### Take Profit

```yaml
take_profit:
  enabled: true
  percent: 30.0
```

Если прибыль достигает 30%:
```
Initial: 10000 USDT
Target: 10000 * 1.30 = 13000 USDT
```

#### Position Limits

```yaml
position:
  max_position_size: 0.1                   # Макс 0.1 BTC
  max_open_orders: 50                      # Макс 50 ордеров
```

---

### 9. Notifications

```yaml
notifications:
  telegram:
    enabled: true
    bot_token: "${TELEGRAM_BOT_TOKEN}"
    chat_id: "${TELEGRAM_CHAT_ID}"

    events:
      bot_started: true
      order_filled: true
      dca_triggered: true
      stop_loss_hit: true
      error_occurred: true
      daily_summary: true
```

**Настройка Telegram бота:**

1. Создать бота: @BotFather в Telegram
2. Получить token
3. Узнать chat_id: Написать боту /start, затем:
   ```bash
   curl https://api.telegram.org/bot<TOKEN>/getUpdates
   ```

---

### 10. Logging

```yaml
logging:
  level: "INFO"                            # DEBUG, INFO, WARNING, ERROR

  file:
    enabled: true
    path: "logs/bot.log"
    max_size_mb: 100
    backup_count: 5

  console:
    enabled: true
    colored: true

  database:
    enabled: true
    level: "INFO"
```

**Уровни логирования:**
- `DEBUG` - Все детали (для разработки)
- `INFO` - Обычные события (рекомендуется)
- `WARNING` - Предупреждения
- `ERROR` - Ошибки
- `CRITICAL` - Критические ошибки

---

## Примеры конфигураций

### Консервативная стратегия (новичкам)

```yaml
capital:
  total: 1000.0
  allocation:
    grid: 70.0
    dca: 20.0
    reserve: 10.0

grid:
  price_range:
    lower_bound: 40000.0
    upper_bound: 50000.0
  levels:
    count: 10
  order_size:
    type: "fixed"
    amount: 0.0001
  behavior:
    take_profit_percent: 1.0               # Выше прибыль на уровень

risk:
  stop_loss:
    percent: 10.0                          # Тугой стоп-лосс
```

### Агрессивная стратегия

```yaml
capital:
  allocation:
    grid: 50.0
    dca: 40.0                              # Больше на DCA
    reserve: 10.0

grid:
  levels:
    count: 30                              # Больше уровней
  behavior:
    take_profit_percent: 0.3               # Меньше прибыль, больше сделок

dca:
  steps:
    max_steps: 10
    progression: "increasing"
    increase_factor: 1.3

risk:
  stop_loss:
    percent: 25.0                          # Более широкий стоп
```

---

## Валидация конфигурации

Перед запуском бот валидирует конфигурацию:

**Обязательные проверки:**
- [ ] Сумма allocation = 100%
- [ ] lower_bound < upper_bound
- [ ] amount > минимального ордера биржи
- [ ] max_steps * amount_per_step < dca капитала
- [ ] Все env переменные заданы

**Запуск валидации:**
```bash
python -m dca_grid_bot.validate_config config/bot_config.yaml
```

---

## Best Practices

### 1. Начинайте с testnet

```yaml
exchange:
  testnet: true
```

### 2. Используйте малый капитал

```yaml
capital:
  total: 100.0                             # Начните с $100
```

### 3. Широкие границы сетки

```yaml
grid:
  price_range:
    lower_bound: current_price * 0.8       # -20%
    upper_bound: current_price * 1.2       # +20%
```

### 4. Консервативный DCA

```yaml
dca:
  steps:
    max_steps: 3                           # Только 3 шага
    progression: "fixed"                   # Без увеличения
```

### 5. Включите все защиты

```yaml
risk:
  stop_loss:
    enabled: true
  take_profit:
    enabled: true
  drawdown:
    max_drawdown_percent: 15.0
```

---

## Troubleshooting

### Ошибка: "Insufficient balance"

**Проблема:** Недостаточно капитала для размещения ордеров

**Решение:**
1. Уменьшите `amount` в grid или DCA
2. Уменьшите `levels.count`
3. Увеличьте `reserve` allocation

### Ошибка: "Order below minimum"

**Проблема:** Объем ордера меньше минимального на бирже

**Решение:**
```yaml
grid:
  order_size:
    amount: 0.001                          # Увеличьте amount
```

Минимальные объемы:
- Binance BTC/USDT: 0.00001 BTC
- Bybit BTC/USDT: 0.0001 BTC

### Предупреждение: "Rate limit approaching"

**Решение:**
```yaml
exchange:
  rate_limit:
    requests_per_minute: 500               # Уменьшите лимит
```

---

## Версионирование конфигураций

Рекомендуется сохранять версии конфигураций:

```bash
configs/
  ├── v1_conservative.yaml
  ├── v2_balanced.yaml
  ├── v3_aggressive.yaml
  └── bot_config.yaml -> v2_balanced.yaml  (symlink)
```

---

**Статус:** ✅ Завершено
**Следующая задача:** 0.4 - Система безопасного хранения API ключей
