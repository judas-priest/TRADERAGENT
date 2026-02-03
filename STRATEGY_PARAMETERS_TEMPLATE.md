# ALMIR Fibonacci Strategy - Parameters Documentation Template

## Test Information

| Field | Value |
|-------|-------|
| **Test ID** | |
| **Date** | |
| **Tester** | |
| **Symbol** | |
| **Timeframe** | |
| **Test Period** | From: _____ To: _____ |
| **Preset Used** | □ Default □ Trending □ Sideways □ Volatile □ Conservative □ Aggressive □ Custom |

---

## Strategy Parameters

### 📊 RSI Settings

| Parameter | Value | Default | Notes |
|-----------|-------|---------|-------|
| RSI Length | | 10 | Recommended: 7-14 |
| RSI Smoothing | | 3 | Recommended: 2-5 |
| Oversold Level | | 30 | Recommended: 20-35 |
| Overbought Level | | 65 | Recommended: 60-75 |
| Mid Level | | 50 | Recommended: 45-55 |

### 📈 MACD Settings

| Parameter | Value | Default | Notes |
|-----------|-------|---------|-------|
| Fast Length | | 2 | Recommended: 2-5 |
| Slow Length | | 30 | Recommended: 20-40 |
| Signal Length | | 10 | Recommended: 5-15 |

### 📉 Stochastic Settings

| Parameter | Value | Default | Notes |
|-----------|-------|---------|-------|
| Length | | 14 | Recommended: 10-20 |
| Smooth | | 3 | Recommended: 2-5 |
| Oversold | | 30 | Recommended: 20-35 |
| Overbought | | 83 | Recommended: 70-85 |

### 📊 Volume Settings

| Parameter | Value | Default | Notes |
|-----------|-------|---------|-------|
| MA Length | | 10 | Recommended: 5-20 |
| Multiplier | | 2.0 | Recommended: 1.5-3.0 |
| Use Directional | | ☑ | Boolean |

### 📈 EMA Settings

| Parameter | Value | Default | Notes |
|-----------|-------|---------|-------|
| EMA 1 Length | | 9 | Recommended: 5-13 |
| EMA 2 Length | | 5 | Recommended: 3-9 |
| EMA 3 Length | | 200 | Recommended: 100-300 |

### 🎯 Confluence Settings

| Parameter | Value | Default | Notes |
|-----------|-------|---------|-------|
| Min Confluence Score | | 6 | Recommended: 4-10 |
| Min Bars Between Signals | | 12 | Recommended: 8-20 |

### ⚖️ Indicator Weights

| Parameter | Value | Default | Notes |
|-----------|-------|---------|-------|
| RSI Weight | | 2 | Range: 0-5 |
| MACD Weight | | 2 | Range: 0-5 |
| Stochastic Weight | | 2 | Range: 0-5 |
| Volume Weight | | 2 | Range: 0-5 |
| Price Action Weight | | 1 | Range: 0-5 |
| EMA Weight | | 1 | Range: 0-5 |
| Divergence Weight | | 2 | Range: 0-5 |

### 🔄 Divergence Settings

| Parameter | Value | Default | Notes |
|-----------|-------|---------|-------|
| Enable Divergence | | ☑ | Boolean |
| Lookback | | 3 | Recommended: 2-10 |
| Min Strength | | 0.6 | Recommended: 0.3-1.0 |

### 🔧 Adaptive Filters

| Parameter | Value | Default | Notes |
|-----------|-------|---------|-------|
| Enable Adaptive Filters | | ☑ | Boolean |
| Trend Filter | | ☑ | Boolean |
| Volatility Filter | | ☑ | Boolean |
| High Vol Threshold | | 0.85 | Recommended: 0.7-1.0 |
| Low Vol Threshold | | 0.6 | Recommended: 0.3-0.7 |

### 📐 Fibonacci Settings

| Parameter | Value | Default | Notes |
|-----------|-------|---------|-------|
| Lookback | | 100 | Recommended: 50-200 |
| Show Levels | | ☑ | Boolean |
| Show Labels | | ☑ | Boolean |

### 💰 Position Management

| Parameter | Value | Default | Notes |
|-----------|-------|---------|-------|
| Use Multiple Entries | | ☑ | Boolean |
| Entry #1 Size (%) | | 1.0 | % of equity |
| Entry #2 Size (%) | | 1.0 | % of equity |
| Entry #3 Size (%) | | 1.0 | % of equity |
| TP1 Close (%) | | 30.0 | % of position |
| TP2 Close (%) | | 30.0 | % of position |
| TP3 Close (%) | | 40.0 | % of position |

---

## Test Results

### Performance Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| **Total Trades** | | |
| **Winning Trades** | | |
| **Losing Trades** | | |
| **Win Rate (%)** | | |
| **Profit Factor** | | |
| **Net Profit** | | |
| **Gross Profit** | | |
| **Gross Loss** | | |
| **Max Drawdown** | | |
| **Max Drawdown (%)** | | |
| **Average Trade** | | |
| **Average Win** | | |
| **Average Loss** | | |
| **Largest Win** | | |
| **Largest Loss** | | |
| **Sharpe Ratio** | | |
| **Sortino Ratio** | | |

### Extended Statistics

| Metric | Value | Notes |
|--------|-------|-------|
| **Green Candle Signals** | | |
| **Red Candle Signals** | | |
| **Entries with RSI Signal** | | |
| **Entries with MACD Cross** | | |
| **Entries with Stoch Signal** | | |
| **Entries with Divergence** | | |

### Market Condition Analysis

| Condition | Trades | Win Rate | Profit | Notes |
|-----------|--------|----------|--------|-------|
| **Trending Market** | | | | |
| **Sideways Market** | | | | |
| **High Volatility** | | | | |
| **Low Volatility** | | | | |

---

## Observations & Notes

### What Worked Well
-
-
-

### What Didn't Work
-
-
-

### Market Conditions
-
-
-

### Recommendations for Next Test
-
-
-

---

## Parameter Optimization Ideas

| Parameter | Current Value | Test Range | Optimal Value | Notes |
|-----------|---------------|------------|---------------|-------|
| | | | | |
| | | | | |
| | | | | |

---

## Screenshots & Charts

Include screenshots of:
- [ ] Full test period equity curve
- [ ] Example winning trade with Fibonacci levels
- [ ] Example losing trade with Fibonacci levels
- [ ] Strategy statistics panel
- [ ] Extended statistics table

---

## Comparison with Previous Tests

| Metric | This Test | Previous Test | Change | Notes |
|--------|-----------|---------------|--------|-------|
| Win Rate | | | | |
| Profit Factor | | | | |
| Net Profit | | | | |
| Max Drawdown | | | | |
| Total Trades | | | | |

---

## Export Data (CSV Format)

```csv
Symbol,Timeframe,Parameters,TotalTrades,WinRate,ProfitFactor,MaxDrawdown,NetProfit,GreenCandleSignals,RedCandleSignals
BTCUSDT,1h,"{preset:Default,...}",45,62.22,1.85,-450.50,1250.75,28,17
```

---

**Template Version:** 1.0
**Last Updated:** 2026-02-03
**Related Issue:** #87
**Strategy Version:** Enhanced
