"""Unit tests for Position Manager"""

import unittest
from decimal import Decimal
from datetime import datetime
import pandas as pd

from bot.strategies.smc.position_manager import (
    PositionManager, PositionMetrics, PositionStatus, PerformanceStats
)
from bot.strategies.smc.market_structure import MarketStructureAnalyzer
from bot.strategies.smc.entry_signals import SMCSignal, SignalDirection, PriceActionPattern, PatternType


class TestPositionManager(unittest.TestCase):
    def setUp(self):
        self.ms = MarketStructureAnalyzer()
        self.pm = PositionManager(
            market_structure=self.ms,
            account_balance=Decimal("10000"),
            risk_per_trade_pct=2.0
        )
    
    def _create_test_signal(self, direction=SignalDirection.LONG):
        pattern = PriceActionPattern(
            pattern_type=PatternType.ENGULFING,
            is_bullish=(direction == SignalDirection.LONG),
            index=10,
            timestamp=pd.Timestamp.now(),
            open=Decimal("100"),
            high=Decimal("102"),
            low=Decimal("98"),
            close=Decimal("101")
        )
        
        return SMCSignal(
            timestamp=pd.Timestamp.now(),
            direction=direction,
            entry_price=Decimal("100"),
            stop_loss=Decimal("95") if direction == SignalDirection.LONG else Decimal("105"),
            take_profit=Decimal("112.5") if direction == SignalDirection.LONG else Decimal("87.5"),
            pattern=pattern,
            confidence=0.75,
            risk_reward_ratio=2.5
        )
    
    def test_position_size_calculation(self):
        signal = self._create_test_signal()
        size = self.pm.calculate_position_size(signal)
        
        self.assertGreater(size, 0)
        self.assertIsInstance(size, Decimal)
    
    def test_kelly_criterion(self):
        # Populate performance stats
        self.pm.performance_stats.total_trades = 20
        self.pm.performance_stats.winning_trades = 12
        self.pm.performance_stats.avg_win = Decimal("100")
        self.pm.performance_stats.avg_loss = Decimal("50")
        self.pm.performance_stats.win_rate = 0.6
        
        kelly_pct = self.pm._calculate_kelly_percentage()
        
        self.assertGreater(kelly_pct, 0)
        self.assertLess(kelly_pct, 10)
    
    def test_open_position(self):
        signal = self._create_test_signal()
        size = Decimal("1.0")
        
        position = self.pm.open_position(signal, size, "test_1")
        
        self.assertEqual(position.status, PositionStatus.OPEN)
        self.assertEqual(position.entry_price, signal.entry_price)
        self.assertIn("test_1", self.pm.open_positions)
    
    def test_breakeven_move(self):
        signal = self._create_test_signal()
        size = Decimal("1.0")
        
        position = self.pm.open_position(signal, size, "test_1")
        
        # Move price to 1:1 RR
        risk = abs(signal.entry_price - signal.stop_loss)
        new_price = signal.entry_price + risk
        
        self.pm.update_position("test_1", new_price)
        
        updated_pos = self.pm.open_positions["test_1"]
        self.assertEqual(updated_pos.status, PositionStatus.BREAKEVEN)
    
    def test_close_position(self):
        signal = self._create_test_signal()
        size = Decimal("1.0")
        
        self.pm.open_position(signal, size, "test_1")
        closed_pos = self.pm.close_position("test_1", signal.take_profit, "take_profit")
        
        self.assertEqual(closed_pos.status, PositionStatus.CLOSED)
        self.assertGreater(closed_pos.realized_pnl, 0)
        self.assertNotIn("test_1", self.pm.open_positions)
    
    def test_risk_validation(self):
        signal = self._create_test_signal()
        size = Decimal("1.0")
        
        is_valid, reason = self.pm.validate_position_risk(signal, size)
        
        self.assertTrue(is_valid)
        self.assertEqual(reason, "")
    
    def test_risk_validation_fails_rr(self):
        signal = self._create_test_signal()
        signal.risk_reward_ratio = 1.0  # Below minimum
        size = Decimal("1.0")
        
        is_valid, reason = self.pm.validate_position_risk(signal, size)
        
        self.assertFalse(is_valid)
        self.assertIn("RR ratio", reason)
    
    def test_performance_stats_update(self):
        position = PositionMetrics(
            entry_price=Decimal("100"),
            current_price=Decimal("110"),
            stop_loss=Decimal("95"),
            take_profit=Decimal("110"),
            position_size=Decimal("1.0"),
            realized_pnl=Decimal("10"),
            status=PositionStatus.CLOSED
        )
        
        stats = PerformanceStats()
        stats.update_from_position(position)
        
        self.assertEqual(stats.total_trades, 1)
        self.assertEqual(stats.winning_trades, 1)
        self.assertEqual(stats.win_rate, 1.0)


if __name__ == "__main__":
    unittest.main()
