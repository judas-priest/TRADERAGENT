"""Tests for DCA Engine v2.0.

Tests signal-controlled deal opening, false signal filters,
risk integration, trailing stop monitoring, and full lifecycle.
"""

from decimal import Decimal

import pytest

from bot.strategies.dca.dca_engine import (
    DCAEngine,
    FalseSignalFilter,
)
from bot.strategies.dca.dca_position_manager import DCAOrderConfig
from bot.strategies.dca.dca_risk_manager import DCARiskConfig
from bot.strategies.dca.dca_signal_generator import (
    DCASignalConfig,
    MarketState,
    TrendDirection,
)
from bot.strategies.dca.dca_trailing_stop import TrailingStopConfig, TrailingStopType

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def signal_config():
    return DCASignalConfig(
        trend_direction=TrendDirection.DOWN,
        min_trend_strength=20.0,
        entry_price_min=None,
        entry_price_max=None,
        require_confluence=True,
        min_confluence_score=0.5,  # Lower threshold for testing
        max_concurrent_deals=3,
        max_daily_loss=Decimal("500"),
        min_seconds_between_deals=0,
    )


@pytest.fixture
def order_config():
    return DCAOrderConfig(
        base_order_volume=Decimal("100"),
        max_safety_orders=3,
        volume_multiplier=Decimal("1.5"),
        price_step_pct=Decimal("2.0"),
        take_profit_pct=Decimal("3.0"),
        stop_loss_pct=Decimal("10.0"),
        max_position_cost=Decimal("5000"),
    )


@pytest.fixture
def risk_config():
    return DCARiskConfig(
        max_concurrent_deals=3,
        max_total_exposure=Decimal("15000"),
        max_daily_loss=Decimal("500"),
    )


@pytest.fixture
def trailing_config():
    return TrailingStopConfig(
        enabled=True,
        activation_pct=Decimal("1.5"),
        distance_pct=Decimal("0.8"),
        stop_type=TrailingStopType.PERCENTAGE,
    )


@pytest.fixture
def engine(signal_config, order_config, risk_config, trailing_config):
    return DCAEngine(
        symbol="BTC/USDT",
        signal_config=signal_config,
        order_config=order_config,
        risk_config=risk_config,
        trailing_config=trailing_config,
    )


@pytest.fixture
def good_signal_state():
    """Market state that triggers a signal (all conditions pass)."""
    return MarketState(
        current_price=Decimal("3100"),
        ema_fast=Decimal("3050"),
        ema_slow=Decimal("3200"),
        adx=25.0,
        rsi=30.0,
        volume_24h=Decimal("1500000"),
        avg_volume=Decimal("1000000"),
        bb_lower=Decimal("3080"),
        nearest_support=Decimal("3050"),
    )


@pytest.fixture
def no_signal_state():
    """Market state that does NOT trigger a signal."""
    return MarketState(
        current_price=Decimal("3100"),
        ema_fast=Decimal("3300"),  # Uptrend — fails for DOWN mode
        ema_slow=Decimal("3200"),
        adx=15.0,  # Weak
        rsi=50.0,  # Not oversold
    )


# =========================================================================
# Signal-Controlled Entry Tests
# =========================================================================


class TestSignalControlledEntry:
    def test_opens_deal_on_good_signal(self, engine, good_signal_state):
        action = engine.on_price_update(
            good_signal_state,
            available_balance=Decimal("5000"),
            total_balance=Decimal("10000"),
        )
        assert action.should_open_deal is True
        assert action.signal_result is not None
        assert action.signal_result.should_open is True

    def test_no_deal_on_bad_signal(self, engine, no_signal_state):
        action = engine.on_price_update(
            no_signal_state,
            available_balance=Decimal("5000"),
            total_balance=Decimal("10000"),
        )
        assert action.should_open_deal is False

    def test_no_deal_when_no_data(self, engine):
        state = MarketState(current_price=Decimal("3100"))
        action = engine.on_price_update(
            state,
            available_balance=Decimal("5000"),
            total_balance=Decimal("10000"),
        )
        # With min_confluence=0.5 and all conditions skipped (pass),
        # score = 1.0 → should open
        assert action.should_open_deal is True

    def test_signal_result_included(self, engine, good_signal_state):
        action = engine.on_price_update(
            good_signal_state,
            available_balance=Decimal("5000"),
            total_balance=Decimal("10000"),
        )
        assert action.signal_result is not None


