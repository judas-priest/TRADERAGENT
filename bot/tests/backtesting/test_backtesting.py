"""Tests for backtesting framework"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from bot.tests.backtesting.market_simulator import MarketSimulator, OrderSide, OrderStatus
from bot.tests.backtesting.backtesting_engine import BacktestingEngine
from bot.tests.backtesting.test_data import HistoricalDataProvider


class TestMarketSimulator:
    """Test market simulator functionality"""

    @pytest.fixture
    def simulator(self):
        return MarketSimulator(
            symbol="BTC/USDT",
            initial_balance_quote=Decimal("10000"),
        )

    @pytest.mark.asyncio
    async def test_market_buy_order(self, simulator):
        """Test market buy order execution"""
        simulator.set_price(Decimal("45000"))

        order = await simulator.create_order(
            symbol="BTC/USDT",
            order_type="market",
            side="buy",
            amount=Decimal("0.1"),
        )

        assert order["status"] == "closed"
        assert float(order["filled"]) == 0.1

        # Check balance updated
        balance = simulator.get_balance()
        assert balance["BTC"]["total"] > 0  # Should have BTC now
        assert balance["USDT"]["total"] < 10000  # USDT should decrease

    @pytest.mark.asyncio
    async def test_market_sell_order(self, simulator):
        """Test market sell order execution"""
        simulator.set_price(Decimal("45000"))

        # First buy some BTC
        await simulator.create_order(
            symbol="BTC/USDT",
            order_type="market",
            side="buy",
            amount=Decimal("0.1"),
        )

        # Now sell it
        order = await simulator.create_order(
            symbol="BTC/USDT",
            order_type="market",
            side="sell",
            amount=Decimal("0.1"),
        )

        assert order["status"] == "closed"
        balance = simulator.get_balance()
        assert balance["BTC"]["total"] < 0.1  # BTC sold

    @pytest.mark.asyncio
    async def test_limit_buy_order(self, simulator):
        """Test limit buy order creation and execution"""
        simulator.set_price(Decimal("45000"))

        # Place limit buy below current price
        order = await simulator.create_order(
            symbol="BTC/USDT",
            order_type="limit",
            side="buy",
            amount=Decimal("0.1"),
            price=Decimal("44000"),
        )

        # Should be open (not executed yet)
        assert order["status"] == "open"

        # Price drops, order should execute
        simulator.set_price(Decimal("44000"))

        # Check order was executed
        updated_order = simulator.get_order(order["id"])
        assert updated_order["status"] == "closed"

    @pytest.mark.asyncio
    async def test_limit_sell_order(self, simulator):
        """Test limit sell order"""
        simulator.set_price(Decimal("45000"))

        # Buy some BTC first
        await simulator.create_order(
            symbol="BTC/USDT",
            order_type="market",
            side="buy",
            amount=Decimal("0.1"),
        )

        # Place limit sell above current price
        order = await simulator.create_order(
            symbol="BTC/USDT",
            order_type="limit",
            side="sell",
            amount=Decimal("0.1"),
            price=Decimal("46000"),
        )

        assert order["status"] == "open"

        # Price rises, order should execute
        simulator.set_price(Decimal("46000"))

        updated_order = simulator.get_order(order["id"])
        assert updated_order["status"] == "closed"

    @pytest.mark.asyncio
    async def test_insufficient_balance(self, simulator):
        """Test order rejection due to insufficient balance"""
        simulator.set_price(Decimal("45000"))

        # Try to buy more than balance allows
        with pytest.raises(Exception):
            await simulator.create_order(
                symbol="BTC/USDT",
                order_type="market",
                side="buy",
                amount=Decimal("10"),  # Would cost 450,000 USDT
            )

    @pytest.mark.asyncio
    async def test_cancel_order(self, simulator):
        """Test order cancellation"""
        simulator.set_price(Decimal("45000"))

        # Place limit order
        order = await simulator.create_order(
            symbol="BTC/USDT",
            order_type="limit",
            side="buy",
            amount=Decimal("0.1"),
            price=Decimal("44000"),
        )

        # Cancel it
        canceled = await simulator.cancel_order(order["id"])
        assert canceled["status"] == "canceled"

    def test_portfolio_value_calculation(self, simulator):
        """Test portfolio value calculation"""
        simulator.set_price(Decimal("45000"))
        initial_value = simulator.get_portfolio_value()

        assert initial_value == Decimal("10000")

        # Manually adjust balance for testing
        simulator.balance.base = Decimal("0.5")  # 0.5 BTC
        simulator.balance.quote = Decimal("5000")  # 5000 USDT

        # Portfolio = 0.5 * 45000 + 5000 = 27,500
        portfolio_value = simulator.get_portfolio_value()
        assert portfolio_value == Decimal("27500")

    def test_get_open_orders(self, simulator):
        """Test retrieving open orders"""
        open_orders = simulator.get_open_orders()
        assert len(open_orders) == 0


class TestHistoricalDataProvider:
    """Test historical data provider"""

    @pytest.fixture
    def provider(self):
        return HistoricalDataProvider()

    def test_generate_synthetic_data(self, provider):
        """Test synthetic data generation"""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2)

        data = provider.get_historical_prices(
            symbol="BTC/USDT",
            start_date=start_date,
            end_date=end_date,
            interval="1h",
        )

        assert len(data) == 24  # 24 hours
        assert all("open" in candle for candle in data)
        assert all("close" in candle for candle in data)
        assert all("high" in candle for candle in data)
        assert all("low" in candle for candle in data)
        assert all("volume" in candle for candle in data)

    def test_trending_data_generation(self, provider):
        """Test trend-specific data generation"""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 3)

        # Generate uptrend data
        up_data = provider.generate_trending_data(
            symbol="BTC/USDT",
            start_date=start_date,
            end_date=end_date,
            interval="1h",
            trend="up",
            base_price=Decimal("45000"),
        )

        # Verify uptrend (last price should be higher than first)
        assert up_data[-1]["close"] > up_data[0]["close"]

    def test_data_caching(self, provider):
        """Test that data is cached"""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2)

        # First call
        data1 = provider.get_historical_prices(
            symbol="BTC/USDT",
            start_date=start_date,
            end_date=end_date,
            interval="1h",
        )

        # Second call should return same data
        data2 = provider.get_historical_prices(
            symbol="BTC/USDT",
            start_date=start_date,
            end_date=end_date,
            interval="1h",
        )

        assert len(data1) == len(data2)
        assert data1[0]["timestamp"] == data2[0]["timestamp"]


class TestBacktestingEngine:
    """Test backtesting engine"""

    @pytest.fixture
    def engine(self):
        return BacktestingEngine(
            symbol="BTC/USDT",
            initial_balance=Decimal("10000"),
        )

    @pytest.mark.asyncio
    async def test_simple_backtest(self, engine):
        """Test simple backtest execution"""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 3)

        result = await engine.run_backtest(
            strategy_name="Test Strategy",
            strategy_config={},
            start_date=start_date,
            end_date=end_date,
            data_interval="1h",
        )

        assert result.strategy_name == "Test Strategy"
        assert result.symbol == "BTC/USDT"
        assert result.initial_balance == Decimal("10000")
        assert result.start_time == start_date
        assert result.end_time == end_date
        assert len(result.equity_curve) > 0

    @pytest.mark.asyncio
    async def test_backtest_with_trades(self, engine):
        """Test backtest with actual trades"""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2)

        # Get some price data
        data = engine.data_provider.get_historical_prices(
            symbol="BTC/USDT",
            start_date=start_date,
            end_date=end_date,
            interval="1h",
        )

        # Execute some trades
        engine.simulator.set_price(Decimal(str(data[0]["close"])))
        await engine.simulator.create_order(
            symbol="BTC/USDT",
            order_type="market",
            side="buy",
            amount=Decimal("0.1"),
        )

        engine.simulator.set_price(Decimal(str(data[-1]["close"])))
        await engine.simulator.create_order(
            symbol="BTC/USDT",
            order_type="market",
            side="sell",
            amount=Decimal("0.1"),
        )

        # Run backtest
        result = await engine.run_backtest(
            strategy_name="Simple Buy-Sell",
            strategy_config={},
            start_date=start_date,
            end_date=end_date,
            data_interval="1h",
        )

        assert result.total_trades > 0

    def test_result_to_dict(self, engine):
        """Test result serialization"""
        from bot.tests.backtesting.backtesting_engine import BacktestResult

        result = BacktestResult(
            strategy_name="Test",
            symbol="BTC/USDT",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 2),
            duration=timedelta(days=1),
            initial_balance=Decimal("10000"),
            final_balance=Decimal("10500"),
            total_return=Decimal("500"),
            total_return_pct=Decimal("5"),
            max_drawdown=Decimal("100"),
            max_drawdown_pct=Decimal("1"),
            total_trades=10,
            winning_trades=6,
            losing_trades=4,
            win_rate=Decimal("60"),
            total_buy_orders=5,
            total_sell_orders=5,
            avg_profit_per_trade=Decimal("50"),
        )

        result_dict = result.to_dict()
        assert result_dict["strategy_name"] == "Test"
        assert result_dict["performance"]["total_return"] == 500.0
        assert result_dict["trading_stats"]["win_rate"] == 60.0


@pytest.mark.integration
class TestBacktestingIntegration:
    """Integration tests for backtesting system"""

    @pytest.mark.asyncio
    async def test_grid_strategy_backtest(self):
        """Test grid strategy backtesting"""
        engine = BacktestingEngine(
            symbol="BTC/USDT",
            initial_balance=Decimal("10000"),
        )

        grid_config = {
            "upper_price": "46000",
            "lower_price": "44000",
            "grid_levels": 5,
            "amount_per_grid": "100",
        }

        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 7)

        result = await engine.run_grid_backtest(
            grid_config=grid_config,
            start_date=start_date,
            end_date=end_date,
        )

        assert result.strategy_name == "Grid Trading"
        assert result.initial_balance == Decimal("10000")
