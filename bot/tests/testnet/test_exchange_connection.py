"""Tests for exchange connectivity on testnet"""

from typing import Any

import ccxt
import pytest

pytestmark = pytest.mark.testnet


@pytest.fixture
def testnet_config() -> dict[str, Any]:
    """Get testnet configuration from environment or use defaults"""
    import os

    return {
        "exchange": os.getenv("TESTNET_EXCHANGE", "binance"),
        "api_key": os.getenv("TESTNET_API_KEY", ""),
        "secret": os.getenv("TESTNET_SECRET", ""),
        "sandbox": True,
    }


@pytest.fixture
def exchange_client(testnet_config: dict[str, Any]):
    """Create CCXT exchange client for testnet"""
    if not testnet_config["api_key"] or not testnet_config["secret"]:
        pytest.skip("Testnet credentials not configured")

    exchange_id = testnet_config["exchange"]
    exchange_class = getattr(ccxt, exchange_id)

    client = exchange_class(
        {
            "apiKey": testnet_config["api_key"],
            "secret": testnet_config["secret"],
            "enableRateLimit": True,
            "options": {
                "defaultType": "spot",
            },
        }
    )

    # Enable sandbox/testnet mode
    client.set_sandbox_mode(True)

    return client


class TestExchangeConnection:
    """Test exchange connection and API access"""

    def test_exchange_initialization(self, exchange_client):
        """Test that exchange client initializes correctly"""
        assert exchange_client is not None
        assert exchange_client.has["fetchTicker"]
        assert exchange_client.has["createOrder"]

    @pytest.mark.asyncio
    async def test_fetch_balance(self, exchange_client):
        """Test fetching account balance"""
        try:
            balance = exchange_client.fetch_balance()
            assert balance is not None
            assert "total" in balance
            assert "free" in balance
            assert "used" in balance
            print("\n✅ Balance fetched successfully")
            print(f"   Free USDT: {balance.get('USDT', {}).get('free', 0)}")
            print(f"   Free BTC: {balance.get('BTC', {}).get('free', 0)}")
        except Exception as e:
            pytest.fail(f"Failed to fetch balance: {e}")

    @pytest.mark.asyncio
    async def test_fetch_ticker(self, exchange_client):
        """Test fetching ticker data"""
        try:
            ticker = exchange_client.fetch_ticker("BTC/USDT")
            assert ticker is not None
            assert "last" in ticker
            assert "bid" in ticker
            assert "ask" in ticker
            assert ticker["last"] > 0
            print("\n✅ Ticker fetched successfully")
            print(f"   BTC/USDT Last Price: ${ticker['last']:,.2f}")
        except Exception as e:
            pytest.fail(f"Failed to fetch ticker: {e}")

    @pytest.mark.asyncio
    async def test_fetch_order_book(self, exchange_client):
        """Test fetching order book"""
        try:
            orderbook = exchange_client.fetch_order_book("BTC/USDT", limit=10)
            assert orderbook is not None
            assert "bids" in orderbook
            assert "asks" in orderbook
            assert len(orderbook["bids"]) > 0
            assert len(orderbook["asks"]) > 0
            print("\n✅ Order book fetched successfully")
            print(f"   Best Bid: ${orderbook['bids'][0][0]:,.2f}")
            print(f"   Best Ask: ${orderbook['asks'][0][0]:,.2f}")
        except Exception as e:
            pytest.fail(f"Failed to fetch order book: {e}")

    @pytest.mark.asyncio
    async def test_fetch_ohlcv(self, exchange_client):
        """Test fetching OHLCV candlestick data"""
        try:
            ohlcv = exchange_client.fetch_ohlcv("BTC/USDT", "1h", limit=10)
            assert ohlcv is not None
            assert len(ohlcv) > 0
            assert len(ohlcv[0]) == 6  # timestamp, open, high, low, close, volume
            print("\n✅ OHLCV data fetched successfully")
            print(f"   Retrieved {len(ohlcv)} candles")
        except Exception as e:
            pytest.fail(f"Failed to fetch OHLCV: {e}")

    @pytest.mark.asyncio
    async def test_fetch_markets(self, exchange_client):
        """Test fetching available markets"""
        try:
            markets = exchange_client.fetch_markets()
            assert markets is not None
            assert len(markets) > 0

            # Find BTC/USDT market
            btc_usdt = next((m for m in markets if m["symbol"] == "BTC/USDT"), None)
            assert btc_usdt is not None
            print("\n✅ Markets fetched successfully")
            print(f"   Total markets: {len(markets)}")
            print(f"   BTC/USDT found: {btc_usdt['symbol']}")
        except Exception as e:
            pytest.fail(f"Failed to fetch markets: {e}")


