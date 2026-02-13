# Trend-Follower Strategy

**Status:** ✅ Production Ready (v1.0.0)
**Issue:** [#124](https://github.com/alekseymavai/TRADERAGENT/issues/124)

## 📋 Overview

Adaptive Trend-Following strategy for cryptocurrency trading with comprehensive risk management and market phase detection. This strategy combines trend-following principles with adaptive position management to capture market movements while protecting capital.

### Key Features

- ✅ **Real-time Market Analysis** - EMA(20), EMA(50), ATR(14), RSI(14)
- ✅ **Market Phase Detection** - Bullish Trend, Bearish Trend, Sideways
- ✅ **Adaptive Entry Logic** - Different approaches for trending vs ranging markets
- ✅ **Dynamic Position Management** - ATR-based TP/SL, trailing stops, partial closes
- ✅ **Robust Risk Management** - Position sizing, drawdown protection, daily limits
- ✅ **Comprehensive Logging** - Full trade journal with entry/exit reasons
- ✅ **Performance Validation** - Built-in backtesting metrics validation

## 🎯 Strategy Logic

### 1. Market Analysis & Phase Detection

The strategy continuously analyzes market conditions using technical indicators:

**Indicators:**
- **EMA(20) & EMA(50):** Trend direction and momentum
- **ATR(14):** Volatility measurement for dynamic stops
- **RSI(14):** Momentum and overbought/oversold conditions

**Market Phases:**

- **Bullish Trend:**
  - EMA(20) > EMA(50)
  - Price > EMA(20)
  - EMA divergence > 0.5%

- **Bearish Trend:**
  - EMA(20) < EMA(50)
  - Price < EMA(20)
  - EMA divergence > 0.5%

- **Sideways (Ranging):**
  - EMA difference < 0.5%
  - Price within High-Low range of last 50 candles

### 2. Entry Logic

**For LONG Positions:**

*Trend Scenario:*
- Wait for pullback to EMA(20) or support zone
- Enter on bounce with volume confirmation
- Require increased volume (1.5x average)

*Sideways Scenario:*
- RSI exits oversold zone (<30)
- Range breakout upward with volume
- Support bounces with confirmation

**For SHORT Positions:**
- Inverse logic of LONG positions
- Pullback to EMA(20) or resistance
- RSI exits overbought (>70)
- Range breakout downward

**Filters:**
- ❌ Don't trade if ATR > 5% of price (high volatility filter)
- ❌ Volume confirmation required (configurable)
- ❌ Respect daily loss limits and position count

### 3. Position Management

**Dynamic TP/SL (Based on ATR & Market Phase):**

| Market Phase | TP Multiplier | SL Multiplier |
|--------------|---------------|---------------|
| Sideways     | 1.2 × ATR     | 0.7 × ATR     |
| Weak Trend   | 1.8 × ATR     | 1.0 × ATR     |
| Strong Trend | 2.5 × ATR     | 1.0 × ATR     |

**Trailing Stop:**
- Activate when profit > 1.5 × ATR
- Trail by 0.5 × ATR distance from peak
- Updates automatically as price moves favorably

**Breakeven:**
- Move SL to entry price when profit > 1 × ATR
- Protects position from turning into loss

**Partial Close:**
- Close 50% of position at 70% of TP target
- Continue with remaining 50% using trailing stop
- Locks in partial profit while letting winners run

### 4. Risk Management

**Position Sizing (Updated per owner requirements):**
- Base size: **1% of current capital per trade** (updated from 2%)
- Max drawdown: ≤ 1% of capital per trade
- Maximum position: $10,000 (configurable)
- **Max total exposure: 20% of capital in open positions** (new requirement)

**Drawdown Protection:**
- Track consecutive losses
- Reduce size by 50% after 3 consecutive losses
- Automatic recovery when winning streak returns

**Daily Limits:**
- Maximum daily loss: $500 (configurable)
- Stop trading when limit reached
- Reset at start of new trading day
- Maximum concurrent positions: **20** (updated from 3, to allow up to 20% exposure with 1% per position)

**Balance Checks:**
- Ensure sufficient balance before trading
- Maintain 10% buffer for margin
- API availability verification
- Check total exposure doesn't exceed 20% of capital

### 5. Trade Logging

**Comprehensive Trade Journal:**
- Entry/exit prices and timestamps
- Entry reason (pullback, support bounce, RSI signal, etc.)
- Exit reason (TP, SL, trailing stop, partial close)
- Market conditions at entry (phase, indicators, trend strength)
- Performance metrics (P&L, duration, max favorable/adverse excursion)
- Volume confirmation status and confidence score

**Performance Metrics:**
- Total trades and win rate
- Profit factor and average win/loss
- Maximum drawdown percentage
- Sharpe ratio (annualized)
- Average trade duration

## 💻 Usage

### Basic Usage

```python
from decimal import Decimal
import pandas as pd
from bot.strategies.trend_follower import TrendFollowerStrategy, TrendFollowerConfig

# Initialize strategy with default config
strategy = TrendFollowerStrategy(
    initial_capital=Decimal("10000"),
    log_trades=True
)

# Load OHLCV data
df = pd.DataFrame({
    'open': [...],
    'high': [...],
    'low': [...],
    'close': [...],
    'volume': [...]
})

# Analyze market
market_conditions = strategy.analyze_market(df)
print(f"Market Phase: {market_conditions.phase}")
print(f"Trend Strength: {market_conditions.trend_strength}")

# Check for entry signal
current_balance = Decimal("10000")
entry_data = strategy.check_entry_signal(df, current_balance)

if entry_data:
    entry_signal, risk_metrics, position_size = entry_data
    print(f"Entry Signal: {entry_signal.signal_type}")
    print(f"Reason: {entry_signal.entry_reason}")
    print(f"Position Size: ${position_size}")

    # Open position
    position_id = strategy.open_position(entry_signal, position_size)
    print(f"Position opened: {position_id}")

# Update position (in trading loop)
current_price = Decimal("45000")
exit_reason = strategy.update_position(position_id, current_price, df)

if exit_reason:
    print(f"Closing position: {exit_reason}")
    strategy.close_position(position_id, exit_reason, current_price)

# Get statistics
stats = strategy.get_statistics()
print(f"Win Rate: {stats['trade_statistics']['win_rate']:.2f}%")
print(f"Profit Factor: {stats['trade_statistics']['profit_factor']:.2f}")
```

### Custom Configuration

```python
from bot.strategies.trend_follower import TrendFollowerConfig
from decimal import Decimal

config = TrendFollowerConfig(
    # Indicators
    ema_fast_period=20,
    ema_slow_period=50,
    atr_period=14,
    rsi_period=14,

    # Market Phase Detection
    ema_divergence_threshold=Decimal('0.005'),  # 0.5%

    # Entry Logic
    require_volume_confirmation=True,
    volume_multiplier=Decimal('1.5'),
    max_atr_filter_pct=Decimal('0.05'),  # Don't trade if ATR > 5%

    # Position Management
    tp_multipliers=(Decimal('1.2'), Decimal('1.8'), Decimal('2.5')),
    sl_multipliers=(Decimal('0.7'), Decimal('1.0'), Decimal('1.0')),
    enable_trailing_stop=True,
    trailing_activation_atr=Decimal('1.5'),
    enable_partial_close=True,
    partial_close_percentage=Decimal('0.50'),

    # Risk Management (updated per owner requirements)
    risk_per_trade_pct=Decimal('0.01'),  # 1% (updated from 2%)
    max_risk_per_trade_pct=Decimal('0.01'),  # 1%
    max_position_size_usd=Decimal('10000'),
    max_total_exposure_pct=Decimal('0.20'),  # 20% max total exposure (new)
    max_consecutive_losses=3,
    max_daily_loss_usd=Decimal('500'),
    max_positions=20,  # Updated from 3 (allows 20 x 1% = 20% max)

    # Logging
    log_all_signals=True,
    log_market_phases=True,
    debug_mode=False
)

strategy = TrendFollowerStrategy(config=config, initial_capital=Decimal("10000"))
```

## 📊 Performance Validation

The strategy includes built-in performance validation against the criteria from Issue #124:

```python
validation = strategy.validate_performance()

if validation['validated']:
    print("✅ Strategy meets all performance criteria")
else:
    print(f"❌ Failed criteria: {validation['failed_criteria']}")

# Performance criteria:
# - Sharpe Ratio > 1.0
# - Max Drawdown < 20%
# - Profit Factor > 1.5
# - Win Rate > 45%
# - Profit/Loss Ratio > 1.5
```

## 🧪 Testing

### Unit Tests

```bash
# Run all trend_follower tests
pytest tests/strategies/trend_follower/ -v

# Run specific component tests
pytest tests/strategies/trend_follower/test_market_analyzer.py -v
pytest tests/strategies/trend_follower/test_entry_logic.py -v
pytest tests/strategies/trend_follower/test_position_manager.py -v
pytest tests/strategies/trend_follower/test_risk_manager.py -v

# With coverage
pytest tests/strategies/trend_follower/ --cov=bot.strategies.trend_follower --cov-report=html
```

### Backtesting

**Owner's Testing Requirements (per PR #131 comments):**

```bash
# Test configuration as specified by repository owner:
# Symbol: ETH/USDT
# Exchange: Bybit
# Timeframes: d1, h4, h1, m15, m5
# Date range: 2024-01-01 to 2026-02-10
# Position size: 1% of deposit
# Max total exposure: 20% of deposit (USDT)

# Example backtest command for each timeframe:
python -m bot.tests.backtesting.backtesting_engine \
    --strategy trend_follower \
    --exchange bybit \
    --symbol ETH/USDT \
    --timeframe 1d \
    --start-date 2024-01-01 \
    --end-date 2026-02-10 \
    --initial-capital 10000

# Run all required timeframes:
for tf in 1d 4h 1h 15m 5m; do
    python -m bot.tests.backtesting.backtesting_engine \
        --strategy trend_follower \
        --exchange bybit \
        --symbol ETH/USDT \
        --timeframe $tf \
        --start-date 2024-01-01 \
        --end-date 2026-02-10 \
        --initial-capital 10000 \
        --output results_${tf}.json
done

# Expected metrics (minimum requirements from Issue #124):
# - Sharpe Ratio: > 1.0
# - Max Drawdown: < 20%
# - Profit Factor: > 1.5
# - Win Rate: > 45%
```

## 📁 Module Structure

```
bot/strategies/trend_follower/
├── __init__.py                      # Package exports
├── config.py                        # Configuration dataclass (146 lines)
├── market_analyzer.py               # Market phase detection & indicators (322 lines)
├── entry_logic.py                   # Entry signal generation (465 lines)
├── position_manager.py              # Position management & TP/SL (398 lines)
├── risk_manager.py                  # Risk & capital management (287 lines)
├── trade_logger.py                  # Trade logging & metrics (310 lines)
├── trend_follower_strategy.py       # Main strategy orchestration (462 lines)
└── README.md                        # This file
```

**Total:** ~2,400 production lines of code

## 🔄 Integration with DCA-Grid Bots

Similar to SMC Strategy, Trend-Follower can serve as an advisory tool for DCA-Grid bot launches:

```python
class TrendFollowerGridAdvisor:
    """Use Trend-Follower signals to optimize DCA-Grid bot launches"""

    def should_launch_grid_bot(self, symbol: str, df: pd.DataFrame) -> dict:
        strategy = TrendFollowerStrategy()

        # Analyze market
        conditions = strategy.analyze_market(df)

        # Check entry signal
        entry_data = strategy.check_entry_signal(df, current_balance)

        if entry_data:
            signal, metrics, size = entry_data
            if signal.confidence > Decimal('0.7'):
                return {
                    'launch': True,
                    'direction': signal.signal_type,
                    'entry_price': signal.entry_price,
                    'grid_lower': signal.entry_price * Decimal('0.95'),
                    'grid_upper': signal.entry_price * Decimal('1.05'),
                    'market_phase': conditions.phase,
                    'confidence': signal.confidence
                }

        return {'launch': False}
```

## 📈 Expected Performance

Based on backtesting requirements from Issue #124:

- **Sharpe Ratio:** > 1.0 (target: 1.3)
- **Maximum Drawdown:** < 20% (target: 12-15%)
- **Profit Factor:** > 1.5 (target: 1.8)
- **Win Rate:** > 45% (target: 52%)
- **Profit/Loss Ratio:** > 1.5 (target: 1.8)

*Note: Actual performance may vary based on market conditions, timeframe, and configuration parameters.*

## ⚙️ Configuration Parameters

### Market Analysis
- `ema_fast_period`: Fast EMA period (default: 20)
- `ema_slow_period`: Slow EMA period (default: 50)
- `atr_period`: ATR period for volatility (default: 14)
- `rsi_period`: RSI period for momentum (default: 14)

### Entry Logic
- `require_volume_confirmation`: Require volume spike (default: True)
- `volume_multiplier`: Volume threshold multiplier (default: 1.5)
- `max_atr_filter_pct`: Max ATR filter (default: 0.05 = 5%)

### Position Management
- `tp_multipliers`: TP multipliers for (sideways, weak, strong) trends
- `sl_multipliers`: SL multipliers for market phases
- `enable_trailing_stop`: Enable trailing stops (default: True)
- `enable_partial_close`: Enable partial profit taking (default: True)

### Risk Management
- `risk_per_trade_pct`: Risk per trade (default: 0.01 = 1%, updated from 2%)
- `max_risk_per_trade_pct`: Max drawdown (default: 0.01 = 1%)
- `max_total_exposure_pct`: Max total exposure in positions (default: 0.20 = 20%, new)
- `max_consecutive_losses`: Trigger for size reduction (default: 3)
- `max_daily_loss_usd`: Daily stop loss (default: $500)
- `max_positions`: Max concurrent positions (default: 20, updated from 3)

See [config.py](config.py) for complete parameter list with descriptions.

## 📝 Trade Log Example

```json
{
  "trade_id": "uuid",
  "timestamp": "2026-02-12T10:30:00",
  "signal_type": "long",
  "entry_reason": "trend_pullback_to_ema",
  "entry_price": 45000.00,
  "entry_time": "2026-02-12T10:30:00",
  "exit_reason": "trailing_stop",
  "exit_price": 46500.00,
  "exit_time": "2026-02-12T14:30:00",
  "position_size": 200.00,
  "stop_loss": 44500.00,
  "take_profit": 47000.00,
  "market_phase": "bullish_trend",
  "trend_strength": "weak",
  "profit_loss": 300.00,
  "profit_loss_pct": 3.33,
  "duration_seconds": 14400,
  "volume_confirmed": true,
  "confidence": 0.85
}
```

## 🚀 Roadmap

- ✅ v1.0.0: Complete implementation (Released 2026-02-12)
- 🔄 v1.1.0: Advanced pattern recognition (Q1 2026)
- 🔄 v1.2.0: ML-based parameter optimization (Q2 2026)
- 🔄 v2.0.0: Multi-timeframe confluence analysis (Q3 2026)

## 📚 References

- Issue #124: [Trend-Follower Strategy Implementation](https://github.com/alekseymavai/TRADERAGENT/issues/124)
- Technical Analysis: Alexander Elder - "Trading for a Living"
- Risk Management: Van K. Tharp - "Trade Your Way to Financial Freedom"

## 📄 License

Mozilla Public License 2.0 - Same as TRADERAGENT project

---

**⚠️ Disclaimer:** This strategy is for educational purposes only. Always backtest thoroughly and start with small amounts. Past performance does not guarantee future results.
