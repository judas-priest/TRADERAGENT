"""Tests for DCA Signal Generator v2.0.

Tests trend detection, price conditions, indicator conditions,
confluence scoring, risk/timing filters, and full evaluation.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from bot.strategies.dca.dca_signal_generator import (
    ConditionCategory,
    DCASignalConfig,
    DCASignalGenerator,
    MarketState,
    SignalResult,
    TrendDirection,
)

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def config():
    return DCASignalConfig(
        trend_direction=TrendDirection.DOWN,
        min_trend_strength=20.0,
        entry_price_min=Decimal("3000"),
        entry_price_max=Decimal("3200"),
        max_distance_from_support=Decimal("0.02"),
        rsi_oversold_threshold=35.0,
        min_volume_multiplier=Decimal("1.2"),
        bb_tolerance=Decimal("0.02"),
        require_confluence=True,
        min_confluence_score=0.75,
        max_concurrent_deals=3,
        max_daily_loss=Decimal("500"),
        min_seconds_between_deals=3600,
    )


@pytest.fixture
def generator(config):
    return DCASignalGenerator(config)


@pytest.fixture
def bullish_state():
    """Market state that passes all conditions for a DCA entry."""
    return MarketState(
        current_price=Decimal("3100"),
        ema_fast=Decimal("3050"),
        ema_slow=Decimal("3200"),
        adx=25.0,
        rsi=30.0,
        bb_lower=Decimal("3080"),
        volume_24h=Decimal("1500000"),
        avg_volume=Decimal("1000000"),
        nearest_support=Decimal("3050"),
        active_deals=1,
        daily_pnl=Decimal("-100"),
        available_balance=Decimal("5000"),
    )


# =========================================================================
# Config Validation Tests
# =========================================================================


class TestDCASignalConfig:
    def test_defaults(self):
        cfg = DCASignalConfig()
        cfg.validate()  # should not raise
        assert cfg.trend_direction == TrendDirection.DOWN
        assert cfg.min_trend_strength == 20.0
        assert cfg.require_confluence is True

    def test_invalid_trend_strength(self):
        cfg = DCASignalConfig(min_trend_strength=-1)
        with pytest.raises(ValueError, match="min_trend_strength"):
            cfg.validate()

    def test_invalid_rsi_threshold(self):
        cfg = DCASignalConfig(rsi_oversold_threshold=150)
        with pytest.raises(ValueError, match="rsi_oversold_threshold"):
            cfg.validate()

    def test_invalid_confluence_score(self):
        cfg = DCASignalConfig(min_confluence_score=1.5)
        with pytest.raises(ValueError, match="min_confluence_score"):
            cfg.validate()

    def test_invalid_concurrent_deals(self):
        cfg = DCASignalConfig(max_concurrent_deals=-1)
        with pytest.raises(ValueError, match="max_concurrent_deals"):
            cfg.validate()

    def test_invalid_cooldown(self):
        cfg = DCASignalConfig(min_seconds_between_deals=-1)
        with pytest.raises(ValueError, match="min_seconds_between_deals"):
            cfg.validate()

    def test_invalid_price_range(self):
        cfg = DCASignalConfig(
            entry_price_min=Decimal("5000"),
            entry_price_max=Decimal("3000"),
        )
        with pytest.raises(ValueError, match="entry_price_min"):
            cfg.validate()

    def test_zero_total_weight(self):
        cfg = DCASignalConfig(
            weight_trend=0,
            weight_price=0,
            weight_indicator=0,
            weight_risk=0,
            weight_timing=0,
        )
        with pytest.raises(ValueError, match="Total weight"):
            cfg.validate()


# =========================================================================
# Trend Condition Tests
# =========================================================================


class TestTrendCondition:
    def test_downtrend_detected(self, generator):
        state = MarketState(
            current_price=Decimal("3100"),
            ema_fast=Decimal("3050"),
            ema_slow=Decimal("3200"),
            adx=25.0,
        )
        result = generator.check_trend(state)
        assert result.passed is True
        assert result.category == ConditionCategory.TREND

    def test_uptrend_rejected_in_down_mode(self, generator):
        state = MarketState(
            current_price=Decimal("3100"),
            ema_fast=Decimal("3300"),
            ema_slow=Decimal("3200"),
            adx=25.0,
        )
        result = generator.check_trend(state)
        assert result.passed is False

    def test_uptrend_accepted_in_up_mode(self):
        cfg = DCASignalConfig(trend_direction=TrendDirection.UP)
        gen = DCASignalGenerator(cfg)
        state = MarketState(
            current_price=Decimal("3100"),
            ema_fast=Decimal("3300"),
            ema_slow=Decimal("3200"),
            adx=25.0,
        )
        result = gen.check_trend(state)
        assert result.passed is True

    def test_weak_adx_fails(self, generator):
        state = MarketState(
            current_price=Decimal("3100"),
            ema_fast=Decimal("3050"),
            ema_slow=Decimal("3200"),
            adx=15.0,  # Below 20
        )
        result = generator.check_trend(state)
        assert result.passed is False

    def test_no_ema_data_skipped(self, generator):
        state = MarketState(
            current_price=Decimal("3100"),
            adx=25.0,
        )
        result = generator.check_trend(state)
        assert result.passed is True  # No EMA data — skipped, ADX passes
        assert "skipped" in result.detail

    def test_no_adx_data_skipped(self, generator):
        state = MarketState(
            current_price=Decimal("3100"),
            ema_fast=Decimal("3050"),
            ema_slow=Decimal("3200"),
        )
        result = generator.check_trend(state)
        assert result.passed is True  # No ADX — skipped, EMA passes
        assert "skipped" in result.detail

    def test_no_trend_data_at_all(self, generator):
        state = MarketState(current_price=Decimal("3100"))
        result = generator.check_trend(state)
        assert result.passed is True  # All skipped
        assert result.weight == 3

    def test_trend_weight(self, generator):
        state = MarketState(current_price=Decimal("3100"))
        result = generator.check_trend(state)
        assert result.weight == 3


# =========================================================================
# Price Condition Tests
# =========================================================================


class TestPriceCondition:
    def test_price_in_range(self, generator):
        state = MarketState(
            current_price=Decimal("3100"),
            nearest_support=Decimal("3050"),
        )
        result = generator.check_price(state)
        assert result.passed is True

    def test_price_below_range(self, generator):
        state = MarketState(
            current_price=Decimal("2900"),
            nearest_support=Decimal("2850"),
        )
        result = generator.check_price(state)
        assert result.passed is False
        assert "outside range" in result.detail

    def test_price_above_range(self, generator):
        state = MarketState(
            current_price=Decimal("3500"),
            nearest_support=Decimal("3450"),
        )
        result = generator.check_price(state)
        assert result.passed is False

    def test_too_far_from_support(self, generator):
        state = MarketState(
            current_price=Decimal("3100"),
            nearest_support=Decimal("2900"),  # ~6.9% away > 2%
        )
        result = generator.check_price(state)
        assert result.passed is False
        assert "Too far from support" in result.detail

    def test_no_price_range_configured(self):
        cfg = DCASignalConfig(entry_price_min=None, entry_price_max=None)
        gen = DCASignalGenerator(cfg)
        state = MarketState(
            current_price=Decimal("3100"),
            nearest_support=Decimal("3050"),
        )
        result = gen.check_price(state)
        assert result.passed is True  # Range skipped, near support passes

    def test_no_support_data(self, generator):
        state = MarketState(current_price=Decimal("3100"))
        result = generator.check_price(state)
        assert result.passed is True  # Both range OK, support skipped

    def test_price_weight(self, generator):
        state = MarketState(current_price=Decimal("3100"))
        result = generator.check_price(state)
        assert result.weight == 2

    def test_exact_boundary_min(self, generator):
        state = MarketState(
            current_price=Decimal("3000"),
            nearest_support=Decimal("2990"),
        )
        result = generator.check_price(state)
        assert result.passed is True

    def test_exact_boundary_max(self, generator):
        state = MarketState(
            current_price=Decimal("3200"),
            nearest_support=Decimal("3190"),
        )
        result = generator.check_price(state)
        assert result.passed is True


# =========================================================================
# Indicator Condition Tests
# =========================================================================


class TestIndicatorCondition:
    def test_all_indicators_pass(self, generator):
        state = MarketState(
            current_price=Decimal("3080"),
            rsi=30.0,
            volume_24h=Decimal("1500000"),
            avg_volume=Decimal("1000000"),
            bb_lower=Decimal("3070"),
        )
        result = generator.check_indicators(state)
        assert result.passed is True

    def test_rsi_not_oversold(self, generator):
        state = MarketState(
            current_price=Decimal("3080"),
            rsi=45.0,  # Above 35
            volume_24h=Decimal("1500000"),
            avg_volume=Decimal("1000000"),
            bb_lower=Decimal("3070"),
        )
        result = generator.check_indicators(state)
        assert result.passed is False
        assert "not oversold" in result.detail

    def test_low_volume(self, generator):
        state = MarketState(
            current_price=Decimal("3080"),
            rsi=30.0,
            volume_24h=Decimal("900000"),
            avg_volume=Decimal("1000000"),  # 0.9x < 1.2x
            bb_lower=Decimal("3070"),
        )
        result = generator.check_indicators(state)
        assert result.passed is False
        assert "Volume low" in result.detail

    def test_above_bollinger_lower(self, generator):
        state = MarketState(
            current_price=Decimal("3200"),  # Well above BB lower
            rsi=30.0,
            volume_24h=Decimal("1500000"),
            avg_volume=Decimal("1000000"),
            bb_lower=Decimal("3050"),  # tolerance = 3050*1.02 = 3111
        )
        result = generator.check_indicators(state)
        assert result.passed is False
        assert "Above BB lower" in result.detail

    def test_at_bollinger_with_tolerance(self, generator):
        # 2% tolerance: bb_lower * 1.02
        state = MarketState(
            current_price=Decimal("3100"),
            rsi=30.0,
            volume_24h=Decimal("1500000"),
            avg_volume=Decimal("1000000"),
            bb_lower=Decimal("3050"),  # 3050 * 1.02 = 3111 >= 3100
        )
        result = generator.check_indicators(state)
        assert result.passed is True

    def test_no_indicator_data(self, generator):
        state = MarketState(current_price=Decimal("3100"))
        result = generator.check_indicators(state)
        assert result.passed is True  # All skipped

    def test_zero_avg_volume(self, generator):
        state = MarketState(
            current_price=Decimal("3100"),
            rsi=30.0,
            volume_24h=Decimal("1500000"),
            avg_volume=Decimal("0"),
        )
        result = generator.check_indicators(state)
        # Zero avg volume — skipped
        assert "zero" in result.detail.lower()

    def test_indicator_weight(self, generator):
        state = MarketState(current_price=Decimal("3100"))
        result = generator.check_indicators(state)
        assert result.weight == 2


# =========================================================================
# Risk Filter Tests
# =========================================================================


class TestRiskFilter:
    def test_all_risk_ok(self, generator):
        state = MarketState(
            current_price=Decimal("3100"),
            active_deals=1,
            daily_pnl=Decimal("-100"),
            available_balance=Decimal("5000"),
        )
        result = generator.check_risk(state)
        assert result.passed is True

    def test_max_deals_reached(self, generator):
        state = MarketState(
            current_price=Decimal("3100"),
            active_deals=3,
        )
        result = generator.check_risk(state)
        assert result.passed is False
        assert "Max concurrent" in result.detail

    def test_daily_loss_exceeded(self, generator):
        state = MarketState(
            current_price=Decimal("3100"),
            active_deals=0,
            daily_pnl=Decimal("-600"),
        )
        result = generator.check_risk(state)
        assert result.passed is False
        assert "Daily loss" in result.detail

    def test_insufficient_balance(self):
        cfg = DCASignalConfig(min_available_balance=Decimal("1000"))
        gen = DCASignalGenerator(cfg)
        state = MarketState(
            current_price=Decimal("3100"),
            available_balance=Decimal("500"),
        )
        result = gen.check_risk(state)
        assert result.passed is False
        assert "Insufficient balance" in result.detail

    def test_insufficient_capital(self, generator):
        state = MarketState(
            current_price=Decimal("3100"),
            available_balance=Decimal("500"),
            required_capital=Decimal("1000"),
        )
        result = generator.check_risk(state)
        assert result.passed is False
        assert "Not enough capital" in result.detail

    def test_risk_weight(self, generator):
        state = MarketState(current_price=Decimal("3100"))
        result = generator.check_risk(state)
        assert result.weight == 1


# =========================================================================
# Timing Filter Tests
# =========================================================================


class TestTimingFilter:
    def test_no_previous_deal(self, generator):
        state = MarketState(current_price=Decimal("3100"))
        result = generator.check_timing(state)
        assert result.passed is True
        assert "No timing constraint" in result.detail

    def test_cooldown_active(self, generator):
        now = datetime.now(timezone.utc)
        state = MarketState(
            current_price=Decimal("3100"),
            last_deal_closed_at=now - timedelta(minutes=30),  # 1800s < 3600s
            current_time=now,
        )
        result = generator.check_timing(state)
        assert result.passed is False
        assert "Cooldown active" in result.detail

    def test_cooldown_passed(self, generator):
        now = datetime.now(timezone.utc)
        state = MarketState(
            current_price=Decimal("3100"),
            last_deal_closed_at=now - timedelta(hours=2),  # 7200s > 3600s
            current_time=now,
        )
        result = generator.check_timing(state)
        assert result.passed is True
        assert "Cooldown passed" in result.detail

    def test_cooldown_exact_boundary(self, generator):
        now = datetime.now(timezone.utc)
        state = MarketState(
            current_price=Decimal("3100"),
            last_deal_closed_at=now - timedelta(seconds=3600),
            current_time=now,
        )
        result = generator.check_timing(state)
        assert result.passed is True

    def test_no_cooldown_configured(self):
        cfg = DCASignalConfig(min_seconds_between_deals=0)
        gen = DCASignalGenerator(cfg)
        now = datetime.now(timezone.utc)
        state = MarketState(
            current_price=Decimal("3100"),
            last_deal_closed_at=now - timedelta(seconds=1),
            current_time=now,
        )
        result = gen.check_timing(state)
        assert result.passed is True

    def test_timing_weight(self, generator):
        state = MarketState(current_price=Decimal("3100"))
        result = generator.check_timing(state)
        assert result.weight == 1

    def test_naive_datetime_handled(self, generator):
        """Ensure naive datetimes don't crash."""
        now = datetime.now(timezone.utc)
        state = MarketState(
            current_price=Decimal("3100"),
            last_deal_closed_at=datetime(2024, 1, 1, 0, 0, 0),  # naive
            current_time=now,
        )
        result = generator.check_timing(state)
        assert result.passed is True  # Long time ago


