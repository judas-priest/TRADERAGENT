# Sub-Issues for Issue #85: ALMIR Backtesting System

This document contains templates for creating sub-issues to break down the implementation of the ALMIR Fibonacci Strategy Backtesting System.

---

## Issue Template 1: Data Collection Module

**Title:** Implement Data Collection Module for Historical Crypto Data

**Labels:** enhancement, data-pipeline

**Body:**
```markdown
## 📋 Description

Create a Python module to collect and store historical price data from Binance and ByBit for the top 100 cryptocurrency pairs across all timeframes.

## 🎯 Objectives

- Download historical OHLCV data from Binance and ByBit
- Support all timeframes: 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w
- Store data efficiently in a database
- Implement data validation and error handling
- Create update mechanism for incremental data fetching

## 📊 Requirements

### Functional Requirements:
1. Connect to Binance and ByBit APIs using CCXT
2. Fetch top 100 crypto pairs by volume/market cap
3. Download historical data with configurable date range
4. Support multiple timeframes simultaneously
5. Validate data completeness and accuracy
6. Handle API rate limits gracefully
7. Store data in SQLite database
8. Provide progress tracking and logging

### Technical Requirements:
- Python 3.10+
- CCXT library for exchange connectivity
- Pandas for data manipulation
- SQLite for data storage
- Retry logic for API failures
- Configuration file for settings

## 📁 Deliverables

1. **data_collector.py** - Main data collection script
   - Exchange API initialization
   - Symbol fetching logic
   - Historical data download
   - Data validation

2. **database.py** - Database management
   - Schema creation
   - Data insertion/update
   - Query functions
   - Data integrity checks

3. **config.yaml** - Configuration file
   - Exchange settings
   - API credentials (optional)
   - Date ranges
   - Timeframes list
   - Top N pairs to fetch

4. **requirements.txt** - Python dependencies

5. **README_DATA_COLLECTION.md** - Usage documentation

## 🧪 Testing

- [ ] Test connection to Binance API
- [ ] Test connection to ByBit API
- [ ] Verify data download for single pair/timeframe
- [ ] Test multi-pair download
- [ ] Test multi-timeframe download
- [ ] Validate data integrity
- [ ] Test error handling (network errors, API limits)
- [ ] Test incremental updates

## 📊 Success Criteria

- ✅ Successfully download data for 100+ pairs
- ✅ Support all 8 timeframes
- ✅ Data validation passes (no gaps, correct timestamps)
- ✅ Error handling works (retry logic, logging)
- ✅ Database schema is efficient
- ✅ Documentation is complete

## 🔗 Related

- Parent Issue: #85
- Depends on: None
- Blocks: #87 (Strategy Implementation)

## 💡 Implementation Notes

### Database Schema:
```sql
CREATE TABLE ohlcv (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    UNIQUE(exchange, symbol, timeframe, timestamp)
);

CREATE INDEX idx_symbol_timeframe ON ohlcv(symbol, timeframe, timestamp);
```

### Example Usage:
```python
from data_collector import DataCollector

# Initialize
collector = DataCollector(exchange='binance')

# Fetch top 100 pairs
symbols = collector.get_top_symbols(n=100)

# Download data
collector.download_historical_data(
    symbols=symbols,
    timeframes=['1h', '4h', '1d'],
    start_date='2020-01-01',
    end_date='2024-12-31'
)
```

## ⏱️ Estimated Time

30-40 hours
```

---

## Issue Template 2: Strategy Implementation in Python

**Title:** Port ALMIR Fibonacci Strategy from Pine Script to Python

**Labels:** enhancement, strategy, core-logic

