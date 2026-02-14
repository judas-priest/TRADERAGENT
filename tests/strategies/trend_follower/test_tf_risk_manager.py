"""
Tests for Trend Follower RiskManager — position sizing, drawdown, daily limits.
"""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

import pandas as pd
import pytest

from bot.strategies.trend_follower.entry_logic import EntrySignal, SignalType
from bot.strategies.trend_follower.market_analyzer import (
    MarketConditions,
    MarketPhase,
    TrendStrength,
)
from bot.strategies.trend_follower.risk_manager import (
    RiskManager,
    RiskMetrics,
    TradeRecord,
)


def _make_conditions() -> MarketConditions:
    return MarketConditions(
        phase=MarketPhase.BULLISH_TREND,
        trend_strength=TrendStrength.STRONG,
        ema_fast=Decimal("45000"),
        ema_slow=Decimal("44500"),
        ema_divergence_pct=Decimal("0.01"),
        atr=Decimal("500"),
        atr_pct=Decimal("0.01"),
        rsi=Decimal("55"),
        current_price=Decimal("45000"),
        is_in_range=False,
        range_high=Decimal("46000"),
        range_low=Decimal("44000"),
        timestamp=pd.Timestamp("2024-01-01"),
    )


def _make_entry_signal(price: Decimal = Decimal("45000")) -> EntrySignal:
    return EntrySignal(
        signal_type=SignalType.LONG,
        entry_reason="trend_pullback_to_ema",
        entry_price=price,
        confidence=Decimal("0.8"),
        market_conditions=_make_conditions(),
        volume_confirmed=True,
        timestamp=pd.Timestamp("2024-01-01"),
    )


class TestRiskManagerInit:
    def test_defaults(self):
        rm = RiskManager(initial_capital=Decimal("10000"))
        assert rm.initial_capital == Decimal("10000")
        assert rm.risk_per_trade_pct == Decimal("0.01")
        assert rm.max_total_exposure_pct == Decimal("0.20")
        assert rm.max_positions == 20
        assert rm.consecutive_losses == 0
        assert rm.active_positions_count == 0

    def test_custom_params(self):
        rm = RiskManager(
            initial_capital=Decimal("50000"),
            risk_per_trade_pct=Decimal("0.02"),
            max_daily_loss_usd=Decimal("1000"),
        )
        assert rm.risk_per_trade_pct == Decimal("0.02")
        assert rm.max_daily_loss_usd == Decimal("1000")


class TestCheckCanTrade:
    def test_can_trade_basic(self):
        rm = RiskManager(initial_capital=Decimal("10000"))
        signal = _make_entry_signal()
        metrics = rm.check_can_trade(signal, Decimal("10000"))
        assert isinstance(metrics, RiskMetrics)
        assert metrics.can_trade is True
        assert metrics.max_position_size_allowed > 0

    def test_insufficient_balance(self):
        rm = RiskManager(initial_capital=Decimal("10000"))
        signal = _make_entry_signal()
        metrics = rm.check_can_trade(signal, Decimal("0"))
        assert metrics.can_trade is False
        assert "Insufficient balance" in metrics.rejection_reason

    def test_daily_loss_limit(self):
        rm = RiskManager(initial_capital=Decimal("10000"), max_daily_loss_usd=Decimal("100"))
        rm.daily_pnl = Decimal("-100")
        signal = _make_entry_signal()
        metrics = rm.check_can_trade(signal, Decimal("10000"))
        assert metrics.can_trade is False
        assert "Daily loss limit" in metrics.rejection_reason

    def test_max_positions_limit(self):
        rm = RiskManager(initial_capital=Decimal("10000"), max_positions=2)
        rm.active_positions_count = 2
        signal = _make_entry_signal()
        metrics = rm.check_can_trade(signal, Decimal("10000"))
        assert metrics.can_trade is False
        assert "Max positions" in metrics.rejection_reason

    def test_max_exposure_limit(self):
        rm = RiskManager(initial_capital=Decimal("10000"), max_total_exposure_pct=Decimal("0.20"))
        rm.active_positions_total_value = Decimal("2000")
        signal = _make_entry_signal()
        metrics = rm.check_can_trade(signal, Decimal("10000"))
        assert metrics.can_trade is False
        assert "exposure" in metrics.rejection_reason.lower()


class TestPositionSizing:
    def test_position_size_respects_risk_pct(self):
        rm = RiskManager(initial_capital=Decimal("10000"), risk_per_trade_pct=Decimal("0.01"))
        signal = _make_entry_signal()
        metrics = rm.check_can_trade(signal, Decimal("10000"))
        # Position size should not exceed max_position_size_usd
        assert metrics.max_position_size_allowed <= rm.max_position_size_usd

    def test_consecutive_loss_reduction(self):
        rm = RiskManager(
            initial_capital=Decimal("10000"),
            max_consecutive_losses=3,
            size_reduction_factor=Decimal("0.5"),
        )
        signal = _make_entry_signal()

        # Normal size
        normal_metrics = rm.check_can_trade(signal, Decimal("10000"))
        normal_size = normal_metrics.max_position_size_allowed

        # After 3 consecutive losses
        rm.consecutive_losses = 3
        reduced_metrics = rm.check_can_trade(signal, Decimal("10000"))
        reduced_size = reduced_metrics.max_position_size_allowed

        # Reduced size should be smaller
        assert reduced_size < normal_size


