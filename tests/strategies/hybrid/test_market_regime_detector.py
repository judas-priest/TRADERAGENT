"""Tests for Market Regime Detector v2.0.

Tests regime classification (sideways, downtrend, uptrend, high volatility),
strategy recommendation, regime change detection, and indicator scoring.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from bot.strategies.hybrid.market_regime_detector import (
    MarketIndicators,
    MarketRegimeDetectorV2,
    RegimeConfig,
    RegimeResult,
    RegimeType,
    StrategyRecommendation,
)


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def detector():
    return MarketRegimeDetectorV2()


@pytest.fixture
def config():
    return RegimeConfig()


@pytest.fixture
def sideways_indicators():
    """Low ADX, narrow BB, no trend → Sideways."""
    return MarketIndicators(
        current_price=Decimal("3100"),
        ema_fast=Decimal("3095"),
        ema_slow=Decimal("3100"),
        adx=15.0,
        bb_upper=Decimal("3115"),
        bb_lower=Decimal("3085"),
        bb_middle=Decimal("3100"),
        rsi=50.0,
        atr=Decimal("20"),
        atr_pct=0.6,
        current_volume=Decimal("1000000"),
        avg_volume=Decimal("1000000"),
    )


@pytest.fixture
def downtrend_indicators():
    """High ADX, EMA fast < slow, bearish → Downtrend."""
    return MarketIndicators(
        current_price=Decimal("2900"),
        ema_fast=Decimal("2850"),
        ema_slow=Decimal("3000"),
        adx=35.0,
        plus_di=15.0,
        minus_di=30.0,
        bb_upper=Decimal("3020"),
        bb_lower=Decimal("2880"),
        bb_middle=Decimal("2950"),
        rsi=30.0,
        atr=Decimal("80"),
        atr_pct=2.8,
        current_volume=Decimal("1500000"),
        avg_volume=Decimal("1000000"),
    )


@pytest.fixture
def uptrend_indicators():
    """High ADX, EMA fast > slow, bullish → Uptrend."""
    return MarketIndicators(
        current_price=Decimal("3400"),
        ema_fast=Decimal("3350"),
        ema_slow=Decimal("3200"),
        adx=35.0,
        plus_di=30.0,
        minus_di=15.0,
        bb_upper=Decimal("3420"),
        bb_lower=Decimal("3280"),
        bb_middle=Decimal("3350"),
        rsi=65.0,
        atr=Decimal("80"),
        atr_pct=2.4,
        current_volume=Decimal("1200000"),
        avg_volume=Decimal("1000000"),
    )


@pytest.fixture
def high_volatility_indicators():
    """Wide BB, volume spike → High Volatility."""
    return MarketIndicators(
        current_price=Decimal("3000"),
        ema_fast=Decimal("3050"),
        ema_slow=Decimal("3100"),
        adx=30.0,
        bb_upper=Decimal("3300"),
        bb_lower=Decimal("2800"),
        bb_middle=Decimal("3050"),
        rsi=45.0,
        atr=Decimal("200"),
        atr_pct=6.7,
        current_volume=Decimal("3000000"),
        avg_volume=Decimal("1000000"),
    )


# =========================================================================
# Regime Classification Tests
# =========================================================================


class TestRegimeClassification:
    def test_sideways_detection(self, detector, sideways_indicators):
        result = detector.evaluate(sideways_indicators)
        assert result.regime == RegimeType.SIDEWAYS

    def test_downtrend_detection(self, detector, downtrend_indicators):
        result = detector.evaluate(downtrend_indicators)
        assert result.regime == RegimeType.DOWNTREND

    def test_uptrend_detection(self, detector, uptrend_indicators):
        result = detector.evaluate(uptrend_indicators)
        assert result.regime == RegimeType.UPTREND

    def test_high_volatility_detection(self, detector, high_volatility_indicators):
        result = detector.evaluate(high_volatility_indicators)
        assert result.regime == RegimeType.HIGH_VOLATILITY

    def test_transitioning_on_ambiguous(self, detector):
        """Ambiguous signals → transitioning."""
        ind = MarketIndicators(
            current_price=Decimal("3100"),
            ema_fast=Decimal("3100"),
            ema_slow=Decimal("3100"),
            adx=24.0,  # Near threshold
            bb_upper=Decimal("3160"),
            bb_lower=Decimal("3040"),
            bb_middle=Decimal("3100"),
            rsi=50.0,
            current_volume=Decimal("800000"),
            avg_volume=Decimal("1000000"),
        )
        result = detector.evaluate(ind)
        assert result.regime in (RegimeType.TRANSITIONING, RegimeType.SIDEWAYS)

    def test_unknown_on_first_eval_with_no_data(self, detector):
        """No indicator data → still classifies (with defaults)."""
        ind = MarketIndicators(current_price=Decimal("3100"))
        result = detector.evaluate(ind)
        # With all None indicators, should still produce a result
        assert result.regime is not None


# =========================================================================
# Strategy Recommendation Tests
# =========================================================================


class TestStrategyRecommendation:
    def test_sideways_recommends_grid(self, detector, sideways_indicators):
        result = detector.evaluate(sideways_indicators)
        assert result.strategy == StrategyRecommendation.GRID

    def test_downtrend_recommends_dca(self, detector):
        """Strong downtrend (high ADX) → pure DCA."""
        ind = MarketIndicators(
            current_price=Decimal("2900"),
            ema_fast=Decimal("2800"),
            ema_slow=Decimal("3000"),
            adx=45.0,  # Above hybrid_adx_max (35)
            bb_upper=Decimal("3020"),
            bb_lower=Decimal("2880"),
            bb_middle=Decimal("2950"),
            rsi=28.0,
        )
        result = detector.evaluate(ind)
        assert result.strategy == StrategyRecommendation.DCA

    def test_uptrend_recommends_trend_follower(self, detector):
        """Strong uptrend (high ADX) → Trend-Follower."""
        ind = MarketIndicators(
            current_price=Decimal("3400"),
            ema_fast=Decimal("3350"),
            ema_slow=Decimal("3200"),
            adx=45.0,  # Above hybrid_adx_max (35)
            bb_upper=Decimal("3420"),
            bb_lower=Decimal("3280"),
            bb_middle=Decimal("3350"),
            rsi=65.0,
        )
        result = detector.evaluate(ind)
        assert result.strategy == StrategyRecommendation.TREND_FOLLOWER

    def test_moderate_adx_recommends_hybrid(self, detector):
        """Moderate ADX (20-35) in downtrend → Hybrid."""
        ind = MarketIndicators(
            current_price=Decimal("2900"),
            ema_fast=Decimal("2850"),
            ema_slow=Decimal("3000"),
            adx=28.0,  # Between hybrid_adx_min (20) and hybrid_adx_max (35)
            bb_upper=Decimal("3020"),
            bb_lower=Decimal("2880"),
            bb_middle=Decimal("2950"),
            rsi=35.0,
        )
        result = detector.evaluate(ind)
        assert result.strategy == StrategyRecommendation.HYBRID

    def test_high_volatility_recommends_reduce(self, detector, high_volatility_indicators):
        result = detector.evaluate(high_volatility_indicators)
        assert result.strategy == StrategyRecommendation.REDUCE_EXPOSURE


# =========================================================================
# Component Score Tests
# =========================================================================


class TestComponentScores:
    def test_trend_score_bullish(self, detector, uptrend_indicators):
        result = detector.evaluate(uptrend_indicators)
        assert result.trend_score > 0  # Positive = bullish

    def test_trend_score_bearish(self, detector, downtrend_indicators):
        result = detector.evaluate(downtrend_indicators)
        assert result.trend_score < 0  # Negative = bearish

    def test_trend_score_neutral(self, detector, sideways_indicators):
        result = detector.evaluate(sideways_indicators)
        assert abs(result.trend_score) < 0.3  # Close to zero

    def test_volatility_score_high(self, detector, high_volatility_indicators):
        result = detector.evaluate(high_volatility_indicators)
        assert result.volatility_score >= 0.7

    def test_volatility_score_low(self, detector, sideways_indicators):
        result = detector.evaluate(sideways_indicators)
        assert result.volatility_score < 0.5

    def test_range_score_high_in_sideways(self, detector, sideways_indicators):
        result = detector.evaluate(sideways_indicators)
        assert result.range_score > 0.3

    def test_range_score_low_in_trend(self, detector, uptrend_indicators):
        result = detector.evaluate(uptrend_indicators)
        assert result.range_score < 0.3

    def test_volume_score_spike(self, detector, high_volatility_indicators):
        result = detector.evaluate(high_volatility_indicators)
        assert result.volume_score >= 0.8

    def test_volume_score_normal(self, detector, sideways_indicators):
        result = detector.evaluate(sideways_indicators)
        assert result.volume_score == pytest.approx(0.5, abs=0.1)

    def test_no_ema_data(self, detector):
        """Missing EMA data → trend score = 0."""
        ind = MarketIndicators(
            current_price=Decimal("3100"),
            adx=30.0,
            bb_upper=Decimal("3200"),
            bb_lower=Decimal("3000"),
            bb_middle=Decimal("3100"),
        )
        result = detector.evaluate(ind)
        assert result.trend_score == 0.0

    def test_no_volume_data(self, detector):
        """Missing volume → default score."""
        ind = MarketIndicators(
            current_price=Decimal("3100"),
            ema_fast=Decimal("3095"),
            ema_slow=Decimal("3100"),
            adx=15.0,
        )
        result = detector.evaluate(ind)
        assert result.volume_score == 0.5


# =========================================================================
# Regime Change Detection Tests
# =========================================================================


class TestRegimeChangeDetection:
    def test_first_evaluation_no_change(self, detector, sideways_indicators):
        result = detector.evaluate(sideways_indicators)
        assert result.regime_changed is False

    def test_same_regime_no_change(self, detector, sideways_indicators):
        detector.evaluate(sideways_indicators)
        result = detector.evaluate(sideways_indicators)
        assert result.regime_changed is False

    def test_regime_change_requires_confirmation(self, detector, sideways_indicators, downtrend_indicators):
        """Default confirmation_count=2 requires 2 consecutive evaluations."""
        # Establish sideways
        detector.evaluate(sideways_indicators)

        # One downtrend evaluation → not confirmed
        result = detector.evaluate(downtrend_indicators)
        assert result.regime_changed is False

    def test_regime_change_after_confirmation(self):
        """Regime changes after sufficient confirmation and cooldown."""
        config = RegimeConfig(
            confirmation_count=2,
            min_regime_duration_seconds=0,  # No cooldown for testing
        )
        detector = MarketRegimeDetectorV2(config)

        sideways = MarketIndicators(
            current_price=Decimal("3100"),
            ema_fast=Decimal("3095"),
            ema_slow=Decimal("3100"),
            adx=15.0,
            bb_upper=Decimal("3130"),
            bb_lower=Decimal("3070"),
            bb_middle=Decimal("3100"),
        )
        downtrend = MarketIndicators(
            current_price=Decimal("2900"),
            ema_fast=Decimal("2800"),
            ema_slow=Decimal("3000"),
            adx=40.0,
            bb_upper=Decimal("3020"),
            bb_lower=Decimal("2880"),
            bb_middle=Decimal("2950"),
        )

        # Establish sideways
        detector.evaluate(sideways)
        assert detector.current_regime == RegimeType.SIDEWAYS

        # First downtrend signal → pending
        detector.evaluate(downtrend)
        assert detector.current_regime == RegimeType.SIDEWAYS

        # Second downtrend signal → confirmed
        result = detector.evaluate(downtrend)
        assert result.regime_changed is True
        assert detector.current_regime == RegimeType.DOWNTREND
        assert result.change_event is not None
        assert result.change_event.previous_regime == RegimeType.SIDEWAYS
        assert result.change_event.new_regime == RegimeType.DOWNTREND

    def test_cooldown_prevents_rapid_change(self):
        """Regime doesn't change during cooldown period."""
        config = RegimeConfig(
            confirmation_count=1,
            min_regime_duration_seconds=600,  # 10 min
        )
        detector = MarketRegimeDetectorV2(config)

        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        sideways = MarketIndicators(
            current_price=Decimal("3100"),
            ema_fast=Decimal("3095"),
            ema_slow=Decimal("3100"),
            adx=15.0,
            bb_upper=Decimal("3130"),
            bb_lower=Decimal("3070"),
            bb_middle=Decimal("3100"),
            timestamp=now,
        )
        downtrend = MarketIndicators(
            current_price=Decimal("2900"),
            ema_fast=Decimal("2800"),
            ema_slow=Decimal("3000"),
            adx=40.0,
            bb_upper=Decimal("3020"),
            bb_lower=Decimal("2880"),
            bb_middle=Decimal("2950"),
            timestamp=now + timedelta(seconds=60),  # Only 1 min later
        )

        detector.evaluate(sideways)
        result = detector.evaluate(downtrend)
        # Should NOT change — cooldown not met
        assert result.regime_changed is False
        assert detector.current_regime == RegimeType.SIDEWAYS

    def test_regime_change_after_cooldown(self):
        """Regime changes after cooldown period passes."""
        config = RegimeConfig(
            confirmation_count=1,
            min_regime_duration_seconds=60,
        )
        detector = MarketRegimeDetectorV2(config)

        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        sideways = MarketIndicators(
            current_price=Decimal("3100"),
            ema_fast=Decimal("3095"),
            ema_slow=Decimal("3100"),
            adx=15.0,
            bb_upper=Decimal("3130"),
            bb_lower=Decimal("3070"),
            bb_middle=Decimal("3100"),
            timestamp=now,
        )
        downtrend = MarketIndicators(
            current_price=Decimal("2900"),
            ema_fast=Decimal("2800"),
            ema_slow=Decimal("3000"),
            adx=40.0,
            bb_upper=Decimal("3020"),
            bb_lower=Decimal("2880"),
            bb_middle=Decimal("2950"),
            timestamp=now + timedelta(seconds=120),  # 2 min later
        )

        detector.evaluate(sideways)
        detector.evaluate(downtrend)  # First: sets pending
        result = detector.evaluate(downtrend)  # Second: confirms
        assert result.regime_changed is True
        assert detector.current_regime == RegimeType.DOWNTREND

    def test_history_tracks_changes(self):
        """Regime change events are stored in history."""
        config = RegimeConfig(confirmation_count=1, min_regime_duration_seconds=0)
        detector = MarketRegimeDetectorV2(config)

        sideways = MarketIndicators(
            current_price=Decimal("3100"),
            ema_fast=Decimal("3095"),
            ema_slow=Decimal("3100"),
            adx=15.0,
            bb_upper=Decimal("3130"),
            bb_lower=Decimal("3070"),
            bb_middle=Decimal("3100"),
        )
        uptrend = MarketIndicators(
            current_price=Decimal("3400"),
            ema_fast=Decimal("3350"),
            ema_slow=Decimal("3200"),
            adx=45.0,
            bb_upper=Decimal("3420"),
            bb_lower=Decimal("3280"),
            bb_middle=Decimal("3350"),
        )

        detector.evaluate(sideways)
        detector.evaluate(uptrend)  # First: sets pending
        detector.evaluate(uptrend)  # Second: confirms

        assert len(detector.history) == 1
        assert detector.history[0].previous_regime == RegimeType.SIDEWAYS
        assert detector.history[0].new_regime == RegimeType.UPTREND

    def test_pending_reset_on_different_regime(self):
        """Pending count resets when a third regime appears."""
        config = RegimeConfig(confirmation_count=3, min_regime_duration_seconds=0)
        detector = MarketRegimeDetectorV2(config)

        sideways = MarketIndicators(
            current_price=Decimal("3100"),
            ema_fast=Decimal("3095"),
            ema_slow=Decimal("3100"),
            adx=15.0,
            bb_upper=Decimal("3130"),
            bb_lower=Decimal("3070"),
            bb_middle=Decimal("3100"),
        )
        downtrend = MarketIndicators(
            current_price=Decimal("2900"),
            ema_fast=Decimal("2800"),
            ema_slow=Decimal("3000"),
            adx=40.0,
            bb_upper=Decimal("3020"),
            bb_lower=Decimal("2880"),
            bb_middle=Decimal("2950"),
        )
        uptrend = MarketIndicators(
            current_price=Decimal("3400"),
            ema_fast=Decimal("3350"),
            ema_slow=Decimal("3200"),
            adx=45.0,
            bb_upper=Decimal("3420"),
            bb_lower=Decimal("3280"),
            bb_middle=Decimal("3350"),
        )

        detector.evaluate(sideways)  # Establish
        detector.evaluate(downtrend)  # Pending: downtrend (1)
        detector.evaluate(uptrend)  # Different → reset pending to uptrend (1)
        detector.evaluate(downtrend)  # Different → reset to downtrend (1)

        # Still sideways — never got 3 consecutive confirmations
        assert detector.current_regime == RegimeType.SIDEWAYS