**Body:**
```markdown
## 📋 Description

Port the ALMIR Fibonacci Strategy from Pine Script to Python, implementing all indicators, confluence logic, and Fibonacci calculations.

## 🎯 Objectives

- Implement all 7 technical indicators
- Port confluence scoring system
- Implement Fibonacci level calculations
- Create signal generation logic
- Add adaptive filters (volatility, trend)
- Validate against TradingView implementation

## 📊 Requirements

### Indicators to Implement:
1. **RSI** (Relative Strength Index)
   - Configurable period and smoothing
   - Oversold/overbought levels
   - Signal detection (crossovers)

2. **MACD** (Moving Average Convergence Divergence)
   - Fast/slow/signal periods
   - Histogram calculation
   - Bullish/bearish crossovers

3. **Stochastic Oscillator**
   - %K and %D calculation
   - Oversold/overbought detection
   - Signal crossovers

4. **Volume Analysis**
   - Volume moving average
   - Volume ratio calculation
   - Directional volume (buying/selling pressure)

5. **EMA System**
   - Multiple EMA periods (5, 9, 200)
   - Crossover detection
   - Trend confirmation

6. **Divergence Detection**
   - RSI divergences (bullish/bearish)
   - Pivot point detection
   - Divergence strength calculation

7. **Price Action Analysis**
   - Candle pattern recognition
   - Strong candle detection
   - Body-to-range ratio

### Additional Components:
- **ATR** (Average True Range) for volatility
- **ADX** (Average Directional Index) for trend strength
- **Confluence Scoring System**
- **Adaptive Filters**
- **Fibonacci Level Calculator**

## 📁 Deliverables

1. **indicators.py** - Technical indicator implementations
   ```python
   class Indicators:
       @staticmethod
       def rsi(data, period=10, smooth=3):
           # RSI calculation

       @staticmethod
       def macd(data, fast=2, slow=30, signal=10):
           # MACD calculation

       # ... other indicators
   ```

2. **strategy.py** - ALMIR strategy logic
   ```python
   class ALMIRStrategy:
       def __init__(self, params):
           # Initialize with parameters

       def calculate_confluence(self, data):
           # Confluence scoring

       def detect_signals(self, data):
           # Signal generation

       def calculate_fibonacci_levels(self, data, signal):
           # Fibonacci calculations
   ```

3. **tests/test_indicators.py** - Unit tests
4. **tests/test_strategy.py** - Strategy validation tests
5. **validation_report.md** - Comparison with TradingView

## 🧪 Testing & Validation

### Unit Tests:
- [ ] Test each indicator independently
- [ ] Verify RSI calculations
- [ ] Verify MACD calculations
- [ ] Verify Stochastic calculations
- [ ] Test confluence scoring
- [ ] Test signal generation
- [ ] Test Fibonacci calculations

### Integration Tests:
- [ ] Test full strategy pipeline
- [ ] Compare with TradingView results
- [ ] Validate on known test cases
- [ ] Check edge cases (missing data, extreme values)

### Validation Against TradingView:
- [ ] Select 5 test pairs with known signals
- [ ] Compare indicator values (RSI, MACD, etc.)
- [ ] Compare confluence scores
- [ ] Compare signal timing
- [ ] Compare Fibonacci levels
- [ ] Document any discrepancies

## 📊 Success Criteria

- ✅ All 7 indicators implemented and tested
- ✅ Confluence system matches TradingView
- ✅ Signal generation matches TradingView (>95% accuracy)
- ✅ Fibonacci levels match exactly
- ✅ All unit tests pass
- ✅ Validation report shows <5% deviation

## 🔗 Related

- Parent Issue: #85
- Depends on: #86 (Data Collection Module)
- Blocks: #88 (Backtesting Engine)

## 💡 Implementation Notes

### Confluence Scoring Logic:
```python
def calculate_confluence(self, bar):
    score = 0
    reasons = []

    # RSI (weight: 2)
    if self.check_rsi_bullish(bar):
        score += self.params['rsi_weight']
        reasons.append('RSI bullish')

    # MACD (weight: 2)
    if self.check_macd_bullish(bar):
        score += self.params['macd_weight']
        reasons.append('MACD bullish')

    # ... other indicators

    return score, reasons
```

### Fibonacci Calculation:
```python
def calculate_fibonacci_levels(self, base, top, direction='long'):
    levels = {}
    range_val = top - base

    if direction == 'long':
        levels['1.0'] = base
        levels['0.820'] = base + range_val * 0.820
        levels['0.618'] = base + range_val * 0.618
        levels['0.5'] = base + range_val * 0.5
        levels['0.0'] = top
        levels['-0.618'] = top + range_val * 0.618
        levels['-1.618'] = top + range_val * 1.618
        levels['-2.618'] = top + range_val * 2.618

    return levels
