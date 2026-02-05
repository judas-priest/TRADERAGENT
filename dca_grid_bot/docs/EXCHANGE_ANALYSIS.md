# Анализ целевых бирж для DCA-Grid бота

**Дата:** 2026-02-05
**Версия:** 1.0

## Критерии выбора

1. ✅ Поддержка CCXT (проверенная интеграция)
2. ✅ Надежное API с WebSocket
3. ✅ Адекватные комиссии (maker/taker)
4. ✅ Наличие testnet для безопасного тестирования
5. ✅ Ликвидность на целевых парах

---

## Выбранные биржи

### 1. Binance (Приоритет 1) ⭐

**Статус:** Рекомендовано для первого запуска

#### Преимущества
- ✅ Отличная поддержка в CCXT (`ccxt.binance`)
- ✅ Testnet доступен: `https://testnet.binance.vision`
- ✅ Низкие комиссии:
  - Spot: 0.1% (maker/taker)
  - С BNB: 0.075%
- ✅ Высочайшая ликвидность на популярных парах
- ✅ Стабильное и быстрое WebSocket API
- ✅ Хорошая документация

#### Rate Limits
- **REST API:** 1200 запросов/минуту (weight-based)
- **WebSocket:** 5 соединений, 100 подписок на соединение
- **Order Rate:** 50 ордеров/10 секунд

#### Поддерживаемые типы ордеров
- ✅ `LIMIT` - основа для Grid Trading
- ✅ `MARKET` - для срочных DCA покупок
- ✅ `LIMIT_MAKER` (POST_ONLY) - важно для Grid (гарантия maker fee)
- ✅ `STOP_LOSS_LIMIT` - для стоп-лоссов
- ✅ `OCO` (One-Cancels-Other) - опционально

#### Особенности
- ⚠️ Ограничения по регионам (может потребоваться VPN для некоторых стран)
- ℹ️ Требуется верификация KYC для вывода средств
- ℹ️ API ключи с ограничениями по IP (рекомендуется для безопасности)

#### Testnet Endpoints
```python
{
    'apiKey': 'YOUR_TESTNET_KEY',
    'secret': 'YOUR_TESTNET_SECRET',
    'urls': {
        'api': 'https://testnet.binance.vision/api',
        'ws': 'wss://testnet.binance.vision/ws'
    }
}
```

---

### 2. Bybit (Приоритет 2) ⭐

**Статус:** Рекомендовано как альтернатива/дополнение

#### Преимущества
- ✅ Хорошая поддержка в CCXT (`ccxt.bybit`)
- ✅ Testnet: `https://testnet.bybit.com`
- ✅ Низкие комиссии:
  - Spot: 0.1% (maker/taker)
  - VIP уровни снижают до 0.055%
- ✅ Friendly интерфейс для retail трейдеров
- ✅ Unified Trading Account (один баланс для всех типов торговли)
- ✅ Хорошая документация на английском

#### Rate Limits
- **REST API:** 120 запросов/минуту (per API key)
- **WebSocket:** 10 соединений
- **Order Rate:** 100 ордеров/минуту

#### Поддерживаемые типы ордеров
- ✅ `Limit` - стандартные лимитные ордера
- ✅ `Market` - рыночные ордера
- ✅ `PostOnly` - гарантия maker fee
- ✅ `Conditional` - условные ордера (stop-loss, take-profit)

#### Особенности
- ℹ️ Более простое API по сравнению с Binance
- ℹ️ Активно развивающаяся платформа
- ℹ️ Хорошая поддержка для алготрейдинга

---

### 3. OKX (Приоритет 3)

**Статус:** Опционально для будущего расширения

#### Преимущества
- ✅ Поддержка CCXT (`ccxt.okx`)
- ✅ Демо-аккаунт доступен
- ✅ Низкие комиссии (0.08%/0.1%)
- ✅ Хорошая ликвидность

#### Недостатки
- ⚠️ Более сложное API
- ⚠️ Требуется passphrase дополнительно к API key/secret
- ⚠️ Менее интуитивная структура эндпоинтов

#### Rate Limits
- **REST API:** 40-60 запросов/2 секунды (зависит от эндпоинта)
- **WebSocket:** 100 соединений

---

## Проверка поддержки через CCXT

### Пример кода для Binance

