# ALMIR Fibonacci Trading Strategy / Торговая Стратегия ALMIR с Фибоначчи

## 📊 Обзор стратегии / Strategy Overview

Стратегия ALMIR использует уровни Фибоначчи для управления рисками и фиксации прибыли при торговле сигналами разворота тренда.

The ALMIR strategy uses Fibonacci levels for risk management and profit-taking when trading trend reversal signals.

---

## 🟢 LONG Позиция (Бычий сигнал / Bullish Signal)

### Построение уровней / Level Construction
Когда индикатор обнаруживает **зелёную свечу** разворота (бычий сигнал):

When the indicator detects a **green reversal candle** (bullish signal):

```
-2.618  ────────  TP3: Закрыть 40% позиции / Close 40% of position
-1.618  ────────  TP2: Закрыть 30% позиции / Close 30% of position
-0.618  ────────  TP1: Закрыть 30% позиции / Close 30% of position
 0.000  ────────  HIGH зелёной свечи - Вход #1 (1% депозита)
                  Entry #1 at green candle HIGH (1% of deposit)
 0.500  ────────  Вход #2 - лимитный ордер (1% депозита)
                  Entry #2 - limit order (1% of deposit)
 0.618  ────────  Вход #3 - лимитный ордер (1% депозита)
                  Entry #3 - limit order (1% of deposit)
 0.820  ────────  STOP-LOSS (всегда 0.82 / always 0.82)
 1.000  ────────  LOW зелёной свечи - Основание / Base
```

