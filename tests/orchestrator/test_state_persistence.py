"""Tests for state_persistence serialization and BotOrchestrator integration."""

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.core.dca_engine import DCAEngine, DCAPosition
from bot.core.grid_engine import GridEngine, GridOrder, GridType
from bot.core.risk_manager import RiskManager
from bot.database.models_state import BotStateSnapshot
from bot.orchestrator.state_persistence import (
    DecimalEncoder,
    deserialize_dca_state,
    deserialize_grid_state,
    deserialize_hybrid_state,
    deserialize_risk_state,
    deserialize_trend_state,
    serialize_dca_state,
    serialize_grid_state,
    serialize_hybrid_state,
    serialize_risk_state,
    serialize_trend_state,
)


# ---------------------------------------------------------------------------
# DecimalEncoder
# ---------------------------------------------------------------------------


class TestDecimalEncoder:
    def test_decimal(self):
        result = json.dumps({"v": Decimal("1.23")}, cls=DecimalEncoder)
        assert '"1.23"' in result

    def test_datetime(self):
        dt = datetime(2025, 1, 1, 12, 0, 0)
        result = json.dumps({"v": dt}, cls=DecimalEncoder)
        assert "2025-01-01" in result


# ---------------------------------------------------------------------------
# Grid round-trip
# ---------------------------------------------------------------------------


class TestGridSerialization:
    def _make_engine(self) -> GridEngine:
        return GridEngine(
            symbol="BTC/USDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_levels=5,
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.01"),
        )

    def test_serialize_empty(self):
        engine = self._make_engine()
        result = serialize_grid_state(engine)
        assert result is not None
        data = json.loads(result)
        assert data["active_orders"] == {}
        assert data["total_profit"] == "0"

    def test_none_engine(self):
        assert serialize_grid_state(None) is None

    def test_round_trip_with_orders(self):
        engine = self._make_engine()
        order = GridOrder(level=1, price=Decimal("42000"), amount=Decimal("0.002"), side="buy")
        engine.active_orders["abc123"] = order
        engine.total_profit = Decimal("15.50")
        engine.buy_count = 3
        engine.sell_count = 2

        json_str = serialize_grid_state(engine)

        engine2 = self._make_engine()
        ok = deserialize_grid_state(engine2, json_str)
        assert ok is True
        assert len(engine2.active_orders) == 1
        restored = engine2.active_orders["abc123"]
        assert restored.level == 1
        assert restored.price == Decimal("42000")
        assert restored.side == "buy"
        assert engine2.total_profit == Decimal("15.50")
        assert engine2.buy_count == 3
        assert engine2.sell_count == 2

    def test_deserialize_none(self):
        engine = self._make_engine()
        assert deserialize_grid_state(engine, None) is False

    def test_deserialize_bad_json(self):
        engine = self._make_engine()
        assert deserialize_grid_state(engine, "not json") is False


# ---------------------------------------------------------------------------
# DCA round-trip
# ---------------------------------------------------------------------------


class TestDCASerialization:
    def _make_engine(self) -> DCAEngine:
        return DCAEngine(
            symbol="BTC/USDT",
            trigger_percentage=Decimal("0.05"),
            amount_per_step=Decimal("100"),
            max_steps=5,
            take_profit_percentage=Decimal("0.10"),
        )

    def test_serialize_no_position(self):
        engine = self._make_engine()
        result = serialize_dca_state(engine)
        data = json.loads(result)
        assert data["position"] is None

    def test_round_trip_with_position(self):
        engine = self._make_engine()
        engine.execute_dca_step(Decimal("50000"))
        engine.execute_dca_step(Decimal("47000"))
        engine.execute_dca_step(Decimal("44000"))

        json_str = serialize_dca_state(engine)

        engine2 = self._make_engine()
        ok = deserialize_dca_state(engine2, json_str)
        assert ok is True
        assert engine2.position is not None
        assert engine2.position.step_number == engine.position.step_number
        assert engine2.position.average_entry_price == engine.position.average_entry_price
        assert engine2.total_dca_steps == engine.total_dca_steps
        assert engine2.last_buy_price == Decimal("44000")

    def test_none_engine(self):
        assert serialize_dca_state(None) is None
        assert deserialize_dca_state(None, "{}") is False


# ---------------------------------------------------------------------------
# Risk Manager round-trip
# ---------------------------------------------------------------------------


class TestRiskSerialization:
    def _make_manager(self) -> RiskManager:
        rm = RiskManager(
            max_position_size=Decimal("10000"),
            min_order_size=Decimal("10"),
            stop_loss_percentage=Decimal("0.20"),
            max_daily_loss=Decimal("500"),
        )
        rm.initialize_balance(Decimal("5000"))
        return rm

    def test_round_trip(self):
        rm = self._make_manager()
        rm.daily_loss = Decimal("123.45")
        rm.is_halted = True
        rm.halt_reason = "test halt"
        rm.total_trades = 42
        rm.rejected_trades = 3
        rm.stop_loss_triggers = 1

        json_str = serialize_risk_state(rm)
        rm2 = self._make_manager()
        ok = deserialize_risk_state(rm2, json_str)

        assert ok is True
        assert rm2.daily_loss == Decimal("123.45")
        assert rm2.is_halted is True
        assert rm2.halt_reason == "test halt"
        assert rm2.total_trades == 42
        assert rm2.rejected_trades == 3
        assert rm2.stop_loss_triggers == 1

    def test_none(self):
        assert serialize_risk_state(None) is None
        assert deserialize_risk_state(None, "{}") is False