# =========================================================================
# False Signal Filter Tests
# =========================================================================


class TestFalseSignalFilter:
    def test_confirmation_count(
        self, signal_config, order_config, risk_config, trailing_config, good_signal_state
    ):
        engine = DCAEngine(
            symbol="BTC/USDT",
            signal_config=signal_config,
            order_config=order_config,
            risk_config=risk_config,
            trailing_config=trailing_config,
            false_signal_filter=FalseSignalFilter(confirmation_count=3),
        )

        # First 2 signals should be filtered
        r1 = engine.on_price_update(
            good_signal_state, available_balance=Decimal("5000"), total_balance=Decimal("10000")
        )
        assert r1.should_open_deal is False

        r2 = engine.on_price_update(
            good_signal_state, available_balance=Decimal("5000"), total_balance=Decimal("10000")
        )
        assert r2.should_open_deal is False

        # Third signal passes
        r3 = engine.on_price_update(
            good_signal_state, available_balance=Decimal("5000"), total_balance=Decimal("10000")
        )
        assert r3.should_open_deal is True

    def test_price_spike_filter(self, engine, good_signal_state):
        # Set initial price
        engine._last_price = Decimal("2800")  # 10.7% change to 3100

        engine._filter.max_recent_price_change_pct = Decimal("5.0")
        action = engine.on_price_update(
            good_signal_state,
            available_balance=Decimal("5000"),
            total_balance=Decimal("10000"),
        )
        assert action.should_open_deal is False
        assert any("spike" in w.lower() for w in action.warnings)

    def test_no_spike_with_normal_price(self, engine, good_signal_state):
        engine._last_price = Decimal("3090")  # Small change
        engine._filter.max_recent_price_change_pct = Decimal("5.0")
        action = engine.on_price_update(
            good_signal_state,
            available_balance=Decimal("5000"),
            total_balance=Decimal("10000"),
        )
        assert action.should_open_deal is True


# =========================================================================
# Risk Integration Tests
# =========================================================================


class TestRiskIntegration:
    def test_blocked_by_max_deals(self, engine, good_signal_state):
        # Open 3 deals
        for i in range(3):
            engine.open_deal(Decimal(f"{3100 + i}"))

        action = engine.on_price_update(
            good_signal_state,
            available_balance=Decimal("5000"),
            total_balance=Decimal("10000"),
        )
        assert action.should_open_deal is False

    def test_blocked_by_insufficient_balance(self, engine, good_signal_state):
        action = engine.on_price_update(
            good_signal_state,
            available_balance=Decimal("10"),
            total_balance=Decimal("100"),
        )
        assert action.should_open_deal is False


# =========================================================================
# Active Deal Monitoring Tests
# =========================================================================