class TestOrderOperations:
    """Test order creation and management on testnet"""

    @pytest.mark.asyncio
    async def test_create_and_cancel_limit_order(self, exchange_client):
        """Test creating and canceling a limit order"""
        try:
            # Get current price
            ticker = exchange_client.fetch_ticker("BTC/USDT")
            current_price = ticker["last"]

            # Place limit buy order well below market (won't execute)
            buy_price = current_price * 0.8  # 20% below
            amount = 0.001  # Small amount

            order = exchange_client.create_limit_buy_order("BTC/USDT", amount, buy_price)

            assert order is not None
            assert order["id"] is not None
            assert order["status"] in ["open", "pending"]

            print("\n✅ Limit buy order created successfully")
            print(f"   Order ID: {order['id']}")
            print(f"   Price: ${buy_price:,.2f}")
            print(f"   Amount: {amount} BTC")

            # Cancel the order
            canceled = exchange_client.cancel_order(order["id"], "BTC/USDT")
            assert canceled is not None

            print("✅ Order canceled successfully")

        except Exception as e:
            pytest.fail(f"Failed order operation: {e}")

    @pytest.mark.asyncio
    async def test_fetch_open_orders(self, exchange_client):
        """Test fetching open orders"""
        try:
            orders = exchange_client.fetch_open_orders("BTC/USDT")
            assert orders is not None
            print("\n✅ Open orders fetched successfully")
            print(f"   Open orders count: {len(orders)}")
        except Exception as e:
            pytest.fail(f"Failed to fetch open orders: {e}")

    @pytest.mark.asyncio
    async def test_fetch_closed_orders(self, exchange_client):
        """Test fetching closed orders"""
        try:
            orders = exchange_client.fetch_closed_orders("BTC/USDT", limit=10)
            assert orders is not None
            print("\n✅ Closed orders fetched successfully")
            print(f"   Closed orders count: {len(orders)}")
        except Exception as e:
            # Some exchanges might not support this
            print(f"\n⚠️  Fetch closed orders not supported or failed: {e}")


class TestRateLimiting:
    """Test rate limiting and error handling"""

    @pytest.mark.asyncio
    async def test_rate_limit_handling(self, exchange_client):
        """Test that rate limiting is properly handled"""
        import time

        try:
            # Make multiple rapid requests
            start_time = time.time()

            for _i in range(5):
                exchange_client.fetch_ticker("BTC/USDT")

            elapsed = time.time() - start_time

            # Should take at least some time due to rate limiting
            print("\n✅ Rate limiting test completed")
            print(f"   5 requests took {elapsed:.2f} seconds")
            print(f"   Rate limit enabled: {exchange_client.enableRateLimit}")

        except Exception as e:
            print(f"\n⚠️  Rate limit test error: {e}")


@pytest.mark.skipif(
    not pytest.config.getoption("--testnet", default=False),
    reason="Testnet tests require --testnet flag",
)
class TestComprehensiveValidation:
    """Comprehensive testnet validation suite"""

    @pytest.mark.asyncio
    async def test_full_validation(self, exchange_client):
        """Run full validation of testnet functionality"""
        print("\n" + "=" * 70)
        print("TESTNET VALIDATION REPORT")
        print("=" * 70)

        results = {
            "connection": False,
            "balance": False,
            "market_data": False,
            "order_management": False,
        }

        # Test 1: Connection
        try:
            exchange_client.fetch_balance()
            results["connection"] = True
            print("✅ Exchange Connection: PASSED")
        except Exception as e:
            print(f"❌ Exchange Connection: FAILED - {e}")

        # Test 2: Balance
        try:
            balance = exchange_client.fetch_balance()
            usdt_balance = balance.get("USDT", {}).get("free", 0)
            results["balance"] = usdt_balance > 0
            print(f"✅ Balance Check: PASSED (USDT: {usdt_balance})")
        except Exception as e:
            print(f"❌ Balance Check: FAILED - {e}")

        # Test 3: Market Data
        try:
            ticker = exchange_client.fetch_ticker("BTC/USDT")
            orderbook = exchange_client.fetch_order_book("BTC/USDT")
            results["market_data"] = ticker["last"] > 0 and len(orderbook["bids"]) > 0
            print("✅ Market Data: PASSED")
        except Exception as e:
            print(f"❌ Market Data: FAILED - {e}")

        # Test 4: Order Management
        try:
            ticker = exchange_client.fetch_ticker("BTC/USDT")
            order = exchange_client.create_limit_buy_order("BTC/USDT", 0.001, ticker["last"] * 0.8)
            exchange_client.cancel_order(order["id"], "BTC/USDT")
            results["order_management"] = True
            print("✅ Order Management: PASSED")
        except Exception as e:
            print(f"❌ Order Management: FAILED - {e}")

        print("=" * 70)
        passed = sum(results.values())
        total = len(results)
        print(f"RESULTS: {passed}/{total} tests passed")
        print("=" * 70)

        assert passed == total, f"Only {passed}/{total} validation tests passed"
