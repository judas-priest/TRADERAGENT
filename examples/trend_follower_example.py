"""
Trend-Follower Strategy Example

Demonstrates basic usage of the Trend-Follower strategy with simulated data.
"""

from decimal import Decimal
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from bot.strategies.trend_follower import TrendFollowerStrategy, TrendFollowerConfig


def generate_sample_data(periods: int = 200) -> pd.DataFrame:
    """
    Generate sample OHLCV data for testing

    Args:
        periods: Number of candles to generate

    Returns:
        DataFrame with OHLCV data
    """
    print(f"Generating {periods} candles of sample data...")

    # Generate timestamps
    end_time = datetime.now()
    timestamps = [end_time - timedelta(hours=i) for i in range(periods)]
    timestamps.reverse()

    # Generate price data with trend
    base_price = 45000
    prices = []
    current_price = base_price

    for i in range(periods):
        # Add trend component
        trend = 0.002 if i < periods / 2 else -0.001
        # Add random walk
        change = np.random.normal(trend, 0.01)
        current_price *= (1 + change)
        prices.append(current_price)

    # Create OHLC data
    data = []
    for i, price in enumerate(prices):
        high = price * (1 + abs(np.random.normal(0, 0.005)))
        low = price * (1 - abs(np.random.normal(0, 0.005)))
        open_price = prices[i-1] if i > 0 else price
        close = price
        volume = np.random.uniform(100, 1000)

        data.append({
            'open': open_price,
            'high': max(high, open_price, close),
            'low': min(low, open_price, close),
            'close': close,
            'volume': volume
        })

    df = pd.DataFrame(data, index=timestamps)
    print(f"✓ Generated data from {df.index[0]} to {df.index[-1]}")
    print(f"  Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")

    return df


