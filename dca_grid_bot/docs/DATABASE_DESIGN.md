# База данных DCA-Grid Trading Bot

**Версия:** 1.0
**СУБД:** PostgreSQL 14+
**Дата:** 2026-02-05

---

## Обзор

База данных спроектирована для хранения:
- Конфигураций торговых ботов
- Зашифрованных API ключей
- Истории ордеров и сделок
- Состояний ботов для восстановления
- Метрик производительности
- Детальных логов

---

## Структура таблиц

### 1. `bots` - Основная таблица ботов

Хранит конфигурацию и текущее состояние каждого бота.

**Ключевые поля:**
- `id` - Primary key
- `uuid` - Универсальный уникальный идентификатор
- `name` - Уникальное имя бота
- `exchange` - Название биржи (binance, bybit, okx)
- `symbol` - Торговая пара (BTC/USDT)
- `strategy_type` - Тип стратегии (grid, dca, hybrid)
- `config` - JSONB конфигурация (все параметры)
- `state` - Текущее состояние (running, paused, stopped, error, emergency)
- `total_capital` - Общий капитал
- `available_capital` - Доступный капитал
- `allocated_capital` - Капитал в открытых ордерах

**Индексы:**
- `idx_bots_state` - Быстрый поиск по состоянию
- `idx_bots_exchange_symbol` - Поиск по бирже и паре

---

### 2. `exchange_credentials` - API ключи (зашифрованные)

Хранит зашифрованные API ключи для доступа к биржам.

**Безопасность:**
- Все ключи шифруются с использованием Fernet (симметричное шифрование)
- Мастер-ключ шифрования хранится в переменных окружения (`SECRET_KEY`)
- Поддержка IP whitelist

**Поля:**
- `api_key_encrypted` - Зашифрованный API ключ
- `api_secret_encrypted` - Зашифрованный API secret
- `passphrase_encrypted` - Зашифрованная passphrase (для OKX)
- `is_testnet` - Флаг testnet/production

---

### 3. `orders` - Таблица ордеров

Все ордера, размещенные ботом.

**Типы ордеров:**
- `limit` - Лимитные (основа Grid)
- `market` - Рыночные (для DCA)
- `stop_limit` - Стоп-лимитные

**Статусы:**
- `open` - Активный ордер
- `closed` - Исполнен
- `canceled` - Отменен
- `expired` - Истек
- `rejected` - Отклонен биржей

**Стратегическая классификация:**
- `strategy_component` - Какая часть стратегии (grid/dca/manual/stop_loss)
- `grid_level` - Уровень сетки (если применимо)
- `dca_step` - Шаг DCA (если применимо)
- `parent_order_id` - Связь между buy и sell ордерами

**Индексы:**
- `idx_orders_bot_status` - Для быстрого поиска открытых ордеров
- `idx_orders_exchange_id` - Поиск по ID биржи
- `idx_orders_created` - Сортировка по дате создания
- `idx_orders_strategy` - Фильтрация по стратегии

---

### 4. `trades` - Исполненные сделки

Детальная информация о каждой исполненной сделке с биржи.

**Важные поля:**
- `price` - Цена исполнения
- `amount` - Количество
- `cost` - Общая стоимость (price × amount)
- `fee` - Комиссия
- `realized_pnl` - Реализованный P&L (для закрытых позиций)
- `timestamp` - Время исполнения на бирже

**Расчет P&L:**
Реализованный P&L рассчитывается при закрытии пары buy-sell:
```
PnL = (sell_price - buy_price) * amount - total_fees
```

---

### 5. `bot_states` - Снапшоты состояний

Периодические снапшоты полного состояния бота для восстановления после сбоев.

**Типы снапшотов:**
- `periodic` - Регулярные (каждые 5-10 минут)
- `before_stop` - Перед остановкой бота
- `error` - При возникновении ошибки
- `manual` - Ручные снапшоты

**Содержимое `state_data` (JSONB):**
```json
{
  "positions": {
    "BTC": 0.5,
    "USDT": 10000
  },
  "average_entry_price": 42000.50,
  "grid_state": {
    "active_levels": [40000, 40500, 41000],
    "next_buy_level": 39500,
    "next_sell_level": 42500
  },
  "dca_state": {
    "total_dca_steps": 3,
    "average_dca_price": 41000,
    "next_trigger_price": 38000
  }
}
```

---

### 6. `bot_logs` - Логи бота

Детальное логирование всех действий.

**Уровни логирования:**
- `DEBUG` - Подробная отладочная информация
- `INFO` - Информационные сообщения (ордер создан, сделка исполнена)
- `WARNING` - Предупреждения (rate limit близок, баланс низкий)
- `ERROR` - Ошибки (API недоступен, ордер отклонен)
- `CRITICAL` - Критические ошибки (остановка бота)

