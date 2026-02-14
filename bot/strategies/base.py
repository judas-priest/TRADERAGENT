"""
BaseStrategy - Abstract base class for all trading strategies in TRADERAGENT v2.0.

Defines a unified interface that all strategies (SMC, Trend-Follower, Grid, DCA)
must implement for integration with BotOrchestrator v2.0.

Unified types:
- SignalDirection: LONG / SHORT
- BaseSignal: Common signal structure with strategy-specific metadata
- BaseMarketAnalysis: Common market analysis result
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

import pandas as pd


# =============================================================================
# Unified Enums
# =============================================================================


class SignalDirection(str, Enum):
    """Unified signal direction for all strategies."""

    LONG = "long"
    SHORT = "short"


class ExitReason(str, Enum):
    """Unified exit reasons."""

    TAKE_PROFIT = "take_profit"
    STOP_LOSS = "stop_loss"
    TRAILING_STOP = "trailing_stop"
    BREAKEVEN = "breakeven"
    PARTIAL_CLOSE = "partial_close"
    MANUAL = "manual"
    SIGNAL_REVERSED = "signal_reversed"
    RISK_LIMIT = "risk_limit"
    TIMEOUT = "timeout"


# =============================================================================
# Unified Data Structures
# =============================================================================


@dataclass
class BaseSignal:
    """
    Unified signal structure for all strategies.

    Each strategy wraps its specific signal data in the `metadata` dict,
    while exposing common fields for the orchestrator.
    """

    direction: SignalDirection
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    confidence: float  # 0.0 - 1.0
    timestamp: datetime
    strategy_type: str  # 'smc', 'trend_follower', 'grid', 'dca'
    signal_reason: str = ""  # Human-readable reason
    risk_reward_ratio: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def risk_amount(self) -> Decimal:
        """Distance from entry to stop loss."""
        if self.direction == SignalDirection.LONG:
            return self.entry_price - self.stop_loss
        return self.stop_loss - self.entry_price

    @property
    def reward_amount(self) -> Decimal:
        """Distance from entry to take profit."""
        if self.direction == SignalDirection.LONG:
            return self.take_profit - self.entry_price
        return self.entry_price - self.take_profit

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "direction": self.direction.value,
            "entry_price": str(self.entry_price),
            "stop_loss": str(self.stop_loss),
            "take_profit": str(self.take_profit),
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "strategy_type": self.strategy_type,
            "signal_reason": self.signal_reason,
            "risk_reward_ratio": self.risk_reward_ratio,
            "metadata": self.metadata,
        }


@dataclass
class BaseMarketAnalysis:
    """
    Unified market analysis result.

    Provides common fields and allows strategy-specific details in `details`.
    """

    trend: str  # 'bullish', 'bearish', 'sideways', 'unknown'
    trend_strength: float  # 0.0 (no trend) - 1.0 (very strong)
    volatility: float  # ATR or normalized volatility metric
    timestamp: datetime
    strategy_type: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "trend": self.trend,
            "trend_strength": self.trend_strength,
            "volatility": self.volatility,
            "timestamp": self.timestamp.isoformat(),
            "strategy_type": self.strategy_type,
            "details": self.details,
        }


@dataclass
class PositionInfo:
    """Unified position information for status reporting."""

    position_id: str
    direction: SignalDirection
    entry_price: Decimal
    current_price: Decimal
    size: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    unrealized_pnl: Decimal
    entry_time: datetime
    strategy_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyPerformance:
    """Unified performance metrics."""

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: Decimal = Decimal("0")
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    avg_trade_pnl: Decimal = Decimal("0")
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 4),
            "total_pnl": str(self.total_pnl),
            "profit_factor": round(self.profit_factor, 4),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "avg_trade_pnl": str(self.avg_trade_pnl),
            "metadata": self.metadata,
        }


# =============================================================================
# Abstract Base Class
# =============================================================================


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.

    All strategies must implement these methods to integrate with
    BotOrchestrator v2.0 and StrategyRegistry.

    Lifecycle:
        1. __init__(config) - Initialize with configuration
        2. analyze_market(dfs) - Analyze market conditions
        3. generate_signal(df, balance) - Generate entry signal
        4. open_position(signal, size) - Open a position
        5. update_positions(price, df) - Update active positions (check TP/SL)
        6. close_position(id, reason, price) - Close a position
        7. get_status() - Get current strategy status
    """

    @abstractmethod
    def get_strategy_name(self) -> str:
        """Return unique strategy instance name."""
        ...

    @abstractmethod
    def get_strategy_type(self) -> str:
        """Return strategy type (e.g., 'smc', 'trend_follower', 'grid', 'dca')."""
        ...

    @abstractmethod
    def analyze_market(self, *dfs: pd.DataFrame) -> BaseMarketAnalysis:
        """
        Analyze market conditions.

        Accepts variable number of DataFrames for multi-timeframe strategies.
        Single-timeframe strategies can accept just one DataFrame.

        Args:
            *dfs: One or more OHLCV DataFrames (columns: open, high, low, close, volume).

        Returns:
            BaseMarketAnalysis with trend, volatility, and strategy-specific details.
        """
        ...

    @abstractmethod
    def generate_signal(
        self, df: pd.DataFrame, current_balance: Decimal
    ) -> Optional[BaseSignal]:
        """
        Generate an entry signal based on current market data.

        Args:
            df: Primary OHLCV DataFrame for signal generation.
            current_balance: Available balance for position sizing.

        Returns:
            BaseSignal if conditions are met, None otherwise.
        """
        ...

    @abstractmethod
    def open_position(self, signal: BaseSignal, position_size: Decimal) -> str:
        """
        Open a new position based on signal.

        Args:
            signal: The entry signal.
            position_size: Size of the position in quote currency.

        Returns:
            Position ID string.
        """
        ...

    @abstractmethod
    def update_positions(
        self, current_price: Decimal, df: pd.DataFrame
    ) -> list[tuple[str, ExitReason]]:
        """
        Update all active positions with current price.

        Checks TP/SL, trailing stops, partial closes, etc.

        Args:
            current_price: Current market price.
            df: Latest OHLCV data for analysis.

        Returns:
            List of (position_id, exit_reason) tuples for positions that should close.
        """
        ...

    @abstractmethod
    def close_position(
        self, position_id: str, exit_reason: ExitReason, exit_price: Decimal
    ) -> None:
        """
        Close a specific position.

        Args:
            position_id: ID of the position to close.
            exit_reason: Reason for closing.
            exit_price: Price at which position is closed.
        """
        ...

    @abstractmethod
    def get_active_positions(self) -> list[PositionInfo]:
        """Get all currently active positions as unified PositionInfo."""
        ...

    @abstractmethod
    def get_performance(self) -> StrategyPerformance:
        """Get strategy performance metrics."""
        ...

    def get_status(self) -> dict[str, Any]:
        """
        Get comprehensive strategy status.

        Default implementation; strategies can override for more detail.
        """
        positions = self.get_active_positions()
        performance = self.get_performance()

        return {
            "name": self.get_strategy_name(),
            "type": self.get_strategy_type(),
            "active_positions": len(positions),
            "positions": [
                {
                    "id": p.position_id,
                    "direction": p.direction.value,
                    "entry_price": str(p.entry_price),
                    "unrealized_pnl": str(p.unrealized_pnl),
                }
                for p in positions
            ],
            "performance": performance.to_dict(),
        }

    def reset(self) -> None:
        """
        Reset strategy state. Used for backtesting.

        Default: no-op. Strategies that need reset should override.
        """
        pass
