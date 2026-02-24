"""Tests for regime-based strategy selection in BotOrchestrator (#283, #293)."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

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


def _make_orchestrator_stub(cooldown: float = 0.0) -> BotOrchestrator:
    """Create a BotOrchestrator with minimal mocked dependencies.

    We bypass __init__ by creating an empty object and setting only the
    attributes needed for _update_active_strategies / _is_strategy_active.
    """
    orch = object.__new__(BotOrchestrator)
    orch._current_regime = None
    orch._active_strategies = set()
    orch._last_strategy_switch_at = 0.0
    orch._strategy_switch_cooldown = cooldown
    # Async methods used by _update_active_strategies
    orch._publish_event = AsyncMock()
    orch._graceful_transition = AsyncMock()
    return orch


# --- RecommendedStrategy → active strategy set mapping ---


class TestRegimeToStrategyMapping:
    """Verify _update_active_strategies produces correct strategy sets."""

    @pytest.mark.asyncio
    async def test_no_regime_keeps_all_active(self) -> None:
        orch = _make_orchestrator_stub()
        orch._current_regime = None
        await orch._update_active_strategies()
        assert orch._active_strategies == {"grid", "dca", "trend_follower", "smc"}

    @pytest.mark.asyncio
    async def test_tight_range_selects_grid(self) -> None:
        orch = _make_orchestrator_stub()
        orch._current_regime = _make_regime(MarketRegime.TIGHT_RANGE, RecommendedStrategy.GRID)
        await orch._update_active_strategies()
        assert "grid" in orch._active_strategies
        assert "dca" not in orch._active_strategies
        assert "trend_follower" not in orch._active_strategies

    @pytest.mark.asyncio
    async def test_wide_range_selects_grid(self) -> None:
        orch = _make_orchestrator_stub()
        orch._current_regime = _make_regime(MarketRegime.WIDE_RANGE, RecommendedStrategy.GRID)
        await orch._update_active_strategies()
        assert orch._active_strategies == {"grid"}

    @pytest.mark.asyncio
    async def test_bull_trend_selects_trend_follower_and_dca(self) -> None:
        orch = _make_orchestrator_stub()
        orch._current_regime = _make_regime(MarketRegime.BULL_TREND, RecommendedStrategy.DCA)
        await orch._update_active_strategies()
        assert "dca" in orch._active_strategies
        assert "trend_follower" in orch._active_strategies
        assert "smc" in orch._active_strategies
        assert "grid" not in orch._active_strategies

    @pytest.mark.asyncio
    async def test_bull_trend_hybrid_selects_grid_dca_tf_smc(self) -> None:
        orch = _make_orchestrator_stub()
        orch._current_regime = _make_regime(MarketRegime.BULL_TREND, RecommendedStrategy.HYBRID)
        await orch._update_active_strategies()
        assert "grid" in orch._active_strategies
        assert "dca" in orch._active_strategies
        assert "trend_follower" in orch._active_strategies
        assert "smc" in orch._active_strategies

    @pytest.mark.asyncio
    async def test_bear_trend_selects_dca_tf_smc(self) -> None:
        orch = _make_orchestrator_stub()
        orch._current_regime = _make_regime(MarketRegime.BEAR_TREND, RecommendedStrategy.DCA)
        await orch._update_active_strategies()
        assert "dca" in orch._active_strategies
        assert "trend_follower" in orch._active_strategies
        assert "smc" in orch._active_strategies
        assert "grid" not in orch._active_strategies

    @pytest.mark.asyncio
    async def test_quiet_transition_hold_deactivates_all(self) -> None:
        orch = _make_orchestrator_stub()
        orch._current_regime = _make_regime(MarketRegime.QUIET_TRANSITION, RecommendedStrategy.HOLD)
        await orch._update_active_strategies()
        assert orch._active_strategies == set()

    @pytest.mark.asyncio
    async def test_volatile_transition_reduce_deactivates_all(self) -> None:
        orch = _make_orchestrator_stub()
        orch._current_regime = _make_regime(
            MarketRegime.VOLATILE_TRANSITION, RecommendedStrategy.REDUCE_EXPOSURE
        )
        await orch._update_active_strategies()
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


# --- Cooldown guard tests (#293) ---


class TestStrategySwitchCooldown:
    """Verify cooldown prevents rapid strategy oscillation."""

    @pytest.mark.asyncio
    async def test_no_cooldown_allows_immediate_switch(self) -> None:
        """With cooldown=0, switches happen immediately."""
        orch = _make_orchestrator_stub(cooldown=0.0)
        # First: set to grid
        orch._current_regime = _make_regime(MarketRegime.TIGHT_RANGE, RecommendedStrategy.GRID)
        await orch._update_active_strategies()
        assert "grid" in orch._active_strategies

        # Switch immediately to DCA
        orch._current_regime = _make_regime(MarketRegime.BEAR_TREND, RecommendedStrategy.DCA)
        await orch._update_active_strategies()
        assert "dca" in orch._active_strategies
        assert "grid" not in orch._active_strategies

    @pytest.mark.asyncio
    async def test_cooldown_blocks_rapid_switch(self) -> None:
        """Switch is blocked when within cooldown period."""
        orch = _make_orchestrator_stub(cooldown=600.0)
        # First: set to grid
        orch._current_regime = _make_regime(MarketRegime.TIGHT_RANGE, RecommendedStrategy.GRID)
        await orch._update_active_strategies()
        assert "grid" in orch._active_strategies

        # Try to switch to DCA immediately — should be blocked
        orch._current_regime = _make_regime(MarketRegime.BEAR_TREND, RecommendedStrategy.DCA)
        await orch._update_active_strategies()
        # Still grid because cooldown blocked the switch
        assert "grid" in orch._active_strategies
        assert "dca" not in orch._active_strategies

    @pytest.mark.asyncio
    async def test_cooldown_allows_switch_after_expiry(self) -> None:
        """Switch allowed once cooldown has elapsed."""
        orch = _make_orchestrator_stub(cooldown=0.1)  # 100ms
        # First: set to grid
        orch._current_regime = _make_regime(MarketRegime.TIGHT_RANGE, RecommendedStrategy.GRID)
        await orch._update_active_strategies()
        assert "grid" in orch._active_strategies

        # Wait for cooldown to expire
        await asyncio.sleep(0.15)

        # Now switch should work
        orch._current_regime = _make_regime(MarketRegime.BEAR_TREND, RecommendedStrategy.DCA)
        await orch._update_active_strategies()
        assert "dca" in orch._active_strategies

    @pytest.mark.asyncio
    async def test_cooldown_rapid_oscillation(self) -> None:
        """Simulate rapid regime oscillation — only first switch goes through."""
        orch = _make_orchestrator_stub(cooldown=600.0)
        # First: set to grid
        orch._current_regime = _make_regime(MarketRegime.TIGHT_RANGE, RecommendedStrategy.GRID)
        await orch._update_active_strategies()
        first_strategies = orch._active_strategies.copy()

        # Oscillate rapidly between DCA and Grid
        for _ in range(10):
            orch._current_regime = _make_regime(MarketRegime.BEAR_TREND, RecommendedStrategy.DCA)
            await orch._update_active_strategies()
            orch._current_regime = _make_regime(MarketRegime.TIGHT_RANGE, RecommendedStrategy.GRID)
            await orch._update_active_strategies()

        # Should still be on the first set (all blocked by cooldown)
        assert orch._active_strategies == first_strategies

    @pytest.mark.asyncio
    async def test_same_strategies_no_cooldown_needed(self) -> None:
        """If regime changes but strategies stay the same, no cooldown triggered."""
        orch = _make_orchestrator_stub(cooldown=600.0)
        # Both tight_range and wide_range recommend GRID
        orch._current_regime = _make_regime(MarketRegime.TIGHT_RANGE, RecommendedStrategy.GRID)
        await orch._update_active_strategies()
        assert "grid" in orch._active_strategies

        # Change to wide_range (still GRID) — no switch, no cooldown impact
        orch._current_regime = _make_regime(MarketRegime.WIDE_RANGE, RecommendedStrategy.GRID)
        await orch._update_active_strategies()
        assert "grid" in orch._active_strategies

    @pytest.mark.asyncio
    async def test_first_switch_from_empty_not_blocked(self) -> None:
        """First ever switch (from empty set) should never be blocked."""
        orch = _make_orchestrator_stub(cooldown=600.0)
        assert orch._active_strategies == set()

        # First regime detection — should always go through
        orch._current_regime = _make_regime(MarketRegime.BEAR_TREND, RecommendedStrategy.DCA)
        await orch._update_active_strategies()
        assert "dca" in orch._active_strategies

    @pytest.mark.asyncio
    async def test_cooldown_timestamp_updated_on_switch(self) -> None:
        """_last_strategy_switch_at is updated when a switch occurs."""
        orch = _make_orchestrator_stub(cooldown=0.0)
        assert orch._last_strategy_switch_at == 0.0

        # First switch
        orch._current_regime = _make_regime(MarketRegime.TIGHT_RANGE, RecommendedStrategy.GRID)
        await orch._update_active_strategies()

        # Switch
        before = time.monotonic()
        orch._current_regime = _make_regime(MarketRegime.BEAR_TREND, RecommendedStrategy.DCA)
        await orch._update_active_strategies()
        after = time.monotonic()

        assert before <= orch._last_strategy_switch_at <= after