**Компоненты:**
- `GridEngine` - Сеточный движок
- `DCAEngine` - DCA движок
- `RiskManager` - Менеджер рисков
- `ExchangeClient` - API клиент
- `Orchestrator` - Оркестратор

**Пример лога:**
```json
{
  "level": "INFO",
  "message": "Grid buy order filled",
  "component": "GridEngine",
  "context": {
    "order_id": 12345,
    "level": 5,
    "price": 41000.50,
    "amount": 0.001
  }
}
```

---

### 7. `grid_levels` - Уровни сетки

Хранит информацию об уровнях сеточной торговли.

**Структура:**
- `level_number` - Номер уровня (0, 1, 2, ...)
- `price` - Цена уровня
- `side` - Направление (buy/sell)
- `amount` - Количество для ордера
- `is_active` - Активен ли уровень
- `order_id` - Текущий ордер на этом уровне
- `times_triggered` - Статистика срабатываний

**Пример данных:**
```
level_number | price     | side | amount | is_active | times_triggered
-------------|-----------|------|--------|-----------|----------------
0            | 40000.00  | buy  | 0.001  | true      | 5
1            | 40500.00  | buy  | 0.001  | true      | 3
2            | 41000.00  | sell | 0.001  | true      | 2
3            | 41500.00  | sell | 0.001  | false     | 0
```

---

### 8. `dca_history` - История DCA

Хранит информацию о каждом шаге усреднения.

**Ключевые поля:**
- `step_number` - Номер шага (1, 2, 3, ...)
- `trigger_price` - Цена, при которой сработал триггер
- `buy_price` - Цена покупки
- `amount` - Купленное количество
- `average_entry_price` - Средняя цена входа после DCA
- `total_position` - Общая позиция после DCA
- `target_sell_price` - Целевая цена для продажи

**Пример:**
```
step | trigger_price | buy_price | amount | avg_entry_price | total_position | target_sell_price
-----|---------------|-----------|--------|-----------------|----------------|------------------
1    | 40000         | 39800     | 0.01   | 41500           | 0.02           | 43000
2    | 38000         | 37900     | 0.01   | 39850           | 0.03           | 41500
3    | 36000         | 35800     | 0.01   | 38533           | 0.04           | 40200
```

---

### 9. `performance_metrics` - Метрики производительности

Агрегированная статистика по периодам (часы, дни, недели).

**Метрики:**
- `total_trades` - Количество сделок
- `winning_trades` / `losing_trades` - Win/Loss
- `total_volume` - Общий объем торговли
- `total_fees` - Комиссии
- `realized_pnl` - Реализованный P&L
- `unrealized_pnl` - Нереализованный P&L

**Интервалы:**
- `hourly` - Почасовая статистика
- `daily` - Дневная
- `weekly` - Недельная
- `monthly` - Месячная

---

## Представления (Views)

### `active_bots_summary`

Сводная информация по активным ботам.

```sql
SELECT * FROM active_bots_summary;
```

**Возвращает:**
- Основную информацию о боте
- Количество открытых ордеров
- Общее количество сделок
- Реализованный P&L

---

### `bot_pnl_summary`

P&L статистика по всем ботам.

```sql
SELECT * FROM bot_pnl_summary WHERE bot_id = 1;
```

**Возвращает:**
- Общий P&L
- Комиссии
- Чистый P&L (после комиссий)
- Средний P&L на сделку

---

## Функции

### `recalculate_available_capital(bot_id)`

Пересчитывает доступный капитал бота на основе открытых ордеров.

**Логика:**
```
available_capital = total_capital - allocated_capital
allocated_capital = SUM(открытых ордеров)
```

**Использование:**
```sql
SELECT recalculate_available_capital(1);
```

Автоматически обновляет поля `available_capital` и `allocated_capital` в таблице `bots`.

---

## Триггеры

### `update_updated_at`

Автоматически обновляет поле `updated_at` при изменении записи.

**Применяется к:**
- `bots`
- `orders`
- `grid_levels`

---

## Индексы и оптимизация

### Основные индексы

1. **Для быстрого поиска ботов:**
   - `idx_bots_state` - по состоянию
   - `idx_bots_exchange_symbol` - по бирже и паре

2. **Для ордеров:**
   - `idx_orders_bot_status` - критически важен для проверки открытых ордеров
   - `idx_orders_exchange_id` - для синхронизации с биржей
   - `idx_orders_strategy` - для анализа по стратегии