```

## ⏱️ Estimated Time

40-50 hours
```

---

## Issue Template 3: Backtesting Engine Integration

**Title:** Integrate ALMIR Strategy with Backtesting Framework

**Labels:** enhancement, backtesting

**Body:**
```markdown
## 📋 Description

Integrate the ALMIR strategy with a Python backtesting framework (Backtrader or VectorBT) to enable systematic testing across multiple pairs and timeframes.

## 🎯 Objectives

- Choose and integrate backtesting framework
- Implement ALMIR strategy as backtest module
- Add position management (multiple entries, partial exits)
- Implement commission and slippage modeling
- Create batch testing capability
- Generate performance metrics

## 📊 Requirements

### Framework Selection:
**Option 1: Backtrader** (Recommended)
- Mature, well-documented
- Event-driven architecture
- Built-in broker simulation
- Extensive indicator library

**Option 2: VectorBT**
- Fast vectorized computations
- Good for parameter optimization
- Modern API
- Built for quantitative analysis

### Features to Implement:
1. **Strategy Wrapper**
   - Adapt ALMIR logic to framework API
   - Handle data feeds
   - Manage orders and positions

2. **Position Management**
   - Entry #1: Market order at signal
   - Entry #2: Limit order at 0.5 Fib level
   - Entry #3: Limit order at 0.618 Fib level
   - Stop Loss at 0.820 Fib level
   - Partial exits at TP levels

3. **Order Execution**
   - Market orders
   - Limit orders
   - Stop-loss orders
   - Partial position closing

4. **Risk Management**
   - Position sizing (1% per entry)
   - Maximum position (3% total)
   - Stop-loss enforcement

5. **Performance Tracking**
   - Equity curve
   - Drawdown analysis
   - Trade statistics
   - Win rate, profit factor

## 📁 Deliverables

1. **backtest_engine.py** - Backtesting wrapper
   ```python
   class ALMIRBacktester:
       def __init__(self, strategy_params, backtest_params):
           # Initialize backtest engine

       def run_single(self, symbol, timeframe, data):
           # Run backtest on single pair

       def run_batch(self, symbols, timeframes):
           # Run backtest on multiple pairs

       def get_results(self):
           # Return performance metrics
   ```

2. **position_manager.py** - Position management logic
3. **performance_metrics.py** - Metrics calculation
4. **tests/test_backtest.py** - Backtesting tests
5. **example_backtest.py** - Usage example

## 🧪 Testing

- [ ] Test single-pair backtest
- [ ] Test multi-pair backtest
- [ ] Verify order execution (market, limit, stop)
- [ ] Test partial position closing
- [ ] Validate position sizing
- [ ] Test commission/slippage modeling
- [ ] Compare with manual calculations

## 📊 Success Criteria

- ✅ Backtest runs successfully on test data
- ✅ Position management works correctly
- ✅ All order types execute properly
- ✅ Performance metrics are accurate
- ✅ Can test 100+ pairs efficiently
- ✅ Results are reproducible

## 🔗 Related

- Parent Issue: #85
- Depends on: #87 (Strategy Implementation)
- Blocks: #89 (Optimization Framework)

## 💡 Implementation Notes

### Backtrader Strategy Example:
```python
import backtrader as bt

class ALMIRStrategy(bt.Strategy):
    params = (
        ('rsi_length', 10),
        ('min_confluence', 6),
        # ... other parameters
    )

    def __init__(self):
        self.almir = ALMIR(self.data, self.params)

    def next(self):
        # Check for signals
        signal = self.almir.detect_signal()

        if signal == 'bullish' and not self.position:
            # Calculate Fibonacci levels
            fib_levels = self.almir.calculate_fib_levels()

            # Entry #1: Market order
            self.buy(size=self.calculate_position_size(0.01))

            # Entry #2: Limit order
            self.buy_limit(
                price=fib_levels['0.5'],
                size=self.calculate_position_size(0.01)
            )
