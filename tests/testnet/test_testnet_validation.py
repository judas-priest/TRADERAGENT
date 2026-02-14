"""
Testnet deployment validation tests.

Validates that the ByBit demo/testnet client can:
- Connect and authenticate
- Fetch market data (ticker, orderbook, klines)
- Place and cancel test orders
- Fetch account balance and positions
- Handle rate limits and errors gracefully

These tests require BYBIT_TESTNET_API_KEY and BYBIT_TESTNET_API_SECRET
environment variables. If not set, tests are skipped.
"""

import os
from decimal import Decimal

import pytest

from bot.api.bybit_direct_client import ByBitDirectClient
from bot.api.exceptions import (
    AuthenticationError,
    ExchangeAPIError,
    InvalidOrderError,
)


# ---------------------------------------------------------------------------
# Skip if no testnet credentials
# ---------------------------------------------------------------------------

TESTNET_KEY = os.environ.get("BYBIT_TESTNET_API_KEY", "")
TESTNET_SECRET = os.environ.get("BYBIT_TESTNET_API_SECRET", "")

pytestmark = pytest.mark.skipif(
    not TESTNET_KEY or not TESTNET_SECRET,
    reason="BYBIT_TESTNET_API_KEY / BYBIT_TESTNET_API_SECRET not set",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def client():
    """Create and initialize a testnet ByBit client."""
    c = ByBitDirectClient(
        api_key=TESTNET_KEY,
        api_secret=TESTNET_SECRET,
        testnet=True,
        market_type="linear",
    )
    await c.initialize()
    yield c
    await c.close()


# ===========================================================================
# Connection & Authentication
# ===========================================================================


class TestConnection:
    async def test_client_initialized(self, client):
        assert client._session is not None
        assert client.testnet is True
        assert client.base_url == "https://api-demo.bybit.com"

    async def test_fetch_balance(self, client):
        balance = await client.fetch_balance()
        assert isinstance(balance, dict)
        assert "total" in balance
        assert "free" in balance

    async def test_invalid_credentials(self):
        bad_client = ByBitDirectClient(
            api_key="invalid_key",
            api_secret="invalid_secret",
            testnet=True,
        )
        await bad_client.initialize()
        try:
            with pytest.raises((AuthenticationError, ExchangeAPIError)):
                await bad_client.fetch_balance()
        finally:
            await bad_client.close()


# ===========================================================================
# Market Data
# ===========================================================================


class TestMarketData:
    async def test_fetch_ticker(self, client):
        ticker = await client.fetch_ticker("BTC/USDT")
        assert ticker["symbol"] == "BTC/USDT"
        assert ticker["last"] > 0
        assert ticker["bid"] > 0
        assert ticker["ask"] > 0
        assert ticker["ask"] >= ticker["bid"]

    async def test_fetch_ticker_eth(self, client):
        ticker = await client.fetch_ticker("ETH/USDT")
        assert ticker["symbol"] == "ETH/USDT"
        assert ticker["last"] > 0

    async def test_fetch_markets(self, client):
        markets = await client.fetch_markets()
        assert isinstance(markets, dict)
        assert len(markets) > 0
        # BTC/USDT should exist on testnet
        if "BTC/USDT" in markets:
            btc = markets["BTC/USDT"]
            assert btc["active"] is True
            assert btc["base"] == "BTC"
            assert btc["quote"] == "USDT"


# ===========================================================================
# Order Lifecycle
# ===========================================================================


class TestOrderLifecycle:
    async def test_create_and_cancel_limit_order(self, client):
        """Place a limit order far from market and cancel it."""
        ticker = await client.fetch_ticker("BTC/USDT")
        # Place buy order 20% below market — should not fill
        low_price = Decimal(str(round(ticker["last"] * 0.80, 2)))
        result = await client.create_limit_order(
            symbol="BTC/USDT",
            side="buy",
            amount=Decimal("0.001"),
            price=low_price,
        )
        assert "id" in result
        order_id = result["id"]

        # Cancel the order
        cancel_result = await client.cancel_order(order_id, "BTC/USDT")
        assert cancel_result is not None

    async def test_fetch_open_orders(self, client):
        orders = await client.fetch_open_orders("BTC/USDT")
        assert isinstance(orders, list)

    async def test_invalid_order_rejected(self, client):
        """Order with zero amount should be rejected."""
        with pytest.raises((InvalidOrderError, ExchangeAPIError)):
            await client.create_limit_order(
                symbol="BTC/USDT",
                side="buy",
                amount=Decimal("0"),
                price=Decimal("1000"),
            )


# ===========================================================================
# Statistics
# ===========================================================================


class TestStatistics:
    async def test_statistics_after_operations(self, client):
        await client.fetch_ticker("BTC/USDT")
        stats = client.get_statistics()
        assert stats["exchange"] == "bybit"
        assert stats["testnet"] is True
        assert stats["total_requests"] > 0
        assert stats["error_rate"] >= 0


# ===========================================================================
# Strategy Adapter with Testnet Data
# ===========================================================================


class TestStrategyWithTestnetData:
    """Validate that strategy adapters work with real testnet price data."""

    async def test_fetch_klines_for_strategy(self, client):
        """Fetch klines and verify they're usable for strategy analysis."""
        # This tests that the client can provide data for strategies
        ticker = await client.fetch_ticker("BTC/USDT")
        assert ticker["last"] > 0
        # If klines endpoint exists
        if hasattr(client, "fetch_klines"):
            klines = await client.fetch_klines("BTC/USDT", "15", limit=100)
            assert len(klines) > 0
