# ALMIR Indicator Analysis

## Issue #79: Создание индикатора ALMIR

### Цель / Goal
Создать индикатор для автоматического определения свечей, на которых следует строить уровни Фибоначчи, на основе анализа состояний индикатора RSIV_Step_[Almir].

Create an indicator to automatically identify candles where Fibonacci levels should be drawn, based on the analysis of RSIV_Step_[Almir] indicator states.

---

## Анализ скриншотов / Screenshot Analysis

### Screenshot 1: RSIV_Step Indicator Behavior
- **Визуальное представление**: Индикатор отображается в нижней панели с зелеными и розовыми зонами
- **Паттерн**: Ступенчатое (step-like) поведение индикатора с четкими переходами между зонами
- **Зоны перекупленности/перепроданности**: Чередование зеленых (bullish) и розовых (bearish) зон

**Visual representation**: Indicator displays in bottom panel with green and pink zones
**Pattern**: Step-like behavior with clear transitions between zones
**Overbought/Oversold zones**: Alternating green (bullish) and pink (bearish) zones

### Screenshot 2 & 3: Fibonacci Level Placement
- **Зеленые свечи (Green candles)**: Отмечены как точки для построения уровней Фибоначчи при восходящем движении
- **Красные свечи (Red candles)**: Отмечены как точки для построения уровней Фибоначчи при нисходящем движении
- **Логика выбора**: Свечи выбираются в моменты экстремумов, когда индикатор RSIV_Step показывает переход из зоны перепроданности/перекупленности

**Green candles**: Marked as points for Fibonacci levels in uptrend
**Red candles**: Marked as points for Fibonacci levels in downtrend
**Selection logic**: Candles selected at extremum points when RSIV_Step shows transition from oversold/overbought zones

---

## Закономерности определения свечей / Candle Selection Patterns

### Для бычьих сигналов (зеленые свечи) / For Bullish Signals (Green Candles):

1. **Переход из перепроданности**: RSI выходит из зоны перепроданности (< 30)
2. **Подтверждение моментумом**: Сильный объемный моментум на развороте
3. **Состояние RSIV_Step**: Переход от розовой зоны к зеленой (от медвежьей к бычьей)
4. **Локальный минимум**: Свеча находится на локальном минимуме цены

**Transition from oversold**: RSI exits oversold zone (< 30)
**Momentum confirmation**: Strong volume momentum on reversal
**RSIV_Step state**: Transition from pink to green zone (bearish to bullish)
**Local minimum**: Candle is at local price minimum

### Для медвежьих сигналов (красные свечи) / For Bearish Signals (Red Candles):

1. **Переход из перекупленности**: RSI выходит из зоны перекупленности (> 70)
2. **Подтверждение моментумом**: Сильный объемный моментум на развороте
3. **Состояние RSIV_Step**: Переход от зеленой зоны к розовой (от бычьей к медвежьей)
4. **Локальный максимум**: Свеча находится на локальном максимуме цены

**Transition from overbought**: RSI exits overbought zone (> 70)
**Momentum confirmation**: Strong volume momentum on reversal
**RSIV_Step state**: Transition from green to pink zone (bullish to bearish)
**Local maximum**: Candle is at local price maximum

---

## Сигналы и причины выбора свечей / Signals and Reasons for Candle Selection

### Индикаторы, участвующие в определении / Indicators Involved:

1. **RSI (Relative Strength Index)**
   - Определяет зоны перекупленности/перепроданности
   - Пересечение уровней 30 и 70
   - Identifies overbought/oversold zones
   - Crossing levels 30 and 70

2. **Объем (Volume)**
   - Подтверждает силу движения
   - Аномально высокий объем на развороте
   - Confirms strength of movement
   - Abnormally high volume on reversal

3. **MACD (Moving Average Convergence Divergence)**
   - Подтверждает изменение тренда
   - Пересечение сигнальной линии
   - Confirms trend change
   - Signal line crossover

4. **Stochastic Oscillator**
   - Дополнительное подтверждение перекупленности/перепроданности
   - Additional confirmation of overbought/oversold

5. **Price Action**
   - Сильные свечи разворота
   - Паттерны разворота (hammer, shooting star)
   - Strong reversal candles
   - Reversal patterns (hammer, shooting star)

6. **Дивергенции (Divergences)**
   - RSI дивергенция усиливает сигнал
   - RSI divergence strengthens signal

### Confluence подход / Confluence Approach:

Свеча выбирается для построения Фибоначчи, когда **одновременно выполняются минимум 4-5 условий** из вышеперечисленных. Это обеспечивает высокую точность определения разворотных точек.

