"""
Smoke tests for Bybit Demo Trading (Phase 7.3).

These tests connect to api-demo.bybit.com with real credentials
and validate core trading functionality on the demo exchange.

Run with:
    DEMO_SMOKE_TEST=1 python -m pytest tests/integration/test_demo_smoke.py -v

Requires:
    - DATABASE_URL and ENCRYPTION_KEY environment variables
    - 'bybit_production' credentials in database
    - Network access to api-demo.bybit.com
"""

import asyncio
import os
import sys
from decimal import Decimal
from pathlib import Path

import pytest

# Skip all tests unless DEMO_SMOKE_TEST is set
pytestmark = pytest.mark.skipif(
    os.getenv("DEMO_SMOKE_TEST") != "1",
    reason="Demo smoke tests require DEMO_SMOKE_TEST=1",
)

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture(scope="module")
def event_loop():
    """Create event loop for module-scoped fixtures."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def credentials(event_loop):
    """Load API credentials from database."""
    from cryptography.fernet import Fernet

    from bot.database.manager import DatabaseManager

    database_url = os.getenv("DATABASE_URL")
    encryption_key = os.getenv("ENCRYPTION_KEY")

    assert database_url, "DATABASE_URL environment variable required"
    assert encryption_key, "ENCRYPTION_KEY environment variable required"

    db = DatabaseManager(database_url)
    await db.initialize()

    cred = await db.get_credentials_by_name("bybit_production")
    assert cred, "Credentials 'bybit_production' not found in database"

    fernet = Fernet(encryption_key.encode())
    api_key = fernet.decrypt(cred.api_key_encrypted.encode()).decode()
    api_secret = fernet.decrypt(cred.api_secret_encrypted.encode()).decode()

    await db.close()

    return api_key, api_secret


@pytest.fixture(scope="module")
async def client(credentials, event_loop):
    """Create ByBitDirectClient for demo trading."""
    from bot.api.bybit_direct_client import ByBitDirectClient

    api_key, api_secret = credentials

    client = ByBitDirectClient(
        api_key=api_key,
        api_secret=api_secret,
        testnet=True,
        market_type="linear",
    )
    await client.initialize()

    yield client

    await client.close()


class TestDemoConnection:
    """Test basic connectivity to Bybit Demo."""

    async def test_health_check(self, client):
        """Health check passes."""
        assert await client.health_check() is True

    async def test_markets_loaded(self, client):
        """Markets are loaded on initialization."""
        assert len(client.markets) > 0
        assert "BTC/USDT" in client.markets

    async def test_is_initialized(self, client):
        """Client is initialized."""
        assert client.is_initialized is True
        assert client.testnet is True
        assert client.category == "linear"


class TestDemoMarketData:
    """Test market data on demo exchange."""

    @pytest.mark.parametrize("symbol", ["BTC/USDT", "ETH/USDT", "SOL/USDT"])
    async def test_fetch_ticker(self, client, symbol):
        """Fetch ticker for trading pairs."""
        ticker = await client.fetch_ticker(symbol)

        assert ticker["symbol"] == symbol
        assert ticker["last"] > 0
        assert ticker["bid"] > 0
        assert ticker["ask"] > 0

    async def test_fetch_ohlcv(self, client):
        """Fetch OHLCV candles."""
        candles = await client.fetch_ohlcv("BTC/USDT", "1h", limit=10)

        assert len(candles) > 0
        assert len(candles) <= 10

        # Verify OHLCV format: [timestamp, open, high, low, close, volume]
        for candle in candles:
            assert len(candle) == 6
            assert candle[0] > 0  # timestamp
            assert candle[1] > 0  # open
            assert candle[2] >= candle[3]  # high >= low
            assert candle[5] >= 0  # volume >= 0

        # Verify oldest-first ordering (CCXT convention)
        assert candles[0][0] < candles[-1][0]

    async def test_fetch_order_book(self, client):
        """Fetch order book."""
        ob = await client.fetch_order_book("BTC/USDT", limit=5)

        assert "bids" in ob
        assert "asks" in ob
        assert len(ob["bids"]) > 0
        assert len(ob["asks"]) > 0

        # Bid < Ask
        assert ob["bids"][0][0] < ob["asks"][0][0]


class TestDemoAuth:
    """Test authenticated endpoints."""

    async def test_fetch_balance(self, client):
        """Fetch account balance."""
        balance = await client.fetch_balance()

        assert "total" in balance
        assert "free" in balance
        assert "used" in balance
        # Demo account should have some USDT
        assert isinstance(balance["total"], dict)

    async def test_fetch_open_orders(self, client):
        """Fetch open orders (may be empty)."""
        orders = await client.fetch_open_orders("BTC/USDT")
        assert isinstance(orders, list)

    async def test_fetch_closed_orders(self, client):
        """Fetch closed orders (may be empty)."""
        orders = await client.fetch_closed_orders("BTC/USDT", limit=5)
        assert isinstance(orders, list)


class TestDemoOrderLifecycle:
    """Test order creation and cancellation on demo."""

    async def test_create_and_cancel_limit_order(self, client):
        """Create a limit order far from market and cancel it."""
        # Get current price
        ticker = await client.fetch_ticker("BTC/USDT")
        current_price = ticker["last"]

        # Place buy order 30% below market (won't fill)
        safe_price = round(current_price * 0.7, 1)
        # Use minimum quantity for BTC linear: 0.001
        amount = Decimal("0.001")

        order = await client.create_limit_order(
            symbol="BTC/USDT",
            side="buy",
            amount=amount,
            price=Decimal(str(safe_price)),
        )

        assert order["id"], "Order should have an ID"
        assert order["type"] == "limit"
        assert order["side"] == "buy"

        # Cancel the order
        cancel_result = await client.cancel_order(
            order_id=order["id"],
            symbol="BTC/USDT",
        )

        assert cancel_result["status"] == "cancelled"


class TestDemoConfig:
    """Test configuration loading."""

    def test_load_phase7_config(self):
        """Phase 7 demo config loads and validates."""
        # Set dummy env vars for validation
        os.environ.setdefault("DATABASE_URL", os.getenv("DATABASE_URL", ""))
        os.environ.setdefault("ENCRYPTION_KEY", os.getenv("ENCRYPTION_KEY", ""))

        from bot.config.manager import ConfigManager

        cm = ConfigManager(Path("configs/phase7_demo.yaml"))
        config = cm.load()

        assert len(config.bots) == 4

        for bot in config.bots:
            assert bot.exchange.sandbox is True, f"{bot.name} must use sandbox"
            assert bot.dry_run is False, f"{bot.name} should be live on demo"
            assert bot.exchange.exchange_id == "bybit"

    def test_strategy_coverage(self):
        """All four strategies are covered."""
        from bot.config.manager import ConfigManager

        cm = ConfigManager(Path("configs/phase7_demo.yaml"))
        config = cm.load()

        strategies = {bot.strategy for bot in config.bots}
        assert "hybrid" in strategies
        assert "grid" in strategies
        assert "dca" in strategies
        assert "trend_follower" in strategies