# ---------------------------------------------------------------------------
# Trend-Follower round-trip
# ---------------------------------------------------------------------------


class TestTrendSerialization:
    def _make_strategy(self):
        mock = MagicMock()
        mock.risk_manager = MagicMock()
        mock.risk_manager.current_capital = Decimal("9000")
        mock.risk_manager.consecutive_losses = 2
        mock.risk_manager.daily_pnl = Decimal("-50")
        mock.risk_manager.daily_trades = 5
        return mock

    def test_round_trip(self):
        strategy = self._make_strategy()
        json_str = serialize_trend_state(strategy)
        assert json_str is not None

        strategy2 = self._make_strategy()
        ok = deserialize_trend_state(strategy2, json_str)
        assert ok is True
        assert strategy2.risk_manager.current_capital == Decimal("9000")
        assert strategy2.risk_manager.consecutive_losses == 2
        assert strategy2.risk_manager.daily_pnl == Decimal("-50")
        assert strategy2.risk_manager.daily_trades == 5

    def test_none(self):
        assert serialize_trend_state(None) is None
        assert deserialize_trend_state(None, "{}") is False

    def test_no_risk_manager(self):
        mock = MagicMock(spec=[])
        del mock.risk_manager
        assert serialize_trend_state(mock) is None


# ---------------------------------------------------------------------------
# Hybrid Strategy round-trip
# ---------------------------------------------------------------------------


class TestHybridSerialization:
    def _make_strategy(self):
        from bot.strategies.hybrid.hybrid_config import HybridConfig, HybridMode
        from bot.strategies.hybrid.hybrid_strategy import HybridStrategy

        strategy = HybridStrategy(config=HybridConfig())
        return strategy

    def test_serialize_default(self):
        strategy = self._make_strategy()
        result = serialize_hybrid_state(strategy)
        assert result is not None
        data = json.loads(result)
        assert data["mode"] == "grid_only"
        assert data["total_transitions"] == 0
        assert data["last_transition"] is None
        assert "regime_detector" in data

    def test_none_strategy(self):
        assert serialize_hybrid_state(None) is None

    def test_round_trip(self):
        from bot.strategies.hybrid.hybrid_config import HybridMode
        from bot.strategies.hybrid.market_regime_detector import RegimeType, StrategyRecommendation

        strategy = self._make_strategy()
        # Simulate some state changes
        strategy._mode = HybridMode.DCA_ACTIVE
        strategy._total_transitions = 3
        strategy._grid_to_dca_count = 2
        strategy._dca_to_grid_count = 1
        strategy._last_transition = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        strategy._regime_detector._current_regime = RegimeType.DOWNTREND
        strategy._regime_detector._current_strategy = StrategyRecommendation.DCA
        strategy._regime_detector._evaluation_count = 42

        json_str = serialize_hybrid_state(strategy)

        strategy2 = self._make_strategy()
        ok = deserialize_hybrid_state(strategy2, json_str)
        assert ok is True
        assert strategy2._mode == HybridMode.DCA_ACTIVE
        assert strategy2._total_transitions == 3
        assert strategy2._grid_to_dca_count == 2
        assert strategy2._dca_to_grid_count == 1
        assert strategy2._last_transition == datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert strategy2._regime_detector._current_regime == RegimeType.DOWNTREND
        assert strategy2._regime_detector._current_strategy == StrategyRecommendation.DCA
        assert strategy2._regime_detector._evaluation_count == 42

    def test_deserialize_none(self):
        strategy = self._make_strategy()
        assert deserialize_hybrid_state(strategy, None) is False

    def test_deserialize_bad_json(self):
        strategy = self._make_strategy()
        assert deserialize_hybrid_state(strategy, "not json") is False

    def test_deserialize_none_strategy(self):
        assert deserialize_hybrid_state(None, '{"mode": "grid_only"}') is False


# ---------------------------------------------------------------------------
# BotOrchestrator integration (mocked DB)
# ---------------------------------------------------------------------------


