# Smart Money Concepts (SMC) Strategy

## Issue #123: Hybrid Strategy Algorithm Development

### Overview

Реализация торговой стратегии на основе Smart Money Concepts для автоматической торговли криптовалютами.

### Архитектура

```
SMC Strategy
├── config.py              # Конфигурация и параметры
├── market_structure.py    # Анализ рыночной структуры
├── confluence_zones.py    # Order Blocks + Fair Value Gaps (TODO)
├── entry_signals.py       # Генерация сигналов входа (TODO)
├── position_manager.py    # Управление позициями (TODO)
└── smc_strategy.py        # Главный класс стратегии
```

### Компоненты

#### 1. Market Structure Analysis ✅ (Базовая версия)
- Определение тренда (Bullish/Bearish/Ranging)
- Идентификация Swing High/Low
- Обнаружение Break of Structure (BOS)
- Обнаружение Change of Character (CHoCH)

#### 2. Confluence Zones ⏳ (TODO)
- **Order Blocks (OB)**: Зоны накопления/распределения
- **Fair Value Gaps (FVG)**: Ценовые дисбалансы
- Приоритизация зон по силе

#### 3. Entry Signals ⏳ (TODO)
- Price Action паттерны:
  - Engulfing (поглощение)
  - Pin Bar (пин-бар)
  - Inside Bar
- Подтверждение объемом
- Фильтрация по таймфреймам

#### 4. Position Management ⏳ (TODO)
- Динамические Stop Loss/Take Profit
- Trailing Stop
- Kelly Criterion sizing (опционально)
- Break-even management

### Параметры стратегии

```python
# Timeframes
trend_timeframe = '1d'      # D1 - глобальный тренд
structure_timeframe = '4h'   # H4 - структура рынка
working_timeframe = '1h'     # H1 - зоны слияния
entry_timeframe = '15m'      # M15 - точки входа

# Market Structure
trend_period = 20           # Период определения тренда
swing_length = 5            # Свечи для swing точек

# Risk Management
risk_per_trade = 2%         # Риск на сделку
min_risk_reward = 2.5       # Минимальный R:R
max_position_size = 10000   # Макс. позиция в USD

# Performance Targets
profit_factor > 1.5
max_drawdown < 15%
sharpe_ratio > 1.0
hold_time < 48h
```

### Текущий статус

| Компонент | Статус | Прогресс |
|-----------|--------|----------|
| Config | ✅ Готов | 100% |
| Market Structure | ⏳ Базовая версия | 40% |
| Confluence Zones | ⏳ TODO | 0% |
| Entry Signals | ⏳ TODO | 0% |
| Position Manager | ⏳ TODO | 0% |
| Main Strategy | ⏳ Заглушка | 20% |
| Unit Tests | ⏳ TODO | 0% |
| Integration | ⏳ TODO | 0% |
| Backtesting | ⏳ TODO | 0% |

**Общий прогресс: 15%**

### Следующие шаги

1. ✅ **DONE**: Создать структуру проекта
2. ✅ **DONE**: Реализовать конфигурацию
3. ✅ **DONE**: Базовая версия Market Structure
4. ⏳ **TODO**: Полная реализация Market Structure
5. ⏳ **TODO**: Реализовать Confluence Zones (OB + FVG)
6. ⏳ **TODO**: Реализовать Entry Signals
7. ⏳ **TODO**: Реализовать Position Manager
8. ⏳ **TODO**: Интеграция компонентов
9. ⏳ **TODO**: Unit тесты
10. ⏳ **TODO**: Backtesting

### Использование

```python
from bot.strategies.smc import SMCStrategy
from bot.strategies.smc.config import SMCConfig

# Создать стратегию с default config
strategy = SMCStrategy()

# Или с custom config
config = SMCConfig(
    risk_per_trade=Decimal('0.01'),  # 1% риск
    min_risk_reward=Decimal('3.0')   # R:R = 3.0
)
strategy = SMCStrategy(config)

# Анализ рынка (multi-timeframe)
analysis = strategy.analyze_market(df_d1, df_h4, df_h1, df_m15)

# Генерация сигналов
signals = strategy.generate_signals(df_h1, df_m15)

# Проверка состояния
state = strategy.get_strategy_state()
```

### Ссылки

- Issue: https://github.com/alekseymavai/TRADERAGENT/issues/123
- Документация: См. docstrings в модулях
- Тесты:  (TODO)

### Авторы

TRADERAGENT Team  
Claude Sonnet 4.5  
Version: 1.0.0-dev