```

### Performance Metrics to Track:
- Total return
- Sharpe ratio
- Maximum drawdown
- Win rate
- Profit factor
- Average win/loss
- Number of trades
- Average trade duration

## ⏱️ Estimated Time

30-40 hours
```

---

## Issue Template 4: Optimization Framework

**Title:** Build Parameter Optimization Framework

**Labels:** enhancement, optimization

**Body:**
```markdown
## 📋 Description

Create a framework for optimizing ALMIR strategy parameters across different market conditions, pairs, and timeframes.

## 🎯 Objectives

- Implement parameter grid search
- Add walk-forward analysis
- Create market segmentation logic
- Analyze parameter sensitivity
- Generate optimization reports
- Identify optimal settings per segment

## 📊 Requirements

### Optimization Methods:
1. **Grid Search**
   - Test all parameter combinations
   - Configurable parameter ranges
   - Parallel processing support

2. **Walk-Forward Analysis**
   - Rolling window optimization
   - Out-of-sample validation
   - Prevent overfitting

3. **Parameter Sensitivity Analysis**
   - Identify critical parameters
   - Analyze parameter stability
   - Heatmap visualization

4. **Market Segmentation**
   - Group by crypto sector
   - Group by market cap
   - Group by volatility regime
   - Find optimal parameters per segment

### Parameters to Optimize:
```python
{
    'rsi_length': [7, 10, 14, 21],
    'rsi_oversold': [25, 30, 35],
    'rsi_overbought': [60, 65, 70],
    'macd_fast': [2, 5, 12],
    'macd_slow': [26, 30, 35],
    'macd_signal': [9, 10, 12],
    'stoch_length': [10, 14, 21],
    'min_confluence_score': [4, 5, 6, 7, 8],
    'min_bars_between_signals': [8, 10, 12, 15],
    # ... and others
}
```

## 📁 Deliverables

1. **optimizer.py** - Optimization framework
   ```python
   class ParameterOptimizer:
       def __init__(self, backtester, data):
           # Initialize

       def grid_search(self, param_grid):
           # Run grid search

       def walk_forward(self, param_grid, windows):
           # Walk-forward analysis

       def sensitivity_analysis(self, base_params):
           # Analyze parameter sensitivity
   ```

2. **market_segmentation.py** - Market segmentation logic
3. **optimization_results.py** - Results aggregation and analysis
4. **visualizations.py** - Charts and heatmaps
5. **OPTIMIZATION_REPORT_TEMPLATE.md** - Report template

## 🧪 Testing

- [ ] Test grid search on small parameter space
- [ ] Test walk-forward analysis
- [ ] Verify parallel processing
- [ ] Test sensitivity analysis
- [ ] Validate market segmentation
- [ ] Test report generation

## 📊 Success Criteria

- ✅ Grid search works on full parameter space
- ✅ Walk-forward analysis prevents overfitting
- ✅ Market segmentation identifies meaningful groups
- ✅ Optimal parameters found for each segment
- ✅ Sensitivity analysis highlights key parameters
- ✅ Results are reproducible

## 🔗 Related

- Parent Issue: #85
- Depends on: #88 (Backtesting Engine)
- Blocks: #90 (Analysis & Reporting)

## 💡 Implementation Notes

### Grid Search Example:
```python
param_grid = {
    'rsi_length': [7, 10, 14],
    'min_confluence_score': [5, 6, 7],
}

results = optimizer.grid_search(
    param_grid=param_grid,
    symbols=['BTCUSDT', 'ETHUSDT'],
    timeframes=['1h', '4h'],
    metric='sharpe_ratio'
)

# Results format:
# [
#   {'params': {...}, 'sharpe': 1.5, 'return': 0.25, ...},
#   {'params': {...}, 'sharpe': 1.2, 'return': 0.20, ...},
# ]
```

### Market Segmentation:
```python
segments = {
    'large_cap': ['BTCUSDT', 'ETHUSDT', 'BNBUSDT'],
    'defi': ['UNIUSDT', 'AAVEUSDT', 'LINKUSDT'],
    'layer1': ['SOLUSDT', 'ADAUSDT', 'AVAXUSDT'],
    'layer2': ['MATICUSDT', 'ARBUSDT', 'OPUSDT'],
}

