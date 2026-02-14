"""Tests for HybridStrategy — Grid+DCA hybrid mode."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from bot.strategies.dca.dca_engine import DCAEngine
from bot.strategies.dca.dca_signal_generator import MarketState
from bot.strategies.grid.grid_risk_manager import (
    GridRiskAction,
    GridRiskManager,
    RiskCheckResult,
)
from bot.strategies.hybrid.hybrid_config import HybridConfig, HybridMode
from bot.strategies.hybrid.hybrid_strategy import (
    HybridAction,
    HybridStrategy,
    TransitionEvent,
)
from bot.strategies.hybrid.market_regime_detector import (
    MarketRegimeDetectorV2,
    RegimeResult,
    RegimeType,
    StrategyRecommendation,
)


# =============================================================================
# Helpers
# =============================================================================


def _make_market_state(price: float = 3000.0) -> MarketState:
    """Create a MarketState for testing."""
    return MarketState(
        current_price=Decimal(str(price)),
        ema_fast=Decimal(str(price * 1.01)),
        ema_slow=Decimal(str(price * 0.99)),
        adx=20.0,
        rsi=50.0,
        current_time=datetime.now(timezone.utc),
    )


def _make_regime_result(
    regime: RegimeType = RegimeType.SIDEWAYS,
    strategy: StrategyRecommendation = StrategyRecommendation.GRID,
    confidence: float = 0.8,
) -> RegimeResult:
    """Create a RegimeResult for testing."""
    return RegimeResult(
        regime=regime,
        strategy=strategy,
        confidence=confidence,
    )


def _make_dca_engine() -> DCAEngine:
    """Create a DCA engine for testing."""
    return DCAEngine(symbol="BTC/USDT")


def _make_hybrid(
    transition_cooldown: int = 0,
    min_grid_duration: int = 0,
    min_dca_duration: int = 0,
    breakout_adx: float = 25.0,
    return_adx: float = 20.0,
    require_deals_closed: bool = True,
) -> HybridStrategy:
    """Create a HybridStrategy with test-friendly defaults."""
    config = HybridConfig(
        transition_cooldown_seconds=transition_cooldown,
        min_grid_duration_seconds=min_grid_duration,
        min_dca_duration_seconds=min_dca_duration,
        breakout_adx_threshold=breakout_adx,
        return_adx_threshold=return_adx,
        require_dca_deals_closed=require_deals_closed,
    )
    return HybridStrategy(
        config=config,
        grid_risk_manager=GridRiskManager(),
        dca_engine=_make_dca_engine(),
        regime_detector=MarketRegimeDetectorV2(),
    )


# =============================================================================
# TestHybridConfig
# =============================================================================


class TestHybridConfig:
    """Tests for HybridConfig."""

    def test_default_config(self):
        config = HybridConfig()
        total = config.grid_capital_pct + config.dca_capital_pct + config.reserve_pct
        assert abs(total - 1.0) < 0.001
        assert config.breakout_adx_threshold == 25.0
        assert config.return_adx_threshold == 20.0
        assert config.transition_cooldown_seconds == 120

    def test_custom_config(self):
        config = HybridConfig(
            grid_capital_pct=0.5,
            dca_capital_pct=0.4,
            reserve_pct=0.1,
            breakout_adx_threshold=30.0,
        )
        config.validate()
        assert config.grid_capital_pct == 0.5
        assert config.breakout_adx_threshold == 30.0

    def test_config_validation_capital_sum(self):
        config = HybridConfig(
            grid_capital_pct=0.5,
            dca_capital_pct=0.3,
            reserve_pct=0.1,
        )
        with pytest.raises(ValueError, match="sum to 1.0"):
            config.validate()

    def test_config_validation_negative(self):
        config = HybridConfig(
            grid_capital_pct=-0.1,
            dca_capital_pct=1.0,
            reserve_pct=0.1,
        )
        with pytest.raises(ValueError, match="grid_capital_pct"):
            config.validate()


# =============================================================================
# TestHybridStrategy
# =============================================================================


class TestHybridStrategy:
    """Tests for HybridStrategy initialization and basic evaluation."""

    def test_init_starts_in_grid_mode(self):
        hybrid = _make_hybrid()
        assert hybrid.mode == HybridMode.GRID_ONLY
        assert hybrid.mode_since is not None
        assert len(hybrid.transition_history) == 0

    def test_evaluate_in_grid_mode_returns_grid_risk(self):
        hybrid = _make_hybrid()
        state = _make_market_state()
        regime = _make_regime_result()

        action = hybrid.evaluate(
            state,
            atr=Decimal("50"),
            price_move=Decimal("30"),  # Below threshold
            adx=15.0,  # Low ADX
            regime_result=regime,
        )

        assert action.mode == HybridMode.GRID_ONLY
        assert action.grid_risk_result is not None
        assert action.dca_action is None
        assert not action.transition_triggered

    def test_evaluate_in_dca_mode_returns_dca_action(self):
        hybrid = _make_hybrid()
        # Force DCA mode
        hybrid._mode = HybridMode.DCA_ACTIVE
        hybrid._mode_since = datetime.now(timezone.utc) - timedelta(hours=1)

        state = _make_market_state()
        regime = _make_regime_result(
            regime=RegimeType.DOWNTREND,
            strategy=StrategyRecommendation.DCA,
        )

        action = hybrid.evaluate(
            state, atr=Decimal("50"), price_move=Decimal("100"),
            adx=30.0, regime_result=regime,
        )

        assert action.mode == HybridMode.DCA_ACTIVE
        assert action.dca_action is not None

    def test_get_status(self):
        hybrid = _make_hybrid()
        status = hybrid.get_status()

        assert status["mode"] == "grid_only"
        assert "mode_since" in status
        assert "mode_duration_seconds" in status
        assert status["last_transition"] is None
        assert "config" in status

    def test_get_statistics(self):
        hybrid = _make_hybrid()
        stats = hybrid.get_statistics()

        assert stats["total_transitions"] == 0
        assert stats["grid_to_dca_count"] == 0
        assert stats["dca_to_grid_count"] == 0
        assert stats["current_mode"] == "grid_only"


# =============================================================================
# TestGridToDcaTransition
# =============================================================================


class TestGridToDcaTransition:
    """Tests for Grid→DCA transition."""

    def test_breakout_triggers_transition(self):
        hybrid = _make_hybrid()
        state = _make_market_state()

        # Large price move + high ADX → DEACTIVATE → transition
        action = hybrid.evaluate(
            state,
            atr=Decimal("50"),
            price_move=Decimal("120"),  # 2.4x ATR > 2.0 threshold
            adx=30.0,  # > 25.0 threshold
            regime_result=_make_regime_result(
                regime=RegimeType.DOWNTREND,
                strategy=StrategyRecommendation.DCA,
            ),
        )

        assert action.transition_triggered
        assert action.mode == HybridMode.DCA_ACTIVE
        assert action.transition_event is not None
        assert action.transition_event.from_mode == HybridMode.GRID_ONLY
        assert action.transition_event.to_mode == HybridMode.DCA_ACTIVE
        assert hybrid.mode == HybridMode.DCA_ACTIVE

    def test_breakout_blocked_by_cooldown(self):
        hybrid = _make_hybrid(transition_cooldown=300)
        # Simulate recent transition
        hybrid._last_transition = datetime.now(timezone.utc)

        state = _make_market_state()
        action = hybrid.evaluate(
            state,
            atr=Decimal("50"),
            price_move=Decimal("120"),
            adx=30.0,
            regime_result=_make_regime_result(),
        )

        assert not action.transition_triggered
        assert hybrid.mode == HybridMode.GRID_ONLY

    def test_breakout_blocked_by_min_duration(self):
        hybrid = _make_hybrid(min_grid_duration=300)
        # Mode just started (recently)
        hybrid._mode_since = datetime.now(timezone.utc)

        state = _make_market_state()
        action = hybrid.evaluate(
            state,
            atr=Decimal("50"),
            price_move=Decimal("120"),
            adx=30.0,
            regime_result=_make_regime_result(),
        )

        assert not action.transition_triggered
        assert hybrid.mode == HybridMode.GRID_ONLY

    def test_breakout_requires_adx_confirmation(self):
        hybrid = _make_hybrid(breakout_adx=25.0)
        state = _make_market_state()

        # Large price move but low ADX
        action = hybrid.evaluate(
            state,
            atr=Decimal("50"),
            price_move=Decimal("120"),  # ATR ratio triggers DEACTIVATE
            adx=15.0,  # Below breakout threshold
            regime_result=_make_regime_result(),
        )

        assert not action.transition_triggered
        assert hybrid.mode == HybridMode.GRID_ONLY

    def test_transition_event_recorded(self):
        hybrid = _make_hybrid()
        state = _make_market_state()

        hybrid.evaluate(
            state,
            atr=Decimal("50"),
            price_move=Decimal("120"),
            adx=30.0,
            regime_result=_make_regime_result(),
        )

        assert len(hybrid.transition_history) == 1
        event = hybrid.transition_history[0]
        assert event.from_mode == HybridMode.GRID_ONLY
        assert event.to_mode == HybridMode.DCA_ACTIVE
        assert event.trigger_adx == 30.0

    def test_mode_changes_to_dca_active(self):
        hybrid = _make_hybrid()
        state = _make_market_state()

        assert hybrid.mode == HybridMode.GRID_ONLY
        hybrid.evaluate(
            state,
            atr=Decimal("50"),
            price_move=Decimal("120"),
            adx=30.0,
            regime_result=_make_regime_result(),
        )
        assert hybrid.mode == HybridMode.DCA_ACTIVE

    def test_grid_not_active_after_transition(self):
        hybrid = _make_hybrid()
        state = _make_market_state()

        # Trigger Grid→DCA
        hybrid.evaluate(
            state,
            atr=Decimal("50"),
            price_move=Decimal("120"),
            adx=30.0,
            regime_result=_make_regime_result(),
        )

        # Next evaluation in DCA mode should NOT have grid_risk_result
        action = hybrid.evaluate(
            state,
            atr=Decimal("50"),
            price_move=Decimal("30"),
            adx=30.0,
            regime_result=_make_regime_result(
                regime=RegimeType.DOWNTREND,
                strategy=StrategyRecommendation.DCA,
            ),
        )
        assert action.grid_risk_result is None
        assert action.dca_action is not None


# =============================================================================
# TestDcaToGridTransition
# =============================================================================


class TestDcaToGridTransition:
    """Tests for DCA→Grid transition."""

    def test_return_when_sideways_and_low_adx(self):
        hybrid = _make_hybrid(require_deals_closed=False)
        # Force into DCA mode with enough time elapsed
        hybrid._mode = HybridMode.DCA_ACTIVE
        hybrid._mode_since = datetime.now(timezone.utc) - timedelta(hours=1)

        state = _make_market_state()
        regime = _make_regime_result(
            regime=RegimeType.SIDEWAYS,
            strategy=StrategyRecommendation.GRID,
        )

        action = hybrid.evaluate(
            state,
            atr=Decimal("50"),
            price_move=Decimal("30"),
            adx=15.0,  # Below return threshold (20.0)
            regime_result=regime,
        )

        assert action.transition_triggered
        assert hybrid.mode == HybridMode.GRID_ONLY

    def test_return_blocked_by_open_deals(self):
        hybrid = _make_hybrid(require_deals_closed=True)
        hybrid._mode = HybridMode.DCA_ACTIVE
        hybrid._mode_since = datetime.now(timezone.utc) - timedelta(hours=1)

        # Open a DCA deal
        dca = hybrid._dca_engine
        dca.position_manager.open_deal(entry_price=Decimal("3000"))

        state = _make_market_state()
        regime = _make_regime_result(regime=RegimeType.SIDEWAYS)

        action = hybrid.evaluate(
            state,
            atr=Decimal("50"),
            price_move=Decimal("30"),
            adx=15.0,
            regime_result=regime,
        )

        assert not action.transition_triggered
        assert hybrid.mode == HybridMode.DCA_ACTIVE

    def test_return_blocked_by_min_duration(self):
        hybrid = _make_hybrid(min_dca_duration=600)
        hybrid._mode = HybridMode.DCA_ACTIVE
        hybrid._mode_since = datetime.now(timezone.utc)  # Just started

        state = _make_market_state()
        regime = _make_regime_result(regime=RegimeType.SIDEWAYS)

        action = hybrid.evaluate(
            state,
            atr=Decimal("50"),
            price_move=Decimal("30"),
            adx=15.0,
            regime_result=regime,
        )

        assert not action.transition_triggered
        assert hybrid.mode == HybridMode.DCA_ACTIVE

    def test_return_blocked_by_high_adx(self):
        hybrid = _make_hybrid(return_adx=20.0, require_deals_closed=False)
        hybrid._mode = HybridMode.DCA_ACTIVE
        hybrid._mode_since = datetime.now(timezone.utc) - timedelta(hours=1)

        state = _make_market_state()
        regime = _make_regime_result(regime=RegimeType.SIDEWAYS)

        action = hybrid.evaluate(
            state,
            atr=Decimal("50"),
            price_move=Decimal("30"),
            adx=25.0,  # Above return threshold
            regime_result=regime,
        )

        assert not action.transition_triggered
        assert hybrid.mode == HybridMode.DCA_ACTIVE

    def test_return_blocked_by_wrong_regime(self):
        hybrid = _make_hybrid(require_deals_closed=False)
        hybrid._mode = HybridMode.DCA_ACTIVE
        hybrid._mode_since = datetime.now(timezone.utc) - timedelta(hours=1)

        state = _make_market_state()
        regime = _make_regime_result(
            regime=RegimeType.DOWNTREND,  # Not SIDEWAYS
            strategy=StrategyRecommendation.DCA,
        )

        action = hybrid.evaluate(
            state,
            atr=Decimal("50"),
            price_move=Decimal("30"),
            adx=15.0,  # Low enough, but wrong regime
            regime_result=regime,
        )

        assert not action.transition_triggered
        assert hybrid.mode == HybridMode.DCA_ACTIVE

    def test_full_cycle_grid_dca_grid(self):
        hybrid = _make_hybrid(require_deals_closed=False)
        state = _make_market_state()

        # Step 1: Start in Grid
        assert hybrid.mode == HybridMode.GRID_ONLY

        # Step 2: Breakout → DCA
        hybrid.evaluate(
            state,
            atr=Decimal("50"),
            price_move=Decimal("120"),
            adx=30.0,
            regime_result=_make_regime_result(
                regime=RegimeType.DOWNTREND,
                strategy=StrategyRecommendation.DCA,
            ),
        )
        assert hybrid.mode == HybridMode.DCA_ACTIVE

        # Step 3: Set time to allow return
        hybrid._mode_since = datetime.now(timezone.utc) - timedelta(hours=1)

        # Step 4: Return → Grid
        hybrid.evaluate(
            state,
            atr=Decimal("50"),
            price_move=Decimal("20"),
            adx=15.0,
            regime_result=_make_regime_result(
                regime=RegimeType.SIDEWAYS,
                strategy=StrategyRecommendation.GRID,
            ),
        )
        assert hybrid.mode == HybridMode.GRID_ONLY

        # Step 5: Check history
        stats = hybrid.get_statistics()
        assert stats["total_transitions"] == 2
        assert stats["grid_to_dca_count"] == 1
        assert stats["dca_to_grid_count"] == 1

    def test_transition_history_tracking(self):
        hybrid = _make_hybrid(require_deals_closed=False)
        state = _make_market_state()

        # Transition 1: Grid→DCA
        hybrid.evaluate(
            state,
            atr=Decimal("50"),
            price_move=Decimal("120"),
            adx=30.0,
            regime_result=_make_regime_result(),
        )

        assert len(hybrid.transition_history) == 1
        assert hybrid.transition_history[0].to_mode == HybridMode.DCA_ACTIVE


# =============================================================================
# TestHybridEdgeCases
# =============================================================================


class TestHybridEdgeCases:
    """Tests for edge cases and safety mechanisms."""

    def test_rapid_oscillation_prevented(self):
        hybrid = _make_hybrid(transition_cooldown=300, require_deals_closed=False)
        state = _make_market_state()

        # Trigger Grid→DCA
        hybrid.evaluate(
            state,
            atr=Decimal("50"),
            price_move=Decimal("120"),
            adx=30.0,
            regime_result=_make_regime_result(),
        )
        assert hybrid.mode == HybridMode.DCA_ACTIVE

        # Try immediate return → blocked by cooldown
        hybrid._mode_since = datetime.now(timezone.utc) - timedelta(hours=1)
        action = hybrid.evaluate(
            state,
            atr=Decimal("50"),
            price_move=Decimal("20"),
            adx=15.0,
            regime_result=_make_regime_result(regime=RegimeType.SIDEWAYS),
        )
        assert not action.transition_triggered
        assert hybrid.mode == HybridMode.DCA_ACTIVE

    def test_evaluate_with_none_adx(self):
        hybrid = _make_hybrid()
        state = _make_market_state()

        # No ADX → grid risk check still runs (no ADX-based deactivation)
        action = hybrid.evaluate(
            state,
            atr=Decimal("50"),
            price_move=Decimal("30"),
            adx=None,
            regime_result=_make_regime_result(),
        )

        assert action.mode == HybridMode.GRID_ONLY
        assert not action.transition_triggered

    def test_transition_history_max_size(self):
        config = HybridConfig(
            transition_cooldown_seconds=0,
            min_grid_duration_seconds=0,
            min_dca_duration_seconds=0,
            max_transition_history=3,
            require_dca_deals_closed=False,
        )
        hybrid = HybridStrategy(
            config=config,
            grid_risk_manager=GridRiskManager(),
            dca_engine=_make_dca_engine(),
            regime_detector=MarketRegimeDetectorV2(),
        )
        state = _make_market_state()

        for i in range(5):
            if hybrid.mode == HybridMode.GRID_ONLY:
                hybrid.evaluate(
                    state,
                    atr=Decimal("50"),
                    price_move=Decimal("120"),
                    adx=30.0,
                    regime_result=_make_regime_result(
                        regime=RegimeType.DOWNTREND,
                        strategy=StrategyRecommendation.DCA,
                    ),
                )
            else:
                hybrid._mode_since = datetime.now(timezone.utc) - timedelta(hours=1)
                hybrid.evaluate(
                    state,
                    atr=Decimal("50"),
                    price_move=Decimal("20"),
                    adx=15.0,
                    regime_result=_make_regime_result(
                        regime=RegimeType.SIDEWAYS,
                        strategy=StrategyRecommendation.GRID,
                    ),
                )

        assert len(hybrid.transition_history) <= 3

    def test_transition_event_serialization(self):
        event = TransitionEvent(
            from_mode=HybridMode.GRID_ONLY,
            to_mode=HybridMode.DCA_ACTIVE,
            reason="Test breakout",
            timestamp=datetime.now(timezone.utc),
            trigger_adx=30.0,
            trigger_atr_ratio=2.4,
        )
        d = event.to_dict()

        assert d["from_mode"] == "grid_only"
        assert d["to_mode"] == "dca_active"
        assert d["reason"] == "Test breakout"
        assert d["trigger_adx"] == 30.0

    def test_hybrid_action_serialization(self):
        action = HybridAction(
            mode=HybridMode.GRID_ONLY,
            warnings=["test warning"],
        )
        d = action.to_dict()

        assert d["mode"] == "grid_only"
        assert d["transition_triggered"] is False
        assert "test warning" in d["warnings"]
