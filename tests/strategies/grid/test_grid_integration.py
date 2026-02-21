"""Integration tests for Grid Strategy v2.0.

Tests the full grid lifecycle with mock exchange:
- Config → Calculator → Order Manager → Risk Manager flow
- Full buy→sell cycle with profit
- Risk triggers during operation
- Rebalancing scenarios
- ATR-based grid with simulated price data
"""

from decimal import Decimal

import pytest

from bot.strategies.grid.grid_calculator import (
    GridCalculator,
    GridConfig,
    GridSpacing,
)
from bot.strategies.grid.grid_config import (
    GridStrategyConfig,
    VolatilityMode,
)
from bot.strategies.grid.grid_order_manager import (
    GridOrderManager,
)
from bot.strategies.grid.grid_risk_manager import (
    GridRiskAction,
    GridRiskManager,
)

# =========================================================================
# Mock Exchange
# =========================================================================


class MockExchange:
    """Simulates exchange order operations for integration tests."""

    def __init__(self):
        self._order_counter = 0
        self._orders: dict[str, dict] = {}

    async def place_limit_order(self, symbol: str, side: str, amount: float, price: float) -> dict:
        self._order_counter += 1
        order_id = f"MOCK-{self._order_counter:04d}"
        self._orders[order_id] = {
            "id": order_id,
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "price": price,
            "status": "open",
        }
        return {"id": order_id, "status": "open"}

    async def cancel_order(self, order_id: str, symbol: str) -> dict:
        if order_id in self._orders:
            self._orders[order_id]["status"] = "cancelled"
        return {"id": order_id, "status": "cancelled"}

    def simulate_fill(self, order_id: str) -> dict | None:
        """Simulate an order being filled."""
        if order_id not in self._orders:
            return None
        order = self._orders[order_id]
        order["status"] = "filled"
        return {
            "id": order_id,
            "price": order["price"],
            "amount": order["amount"],
            "status": "filled",
        }


# =========================================================================
# Integration Tests — Full Lifecycle
# =========================================================================


