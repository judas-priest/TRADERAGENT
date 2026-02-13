"""
Trade Logger Module

Logs all trades with entry/exit reasons for analysis and backtesting
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

from bot.strategies.trend_follower.entry_logic import EntryReason, EntrySignal, SignalType
from bot.strategies.trend_follower.position_manager import ExitReason
from bot.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TradeLog:
    """Complete trade log entry"""

    # Trade identification
    trade_id: str
    timestamp: datetime

    # Entry information
    signal_type: SignalType
    entry_reason: EntryReason
    entry_price: Decimal
    entry_time: datetime

    # Exit information
    exit_reason: ExitReason
    exit_price: Decimal
    exit_time: datetime

    # Position details
    position_size: Decimal
    stop_loss: Decimal
    take_profit: Decimal

    # Market conditions at entry
    market_phase: str
    trend_strength: str
    ema_fast: Decimal
    ema_slow: Decimal
    atr: Decimal
    rsi: Decimal

    # Performance
    profit_loss: Decimal
    profit_loss_pct: Decimal
    duration_seconds: float
    max_favorable_excursion: Optional[Decimal] = None
    max_adverse_excursion: Optional[Decimal] = None

    # Additional info
    volume_confirmed: bool = False
    confidence: Decimal = Decimal("0")
    notes: str = ""


class TradeLogger:
    """
    Logs all trades with detailed information for analysis

    Implements logging requirement from Issue #124:
    - Keep journal of all trades with entry/exit reasons
    - Enable backtesting with key metrics (Sharpe Ratio, max drawdown, total profit)
    """

    def __init__(
        self,
        log_file_path: Optional[str] = None,
        log_to_file: bool = True,
        log_to_console: bool = True,
    ):
        """
        Initialize Trade Logger

        Args:
            log_file_path: Path to trade log file (default: logs/trades.jsonl)
            log_to_file: Whether to log to file
            log_to_console: Whether to log to console
        """
        self.log_to_file = log_to_file
        self.log_to_console = log_to_console

        if log_file_path:
            self.log_file = Path(log_file_path)
        else:
            self.log_file = Path("logs/trades.jsonl")

        # Create logs directory if needed
        if self.log_to_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)

        self.trade_logs: list[TradeLog] = []

        logger.info(
            "TradeLogger initialized",
            log_file=str(self.log_file) if log_to_file else None,
            log_to_file=log_to_file,
            log_to_console=log_to_console,
        )

    def log_trade(
        self,
        trade_id: str,
        entry_signal: EntrySignal,
        exit_reason: ExitReason,
        exit_price: Decimal,
        exit_time: datetime,
        position_size: Decimal,
        stop_loss: Decimal,
        take_profit: Decimal,
        max_favorable_excursion: Optional[Decimal] = None,
        max_adverse_excursion: Optional[Decimal] = None,
        notes: str = "",
    ) -> None:
        """
        Log a completed trade

        Args:
            trade_id: Unique trade identifier
            entry_signal: Entry signal that initiated the trade
            exit_reason: Reason for exit
            exit_price: Exit price
            exit_time: Exit timestamp
            position_size: Position size
            stop_loss: Stop loss level
            take_profit: Take profit level
            max_favorable_excursion: Maximum profit during trade
            max_adverse_excursion: Maximum loss during trade
            notes: Additional notes
        """
        # Calculate P&L
        if entry_signal.signal_type == SignalType.LONG:
            profit_loss = exit_price - entry_signal.entry_price
        else:
            profit_loss = entry_signal.entry_price - exit_price

        profit_loss_pct = (profit_loss / entry_signal.entry_price) * Decimal("100")

        # Calculate duration
        duration = (exit_time - entry_signal.timestamp).total_seconds()

        # Create trade log
        trade_log = TradeLog(
            trade_id=trade_id,
            timestamp=datetime.now(),
            signal_type=entry_signal.signal_type,
            entry_reason=entry_signal.entry_reason,
            entry_price=entry_signal.entry_price,
            entry_time=entry_signal.timestamp,
            exit_reason=exit_reason,
            exit_price=exit_price,
            exit_time=exit_time,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            market_phase=entry_signal.market_conditions.phase,
            trend_strength=entry_signal.market_conditions.trend_strength,
            ema_fast=entry_signal.market_conditions.ema_fast,
            ema_slow=entry_signal.market_conditions.ema_slow,
            atr=entry_signal.market_conditions.atr,
            rsi=entry_signal.market_conditions.rsi,
            profit_loss=profit_loss,
            profit_loss_pct=profit_loss_pct,
            duration_seconds=duration,
            max_favorable_excursion=max_favorable_excursion,
            max_adverse_excursion=max_adverse_excursion,
            volume_confirmed=entry_signal.volume_confirmed,
            confidence=entry_signal.confidence,
            notes=notes,
        )

        self.trade_logs.append(trade_log)

        # Log to console
        if self.log_to_console:
            logger.info(
                "Trade completed",
                id=trade_id,
                type=entry_signal.signal_type,
                entry_reason=entry_signal.entry_reason,
                exit_reason=exit_reason,
                pnl=float(profit_loss),
                pnl_pct=float(profit_loss_pct),
                duration=duration,
                market_phase=entry_signal.market_conditions.phase,
            )

        # Log to file
        if self.log_to_file:
            self._write_to_file(trade_log)

    def _write_to_file(self, trade_log: TradeLog) -> None:
        """Write trade log to file in JSONL format"""
        try:
            # Convert to dict and handle Decimal/datetime serialization
            log_dict = asdict(trade_log)

            # Convert Decimal to float for JSON serialization
            for key, value in log_dict.items():
                if isinstance(value, Decimal):
                    log_dict[key] = float(value)
                elif isinstance(value, datetime):
                    log_dict[key] = value.isoformat()

            # Append to file
            with open(self.log_file, "a") as f:
                f.write(json.dumps(log_dict) + "\n")

        except Exception as e:
            logger.error("Failed to write trade log to file", error=str(e))

    def get_all_trades(self) -> list[TradeLog]:
        """Get all logged trades"""
        return self.trade_logs.copy()

    def get_statistics(self) -> dict:
        """
        Calculate trading statistics from logged trades

        Returns key metrics for backtesting validation:
        - Total trades
        - Win rate
        - Profit factor
        - Average win/loss
        - Max drawdown
        - Sharpe ratio (simplified)
        """
        if not self.trade_logs:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "total_profit": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
            }

        wins = [t for t in self.trade_logs if t.profit_loss > 0]
        losses = [t for t in self.trade_logs if t.profit_loss <= 0]

        total_win = sum(float(t.profit_loss) for t in wins)
        total_loss = abs(sum(float(t.profit_loss) for t in losses))

        profit_factor = total_win / total_loss if total_loss > 0 else float("inf")

        # Calculate drawdown
        capital = 10000.0  # Starting capital assumption
        peak = capital
        max_drawdown = 0.0

        for trade in self.trade_logs:
            capital += float(trade.profit_loss)
            if capital > peak:
                peak = capital
            drawdown = (peak - capital) / peak
            max_drawdown = max(max_drawdown, drawdown)

        # Calculate Sharpe ratio (simplified)
        returns = [float(t.profit_loss_pct) for t in self.trade_logs]
        if returns:
            avg_return = sum(returns) / len(returns)
            std_return = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5
            sharpe_ratio = (avg_return / std_return * (252**0.5)) if std_return > 0 else 0.0
        else:
            sharpe_ratio = 0.0

        return {
            "total_trades": len(self.trade_logs),
            "win_rate": len(wins) / len(self.trade_logs) * 100 if self.trade_logs else 0.0,
            "profit_factor": profit_factor,
            "total_profit": sum(float(t.profit_loss) for t in self.trade_logs),
            "avg_win": total_win / len(wins) if wins else 0.0,
            "avg_loss": total_loss / len(losses) if losses else 0.0,
            "max_drawdown": max_drawdown * 100,
            "sharpe_ratio": sharpe_ratio,
            "avg_duration_hours": (
                sum(t.duration_seconds for t in self.trade_logs) / len(self.trade_logs) / 3600
            ),
        }

    def export_to_csv(self, output_path: str) -> None:
        """Export trade logs to CSV file"""
        import csv

        if not self.trade_logs:
            logger.warning("No trades to export")
            return

        try:
            with open(output_path, "w", newline="") as f:
                # Get field names from first trade
                fieldnames = list(asdict(self.trade_logs[0]).keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)

                writer.writeheader()
                for trade in self.trade_logs:
                    row = asdict(trade)
                    # Convert Decimal and datetime for CSV
                    for key, value in row.items():
                        if isinstance(value, Decimal):
                            row[key] = float(value)
                        elif isinstance(value, datetime):
                            row[key] = value.isoformat()
                    writer.writerow(row)

            logger.info("Trade logs exported to CSV", path=output_path, count=len(self.trade_logs))

        except Exception as e:
            logger.error("Failed to export trade logs", error=str(e))