class TestRecordTrade:
    def test_record_winning_trade(self):
        rm = RiskManager(initial_capital=Decimal("10000"))
        rm.record_trade(
            signal_type=SignalType.LONG,
            entry_price=Decimal("45000"),
            exit_price=Decimal("46000"),
            size=Decimal("100"),
        )
        assert len(rm.trade_history) == 1
        assert rm.trade_history[0].is_win is True
        assert rm.consecutive_losses == 0
        assert rm.daily_pnl > 0

    def test_record_losing_trade(self):
        rm = RiskManager(initial_capital=Decimal("10000"))
        rm.record_trade(
            signal_type=SignalType.LONG,
            entry_price=Decimal("45000"),
            exit_price=Decimal("44000"),
            size=Decimal("100"),
        )
        assert rm.trade_history[0].is_win is False
        assert rm.consecutive_losses == 1
        assert rm.daily_pnl < 0

    def test_consecutive_losses_counting(self):
        rm = RiskManager(initial_capital=Decimal("10000"))
        for _ in range(3):
            rm.record_trade(
                signal_type=SignalType.LONG,
                entry_price=Decimal("45000"),
                exit_price=Decimal("44500"),
                size=Decimal("100"),
            )
        assert rm.consecutive_losses == 3

        # Win resets counter
        rm.record_trade(
            signal_type=SignalType.LONG,
            entry_price=Decimal("45000"),
            exit_price=Decimal("46000"),
            size=Decimal("100"),
        )
        assert rm.consecutive_losses == 0

    def test_short_trade_pnl(self):
        rm = RiskManager(initial_capital=Decimal("10000"))
        rm.record_trade(
            signal_type=SignalType.SHORT,
            entry_price=Decimal("45000"),
            exit_price=Decimal("44000"),
            size=Decimal("100"),
        )
        assert rm.trade_history[0].is_win is True
        assert rm.trade_history[0].profit_loss > 0


class TestPositionTracking:
    def test_position_opened(self):
        rm = RiskManager(initial_capital=Decimal("10000"))
        rm.position_opened(Decimal("500"))
        assert rm.active_positions_count == 1
        assert rm.active_positions_total_value == Decimal("500")

    def test_position_closed(self):
        rm = RiskManager(initial_capital=Decimal("10000"))
        rm.position_opened(Decimal("500"))
        rm.position_closed(Decimal("500"))
        assert rm.active_positions_count == 0
        assert rm.active_positions_total_value == Decimal("0")

    def test_multiple_positions(self):
        rm = RiskManager(initial_capital=Decimal("10000"))
        rm.position_opened(Decimal("300"))
        rm.position_opened(Decimal("200"))
        assert rm.active_positions_count == 2
        assert rm.active_positions_total_value == Decimal("500")

    def test_close_never_negative(self):
        rm = RiskManager(initial_capital=Decimal("10000"))
        rm.position_closed(Decimal("100"))
        assert rm.active_positions_count == 0
        assert rm.active_positions_total_value == Decimal("0")


class TestDailyMetrics:
    def test_new_day_resets(self):
        rm = RiskManager(initial_capital=Decimal("10000"))
        rm.daily_pnl = Decimal("-200")
        rm.daily_trades = 5
        rm.current_date = date(2023, 1, 1)  # Old date

        signal = _make_entry_signal()
        rm.check_can_trade(signal, Decimal("10000"))

        assert rm.daily_pnl == Decimal("0")
        assert rm.daily_trades == 0


class TestGetStatistics:
    def test_empty_stats(self):
        rm = RiskManager(initial_capital=Decimal("10000"))
        stats = rm.get_statistics()
        assert stats["total_trades"] == 0
        assert stats["win_rate"] == 0.0
        assert stats["current_capital"] == 10000.0

    def test_stats_with_trades(self):
        rm = RiskManager(initial_capital=Decimal("10000"))
        rm.record_trade(SignalType.LONG, Decimal("45000"), Decimal("46000"), Decimal("100"))
        rm.record_trade(SignalType.LONG, Decimal("45000"), Decimal("44000"), Decimal("100"))

        stats = rm.get_statistics()
        assert stats["total_trades"] == 2
        assert stats["win_rate"] == 50.0
        assert stats["profit_factor"] > 0

    def test_profit_factor_all_wins(self):
        rm = RiskManager(initial_capital=Decimal("10000"))
        rm.record_trade(SignalType.LONG, Decimal("45000"), Decimal("46000"), Decimal("100"))
        stats = rm.get_statistics()
        assert stats["profit_factor"] == float("inf")
