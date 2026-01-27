# Fibonacci Tower Indicator

## Overview

**Fibonacci Tower** is a TradingView indicator written in Pine Script v5 that identifies buy signals based on a multi-condition strategy combining technical analysis tools with automatic Fibonacci level construction.

## Strategy Logic

The indicator generates buy signals when **all three conditions** are met simultaneously:

1. **Three Consecutive Bearish Candles**: Price action shows three candles in a row where the closing price is lower than the opening price, indicating downward momentum that may be exhausting.

2. **RSI Oversold Condition**: The Relative Strength Index (RSI) falls below the oversold threshold (default: 30), suggesting the asset may be oversold and due for a reversal.

3. **MACD Reversal**: The MACD line crosses above the signal line (bullish crossover) while the histogram was negative in the previous bar, indicating a potential momentum shift from bearish to bullish.

## Fibonacci Tower Feature

When a buy signal is detected, the indicator automatically constructs a "Fibonacci Tower" by:

1. Identifying the swing high and swing low within the lookback period (default: 100 bars)
2. Calculating and plotting seven Fibonacci retracement levels:
   - **0.0%** (Tower Base) - Red solid line
   - **23.6%** - Orange dashed line
   - **38.2%** - Yellow dashed line
   - **50.0%** - Blue solid line (thicker)
   - **61.8%** (Golden Ratio) - Green dashed line (thicker)
   - **78.6%** - Purple dashed line
   - **100.0%** (Tower Top) - Red solid line

These levels serve as potential support/resistance zones and profit-taking targets.

## Input Parameters

### RSI Settings
- **RSI Length**: Period for RSI calculation (default: 14)
- **RSI Oversold Level**: Threshold for oversold condition (default: 30)

### MACD Settings
- **MACD Fast Length**: Fast EMA period (default: 12)
- **MACD Slow Length**: Slow EMA period (default: 26)
- **MACD Signal Length**: Signal line period (default: 9)

### Fibonacci Settings
- **Fibonacci Lookback Period**: Bars to scan for swing high/low (default: 100)
- **Show Fibonacci Levels**: Toggle to display/hide Fibonacci lines

### Display Settings
- **Show Buy Signals**: Toggle to display/hide buy signal markers
- **Show Level Labels**: Toggle to display/hide Fibonacci level labels

## How to Use

### Installation

1. Open TradingView and navigate to the Pine Editor
2. Create a new indicator
3. Copy the entire code from `fibonacci_tower.pine`
4. Save and add to your chart

### Interpretation

- **Green Triangle Up + "BUY" label**: Indicates all three conditions are met
- **Green background highlight**: Visual confirmation of buy signal
- **Fibonacci levels**: Use these as potential targets or areas to watch for price reactions

### Best Practices

- **Confirm signals**: Don't rely solely on this indicator. Use additional analysis like volume, support/resistance zones, and higher timeframe trends
- **Risk management**: Always use stop losses below the signal candle or below the 0% Fibonacci level
- **Profit targets**: Consider taking partial profits at key Fibonacci levels (38.2%, 50%, 61.8%)
- **Timeframe**: Test the indicator on different timeframes to find what works best for your trading style

## Alert Setup

The indicator includes a built-in alert condition:

1. Right-click on the chart → "Add Alert"
2. Select "Fibonacci Tower Buy Signal" from the condition dropdown
3. Configure your notification preferences
4. Create the alert

You'll receive notifications whenever all three conditions align for a buy signal.

## Technical Implementation Details

- **Pine Script Version**: v5
- **Overlay**: Yes (indicator appears on the price chart)
- **Maximum Lines**: 500 (allows for historical Fibonacci levels)
- **Calculations**:
  - RSI: Uses `ta.rsi()` function
  - MACD: Uses `ta.macd()` function returning line, signal, and histogram
  - Swing points: Uses `ta.highest()` and `ta.lowest()` over lookback period

## Limitations and Considerations

- **Lagging indicators**: RSI and MACD are based on historical prices and may lag in fast-moving markets
- **False signals**: No indicator is perfect; false signals can occur, especially in ranging markets
- **Whipsaws**: Multiple buy signals may appear in choppy conditions
- **Lookback dependency**: Fibonacci levels quality depends on the selected lookback period

## Customization Ideas

You can modify the script to:
- Add additional filters (e.g., volume confirmation, trend filter)
- Adjust the number of bearish candles required
- Change RSI and MACD parameters for different assets or timeframes
- Add sell signal logic for a complete strategy
- Extend Fibonacci levels beyond 100% (161.8%, 200%, etc.)

## Troubleshooting

### No Visualization Appearing?

If you don't see Fibonacci levels or buy signals after adding the indicator:

1. **Check Signal Conditions**: The indicator requires ALL three conditions simultaneously:
   - 3 consecutive bearish candles (close < open)
   - RSI below 30 (oversold)
   - MACD bullish crossover with negative histogram

   These conditions may be rare on some timeframes/assets. Try:
   - Looking at longer historical data (scroll back further)
   - Testing on volatile assets (BTC, ETH) with 4H or 1D timeframes
   - Adjusting RSI threshold (increase to 35-40 for more signals)

2. **Verify Settings**:
   - Ensure "Show Fibonacci Levels" is enabled in indicator settings
   - Ensure "Show Buy Signals" is enabled
   - Check that "Show Level Labels" is enabled to see the level markers

3. **Chart Requirements**:
   - Need at least 100+ bars of history (default Fibonacci lookback period)
   - Indicator works best with sufficient price data

4. **Script Compilation**:
   - Make sure there are no compilation errors in Pine Editor
   - Code should be Pine Script v5 compatible

### Common Issues

- **Lines not extending**: Lines now use `extend=extend.right` to automatically extend to chart edge
- **Labels not showing**: Labels appear at signal bar with left alignment
- **Old signals disappearing**: By design, only the most recent signal's Fibonacci levels are shown

## Version History

- **v1.1**: Bug fixes for visualization (2025-01-27)
  - Fixed line rendering using `extend=extend.right` instead of future bar indices
  - Added validation to prevent drawing with NA coordinates
  - Improved label positioning for consistency
  - Enhanced reliability in real-time mode

- **v1.0**: Initial release with core functionality
  - Three bearish candles detection
  - RSI oversold condition
  - MACD reversal detection
  - Automatic Fibonacci tower construction
  - Visual buy signals and alerts

## Credits

Developed for TRADERAGENT crypto trading system.

## License

This source code is subject to the terms of the Mozilla Public License 2.0.

## References

For more information on the technical indicators used:
- [Fibonacci Retracements Guide](https://pineify.app/resources/blog/pine-script-fibonacci-guide)
- [Combining Indicators in Pine Script](https://pineify.app/resources/blog/how-to-combine-two-indicators-in-tradingview-pine-script)
- [Pine Script Documentation](https://www.tradingview.com/pine-script-docs/)
