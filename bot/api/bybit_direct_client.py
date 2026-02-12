"""
Direct ByBit V5 API Client
Implements proper Demo Trading support based on working implementation.

Key features:
- Correct Demo Trading URL handling (api-demo.bybit.com)
- Production API keys work for both live and demo trading
- Proper signature construction for V5 API
- Extended recvWindow (10000ms) for server time drift
- UNIFIED account type for Demo Trading
"""

import hashlib
import hmac
import time
from decimal import Decimal
from typing import Any, Literal

import aiohttp
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

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
from bot.utils.logger import get_logger

logger = get_logger(__name__)


class ByBitDirectClient:
    """
    Direct ByBit V5 API Client with proper Demo Trading support.

    Based on working implementation from unidel2035/btc repository.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = False,
        market_type: Literal["spot", "linear"] = "spot",
    ) -> None:
        """
        Initialize ByBit Direct Client.

        Args:
            api_key: Production API key (works for both live and demo!)
            api_secret: Production API secret
            testnet: If True, uses api-demo.bybit.com (Demo Trading)
            market_type: 'spot' for spot trading, 'linear' for futures

        Important:
            Demo Trading (testnet=True) ONLY supports 'linear' (futures), NOT 'spot'!
            This will be automatically corrected if testnet=True and market_type='spot'.
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet

        # CRITICAL: Demo Trading does NOT support spot!
        # Force linear for testnet regardless of requested market_type
        if testnet and market_type == "spot":
            logger.warning(
                "Demo Trading does not support spot trading, forcing linear (futures)",
                requested_market_type=market_type,
            )
            market_type = "linear"

        self.market_type = market_type

        # Demo Trading uses production keys with demo URL
        self.base_url = (
            "https://api-demo.bybit.com" if testnet else "https://api.bybit.com"
        )

        # Category for API requests
        self.category = "spot" if market_type == "spot" else "linear"

        # Extended receive window for server time drift
        self.recv_window = 10000  # 10 seconds (increased from 5s)

        # Session for connection pooling
        self._session: aiohttp.ClientSession | None = None

        # Statistics
        self._request_count = 0
        self._error_count = 0

        logger.info(
            "Initializing ByBit Direct Client",
            testnet=testnet,
            market_type=market_type,
            category=self.category,
            base_url=self.base_url,
        )

    async def initialize(self) -> None:
        """Initialize HTTP session"""
        if not self._session:
            self._session = aiohttp.ClientSession()
            logger.info("ByBit Direct Client initialized")

    async def close(self) -> None:
        """Close HTTP session"""
        if self._session:
            await self._session.close()
            self._session = None
            logger.info(
                "ByBit Direct Client closed",
                total_requests=self._request_count,
                total_errors=self._error_count,
            )

    def _create_signature(self, timestamp: int, params_str: str) -> str:
        """
        Create HMAC SHA256 signature for ByBit V5 API.

        Signature format: timestamp + api_key + recv_window + params_str

        Args:
            timestamp: Current timestamp in milliseconds
            params_str: Query string for GET or JSON body for POST

        Returns:
            Hex signature
        """
        payload = f"{timestamp}{self.api_key}{self.recv_window}{params_str}"
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature

    def _build_headers(self, timestamp: int, signature: str) -> dict[str, str]:
        """Build request headers with authentication"""
        return {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-TIMESTAMP": str(timestamp),
            "X-BAPI-SIGN": signature,
            "X-BAPI-SIGN-TYPE": "2",  # HMAC SHA256
            "X-BAPI-RECV-WINDOW": str(self.recv_window),
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        """
        Make HTTP request to ByBit API.

        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint (e.g., '/v5/market/tickers')
            params: Request parameters
            authenticated: Whether request requires authentication

        Returns:
            Response data

        Raises:
            ExchangeAPIError: On API errors
        """
        if not self._session:
            raise ExchangeAPIError("Client not initialized")

        self._request_count += 1
        url = f"{self.base_url}{endpoint}"
        params = params or {}

        headers = {}
        params_str = ""

        # Build query string for GET requests (authenticated or not)
        if method == "GET" and params:
            params_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
            url = f"{url}?{params_str}" if params_str else url

        if authenticated:
            timestamp = int(time.time() * 1000)

            if method == "POST":
                # For POST: params as JSON body for signature
                import json

                params_str = json.dumps(params) if params else ""

            signature = self._create_signature(timestamp, params_str)
            headers = self._build_headers(timestamp, signature)

        try:
            # Log request for debugging
            logger.debug(
                "bybit_api_request",
                method=method,
                url=url,
                params=params if method == "POST" else None,
                authenticated=authenticated,
            )

            if method == "GET":
                async with self._session.get(url, headers=headers) as response:
                    data = await response.json()
            elif method == "POST":
                async with self._session.post(
                    url, json=params, headers=headers
                ) as response:
                    data = await response.json()
            else:
                raise ExchangeAPIError(f"Unsupported method: {method}")

            # Check ByBit response code
            ret_code = data.get("retCode")
            ret_msg = data.get("retMsg", "Unknown error")

            if ret_code != 0:
                self._error_count += 1
                logger.error(
                    "ByBit API error",
                    endpoint=endpoint,
                    url=url,
                    ret_code=ret_code,
                    ret_msg=ret_msg,
                )
                raise self._map_error_code(ret_code, ret_msg)

            return data.get("result", {})

        except aiohttp.ClientError as e:
            self._error_count += 1
            logger.error("Network error", endpoint=endpoint, error=str(e))
            raise NetworkError(f"Network error: {e}") from e

    def _map_error_code(self, ret_code: int, ret_msg: str) -> ExchangeAPIError:
        """Map ByBit error codes to custom exceptions"""
        error_map = {
            10003: AuthenticationError,  # Invalid API key
            10004: AuthenticationError,  # Invalid signature
            10005: AuthenticationError,  # Permission denied
            10006: RateLimitError,  # Too many requests
            10016: ExchangeNotAvailableError,  # Service temporarily unavailable
            110001: InvalidOrderError,  # Order quantity invalid
            110003: InsufficientFundsError,  # Insufficient balance
            110007: InvalidOrderError,  # Order price invalid
            110025: OrderError,  # Order does not exist
        }

        error_class = error_map.get(ret_code, ExchangeAPIError)
        return error_class(f"ByBit error {ret_code}: {ret_msg}")

    @retry(
        retry=retry_if_exception_type((NetworkError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def fetch_balance(self) -> dict[str, Any]:
        """
        Fetch account balance.

        For Demo Trading (testnet), uses UNIFIED account type.
        For Production spot trading, uses SPOT account type.

        Returns:
            Dictionary with balance information in CCXT-compatible format
        """
        # Demo Trading requires UNIFIED account
        account_type = "UNIFIED" if self.testnet or self.market_type != "spot" else "SPOT"

        data = await self._request(
            "GET",
            "/v5/account/wallet-balance",
            {"accountType": account_type},
            authenticated=True,
        )

        # Convert to CCXT-compatible format
        coins = data.get("list", [{}])[0].get("coin", [])
        balance = {"total": {}, "free": {}, "used": {}}

        for coin_data in coins:
            currency = coin_data.get("coin", "")
            wallet_balance = coin_data.get("walletBalance", "0") or "0"
            available = coin_data.get("availableToWithdraw", "") or str(wallet_balance)

            total = float(wallet_balance) if wallet_balance else 0.0
            free = float(available) if available else total
            used = total - free

            balance["total"][currency] = total
            balance["free"][currency] = free if free >= 0 else 0
            balance["used"][currency] = used if used >= 0 else 0

        logger.debug("Fetched balance", account_type=account_type)
        return balance

    @retry(
        retry=retry_if_exception_type((NetworkError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def fetch_ticker(self, symbol: str) -> dict[str, Any]:
        """
        Fetch ticker data for a symbol.

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT' or 'BTCUSDT')

        Returns:
            Dictionary with ticker information in CCXT-compatible format
        """
        # Normalize symbol (remove slash)
        normalized_symbol = symbol.replace("/", "")

        data = await self._request(
            "GET",
            "/v5/market/tickers",
            {"category": self.category, "symbol": normalized_symbol},
            authenticated=False,
        )

        ticker_data = data.get("list", [{}])[0]

        # Convert to CCXT-compatible format
        ticker = {
            "symbol": symbol,
            "last": float(ticker_data.get("lastPrice", "0")),
            "bid": float(ticker_data.get("bid1Price", "0")),
            "ask": float(ticker_data.get("ask1Price", "0")),
            "high": float(ticker_data.get("highPrice24h", "0")),
            "low": float(ticker_data.get("lowPrice24h", "0")),
            "baseVolume": float(ticker_data.get("volume24h", "0")),
            "percentage": float(ticker_data.get("price24hPcnt", "0")) * 100,
        }

        logger.debug("Fetched ticker", symbol=symbol, last=ticker["last"])
        return ticker

    @retry(
        retry=retry_if_exception_type((NetworkError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def fetch_markets(self) -> dict[str, Any]:
        """
        Fetch available trading markets.

        Returns:
            Dictionary of markets in CCXT-compatible format
        """
        data = await self._request(
            "GET",
            "/v5/market/instruments-info",
            {"category": self.category},
            authenticated=False,
        )

        markets = {}
        for instrument in data.get("list", []):
            base = instrument.get("baseCoin", "")
            quote = instrument.get("quoteCoin", "")
            symbol = f"{base}/{quote}"

            lot_size_filter = instrument.get("lotSizeFilter", {})
            price_filter = instrument.get("priceFilter", {})

            markets[symbol] = {
                "id": instrument.get("symbol", ""),
                "symbol": symbol,
                "base": base,
                "quote": quote,
                "active": instrument.get("status", "") == "Trading",
                "limits": {
                    "amount": {
                        "min": float(lot_size_filter.get("minOrderQty", "0")),
                        "max": float(lot_size_filter.get("maxOrderQty", "0")),
                    },
                    "price": {
                        "min": float(price_filter.get("minPrice", "0")),
                        "max": float(price_filter.get("maxPrice", "0")),
                    },
                    "cost": {
                        "min": float(lot_size_filter.get("minOrderAmt", "0")),
                        "max": None,
                    },
                },
                "precision": {
                    "amount": int(lot_size_filter.get("basePrecision", "0.001")),
                    "price": int(price_filter.get("tickSize", "0.01")),
                },
            }

        logger.debug("Fetched markets", count=len(markets))
        return markets

    @retry(
        retry=retry_if_exception_type((NetworkError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def fetch_open_orders(
        self, symbol: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Fetch open orders.

        Args:
            symbol: Optional trading pair to filter

        Returns:
            List of open orders in CCXT-compatible format
        """
        params = {"category": self.category, "openOnly": 0}

        if symbol:
            params["symbol"] = symbol.replace("/", "")

        data = await self._request(
            "GET", "/v5/order/realtime", params, authenticated=True
        )

        orders = []
        for order_data in data.get("list", []):
            orders.append(
                {
                    "id": order_data.get("orderId", ""),
                    "clientOrderId": order_data.get("orderLinkId", ""),
                    "symbol": order_data.get("symbol", ""),
                    "type": order_data.get("orderType", "").lower(),
                    "side": order_data.get("side", "").lower(),
                    "price": float(order_data.get("price", "0")),
                    "amount": float(order_data.get("qty", "0")),
                    "filled": float(order_data.get("cumExecQty", "0")),
                    "remaining": float(order_data.get("leavesQty", "0")),
                    "status": order_data.get("orderStatus", "").lower(),
                    "timestamp": int(order_data.get("createdTime", "0")),
                }
            )

        logger.debug("Fetched open orders", count=len(orders))
        return orders

    @retry(
        retry=retry_if_exception_type((NetworkError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: Decimal,
        price: Decimal,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create a limit order.

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            side: 'buy' or 'sell'
            amount: Order amount in base currency
            price: Order price
            params: Additional parameters

        Returns:
            Order information
        """
        normalized_symbol = symbol.replace("/", "")
        params = params or {}

        order_params = {
            "category": self.category,
            "symbol": normalized_symbol,
            "side": "Buy" if side.lower() == "buy" else "Sell",
            "orderType": "Limit",
            "qty": str(amount),
            "price": str(price),
            "timeInForce": "GTC",  # Good Till Cancel
            "positionIdx": 0,  # One-way mode for futures
            **params,
        }

        data = await self._request(
            "POST", "/v5/order/create", order_params, authenticated=True
        )

        logger.info(
            "Created limit order",
            symbol=symbol,
            side=side,
            amount=amount,
            price=price,
            order_id=data.get("orderId"),
        )

        return {
            "id": data.get("orderId", ""),
            "clientOrderId": data.get("orderLinkId", ""),
            "symbol": symbol,
            "type": "limit",
            "side": side.lower(),
            "price": float(price),
            "amount": float(amount),
        }

    @retry(
        retry=retry_if_exception_type((NetworkError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: Decimal,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create a market order.

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            side: 'buy' or 'sell'
            amount: Order amount in base currency
            params: Additional parameters

        Returns:
            Order information
        """
        normalized_symbol = symbol.replace("/", "")
        params = params or {}

        order_params = {
            "category": self.category,
            "symbol": normalized_symbol,
            "side": "Buy" if side.lower() == "buy" else "Sell",
            "orderType": "Market",
            "qty": str(amount),
            **params,
        }

        data = await self._request(
            "POST", "/v5/order/create", order_params, authenticated=True
        )

        logger.info(
            "Created market order",
            symbol=symbol,
            side=side,
            amount=amount,
            order_id=data.get("orderId"),
        )

        return {
            "id": data.get("orderId", ""),
            "clientOrderId": data.get("orderLinkId", ""),
            "symbol": symbol,
            "type": "market",
            "side": side.lower(),
            "amount": float(amount),
        }
    async def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: float | None = None,
        params: dict | None = None,
    ) -> dict[str, Any]:
        """Create an order wrapper for compatibility."""
        if order_type.lower() == 'limit':
            if price is None:
                raise ValueError("Price required for limit orders")
            return await self.create_limit_order(symbol, side, amount, price, params)
        elif order_type.lower() == 'market':
            return await self.create_market_order(symbol, side, amount, params)
        else:
            raise ValueError(f"Unknown order type: {order_type}")


    def get_statistics(self) -> dict[str, Any]:
        """Get client statistics"""
        return {
            "exchange": "bybit",
            "testnet": self.testnet,
            "total_requests": self._request_count,
            "total_errors": self._error_count,
            "error_rate": (
                self._error_count / self._request_count
                if self._request_count > 0
                else 0
            ),
        }