class TestGridFullLifecycle:
    """Test complete grid strategy flow: config → calculate → place → fill → profit."""

    @pytest.mark.asyncio
    async def test_full_lifecycle_arithmetic(self):
        """Full lifecycle with arithmetic grid."""
        exchange = MockExchange()

        # 1. Create config
        strategy_config = GridStrategyConfig(
            symbol="BTC/USDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            num_levels=11,
            grid_spacing="arithmetic",
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.01"),
        )

        # 2. Setup components
        grid_config = strategy_config.to_grid_config()
        risk_config = strategy_config.to_risk_config()
        manager = GridOrderManager(symbol="BTC/USDT")
        risk_mgr = GridRiskManager(config=risk_config)
        risk_mgr.set_grid_entry_price(Decimal("45000"))

        # 3. Calculate initial orders
        current_price = Decimal("45000")
        orders = manager.calculate_initial_orders(grid_config, current_price)
        buys = [o for o in orders if o.grid_level.side == "buy"]
        sells = [o for o in orders if o.grid_level.side == "sell"]
        assert len(buys) == 5  # 40k, 41k, 42k, 43k, 44k
        assert len(sells) == 5  # 46k, 47k, 48k, 49k, 50k

        # 4. Place orders (with risk check)
        for order in orders:
            quote_value = order.grid_level.price * order.grid_level.amount
            risk_check = risk_mgr.validate_order_size(quote_value, Decimal("0"), 0)
            assert risk_check.is_safe

            result = await exchange.place_limit_order(
                "BTC/USDT",
                order.grid_level.side,
                float(order.grid_level.amount),
                float(order.grid_level.price),
            )
            manager.register_exchange_order(order.id, result["id"])

        assert len(manager.active_orders) == 10

        # 5. Simulate buy fill
        buy_order = buys[0]
        fill_data = exchange.simulate_fill(buy_order.exchange_order_id)
        counter = manager.on_order_filled(
            buy_order.exchange_order_id,
            buy_order.grid_level.price,
            buy_order.grid_level.amount,
        )
        assert counter is not None
        assert counter.grid_level.side == "sell"

        # 6. Place counter-order
        counter_result = await exchange.place_limit_order(
            "BTC/USDT",
            counter.grid_level.side,
            float(counter.grid_level.amount),
            float(counter.grid_level.price),
        )
        manager.register_exchange_order(counter.id, counter_result["id"])

        # 7. Simulate counter sell fill
        exchange.simulate_fill(counter.exchange_order_id)
        counter2 = manager.on_order_filled(
            counter.exchange_order_id,
            counter.grid_level.price,
            counter.grid_level.amount,
        )

        # 8. Verify profit
        completed = manager.completed_cycles
        assert len(completed) == 1
        assert completed[0].profit > 0
        assert manager.total_realized_pnl > 0

    @pytest.mark.asyncio
    async def test_full_lifecycle_geometric(self):
        """Full lifecycle with geometric grid."""
        config = GridStrategyConfig.from_preset("ETH/USDT", VolatilityMode.HIGH)
        config = GridStrategyConfig(
            symbol="ETH/USDT",
            upper_price=Decimal("4000"),
            lower_price=Decimal("3000"),
            num_levels=10,
            grid_spacing="geometric",
            amount_per_grid=Decimal("200"),
            profit_per_grid=Decimal("0.01"),
        )

        grid_config = config.to_grid_config()
        manager = GridOrderManager(symbol="ETH/USDT")
        orders = manager.calculate_initial_orders(grid_config, Decimal("3500"))

        # Verify geometric spacing
        levels = GridCalculator.calculate_geometric_levels(Decimal("4000"), Decimal("3000"), 10)
        pcts = GridCalculator.grid_spacing_pct(levels)
        # All percentage gaps should be approximately equal
        avg_pct = sum(pcts) / len(pcts)
        for pct in pcts:
            assert abs(pct - avg_pct) < Decimal("0.5")

        assert len(orders) > 0


# =========================================================================
# Integration Tests — Risk Triggers
# =========================================================================


class TestGridRiskIntegration:
    def test_stop_loss_during_operation(self):
        """Grid should stop when price moves too far."""
        config = GridStrategyConfig.from_preset("BTC/USDT", VolatilityMode.MEDIUM)
        risk_mgr = GridRiskManager(config=config.to_risk_config())
        risk_mgr.set_grid_entry_price(Decimal("45000"))

        # Small move — safe
        result = risk_mgr.check_grid_stop_loss(Decimal("44000"))
        assert result.is_safe

        # Big move — stop loss (>5%)
        result = risk_mgr.check_grid_stop_loss(Decimal("42000"))
        assert result.action == GridRiskAction.STOP_LOSS

    def test_trend_detection_deactivates_grid(self):
        """Grid should deactivate in strong trend."""
        config = GridStrategyConfig.from_preset("BTC/USDT", VolatilityMode.MEDIUM)
        risk_mgr = GridRiskManager(config=config.to_risk_config())

        # Ranging — safe
        result = risk_mgr.check_trend_suitability(atr=Decimal("500"), price_move=Decimal("400"))
        assert result.is_safe

        # Strong trend — deactivate
        result = risk_mgr.check_trend_suitability(atr=Decimal("500"), price_move=Decimal("1200"))
        assert result.action == GridRiskAction.DEACTIVATE

    def test_consecutive_losses_pause(self):
        """Grid should pause after too many losses."""
        config = GridStrategyConfig.from_preset("BTC/USDT", VolatilityMode.MEDIUM)
        risk_mgr = GridRiskManager(config=config.to_risk_config())

        for _ in range(5):
            risk_mgr.record_trade_result(Decimal("-20"))

        result = risk_mgr.check_consecutive_losses()
        assert result.action == GridRiskAction.PAUSE

    def test_comprehensive_risk_evaluation(self):
        """Test evaluate_risk with multiple conditions."""
        config = GridStrategyConfig.from_preset("BTC/USDT", VolatilityMode.MEDIUM)
        risk_mgr = GridRiskManager(config=config.to_risk_config())
        risk_mgr.set_grid_entry_price(Decimal("45000"))

        # All safe
        result = risk_mgr.evaluate_risk(
            current_price=Decimal("45000"),
            current_equity=Decimal("10000"),
            current_exposure=Decimal("5000"),
            open_orders=10,
            atr=Decimal("500"),
            price_move=Decimal("300"),
            available_balance=Decimal("5000"),
            total_balance=Decimal("10000"),
        )
        assert result.is_safe