# =========================================================================
# Confidence Tests
# =========================================================================


class TestConfidence:
    def test_sideways_confidence(self, detector, sideways_indicators):
        result = detector.evaluate(sideways_indicators)
        assert result.confidence >= 0.5

    def test_strong_trend_confidence(self, detector, uptrend_indicators):
        result = detector.evaluate(uptrend_indicators)
        assert result.confidence >= 0.5

    def test_high_volatility_confidence(self, detector, high_volatility_indicators):
        result = detector.evaluate(high_volatility_indicators)
        assert result.confidence >= 0.7

    def test_confidence_bounded(self, detector, sideways_indicators):
        result = detector.evaluate(sideways_indicators)
        assert 0.0 <= result.confidence <= 1.0


# =========================================================================
# Serialization Tests
# =========================================================================


class TestSerialization:
    def test_result_to_dict(self, detector, sideways_indicators):
        result = detector.evaluate(sideways_indicators)
        d = result.to_dict()
        assert "regime" in d
        assert "strategy" in d
        assert "confidence" in d
        assert "trend_score" in d
        assert "volatility_score" in d
        assert "range_score" in d
        assert "volume_score" in d
        assert d["regime"] == "sideways"

    def test_change_event_to_dict(self):
        config = RegimeConfig(confirmation_count=1, min_regime_duration_seconds=0)
        detector = MarketRegimeDetectorV2(config)

        sideways = MarketIndicators(
            current_price=Decimal("3100"),
            ema_fast=Decimal("3095"),
            ema_slow=Decimal("3100"),
            adx=15.0,
            bb_upper=Decimal("3130"),
            bb_lower=Decimal("3070"),
            bb_middle=Decimal("3100"),
        )
        uptrend = MarketIndicators(
            current_price=Decimal("3400"),
            ema_fast=Decimal("3350"),
            ema_slow=Decimal("3200"),
            adx=45.0,
            bb_upper=Decimal("3420"),
            bb_lower=Decimal("3280"),
            bb_middle=Decimal("3350"),
        )

        detector.evaluate(sideways)
        detector.evaluate(uptrend)  # First: sets pending
        result = detector.evaluate(uptrend)  # Second: confirms
        assert result.change_event is not None
        d = result.change_event.to_dict()
        assert d["previous_regime"] == "sideways"
        assert d["new_regime"] == "uptrend"