class TestOrchestratorStatePersistence:
    """Test that BotOrchestrator.save_state / load_state / reconcile work."""

    def _make_orchestrator(self):
        from bot.orchestrator.bot_orchestrator import BotOrchestrator

        config = MagicMock()
        config.name = "test_bot"
        config.symbol = "BTC/USDT"
        config.strategy = "grid"
        config.dry_run = False
        config.risk_management = None
        config.grid = None
        config.dca = None
        config.trend_follower = None

        exchange = AsyncMock()
        db = AsyncMock()
        db.save_state_snapshot = AsyncMock()
        db.load_state_snapshot = AsyncMock(return_value=None)

        orch = BotOrchestrator(
            bot_config=config,
            exchange_client=exchange,
            db_manager=db,
            redis_url="redis://localhost:6379",
        )
        return orch

    @pytest.mark.asyncio
    async def test_save_state_calls_db(self):
        orch = self._make_orchestrator()
        await orch.save_state()
        orch.db.save_state_snapshot.assert_called_once()
        snapshot = orch.db.save_state_snapshot.call_args[0][0]
        assert snapshot.bot_name == "test_bot"

    @pytest.mark.asyncio
    async def test_load_state_no_snapshot(self):
        orch = self._make_orchestrator()
        orch.db.load_state_snapshot.return_value = None
        await orch.load_state()
        assert orch._state_loaded is False

    @pytest.mark.asyncio
    async def test_load_state_with_grid(self):
        orch = self._make_orchestrator()
        orch.grid_engine = GridEngine(
            symbol="BTC/USDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_levels=5,
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.01"),
        )

        grid_data = json.dumps({
            "active_orders": {
                "order1": {
                    "level": 0,
                    "price": "41000",
                    "amount": "0.002",
                    "side": "buy",
                    "order_id": "order1",
                    "filled": False,
                }
            },
            "total_profit": "10.5",
            "buy_count": 2,
            "sell_count": 1,
        })

        snapshot = BotStateSnapshot(
            bot_name="test_bot",
            bot_state="running",
            grid_state=grid_data,
            saved_at=datetime.now(timezone.utc),
        )
        orch.db.load_state_snapshot.return_value = snapshot

        await orch.load_state()
        assert orch._state_loaded is True
        assert "order1" in orch.grid_engine.active_orders
        assert orch.grid_engine.total_profit == Decimal("10.5")

    @pytest.mark.asyncio
    async def test_reconcile_removes_orphans(self):
        orch = self._make_orchestrator()
        orch.grid_engine = GridEngine(
            symbol="BTC/USDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_levels=5,
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.01"),
        )
        # Simulate loaded state with an order that no longer exists
        order = GridOrder(level=0, price=Decimal("41000"), amount=Decimal("0.002"), side="buy")
        orch.grid_engine.active_orders["orphan_order"] = order

        orch.exchange.fetch_open_orders = AsyncMock(return_value=[])
        orch.exchange.fetch_order = AsyncMock(return_value={"status": "canceled"})

        await orch.reconcile_with_exchange()

        assert "orphan_order" not in orch.grid_engine.active_orders

    @pytest.mark.asyncio
    async def test_reconcile_handles_filled(self):
        orch = self._make_orchestrator()
        orch.grid_engine = GridEngine(
            symbol="BTC/USDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_levels=5,
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.01"),
        )
        order = GridOrder(level=0, price=Decimal("41000"), amount=Decimal("0.002"), side="buy")
        orch.grid_engine.active_orders["filled_order"] = order

        orch.exchange.fetch_open_orders = AsyncMock(return_value=[])
        orch.exchange.fetch_order = AsyncMock(return_value={"status": "closed"})

        await orch.reconcile_with_exchange()

        # Order should have been handled as filled
        assert "filled_order" not in orch.grid_engine.active_orders
        assert orch.grid_engine.buy_count == 1

    @pytest.mark.asyncio
    async def test_stop_calls_save_state(self):
        orch = self._make_orchestrator()
        orch.state = MagicMock()
        orch.state.__eq__ = lambda s, o: False  # not STOPPED
        orch.state.value = "running"

        # Patch to bypass actual state lock and stop logic
        with patch.object(orch, 'save_state', new_callable=AsyncMock) as mock_save:
            with patch.object(orch, '_cancel_all_orders', new_callable=AsyncMock):
                with patch.object(orch, '_publish_event', new_callable=AsyncMock):
                    with patch.object(orch, 'health_monitor') as mock_hm:
                        mock_hm.stop = AsyncMock()
                        with patch.object(orch, 'strategy_registry') as mock_sr:
                            mock_sr.stop_all = AsyncMock()
                            # Direct call to stop (bypass state lock for test)
                            orch._running = True
                            orch._main_task = None
                            orch._price_monitor_task = None
                            orch._regime_monitor_task = None
                            # Release lock manually
                            orch._state_lock = asyncio.Lock()
                            from bot.orchestrator.bot_orchestrator import BotState
                            orch.state = BotState.RUNNING
                            await orch.stop()
                            mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_reset_state_deletes_snapshot(self):
        orch = self._make_orchestrator()
        orch.db.delete_state_snapshot = AsyncMock(return_value=True)
        orch._state_loaded = True

        await orch.reset_state()

        orch.db.delete_state_snapshot.assert_called_once_with("test_bot")
        assert orch._state_loaded is False

    @pytest.mark.asyncio
    async def test_save_state_includes_hybrid_state(self):
        orch = self._make_orchestrator()
        await orch.save_state()
        snapshot = orch.db.save_state_snapshot.call_args[0][0]
        # hybrid_strategy is None, so hybrid_state should be None
        assert snapshot.hybrid_state is None