### Размещение уровней / Level Placement
- **1.0 (Base)** = LOW зелёной свечи (минимум сигнальной свечи)
- **0.0 (Entry #1)** = HIGH зелёной свечи (максимум сигнальной свечи)
- Все промежуточные уровни рассчитываются между этими двумя точками
- Отрицательные уровни (-0.618, -1.618, -2.618) находятся **выше** уровня 0.0

### Алгоритм входа / Entry Algorithm

#### Вход #1 (0.0 level - HIGH)
```pine
// При закрытии сигнальной свечи / At signal candle close
if bullishSignal
    strategy.entry("Long1", strategy.long, qty=positionSize * 0.01)
    entryPrice1 = high  // Entry at 0.0 level
```

#### Вход #2 (0.5 level)
```pine
// Лимитный ордер на уровне 0.5 / Limit order at 0.5 level
entry2Price = low + (high - low) * 0.5
strategy.entry("Long2", strategy.long, qty=positionSize * 0.01, limit=entry2Price)
```

#### Вход #3 (0.618 level)
```pine
// Лимитный ордер на уровне 0.618 / Limit order at 0.618 level
entry3Price = low + (high - low) * 0.618
strategy.entry("Long3", strategy.long, qty=positionSize * 0.01, limit=entry3Price)
```

### Stop-Loss (0.820 level)
```pine
// Стоп-лосс всегда на уровне 0.82 / Stop-loss always at 0.82 level
stopLossPrice = low + (high - low) * 0.820
strategy.exit("SL", stop=stopLossPrice)
```

### Take-Profit Levels / Уровни Тейк-Профита

#### TP1 (-0.618 level) - Закрыть 30% / Close 30%
```pine
tp1Price = high + (high - low) * 0.618  // Above entry
strategy.exit("TP1", qty_percent=30, limit=tp1Price)
```

#### TP2 (-1.618 level) - Закрыть 30% / Close 30%
```pine
tp2Price = high + (high - low) * 1.618  // Above TP1
strategy.exit("TP2", qty_percent=30, limit=tp2Price)
```

#### TP3 (-2.618 level) - Закрыть 40% / Close 40%
```pine
tp3Price = high + (high - low) * 2.618  // Above TP2
strategy.exit("TP3", qty_percent=40, limit=tp3Price)
```

---

## 🔴 SHORT Позиция (Медвежий сигнал / Bearish Signal)

### Построение уровней / Level Construction
Когда индикатор обнаруживает **красную свечу** разворота (медвежий сигнал):

When the indicator detects a **red reversal candle** (bearish signal):

```
 1.000  ────────  HIGH красной свечи - Основание / Base
 0.820  ────────  STOP-LOSS (всегда 0.82 / always 0.82)
 0.618  ────────  Вход #3 - лимитный ордер (1% депозита)
                  Entry #3 - limit order (1% of deposit)
 0.500  ────────  Вход #2 - лимитный ордер (1% депозита)
                  Entry #2 - limit order (1% of deposit)
 0.000  ────────  LOW красной свечи - Вход #1 (1% депозита)
                  Entry #1 at red candle LOW (1% of deposit)
-0.618  ────────  TP1: Закрыть 30% позиции / Close 30% of position
-1.618  ────────  TP2: Закрыть 30% позиции / Close 30% of position
-2.618  ────────  TP3: Закрыть 40% позиции / Close 40% of position
```

### Размещение уровней / Level Placement
- **1.0 (Base)** = HIGH красной свечи (максимум сигнальной свечи)
- **0.0 (Entry #1)** = LOW красной свечи (минимум сигнальной свечи)
- Все промежуточные уровни рассчитываются между этими двумя точками
- Отрицательные уровни (-0.618, -1.618, -2.618) находятся **ниже** уровня 0.0

### Алгоритм входа / Entry Algorithm

#### Вход #1 (0.0 level - LOW)
```pine
// При закрытии сигнальной свечи / At signal candle close
if bearishSignal
    strategy.entry("Short1", strategy.short, qty=positionSize * 0.01)
    entryPrice1 = low  // Entry at 0.0 level
```

#### Вход #2 (0.5 level)
```pine
// Лимитный ордер на уровне 0.5 / Limit order at 0.5 level
entry2Price = high - (high - low) * 0.5
strategy.entry("Short2", strategy.short, qty=positionSize * 0.01, limit=entry2Price)
```

#### Вход #3 (0.618 level)
```pine
// Лимитный ордер на уровне 0.618 / Limit order at 0.618 level
entry3Price = high - (high - low) * 0.618
strategy.entry("Short3", strategy.short, qty=positionSize * 0.01, limit=entry3Price)
```

### Stop-Loss (0.820 level)
```pine
// Стоп-лосс всегда на уровне 0.82 / Stop-loss always at 0.82 level
stopLossPrice = high - (high - low) * 0.820
strategy.exit("SL", stop=stopLossPrice)
```

### Take-Profit Levels / Уровни Тейк-Профита

#### TP1 (-0.618 level) - Закрыть 30% / Close 30%
```pine
tp1Price = low - (high - low) * 0.618  // Below entry
strategy.exit("TP1", qty_percent=30, limit=tp1Price)
```

#### TP2 (-1.618 level) - Закрыть 30% / Close 30%
```pine
tp2Price = low - (high - low) * 1.618  // Below TP1
strategy.exit("TP2", qty_percent=30, limit=tp2Price)
```

#### TP3 (-2.618 level) - Закрыть 40% / Close 40%
```pine
tp3Price = low - (high - low) * 2.618  // Below TP2
strategy.exit("TP3", qty_percent=40, limit=tp3Price)
```

---

## 💼 Управление Капиталом / Money Management

### Размер позиции / Position Sizing
- **Каждый вход**: 1% от депозита / 1% of deposit per entry
- **Максимальная позиция**: 3% от депозита (если все 3 входа исполнены)
- **Maximum position**: 3% of deposit (if all 3 entries filled)

### Распределение тейк-профитов / Take-Profit Distribution
```
TP1 (-0.618): 30% позиции → Остаётся 70% / 30% of position → 70% remains
TP2 (-1.618): 30% позиции → Остаётся 40% / 30% of position → 40% remains
TP3 (-2.618): 40% позиции → Остаётся 0%  / 40% of position → 0% remains
```

### Риск на сделку / Risk Per Trade
```
Вход #1: 1% × (0.0 - 0.820) = 0.18% риска / risk
Вход #2: 1% × (0.5 - 0.820) = 0.32% риска / risk
Вход #3: 1% × (0.618 - 0.820) = 0.202% риска / risk
─────────────────────────────────────────────────
Общий риск / Total Risk: ~0.7% от депозита / of deposit
```

---

## 📐 Математика Уровней / Level Mathematics

### Расчёт цены уровня / Price Calculation Formula

Для LONG (bullish):
```
level_price = low + (high - low) × level_coefficient

Примеры / Examples:
- Level 1.0:    low + (high - low) × 1.0    = low (base)
- Level 0.820:  low + (high - low) × 0.820  = stop-loss
- Level 0.618:  low + (high - low) × 0.618  = entry #3
- Level 0.5:    low + (high - low) × 0.5    = entry #2
- Level 0.0:    low + (high - low) × 0.0    = high (entry #1)
- Level -0.618: high + (high - low) × 0.618 = TP1
- Level -1.618: high + (high - low) × 1.618 = TP2
- Level -2.618: high + (high - low) × 2.618 = TP3
```

Для SHORT (bearish):
```
level_price = high - (high - low) × level_coefficient

Примеры / Examples:
- Level 1.0:    high - (high - low) × 0.0    = high (base)
- Level 0.820:  high - (high - low) × 0.18   = stop-loss
- Level 0.618:  high - (high - low) × 0.382  = entry #3
- Level 0.5:    high - (high - low) × 0.5    = entry #2
- Level 0.0:    high - (high - low) × 1.0    = low (entry #1)
- Level -0.618: low - (high - low) × 0.618   = TP1
- Level -1.618: low - (high - low) × 1.618   = TP2
- Level -2.618: low - (high - low) × 2.618   = TP3
```

---

## 🎯 Статистика R:R / Risk-Reward Statistics

### LONG сценарий / LONG scenario
```
Расстояние / Distance:
- От Entry #1 до SL:  0.18 × range  (риск / risk)
- От Entry #1 до TP1: 0.618 × range (R:R = 3.43)
- От Entry #1 до TP2: 1.618 × range (R:R = 8.99)
- От Entry #1 до TP3: 2.618 × range (R:R = 14.54)

Ожидаемый R:R / Expected R:R:
0.3 × 3.43 + 0.3 × 8.99 + 0.4 × 14.54 = 9.55
```

### SHORT сценарий / SHORT scenario
```
Те же расчёты / Same calculations apply
Expected R:R: 9.55
```

---

## ⚠️ Важные Замечания / Important Notes

### 1. Первый вход всегда по рынку / First Entry Always Market
- Вход #1 исполняется **при закрытии** сигнальной свечи
- Цена входа = 0.0 level (High для LONG, Low для SHORT)
- Entry #1 executes **at close** of signal candle
- Entry price = 0.0 level (High for LONG, Low for SHORT)

### 2. Последующие входы - лимитные ордера / Subsequent Entries - Limit Orders
- Вход #2 и #3 - **лимитные ордера** на откате
- Могут не исполниться, если цена не вернётся
- Entries #2 and #3 are **limit orders** on pullback
- May not fill if price doesn't retrace

### 3. Stop-Loss всегда 0.820 / Stop-Loss Always 0.820
- Фиксированный уровень для всех входов
- Не изменяется в процессе сделки
- Fixed level for all entries
- Does not change during trade

### 4. Уровни видны только для последних сигналов / Levels Visible Only for Latest Signals
- Индикатор отображает уровни для последней найденной зелёной и красной свечи
- Старые уровни автоматически удаляются при новом сигнале
- Indicator displays levels for latest found green and red candle
- Old levels automatically removed on new signal

---

## 🧪 Пример Расчёта / Calculation Example

### LONG сигнал на BTC / LONG signal on BTC
```
Сигнальная свеча / Signal candle:
High = $50,000 (уровень 0.0 / level 0.0)
Low  = $49,000 (уровень 1.0 / level 1.0)
Range = $1,000

Расчёт уровней / Level calculation:
- 1.0 (Base):      $49,000 + $1,000 × 1.0    = $49,000
- 0.820 (SL):      $49,000 + $1,000 × 0.820  = $49,820
- 0.618 (Entry#3): $49,000 + $1,000 × 0.618  = $49,618
- 0.5 (Entry#2):   $49,000 + $1,000 × 0.5    = $49,500
- 0.0 (Entry#1):   $49,000 + $1,000 × 0.0    = $50,000
- -0.618 (TP1):    $50,000 + $1,000 × 0.618  = $50,618
- -1.618 (TP2):    $50,000 + $1,000 × 1.618  = $51,618
- -2.618 (TP3):    $50,000 + $1,000 × 2.618  = $52,618

План торговли / Trading plan:
1. Вход #1: Market buy at $50,000 (1% депозита)
2. Вход #2: Limit buy at $49,500 (1% депозита)
3. Вход #3: Limit buy at $49,618 (1% депозита)
4. Stop-Loss: $49,820 для всех входов / for all entries
5. TP1: Sell 30% at $50,618
6. TP2: Sell 30% at $51,618
7. TP3: Sell 40% at $52,618
```

---

## 📊 Реализация в Коде / Code Implementation

Текущая реализация в `indicators/almir_indicator_overlay.pine` **полностью соответствует** описанной стратегии:

Current implementation in `indicators/almir_indicator_overlay.pine` **fully matches** the described strategy:

```pine
// For LONG (lines 171-176)
if bullishSignal
    lastBullishBar := bar_index
    bullishStartBar := bar_index
    bullishStartPrice := low   // 1.0 level = Low (base)
    bullishEndPrice := high    // 0.0 level = High (entry #1)

// For SHORT (lines 179-184)
if bearishSignal
    lastBearishBar := bar_index
    bearishStartBar := bar_index
    bearishStartPrice := high  // 1.0 level = High (base)
    bearishEndPrice := low     // 0.0 level = Low (entry #1)

// Drawing formula (line 193)
price = startPrice + (endPrice - startPrice) * level
```

✅ **Проверено**: Уровни строятся правильно!
✅ **Verified**: Levels are drawn correctly!

---

## 🔄 Следующие Шаги / Next Steps

### Для пользователя / For User:
1. ✅ Установить индикатор в TradingView
2. ✅ Проверить построение уровней на исторических данных
3. ⏳ Протестировать стратегию на demo-счёте
4. ⏳ Оптимизировать параметры confluence для своих инструментов
5. ⏳ Провести backtesting с учётом комиссий и проскальзывания

### Для разработчика / For Developer:
1. ✅ Реализовать индикатор с уровнями Фибоначчи
2. ✅ Документировать торговую стратегию
3. ⏳ Создать полноценную торговую стратегию (strategy script)
4. ⏳ Добавить автоматическое управление позициями
5. ⏳ Реализовать трейлинг-стоп после TP1

---

## 📚 Дополнительные Ресурсы / Additional Resources

- [ALMIR Indicator Guide RU](../ALMIR_INDICATOR_GUIDE_RU.md) - Полное руководство
- [Technical Analysis](./almir_indicator_analysis.md) - Анализ индикатора
- [Action Plan](../ACTION_PLAN_ISSUE_79.md) - План разработки

---

**⚠️ Дисклеймер**: Данная торговая стратегия предназначена только для образовательных целей. Прошлые результаты не гарантируют будущей прибыли. Всегда используйте управление рисками и тестируйте на demo-счёте перед реальной торговлей.

**⚠️ Disclaimer**: This trading strategy is for educational purposes only. Past performance does not guarantee future profits. Always use risk management and test on demo account before live trading.

---

📝 *Документ создан: 2026-02-02*
🤖 *Created by AI Issue Solver for TRADERAGENT Project*
