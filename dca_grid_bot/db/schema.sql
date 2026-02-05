-- DCA-Grid Trading Bot Database Schema
-- PostgreSQL 14+
-- Version: 1.0
-- Date: 2026-02-05

-- ============================================================================
-- EXTENSIONS
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- For UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- For encryption functions

-- ============================================================================
-- TABLES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Таблица ботов
-- Хранит основную информацию о торговых ботах
-- ----------------------------------------------------------------------------
CREATE TABLE bots (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL UNIQUE,
    exchange VARCHAR(50) NOT NULL,           -- 'binance', 'bybit', 'okx'
    symbol VARCHAR(20) NOT NULL,             -- 'BTC/USDT', 'ETH/USDT'
    strategy_type VARCHAR(20) NOT NULL,      -- 'grid', 'dca', 'hybrid'
    config JSONB NOT NULL,                   -- Полная конфигурация (см. config.yaml)
    state VARCHAR(20) DEFAULT 'stopped' NOT NULL, -- 'running', 'paused', 'stopped', 'error', 'emergency'

    -- Капитал
    total_capital DECIMAL(20, 8) NOT NULL,
    available_capital DECIMAL(20, 8) NOT NULL,
    allocated_capital DECIMAL(20, 8) DEFAULT 0, -- Капитал в открытых ордерах

    -- Статистика
    total_trades INTEGER DEFAULT 0,
    total_profit DECIMAL(20, 8) DEFAULT 0,
    win_rate DECIMAL(5, 2) DEFAULT 0,        -- Процент прибыльных сделок

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    started_at TIMESTAMP,                     -- Время последнего запуска
    stopped_at TIMESTAMP,                     -- Время последней остановки

    CONSTRAINT chk_state CHECK (state IN ('running', 'paused', 'stopped', 'error', 'emergency')),
    CONSTRAINT chk_strategy CHECK (strategy_type IN ('grid', 'dca', 'hybrid')),
    CONSTRAINT chk_capital CHECK (total_capital >= 0 AND available_capital >= 0)
);

CREATE INDEX idx_bots_state ON bots(state);
CREATE INDEX idx_bots_exchange_symbol ON bots(exchange, symbol);

COMMENT ON TABLE bots IS 'Основная таблица торговых ботов';
COMMENT ON COLUMN bots.config IS 'JSONB конфигурация бота (параметры сетки, DCA, риск-менеджмент)';
COMMENT ON COLUMN bots.state IS 'Текущее состояние бота';

-- ----------------------------------------------------------------------------
-- Таблица API ключей бирж (зашифрованные)
-- Хранит зашифрованные API ключи для подключения к биржам
-- ----------------------------------------------------------------------------
CREATE TABLE exchange_credentials (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    exchange VARCHAR(50) NOT NULL,

    -- Зашифрованные данные (используется Fernet или AES-256)
    api_key_encrypted TEXT NOT NULL,
    api_secret_encrypted TEXT NOT NULL,
    passphrase_encrypted TEXT,               -- Для OKX и некоторых других бирж

    -- Метаданные
    is_testnet BOOLEAN DEFAULT FALSE,
    ip_whitelist TEXT[],                     -- Список разрешенных IP (если применимо)

    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    last_used_at TIMESTAMP,

    CONSTRAINT uq_bot_exchange UNIQUE(bot_id, exchange)
);

CREATE INDEX idx_creds_bot ON exchange_credentials(bot_id);

COMMENT ON TABLE exchange_credentials IS 'Зашифрованные API ключи для доступа к биржам';
COMMENT ON COLUMN exchange_credentials.api_key_encrypted IS 'API ключ зашифрован с использованием SECRET_KEY из переменных окружения';

