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

---

## 📊 Текущий статус проекта

### ✅ Завершено (v1.1.0)

**1. SMC Strategy - ПОЛНОСТЬЮ РЕАЛИЗОВАНА (100%)**

Статус: ✅ Production Ready (Released 2026-02-12, v1.0.0)

**2. Trend-Follower Strategy - ПОЛНОСТЬЮ РЕАЛИЗОВАНА (100%)**

Статус: ✅ Production Ready (Released 2026-02-13, v1.1.0)

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

**4. Git Operations - ЗАВЕРШЕНЫ**
- ✅ PR #125 смержен в main - SMC Strategy (commit: `8b4945c`)
- ✅ PR #131 смержен в main - Trend-Follower Strategy (commit: `b8bd50e`)
- ✅ Issue #124 закрыт (Trend-Follower)
- ✅ Все issues SMC закрыты (#123, #126, #127, #128, #129, #130)
- ✅ Release v1.0.0: https://github.com/alekseymavai/TRADERAGENT/releases/tag/v1.0.0
- ✅ README.md обновлен с разделами SMC + Trend-Follower

**3. Документация - ЗАВЕРШЕНА**
- ✅ Release notes v1.0.0 с полным описанием
- ✅ README.md: добавлен раздел "🎓 SMC Strategy (Smart Money Concepts)" (+176 строк)
- ✅ Inline документация во всех модулях SMC
- ✅ `bot/strategies/smc/README_old.md` - детальное руководство

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
- `8b4945c` - Merge PR #125 (SMC Strategy complete implementation)
- `0cd6ef4` - README.md update with SMC section
- `956c8ac` - Position Manager implementation
- `80cf88b` - Final SMC integration

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

## 🔄 Что дальше (Next Steps)

### Приоритет 1: Integration Testing (ТЕКУЩАЯ ЗАДАЧА)
- [x] Обновить SESSION_CONTEXT.md с информацией о Trend-Follower
- [ ] **Создать integration tests для Trend-Follower с orchestrator**
- [ ] Интегрировать SMCGridAdvisor в main bot orchestrator
- [ ] Протестировать decision-making flow для запуска Grid ботов
- [ ] Проверить multi-timeframe data pipeline

### Приоритет 2: Backtesting & Validation
**SMC Strategy:**
- [ ] Запустить полный backtest на 6+ месяцев исторических данных BTC/USDT
- [ ] Проверить достижение target метрик (Sharpe >1.0, Win Rate >45%)

**Trend-Follower Strategy:**
- [ ] Запустить backtest на 6+ месяцев данных
- [ ] Валидация против требований issue #124:
  - [ ] Sharpe Ratio > 1.0
  - [ ] Max Drawdown < 20%
  - [ ] Profit Factor > 1.5
  - [ ] Win Rate > 45%
  - [ ] Profit/Loss Ratio > 1.5
- [ ] Сгенерировать отчет с графиками

### Приоритет 3: Paper Trading
- [ ] Настроить paper trading environment
- [ ] Запустить обе стратегии в testnet режиме
- [ ] Мониторинг сигналов (минимум 2 недели)
- [ ] Сравнительный анализ SMC vs Trend-Follower

### Приоритет 4: Production Deployment
- [ ] После успешного paper trading - перенести на live
- [ ] Настроить monitoring (Prometheus + Grafana)
- [ ] Настроить alerts (Telegram)
- [ ] Начать с малых сумм
- [ ] A/B тестирование обеих стратегий

---

## 🛠️ Рабочее окружение

### Репозиторий на диске
- Проект обычно клонируется в `/home/hive/btc/` или `/tmp/`
- Для Git операций можно клонировать временно в `/tmp/traderagent_*`

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
```

### Запуск тестов
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

---

## 📌 Quick Reference

**Основные файлы:**
- `/home/hive/btc/CLAUDE.md` - правила работы с проектом
- `/home/hive/btc/bot/strategies/smc/smc_strategy.py` - главный класс SMC
- `/home/hive/btc/README.md` - главная документация проекта

**GitHub URLs:**
- Repo: https://github.com/alekseymavai/TRADERAGENT
- Release v1.0.0: https://github.com/alekseymavai/TRADERAGENT/releases/tag/v1.0.0
- Issues: https://github.com/alekseymavai/TRADERAGENT/issues
- PR #125: https://github.com/alekseymavai/TRADERAGENT/pull/125

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
→ Нужно создать скрипт для backtesting SMC Strategy на исторических данных

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

**Последнее обновление контекста:** 2026-02-13 (после Release v1.1.0 - Trend-Follower Strategy merge)
