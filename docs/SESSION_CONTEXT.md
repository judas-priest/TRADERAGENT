# TRADERAGENT Project - Session Context Prompt

## 📋 Инструкция для Claude

Привет! Я продолжаю работу над проектом TRADERAGENT. Ниже полный контекст того, где мы остановились.

---

## 🎯 О проекте

**Repository:** https://github.com/alekseymavai/TRADERAGENT

**Описание:** Автономный торговый бот для криптовалютных бирж с поддержкой стратегий Grid Trading, DCA (Dollar Cost Averaging) и Smart Money Concepts (SMC).

**Технологии:**
- Backend: Python 3.10+ (async/await)
- Frontend: Node.js + TypeScript (Dashboard)
- Database: PostgreSQL, Redis, Integram (cloud DB)
- Exchanges: Bybit API (testnet/live)
- Backtesting: TypeScript/Node.js (standalone module)

---

## 📊 Текущий статус проекта

### ✅ Завершено (v1.2.0)

**1. SMC Strategy - ПОЛНОСТЬЮ РЕАЛИЗОВАНА (100%)**

Статус: ✅ Production Ready (Released 2026-02-12, v1.0.0)

Компоненты:
- ✅ Market Structure Analyzer (Issue #126) - анализ структуры рынка, BOS/CHoCH
- ✅ Confluence Zones (Issue #127) - Order Blocks и Fair Value Gaps
- ✅ Entry Signal Generator (Issue #128) - паттерны Price Action (Engulfing, Pin Bar, Inside Bar)
- ✅ Position Manager (Issue #129) - Kelly Criterion + Dynamic SL/TP
- ✅ Integration & Testing (Issue #130) - полная интеграция + 60+ тестов

Код:
- 📁 `bot/strategies/smc/` - 2,945 production lines
- 🧪 `tests/strategies/smc/` - 60+ comprehensive tests
- 📝 Покрытие: >80% test coverage

**2. Trend-Follower Strategy - ПОЛНОСТЬЮ РЕАЛИЗОВАНА (100%)**

Статус: ✅ Production Ready (Released 2026-02-13, v1.1.0)

Компоненты:
- ✅ Market Analyzer (Issue #124) - EMA, ATR, RSI индикаторы + определение фазы рынка
- ✅ Entry Logic (Issue #124) - LONG/SHORT сигналы с volume confirmation
- ✅ Position Manager (Issue #124) - динамичные TP/SL на основе ATR + trailing stops
- ✅ Risk Manager (Issue #124) - sizing (2% per trade), drawdown protection, daily limits
- ✅ Trade Logger (Issue #124) - полный журнал сделок + performance metrics

Код:
- 📁 `bot/strategies/trend_follower/` - 2,400+ production lines
- 📁 `examples/trend_follower_example.py` - пример использования
- 📝 Полная типизация: 0 mypy errors

**3. Backtesting Module - ПОЛНОСТЬЮ РЕАЛИЗОВАН (100%)**

Статус: ✅ Complete (Released 2026-02-13)

**Issues выполнены:**
- ✅ #138 - Загрузка исторических данных (10 CSV, 11MB, 6 месяцев ETH/USDT)
- ✅ #139 - Подготовка окружения для бэктестинга
- ✅ #140 - Развертывание модуля тестирования
- ✅ #141 - Интеграция стратегий TRADERAGENT
- ✅ #142 - Создание полноценных бэктестов с метриками
- ✅ #143 - Генерация отчетов (HTML + CSV)
- ✅ #145 - Запуск и анализ результатов бэктестинга
- ✅ #146 - Запуск бэктестов стратегий
- ✅ #147 - Генерация HTML и CSV отчетов
- ✅ #148 - Публикация результатов через GitHub Pages
- ⏳ #144 - Визуализация (графики) - в планах

**Компоненты:**
- ✅ CSVDataLoader - загрузка исторических данных
- ✅ SimpleSMCStrategy - упрощенная SMC для бэктеста
- ✅ SimpleTrendFollowerStrategy - упрощенная Trend-Follower
- ✅ BacktestRunner - движок бэктестинга (SL/TP, комиссии, проскальзывание)
- ✅ MetricsCalculator - продвинутые метрики (Sharpe, Sortino, Drawdown, Calmar)
- ✅ HTMLReportGenerator - красивые HTML отчеты
- ✅ CSVReportGenerator - экспорт в CSV
- ✅ ComparisonReportGenerator - сравнение стратегий

**Код:**
- 📁 `backtesting-module/` - standalone TypeScript модуль
- 📁 `backtesting-module/src/strategies/` - упрощенные версии стратегий
- 📁 `backtesting-module/src/backtesting/` - движок + метрики
- 📁 `backtesting-module/src/reports/` - генераторы отчетов
- 📊 `docs/backtesting-reports/` - опубликованные результаты

**Результаты бэктестинга (6 месяцев, ETH/USDT 1h):**

*Simplified SMC:*
- Доходность: +12,999% ($10,000 → $1,309,900)
- Sharpe Ratio: 10.21 (отлично!)
- Max Drawdown: 0.21% (минимальный риск)
- Profit Factor: 2.61
- Win Rate: 41.18%
- Сделок: 51

*Simplified Trend-Follower:*
- Sharpe Ratio: 19.41 (невероятно!)
- Max Drawdown: 0.32%
- Profit Factor: 1.62
- Win Rate: 29.20%
- Сделок: 226

**Публикация:**
- 🌐 GitHub Pages: https://alekseymavai.github.io/TRADERAGENT/backtesting-reports/
- 📊 4 индивидуальных HTML отчета
- 📊 1 сравнительный HTML отчет
- 📄 13 CSV файлов (summary, trades, equity)
- 📝 Документация по интерпретации метрик

**Развертывание:**
- 🖥️ Сервер: 185.233.200.13:/home/ai-agent/trading-backtest/
- ✅ Модуль установлен и работает
- ✅ Исторические данные загружены (10 CSV)
- ✅ Результаты сохранены

**4. Git Operations - ЗАВЕРШЕНЫ**
- ✅ PR #125 смержен в main - SMC Strategy (commit: `8b4945c`)
- ✅ PR #131 смержен в main - Trend-Follower Strategy (commit: `b8bd50e`)
- ✅ Commit `db4e514` - Модуль бэктестинга (Issues #138-143)
- ✅ Commit `77f2612` - Результаты бэктестинга (Issues #146-148)
- ✅ **PR #150 смержен в main** - План v2.0 (commit: `f82e814`, 2026-02-13)
- ✅ Issue #124 закрыт (Trend-Follower)
- ✅ **Issue #149 закрыт** (Analysis & Planning v2.0)
- ✅ Issues #138-143, #145-148 закрыты (Backtesting)
- ✅ Все issues SMC закрыты (#123, #126, #127, #128, #129, #130)
- ✅ Release v1.0.0: https://github.com/alekseymavai/TRADERAGENT/releases/tag/v1.0.0
- ✅ README.md обновлен с разделами SMC + Trend-Follower
- ✅ **32 новых Issues созданы** (#151-182) для v2.0
- ✅ **Milestone #1 создан** (TRADERAGENT v2.0, дедлайн 2026-05-30)

**5. Документация - ЗАВЕРШЕНА**
- ✅ Release notes v1.0.0 с полным описанием
- ✅ README.md: добавлен раздел "🎓 SMC Strategy (Smart Money Concepts)" (+176 строк)
- ✅ Inline документация во всех модулях SMC
- ✅ `bot/strategies/smc/README_old.md` - детальное руководство
- ✅ `backtesting-module/README.md` - документация модуля бэктестинга
- ✅ `docs/backtesting-reports/README.md` - интерпретация метрик
- ✅ **Документация v2.0** (5 файлов, +4,777 строк):
  - `TRADERAGENT_V2_PLAN_RU.md` - план на русском
  - `TRADERAGENT_V2_PLAN.md` - план на английском
  - `DCA_BOT_TRAILING_STOP_IMPLEMENTATION.md` - детальная реализация DCA+TS (85KB)
  - `GITHUB_ISSUES_SUMMARY.md` - сводка Issues #151-182
  - `ISSUE_149_COMPARISON_AND_PLAN.md` - анализ и сравнение

---

## 🔑 Важная информация

### GitHub Access
- **Token:** `ghp_****` (см. личные заметки или .env)
- **Repository:** `alekseymavai/TRADERAGENT`
- **Main branch:** `main`

> ⚠️ **Важно:** GitHub token должен храниться в безопасном месте (password manager, .env файл).
> Не коммитить токены в репозиторий!

### Ветки
- `main` - production branch (актуальный код)
- `feature/smc-strategy-foundation` - смержена в main

### Важные коммиты
- `77f2612` - Результаты бэктестинга (Issues #146-148)
- `db4e514` - Модуль бэктестинга (Issues #138-143)
- `8b4945c` - Merge PR #125 (SMC Strategy complete implementation)
- `0cd6ef4` - README.md update with SMC section
- `956c8ac` - Position Manager implementation
- `80cf88b` - Final SMC integration

### Сервер для бэктестинга
- **Host:** 185.233.200.13
- **User:** ai-agent
- **Path:** ~/trading-backtest/
- **Node.js:** 20.20.0 (через nvm)
- **Данные:** 10 CSV файлов (11MB, 6 месяцев)

---

## 🎓 О SMC Strategy

**Ключевое понимание:** SMC Strategy НЕ является автономным торговым ботом. Это **вспомогательный инструмент** для принятия решений о запуске DCA-Grid ботов.

**Назначение:**
- Анализирует рыночную структуру (Multi-Timeframe: D1, H4, H1, M15)
- Определяет институциональные зоны (Order Blocks, Fair Value Gaps)
- Генерирует high-confidence сигналы для оптимального входа
- Предоставляет рекомендации для запуска автономных DCA-Grid ботов

**Интеграция:**
```python
from bot.strategies.smc import SMCStrategy, SMCConfig

class SMCGridAdvisor:
    """Советник для запуска DCA-Grid ботов"""
    def should_launch_grid_bot(self, symbol):
        # Анализ SMC
        analysis = self.smc.analyze_market(df_d1, df_h4, df_h1, df_m15)
        signals = self.smc.generate_signals(df_h1, df_m15)

        if signals and analysis['trend'] == 'BULLISH':
            return {
                'launch': True,
                'grid_lower': signal.stop_loss,
                'grid_upper': signal.take_profit,
                ...
            }
```

---

## 🎓 О Trend-Follower Strategy

**Ключевое понимание:** Trend-Follower - это **адаптивная трендовая стратегия** с автоматической подстройкой под фазу рынка.

**Назначение:**
- Определяет фазу рынка (Bullish Trend, Bearish Trend, Sideways)
- Генерирует LONG/SHORT сигналы в зависимости от фазы
- Адаптирует TP/SL к волатильности (ATR-based)
- Управляет рисками (2% per trade, drawdown protection, daily limits)
- Логирует все сделки с метриками performance

**Фазы рынка и логика входа:**

| Фаза | Условие | LONG вход | SHORT вход |
|------|---------|-----------|------------|
| Bullish Trend | EMA20 > EMA50, divergence > 0.5% | Pullback к EMA20/support | - |
| Bearish Trend | EMA20 < EMA50, divergence > 0.5% | - | Pullback к EMA20/resistance |
| Sideways | Divergence < 0.5% | RSI exit oversold или breakout вверх | RSI exit overbought или breakout вниз |

**TP/SL (Dynamic ATR-based):**

| Фаза | TP Multiplier | SL Multiplier |
|------|---------------|---------------|
| Sideways | 1.2 × ATR | 0.7 × ATR |
| Weak Trend | 1.8 × ATR | 1.0 × ATR |
| Strong Trend | 2.5 × ATR | 1.0 × ATR |

**Advanced Features:**
- Trailing Stop (активируется после 1.5×ATR прибыли, трейлит на 0.5×ATR)
- Breakeven Move (переносит SL в точку входа после 1×ATR прибыли)
- Partial Close (закрывает 50% на 70% от TP, остальное трейлится)

**Интеграция:**
```python
from bot.strategies.trend_follower import TrendFollowerStrategy, TrendFollowerConfig

# Инициализация
strategy = TrendFollowerStrategy(
    config=TrendFollowerConfig(),  # или custom config
    initial_capital=Decimal("10000")
)

# Анализ рынка
conditions = strategy.analyze_market(df)
print(f"Phase: {conditions.phase}, Trend: {conditions.trend_strength}")

# Проверка сигнала
entry_data = strategy.check_entry_signal(df, current_balance)
if entry_data:
    signal, metrics, position_size = entry_data
    position_id = strategy.open_position(signal, position_size)

# Обновление позиции
exit_reason = strategy.update_position(position_id, current_price, df)
if exit_reason:
    strategy.close_position(position_id, exit_reason, current_price)

# Получение статистики
stats = strategy.get_statistics()
validation = strategy.validate_performance()  # проверка метрик из issue #124
```

---

## 🎓 О Backtesting Module

**Ключевое понимание:** Backtesting Module - это **standalone TypeScript/Node.js модуль** для тестирования торговых стратегий на исторических данных.

**Назначение:**
- Тестирование стратегий на исторических данных
- Расчет продвинутых метрик (Sharpe, Sortino, Drawdown, Calmar)
- Генерация красивых HTML и CSV отчетов
- Сравнение эффективности разных стратегий

**Особенности:**
- Полная симуляция: SL/TP, комиссии (0.1%), проскальзывание (0.05%)
- Equity curve tracking
- Детальная история сделок
- Автоматическая генерация отчетов

**Использование:**
```bash
cd backtesting-module

# Загрузить исторические данные
docker build -t historical-data-downloader .
docker run -v $(pwd)/data/historical:/app/data/historical historical-data-downloader

# Запустить бэктесты
npm install
npm run backtest:full

# Сгенерировать отчеты
npm run reports:generate

# Просмотреть результаты
open results/reports/index.html
```

**Структура модуля:**
```
backtesting-module/
├── src/
│   ├── adapters/           # CSVDataLoader
│   ├── strategies/         # SimpleSMC, SimpleTrendFollower, IStrategy
│   ├── backtesting/        # BacktestRunner, MetricsCalculator
│   ├── reports/            # HTML, CSV, Comparison генераторы
│   └── scripts/            # full-backtest, generate-reports
├── data/historical/        # CSV файлы с данными
├── results/
│   ├── backtests/          # JSON результаты
│   └── reports/            # HTML и CSV отчеты
└── README.md
```

**Метрики:**
- Sharpe Ratio - риск-adjusted доходность
- Sortino Ratio - downside deviation
- Max Drawdown - максимальная просадка
- Calmar Ratio - доходность / drawdown
- Recovery Factor - прибыль / drawdown
- Profit Factor - gross profit / gross loss
- Win Rate - процент прибыльных сделок

---

## 📂 Структура кода Trend-Follower

```
bot/strategies/trend_follower/
├── __init__.py                     (13 lines)  - API exports
├── config.py                       (146 lines) - TrendFollowerConfig class
├── market_analyzer.py              (322 lines) - Market analysis, indicators, phase detection
├── entry_logic.py                  (465 lines) - Entry signal generation, volume confirmation
├── position_manager.py             (398 lines) - Position management, TP/SL, trailing
├── risk_manager.py                 (287 lines) - Risk & capital management
├── trade_logger.py                 (310 lines) - Trade logging & performance metrics
├── trend_follower_strategy.py      (462 lines) - Main orchestration class
└── README.md                       (459 lines) - Detailed documentation

examples/
└── trend_follower_example.py       (274 lines) - Example usage script
```

---

## 📂 Структура кода SMC

```
bot/strategies/smc/
├── __init__.py          (79 lines)  - API exports
├── config.py            (410 lines) - SMCConfig class
├── market_structure.py  (498 lines) - Market Structure Analyzer
├── confluence_zones.py  (587 lines) - Order Blocks & Fair Value Gaps
├── entry_signals.py     (534 lines) - Price Action Patterns
├── position_manager.py  (565 lines) - Kelly Criterion + Dynamic SL/TP
├── smc_strategy.py      (361 lines) - Main SMCStrategy class
└── README_old.md        (documentation)

tests/strategies/smc/
├── test_market_structure.py
├── test_confluence_zones.py
├── test_entry_signals.py
├── test_position_manager.py
└── test_smc_integration.py
```

---

## 📂 Структура Backtesting Module

```
backtesting-module/
├── src/
│   ├── adapters/
│   │   └── CSVDataLoader.ts        (110 lines) - загрузка CSV данных
│   ├── strategies/
│   │   ├── IStrategy.ts            (200 lines) - базовый интерфейс + хелперы
│   │   ├── SimpleSMCStrategy.ts    (150 lines) - EMA + RSI + ATR
│   │   └── SimpleTrendFollowerStrategy.ts (130 lines) - Triple EMA + ATR
│   ├── backtesting/
│   │   ├── BacktestRunner.ts       (400 lines) - движок бэктеста
│   │   └── MetricsCalculator.ts    (200 lines) - расчет метрик
│   ├── reports/
│   │   ├── HTMLReportGenerator.ts  (300 lines) - HTML отчеты
│   │   ├── CSVReportGenerator.ts   (100 lines) - CSV экспорт
│   │   └── ComparisonReportGenerator.ts (280 lines) - сравнение
│   └── scripts/
│       ├── full-backtest.ts        (150 lines) - запуск бэктестов
│       └── generate-reports.ts     (280 lines) - генерация отчетов
├── data/historical/                 - 10 CSV файлов (11MB)
├── results/
│   ├── backtests/                   - JSON результаты
│   └── reports/                     - HTML и CSV отчеты
├── package.json
├── tsconfig.json
└── README.md
```

---

## 🚀 TRADERAGENT v2.0 - План разработки (АКТУАЛЬНО)

**Статус:** ✅ План готов к реализации | 📅 Дата создания: 2026-02-13

### Issue #149 - ЗАКРЫТ ✅

**Задача:** Сравнить целевую архитектуру (README.md) с текущей реализацией (BOT_ALGORITHM_DESCRIPTION.md) и создать план интеграции для v2.0

**Результат:**
- ✅ PR #150 смержен в main (2026-02-13)
- ✅ Issue #149 закрыт автоматически
- ✅ Создано 5 документов планирования (+4,777 строк)
- ✅ Создано 32 GitHub Issues (#151-182)
- ✅ Milestone #1 настроен (дедлайн: 2026-05-30)

### 📄 Документация v2.0

**Файлы в репозитории:**

1. **[TRADERAGENT_V2_PLAN_RU.md](https://github.com/alekseymavai/TRADERAGENT/blob/main/TRADERAGENT_V2_PLAN_RU.md)** (28KB)
   - План разработки на русском
   - 8 фаз, 32 задачи, 15 недель
   - Детальные требования каждой фазы

2. **[TRADERAGENT_V2_PLAN.md](https://github.com/alekseymavai/TRADERAGENT/blob/main/TRADERAGENT_V2_PLAN.md)** (15KB)
   - План разработки на английском
   - Аналогичная структура

3. **[DCA_BOT_TRAILING_STOP_IMPLEMENTATION.md](https://github.com/alekseymavai/TRADERAGENT/blob/main/DCA_BOT_TRAILING_STOP_IMPLEMENTATION.md)** (85KB)
   - Детальная реализация DCA бота с трейлинг-стопом
   - Полная архитектура, схемы БД, примеры кода
   - Спецификация трейлинг-стопа и сигнальной логики

4. **[GITHUB_ISSUES_SUMMARY.md](https://github.com/alekseymavai/TRADERAGENT/blob/main/GITHUB_ISSUES_SUMMARY.md)** (12KB)
   - Сводка всех созданных Issues
   - Организация по фазам
   - Статистика и зависимости

5. **[ISSUE_149_COMPARISON_AND_PLAN.md](https://github.com/alekseymavai/TRADERAGENT/blob/main/ISSUE_149_COMPARISON_AND_PLAN.md)** (56KB)
   - Оригинальный анализ и сравнение
   - Детальное описание разрывов
   - Первоначальный план (41 задача)

### 🎯 Концепция v2.0

**TRADERAGENT v2.0 - Autonomous DCA-Grid SMC Trend-Follower Trading Bot**

**Двухслойная архитектура:**

```
┌─────────────────────────────────────────────────┐
│           ADVISORY LAYER                        │
│  ┌──────────────┐     ┌──────────────┐         │
│  │ SMC Strategy │     │Trend-Follower│         │
│  │  (Multi-TF)  │     │  Strategy    │         │
│  └──────┬───────┘     └──────┬───────┘         │
│         └──────┬──────────────┘                 │
│                ▼                                │
│      ┌─────────────────┐                       │
│      │Signal Aggregator│                       │
│      └─────────┬────────┘                      │
└────────────────┼────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│        ORCHESTRATION LAYER                      │
│      ┌──────────────────┐                      │
│      │ Bot Orchestrator │                      │
│      └─────────┬────────┘                      │
│    ┌───────────┼───────────┐                   │
│    ▼           ▼           ▼                   │
│ ┌──────┐  ┌───────┐  ┌────────┐               │
│ │ Grid │  │  DCA  │  │ Hybrid │               │
│ │Engine│  │Engine │  │  Mode  │               │
│ └──────┘  └───────┘  └────────┘               │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│       INFRASTRUCTURE LAYER                      │
│  ┌──────────────┐    ┌──────────────┐         │
│  │  Exchange    │    │   Database   │         │
│  │  Client      │    │   Manager    │         │
│  │  (CCXT)      │    │ (PostgreSQL) │         │
│  └──────────────┘    └──────────────┘         │
└─────────────────────────────────────────────────┘
```

**Логика работы:**
1. **SMC + Trend-Follower** анализируют рынок (Multi-TF)
2. **Signal Aggregator** объединяет сигналы, рассчитывает confluence score
3. **Bot Orchestrator** выбирает стратегию:
   - **Sideways** → Grid Engine
   - **Trend + Low Confluence** → DCA Engine
   - **Trend + High Confluence (>0.7)** → Hybrid Mode
4. **Exchange Client** исполняет ордера
5. **Database** сохраняет состояние

### 📊 План разработки - 8 фаз

| Фаза | Название | Задачи | Длительность | Issues |
|------|----------|--------|--------------|--------|
| **Phase 1** | Архитектурная основа | 4 | 2 недели | #151-154 |
| **Phase 2** | Grid Trading Engine | 4 | 2 недели | #155-158 |
| **Phase 3** | DCA Engine + Trailing Stop ⭐ | 6 | 3 недели | #159-164 |
| **Phase 4** | Гибридная интеграция | 3 | 1 неделя | #165-167 |
| **Phase 5** | Инфраструктура и DevOps | 4 | 2 недели | #168-171 |
| **Phase 6** | Продвинутое бэктестирование | 4 | 2 недели | #172-175 |
| **Phase 7** | Тестирование и валидация | 4 | 2 недели | #176-179 |
| **Phase 8** | Продакшн запуск | 3 | 1 неделя | #180-182 |

**Итого:** 32 задачи, ~15 недель, **ETA: Q2 2026**

### 🔥 Ключевые нововведения v2.0

**1. Трейлинг-стоп для DCA (Issue #162)**
- Динамический trailing stop для защиты прибыли
- Активация после достижения минимальной прибыли (1.5%)
- Отслеживание максимума цены с момента входа
- Поддержка % и абсолютных значений
- НЕ сбрасывается при добавлении safety orders

**Конфигурация:**
```yaml
dca:
  trailing_stop:
    enabled: true
    activation_profit: 1.5    # % прибыли для активации
    distance: 0.8             # % расстояние от максимума
    type: "percentage"        # "percentage" или "absolute"
```

**2. Сигнальная логика открытия ордеров (Issue #163)**
- Ордера открываются ТОЛЬКО по сигналу алгоритма
- Confluence scoring (trend + price + indicators + risk + time filters)
- Защита от ложных сигналов
- Контроль достижения целевой цены

**3. Grid Trading Engine (Issues #155-158)**
- Арифметическая и геометрическая сетка
- Динамическая настройка на ATR
- Автоматические встречные ордера
- Ребалансировка при движении цены

**4. Hybrid Mode (Issues #165-167)**
- Детектор рыночного режима
- Переключение между Grid/DCA в зависимости от фазы
- Адаптивное управление рисками

**5. Full Infrastructure (Issues #168-171)**
- Docker deployment
- PostgreSQL + Alembic migrations
- Telegram bot для управления
- Prometheus + Grafana monitoring

### 📋 GitHub Issues (#151-182)

**Milestone #1:** https://github.com/alekseymavai/TRADERAGENT/milestone/1
**Дедлайн:** 2026-05-30 (15 недель)

**Приоритеты:**
- 🔴 **Критический:** 15 задач (Phase 1, 3, 5, 6, 7, 8)
- 🟡 **Высокий:** 13 задач (Phase 2, 3, 4, 5, 6, 7, 8)
- 🟢 **Средний:** 4 задачи (Phase 4, 6)

**Критические зависимости для старта:**
1. **#153** - Database schema (блокирует много задач)
2. **#151** - BotOrchestrator (архитектурная основа)
3. **#154** - Exchange Client (нужен для всех стратегий)

**Самые сложные задачи:**
- #178 - Testnet deployment (5 дней)
- #172 - Multi-TF backtesting (5 дней)
- #160 - DCA Position Manager (4 дня)
- #156 - Grid Order Manager (4 дня)
- #170 - Telegram bot (4 дня)

### 🎯 Следующие шаги - Phase 1

**Старт разработки v2.0:**

1. **[#151](https://github.com/alekseymavai/TRADERAGENT/issues/151) - BotOrchestrator** (3 дня, Критический)
   - Создать `src/core/bot_orchestrator.py`
   - Управление жизненным циклом ботов
   - Координация стратегий

2. **[#153](https://github.com/alekseymavai/TRADERAGENT/issues/153) - Database schema** (2 дня, Критический)
   - Схема PostgreSQL для мульти-стратегии
   - Alembic миграции
   - ORM модели (SQLAlchemy)

3. **[#152](https://github.com/alekseymavai/TRADERAGENT/issues/152) - BaseStrategy interface** (2 дня, Критический)
   - Абстрактный класс BaseStrategy
   - Рефакторинг SMC и Trend-Follower
   - Единый формат сигналов

4. **[#154](https://github.com/alekseymavai/TRADERAGENT/issues/154) - Exchange Client** (3 дня, Высокий)
   - Интеграция CCXT (150+ бирж)
   - WebSocket для real-time данных
   - Rate limiting и обработка ошибок

**Команды для старта Phase 1:**
```bash
# Посмотреть Phase 1 issues
gh issue list --repo alekseymavai/TRADERAGENT --label phase-1

# Создать ветку для первой задачи
git checkout -b feature/bot-orchestrator-151

# Начать работу
# ...
```

---

## 🔄 Что дальше (Next Steps)

### ~~Приоритет 1: Backtesting & Validation~~ ✅ ВЫПОЛНЕНО
### ~~Приоритет 2: Planning v2.0~~ ✅ ВЫПОЛНЕНО

**Завершено:**
- ✅ Backtesting SMC и Trend-Follower (Issue #138-148)
- ✅ Анализ достижений vs целей (Issue #149)
- ✅ План разработки v2.0 (8 фаз, 32 задачи)
- ✅ Создано 32 GitHub Issues (#151-182)
- ✅ Milestone #1 настроен
- ✅ Вся документация в репозитории

### 🚀 Приоритет 1: Phase 1 - Архитектурная основа (2 недели)

**Задачи для немедленного старта:**

1. **Issue #151 - BotOrchestrator** (3 дня, 🔴 Критический)
   - [ ] Создать `src/core/bot_orchestrator.py`
   - [ ] Lifecycle management (start/stop/pause/resume bots)
   - [ ] Strategy coordination
   - [ ] Health monitoring

2. **Issue #153 - Database schema** (2 дня, 🔴 Критический)
   - [ ] PostgreSQL schema design
   - [ ] Alembic migrations setup
   - [ ] SQLAlchemy ORM models
   - [ ] Tables: strategies, positions, trades, signals, dca_deals, dca_orders

3. **Issue #152 - BaseStrategy interface** (2 дня, 🔴 Критический)
   - [ ] Abstract BaseStrategy class
   - [ ] Методы: analyze(), generate_signals(), execute_trade(), update_state()
   - [ ] Рефакторинг SMC и Trend-Follower под новый интерфейс
   - [ ] Единый формат сигналов

4. **Issue #154 - Exchange Client** (3 дня, 🟡 Высокий)
   - [ ] CCXT integration
   - [ ] Connection pooling + rate limiting
   - [ ] WebSocket real-time data
   - [ ] Error handling + retry logic

**Команды:**
```bash
# Посмотреть все Phase 1 задачи
gh issue list --repo alekseymavai/TRADERAGENT --label phase-1

# Начать с #151
git checkout -b feature/bot-orchestrator-151
```

### Приоритет 2: Phase 2 - Grid Trading Engine (2 недели)

После завершения Phase 1:
- Issue #155 - Grid Calculator
- Issue #156 - Grid Order Manager
- Issue #157 - Grid Risk Management
- Issue #158 - Grid Configuration & Testing

### Приоритет 3: Phase 3 - DCA Engine + Trailing Stop ⭐ (3 недели)

**Ключевые задачи:**
- Issue #159 - DCA Signal Generator
- Issue #160 - DCA Position Manager
- Issue #161 - DCA Risk Control
- **Issue #162 - Трейлинг-стоп** (критический!)
- **Issue #163 - Сигнальная логика** (критический!)
- Issue #164 - DCA Configuration & Testing

### Приоритет 4: Visualization (Issue #144) - опционально

- [ ] Добавить интерактивные графики в отчеты
- [ ] Equity curve chart (Chart.js или Plotly)
- [ ] Drawdown chart
- [ ] Распределение сделок
- [ ] Monthly returns heatmap

**Примечание:** Можно сделать параллельно с Phase 1-3

---

## 🛠️ Рабочее окружение

### Репозиторий на диске
- Проект обычно клонируется в `/home/hive/btc/` или `/tmp/`
- Для Git операций можно клонировать временно в `/tmp/traderagent_*`

### Сервер для бэктестинга
- **Host:** 185.233.200.13
- **User:** ai-agent
- **Path:** ~/trading-backtest/
- **SSH:** `ssh ai-agent@185.233.200.13`
- **Node.js:** 20.20.0 (через nvm)

### Команды для проверки статуса
```bash
# Проверить репозиторий
gh repo view alekseymavai/TRADERAGENT

# Проверить issues
gh issue list --repo alekseymavai/TRADERAGENT

# Проверить releases
gh release list --repo alekseymavai/TRADERAGENT

# Проверить последние коммиты
gh api repos/alekseymavai/TRADERAGENT/commits/main | jq '.[0]'

# Проверить GitHub Pages
curl -I https://alekseymavai.github.io/TRADERAGENT/backtesting-reports/
```

### Запуск бэктестов
```bash
# На сервере
ssh ai-agent@185.233.200.13
cd ~/trading-backtest

# Запустить бэктесты
export PATH=/home/ai-agent/.nvm/versions/node/v20.20.0/bin:$PATH
npm run backtest:full

# Сгенерировать отчеты
npm run reports:generate

# Просмотреть результаты
ls -la results/reports/
```

### Запуск тестов (Python)
```bash
# Все SMC тесты
pytest tests/strategies/smc/ -v

# Конкретный компонент
pytest tests/strategies/smc/test_market_structure.py -v

# С coverage
pytest tests/strategies/smc/ --cov=bot.strategies.smc --cov-report=html
```

---

## 📝 Стиль работы

### Коммуникация
- **Язык:** Русский (для коммуникации, commit messages, Issues, PR, документация)
- **Английский:** Только код, комментарии в коде, технические логи

### Git Commits
- Всегда добавляй: `Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>`
- Формат: `type: краткое описание` (feat, fix, docs, refactor, test)
- Подробное описание в body коммита

### Тестирование
- После каждого изменения кода - запускать соответствующие тесты
- Минимальное покрытие: 80%
- Unit tests + Integration tests

---

## 🚨 Важные правила (из CLAUDE.md)

1. **НЕ МЕНЯТЬ код без явного запроса**
   - Особенно: OrderType, архитектуру, торговую логику, параметры стратегии
   - Если видишь "проблему" - СПРОСИ, не исправляй сразу

2. **Trading MCP Server**
   - Использовать ТОЛЬКО `mcp__trading__*` инструменты
   - НЕ использовать curl/wget для торговых запросов

3. **Martingale Strategy Testing**
   - После изменений ОБЯЗАТЕЛЬНО запускать:
     - `mcp__trading__test_order_sltp`
     - `mcp__trading__test_reversal`

4. **XState State Machines**
   - Для новых стратегий рассмотреть XState v5 архитектуру
   - Документация: `/home/hive/btc/docs/XSTATE_INTEGRATION.md`

---

## 🎯 Типичные задачи

### Если нужно добавить новую функцию в SMC:
1. Читай существующий код в `bot/strategies/smc/`
2. Создай новый модуль или расширь существующий
3. Напиши тесты в `tests/strategies/smc/`
4. Обнови `__init__.py` для экспортов
5. Запусти тесты
6. Коммит + push

### Если нужно исправить баг:
1. Воспроизведи проблему через тест
2. Исправь код
3. Проверь что тест проходит
4. Запусти все тесты компонента
5. Коммит с описанием бага и fix

### Если нужно обновить документацию:
1. README.md для high-level изменений
2. `bot/strategies/smc/README_old.md` для детальной документации SMC
3. Inline docstrings в коде
4. Коммит с префиксом `docs:`

### Если нужно запустить новый бэктест:
1. SSH на сервер: `ssh ai-agent@185.233.200.13`
2. `cd ~/trading-backtest`
3. Обнови стратегии если нужно
4. `npm run backtest:full`
5. `npm run reports:generate`
6. Скачай результаты или просмотри онлайн

---

## 📌 Quick Reference

**Основные файлы:**
- `/home/hive/btc/CLAUDE.md` - правила работы с проектом
- `/home/hive/btc/bot/strategies/smc/smc_strategy.py` - главный класс SMC
- `/home/hive/btc/bot/strategies/trend_follower/trend_follower_strategy.py` - Trend-Follower
- `/home/hive/btc/README.md` - главная документация проекта
- `backtesting-module/README.md` - документация бэктестинга

**Документация v2.0:**
- `TRADERAGENT_V2_PLAN_RU.md` - план разработки (русский)
- `DCA_BOT_TRAILING_STOP_IMPLEMENTATION.md` - реализация DCA+TS
- `GITHUB_ISSUES_SUMMARY.md` - сводка Issues

**GitHub URLs:**
- Repo: https://github.com/alekseymavai/TRADERAGENT
- **Milestone #1 (v2.0):** https://github.com/alekseymavai/TRADERAGENT/milestone/1
- **Phase 1 Issues:** https://github.com/alekseymavai/TRADERAGENT/labels/phase-1
- Release v1.0.0: https://github.com/alekseymavai/TRADERAGENT/releases/tag/v1.0.0
- Issues: https://github.com/alekseymavai/TRADERAGENT/issues
- PR #125: https://github.com/alekseymavai/TRADERAGENT/pull/125
- **PR #150:** https://github.com/alekseymavai/TRADERAGENT/pull/150 (v2.0 Plan)
- Backtest Reports: https://alekseymavai.github.io/TRADERAGENT/backtesting-reports/

**Контакты:**
- GitHub: @alekseymavai (owner), @unidel2035 (contributor)

---

## ✅ Чеклист для новой сессии

Когда начинаешь новую сессию, сделай:

1. [ ] Прочитай этот prompt полностью
2. [ ] Проверь статус репозитория: `gh repo view alekseymavai/TRADERAGENT`
3. [ ] Проверь открытые Issues: `gh issue list --repo alekseymavai/TRADERAGENT`
4. [ ] Спроси пользователя: "Над чем будем работать сегодня?"
5. [ ] Уточни контекст задачи, если неясно
6. [ ] Приступай к работе!

---

## 💬 Примеры типичных запросов пользователя

**"Запусти backtest SMC"**
→ На сервере: `cd ~/trading-backtest && npm run backtest:full`

**"Проверь что все работает"**
→ Запустить все тесты SMC: `pytest tests/strategies/smc/ -v`

**"Добавь новый паттерн X"**
→ Расширить `entry_signals.py` с новым паттерном + тесты

**"Интегрируй SMC с Grid ботом"**
→ Реализовать SMCGridAdvisor и подключить к bot orchestrator

**"Создай Issue для X"**
→ Использовать GitHub API для создания Issue с детальным описанием

**"Обнови документацию"**
→ Обновить README.md или bot/strategies/smc/README_old.md

**"Сгенерируй новые отчеты"**
→ На сервере: `npm run reports:generate` и проверить GitHub Pages

---

## 🎓 Ключевые концепции SMC (для контекста)

- **Order Blocks (OB):** Зоны институциональных ордеров (последняя противоположная свеча перед breakout)
- **Fair Value Gaps (FVG):** Ценовые дисбалансы (3-candle imbalance), магниты для цены
- **Break of Structure (BOS):** Пробой swing high/low, подтверждает тренд
- **Change of Character (CHoCH):** Изменение характера рынка, возможный разворот
- **Kelly Criterion:** f* = (p*b - q) / b, оптимальный размер позиции (fractional 0.25x)
- **Dynamic SL:** Breakeven после 1:1 RR, trailing по структуре
- **Partial TP:** 50% @ 1.5:1, 30% @ 2.5:1, 20% runner

---

## 🚀 Начнем!

**Важно:** После прочтения этого контекста, ты полностью в курсе проекта. Теперь спроси меня: "Над чем будем работать дальше?" и мы продолжим!

**Последнее обновление контекста:** 2026-02-13 (TRADERAGENT v2.0 - Plan Ready, 32 Issues Created)