-- ----------------------------------------------------------------------------
-- Таблица ордеров
-- Хранит информацию обо всех размещенных ордерах
-- ----------------------------------------------------------------------------
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,

    -- Идентификация ордера
    exchange_order_id VARCHAR(100),          -- ID ордера на бирже
    client_order_id VARCHAR(100),            -- Наш внутренний ID

    -- Параметры ордера
    symbol VARCHAR(20) NOT NULL,
    type VARCHAR(10) NOT NULL,               -- 'limit', 'market', 'stop_limit'
    side VARCHAR(10) NOT NULL,               -- 'buy', 'sell'
    price DECIMAL(20, 8),                    -- NULL для market ордеров
    amount DECIMAL(20, 8) NOT NULL,          -- Запрошенное количество
    filled DECIMAL(20, 8) DEFAULT 0,         -- Исполненное количество
    remaining DECIMAL(20, 8),                -- Оставшееся количество
    cost DECIMAL(20, 8),                     -- Общая стоимость (price * filled)

    -- Статус
    status VARCHAR(20) NOT NULL,             -- 'open', 'closed', 'canceled', 'expired', 'rejected'

    -- Стратегия
    strategy_component VARCHAR(20),          -- 'grid', 'dca', 'manual', 'stop_loss'
    grid_level INTEGER,                      -- Уровень сетки (если grid)
    dca_step INTEGER,                        -- Шаг DCA (если dca)

    -- Связи
    parent_order_id INTEGER REFERENCES orders(id), -- Для связанных ордеров (buy → sell)

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    closed_at TIMESTAMP,

    CONSTRAINT chk_order_type CHECK (type IN ('limit', 'market', 'stop_limit')),
    CONSTRAINT chk_order_side CHECK (side IN ('buy', 'sell')),
    CONSTRAINT chk_order_status CHECK (status IN ('open', 'closed', 'canceled', 'expired', 'rejected')),
    CONSTRAINT chk_order_amounts CHECK (amount > 0 AND filled >= 0 AND filled <= amount)
);

CREATE INDEX idx_orders_bot_status ON orders(bot_id, status);
CREATE INDEX idx_orders_exchange_id ON orders(exchange_order_id);
CREATE INDEX idx_orders_created ON orders(created_at DESC);
CREATE INDEX idx_orders_strategy ON orders(bot_id, strategy_component);

COMMENT ON TABLE orders IS 'Все ордера, размещенные ботом на биржах';
COMMENT ON COLUMN orders.parent_order_id IS 'Связь между buy и sell ордерами в сетке';

-- ----------------------------------------------------------------------------
-- Таблица сделок (исполненные ордера)
-- Хранит детальную информацию о каждой исполненной сделке
-- ----------------------------------------------------------------------------
CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL,

    -- Идентификация
    exchange_trade_id VARCHAR(100),

    -- Параметры сделки
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,               -- 'buy', 'sell'
    price DECIMAL(20, 8) NOT NULL,           -- Цена исполнения
    amount DECIMAL(20, 8) NOT NULL,          -- Количество
    cost DECIMAL(20, 8) NOT NULL,            -- Общая стоимость (price * amount)

    -- Комиссии
    fee DECIMAL(20, 8),
    fee_currency VARCHAR(10),

    -- P&L
    realized_pnl DECIMAL(20, 8),             -- Реализованная прибыль/убыток

    -- Время
    timestamp TIMESTAMP NOT NULL,            -- Время исполнения на бирже
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,

    CONSTRAINT chk_trade_side CHECK (side IN ('buy', 'sell')),
    CONSTRAINT chk_trade_amounts CHECK (price > 0 AND amount > 0 AND cost > 0)
);

CREATE INDEX idx_trades_bot_timestamp ON trades(bot_id, timestamp DESC);
CREATE INDEX idx_trades_order ON trades(order_id);
CREATE INDEX idx_trades_symbol ON trades(bot_id, symbol);

COMMENT ON TABLE trades IS 'Исполненные сделки с биржи';
COMMENT ON COLUMN trades.realized_pnl IS 'P&L рассчитывается при закрытии пары buy-sell';

-- ----------------------------------------------------------------------------
-- Таблица состояний бота (snapshots)
-- Периодические снапшоты состояния бота для восстановления
-- ----------------------------------------------------------------------------
CREATE TABLE bot_states (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,

    -- Snapshot данных
    state_data JSONB NOT NULL,               -- Полное состояние: позиции, средние цены, active levels

    -- Метаданные
    snapshot_type VARCHAR(20) DEFAULT 'periodic', -- 'periodic', 'before_stop', 'error'

    timestamp TIMESTAMP DEFAULT NOW() NOT NULL,

    CONSTRAINT chk_snapshot_type CHECK (snapshot_type IN ('periodic', 'before_stop', 'error', 'manual'))
);

CREATE INDEX idx_bot_states_bot_time ON bot_states(bot_id, timestamp DESC);

COMMENT ON TABLE bot_states IS 'Периодические снапшоты состояния бота для восстановления после сбоев';

