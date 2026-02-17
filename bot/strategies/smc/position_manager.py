"""
Position Manager Module

Manages position sizing, stop loss, take profit, and risk validation:
- Kelly Criterion position sizing
- Dynamic SL adjustment (breakeven, trailing)
- Dynamic TP management (partial exits)
- Risk validation system
- Position performance tracking
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

import pandas as pd

from bot.strategies.smc.entry_signals import SMCSignal
from bot.strategies.smc.market_structure import MarketStructureAnalyzer
from bot.utils.logger import get_logger

logger = get_logger(__name__)


class PositionStatus(str, Enum):
    """Position status"""

    OPEN = "open"
    CLOSED = "closed"
    BREAKEVEN = "breakeven"
    PARTIAL = "partial"


@dataclass
class PositionMetrics:
    """Position performance metrics"""

    entry_price: Decimal
    current_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal

    position_size: Decimal
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")

    max_favorable_excursion: Decimal = Decimal("0")  # MFE
    max_adverse_excursion: Decimal = Decimal("0")  # MAE

    entry_time: datetime = field(default_factory=datetime.now)
    exit_time: Optional[datetime] = None
    hold_time_hours: float = 0.0

    status: PositionStatus = PositionStatus.OPEN
    exit_reason: Optional[str] = None


@dataclass
class PerformanceStats:
    """Strategy performance statistics"""

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    total_profit: Decimal = Decimal("0")
    total_loss: Decimal = Decimal("0")

    avg_win: Decimal = Decimal("0")
    avg_loss: Decimal = Decimal("0")

    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_rr: float = 0.0

    largest_win: Decimal = Decimal("0")
    largest_loss: Decimal = Decimal("0")

    avg_hold_time_hours: float = 0.0

    def update_from_position(self, position: PositionMetrics):
        """Update stats from closed position"""
        if position.status != PositionStatus.CLOSED:
            return

        self.total_trades += 1

        pnl = position.realized_pnl

        if pnl > 0:
            self.winning_trades += 1
            self.total_profit += pnl
            self.largest_win = max(self.largest_win, pnl)
        else:
            self.losing_trades += 1
            self.total_loss += abs(pnl)
            self.largest_loss = max(self.largest_loss, abs(pnl))

        # Recalculate averages
        if self.winning_trades > 0:
            self.avg_win = self.total_profit / self.winning_trades

        if self.losing_trades > 0:
            self.avg_loss = self.total_loss / self.losing_trades

        if self.total_trades > 0:
            self.win_rate = self.winning_trades / self.total_trades

        if self.total_loss > 0:
            self.profit_factor = float(self.total_profit / self.total_loss)

        # Average hold time
        total_hold = position.hold_time_hours
        if self.total_trades > 1:
            # Running average
            self.avg_hold_time_hours = (
                self.avg_hold_time_hours * (self.total_trades - 1) + total_hold
            ) / self.total_trades
        else:
            self.avg_hold_time_hours = total_hold

    def get_kelly_inputs(self) -> tuple[float, float]:
        """
        Get inputs for Kelly Criterion

        Returns:
            Tuple of (win_rate, avg_win_loss_ratio)
        """
        if self.avg_loss == 0 or self.total_trades < 10:
            return 0.5, 2.0  # Default values

        win_loss_ratio = float(self.avg_win / self.avg_loss)

        return self.win_rate, win_loss_ratio


class PositionManager:
    """
    Manages trading positions with dynamic risk management
    """

    def __init__(
        self,
        market_structure: MarketStructureAnalyzer,
        account_balance: Decimal,
        risk_per_trade_pct: float = 2.0,
        max_position_size: Decimal = Decimal("10000"),
        min_rr_ratio: float = 2.5,
        use_kelly: bool = True,
        kelly_fraction: float = 0.25,
    ):
        """
        Initialize Position Manager

        Args:
            market_structure: MarketStructureAnalyzer instance
            account_balance: Account balance in quote currency
            risk_per_trade_pct: Default risk percentage per trade
            max_position_size: Maximum position size in quote currency
            min_rr_ratio: Minimum risk:reward ratio
            use_kelly: Whether to use Kelly Criterion for sizing
            kelly_fraction: Fractional Kelly (0.25 = quarter Kelly)
        """
        self.market_structure = market_structure
        self.account_balance = account_balance
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_position_size = max_position_size
        self.min_rr_ratio = min_rr_ratio
        self.use_kelly = use_kelly
        self.kelly_fraction = kelly_fraction

        self.open_positions: dict[str, PositionMetrics] = {}
        self.closed_positions: list[PositionMetrics] = []
        self.performance_stats = PerformanceStats()

        logger.info(
            "PositionManager initialized",
            balance=float(account_balance),
            risk_pct=risk_per_trade_pct,
            use_kelly=use_kelly,
        )

    def calculate_position_size(
        self, signal: SMCSignal, account_balance: Optional[Decimal] = None
    ) -> Decimal:
        """
        Calculate optimal position size for signal

        Args:
            signal: SMCSignal with entry and stop loss
            account_balance: Current account balance (uses stored if None)

        Returns:
            Position size in base currency
        """
        balance = account_balance or self.account_balance

        # Calculate risk amount in quote currency
        risk_per_trade = balance * Decimal(str(self.risk_per_trade_pct / 100))

        # Apply Kelly Criterion if enabled and sufficient history
        if self.use_kelly and self.performance_stats.total_trades >= 10:
            kelly_pct = self._calculate_kelly_percentage()
            if kelly_pct > 0:
                risk_per_trade = balance * Decimal(str(kelly_pct / 100))
                logger.debug(f"Using Kelly sizing: {kelly_pct:.2f}%")

        # Calculate position size based on stop loss
        risk_per_unit = abs(signal.entry_price - signal.stop_loss)

        if risk_per_unit == 0:
            logger.warning("Risk per unit is zero, cannot calculate position size")
            return Decimal("0")

        position_size = risk_per_trade / risk_per_unit

        # Apply maximum position size limit
        max_size_in_base = self.max_position_size / signal.entry_price
        position_size = min(position_size, max_size_in_base)

        logger.info(
            "Position size calculated",
            size=float(position_size),
            risk_amount=float(risk_per_trade),
            entry=float(signal.entry_price),
        )

        return position_size

    def _calculate_kelly_percentage(self) -> float:
        """
        Calculate Kelly Criterion percentage

        Kelly Formula: f* = (p*b - q) / b
        - p: win probability
        - q: loss probability (1-p)
        - b: ratio of avg win to avg loss

        Returns:
            Percentage of capital to risk
        """
        win_rate, win_loss_ratio = self.performance_stats.get_kelly_inputs()

        p = win_rate
        q = 1 - p
        b = win_loss_ratio

        if b == 0:
            return self.risk_per_trade_pct

        # Kelly formula
        kelly_f = (p * b - q) / b

        # Apply fractional Kelly for safety
        kelly_f = kelly_f * self.kelly_fraction

        # Convert to percentage and cap at reasonable limits
        kelly_pct = max(0.5, min(kelly_f * 100, 10.0))

        logger.debug(
            "Kelly calculated",
            win_rate=win_rate,
            win_loss_ratio=win_loss_ratio,
            kelly_pct=kelly_pct,
        )

        return kelly_pct

    def open_position(
        self, signal: SMCSignal, position_size: Decimal, position_id: str
    ) -> PositionMetrics:
        """
        Open a new position

        Args:
            signal: SMCSignal with trade details
            position_size: Calculated position size
            position_id: Unique position identifier

        Returns:
            PositionMetrics object
        """
        position = PositionMetrics(
            entry_price=signal.entry_price,
            current_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            position_size=position_size,
            entry_time=datetime.now(),
            status=PositionStatus.OPEN,
        )

        self.open_positions[position_id] = position

        logger.info(
            "Position opened",
            id=position_id,
            entry=float(signal.entry_price),
            sl=float(signal.stop_loss),
            tp=float(signal.take_profit),
            size=float(position_size),
        )

        return position

    def update_position(
        self, position_id: str, current_price: Decimal, df: Optional[pd.DataFrame] = None
    ) -> PositionMetrics:
        """
        Update position with current price and adjust SL/TP if needed

        Args:
            position_id: Position identifier
            current_price: Current market price
            df: Optional dataframe for structure-based trailing

        Returns:
            Updated PositionMetrics
        """
        if position_id not in self.open_positions:
            raise ValueError(f"Position {position_id} not found")

        position = self.open_positions[position_id]
        position.current_price = current_price

        # Calculate unrealized PnL
        if position.entry_price > position.stop_loss:  # Long position
            position.unrealized_pnl = (
                current_price - position.entry_price
            ) * position.position_size
        else:  # Short position
            position.unrealized_pnl = (
                position.entry_price - current_price
            ) * position.position_size

        # Update MFE and MAE
        position.max_favorable_excursion = max(
            position.max_favorable_excursion, position.unrealized_pnl
        )

        if position.unrealized_pnl < 0:
            position.max_adverse_excursion = min(
                position.max_adverse_excursion, position.unrealized_pnl
            )

        # Check for breakeven move
        if position.status == PositionStatus.OPEN:
            self._check_breakeven_move(position)

        # Trail stop loss if dataframe provided
        if df is not None and len(df) > 0:
            self._trail_stop_loss(position, df)

        return position

    def _check_breakeven_move(self, position: PositionMetrics) -> None:
        """
        Move stop loss to breakeven after 1:1 RR achieved
        """
        is_long = position.entry_price > position.stop_loss
        risk = abs(position.entry_price - position.stop_loss)

        if is_long:
            # Long: check if price moved up by 1x risk
            if position.current_price >= position.entry_price + risk:
                new_sl = position.entry_price
                if new_sl > position.stop_loss:
                    position.stop_loss = new_sl
                    position.status = PositionStatus.BREAKEVEN
                    logger.info(f"Moved SL to breakeven: {float(new_sl)}")
        else:
            # Short: check if price moved down by 1x risk
            if position.current_price <= position.entry_price - risk:
                new_sl = position.entry_price
                if new_sl < position.stop_loss:
                    position.stop_loss = new_sl
                    position.status = PositionStatus.BREAKEVEN
                    logger.info(f"Moved SL to breakeven: {float(new_sl)}")

    def _trail_stop_loss(self, position: PositionMetrics, df: pd.DataFrame) -> None:
        """
        Trail stop loss based on market structure (swing points)
        """
        is_long = position.entry_price < position.stop_loss

        # Get recent swing point
        if is_long:
            recent_swing = self.market_structure.get_recent_swing_low()
            if recent_swing:
                # Trail to swing low with buffer
                buffer = recent_swing.price * Decimal("0.005")  # 0.5%
                new_sl = recent_swing.price - buffer

                # Only trail up, never widen
                if new_sl > position.stop_loss:
                    position.stop_loss = new_sl
                    logger.debug(f"Trailed SL to {float(new_sl)}")
        else:
            recent_swing = self.market_structure.get_recent_swing_high()
            if recent_swing:
                # Trail to swing high with buffer
                buffer = recent_swing.price * Decimal("0.005")
                new_sl = recent_swing.price + buffer

                # Only trail down, never widen
                if new_sl < position.stop_loss:
                    position.stop_loss = new_sl
                    logger.debug(f"Trailed SL to {float(new_sl)}")

    def check_exit_conditions(
        self, position_id: str, current_price: Decimal
    ) -> tuple[bool, Optional[str]]:
        """
        Check if position should be exited

        Returns:
            Tuple of (should_exit, exit_reason)
        """
        if position_id not in self.open_positions:
            return False, None

        position = self.open_positions[position_id]
        is_long = position.entry_price < position.stop_loss

        # Check stop loss
        if is_long:
            if current_price <= position.stop_loss:
                return True, "stop_loss"
        else:
            if current_price >= position.stop_loss:
                return True, "stop_loss"

        # Check take profit
        if is_long:
            if current_price >= position.take_profit:
                return True, "take_profit"
        else:
            if current_price <= position.take_profit:
                return True, "take_profit"

        return False, None

    def close_position(
        self, position_id: str, exit_price: Decimal, exit_reason: str
    ) -> PositionMetrics:
        """
        Close an open position

        Args:
            position_id: Position identifier
            exit_price: Exit price
            exit_reason: Reason for exit

        Returns:
            Closed PositionMetrics
        """
        if position_id not in self.open_positions:
            raise ValueError(f"Position {position_id} not found")

        position = self.open_positions.pop(position_id)

        # Calculate realized PnL
        is_long = position.entry_price > position.stop_loss
        if is_long:
            position.realized_pnl = (exit_price - position.entry_price) * position.position_size
        else:
            position.realized_pnl = (position.entry_price - exit_price) * position.position_size

        # Update position
        position.current_price = exit_price
        position.status = PositionStatus.CLOSED
        position.exit_time = datetime.now()
        position.exit_reason = exit_reason

        # Calculate hold time
        hold_duration = position.exit_time - position.entry_time
        position.hold_time_hours = hold_duration.total_seconds() / 3600

        # Update account balance
        self.account_balance += position.realized_pnl

        # Update performance stats
        self.performance_stats.update_from_position(position)
        self.closed_positions.append(position)

        logger.info(
            "Position closed",
            id=position_id,
            pnl=float(position.realized_pnl),
            reason=exit_reason,
            hold_hours=position.hold_time_hours,
        )

        return position

    def validate_position_risk(self, signal: SMCSignal, position_size: Decimal) -> tuple[bool, str]:
        """
        Validate position meets risk management rules

        Returns:
            Tuple of (is_valid, rejection_reason)
        """
        # Check RR ratio
        if signal.risk_reward_ratio < self.min_rr_ratio:
            return False, f"RR ratio {signal.risk_reward_ratio:.2f} < minimum {self.min_rr_ratio}"

        # Check position size
        position_value = position_size * signal.entry_price
        if position_value > self.max_position_size:
            return (
                False,
                f"Position size {float(position_value):.2f} exceeds max {float(self.max_position_size)}",
            )

        # Check risk amount
        risk_amount = position_size * abs(signal.entry_price - signal.stop_loss)
        max_risk = self.account_balance * Decimal(str(self.risk_per_trade_pct / 100))

        if risk_amount > max_risk * Decimal("1.1"):  # 10% tolerance
            return False, f"Risk amount {float(risk_amount):.2f} exceeds max {float(max_risk):.2f}"

        # Check total exposure
        total_exposure = sum(
            pos.position_size * pos.current_price for pos in self.open_positions.values()
        )
        total_exposure += position_value

        max_total_exposure = self.account_balance * Decimal("3")  # Max 3x leverage
        if total_exposure > max_total_exposure:
            return (
                False,
                f"Total exposure {float(total_exposure):.2f} exceeds max {float(max_total_exposure)}",
            )

        return True, ""

    def get_position_summary(self) -> dict:
        """Get summary of all positions and performance"""
        return {
            "open_positions": len(self.open_positions),
            "closed_positions": len(self.closed_positions),
            "account_balance": float(self.account_balance),
            "total_unrealized_pnl": float(
                sum(pos.unrealized_pnl for pos in self.open_positions.values())
            ),
            "performance": {
                "total_trades": self.performance_stats.total_trades,
                "win_rate": self.performance_stats.win_rate,
                "profit_factor": self.performance_stats.profit_factor,
                "avg_win": float(self.performance_stats.avg_win),
                "avg_loss": float(self.performance_stats.avg_loss),
                "total_profit": float(self.performance_stats.total_profit),
                "total_loss": float(self.performance_stats.total_loss),
            },
        }