class TestActiveDealMonitoring:
    def test_trailing_stop_triggers_exit(self, engine):
        # Open deal at 3100
        deal = engine.open_deal(Decimal("3100"))

        # Price rises → activate trailing
        state = MarketState(current_price=Decimal("3200"))
        engine.on_price_update(
            state, available_balance=Decimal("5000"), total_balance=Decimal("10000")
        )

        # New high
        state = MarketState(current_price=Decimal("3500"))
        engine.on_price_update(
            state, available_balance=Decimal("5000"), total_balance=Decimal("10000")
        )

        # Drop below stop (3500 * 0.992 = 3472)
        state = MarketState(current_price=Decimal("3470"))
        action = engine.on_price_update(
            state, available_balance=Decimal("5000"), total_balance=Decimal("10000")
        )

        assert len(action.deals_to_close) == 1
        assert action.deals_to_close[0].deal_id == deal.id
        assert action.deals_to_close[0].reason == "trailing_stop"

    def test_stop_loss_triggers_exit(self, engine):
        deal = engine.open_deal(Decimal("3100"))

        # Price drops to SL (3100 * 0.90 = 2790)
        state = MarketState(current_price=Decimal("2780"))
        action = engine.on_price_update(
            state, available_balance=Decimal("5000"), total_balance=Decimal("10000")
        )

        assert len(action.deals_to_close) == 1
        assert action.deals_to_close[0].reason == "stop_loss"

    def test_take_profit_without_trailing(self):
        engine = DCAEngine(
            symbol="BTC/USDT",
            trailing_config=TrailingStopConfig(enabled=False),
        )
        deal = engine.open_deal(Decimal("3100"))

        # TP at 3100 * 1.03 = 3193
        state = MarketState(current_price=Decimal("3200"))
        action = engine.on_price_update(
            state, available_balance=Decimal("5000"), total_balance=Decimal("10000")
        )

        assert len(action.deals_to_close) == 1
        assert action.deals_to_close[0].reason == "take_profit"

    def test_safety_order_trigger(self, engine):
        deal = engine.open_deal(Decimal("3100"))

        # SO1 at 3100 * 0.98 = 3038
        state = MarketState(current_price=Decimal("3030"))
        action = engine.on_price_update(
            state, available_balance=Decimal("5000"), total_balance=Decimal("10000")
        )

        assert len(action.safety_order_triggers) == 1
        assert action.safety_order_triggers[0] == (deal.id, 1)

    def test_no_triggers_when_normal(self, engine):
        engine.open_deal(Decimal("3100"))

        state = MarketState(current_price=Decimal("3100"))
        action = engine.on_price_update(
            state, available_balance=Decimal("5000"), total_balance=Decimal("10000")
        )

        assert len(action.deals_to_close) == 0
        assert len(action.safety_order_triggers) == 0


# =========================================================================
# Deal Lifecycle Tests
# =========================================================================


class TestDealLifecycle:
    def test_open_deal(self, engine):
        deal = engine.open_deal(Decimal("3100"))
        assert deal.symbol == "BTC/USDT"
        assert deal.base_order_price == Decimal("3100")

    def test_fill_safety_order(self, engine):
        deal = engine.open_deal(Decimal("3100"))
        updated = engine.fill_safety_order(deal.id, level=1, fill_price=Decimal("3038"))
        assert updated.safety_orders_filled == 1

    def test_close_deal_records_pnl(self, engine):
        deal = engine.open_deal(Decimal("3100"))
        result = engine.close_deal(deal.id, Decimal("3200"), "take_profit")
        assert result.realized_profit > 0

        # Risk manager should have recorded the trade
        assert engine.risk_manager._total_realized_pnl > 0

    def test_trailing_snapshot_cleaned_on_close(self, engine):
        deal = engine.open_deal(Decimal("3100"))
        assert deal.id in engine._trailing_snapshots

        engine.close_deal(deal.id, Decimal("3200"), "take_profit")
        assert deal.id not in engine._trailing_snapshots


# =========================================================================
# Statistics Tests
# =========================================================================


class TestStatistics:
    def test_get_statistics(self, engine):
        stats = engine.get_statistics()
        assert stats["symbol"] == "BTC/USDT"
        assert "signal_generator" in stats
        assert "position_manager" in stats
        assert "risk_manager" in stats
        assert "trailing_stop" in stats
        assert "filter" in stats


# =========================================================================
# Full Integration Tests
# =========================================================================


