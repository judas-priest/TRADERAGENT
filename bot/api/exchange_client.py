"""
Exchange API Client with CCXT wrapper
Handles rate limiting, retry logic, error handling, and WebSocket support
"""

import asyncio
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional

import ccxt.pro as ccxtpro
from ccxt.async_support import Exchange as CCXTExchange
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


class ExchangeAPIClient:
    """
    Wrapper around CCXT for unified exchange API access.

    Features:
    - Rate limit handling with automatic backoff
    - Retry logic for transient failures
    - Comprehensive error handling and mapping
    - WebSocket support for real-time data
    - Connection pooling and session management
    """

    def __init__(
        self,
        exchange_id: str,
        api_key: str,
        api_secret: str,
        password: Optional[str] = None,
        sandbox: bool = False,
        rate_limit: bool = True,
    ) -> None:
        """
        Initialize Exchange API Client.

        Args:
            exchange_id: Exchange identifier (e.g., 'binance', 'bybit')
            api_key: API key for authentication
            api_secret: API secret for authentication
            password: Optional password for exchanges that require it
            sandbox: Whether to use testnet/sandbox mode
            rate_limit: Whether to enable built-in rate limiting
        """
        self.exchange_id = exchange_id
        self._api_key = api_key
        self._api_secret = api_secret
        self._password = password
        self._sandbox = sandbox
        self._rate_limit = rate_limit

        # Initialize REST exchange
        self._exchange: Optional[CCXTExchange] = None

        # Initialize WebSocket exchange
        self._ws_exchange: Optional[ccxtpro.Exchange] = None

        # Rate limiting state
        self._last_request_time = 0.0
        self._min_request_interval = 0.1  # 100ms between requests

        # Statistics
        self._request_count = 0
        self._error_count = 0

        logger.info(
            "Initializing ExchangeAPIClient",
            exchange=exchange_id,
            sandbox=sandbox,
            rate_limit=rate_limit,
        )

    async def initialize(self) -> None:
        """Initialize the exchange connections"""
        try:
            # Create REST exchange instance
            exchange_class = getattr(ccxtpro, self.exchange_id)
            self._exchange = exchange_class(
                {
                    "apiKey": self._api_key,
                    "secret": self._api_secret,
                    "password": self._password,
                    "enableRateLimit": self._rate_limit,
                    "options": {
                        "defaultType": "spot",  # Can be configured per-exchange
                    },
                }
            )

            if self._sandbox:
                self._exchange.set_sandbox_mode(True)

            # Create WebSocket exchange instance
            self._ws_exchange = exchange_class(
                {
                    "apiKey": self._api_key,
                    "secret": self._api_secret,
                    "password": self._password,
                    "enableRateLimit": self._rate_limit,
                }
            )

            if self._sandbox:
                self._ws_exchange.set_sandbox_mode(True)

            # Load markets
            await self._exchange.load_markets()

            logger.info(
                "Exchange initialized successfully",
                exchange=self.exchange_id,
                markets_count=len(self._exchange.markets),
            )

        except Exception as e:
            logger.error(
                "Failed to initialize exchange",
                exchange=self.exchange_id,
                error=str(e),
            )
            raise ExchangeAPIError(f"Failed to initialize {self.exchange_id}: {e}") from e

    async def close(self) -> None:
        """Close exchange connections"""
        try:
            if self._exchange:
                await self._exchange.close()
            if self._ws_exchange:
                await self._ws_exchange.close()

            logger.info(
                "Exchange connections closed",
                exchange=self.exchange_id,
                total_requests=self._request_count,
                total_errors=self._error_count,
            )
        except Exception as e:
            logger.error("Error closing exchange connections", error=str(e))

    def _handle_rate_limit(self) -> None:
        """Implement manual rate limiting between requests"""
        if not self._rate_limit:
            return

        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time

        if time_since_last_request < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last_request
            time.sleep(sleep_time)

        self._last_request_time = time.time()

    def _map_ccxt_exception(self, e: Exception) -> ExchangeAPIError:
        """Map CCXT exceptions to custom exceptions"""
        error_str = str(e).lower()

        if isinstance(e, ccxtpro.RateLimitExceeded):
            return RateLimitError(f"Rate limit exceeded: {e}")
        elif isinstance(e, ccxtpro.AuthenticationError):
            return AuthenticationError(f"Authentication failed: {e}")
        elif isinstance(e, ccxtpro.InsufficientFunds):
            return InsufficientFundsError(f"Insufficient funds: {e}")
        elif isinstance(e, ccxtpro.InvalidOrder):
            return InvalidOrderError(f"Invalid order: {e}")
        elif isinstance(e, ccxtpro.OrderNotFound):
            return OrderError(f"Order not found: {e}")
        elif isinstance(e, ccxtpro.NetworkError):
            return NetworkError(f"Network error: {e}")
        elif isinstance(e, ccxtpro.ExchangeNotAvailable):
            return ExchangeNotAvailableError(f"Exchange not available: {e}")
        else:
            return ExchangeAPIError(f"Exchange API error: {e}")

    @retry(
        retry=retry_if_exception_type((NetworkError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def fetch_balance(self) -> Dict[str, Any]:
        """
        Fetch account balance.

        Returns:
            Dictionary with balance information
        """
        self._handle_rate_limit()
        self._request_count += 1

        try:
            if not self._exchange:
                raise ExchangeAPIError("Exchange not initialized")

            balance = await self._exchange.fetch_balance()
            logger.debug("Fetched balance", exchange=self.exchange_id)
            return balance

        except Exception as e:
            self._error_count += 1
            logger.error("Failed to fetch balance", error=str(e))
            raise self._map_ccxt_exception(e) from e

    @retry(
        retry=retry_if_exception_type((NetworkError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch ticker data for a symbol.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')

        Returns:
            Dictionary with ticker information
        """
        self._handle_rate_limit()
        self._request_count += 1

        try:
            if not self._exchange:
                raise ExchangeAPIError("Exchange not initialized")

            ticker = await self._exchange.fetch_ticker(symbol)
            logger.debug("Fetched ticker", symbol=symbol, last=ticker.get("last"))
            return ticker

        except Exception as e:
            self._error_count += 1
            logger.error("Failed to fetch ticker", symbol=symbol, error=str(e))
            raise self._map_ccxt_exception(e) from e

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
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a limit order.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            side: 'buy' or 'sell'
            amount: Order amount in base currency
            price: Order price
            params: Additional exchange-specific parameters

        Returns:
            Dictionary with order information
        """
        self._handle_rate_limit()
        self._request_count += 1

        try:
            if not self._exchange:
                raise ExchangeAPIError("Exchange not initialized")

            order = await self._exchange.create_limit_order(
                symbol=symbol,
                side=side,
                amount=float(amount),
                price=float(price),
                params=params or {},
            )

            logger.info(
                "Created limit order",
                symbol=symbol,
                side=side,
                amount=amount,
                price=price,
                order_id=order.get("id"),
            )
            return order

        except Exception as e:
            self._error_count += 1
            logger.error(
                "Failed to create limit order",
                symbol=symbol,
                side=side,
                amount=amount,
                price=price,
                error=str(e),
            )
            raise self._map_ccxt_exception(e) from e

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
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a market order.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            side: 'buy' or 'sell'
            amount: Order amount in base currency
            params: Additional exchange-specific parameters

        Returns:
            Dictionary with order information
        """
        self._handle_rate_limit()
        self._request_count += 1

        try:
            if not self._exchange:
                raise ExchangeAPIError("Exchange not initialized")

            order = await self._exchange.create_market_order(
                symbol=symbol,
                side=side,
                amount=float(amount),
                params=params or {},
            )

            logger.info(
                "Created market order",
                symbol=symbol,
                side=side,
                amount=amount,
                order_id=order.get("id"),
            )
            return order

        except Exception as e:
            self._error_count += 1
            logger.error(
                "Failed to create market order",
                symbol=symbol,
                side=side,
                amount=amount,
                error=str(e),
            )
            raise self._map_ccxt_exception(e) from e

    @retry(
        retry=retry_if_exception_type((NetworkError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def cancel_order(
        self, order_id: str, symbol: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Cancel an order.

        Args:
            order_id: Order ID to cancel
            symbol: Trading pair symbol
            params: Additional exchange-specific parameters

        Returns:
            Dictionary with cancellation result
        """
        self._handle_rate_limit()
        self._request_count += 1

        try:
            if not self._exchange:
                raise ExchangeAPIError("Exchange not initialized")

            result = await self._exchange.cancel_order(
                id=order_id,
                symbol=symbol,
                params=params or {},
            )

            logger.info(
                "Cancelled order",
                order_id=order_id,
                symbol=symbol,
            )
            return result

        except Exception as e:
            self._error_count += 1
            logger.error(
                "Failed to cancel order",
                order_id=order_id,
                symbol=symbol,
                error=str(e),
            )
            raise self._map_ccxt_exception(e) from e

    @retry(
        retry=retry_if_exception_type((NetworkError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def fetch_order(
        self, order_id: str, symbol: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Fetch order details.

        Args:
            order_id: Order ID to fetch
            symbol: Trading pair symbol
            params: Additional exchange-specific parameters

        Returns:
            Dictionary with order information
        """
        self._handle_rate_limit()
        self._request_count += 1

        try:
            if not self._exchange:
                raise ExchangeAPIError("Exchange not initialized")

            order = await self._exchange.fetch_order(
                id=order_id,
                symbol=symbol,
                params=params or {},
            )

            logger.debug(
                "Fetched order",
                order_id=order_id,
                symbol=symbol,
                status=order.get("status"),
            )
            return order

        except Exception as e:
            self._error_count += 1
            logger.error(
                "Failed to fetch order",
                order_id=order_id,
                symbol=symbol,
                error=str(e),
            )
            raise self._map_ccxt_exception(e) from e

    @retry(
        retry=retry_if_exception_type((NetworkError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def fetch_open_orders(
        self, symbol: Optional[str] = None, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch open orders.

        Args:
            symbol: Optional trading pair symbol to filter
            params: Additional exchange-specific parameters

        Returns:
            List of open orders
        """
        self._handle_rate_limit()
        self._request_count += 1

        try:
            if not self._exchange:
                raise ExchangeAPIError("Exchange not initialized")

            orders = await self._exchange.fetch_open_orders(
                symbol=symbol,
                params=params or {},
            )

            logger.debug(
                "Fetched open orders",
                symbol=symbol or "all",
                count=len(orders),
            )
            return orders

        except Exception as e:
            self._error_count += 1
            logger.error(
                "Failed to fetch open orders",
                symbol=symbol,
                error=str(e),
            )
            raise self._map_ccxt_exception(e) from e

    async def watch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Watch ticker updates via WebSocket.

        Args:
            symbol: Trading pair symbol

        Returns:
            Dictionary with ticker information
        """
        try:
            if not self._ws_exchange:
                raise ExchangeAPIError("WebSocket exchange not initialized")

            ticker = await self._ws_exchange.watch_ticker(symbol)
            return ticker

        except Exception as e:
            logger.error(
                "Failed to watch ticker",
                symbol=symbol,
                error=str(e),
            )
            raise self._map_ccxt_exception(e) from e

    async def watch_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Watch order updates via WebSocket.

        Args:
            symbol: Optional trading pair symbol to filter

        Returns:
            List of order updates
        """
        try:
            if not self._ws_exchange:
                raise ExchangeAPIError("WebSocket exchange not initialized")

            orders = await self._ws_exchange.watch_orders(symbol)
            return orders

        except Exception as e:
            logger.error(
                "Failed to watch orders",
                symbol=symbol,
                error=str(e),
            )
            raise self._map_ccxt_exception(e) from e

    def get_statistics(self) -> Dict[str, Any]:
        """Get client statistics"""
        return {
            "exchange": self.exchange_id,
            "total_requests": self._request_count,
            "total_errors": self._error_count,
            "error_rate": (
                self._error_count / self._request_count if self._request_count > 0 else 0
            ),
        }