# =========================================================================
# Integration Tests — Rebalancing
# =========================================================================


class TestGridRebalanceIntegration:
    @pytest.mark.asyncio
    async def test_rebalance_on_price_movement(self):
        """Test grid rebalance when price moves significantly."""
        exchange = MockExchange()
        manager = GridOrderManager(symbol="BTC/USDT")

        # Initial grid at 45000
        config1 = GridConfig(
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            num_levels=11,
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.01"),
        )
        orders = manager.calculate_initial_orders(config1, Decimal("45000"))
        for o in orders:
            result = await exchange.place_limit_order(
                "BTC/USDT",
                o.grid_level.side,
                float(o.grid_level.amount),
                float(o.grid_level.price),
            )
            manager.register_exchange_order(o.id, result["id"])

        initial_active = len(manager.active_orders)
        assert initial_active == 10

        # Price moved to 48000 — rebalance
        config2 = GridConfig(
            upper_price=Decimal("53000"),
            lower_price=Decimal("43000"),
            num_levels=11,
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.01"),
        )

        cancelled, new_orders = manager.rebalance(config2, Decimal("48000"))

        # Cancel old orders on exchange
        for o in cancelled:
            if o.exchange_order_id:
                await exchange.cancel_order(o.exchange_order_id, "BTC/USDT")

        # Place new orders
        for o in new_orders:
            result = await exchange.place_limit_order(
                "BTC/USDT",
                o.grid_level.side,
                float(o.grid_level.amount),
                float(o.grid_level.price),
            )
            manager.register_exchange_order(o.id, result["id"])

        assert len(cancelled) == initial_active
        assert len(manager.active_orders) == len(new_orders)


# =========================================================================
# Integration Tests — ATR-Based Grid
# =========================================================================


class TestATRGridIntegration:
    @pytest.fixture
    def price_data(self):
        """30 bars of BTC-like price data."""
        base = 45000
        highs, lows, closes = [], [], []
        for i in range(30):
            h = Decimal(str(base + 300 + (i % 7) * 50))
            low = Decimal(str(base - 300 - (i % 5) * 40))
            c = Decimal(str(base + (i % 9) * 30 - 120))
            highs.append(h)
            lows.append(low)
            closes.append(c)
        return highs, lows, closes

    def test_atr_grid_full_setup(self, price_data):
        """Test ATR-based grid calculation and order manager setup."""
        highs, lows, closes = price_data
        current_price = Decimal("45000")

        # Calculate ATR grid
        orders, meta = GridCalculator.calculate_atr_grid(
            current_price=current_price,
            highs=highs,
            lows=lows,
            closes=closes,
            atr_period=14,
            atr_multiplier=Decimal("3"),
            spacing=GridSpacing.ARITHMETIC,
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.005"),
        )

        assert len(orders) > 0
        assert Decimal(meta["atr"]) > 0

        # Setup order manager
        manager = GridOrderManager(symbol="BTC/USDT")
        config = GridConfig(
            upper_price=Decimal(meta["upper_price"]),
            lower_price=Decimal(meta["lower_price"]),
            num_levels=meta["num_levels"],
            spacing=GridSpacing.ARITHMETIC,
            amount_per_grid=Decimal("100"),
            profit_per_grid=Decimal("0.005"),
        )
        order_states = manager.calculate_initial_orders(config, current_price)
        assert len(order_states) > 0

        # Verify risk check passes
        risk_mgr = GridRiskManager()
        risk_mgr.set_grid_entry_price(current_price)
        result = risk_mgr.evaluate_risk(
            current_price=current_price,
            current_equity=Decimal("10000"),
            current_exposure=Decimal("0"),
            open_orders=0,
        )
        assert result.is_safe


