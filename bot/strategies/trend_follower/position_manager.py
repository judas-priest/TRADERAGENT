"""
Position Manager Module

Manages open positions with dynamic TP/SL, trailing stops, and partial close:
- Calculate TP and SL based on ATR and market phase
- Implement breakeven move
- Implement trailing stop
- Implement partial position close
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from bot.strategies.trend_follower.entry_logic import EntrySignal, SignalType
from bot.strategies.trend_follower.market_analyzer import MarketConditions, TrendStrength
from bot.utils.logger import get_logger

logger = get_logger(__name__)


class PositionStatus(str, Enum):
    """Position status"""
    OPEN = "open"
    PARTIAL_CLOSED = "partial_closed"
    BREAKEVEN = "breakeven"
    TRAILING = "trailing"
    CLOSED = "closed"


class ExitReason(str, Enum):
    """Reason for position exit"""
    TAKE_PROFIT = "take_profit"
    STOP_LOSS = "stop_loss"
    PARTIAL_TAKE_PROFIT = "partial_take_profit"
    TRAILING_STOP = "trailing_stop"
    MANUAL = "manual"


@dataclass
class PositionLevels:
    """Position price levels"""
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    breakeven_price: Optional[Decimal] = None
    trailing_stop: Optional[Decimal] = None
    partial_tp_price: Optional[Decimal] = None


@dataclass
class Position:
    """Active trading position"""
    signal_type: SignalType
    entry_price: Decimal
    entry_time: datetime
    size: Decimal  # Position size (quantity or USD value)
    levels: PositionLevels
    status: PositionStatus
    market_conditions: MarketConditions
    entry_signal: EntrySignal
    max_profit: Decimal = Decimal('0')
    current_profit: Decimal = Decimal('0')
    partial_closed_size: Decimal = Decimal('0')


class PositionManager:
    """
    Manages trading positions with dynamic risk management

    Implements position management from Issue #124:
    - Calculate TP/SL based on ATR and market phase:
        * TP = Entry_price ± (ATR × Multiplier)
          Multiplier: Sideways=1.2, Weak trend=1.8, Strong trend=2.5
        * SL = Entry_price ∓ (ATR × Multiplier_SL)
          Multiplier_SL: Sideways=0.7, Trend=1.0

    - Trailing Stop:
        * When profit > 1 × ATR: move SL to breakeven
        * When profit > 1.5 × ATR: activate trailing with 0.5 × ATR distance

    - Partial Close:
        * At 70% of TP target: close 50% of position
        * Continue with remaining 50% using trailing stop
    """

    def __init__(
        self,
        tp_multipliers: tuple = (Decimal('1.2'), Decimal('1.8'), Decimal('2.5')),
        sl_multipliers: tuple = (Decimal('0.7'), Decimal('1.0'), Decimal('1.0')),
        enable_breakeven: bool = True,
        breakeven_activation_atr: Decimal = Decimal('1.0'),
        enable_trailing: bool = True,
        trailing_activation_atr: Decimal = Decimal('1.5'),
        trailing_distance_atr: Decimal = Decimal('0.5'),
        enable_partial_close: bool = True,
        partial_close_percentage: Decimal = Decimal('0.50'),
        partial_tp_percentage: Decimal = Decimal('0.70')
    ):
        """
        Initialize Position Manager

        Args:
            tp_multipliers: TP multipliers for (sideways, weak_trend, strong_trend)
            sl_multipliers: SL multipliers for (sideways, weak_trend, strong_trend)
            enable_breakeven: Enable breakeven move
            breakeven_activation_atr: ATR multiplier to activate breakeven
            enable_trailing: Enable trailing stop
            trailing_activation_atr: ATR multiplier to activate trailing
            trailing_distance_atr: ATR multiplier for trailing distance
            enable_partial_close: Enable partial close
            partial_close_percentage: Percentage to close at partial TP
            partial_tp_percentage: Percentage of TP to trigger partial close
        """
        self.tp_multipliers = tp_multipliers
        self.sl_multipliers = sl_multipliers
        self.enable_breakeven = enable_breakeven
        self.breakeven_activation_atr = breakeven_activation_atr
        self.enable_trailing = enable_trailing
        self.trailing_activation_atr = trailing_activation_atr
        self.trailing_distance_atr = trailing_distance_atr
        self.enable_partial_close = enable_partial_close
        self.partial_close_percentage = partial_close_percentage
        self.partial_tp_percentage = partial_tp_percentage

        self.active_positions: dict[str, Position] = {}

        logger.info(
            "PositionManager initialized",
            tp_multipliers=tuple(float(x) for x in tp_multipliers),
            sl_multipliers=tuple(float(x) for x in sl_multipliers),
            trailing_enabled=enable_trailing,
            partial_close_enabled=enable_partial_close
        )

    def open_position(
        self,
        entry_signal: EntrySignal,
        position_size: Decimal,
        position_id: str
    ) -> Position:
        """
        Open a new position based on entry signal

        Args:
            entry_signal: Entry signal with market conditions
            position_size: Position size (quantity or USD value)
            position_id: Unique position identifier

        Returns:
            Position object
        """
        conditions = entry_signal.market_conditions

        # Calculate TP and SL levels
        levels = self._calculate_levels(
            entry_signal.signal_type,
            entry_signal.entry_price,
            conditions
        )

        position = Position(
            signal_type=entry_signal.signal_type,
            entry_price=entry_signal.entry_price,
            entry_time=datetime.now(),
            size=position_size,
            levels=levels,
            status=PositionStatus.OPEN,
            market_conditions=conditions,
            entry_signal=entry_signal
        )

        self.active_positions[position_id] = position

        logger.info(
            "Position opened",
            id=position_id,
            type=entry_signal.signal_type,
            entry=float(entry_signal.entry_price),
            sl=float(levels.stop_loss),
            tp=float(levels.take_profit),
            size=float(position_size)
        )

        return position

    def update_position(
        self,
        position_id: str,
        current_price: Decimal,
        market_conditions: MarketConditions
    ) -> Optional[ExitReason]:
        """
        Update position with current price and check exit conditions

        Args:
            position_id: Position identifier
            current_price: Current market price
            market_conditions: Current market conditions

        Returns:
            ExitReason if position should be closed, None otherwise
        """
        if position_id not in self.active_positions:
            logger.warning("Position not found", id=position_id)
            return None

        position = self.active_positions[position_id]

        # Calculate current profit
        if position.signal_type == SignalType.LONG:
            position.current_profit = current_price - position.entry_price
        else:
            position.current_profit = position.entry_price - current_price

        # Update max profit
        position.max_profit = max(position.max_profit, position.current_profit)

        # Check stop loss
        if self._check_stop_loss(position, current_price):
            return ExitReason.STOP_LOSS

        # Check take profit
        if self._check_take_profit(position, current_price):
            return ExitReason.TAKE_PROFIT

        # Check partial take profit
        if (self.enable_partial_close and
            position.status == PositionStatus.OPEN and
            self._check_partial_tp(position, current_price)):
            self._execute_partial_close(position, position_id)
            return ExitReason.PARTIAL_TAKE_PROFIT

        # Move to breakeven
        if (self.enable_breakeven and
            position.status == PositionStatus.OPEN and
            self._should_move_to_breakeven(position, market_conditions)):
            self._move_to_breakeven(position)

        # Activate trailing stop
        valid_statuses = (
            PositionStatus.OPEN, PositionStatus.BREAKEVEN, PositionStatus.PARTIAL_CLOSED
        )
        if (self.enable_trailing and
            position.status in valid_statuses and
            self._should_activate_trailing(position, market_conditions)):
            self._activate_trailing_stop(position, current_price, market_conditions)

        # Update trailing stop
        if (position.status == PositionStatus.TRAILING and
            position.levels.trailing_stop):
            self._update_trailing_stop(position, current_price, market_conditions)
            if self._check_trailing_stop(position, current_price):
                return ExitReason.TRAILING_STOP

        return None

    def close_position(self, position_id: str, reason: ExitReason) -> None:
        """Close position"""
        if position_id in self.active_positions:
            position = self.active_positions[position_id]
            position.status = PositionStatus.CLOSED

            logger.info(
                "Position closed",
                id=position_id,
                reason=reason,
                profit=float(position.current_profit),
                duration=(datetime.now() - position.entry_time).total_seconds()
            )

            del self.active_positions[position_id]

    def _calculate_levels(
        self,
        signal_type: SignalType,
        entry_price: Decimal,
        conditions: MarketConditions
    ) -> PositionLevels:
        """Calculate TP and SL levels based on market phase"""
        atr = conditions.atr

        # Select multipliers based on trend strength
        if conditions.trend_strength == TrendStrength.STRONG:
            tp_mult = self.tp_multipliers[2]  # Strong trend
            sl_mult = self.sl_multipliers[2]
        elif conditions.trend_strength == TrendStrength.WEAK:
            tp_mult = self.tp_multipliers[1]  # Weak trend
            sl_mult = self.sl_multipliers[1]
        else:
            tp_mult = self.tp_multipliers[0]  # Sideways
            sl_mult = self.sl_multipliers[0]

        # Calculate TP and SL
        if signal_type == SignalType.LONG:
            take_profit = entry_price + (atr * tp_mult)
            stop_loss = entry_price - (atr * sl_mult)
        else:  # SHORT
            take_profit = entry_price - (atr * tp_mult)
            stop_loss = entry_price + (atr * sl_mult)

        # Calculate partial TP price if enabled
        partial_tp_price = None
        if self.enable_partial_close:
            partial_tp_distance = (take_profit - entry_price) * self.partial_tp_percentage
            partial_tp_price = entry_price + partial_tp_distance

        return PositionLevels(
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            partial_tp_price=partial_tp_price
        )

    def _check_stop_loss(self, position: Position, current_price: Decimal) -> bool:
        """Check if stop loss hit"""
        sl = position.levels.trailing_stop or position.levels.stop_loss

        if position.signal_type == SignalType.LONG:
            return current_price <= sl
        else:
            return current_price >= sl

    def _check_take_profit(self, position: Position, current_price: Decimal) -> bool:
        """Check if take profit hit"""
        if position.signal_type == SignalType.LONG:
            return current_price >= position.levels.take_profit
        else:
            return current_price <= position.levels.take_profit

    def _check_partial_tp(self, position: Position, current_price: Decimal) -> bool:
        """Check if partial take profit level reached"""
        if not position.levels.partial_tp_price:
            return False

        if position.signal_type == SignalType.LONG:
            return current_price >= position.levels.partial_tp_price
        else:
            return current_price <= position.levels.partial_tp_price

    def _execute_partial_close(self, position: Position, position_id: str) -> None:
        """Execute partial close of position"""
        close_size = position.size * self.partial_close_percentage
        position.partial_closed_size += close_size
        position.size -= close_size
        position.status = PositionStatus.PARTIAL_CLOSED

        logger.info(
            "Partial close executed",
            id=position_id,
            closed_size=float(close_size),
            remaining_size=float(position.size),
            profit=float(position.current_profit)
        )

    def _should_move_to_breakeven(
        self, position: Position, conditions: MarketConditions
    ) -> bool:
        """Check if position should move to breakeven"""
        profit_threshold = conditions.atr * self.breakeven_activation_atr
        return position.current_profit >= profit_threshold

    def _move_to_breakeven(self, position: Position) -> None:
        """Move stop loss to breakeven"""
        position.levels.breakeven_price = position.entry_price
        position.levels.stop_loss = position.entry_price
        position.status = PositionStatus.BREAKEVEN

        logger.info(
            "Moved to breakeven",
            entry=float(position.entry_price),
            profit=float(position.current_profit)
        )

    def _should_activate_trailing(
        self, position: Position, conditions: MarketConditions
    ) -> bool:
        """Check if trailing stop should be activated"""
        profit_threshold = conditions.atr * self.trailing_activation_atr
        return position.current_profit >= profit_threshold

    def _activate_trailing_stop(
        self, position: Position, current_price: Decimal, conditions: MarketConditions
    ) -> None:
        """Activate trailing stop"""
        trailing_distance = conditions.atr * self.trailing_distance_atr

        if position.signal_type == SignalType.LONG:
            position.levels.trailing_stop = current_price - trailing_distance
        else:
            position.levels.trailing_stop = current_price + trailing_distance

        position.status = PositionStatus.TRAILING

        logger.info(
            "Trailing stop activated",
            current_price=float(current_price),
            trailing_stop=float(position.levels.trailing_stop),
            distance=float(trailing_distance)
        )

    def _update_trailing_stop(
        self, position: Position, current_price: Decimal, conditions: MarketConditions
    ) -> None:
        """Update trailing stop if profit increased"""
        if not position.levels.trailing_stop:
            return

        trailing_distance = conditions.atr * self.trailing_distance_atr

        if position.signal_type == SignalType.LONG:
            new_trailing = current_price - trailing_distance
            if new_trailing > position.levels.trailing_stop:
                position.levels.trailing_stop = new_trailing
                logger.debug(
                    "Trailing stop updated",
                    new_stop=float(new_trailing),
                    current_price=float(current_price)
                )
        else:
            new_trailing = current_price + trailing_distance
            if new_trailing < position.levels.trailing_stop:
                position.levels.trailing_stop = new_trailing
                logger.debug(
                    "Trailing stop updated",
                    new_stop=float(new_trailing),
                    current_price=float(current_price)
                )

    def _check_trailing_stop(self, position: Position, current_price: Decimal) -> bool:
        """Check if trailing stop hit"""
        if not position.levels.trailing_stop:
            return False

        if position.signal_type == SignalType.LONG:
            return current_price <= position.levels.trailing_stop
        else:
            return current_price >= position.levels.trailing_stop
