# Fibonacci Tower Code Analysis

## Issue Report
User states: "Код из файла fibonacci_tower.pine вставлен в редактор Pine По инструкции. Визуализация не обнаружена."
Translation: "Code from fibonacci_tower.pine file was inserted into Pine editor following instructions. Visualization not found."

## Identified Problems

### 1. **Critical Bug: Undefined swingHigh/swingLow on first bars**
- Lines 71-78: Fibonacci calculations use `swingHigh` and `swingLow`
- These variables are initialized as `na` (lines 57-58)
- They only get values when `buySignal` is true (lines 63-68)
- **Problem**: Before the first buy signal, `fibRange = na - na`, resulting in `na`
- This means all Fibonacci levels (fib0, fib236, etc.) will be `na` before the first signal
- Drawing lines with `na` coordinates causes them to not appear

### 2. **Line Extension Issue**
- Lines 131-137: Fibonacci lines extend from `bar_index` to `bar_index + 50`
- **Problem**: Using future bar indices (`bar_index + 50`) can cause issues in real-time mode
- TradingView may not render lines that extend too far into the future on real-time data
- Better approach: Use `extend=extend.right` parameter instead of hardcoding future bar

### 3. **Unused Variables**
- Lines 59-60, 67-68: `swingHighBar` and `swingLowBar` are set but never used
- These should ideally track where the swing high/low actually occurred for more accurate visualization

### 4. **Potential Logic Issue: Fibonacci Levels Calculation Timing**
- Lines 63-68: When `buySignal` occurs, swing high/low are calculated
- Lines 71-78: Fibonacci levels are calculated every bar using current swingHigh/swingLow
- Lines 112-147: Lines are only drawn when `buySignal` is true
- **Problem**: After first signal, fibRange and levels keep recalculating every bar, but lines are only redrawn on new signals

## Recommended Fixes

### Fix 1: Check for na values before drawing
Add validation before creating lines to ensure coordinates are valid

### Fix 2: Use line.set_* functions to update existing lines
Instead of deleting and recreating lines, update their positions

### Fix 3: Use extend parameter instead of future bar_index
Change from `bar_index + 50` to using `extend=extend.right`

### Fix 4: Store bar_index when swing points are found
Actually use swingHighBar and swingLowBar to draw lines from the correct starting point

## Root Cause
The most likely reason for "no visualization" is that:
1. The indicator requires a buy signal to appear before any lines are drawn
2. Buy signal conditions are strict (3 bearish candles + RSI oversold + MACD reversal)
3. On many charts/timeframes, this condition might not be met in visible history
4. Even when met, lines might not render properly due to future bar_index issues
