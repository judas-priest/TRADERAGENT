# TRADERAGENT v2.0 Strategy Documentation

## Architecture

All strategies implement the `BaseStrategy` abstract class (`bot/strategies/base.py`), providing a unified interface for the `BotOrchestrator`.

### Strategy Lifecycle

```
analyze_market(dfs...) -> BaseMarketAnalysis
        |
generate_signal(df, balance) -> BaseSignal | None
        |
open_position() -> PositionInfo
        |
update_positions(price, df) -> list[PositionInfo]  (check exits)
        |
close_position() -> PositionInfo
```

### Unified Types

| Type | Purpose |
|------|---------|
| `SignalDirection` | `LONG` or `SHORT` |
| `BaseSignal` | Entry price, SL, TP, confidence, R:R |
| `BaseMarketAnalysis` | Trend, sentiment, support/resistance |
| `PositionInfo` | Open position with entry, size, PnL |
| `StrategyPerformance` | Win rate, PnL, Sharpe, drawdown |
| `ExitReason` | TP, SL, trailing stop, breakeven, etc. |

---

## 1. SMC Strategy (Smart Money Concepts)

**Adapter**: `bot/strategies/smc_adapter.py` -> `SMCStrategyAdapter`
**Core**: `bot/strategies/smc/smc_strategy.py` -> `SMCStrategy`
**Config**: `bot/strategies/smc/config.py` -> `SMCConfig`

### Overview

Institutional-grade strategy based on Smart Money Concepts. Analyzes market structure across 4 timeframes to identify high-probability entries at Order Blocks and Fair Value Gaps.

### Multi-Timeframe Analysis

| Timeframe | Purpose |
|-----------|---------|
| D1 | Global trend direction |
| H4 | Market structure (BOS, CHoCH) |
| H1 | Confluence zones (OB, FVG) |
| M15 | Entry signals and timing |

### Components

1. **Market Structure Analyzer** - Identifies swing highs/lows, Break of Structure (BOS), Change of Character (CHoCH)
2. **Confluence Zone Analyzer** - Detects Order Blocks and Fair Value Gaps
3. **Entry Signal Generator** - Finds price action patterns at confluence zones
4. **Position Manager** - Kelly Criterion sizing, dynamic SL/TP, trailing stops

### Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `trend_timeframe` | `"1d"` | Timeframe for global trend |
| `structure_timeframe` | `"4h"` | Timeframe for market structure |
| `working_timeframe` | `"1h"` | Timeframe for confluence zones |
| `entry_timeframe` | `"15m"` | Timeframe for entries |
| `swing_length` | `5` | Candles for swing identification |
| `trend_period` | `20` | Trend detection lookback |
| `order_block_lookback` | `50` | OB search depth |
| `fvg_min_size` | `0.001` | Min FVG size (% of price) |
| `risk_per_trade` | `0.02` | 2% risk per trade |
| `min_risk_reward` | `2.5` | Minimum R:R ratio |
| `max_position_size` | `10000` | Max USD per position |
| `use_trailing_stop` | `true` | Enable trailing stop |
| `trailing_stop_activation` | `0.015` | Activate at 1.5% profit |
| `trailing_stop_distance` | `0.005` | Trail by 0.5% |
| `require_volume_confirmation` | `true` | Volume filter |
| `min_volume_multiplier` | `1.5` | 1.5x avg volume required |

---

## 2. Trend-Follower Strategy

**Adapter**: `bot/strategies/trend_follower_adapter.py` -> `TrendFollowerAdapter`
**Core**: `bot/strategies/trend_follower/` module

### Overview

Follows established trends using technical indicators. Uses a single timeframe and identifies trend direction via moving averages, RSI, and momentum indicators.

### Analysis Flow

1. Calculate moving averages (fast/slow)
2. Determine trend direction via crossovers
3. Confirm with RSI and momentum
4. Generate entry on pullback to support/resistance
5. Trail stops with ATR-based distance

### Key Characteristics

- Single-timeframe operation (uses first DataFrame only)
- Lower trade frequency, higher holding period
- Trend confirmation via multiple indicators
- ATR-based stop loss placement

---

## 3. Grid Strategy

**Adapter**: `bot/strategies/grid_adapter.py` -> `GridAdapter`
**Core**: `bot/strategies/grid/` module

### Overview

Places a grid of buy and sell orders at fixed price intervals around a center price. Profits from price oscillation within a range.

### How It Works

1. Define price range (upper/lower bounds)
2. Place grid levels evenly across the range
3. Buy when price hits a lower grid level
4. Sell when price hits an upper grid level
5. Profit from the spread between levels

### Key Parameters

| Parameter | Limit | Description |
|-----------|-------|-------------|
| `num_levels` | Max 50 | Number of grid levels |
| `amount_per_grid` | - | USD per grid order |
| `grid_range_pct` | Max 20% | Price range as % of center |

### Risk Considerations

- Total investment = `num_levels * amount_per_grid` (max $50,000)
- Works best in ranging/sideways markets
- Can accumulate losses in strong trends

---

## 4. DCA Strategy (Dollar Cost Averaging)

**Adapter**: `bot/strategies/dca_adapter.py` -> `DCAAdapter`
**Core**: `bot/strategies/dca/` module

### Overview

Places an initial order and adds safety orders as price dips, averaging down the entry price. Takes profit when the averaged price reaches the take-profit target.

### How It Works

1. Place base order at current price
2. If price drops, place safety orders at defined intervals
3. Each safety order averages down the entry
4. Take profit when average price + TP% reached

### Key Parameters

| Parameter | Limit | Description |
|-----------|-------|-------------|
| `base_order_size` | - | Initial order size in USD |
| `safety_order_size` | - | Safety order size in USD |
| `max_safety_orders` | Max 10 | Maximum safety orders |
| `take_profit_pct` | Min 0.5% | Take profit percentage |

### Risk Considerations

- Max capital = `base + (safety_size * max_orders)` (max $50,000)
- Can tie up significant capital in drawdowns
- Works best in volatile markets with mean reversion

---

## Strategy Selection Guide

| Market Condition | Recommended Strategy |
|-----------------|---------------------|
| Strong trend | SMC or Trend-Follower |
| Range-bound | Grid |
| High volatility + mean reversion | DCA |
| Uncertain | SMC (multi-timeframe analysis) |

## Switching Strategies

Use the Telegram `/switch_strategy` command or the orchestrator API:

```python
orchestrator.switch_strategy("smc")  # or "trend_follower", "grid", "dca"
```
