"""
Risk Manager Module

Manages capital and risk:
- Position sizing (2% risk per trade, max 1% drawdown)
- Drawdown protection (reduce size after consecutive losses)
- Daily loss limits
- Balance checks before trading
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from bot.strategies.trend_follower.entry_logic import EntrySignal, SignalType
from bot.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TradeRecord:
    """Record of a completed trade"""
    timestamp: datetime
    signal_type: SignalType
    entry_price: Decimal
    exit_price: Decimal
    size: Decimal
    profit_loss: Decimal
    is_win: bool


@dataclass
class RiskMetrics:
    """Current risk metrics"""
    current_capital: Decimal
    available_capital: Decimal
    daily_pnl: Decimal
    consecutive_losses: int
    total_trades_today: int
    max_position_size_allowed: Decimal
    risk_per_trade_pct: Decimal
    can_trade: bool
    rejection_reason: Optional[str] = None


class RiskManager:
    """
    Manages trading risk and capital allocation

    Implements risk management from Issue #124 (updated per owner requirements):
    - Position Size: 1% of current capital per trade (updated from 2%)
    - Max Total Exposure: 20% of capital in open positions (new requirement)
    - Max Drawdown: Not more than 1% of capital per trade
    - Drawdown Protection: Reduce size by 50% after 3 consecutive losses
    - Daily Limits: Stop trading after max daily loss reached
    """

    def __init__(
        self,
        initial_capital: Decimal,
        risk_per_trade_pct: Decimal = Decimal('0.01'),  # Updated to 1%
        max_risk_per_trade_pct: Decimal = Decimal('0.01'),
        max_position_size_usd: Decimal = Decimal('10000'),
        max_total_exposure_pct: Decimal = Decimal('0.20'),  # New: max 20% total exposure
        max_consecutive_losses: int = 3,
        size_reduction_factor: Decimal = Decimal('0.5'),
        max_daily_loss_usd: Decimal = Decimal('500'),
        max_positions: int = 20,  # Updated to 20 (20 x 1% = 20% max)
        min_balance_buffer_pct: Decimal = Decimal('0.1')
    ):
        """
        Initialize Risk Manager

        Args:
            initial_capital: Starting capital
            risk_per_trade_pct: Risk per trade as % of capital (default: 1%, updated)
            max_risk_per_trade_pct: Max drawdown per trade (default: 1%)
            max_position_size_usd: Maximum position size in USD
            max_total_exposure_pct: Max % of capital in open positions (default: 20%, new)
            max_consecutive_losses: Trigger for size reduction (default: 3)
            size_reduction_factor: Size reduction after losses (default: 50%)
            max_daily_loss_usd: Max daily loss before stopping (default: $500)
            max_positions: Maximum concurrent positions (default: 20, updated)
            min_balance_buffer_pct: Min balance buffer % (default: 10%)
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_risk_per_trade_pct = max_risk_per_trade_pct
        self.max_position_size_usd = max_position_size_usd
        self.max_total_exposure_pct = max_total_exposure_pct
        self.max_consecutive_losses = max_consecutive_losses
        self.size_reduction_factor = size_reduction_factor
        self.max_daily_loss_usd = max_daily_loss_usd
        self.max_positions = max_positions
        self.min_balance_buffer_pct = min_balance_buffer_pct

        # State tracking
        self.consecutive_losses = 0
        self.trade_history: list[TradeRecord] = []
        self.active_positions_count = 0
        self.active_positions_total_value = Decimal('0')  # Track total value in open positions
        self.current_date = date.today()
        self.daily_pnl = Decimal('0')
        self.daily_trades = 0

        logger.info(
            "RiskManager initialized",
            initial_capital=float(initial_capital),
            risk_per_trade=float(risk_per_trade_pct),
            max_total_exposure=float(max_total_exposure_pct),
            max_daily_loss=float(max_daily_loss_usd),
            max_positions=max_positions
        )

    def check_can_trade(
        self,
        entry_signal: EntrySignal,
        current_balance: Decimal
    ) -> RiskMetrics:
        """
        Check if trading is allowed and calculate position size

        Args:
            entry_signal: Entry signal to evaluate
            current_balance: Current account balance

        Returns:
            RiskMetrics with trading decision and parameters
        """
        self._update_daily_metrics()
        self.current_capital = current_balance

        # Calculate available capital (with buffer)
        buffer = current_balance * self.min_balance_buffer_pct
        available_capital = current_balance - buffer

        # Check if sufficient balance
        if available_capital <= 0:
            return RiskMetrics(
                current_capital=self.current_capital,
                available_capital=available_capital,
                daily_pnl=self.daily_pnl,
                consecutive_losses=self.consecutive_losses,
                total_trades_today=self.daily_trades,
                max_position_size_allowed=Decimal('0'),
                risk_per_trade_pct=self.risk_per_trade_pct,
                can_trade=False,
                rejection_reason="Insufficient balance (below buffer threshold)"
            )

        # Check daily loss limit
        if abs(self.daily_pnl) >= self.max_daily_loss_usd:
            return RiskMetrics(
                current_capital=self.current_capital,
                available_capital=available_capital,
                daily_pnl=self.daily_pnl,
                consecutive_losses=self.consecutive_losses,
                total_trades_today=self.daily_trades,
                max_position_size_allowed=Decimal('0'),
                risk_per_trade_pct=self.risk_per_trade_pct,
                can_trade=False,
                rejection_reason=f"Daily loss limit reached: ${float(abs(self.daily_pnl))}"
            )

        # Check max positions
        if self.active_positions_count >= self.max_positions:
            pos_msg = (
                f"Max positions reached: "
                f"{self.active_positions_count}/{self.max_positions}"
            )
            return RiskMetrics(
                current_capital=self.current_capital,
                available_capital=available_capital,
                daily_pnl=self.daily_pnl,
                consecutive_losses=self.consecutive_losses,
                total_trades_today=self.daily_trades,
                max_position_size_allowed=Decimal('0'),
                risk_per_trade_pct=self.risk_per_trade_pct,
                can_trade=False,
                rejection_reason=pos_msg
            )

        # Check total exposure limit (new requirement: max 20% of capital in open positions)
        max_total_exposure_usd = current_balance * self.max_total_exposure_pct
        if self.active_positions_total_value >= max_total_exposure_usd:
            exposure_msg = (
                f"Max total exposure reached: "
                f"${float(self.active_positions_total_value):.2f} / "
                f"${float(max_total_exposure_usd):.2f} "
                f"({float(self.max_total_exposure_pct * 100):.0f}% of capital)"
            )
            return RiskMetrics(
                current_capital=self.current_capital,
                available_capital=available_capital,
                daily_pnl=self.daily_pnl,
                consecutive_losses=self.consecutive_losses,
                total_trades_today=self.daily_trades,
                max_position_size_allowed=Decimal('0'),
                risk_per_trade_pct=self.risk_per_trade_pct,
                can_trade=False,
                rejection_reason=exposure_msg
            )

        # Calculate position size with risk management
        position_size = self._calculate_position_size(entry_signal, available_capital)

        return RiskMetrics(
            current_capital=self.current_capital,
            available_capital=available_capital,
            daily_pnl=self.daily_pnl,
            consecutive_losses=self.consecutive_losses,
            total_trades_today=self.daily_trades,
            max_position_size_allowed=position_size,
            risk_per_trade_pct=self.risk_per_trade_pct,
            can_trade=True
        )

    def _calculate_position_size(
        self,
        entry_signal: EntrySignal,
        available_capital: Decimal
    ) -> Decimal:
        """
        Calculate position size based on risk management rules

        - Base size: risk_per_trade_pct% of capital (1% per owner requirement)
        - Adjust for consecutive losses (reduce by size_reduction_factor)
        - Limit by max_position_size_usd
        - Ensure max drawdown <= max_risk_per_trade_pct%
        """
        # Base position size (1% of capital per owner requirement)
        base_size = available_capital * self.risk_per_trade_pct

        # Apply consecutive loss reduction
        if self.consecutive_losses >= self.max_consecutive_losses:
            base_size *= self.size_reduction_factor
            logger.info(
                "Position size reduced due to consecutive losses",
                losses=self.consecutive_losses,
                reduction_factor=float(self.size_reduction_factor),
                new_size=float(base_size)
            )

        # Calculate size based on stop loss distance to respect max risk
        entry_price = entry_signal.entry_price
        market_conditions = entry_signal.market_conditions

        # Estimate SL distance based on ATR
        atr = market_conditions.atr
        sl_distance = atr * Decimal('1.0')  # Conservative estimate

        # Max risk in USD
        max_risk_usd = available_capital * self.max_risk_per_trade_pct

        # Position size to respect max risk
        risk_based_size = max_risk_usd / (sl_distance / entry_price)

        # Use the smaller of base_size and risk_based_size
        position_size = min(base_size, risk_based_size)

        # Apply maximum position size limit
        position_size = min(position_size, self.max_position_size_usd)

        logger.debug(
            "Position size calculated",
            base_size=float(base_size),
            risk_based_size=float(risk_based_size),
            final_size=float(position_size),
            risk_pct=float((position_size * sl_distance / entry_price) / available_capital)
        )

        return position_size

    def record_trade(
        self,
        signal_type: SignalType,
        entry_price: Decimal,
        exit_price: Decimal,
        size: Decimal
    ) -> None:
        """
        Record completed trade and update metrics

        Args:
            signal_type: LONG or SHORT
            entry_price: Entry price
            exit_price: Exit price
            size: Position size
        """
        # Calculate P&L
        if signal_type == SignalType.LONG:
            profit_loss = (exit_price - entry_price) * size / entry_price
        else:
            profit_loss = (entry_price - exit_price) * size / entry_price

        is_win = profit_loss > 0

        # Create trade record
        trade = TradeRecord(
            timestamp=datetime.now(),
            signal_type=signal_type,
            entry_price=entry_price,
            exit_price=exit_price,
            size=size,
            profit_loss=profit_loss,
            is_win=is_win
        )

        self.trade_history.append(trade)
        self.daily_pnl += profit_loss
        self.daily_trades += 1

        # Update capital
        self.current_capital += profit_loss

        # Update consecutive losses
        if is_win:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1

        logger.info(
            "Trade recorded",
            type=signal_type,
            pnl=float(profit_loss),
            is_win=is_win,
            consecutive_losses=self.consecutive_losses,
            new_capital=float(self.current_capital),
            daily_pnl=float(self.daily_pnl)
        )

    def position_opened(self, position_value: Decimal) -> None:
        """
        Increment active positions counter and track total exposure

        Args:
            position_value: USD value of the opened position
        """
        self.active_positions_count += 1
        self.active_positions_total_value += position_value
        logger.debug(
            "Position opened",
            active_count=self.active_positions_count,
            position_value=float(position_value),
            total_exposure=float(self.active_positions_total_value)
        )

    def position_closed(self, position_value: Decimal) -> None:
        """
        Decrement active positions counter and reduce total exposure

        Args:
            position_value: USD value of the closed position
        """
        self.active_positions_count = max(0, self.active_positions_count - 1)
        self.active_positions_total_value = max(Decimal('0'), self.active_positions_total_value - position_value)
        logger.debug(
            "Position closed",
            active_count=self.active_positions_count,
            position_value=float(position_value),
            total_exposure=float(self.active_positions_total_value)
        )

    def _update_daily_metrics(self) -> None:
        """Reset daily metrics if new day"""
        current_date = date.today()
        if current_date != self.current_date:
            logger.info(
                "New trading day",
                previous_daily_pnl=float(self.daily_pnl),
                previous_trades=self.daily_trades
            )
            self.current_date = current_date
            self.daily_pnl = Decimal('0')
            self.daily_trades = 0

    def get_statistics(self) -> dict:
        """
        Get trading statistics

        Returns:
            Dictionary with performance metrics
        """
        if not self.trade_history:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0,
                'current_capital': float(self.current_capital)
            }

        wins = [t for t in self.trade_history if t.is_win]
        losses = [t for t in self.trade_history if not t.is_win]

        total_win = sum(t.profit_loss for t in wins)
        total_loss = abs(sum(t.profit_loss for t in losses))

        profit_factor = float(total_win / total_loss) if total_loss > 0 else float('inf')

        return {
            'total_trades': len(self.trade_history),
            'win_rate': len(wins) / len(self.trade_history) * 100,
            'total_pnl': float(sum(t.profit_loss for t in self.trade_history)),
            'avg_win': float(total_win / len(wins)) if wins else 0.0,
            'avg_loss': float(total_loss / len(losses)) if losses else 0.0,
            'profit_factor': profit_factor,
            'current_capital': float(self.current_capital),
            'daily_pnl': float(self.daily_pnl),
            'consecutive_losses': self.consecutive_losses
        }
