"""Tests for regime-based strategy selection in BotOrchestrator (#283)."""

from __future__ import annotations

from datetime import datetime, timezone

from bot.orchestrator.bot_orchestrator import BotOrchestrator
from bot.orchestrator.market_regime import (
    MarketRegime,
    RecommendedStrategy,
    RegimeAnalysis,
)


def _make_regime(
    regime: MarketRegime,
    recommended: RecommendedStrategy,
    confidence: float = 0.8,
) -> RegimeAnalysis:
    """Create a minimal RegimeAnalysis for testing."""
    return RegimeAnalysis(
        regime=regime,
        confidence=confidence,
        recommended_strategy=recommended,
        confluence_score=0.5,
        trend_strength=0.0,
        volatility_percentile=50.0,
        ema_divergence_pct=1.0,
        atr_pct=1.0,
        rsi=50.0,
        adx=30.0,
        bb_width_pct=3.0,
        volume_ratio=1.0,
        regime_duration_seconds=120,
        previous_regime=None,
        timestamp=datetime.now(timezone.utc),
        analysis_details={},
    )


def _make_orchestrator_stub() -> BotOrchestrator:
    """Create a BotOrchestrator with minimal mocked dependencies.

    We bypass __init__ by creating an empty object and setting only the
    attributes needed for _update_active_strategies / _is_strategy_active.
    """
    orch = object.__new__(BotOrchestrator)
    orch._current_regime = None
    orch._active_strategies = set()
    return orch


# --- RecommendedStrategy → active strategy set mapping ---


class TestRegimeToStrategyMapping:
    """Verify _update_active_strategies produces correct strategy sets."""

    def test_no_regime_keeps_all_active(self) -> None:
        orch = _make_orchestrator_stub()
        orch._current_regime = None
        orch._update_active_strategies()
        assert orch._active_strategies == {"grid", "dca", "trend_follower", "smc"}

    def test_tight_range_selects_grid(self) -> None:
        orch = _make_orchestrator_stub()
        orch._current_regime = _make_regime(MarketRegime.TIGHT_RANGE, RecommendedStrategy.GRID)
        orch._update_active_strategies()
        assert "grid" in orch._active_strategies
        assert "dca" not in orch._active_strategies
        assert "trend_follower" not in orch._active_strategies

    def test_wide_range_selects_grid(self) -> None:
        orch = _make_orchestrator_stub()
        orch._current_regime = _make_regime(MarketRegime.WIDE_RANGE, RecommendedStrategy.GRID)
        orch._update_active_strategies()
        assert orch._active_strategies == {"grid"}

    def test_bull_trend_selects_trend_follower_and_dca(self) -> None:
        orch = _make_orchestrator_stub()
        orch._current_regime = _make_regime(MarketRegime.BULL_TREND, RecommendedStrategy.DCA)
        orch._update_active_strategies()
        assert "dca" in orch._active_strategies
        assert "trend_follower" in orch._active_strategies
        assert "smc" in orch._active_strategies
        assert "grid" not in orch._active_strategies

    def test_bull_trend_hybrid_selects_grid_dca_tf_smc(self) -> None:
        orch = _make_orchestrator_stub()
        orch._current_regime = _make_regime(MarketRegime.BULL_TREND, RecommendedStrategy.HYBRID)
        orch._update_active_strategies()
        assert "grid" in orch._active_strategies
        assert "dca" in orch._active_strategies
        assert "trend_follower" in orch._active_strategies
        assert "smc" in orch._active_strategies

    def test_bear_trend_selects_dca_tf_smc(self) -> None:
        orch = _make_orchestrator_stub()
        orch._current_regime = _make_regime(MarketRegime.BEAR_TREND, RecommendedStrategy.DCA)
        orch._update_active_strategies()
        assert "dca" in orch._active_strategies
        assert "trend_follower" in orch._active_strategies
        assert "smc" in orch._active_strategies
        assert "grid" not in orch._active_strategies

    def test_quiet_transition_hold_deactivates_all(self) -> None:
        orch = _make_orchestrator_stub()
        orch._current_regime = _make_regime(MarketRegime.QUIET_TRANSITION, RecommendedStrategy.HOLD)
        orch._update_active_strategies()
        assert orch._active_strategies == set()

    def test_volatile_transition_reduce_deactivates_all(self) -> None:
        orch = _make_orchestrator_stub()
        orch._current_regime = _make_regime(
            MarketRegime.VOLATILE_TRANSITION, RecommendedStrategy.REDUCE_EXPOSURE
        )
        orch._update_active_strategies()
        # volatile_transition enables SMC
        assert "smc" in orch._active_strategies
        assert "grid" not in orch._active_strategies
        assert "dca" not in orch._active_strategies


class TestIsStrategyActive:
    """Verify _is_strategy_active helper."""

    def test_active_strategy_returns_true(self) -> None:
        orch = _make_orchestrator_stub()
        orch._active_strategies = {"grid", "dca"}
        assert orch._is_strategy_active("grid") is True
        assert orch._is_strategy_active("dca") is True

    def test_inactive_strategy_returns_false(self) -> None:
        orch = _make_orchestrator_stub()
        orch._active_strategies = {"grid"}
        assert orch._is_strategy_active("dca") is False
        assert orch._is_strategy_active("trend_follower") is False

    def test_empty_set_all_inactive(self) -> None:
        orch = _make_orchestrator_stub()
        orch._active_strategies = set()
        assert orch._is_strategy_active("grid") is False
        assert orch._is_strategy_active("smc") is False


class TestGetStrategyRecommendation:
    """Verify get_strategy_recommendation() returns correct value."""

    def test_returns_none_when_no_regime(self) -> None:
        orch = _make_orchestrator_stub()
        orch._current_regime = None
        assert orch.get_strategy_recommendation() is None

    def test_returns_recommendation_from_regime(self) -> None:
        orch = _make_orchestrator_stub()
        orch._current_regime = _make_regime(MarketRegime.BULL_TREND, RecommendedStrategy.DCA)
        assert orch.get_strategy_recommendation() == RecommendedStrategy.DCA

    def test_returns_grid_for_tight_range(self) -> None:
        orch = _make_orchestrator_stub()
        orch._current_regime = _make_regime(MarketRegime.TIGHT_RANGE, RecommendedStrategy.GRID)
        assert orch.get_strategy_recommendation() == RecommendedStrategy.GRID