# Find optimal params for each segment
for segment, symbols in segments.items():
    optimal = optimizer.find_best_params(symbols)
    print(f"{segment}: {optimal}")
```

## ⏱️ Estimated Time

20-30 hours
```

---

## Issue Template 5: Analysis & Reporting System

**Title:** Create Comprehensive Analysis and Reporting System

**Labels:** enhancement, reporting, analytics

**Body:**
```markdown
## 📋 Description

Build a system to analyze backtesting results, generate statistical reports, and create visualizations for strategy performance across all tested pairs and timeframes.

## 🎯 Objectives

- Calculate advanced statistical metrics
- Generate comparison reports
- Create performance visualizations
- Analyze candle profitability
- Identify indicator correlations
- Produce executive summary

## 📊 Requirements

### Statistical Analysis:
1. **Performance Metrics**
   - Return (total, annualized, per timeframe)
   - Risk metrics (Sharpe, Sortino, Calmar ratios)
   - Drawdown analysis (max, average, duration)
   - Win rate and profit factor
   - Expectancy and Kelly criterion

2. **Trade Analysis**
   - Distribution of returns
   - Win/loss streaks
   - Trade duration distribution
   - Entry/exit timing analysis
   - Slippage impact

3. **Candle Profitability**
   - Which candles are most profitable
   - Green vs red candle performance
   - Confluence score vs profitability
   - Indicator state correlation

4. **Market Condition Analysis**
   - Performance by volatility regime
   - Performance by trend strength
   - Performance by market cap segment
   - Performance by crypto sector

### Visualizations:
- Equity curves
- Drawdown charts
- Return distributions (histograms)
- Heatmaps (parameters vs performance)
- Correlation matrices
- Scatter plots (risk vs return)
- Time-series analysis

## 📁 Deliverables

1. **analytics.py** - Statistical analysis functions
   ```python
   class PerformanceAnalytics:
       @staticmethod
       def calculate_sharpe_ratio(returns, risk_free_rate=0):
           # Sharpe calculation

       @staticmethod
       def calculate_max_drawdown(equity_curve):
           # Max drawdown

       # ... other metrics
   ```

2. **report_generator.py** - Report generation
   ```python
   class ReportGenerator:
       def generate_summary(self, results):
           # Executive summary

       def generate_detailed_report(self, results):
           # Detailed analysis

       def export_to_html(self, report):
           # HTML export
   ```

3. **visualizations.py** - Chart generation
4. **templates/report_template.html** - HTML report template
5. **example_reports/** - Sample generated reports

## 🧪 Testing

- [ ] Test metrics calculation accuracy
- [ ] Verify visualization rendering
- [ ] Test HTML report generation
- [ ] Validate statistical significance tests
- [ ] Test with edge cases (no trades, all losing trades)

## 📊 Report Structure

### Executive Summary:
- Overall performance metrics
- Best performing pairs/timeframes
- Optimal parameter sets
- Key findings and recommendations

### Detailed Analysis:
1. **Overall Performance**
   - Aggregate statistics
   - Equity curve
   - Drawdown analysis

2. **Per-Timeframe Analysis**
   - Performance by timeframe
   - Comparison charts
   - Statistical significance

3. **Per-Pair Analysis**
   - Top/bottom performers
   - Pair-specific insights

4. **Candle Profitability Analysis**
   - Most profitable candle characteristics
   - Indicator state correlation
   - Confluence score effectiveness

5. **Market Segmentation Results**
   - Performance by segment
   - Optimal parameters per segment
   - Sector recommendations

6. **Parameter Sensitivity**
   - Critical parameters identified
   - Stability analysis
   - Robustness assessment

## 📊 Success Criteria

- ✅ All statistical metrics calculated correctly
- ✅ Visualizations are clear and informative
- ✅ Reports are comprehensive and actionable
- ✅ HTML export works properly
- ✅ Findings are statistically validated

## 🔗 Related

- Parent Issue: #85
- Depends on: #89 (Optimization Framework)
- Blocks: #91 (Dashboard Development)

## 💡 Sample Report Sections

### Example: Candle Profitability Analysis
```
Most Profitable Candle Characteristics:
- Confluence Score: 7-8 (avg return: +2.5%)
- RSI State: Oversold + divergence present
- Volume: 2.5x+ average
- MACD: Bullish crossover in negative territory
- Market State: Sideways to weak trend