-- ----------------------------------------------------------------------------
-- Таблица логов бота
-- Детальное логирование всех действий бота
-- ----------------------------------------------------------------------------
CREATE TABLE bot_logs (
    id BIGSERIAL PRIMARY KEY,
    bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE,

    -- Лог информация
    level VARCHAR(10) NOT NULL,              -- 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    message TEXT NOT NULL,
    component VARCHAR(50),                   -- 'GridEngine', 'DCAEngine', 'RiskManager', etc.

    -- Контекст
    context JSONB,                           -- Дополнительные данные (order_id, price, etc.)

    timestamp TIMESTAMP DEFAULT NOW() NOT NULL,

    CONSTRAINT chk_log_level CHECK (level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'))
);

CREATE INDEX idx_bot_logs_bot_time ON bot_logs(bot_id, timestamp DESC);
CREATE INDEX idx_bot_logs_level ON bot_logs(level, timestamp DESC);
CREATE INDEX idx_bot_logs_component ON bot_logs(component, timestamp DESC);

COMMENT ON TABLE bot_logs IS 'Логи всех действий и событий бота';

-- ----------------------------------------------------------------------------
-- Таблица уровней сетки (Grid Levels)
-- Хранит информацию об уровнях сеточной торговли
-- ----------------------------------------------------------------------------
CREATE TABLE grid_levels (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,

    -- Параметры уровня
    level_number INTEGER NOT NULL,           -- Номер уровня (0, 1, 2, ...)
    price DECIMAL(20, 8) NOT NULL,           -- Цена уровня
    side VARCHAR(10) NOT NULL,               -- 'buy' или 'sell'
    amount DECIMAL(20, 8) NOT NULL,          -- Количество для этого уровня

    -- Состояние
    is_active BOOLEAN DEFAULT TRUE,
    order_id INTEGER REFERENCES orders(id),  -- Текущий активный ордер на этом уровне

    -- Статистика
    times_triggered INTEGER DEFAULT 0,       -- Сколько раз сработал этот уровень
    total_volume DECIMAL(20, 8) DEFAULT 0,   -- Общий объем торговли на этом уровне

    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,

    CONSTRAINT uq_bot_level UNIQUE(bot_id, level_number),
    CONSTRAINT chk_grid_side CHECK (side IN ('buy', 'sell')),
    CONSTRAINT chk_grid_price CHECK (price > 0 AND amount > 0)
);

CREATE INDEX idx_grid_levels_bot ON grid_levels(bot_id, level_number);
CREATE INDEX idx_grid_levels_active ON grid_levels(bot_id, is_active);

COMMENT ON TABLE grid_levels IS 'Уровни сеточной торговли';

-- ----------------------------------------------------------------------------
-- Таблица истории DCA
-- Хранит информацию о шагах усреднения (DCA steps)
-- ----------------------------------------------------------------------------
CREATE TABLE dca_history (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,

    -- Параметры DCA шага
    step_number INTEGER NOT NULL,            -- Номер шага DCA
    trigger_price DECIMAL(20, 8) NOT NULL,   -- Цена, при которой сработал триггер
    buy_price DECIMAL(20, 8) NOT NULL,       -- Цена покупки
    amount DECIMAL(20, 8) NOT NULL,          -- Купленное количество
    cost DECIMAL(20, 8) NOT NULL,            -- Общая стоимость

    -- Результаты
    order_id INTEGER REFERENCES orders(id),
    average_entry_price DECIMAL(20, 8),      -- Средняя цена входа после этого DCA
    total_position DECIMAL(20, 8),           -- Общая позиция после этого DCA

    -- Цели
    target_sell_price DECIMAL(20, 8),        -- Целевая цена продажи

    timestamp TIMESTAMP DEFAULT NOW() NOT NULL,

    CONSTRAINT chk_dca_prices CHECK (buy_price > 0 AND amount > 0 AND cost > 0)
);

CREATE INDEX idx_dca_history_bot ON dca_history(bot_id, step_number);
CREATE INDEX idx_dca_history_time ON dca_history(bot_id, timestamp DESC);

COMMENT ON TABLE dca_history IS 'История шагов усреднения (DCA)';

-- ----------------------------------------------------------------------------
-- Таблица производительности (Performance Metrics)
-- Агрегированная статистика по дням/часам
-- ----------------------------------------------------------------------------
CREATE TABLE performance_metrics (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,

    -- Период
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    interval_type VARCHAR(10) NOT NULL,      -- 'hourly', 'daily', 'weekly'

    -- Метрики
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    total_volume DECIMAL(20, 8) DEFAULT 0,
    total_fees DECIMAL(20, 8) DEFAULT 0,
    realized_pnl DECIMAL(20, 8) DEFAULT 0,
    unrealized_pnl DECIMAL(20, 8) DEFAULT 0,

    -- Цены
    opening_price DECIMAL(20, 8),
    closing_price DECIMAL(20, 8),
    highest_price DECIMAL(20, 8),
    lowest_price DECIMAL(20, 8),

    created_at TIMESTAMP DEFAULT NOW() NOT NULL,

    CONSTRAINT chk_interval_type CHECK (interval_type IN ('hourly', 'daily', 'weekly', 'monthly')),
    CONSTRAINT uq_bot_period UNIQUE(bot_id, period_start, interval_type)
);

CREATE INDEX idx_perf_metrics_bot_period ON performance_metrics(bot_id, period_start DESC);

COMMENT ON TABLE performance_metrics IS 'Агрегированные метрики производительности по периодам';

-- ============================================================================
-- VIEWS
-- ============================================================================

-- Представление для активных ботов с открытыми ордерами
CREATE VIEW active_bots_summary AS
SELECT
    b.id,
    b.name,
    b.exchange,
    b.symbol,
    b.state,
    b.total_capital,
    b.available_capital,
    b.allocated_capital,
    COUNT(DISTINCT o.id) FILTER (WHERE o.status = 'open') as open_orders_count,
    COUNT(DISTINCT t.id) as total_trades_count,
    COALESCE(SUM(t.realized_pnl), 0) as total_realized_pnl
FROM bots b
LEFT JOIN orders o ON b.id = o.bot_id
LEFT JOIN trades t ON b.id = t.bot_id
WHERE b.state IN ('running', 'paused')
GROUP BY b.id;

COMMENT ON VIEW active_bots_summary IS 'Сводная информация по активным ботам';

-- Представление для P&L по ботам
CREATE VIEW bot_pnl_summary AS
SELECT
    b.id as bot_id,
    b.name,
    b.symbol,
    COUNT(t.id) as total_trades,
    COALESCE(SUM(t.realized_pnl), 0) as total_pnl,
    COALESCE(SUM(t.fee), 0) as total_fees,
    COALESCE(SUM(t.realized_pnl) - SUM(t.fee), 0) as net_pnl,
    COALESCE(AVG(t.realized_pnl), 0) as avg_pnl_per_trade
FROM bots b
LEFT JOIN trades t ON b.id = t.bot_id
GROUP BY b.id, b.name, b.symbol;

COMMENT ON VIEW bot_pnl_summary IS 'P&L статистика по ботам';

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Функция для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Применить триггер к таблицам
CREATE TRIGGER update_bots_updated_at BEFORE UPDATE ON bots
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_orders_updated_at BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_grid_levels_updated_at BEFORE UPDATE ON grid_levels
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Функция для расчета доступного капитала
CREATE OR REPLACE FUNCTION recalculate_available_capital(p_bot_id INTEGER)
RETURNS DECIMAL(20, 8) AS $$
DECLARE
    v_total_capital DECIMAL(20, 8);
    v_allocated_capital DECIMAL(20, 8);
BEGIN
    SELECT total_capital INTO v_total_capital
    FROM bots WHERE id = p_bot_id;

    SELECT COALESCE(SUM(amount * price), 0) INTO v_allocated_capital
    FROM orders
    WHERE bot_id = p_bot_id AND status = 'open';

    UPDATE bots
    SET
        allocated_capital = v_allocated_capital,
        available_capital = v_total_capital - v_allocated_capital
    WHERE id = p_bot_id;

    RETURN v_total_capital - v_allocated_capital;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION recalculate_available_capital IS 'Пересчитывает доступный капитал бота на основе открытых ордеров';

-- ============================================================================
-- INITIAL DATA (Optional)
-- ============================================================================

-- Можно добавить тестовые данные для разработки
-- INSERT INTO bots (name, exchange, symbol, strategy_type, config, total_capital, available_capital)
-- VALUES (...);

-- ============================================================================
-- MAINTENANCE
-- ============================================================================

-- Политика очистки старых логов (опционально, можно настроить через cronjob)
-- DELETE FROM bot_logs WHERE timestamp < NOW() - INTERVAL '30 days' AND level IN ('DEBUG', 'INFO');

-- ============================================================================
-- GRANTS (настроить права доступа)
-- ============================================================================

-- Создать пользователя для бота (опционально)
-- CREATE USER bot_user WITH PASSWORD 'secure_password';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO bot_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO bot_user;
