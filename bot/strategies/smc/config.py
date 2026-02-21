"""
SMC Strategy Configuration
Default parameters based on issue #123 requirements
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class SMCConfig:
    """Smart Money Concepts strategy configuration"""

    # Timeframe settings
    trend_timeframe: str = "1d"  # D1 for global trend
    structure_timeframe: str = "4h"  # H4 for market structure
    working_timeframe: str = "1h"  # H1 for confluence zones
    entry_timeframe: str = "15m"  # M15 for entry signals

    # Market Structure parameters
    trend_period: int = 20  # Lookback period for trend detection
    swing_length: int = 50  # Candles for swing high/low identification
    close_break: bool = True  # BOS/CHoCH: require candle close beyond level (vs wick)

    # Confluence Zone parameters
    close_mitigation: bool = False  # OB: require close through OB for mitigation (vs wick)
    join_consecutive_fvg: bool = False  # FVG: merge adjacent same-direction FVGs
    liquidity_range_percent: float = 0.01  # Liquidity: % range for grouping swing clusters

    # Risk Management
    risk_per_trade: Decimal = Decimal("0.02")  # 2% risk per trade
    min_risk_reward: Decimal = Decimal("2.5")  # Minimum R:R ratio
    max_position_size: Decimal = Decimal("10000")  # Max position in USD

    # Entry Signal parameters
    require_volume_confirmation: bool = True
    min_volume_multiplier: Decimal = Decimal("1.5")  # 1.5x average volume

    # Position Management
    max_positions: int = 3  # Maximum concurrent positions
    use_trailing_stop: bool = True
    trailing_stop_activation: Decimal = Decimal("0.015")  # Activate at +1.5% profit
    trailing_stop_distance: Decimal = Decimal("0.005")  # Trail by 0.5%

    # Performance thresholds (for validation)
    min_profit_factor: Decimal = Decimal("1.5")
    max_drawdown: Decimal = Decimal("0.15")  # 15%
    min_sharpe_ratio: Decimal = Decimal("1.0")
    max_hold_time_hours: int = 48

    # Logging
    debug_mode: bool = True
    log_all_signals: bool = True


# Default configuration instance
DEFAULT_SMC_CONFIG = SMCConfig()