# =========================================================================
# Confluence Scoring Tests
# =========================================================================


class TestConfluenceScoring:
    def test_all_conditions_pass(self, generator, bullish_state):
        result = generator.evaluate(bullish_state)
        assert result.confluence_score == 1.0
        assert result.should_open is True

    def test_perfect_score_pct(self, generator, bullish_state):
        result = generator.evaluate(bullish_state)
        assert result.score_pct == 100.0

    def test_no_data_passes_all(self):
        """With no market data, all conditions are skipped → all pass."""
        cfg = DCASignalConfig(
            entry_price_min=None,
            entry_price_max=None,
            max_concurrent_deals=0,
            max_daily_loss=Decimal("0"),
            min_seconds_between_deals=0,
        )
        gen = DCASignalGenerator(cfg)
        state = MarketState(current_price=Decimal("3100"))
        result = gen.evaluate(state)
        assert result.confluence_score == 1.0

    def test_one_category_fails(self, generator):
        """One failed category reduces score."""
        state = MarketState(
            current_price=Decimal("3100"),
            ema_fast=Decimal("3300"),  # Uptrend — fails for DOWN mode
            ema_slow=Decimal("3200"),
            adx=25.0,
            rsi=30.0,
            volume_24h=Decimal("1500000"),
            avg_volume=Decimal("1000000"),
            bb_lower=Decimal("3080"),
            nearest_support=Decimal("3050"),
        )
        result = generator.evaluate(state)
        # trend(3) fails, price(2)+indicator(2)+risk(1)+timing(1)=6 pass
        # score = 6/9 = 0.6667
        assert result.confluence_score < 0.75
        assert result.should_open is False

    def test_custom_weights(self):
        cfg = DCASignalConfig(
            weight_trend=1,
            weight_price=1,
            weight_indicator=1,
            weight_risk=1,
            weight_timing=1,
            entry_price_min=None,
            entry_price_max=None,
            require_confluence=True,
            min_confluence_score=0.6,
        )
        gen = DCASignalGenerator(cfg)
        state = MarketState(
            current_price=Decimal("3100"),
            ema_fast=Decimal("3300"),  # Fails trend
            ema_slow=Decimal("3200"),
            adx=25.0,
        )
        result = gen.evaluate(state)
        # 4 out of 5 pass → 0.8 >= 0.6
        assert result.should_open is True