def main():
    """Run Trend-Follower strategy example"""
    print("=" * 70)
    print("TREND-FOLLOWER STRATEGY EXAMPLE")
    print("=" * 70)
    print()

    # Create custom configuration
    config = TrendFollowerConfig(
        # Indicators
        ema_fast_period=20,
        ema_slow_period=50,
        atr_period=14,
        rsi_period=14,

        # Entry logic
        require_volume_confirmation=True,
        volume_multiplier=Decimal('1.3'),  # More lenient for example
        max_atr_filter_pct=Decimal('0.05'),

        # Position management
        enable_trailing_stop=True,
        enable_partial_close=True,
        enable_breakeven=True,

        # Risk management
        risk_per_trade_pct=Decimal('0.02'),
        max_consecutive_losses=3,
        max_daily_loss_usd=Decimal('500'),
        max_positions=3,

        # Logging
        log_all_signals=True,
        log_market_phases=True,
        debug_mode=False
    )

    # Initialize strategy
    initial_capital = Decimal("10000")
    print(f"📊 Initializing strategy with ${initial_capital} capital")
    print()

    strategy = TrendFollowerStrategy(
        config=config,
        initial_capital=initial_capital,
        log_trades=True,
        log_file_path="logs/trend_follower_example.jsonl"
    )

    # Generate sample data
    df = generate_sample_data(periods=200)
    print()

    # Analyze market conditions
    print("-" * 70)
    print("MARKET ANALYSIS")
    print("-" * 70)

    market_conditions = strategy.analyze_market(df)

    print(f"📈 Market Phase: {market_conditions.phase}")
    print(f"💪 Trend Strength: {market_conditions.trend_strength}")
    print(f"💵 Current Price: ${market_conditions.current_price:.2f}")
    print(f"📉 EMA(20): ${market_conditions.ema_fast:.2f}")
    print(f"📉 EMA(50): ${market_conditions.ema_slow:.2f}")
    print(f"📊 EMA Divergence: {float(market_conditions.ema_divergence_pct) * 100:.2f}%")
    print(f"📈 ATR: ${market_conditions.atr:.2f} ({float(market_conditions.atr_pct) * 100:.2f}%)")
    print(f"🎯 RSI: {market_conditions.rsi:.2f}")
    print()

    # Check for entry signal
    print("-" * 70)
    print("ENTRY SIGNAL CHECK")
    print("-" * 70)

    current_balance = initial_capital
    entry_data = strategy.check_entry_signal(df, current_balance)

    if entry_data:
        entry_signal, risk_metrics, position_size = entry_data

        print(f"✅ Entry signal found!")
        print(f"   Type: {entry_signal.signal_type.upper()}")
        print(f"   Reason: {entry_signal.entry_reason}")
        print(f"   Entry Price: ${entry_signal.entry_price:.2f}")
        print(f"   Confidence: {float(entry_signal.confidence) * 100:.1f}%")
        print(f"   Volume Confirmed: {'✓' if entry_signal.volume_confirmed else '✗'}")
        print()
        print(f"💰 Position Sizing:")
        print(f"   Position Size: ${position_size:.2f}")
        print(f"   Risk per Trade: {float(risk_metrics.risk_per_trade_pct) * 100:.1f}%")
        print(f"   Available Capital: ${risk_metrics.available_capital:.2f}")
        print()

        # Open position
        print("-" * 70)
        print("OPENING POSITION")
        print("-" * 70)

        position_id = strategy.open_position(entry_signal, position_size)
        positions = strategy.get_active_positions()
        position = positions[position_id]

        print(f"📝 Position ID: {position_id[:8]}...")
        print(f"   Entry: ${position.entry_price:.2f}")
        print(f"   Stop Loss: ${position.levels.stop_loss:.2f}")
        print(f"   Take Profit: ${position.levels.take_profit:.2f}")
        print(f"   Size: ${position.size:.2f}")
        print(f"   Status: {position.status}")
        print()

        # Simulate price updates
        print("-" * 70)
        print("POSITION UPDATES (Simulated)")
        print("-" * 70)

        # Generate a few more candles
        extended_df = pd.concat([
            df,
            generate_sample_data(periods=10).iloc[-10:]
        ])

        for i in range(5):
            current_price = Decimal(str(extended_df['close'].iloc[-5 + i]))
            print(f"\n📊 Update #{i+1}: Price = ${current_price:.2f}")

            exit_reason = strategy.update_position(position_id, current_price, extended_df.iloc[:len(df) + i + 1])

            position = strategy.get_active_positions().get(position_id)
            if position:
                print(f"   Profit: ${position.current_profit:.2f}")
                print(f"   Status: {position.status}")
                if position.levels.trailing_stop:
                    print(f"   Trailing SL: ${position.levels.trailing_stop:.2f}")

            if exit_reason:
                print(f"\n🔔 Exit triggered: {exit_reason}")
                strategy.close_position(position_id, exit_reason, current_price)
                break
        else:
            # Close manually if not exited
            print(f"\n🔔 Manually closing position")
            strategy.close_position(position_id, "manual", current_price)

        print()

    else:
        print(f"❌ No entry signal at current market conditions")
        print(f"   Market phase: {market_conditions.phase}")
        print(f"   Waiting for valid setup...")
        print()

    # Display statistics
    print("-" * 70)
    print("STRATEGY STATISTICS")
    print("-" * 70)

    stats = strategy.get_statistics()

    print(f"📊 Risk Metrics:")
    print(f"   Current Capital: ${stats['risk_metrics']['current_capital']:.2f}")
    print(f"   Daily P&L: ${stats['risk_metrics']['daily_pnl']:.2f}")
    print(f"   Consecutive Losses: {stats['risk_metrics']['consecutive_losses']}")
    print(f"   Active Positions: {stats['active_positions']}")
    print()

    if 'trade_statistics' in stats:
        trade_stats = stats['trade_statistics']
        print(f"📈 Trade Statistics:")
        print(f"   Total Trades: {trade_stats['total_trades']}")
        print(f"   Win Rate: {trade_stats['win_rate']:.1f}%")
        print(f"   Profit Factor: {trade_stats['profit_factor']:.2f}")
        print(f"   Total Profit: ${trade_stats['total_profit']:.2f}")
        print(f"   Avg Win: ${trade_stats['avg_win']:.2f}")
        print(f"   Avg Loss: ${trade_stats['avg_loss']:.2f}")
        print(f"   Max Drawdown: {trade_stats['max_drawdown']:.2f}%")
        print(f"   Sharpe Ratio: {trade_stats['sharpe_ratio']:.2f}")
        print()

    # Validate performance (if enough trades)
    if stats.get('trade_statistics', {}).get('total_trades', 0) > 0:
        print("-" * 70)
        print("PERFORMANCE VALIDATION")
        print("-" * 70)

        validation = strategy.validate_performance()

        if validation['validated']:
            print("✅ Strategy meets all performance criteria!")
        else:
            print(f"⚠️  Strategy validation: {len(validation['failed_criteria'])} criteria failed")

        print()
        for criterion, data in validation['criteria'].items():
            status = "✓" if data['pass'] else "✗"
            print(f"  {status} {criterion}: {data['value']:.2f} (threshold: {data['threshold']:.2f})")
        print()

    print("=" * 70)
    print("Example completed!")
    print("Check logs/trend_follower_example.jsonl for detailed trade logs")
    print("=" * 70)


if __name__ == "__main__":
    main()