3. **Для сделок:**
   - `idx_trades_bot_timestamp` - для отчетов по времени
   - `idx_trades_symbol` - для анализа по паре

4. **Для логов:**
   - `idx_bot_logs_bot_time` - для быстрого доступа к последним логам
   - `idx_bot_logs_level` - для фильтрации по уровню (ERROR, CRITICAL)

### Рекомендации по производительности

1. **Партиционирование:**
   - Для `bot_logs` и `trades` можно использовать партиционирование по времени (monthly partitions)

2. **Архивация:**
   - Логи старше 30 дней можно архивировать
   - Сделки старше 1 года перемещать в архивную таблицу

3. **Vacuum:**
   - Регулярный VACUUM для поддержания производительности
   - ANALYZE после массовых операций

---

## Безопасность

### Шифрование API ключей

**Метод:** Fernet (симметричное шифрование на основе AES-128-CBC)

**Процесс:**
1. Мастер-ключ (`SECRET_KEY`) хранится в переменных окружения
2. При сохранении: `encrypted = Fernet(SECRET_KEY).encrypt(api_key)`
3. При чтении: `api_key = Fernet(SECRET_KEY).decrypt(encrypted)`

**Пример кода:**
```python
from cryptography.fernet import Fernet

# Генерация ключа (один раз)
key = Fernet.generate_key()
# Сохранить в .env: SECRET_KEY=<key>

# Шифрование
cipher = Fernet(key)
encrypted_key = cipher.encrypt(b"my_api_key")

# Дешифрование
decrypted_key = cipher.decrypt(encrypted_key)
```

### Права доступа

**Рекомендации:**
1. Создать отдельного пользователя БД для бота
2. Ограничить права только необходимыми таблицами
3. Запретить DDL операции (CREATE, DROP)
4. Использовать SSL соединение

```sql
CREATE USER bot_user WITH PASSWORD 'secure_password';
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO bot_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO bot_user;
```

---

## Миграции

### Управление миграциями: Alembic

**Установка:**
```bash
pip install alembic
alembic init migrations
```

**Создание миграции:**
```bash
alembic revision -m "Initial schema"
```

**Применение миграций:**
```bash
alembic upgrade head
```

**Откат:**
```bash
alembic downgrade -1
```

---

## Backup и восстановление

### Резервное копирование

**Полный бэкап:**
```bash
pg_dump -h localhost -U postgres -d dca_grid_bot > backup.sql
```

**Только схема:**
```bash
pg_dump -h localhost -U postgres -d dca_grid_bot --schema-only > schema.sql
```

**Только данные:**
```bash
pg_dump -h localhost -U postgres -d dca_grid_bot --data-only > data.sql
```

### Восстановление

```bash
psql -h localhost -U postgres -d dca_grid_bot < backup.sql
```

### Автоматический бэкап (cron)

```bash
# Каждый день в 2:00 ночи
0 2 * * * pg_dump dca_grid_bot | gzip > /backups/dca_grid_bot_$(date +\%Y\%m\%d).sql.gz
```

---

## Мониторинг

### Важные метрики для мониторинга

1. **Размер таблиц:**
```sql
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

2. **Количество записей:**
```sql
SELECT
    'bot_logs' as table_name, COUNT(*) FROM bot_logs
UNION ALL
SELECT 'trades', COUNT(*) FROM trades
UNION ALL
SELECT 'orders', COUNT(*) FROM orders;
```

3. **Активность ботов:**
```sql
SELECT state, COUNT(*) FROM bots GROUP BY state;
```

4. **Ошибки в логах:**
```sql
SELECT COUNT(*) FROM bot_logs
WHERE level IN ('ERROR', 'CRITICAL')
AND timestamp > NOW() - INTERVAL '1 hour';
```

---

## Тестовые данные

### Создание тестового бота

```sql
INSERT INTO bots (name, exchange, symbol, strategy_type, config, total_capital, available_capital)
VALUES (
    'test_bot_btc_usdt',
    'binance',
    'BTC/USDT',
    'hybrid',
    '{"grid": {"lower": 40000, "upper": 45000, "levels": 10}, "dca": {"step_percent": 3, "max_steps": 5}}'::jsonb,
    10000.00,
    10000.00
);
```

---

## Статус

✅ **Схема готова к использованию**

**Следующие шаги:**
1. Создать базу данных
2. Применить схему (`psql < schema.sql`)
3. Настроить Alembic для миграций
4. Создать SQLAlchemy модели (Task 1.3)

---

**Файлы:**
- `dca_grid_bot/db/schema.sql` - DDL схема
- `dca_grid_bot/docs/DATABASE_DESIGN.md` - Данный документ