# =========================================================================
# Full Evaluation Tests
# =========================================================================


class TestFullEvaluation:
    def test_signal_confirmed_confluence(self, generator, bullish_state):
        result = generator.evaluate(bullish_state)
        assert result.should_open is True
        assert "confirmed" in result.reason

    def test_confluence_too_low(self, generator):
        state = MarketState(
            current_price=Decimal("3100"),
            ema_fast=Decimal("3300"),  # Uptrend (fails)
            ema_slow=Decimal("3200"),
            adx=15.0,  # Weak (fails)
            rsi=50.0,  # Not oversold (fails)
        )
        result = generator.evaluate(state)
        assert result.should_open is False
        assert "too low" in result.reason

    def test_risk_filter_blocks(self, generator):
        state = MarketState(
            current_price=Decimal("3100"),
            active_deals=3,  # Max reached
            ema_fast=Decimal("3050"),
            ema_slow=Decimal("3200"),
            adx=25.0,
        )
        result = generator.evaluate(state)
        assert result.should_open is False
        assert "Max concurrent" in result.reason

    def test_timing_filter_blocks(self, generator):
        now = datetime.now(timezone.utc)
        state = MarketState(
            current_price=Decimal("3100"),
            last_deal_closed_at=now - timedelta(minutes=10),
            current_time=now,
            ema_fast=Decimal("3050"),
            ema_slow=Decimal("3200"),
        )
        result = generator.evaluate(state)
        assert result.should_open is False
        assert "Cooldown" in result.reason

    def test_simple_and_mode(self):
        """Test require_confluence=False (AND mode)."""
        cfg = DCASignalConfig(
            require_confluence=False,
            entry_price_min=None,
            entry_price_max=None,
        )
        gen = DCASignalGenerator(cfg)
        state = MarketState(
            current_price=Decimal("3100"),
            ema_fast=Decimal("3050"),
            ema_slow=Decimal("3200"),
            adx=25.0,
            rsi=30.0,
            volume_24h=Decimal("1500000"),
            avg_volume=Decimal("1000000"),
            bb_lower=Decimal("3080"),
        )
        result = gen.evaluate(state)
        assert result.should_open is True
        assert "All conditions met" in result.reason

    def test_simple_and_mode_fails(self):
        cfg = DCASignalConfig(
            require_confluence=False,
            entry_price_min=None,
            entry_price_max=None,
        )
        gen = DCASignalGenerator(cfg)
        state = MarketState(
            current_price=Decimal("3100"),
            ema_fast=Decimal("3300"),  # Uptrend — fails
            ema_slow=Decimal("3200"),
            adx=25.0,
            rsi=30.0,
        )
        result = gen.evaluate(state)
        assert result.should_open is False
        assert "Conditions not met" in result.reason
        assert "trend" in result.reason

    def test_conditions_in_result(self, generator, bullish_state):
        result = generator.evaluate(bullish_state)
        assert len(result.conditions) == 5
        categories = {c.category for c in result.conditions}
        assert ConditionCategory.TREND in categories
        assert ConditionCategory.PRICE in categories
        assert ConditionCategory.INDICATOR in categories
        assert ConditionCategory.RISK in categories
        assert ConditionCategory.TIMING in categories

    def test_result_has_timestamp(self, generator, bullish_state):
        result = generator.evaluate(bullish_state)
        assert result.timestamp is not None