# =========================================================================
# Integration Tests — Config Presets with Components
# =========================================================================


class TestPresetIntegration:
    def test_low_volatility_setup(self):
        """Low volatility preset should produce tight grid."""
        cfg = GridStrategyConfig.from_preset(
            "USDT/DAI",
            VolatilityMode.LOW,
            upper_price="1.005",
            lower_price="0.995",
        )
        grid_config = cfg.to_grid_config()
        assert grid_config is not None
        assert grid_config.num_levels == 20
        assert grid_config.spacing == GridSpacing.ARITHMETIC

        levels = GridCalculator.calculate_levels(
            grid_config.upper_price,
            grid_config.lower_price,
            grid_config.num_levels,
            grid_config.spacing,
        )
        # Tight spread
        assert levels[-1] - levels[0] == Decimal("0.01")

    def test_high_volatility_geometric(self):
        """High volatility preset should use geometric grid."""
        cfg = GridStrategyConfig.from_preset(
            "SOL/USDT",
            VolatilityMode.HIGH,
            upper_price="200",
            lower_price="100",
        )
        grid_config = cfg.to_grid_config()
        assert grid_config is not None
        assert grid_config.spacing == GridSpacing.GEOMETRIC

        levels = GridCalculator.calculate_geometric_levels(
            grid_config.upper_price,
            grid_config.lower_price,
            grid_config.num_levels,
        )
        # Geometric: denser at lower prices
        gaps = [levels[i] - levels[i - 1] for i in range(1, len(levels))]
        for i in range(1, len(gaps)):
            assert gaps[i] > gaps[i - 1]

    def test_medium_preset_risk_matches(self):
        """Medium preset risk config should match expected values."""
        cfg = GridStrategyConfig.from_preset("BTC/USDT", VolatilityMode.MEDIUM)
        risk = cfg.to_risk_config()
        assert risk.max_total_exposure == Decimal("10000")
        assert risk.grid_stop_loss_pct == Decimal("0.05")
        assert risk.trend_adx_threshold == 25.0

    def test_all_presets_produce_valid_risk_config(self):
        """All presets should produce valid risk configs."""
        for mode in [VolatilityMode.LOW, VolatilityMode.MEDIUM, VolatilityMode.HIGH]:
            cfg = GridStrategyConfig.from_preset("BTC/USDT", mode)
            risk = cfg.to_risk_config()
            risk.validate()  # should not raise


# =========================================================================
# Statistics Integration
# =========================================================================


class TestStatisticsIntegration:
    def test_combined_statistics(self):
        """Test getting statistics from all components."""
        manager = GridOrderManager(symbol="BTC/USDT")
        config = GridConfig(
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            num_levels=11,
            amount_per_grid=Decimal("100"),
        )
        manager.calculate_initial_orders(config, Decimal("45000"))
        om_stats = manager.get_statistics()

        risk_mgr = GridRiskManager()
        risk_mgr.set_grid_entry_price(Decimal("45000"))
        rm_stats = risk_mgr.get_statistics()

        # Verify both have expected keys
        assert "total_orders" in om_stats
        assert "active_orders" in om_stats
        assert "peak_equity" in rm_stats
        assert "grid_entry_price" in rm_stats