# =========================================================================
# Statistics and Reset Tests
# =========================================================================


class TestStatisticsAndReset:
    def test_statistics(self, detector, sideways_indicators):
        detector.evaluate(sideways_indicators)
        stats = detector.get_statistics()
        assert stats["current_regime"] == "sideways"
        assert stats["evaluation_count"] == 1
        assert "config" in stats

    def test_reset(self, detector, sideways_indicators):
        detector.evaluate(sideways_indicators)
        assert detector.current_regime == RegimeType.SIDEWAYS

        detector.reset()
        assert detector.current_regime == RegimeType.UNKNOWN
        assert detector.current_strategy == StrategyRecommendation.HOLD
        assert len(detector.history) == 0

    def test_evaluation_count(self, detector, sideways_indicators):
        detector.evaluate(sideways_indicators)
        detector.evaluate(sideways_indicators)
        detector.evaluate(sideways_indicators)
        stats = detector.get_statistics()
        assert stats["evaluation_count"] == 3


# =========================================================================
# Warnings Tests
# =========================================================================


class TestWarnings:
    def test_bb_width_warning(self, detector, high_volatility_indicators):
        result = detector.evaluate(high_volatility_indicators)
        assert any("BB width" in w for w in result.warnings)

    def test_no_warning_in_sideways(self, detector, sideways_indicators):
        result = detector.evaluate(sideways_indicators)
        assert len(result.warnings) == 0