# =========================================================================
# SignalResult Tests
# =========================================================================


class TestSignalResult:
    def test_to_dict(self, generator, bullish_state):
        result = generator.evaluate(bullish_state)
        d = result.to_dict()
        assert "should_open" in d
        assert "confluence_score" in d
        assert "score_pct" in d
        assert "conditions" in d
        assert len(d["conditions"]) == 5

    def test_score_pct_rounding(self):
        r = SignalResult(
            should_open=True,
            confluence_score=0.777777,
            reason="test",
        )
        assert r.score_pct == 77.8


# =========================================================================
# Statistics Tests
# =========================================================================


class TestStatistics:
    def test_get_statistics(self, generator):
        stats = generator.get_statistics()
        assert stats["trend_direction"] == "down"
        assert stats["min_trend_strength"] == 20.0
        assert stats["require_confluence"] is True
        assert stats["weights"]["trend"] == 3
        assert stats["weights"]["price"] == 2
        assert stats["weights"]["indicator"] == 2
        assert stats["weights"]["risk"] == 1
        assert stats["weights"]["timing"] == 1
        assert stats["max_concurrent_deals"] == 3
        assert stats["cooldown_seconds"] == 3600


# =========================================================================
# Edge Cases
# =========================================================================


class TestEdgeCases:
    def test_zero_price(self):
        cfg = DCASignalConfig(
            entry_price_min=None,
            entry_price_max=None,
        )
        gen = DCASignalGenerator(cfg)
        state = MarketState(current_price=Decimal("0"))
        result = gen.evaluate(state)
        # Should not crash
        assert isinstance(result, SignalResult)

    def test_negative_pnl_within_limit(self, generator):
        state = MarketState(
            current_price=Decimal("3100"),
            daily_pnl=Decimal("-499"),
        )
        result = generator.check_risk(state)
        assert result.passed is True

    def test_negative_pnl_exact_limit(self, generator):
        state = MarketState(
            current_price=Decimal("3100"),
            daily_pnl=Decimal("-500"),
        )
        result = generator.check_risk(state)
        assert result.passed is True  # Not below -500

    def test_negative_pnl_exceeds_limit(self, generator):
        state = MarketState(
            current_price=Decimal("3100"),
            daily_pnl=Decimal("-501"),
        )
        result = generator.check_risk(state)
        assert result.passed is False

    def test_default_generator(self):
        gen = DCASignalGenerator()
        state = MarketState(current_price=Decimal("3100"))
        result = gen.evaluate(state)
        assert isinstance(result, SignalResult)

    def test_both_blocking_filters_fail(self, generator):
        now = datetime.now(timezone.utc)
        state = MarketState(
            current_price=Decimal("3100"),
            active_deals=3,
            last_deal_closed_at=now - timedelta(minutes=10),
            current_time=now,
        )
        result = generator.evaluate(state)
        assert result.should_open is False
        assert result.confluence_score == 0.0
        # Both reasons mentioned
        assert "Max concurrent" in result.reason
        assert "Cooldown" in result.reason

    def test_config_property(self, generator, config):
        assert generator.config is config