Least Profitable Candle Characteristics:
- Confluence Score: 4-5 (avg return: -0.5%)
- During strong trends (ADX > 40)
- High volatility without directional bias
```

### Example: Segment Recommendations
```
Large Cap Pairs (BTC, ETH, BNB):
- Best Timeframe: 4h, 1d
- Optimal Confluence: 6
- RSI Length: 14
- Expected Sharpe: 1.8
- Win Rate: 58%

DeFi Tokens (UNI, AAVE, LINK):
- Best Timeframe: 1h, 4h
- Optimal Confluence: 7
- RSI Length: 10
- Expected Sharpe: 1.5
- Win Rate: 55%
```

## ⏱️ Estimated Time

20-30 hours
```

---

## Issue Template 6: Dashboard Development

**Title:** Build Interactive Dashboard for Results Exploration

**Labels:** enhancement, ui, dashboard

**Body:**
```markdown
## 📋 Description

Create an interactive web dashboard using Streamlit to explore backtesting results, compare parameters, and visualize strategy performance.

## 🎯 Objectives

- Build user-friendly web interface
- Enable interactive result exploration
- Provide parameter comparison tools
- Display real-time visualizations
- Support data export functionality

## 📊 Requirements

### Dashboard Pages:

1. **Overview Page**
   - Summary statistics
   - Top performers
   - Key metrics cards
   - Quick filters

2. **Detailed Results Page**
   - Filterable results table
   - Sort by any column
   - Export to CSV/Excel
   - Drill-down capability

3. **Comparison Page**
   - Compare multiple parameter sets
   - Side-by-side equity curves
   - Metric comparison charts
   - Statistical significance tests

4. **Visualization Page**
   - Interactive charts (Plotly)
   - Heatmaps
   - Correlation matrices
   - Custom chart builder

5. **Market Segmentation Page**
   - Segment performance
   - Optimal parameters per segment
   - Sector analysis

### Features:
- **Filters**: Symbol, timeframe, date range, parameter values
- **Sorting**: Any column, ascending/descending
- **Export**: CSV, Excel, JSON, PDF report
- **Search**: Full-text search across results
- **Bookmarks**: Save favorite parameter sets
- **Notes**: Add annotations to results

## 📁 Deliverables

1. **dashboard.py** - Main Streamlit app
   ```python
   import streamlit as st

   def main():
       st.set_page_config(page_title="ALMIR Backtest Dashboard")

       page = st.sidebar.selectbox("Choose a page", [
           "Overview",
           "Detailed Results",
           "Comparison",
           "Visualizations",
           "Market Segmentation"
       ])

       if page == "Overview":
           show_overview()
       # ... other pages
   ```

2. **pages/overview.py** - Overview page
3. **pages/results.py** - Results exploration
4. **pages/comparison.py** - Parameter comparison
5. **pages/visualizations.py** - Charts and graphs
6. **pages/segmentation.py** - Market segments
7. **utils/dashboard_helpers.py** - Helper functions
8. **README_DASHBOARD.md** - Usage guide

## 🧪 Testing

- [ ] Test all pages load correctly
- [ ] Test filters and sorting
- [ ] Test data export
- [ ] Test chart interactivity
- [ ] Test with large datasets
- [ ] Test on different browsers

## 📊 Success Criteria

- ✅ Dashboard runs without errors
- ✅ All pages are functional
- ✅ Filters work correctly
- ✅ Export functionality works
- ✅ Charts are interactive and informative
- ✅ Performance is acceptable (<2s page load)
- ✅ User guide is complete

## 🔗 Related

- Parent Issue: #85
- Depends on: #90 (Analysis & Reporting)
- Blocks: None (final deliverable)

## 💡 Implementation Notes

### Streamlit Layout Example:
```python
# Overview Page
def show_overview():
    st.title("🚀 ALMIR Backtest Dashboard")

    # Load data
    results = load_results()

    # Metrics cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Tests", len(results))
    with col2:
        st.metric("Avg Return", f"{results['return'].mean():.2%}")
    with col3:
        st.metric("Avg Sharpe", f"{results['sharpe'].mean():.2f}")
    with col4:
        st.metric("Win Rate", f"{results['win_rate'].mean():.2%}")

    # Best performers
    st.subheader("Top 10 Performers")
    top_10 = results.nlargest(10, 'sharpe')
    st.dataframe(top_10[['symbol', 'timeframe', 'sharpe', 'return', 'win_rate']])

    # Equity curve
    st.subheader("Cumulative Returns")
    fig = create_equity_curve(results)
    st.plotly_chart(fig)