# =========================================================================
# Custom Config Tests
# =========================================================================


class TestCustomConfig:
    def test_lower_adx_threshold(self):
        """Lower ADX threshold makes more markets appear trending."""
        config = RegimeConfig(adx_trend_threshold=10.0)
        detector = MarketRegimeDetectorV2(config)

        # ADX=15 normally sideways, but with threshold=10 → trending
        ind = MarketIndicators(
            current_price=Decimal("3100"),
            ema_fast=Decimal("3200"),
            ema_slow=Decimal("3100"),
            adx=15.0,
            bb_upper=Decimal("3160"),
            bb_lower=Decimal("3040"),
            bb_middle=Decimal("3100"),
        )
        result = detector.evaluate(ind)
        assert result.regime == RegimeType.UPTREND

    def test_wider_bb_threshold(self):
        """Higher BB threshold means less high-volatility detection."""
        config = RegimeConfig(bb_wide_pct=Decimal("20.0"))
        detector = MarketRegimeDetectorV2(config)

        # Wide BB but threshold is very high → not high volatility
        ind = MarketIndicators(
            current_price=Decimal("3000"),
            ema_fast=Decimal("3050"),
            ema_slow=Decimal("3100"),
            adx=20.0,
            bb_upper=Decimal("3200"),
            bb_lower=Decimal("2800"),
            bb_middle=Decimal("3000"),
            rsi=45.0,
            atr_pct=2.0,
        )
        result = detector.evaluate(ind)
        assert result.regime != RegimeType.HIGH_VOLATILITY