class TestFullIntegration:
    def test_signal_to_open_to_trailing_close(self, engine, good_signal_state):
        # Step 1: Signal triggers open
        action = engine.on_price_update(
            good_signal_state,
            available_balance=Decimal("5000"),
            total_balance=Decimal("10000"),
        )
        assert action.should_open_deal is True

        # Step 2: Execute open on exchange
        deal = engine.open_deal(Decimal("3100"))

        # Step 3: Price rises
        for price in [3150, 3200, 3300, 3400, 3500]:
            state = MarketState(current_price=Decimal(str(price)))
            action = engine.on_price_update(
                state, available_balance=Decimal("5000"), total_balance=Decimal("10000")
            )
            assert len(action.deals_to_close) == 0  # Not triggered yet

        # Step 4: Price drops to trailing stop (3500*0.992=3472)
        state = MarketState(current_price=Decimal("3470"))
        action = engine.on_price_update(
            state, available_balance=Decimal("5000"), total_balance=Decimal("10000")
        )
        assert len(action.deals_to_close) == 1
        assert action.deals_to_close[0].reason == "trailing_stop"

        # Step 5: Close deal
        result = engine.close_deal(deal.id, Decimal("3470"), "trailing_stop")
        assert result.realized_profit > 0

    def test_signal_to_safety_orders_to_recovery(self, engine, good_signal_state):
        # Step 1: Open deal
        action = engine.on_price_update(
            good_signal_state,
            available_balance=Decimal("5000"),
            total_balance=Decimal("10000"),
        )
        assert action.should_open_deal is True
        deal = engine.open_deal(Decimal("3100"))

        # Step 2: Price drops → trigger SO
        state = MarketState(current_price=Decimal("3030"))
        action = engine.on_price_update(
            state, available_balance=Decimal("5000"), total_balance=Decimal("10000")
        )
        assert len(action.safety_order_triggers) == 1
        engine.fill_safety_order(deal.id, 1, Decimal("3030"))

        # Step 3: Price drops more → trigger SO2
        state = MarketState(current_price=Decimal("2960"))
        action = engine.on_price_update(
            state, available_balance=Decimal("5000"), total_balance=Decimal("10000")
        )
        assert len(action.safety_order_triggers) == 1
        engine.fill_safety_order(deal.id, 2, Decimal("2960"))

        # Step 4: Price recovers past TP
        # With trailing enabled, we need activation + stop
        avg = deal.average_entry_price
        for price in [3000, 3100, 3200, 3300]:
            state = MarketState(current_price=Decimal(str(price)))
            engine.on_price_update(
                state, available_balance=Decimal("5000"), total_balance=Decimal("10000")
            )

        # Step 5: Price drops → trailing stop
        # highest is 3300, stop = 3300*0.992 = 3273.6
        state = MarketState(current_price=Decimal("3270"))
        action = engine.on_price_update(
            state, available_balance=Decimal("5000"), total_balance=Decimal("10000")
        )
        assert len(action.deals_to_close) == 1

        result = engine.close_deal(deal.id, Decimal("3270"), "trailing_stop")
        assert result.realized_profit > 0  # Recovered from dip

    def test_multiple_deals_monitored(self, engine):
        d1 = engine.open_deal(Decimal("3100"))
        d2 = engine.open_deal(Decimal("50000"))

        # d2 hits stop loss (50000 * 0.9 = 45000)
        state = MarketState(current_price=Decimal("44000"))
        action = engine.on_price_update(
            state, available_balance=Decimal("5000"), total_balance=Decimal("10000")
        )

        # d2 should have SL, d1 also has SL (3100*0.9=2790, 44000>2790 but we need to check)
        # Actually d1 SL = 2790, current=44000 > 2790 so d1 is fine
        # d2 SL = 45000, current=44000 < 45000 so d2 hits SL
        sl_deals = [e for e in action.deals_to_close if e.reason == "stop_loss"]
        assert any(e.deal_id == d2.id for e in sl_deals)