```

### Feature Highlights:
- Real-time filtering without page reload
- Interactive charts (zoom, pan, hover)
- Responsive design (works on mobile)
- Persistent state (remember filters)
- Dark/light theme toggle

## ⏱️ Estimated Time

10-20 hours
```

---

## Issue Template 7: Documentation & User Guide

**Title:** Create Comprehensive Documentation and User Guide

**Labels:** documentation

**Body:**
```markdown
## 📋 Description

Write complete documentation for the ALMIR backtesting system, including installation guide, usage examples, API reference, and troubleshooting.

## 🎯 Objectives

- Installation instructions
- Usage guide with examples
- API documentation
- Configuration reference
- Troubleshooting guide
- FAQ section

## 📁 Deliverables

1. **README.md** - Main project README
   - Project overview
   - Quick start guide
   - Links to detailed docs

2. **INSTALLATION.md** - Installation guide
   - Prerequisites
   - Step-by-step installation
   - Virtual environment setup
   - Troubleshooting common issues

3. **USER_GUIDE.md** - Comprehensive user guide
   - Data collection tutorial
   - Running backtests
   - Parameter optimization
   - Result analysis
   - Dashboard usage

4. **API_REFERENCE.md** - API documentation
   - Class and function reference
   - Parameter descriptions
   - Return values
   - Usage examples

5. **CONFIGURATION.md** - Configuration guide
   - All configuration options
   - Default values
   - Best practices

6. **FAQ.md** - Frequently asked questions

7. **CONTRIBUTING.md** - Contribution guidelines

## 📊 Success Criteria

- ✅ All major components documented
- ✅ Installation guide is clear and complete
- ✅ Usage examples work as shown
- ✅ API reference is comprehensive
- ✅ Troubleshooting covers common issues

## 🔗 Related

- Parent Issue: #85
- Depends on: All implementation issues
- Blocks: None

## ⏱️ Estimated Time

10-20 hours
```

---

## Summary of Sub-Issues

| Issue # | Title | Priority | Est. Hours | Dependencies |
|---------|-------|----------|-----------|--------------|
| #86 | Data Collection Module | High | 30-40 | None |
| #87 | Strategy Implementation | High | 40-50 | #86 |
| #88 | Backtesting Engine | High | 30-40 | #87 |
| #89 | Optimization Framework | Medium | 20-30 | #88 |
| #90 | Analysis & Reporting | Medium | 20-30 | #89 |
| #91 | Dashboard Development | Low | 10-20 | #90 |
| #92 | Documentation | Low | 10-20 | All |

**Total Estimated Time:** 160-230 hours

---

## Implementation Order

1. **Phase 1: Foundation** (Weeks 1-2)
   - Issue #86: Data Collection Module

2. **Phase 2: Core Logic** (Weeks 2-3)
   - Issue #87: Strategy Implementation

3. **Phase 3: Testing** (Weeks 3-4)
   - Issue #88: Backtesting Engine

4. **Phase 4: Optimization** (Weeks 4-5)
   - Issue #89: Optimization Framework

5. **Phase 5: Analysis** (Weeks 5-6)
   - Issue #90: Analysis & Reporting

6. **Phase 6: Finalization** (Week 6)
   - Issue #91: Dashboard Development
   - Issue #92: Documentation