```python
import ccxt

# Инициализация Binance
exchange = ccxt.binance({
    'apiKey': 'YOUR_API_KEY',
    'secret': 'YOUR_SECRET',
    'enableRateLimit': True,  # Автоматический rate limiting
    'options': {
        'defaultType': 'spot',  # Используем spot рынок
        'adjustForTimeDifference': True  # Синхронизация времени
    }
})

# Проверка возможностей
capabilities = {
    'createLimitOrder': exchange.has['createLimitOrder'],      # True
    'createMarketOrder': exchange.has['createMarketOrder'],    # True
    'createPostOnlyOrder': exchange.has['createPostOnlyOrder'], # True (через timeInForce)
    'fetchOpenOrders': exchange.has['fetchOpenOrders'],        # True
    'fetchMyTrades': exchange.has['fetchMyTrades'],            # True
    'fetchBalance': exchange.has['fetchBalance'],              # True
    'fetchOrderBook': exchange.has['fetchOrderBook'],          # True
    'fetchTicker': exchange.has['fetchTicker'],                # True
    'cancelOrder': exchange.has['cancelOrder'],                # True
    'cancelAllOrders': exchange.has['cancelAllOrders'],        # True
    'ws': exchange.has['ws']                                   # WebSocket support
}

print(capabilities)
```

### Пример кода для Bybit

```python
import ccxt

exchange = ccxt.bybit({
    'apiKey': 'YOUR_API_KEY',
    'secret': 'YOUR_SECRET',
    'enableRateLimit': True,
    'options': {
        'defaultType': 'spot'
    }
})

# Аналогичная проверка возможностей
```

---

## Тестирование на Testnet

### Binance Testnet Setup

1. **Получить testnet ключи:**
   - Перейти на https://testnet.binance.vision
   - Создать аккаунт (не требует KYC)
   - Сгенерировать API ключи

2. **Пополнить testnet баланс:**
   - В интерфейсе testnet есть функция "Get Test Funds"
   - Можно получить виртуальные BTC, ETH, USDT

3. **Конфигурация в коде:**
```python
exchange = ccxt.binance({
    'apiKey': 'testnet_key',
    'secret': 'testnet_secret',
    'enableRateLimit': True,
    'urls': {
        'api': 'https://testnet.binance.vision/api',
    },
    'options': {'defaultType': 'spot'}
})
```

### Bybit Testnet Setup

1. **Получить testnet ключи:**
   - https://testnet.bybit.com
   - Регистрация с email
   - API Management → Create Key

2. **Виртуальные средства:**
   - Автоматически начисляются при создании аккаунта

---

## Рекомендации для реализации

### Приоритет разработки

1. **Фаза 1 (MVP):** Binance Spot только
   - Наиболее стабильное API
   - Лучшая документация
   - Простейший старт

2. **Фаза 2:** Добавить Bybit
   - Расширение поддержки бирж
   - Диверсификация рисков

3. **Фаза 3:** OKX и другие (опционально)

### Обязательные проверки перед production

- [ ] Протестировать все типы ордеров на testnet
- [ ] Проверить обработку rate limits
- [ ] Протестировать reconnect при обрыве WebSocket
- [ ] Проверить синхронизацию времени (важно для Binance!)
- [ ] Протестировать обработку ошибок API (invalid symbol, insufficient balance, etc.)
- [ ] Проверить комиссии реальные vs документация

### Структура кода для мультибиржевости

```python
# Абстрактный класс
class ExchangeClient:
    def create_limit_order(self, symbol, side, amount, price): pass
    def fetch_balance(self): pass
    # ... другие методы

# Реализации
class BinanceClient(ExchangeClient): pass
class BybitClient(ExchangeClient): pass
```

---

## Заключение

**Выбор для MVP:** Binance Spot

**Обоснование:**
- Проверенная стабильность
- Лучшая документация
- Активное комьюнити
- Простота testnet тестирования

**План тестирования:**
1. Все разработки тестировать на Binance Testnet
2. После стабилизации - перейти на Bybit testnet
3. Production запуск только после полного цикла тестов

**Риски и митигация:**
- **Риск:** Regional restrictions
  - **Митигация:** VPS в разрешенной юрисдикции
- **Риск:** API изменения
  - **Митигация:** Версионирование API, мониторинг changelog бирж
- **Риск:** Rate limit нарушения
  - **Митигация:** Built-in rate limiter в CCXT + собственный контроль

---

**Статус:** ✅ Завершено
**Следующий шаг:** Задача 0.2 - Проектирование схемы базы данных
