"""Tests for ExchangeAPIClient v2.0.

Uses mocked CCXT exchange to test client logic without real API calls.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.api.exceptions import (
    AuthenticationError,
    ExchangeAPIError,
    ExchangeNotAvailableError,
    InsufficientFundsError,
    InvalidOrderError,
    NetworkError,
    OrderError,
    RateLimitError,
)
from bot.api.exchange_client import ExchangeAPIClient

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def client():
    """Create a client without initialization."""
    return ExchangeAPIClient(
        exchange_id="bybit",
        api_key="test_key",
        api_secret="test_secret",
        sandbox=True,
        rate_limit=False,  # Disable for fast tests
    )


@pytest.fixture
def mock_exchange():
    """Create a mock CCXT exchange."""
    mock = AsyncMock()
    mock.markets = {"BTC/USDT": {"symbol": "BTC/USDT"}}
    mock.close = AsyncMock()
    mock.load_markets = AsyncMock(return_value={"BTC/USDT": {}})
    mock.fetch_time = AsyncMock(return_value=1700000000000)
    mock.set_sandbox_mode = MagicMock()
    return mock


@pytest.fixture
def initialized_client(client, mock_exchange):
    """Create a client with mocked exchange."""
    client._exchange = mock_exchange
    client._ws_exchange = AsyncMock()
    client._initialized = True
    return client


# =========================================================================
# Initialization Tests
# =========================================================================


class TestInitialization:
    def test_default_state(self):
        client = ExchangeAPIClient(
            exchange_id="binance",
            api_key="key",
            api_secret="secret",
        )
        assert client.exchange_id == "binance"
        assert client.is_initialized is False
        assert client.markets == {}
        assert client._rate_limit is True
        assert client._default_type == "spot"

    def test_custom_params(self):
        client = ExchangeAPIClient(
            exchange_id="bybit",
            api_key="key",
            api_secret="secret",
            sandbox=True,
            default_type="swap",
            max_retries=5,
        )
        assert client._sandbox is True
        assert client._default_type == "swap"
        assert client._max_retries == 5

    @pytest.mark.asyncio
    async def test_initialize_success(self, mock_exchange):
        with patch("bot.api.exchange_client.ccxtpro") as mock_ccxt:
            mock_cls = MagicMock(return_value=mock_exchange)
            mock_ccxt.bybit = mock_cls

            client = ExchangeAPIClient(
                exchange_id="bybit",
                api_key="key",
                api_secret="secret",
                sandbox=True,
                rate_limit=False,
            )
            await client.initialize()

            assert client.is_initialized
            assert client._initialized_at is not None
            mock_exchange.set_sandbox_mode.assert_called_with(True)
            mock_exchange.load_markets.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_initialize_failure(self):
        with patch("bot.api.exchange_client.ccxtpro") as mock_ccxt:
            mock_ccxt.bybit = MagicMock(side_effect=Exception("Connection failed"))

            client = ExchangeAPIClient(
                exchange_id="bybit",
                api_key="key",
                api_secret="secret",
                rate_limit=False,
            )
            with pytest.raises(ExchangeAPIError, match="Failed to initialize"):
                await client.initialize()

    @pytest.mark.asyncio
    async def test_close(self, initialized_client):
        await initialized_client.close()
        assert initialized_client.is_initialized is False
        initialized_client._exchange.close.assert_awaited_once()


# =========================================================================
# Health Check Tests
# =========================================================================


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_healthy(self, initialized_client):
        assert await initialized_client.health_check() is True

    @pytest.mark.asyncio
    async def test_not_initialized(self, client):
        assert await client.health_check() is False

    @pytest.mark.asyncio
    async def test_health_check_failure(self, initialized_client):
        initialized_client._exchange.fetch_time = AsyncMock(side_effect=Exception("timeout"))
        assert await initialized_client.health_check() is False


# =========================================================================
# Rate Limiting Tests
# =========================================================================


class TestRateLimiting:
    def test_adaptive_rate_limit_increase(self, client):
        initial = client._adaptive_interval
        client._on_rate_limit_hit()
        assert client._adaptive_interval > initial
        assert client._rate_limit_hits == 1

    def test_adaptive_rate_limit_decrease(self, client):
        client._adaptive_interval = 0.5
        client._on_request_success()
        assert client._adaptive_interval < 0.5

    def test_adaptive_rate_limit_floor(self, client):
        client._adaptive_interval = client._min_request_interval
        client._on_request_success()
        assert client._adaptive_interval == client._min_request_interval

    def test_adaptive_rate_limit_ceiling(self, client):
        for _ in range(50):
            client._on_rate_limit_hit()
        assert client._adaptive_interval <= 2.0


# =========================================================================
# Exception Mapping Tests
# =========================================================================


class TestExceptionMapping:
    def test_rate_limit_exceeded(self, client):
        import ccxt.pro as ccxtpro

        e = ccxtpro.RateLimitExceeded("too fast")
        result = client._map_ccxt_exception(e)
        assert isinstance(result, RateLimitError)
        assert client._rate_limit_hits == 1

    def test_auth_error(self, client):
        import ccxt.pro as ccxtpro

        e = ccxtpro.AuthenticationError("bad key")
        result = client._map_ccxt_exception(e)
        assert isinstance(result, AuthenticationError)

    def test_insufficient_funds(self, client):
        import ccxt.pro as ccxtpro

        e = ccxtpro.InsufficientFunds("no funds")
        result = client._map_ccxt_exception(e)
        assert isinstance(result, InsufficientFundsError)

    def test_invalid_order(self, client):
        import ccxt.pro as ccxtpro

        e = ccxtpro.InvalidOrder("bad params")
        result = client._map_ccxt_exception(e)
        assert isinstance(result, InvalidOrderError)

    def test_order_not_found(self, client):
        import ccxt.pro as ccxtpro

        e = ccxtpro.OrderNotFound("not found")
        result = client._map_ccxt_exception(e)
        assert isinstance(result, OrderError)

    def test_network_error(self, client):
        import ccxt.pro as ccxtpro

        e = ccxtpro.NetworkError("timeout")
        result = client._map_ccxt_exception(e)
        assert isinstance(result, NetworkError)

    def test_exchange_not_available(self, client):
        import ccxt.pro as ccxtpro

        e = ccxtpro.ExchangeNotAvailable("maintenance")
        result = client._map_ccxt_exception(e)
        assert isinstance(result, ExchangeNotAvailableError)

    def test_generic_error(self, client):
        e = Exception("something else")
        result = client._map_ccxt_exception(e)
        assert isinstance(result, ExchangeAPIError)

    def test_last_error_tracked(self, client):
        e = Exception("tracked error")
        client._map_ccxt_exception(e)
        assert client._last_error == "tracked error"
        assert client._last_error_time is not None


# =========================================================================
# Market Data Tests
# =========================================================================


class TestMarketData:
    @pytest.mark.asyncio
    async def test_fetch_balance(self, initialized_client):
        initialized_client._exchange.fetch_balance = AsyncMock(
            return_value={"USDT": {"free": 1000}}
        )
        result = await initialized_client.fetch_balance()
        assert result["USDT"]["free"] == 1000

    @pytest.mark.asyncio
    async def test_fetch_ticker(self, initialized_client):
        initialized_client._exchange.fetch_ticker = AsyncMock(
            return_value={"symbol": "BTC/USDT", "last": 45000}
        )
        result = await initialized_client.fetch_ticker("BTC/USDT")
        assert result["last"] == 45000

    @pytest.mark.asyncio
    async def test_fetch_ohlcv(self, initialized_client):
        mock_data = [
            [1700000000000, 45000, 45500, 44800, 45200, 100],
            [1700003600000, 45200, 45800, 45100, 45600, 120],
        ]
        initialized_client._exchange.fetch_ohlcv = AsyncMock(return_value=mock_data)
        result = await initialized_client.fetch_ohlcv("BTC/USDT", "1h", limit=2)
        assert len(result) == 2
        assert result[0][4] == 45200  # close

    @pytest.mark.asyncio
    async def test_fetch_order_book(self, initialized_client):
        initialized_client._exchange.fetch_order_book = AsyncMock(
            return_value={
                "bids": [[45000, 1.5], [44900, 2.0]],
                "asks": [[45100, 1.0], [45200, 0.5]],
            }
        )
        result = await initialized_client.fetch_order_book("BTC/USDT", limit=2)
        assert len(result["bids"]) == 2
        assert len(result["asks"]) == 2

    @pytest.mark.asyncio
    async def test_fetch_trades(self, initialized_client):
        initialized_client._exchange.fetch_trades = AsyncMock(
            return_value=[{"price": 45000, "amount": 0.1, "side": "buy"}]
        )
        result = await initialized_client.fetch_trades("BTC/USDT")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_not_initialized_raises(self, client):
        with pytest.raises(ExchangeAPIError, match="not initialized"):
            await client.fetch_ticker("BTC/USDT")


# =========================================================================
# Order Management Tests
# =========================================================================


class TestOrderManagement:
    @pytest.mark.asyncio
    async def test_create_limit_order(self, initialized_client):
        initialized_client._exchange.create_limit_order = AsyncMock(
            return_value={"id": "order-123", "status": "open"}
        )
        result = await initialized_client.create_limit_order(
            "BTC/USDT", "buy", Decimal("0.1"), Decimal("45000")
        )
        assert result["id"] == "order-123"

    @pytest.mark.asyncio
    async def test_create_market_order(self, initialized_client):
        initialized_client._exchange.create_market_order = AsyncMock(
            return_value={"id": "order-456", "status": "closed"}
        )
        result = await initialized_client.create_market_order("BTC/USDT", "sell", Decimal("0.5"))
        assert result["id"] == "order-456"

    @pytest.mark.asyncio
    async def test_create_order_limit(self, initialized_client):
        initialized_client._exchange.create_limit_order = AsyncMock(
            return_value={"id": "order-789", "type": "limit"}
        )
        result = await initialized_client.create_order("BTC/USDT", "limit", "buy", 0.1, price=45000)
        assert result["type"] == "limit"

    @pytest.mark.asyncio
    async def test_create_order_market(self, initialized_client):
        initialized_client._exchange.create_market_order = AsyncMock(
            return_value={"id": "order-999", "type": "market"}
        )
        result = await initialized_client.create_order("BTC/USDT", "market", "sell", 0.5)
        assert result["type"] == "market"

    @pytest.mark.asyncio
    async def test_cancel_order(self, initialized_client):
        initialized_client._exchange.cancel_order = AsyncMock(
            return_value={"id": "order-123", "status": "canceled"}
        )
        result = await initialized_client.cancel_order("order-123", "BTC/USDT")
        assert result["status"] == "canceled"

    @pytest.mark.asyncio
    async def test_cancel_all_orders(self, initialized_client):
        initialized_client._exchange.cancel_all_orders = AsyncMock(
            return_value=[{"id": "o1"}, {"id": "o2"}]
        )
        result = await initialized_client.cancel_all_orders("BTC/USDT")
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_fetch_order(self, initialized_client):
        initialized_client._exchange.fetch_order = AsyncMock(
            return_value={"id": "order-123", "status": "closed", "filled": 0.1}
        )
        result = await initialized_client.fetch_order("order-123", "BTC/USDT")
        assert result["filled"] == 0.1

    @pytest.mark.asyncio
    async def test_fetch_open_orders(self, initialized_client):
        initialized_client._exchange.fetch_open_orders = AsyncMock(
            return_value=[{"id": "o1"}, {"id": "o2"}]
        )
        result = await initialized_client.fetch_open_orders("BTC/USDT")
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_fetch_closed_orders(self, initialized_client):
        initialized_client._exchange.fetch_closed_orders = AsyncMock(
            return_value=[{"id": "o1", "status": "closed"}]
        )
        result = await initialized_client.fetch_closed_orders("BTC/USDT")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_set_leverage(self, initialized_client):
        initialized_client._exchange.set_leverage = AsyncMock(return_value={"leverage": 10})
        result = await initialized_client.set_leverage(10, "BTC/USDT")
        assert result["leverage"] == 10


# =========================================================================
# WebSocket Tests
# =========================================================================


class TestWebSocket:
    @pytest.mark.asyncio
    async def test_watch_ticker(self, initialized_client):
        initialized_client._ws_exchange.watch_ticker = AsyncMock(
            return_value={"symbol": "BTC/USDT", "last": 45000}
        )
        result = await initialized_client.watch_ticker("BTC/USDT")
        assert result["last"] == 45000

    @pytest.mark.asyncio
    async def test_watch_orders(self, initialized_client):
        initialized_client._ws_exchange.watch_orders = AsyncMock(
            return_value=[{"id": "o1", "status": "open"}]
        )
        result = await initialized_client.watch_orders("BTC/USDT")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_watch_ohlcv(self, initialized_client):
        initialized_client._ws_exchange.watch_ohlcv = AsyncMock(
            return_value=[[1700000000000, 45000, 45500, 44800, 45200, 100]]
        )
        result = await initialized_client.watch_ohlcv("BTC/USDT", "1m")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_watch_trades(self, initialized_client):
        initialized_client._ws_exchange.watch_trades = AsyncMock(
            return_value=[{"price": 45000, "amount": 0.1}]
        )
        result = await initialized_client.watch_trades("BTC/USDT")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_watch_order_book(self, initialized_client):
        initialized_client._ws_exchange.watch_order_book = AsyncMock(
            return_value={"bids": [[45000, 1]], "asks": [[45100, 1]]}
        )
        result = await initialized_client.watch_order_book("BTC/USDT")
        assert "bids" in result

    @pytest.mark.asyncio
    async def test_ws_not_initialized(self, client):
        with pytest.raises(ExchangeAPIError, match="not initialized"):
            await client.watch_ticker("BTC/USDT")


# =========================================================================
# Statistics Tests
# =========================================================================


class TestStatistics:
    def test_initial_stats(self, client):
        stats = client.get_statistics()
        assert stats["exchange"] == "bybit"
        assert stats["initialized"] is False
        assert stats["total_requests"] == 0
        assert stats["total_errors"] == 0
        assert stats["rate_limit_hits"] == 0
        assert stats["avg_latency_ms"] == 0.0

    @pytest.mark.asyncio
    async def test_stats_after_requests(self, initialized_client):
        initialized_client._exchange.fetch_ticker = AsyncMock(return_value={"last": 45000})
        await initialized_client.fetch_ticker("BTC/USDT")
        await initialized_client.fetch_ticker("ETH/USDT")

        stats = initialized_client.get_statistics()
        assert stats["total_requests"] == 2
        assert stats["total_errors"] == 0
        assert stats["avg_latency_ms"] >= 0

    def test_stats_with_errors(self, client):
        client._request_count = 10
        client._error_count = 2
        client._rate_limit_hits = 1
        stats = client.get_statistics()
        assert stats["error_rate"] == 0.2
        assert stats["rate_limit_hits"] == 1
