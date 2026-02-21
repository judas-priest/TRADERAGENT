"""Tests for BaseStrategy ABC, unified types, and strategy adapters."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import numpy as np
import pandas as pd
import pytest

from bot.strategies.base import (
    BaseMarketAnalysis,
    BaseSignal,
    BaseStrategy,
    ExitReason,
    PositionInfo,
    SignalDirection,
    StrategyPerformance,
)

# =========================================================================
# Helpers
# =========================================================================


def _make_ohlcv(close_prices: list[float], spread: float = 0.02) -> pd.DataFrame:
    """Build OHLCV DataFrame from close prices."""
    n = len(close_prices)
    close = np.array(close_prices, dtype=float)
    high = close * (1 + spread)
    low = close * (1 - spread)
    open_ = (close + np.roll(close, 1)) / 2
    open_[0] = close[0]
    volume = np.random.uniform(1000, 5000, n)
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=n, freq="1h"),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


class ConcreteStrategy(BaseStrategy):
    """Minimal concrete implementation for testing the ABC."""

    def __init__(self):
        self._positions: dict[str, dict] = {}
        self._trades: list[dict] = []

    def get_strategy_name(self) -> str:
        return "test-concrete"

    def get_strategy_type(self) -> str:
        return "test"

    def analyze_market(self, *dfs: pd.DataFrame) -> BaseMarketAnalysis:
        return BaseMarketAnalysis(
            trend="bullish",
            trend_strength=0.8,
            volatility=0.05,
            timestamp=datetime.now(timezone.utc),
            strategy_type="test",
        )

    def generate_signal(self, df: pd.DataFrame, current_balance: Decimal) -> Optional[BaseSignal]:
        if len(df) < 5:
            return None
        return BaseSignal(
            direction=SignalDirection.LONG,
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            take_profit=Decimal("110"),
            confidence=0.75,
            timestamp=datetime.now(timezone.utc),
            strategy_type="test",
            signal_reason="test_signal",
            risk_reward_ratio=2.0,
        )

    def open_position(self, signal: BaseSignal, position_size: Decimal) -> str:
        pos_id = f"test-{len(self._positions)}"
        self._positions[pos_id] = {
            "signal": signal,
            "size": position_size,
            "entry_price": signal.entry_price,
            "current_price": signal.entry_price,
        }
        return pos_id

    def update_positions(
        self, current_price: Decimal, df: pd.DataFrame
    ) -> list[tuple[str, ExitReason]]:
        exits = []
        for pos_id, pos in list(self._positions.items()):
            pos["current_price"] = current_price
            if current_price >= pos["signal"].take_profit:
                exits.append((pos_id, ExitReason.TAKE_PROFIT))
            elif current_price <= pos["signal"].stop_loss:
                exits.append((pos_id, ExitReason.STOP_LOSS))
        return exits

    def close_position(
        self, position_id: str, exit_reason: ExitReason, exit_price: Decimal
    ) -> None:
        pos = self._positions.pop(position_id, None)
        if pos:
            self._trades.append(
                {
                    "id": position_id,
                    "reason": exit_reason,
                    "exit_price": exit_price,
                }
            )

    def get_active_positions(self) -> list[PositionInfo]:
        result = []
        for pos_id, pos in self._positions.items():
            result.append(
                PositionInfo(
                    position_id=pos_id,
                    direction=pos["signal"].direction,
                    entry_price=pos["entry_price"],
                    current_price=pos["current_price"],
                    size=pos["size"],
                    stop_loss=pos["signal"].stop_loss,
                    take_profit=pos["signal"].take_profit,
                    unrealized_pnl=Decimal("0"),
                    entry_time=datetime.now(timezone.utc),
                    strategy_type="test",
                )
            )
        return result

    def get_performance(self) -> StrategyPerformance:
        return StrategyPerformance(total_trades=len(self._trades))


# =========================================================================
# SignalDirection Tests
# =========================================================================


class TestSignalDirection:
    def test_values(self):
        assert SignalDirection.LONG.value == "long"
        assert SignalDirection.SHORT.value == "short"

    def test_is_str_enum(self):
        assert isinstance(SignalDirection.LONG, str)
        assert SignalDirection.LONG == "long"


# =========================================================================
# ExitReason Tests
# =========================================================================


class TestExitReason:
    def test_all_values(self):
        expected = {
            "take_profit",
            "stop_loss",
            "trailing_stop",
            "breakeven",
            "partial_close",
            "manual",
            "signal_reversed",
            "risk_limit",
            "timeout",
        }
        actual = {e.value for e in ExitReason}
        assert actual == expected

    def test_is_str_enum(self):
        assert isinstance(ExitReason.TAKE_PROFIT, str)


# =========================================================================
# BaseSignal Tests
# =========================================================================


class TestBaseSignal:
    def _make_signal(self, direction=SignalDirection.LONG) -> BaseSignal:
        return BaseSignal(
            direction=direction,
            entry_price=Decimal("100"),
            stop_loss=Decimal("95") if direction == SignalDirection.LONG else Decimal("105"),
            take_profit=Decimal("110") if direction == SignalDirection.LONG else Decimal("90"),
            confidence=0.8,
            timestamp=datetime.now(timezone.utc),
            strategy_type="test",
            signal_reason="test",
            risk_reward_ratio=2.0,
        )

    def test_long_risk_amount(self):
        sig = self._make_signal(SignalDirection.LONG)
        assert sig.risk_amount == Decimal("5")

    def test_long_reward_amount(self):
        sig = self._make_signal(SignalDirection.LONG)
        assert sig.reward_amount == Decimal("10")

    def test_short_risk_amount(self):
        sig = self._make_signal(SignalDirection.SHORT)
        assert sig.risk_amount == Decimal("5")

    def test_short_reward_amount(self):
        sig = self._make_signal(SignalDirection.SHORT)
        assert sig.reward_amount == Decimal("10")

    def test_to_dict(self):
        sig = self._make_signal()
        d = sig.to_dict()
        assert d["direction"] == "long"
        assert d["entry_price"] == "100"
        assert d["stop_loss"] == "95"
        assert d["take_profit"] == "110"
        assert d["confidence"] == 0.8
        assert d["strategy_type"] == "test"
        assert "timestamp" in d

    def test_metadata_default_empty(self):
        sig = self._make_signal()
        assert sig.metadata == {}

    def test_metadata_custom(self):
        sig = BaseSignal(
            direction=SignalDirection.LONG,
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            take_profit=Decimal("110"),
            confidence=0.7,
            timestamp=datetime.now(timezone.utc),
            strategy_type="test",
            metadata={"key": "value"},
        )
        assert sig.metadata == {"key": "value"}


# =========================================================================
# BaseMarketAnalysis Tests
# =========================================================================


class TestBaseMarketAnalysis:
    def test_creation(self):
        analysis = BaseMarketAnalysis(
            trend="bullish",
            trend_strength=0.8,
            volatility=0.05,
            timestamp=datetime.now(timezone.utc),
            strategy_type="test",
        )
        assert analysis.trend == "bullish"
        assert analysis.trend_strength == 0.8

    def test_to_dict(self):
        analysis = BaseMarketAnalysis(
            trend="sideways",
            trend_strength=0.3,
            volatility=0.02,
            timestamp=datetime.now(timezone.utc),
            strategy_type="smc",
            details={"rsi": 50},
        )
        d = analysis.to_dict()
        assert d["trend"] == "sideways"
        assert d["details"]["rsi"] == 50


# =========================================================================
# PositionInfo Tests
# =========================================================================


class TestPositionInfo:
    def test_creation(self):
        pos = PositionInfo(
            position_id="pos-1",
            direction=SignalDirection.LONG,
            entry_price=Decimal("100"),
            current_price=Decimal("105"),
            size=Decimal("10"),
            stop_loss=Decimal("95"),
            take_profit=Decimal("110"),
            unrealized_pnl=Decimal("50"),
            entry_time=datetime.now(timezone.utc),
            strategy_type="test",
        )
        assert pos.position_id == "pos-1"
        assert pos.direction == SignalDirection.LONG


# =========================================================================
# StrategyPerformance Tests
# =========================================================================


class TestStrategyPerformance:
    def test_defaults(self):
        perf = StrategyPerformance()
        assert perf.total_trades == 0
        assert perf.win_rate == 0.0
        assert perf.total_pnl == Decimal("0")

    def test_to_dict(self):
        perf = StrategyPerformance(
            total_trades=10,
            winning_trades=7,
            losing_trades=3,
            win_rate=0.7,
            total_pnl=Decimal("500"),
            profit_factor=2.5,
        )
        d = perf.to_dict()
        assert d["total_trades"] == 10
        assert d["win_rate"] == 0.7
        assert d["total_pnl"] == "500"


# =========================================================================
# ConcreteStrategy (BaseStrategy ABC) Tests
# =========================================================================


class TestBaseStrategyInterface:
    """Test BaseStrategy ABC via ConcreteStrategy."""

    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            BaseStrategy()

    def test_strategy_name_and_type(self):
        s = ConcreteStrategy()
        assert s.get_strategy_name() == "test-concrete"
        assert s.get_strategy_type() == "test"

    def test_analyze_market(self):
        s = ConcreteStrategy()
        df = _make_ohlcv([100, 101, 102])
        result = s.analyze_market(df)
        assert isinstance(result, BaseMarketAnalysis)
        assert result.trend == "bullish"

    def test_generate_signal_none(self):
        s = ConcreteStrategy()
        df = _make_ohlcv([100, 101])
        assert s.generate_signal(df, Decimal("1000")) is None

    def test_generate_signal_valid(self):
        s = ConcreteStrategy()
        df = _make_ohlcv([100, 101, 102, 103, 104, 105])
        sig = s.generate_signal(df, Decimal("1000"))
        assert sig is not None
        assert isinstance(sig, BaseSignal)
        assert sig.direction == SignalDirection.LONG

    def test_open_and_close_position(self):
        s = ConcreteStrategy()
        df = _make_ohlcv([100, 101, 102, 103, 104, 105])
        sig = s.generate_signal(df, Decimal("1000"))
        pos_id = s.open_position(sig, Decimal("500"))
        assert pos_id == "test-0"

        positions = s.get_active_positions()
        assert len(positions) == 1
        assert positions[0].position_id == pos_id

        s.close_position(pos_id, ExitReason.TAKE_PROFIT, Decimal("110"))
        assert len(s.get_active_positions()) == 0

    def test_update_positions_take_profit(self):
        s = ConcreteStrategy()
        df = _make_ohlcv([100, 101, 102, 103, 104, 105])
        sig = s.generate_signal(df, Decimal("1000"))
        s.open_position(sig, Decimal("500"))

        exits = s.update_positions(Decimal("110"), df)
        assert len(exits) == 1
        assert exits[0][1] == ExitReason.TAKE_PROFIT

    def test_update_positions_stop_loss(self):
        s = ConcreteStrategy()
        df = _make_ohlcv([100, 101, 102, 103, 104, 105])
        sig = s.generate_signal(df, Decimal("1000"))
        s.open_position(sig, Decimal("500"))

        exits = s.update_positions(Decimal("90"), df)
        assert len(exits) == 1
        assert exits[0][1] == ExitReason.STOP_LOSS

    def test_get_performance(self):
        s = ConcreteStrategy()
        perf = s.get_performance()
        assert isinstance(perf, StrategyPerformance)
        assert perf.total_trades == 0

    def test_get_status(self):
        s = ConcreteStrategy()
        status = s.get_status()
        assert status["name"] == "test-concrete"
        assert status["type"] == "test"
        assert status["active_positions"] == 0
        assert "performance" in status

    def test_reset_default_noop(self):
        s = ConcreteStrategy()
        # Should not raise
        s.reset()

    def test_full_lifecycle(self):
        """Test complete signal → open → update → close lifecycle."""
        s = ConcreteStrategy()
        df = _make_ohlcv([100 + i for i in range(20)])

        # Analyze
        analysis = s.analyze_market(df)
        assert analysis.trend == "bullish"

        # Generate signal
        sig = s.generate_signal(df, Decimal("10000"))
        assert sig is not None

        # Open
        pos_id = s.open_position(sig, Decimal("1000"))
        assert len(s.get_active_positions()) == 1

        # Update - no exit
        exits = s.update_positions(Decimal("105"), df)
        assert len(exits) == 0

        # Update - TP hit
        exits = s.update_positions(Decimal("115"), df)
        assert len(exits) == 1

        # Close
        s.close_position(pos_id, exits[0][1], Decimal("115"))
        assert len(s.get_active_positions()) == 0
        assert s.get_performance().total_trades == 1