A candle is selected for Fibonacci construction when **at least 4-5 conditions are met simultaneously**. This ensures high accuracy in identifying reversal points.

---

## RSIV_Step_[Almir] Parameters Analysis

Параметры из задачи / Parameters from task:
```
RSIV_Step_[Almir] (1, 10, 3, 50, 30, 10, 10, 0, 2, 0, 2, 30, 10, 20, 3, 14, 24, 5, 0,85, 6, 200, 5, 9, 2, 65, 30, 83, 12, 3, 0,6, 2)
```

### Предполагаемое назначение параметров / Assumed Parameter Purposes:

Основываясь на типичных параметрах индикаторов и анализе:

1-3: **RSI основные параметры** (период 1, длина 10, сглаживание 3)
4-5: **Уровни перекупленности/перепроданности** (50, 30)
6-10: **Объемный анализ** (10, 10, 0, 2, 0)
11-15: **MACD параметры** (2, 30, 10, 20, 3)
16-20: **Stochastic параметры** (14, 24, 5, 0.85, 6)
21-25: **EMA параметры** (200, 5, 9, 2, 65)
26-32: **Адаптивные фильтры** (30, 83, 12, 3, 0.6, 2)

Based on typical indicator parameters and analysis:

1-3: **RSI core parameters** (period 1, length 10, smoothing 3)
4-5: **Overbought/oversold levels** (50, 30)
6-10: **Volume analysis** (10, 10, 0, 2, 0)
11-15: **MACD parameters** (2, 30, 10, 20, 3)
16-20: **Stochastic parameters** (14, 24, 5, 0.85, 6)
21-25: **EMA parameters** (200, 5, 9, 2, 65)
26-32: **Adaptive filters** (30, 83, 12, 3, 0.6, 2)

---

## Предлагаемая реализация / Proposed Implementation

### Алгоритм определения ключевых свечей / Key Candle Detection Algorithm:

```
1. Вычислить все базовые индикаторы (RSI, MACD, Stochastic, Volume, EMA)
   Calculate all base indicators (RSI, MACD, Stochastic, Volume, EMA)

2. Определить состояние рынка (тренд/флэт, волатильность)
   Determine market state (trend/flat, volatility)

3. Для каждой свечи вычислить confluence score:
   For each candle calculate confluence score:
   - RSI transition (вес 2)
   - Volume momentum (вес 2)
   - MACD signal (вес 2)
   - Stochastic signal (вес 1)
   - Price action (вес 1)
   - Divergence bonus (вес 2)

4. Если score >= порога И выполнены фильтры:
   If score >= threshold AND filters passed:
   - Отметить свечу как ключевую
   - Построить уровни Фибоначчи от этой свечи
   - Mark candle as key
   - Draw Fibonacci levels from this candle

5. Применить адаптивные фильтры:
   Apply adaptive filters:
   - Минимальное расстояние между сигналами
   - Фильтр против сильного тренда
   - Фильтр консолидации
   - Minimum distance between signals
   - Filter against strong trend
   - Consolidation filter
```

---

## План создания индикатора / Indicator Creation Plan

### Phase 1: Core Structure
- [ ] Создать базовую структуру Pine Script v6
- [ ] Импортировать параметры RSIV_Step_[Almir]
- [ ] Настроить входные параметры

### Phase 2: Indicator Calculations
- [ ] Реализовать RSI с настройками из параметров
- [ ] Реализовать MACD
- [ ] Реализовать Stochastic
- [ ] Реализовать анализ объема
- [ ] Реализовать EMA системы

### Phase 3: Signal Detection
- [ ] Реализовать логику confluence scoring
- [ ] Добавить определение дивергенций
- [ ] Настроить адаптивные фильтры

### Phase 4: Visualization
- [ ] Отметки ключевых свечей на графике
- [ ] Построение уровней Фибоначчи
- [ ] Таблица состояния индикаторов
- [ ] Цветовая индикация зон (зеленая/розовая)

### Phase 5: Testing & Optimization
- [ ] Тестирование на исторических данных
- [ ] Оптимизация параметров
- [ ] Документация и примеры использования

---

## Ожидаемый результат / Expected Result

Индикатор ALMIR будет:
- Автоматически определять ключевые свечи для построения Фибоначчи
- Отображать зоны как в RSIV_Step (зеленые/розовые)
- Строить уровни Фибоначчи от определенных свечей
- Показывать confluence score для каждого сигнала
- Адаптироваться к различным рыночным условиям

ALMIR indicator will:
- Automatically identify key candles for Fibonacci construction
- Display zones like RSIV_Step (green/pink)
- Draw Fibonacci levels from identified candles
- Show confluence score for each signal
- Adapt to different market conditions
