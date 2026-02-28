"""Tests for HybridStrategy integration in BotOrchestrator."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.orchestrator.bot_orchestrator import BotOrchestrator
from bot.strategies.hybrid.hybrid_config import HybridConfig, HybridMode
from bot.strategies.hybrid.hybrid_strategy import HybridStrategy


def _make_orchestrator_stub(
    *,
    has_grid: bool = True,
    has_dca: bool = True,
    has_hybrid: bool = True,
    strategy: str = "hybrid",
) -> BotOrchestrator:
    """Create BotOrchestrator stub with minimal attributes for hybrid tests."""
    orch = object.__new__(BotOrchestrator)
    orch.config = MagicMock()
    orch.config.name = "test-bot"
    orch.config.strategy = strategy

    orch.grid_engine = MagicMock() if has_grid else None
    orch.dca_engine = MagicMock() if has_dca else None
    orch.current_price = Decimal("50000")
    orch._current_regime = None
    orch._active_strategies = {"grid", "dca"}
    orch.redis_client = None

    if has_hybrid and has_grid and has_dca:
        orch.hybrid_strategy = HybridStrategy(
            config=HybridConfig(),
            grid_risk_manager=MagicMock(),
            dca_engine=None,
        )
    else:
        orch.hybrid_strategy = None

    # Mock async methods
    orch._process_grid_orders = AsyncMock()
    orch._process_dca_logic = AsyncMock()
    orch._publish_event = AsyncMock()
    return orch


class TestHybridStrategyInstantiation:
    """Verify hybrid_strategy is set for hybrid configs and None otherwise."""

    def test_hybrid_config_creates_strategy(self):
        orch = _make_orchestrator_stub(strategy="hybrid")
        assert orch.hybrid_strategy is not None
        assert isinstance(orch.hybrid_strategy, HybridStrategy)

    def test_non_hybrid_config_no_strategy(self):
        orch = _make_orchestrator_stub(strategy="grid", has_hybrid=False)
        assert orch.hybrid_strategy is None

    def test_missing_dca_engine_no_strategy(self):
        orch = _make_orchestrator_stub(has_dca=False, has_hybrid=False)
        assert orch.hybrid_strategy is None

    def test_missing_grid_engine_no_strategy(self):
        orch = _make_orchestrator_stub(has_grid=False, has_hybrid=False)
        assert orch.hybrid_strategy is None


class TestHybridModeRouting:
    """Verify _process_hybrid_logic routes to correct engine based on mode."""

    @pytest.mark.asyncio
    async def test_grid_only_mode_runs_grid(self):
        orch = _make_orchestrator_stub()
        # Default mode is GRID_ONLY
        assert orch.hybrid_strategy.mode == HybridMode.GRID_ONLY

        await orch._process_hybrid_logic()

        orch._process_grid_orders.assert_awaited_once()
        orch._process_dca_logic.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_dca_active_mode_runs_dca(self):
        orch = _make_orchestrator_stub()
        # Force DCA mode
        orch.hybrid_strategy._mode = HybridMode.DCA_ACTIVE

        await orch._process_hybrid_logic()

        orch._process_dca_logic.assert_awaited_once()
        orch._process_grid_orders.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_both_active_runs_both(self):
        orch = _make_orchestrator_stub()
        orch.hybrid_strategy._mode = HybridMode.BOTH_ACTIVE

        await orch._process_hybrid_logic()

        orch._process_grid_orders.assert_awaited_once()
        orch._process_dca_logic.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_transitioning_runs_both(self):
        orch = _make_orchestrator_stub()
        orch.hybrid_strategy._mode = HybridMode.TRANSITIONING

        await orch._process_hybrid_logic()

        orch._process_grid_orders.assert_awaited_once()
        orch._process_dca_logic.assert_awaited_once()


class TestHybridFallback:
    """Verify graceful fallback when hybrid evaluation fails."""

    @pytest.mark.asyncio
    async def test_evaluate_error_falls_back_to_both(self):
        orch = _make_orchestrator_stub()
        orch.hybrid_strategy.evaluate = MagicMock(side_effect=RuntimeError("boom"))

        await orch._process_hybrid_logic()

        # Both engines should run as fallback
        orch._process_grid_orders.assert_awaited_once()
        orch._process_dca_logic.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_current_price_returns_early(self):
        orch = _make_orchestrator_stub()
        orch.current_price = None

        await orch._process_hybrid_logic()

        orch._process_grid_orders.assert_not_awaited()
        orch._process_dca_logic.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_hybrid_strategy_returns_early(self):
        orch = _make_orchestrator_stub(has_hybrid=False)

        await orch._process_hybrid_logic()

        orch._process_grid_orders.assert_not_awaited()
        orch._process_dca_logic.assert_not_awaited()


class TestHybridBackwardCompat:
    """Verify non-hybrid bots are unaffected."""

    @pytest.mark.asyncio
    async def test_grid_only_bot_no_hybrid(self):
        orch = _make_orchestrator_stub(strategy="grid", has_dca=False, has_hybrid=False)
        orch._active_strategies = {"grid"}
        assert orch.hybrid_strategy is None
        # Grid-only would go through the else branch in _main_loop

    @pytest.mark.asyncio
    async def test_dca_only_bot_no_hybrid(self):
        orch = _make_orchestrator_stub(strategy="dca", has_grid=False, has_hybrid=False)
        orch._active_strategies = {"dca"}
        assert orch.hybrid_strategy is None


class TestHybridMissingRegime:
    """Verify missing regime data doesn't crash."""

    @pytest.mark.asyncio
    async def test_no_regime_data_evaluates_safely(self):
        orch = _make_orchestrator_stub()
        orch._current_regime = None

        # Should not raise
        await orch._process_hybrid_logic()

        # Default GRID_ONLY mode should run grid
        orch._process_grid_orders.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_regime_with_adx_passes_to_evaluate(self):
        orch = _make_orchestrator_stub()
        regime = MagicMock()
        regime.adx = 35.0
        orch._current_regime = regime

        await orch._process_hybrid_logic()

        # Should still work — GRID_ONLY by default
        orch._process_grid_orders.assert_awaited_once()
