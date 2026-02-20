"""
Exchange API Client v2.0 with CCXT wrapper.

Improvements over v1.0:
- Async rate limiting (non-blocking)
- OHLCV and order book fetching
- WebSocket OHLCV/trades streaming
- Connection health checks
- Adaptive rate limiting
- Enhanced statistics and error tracking
"""

import asyncio
import time
from collections import deque
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

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
    - Rate limit handling with async backoff (non-blocking)
    - Retry logic for transient failures
    - Comprehensive error handling and mapping
    - WebSocket support for real-time data (ticker, orders, OHLCV, trades)
    - Connection health checks
    - OHLCV and order book fetching
    - Enhanced statistics tracking
    """

    def __init__(
        self,
        exchange_id: str,
        api_key: str,
        api_secret: str,
        password: str | None = None,
        sandbox: bool = False,
        rate_limit: bool = True,
        default_type: str = "spot",
        max_retries: int = 3,
    ) -> None:
        self.exchange_id = exchange_id
        self._api_key = api_key
        self._api_secret = api_secret
        self._password = password
        self._sandbox = sandbox
        self._rate_limit = rate_limit
        self._default_type = default_type
        self._max_retries = max_retries

        # Exchange instances
        self._exchange: CCXTExchange | None = None
        self._ws_exchange: ccxtpro.Exchange | None = None

        # Async rate limiting
        self._rate_lock = asyncio.Lock()
        self._last_request_time = 0.0
        self._min_request_interval = 0.1  # 100ms default
        self._adaptive_interval = 0.1  # Adjusts on rate limit hits

        # Statistics
        self._request_count = 0
        self._error_count = 0
        self._rate_limit_hits = 0
        self._last_error: str | None = None
        self._last_error_time: datetime | None = None
        self._initialized = False
        self._initialized_at: datetime | None = None

        # Recent latencies for monitoring
        self._latencies: deque[float] = deque(maxlen=100)

        logger.info(
            "Initializing ExchangeAPIClient",
            exchange=exchange_id,
            sandbox=sandbox,
            rate_limit=rate_limit,
            default_type=default_type,
        )

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def markets(self) -> dict[str, Any]:
        if self._exchange:
            return self._exchange.markets
        return {}

    async def initialize(self) -> None:
        """Initialize exchange REST and WebSocket connections."""
        try:
            exchange_class = getattr(ccxtpro, self.exchange_id)
            config = {
                "apiKey": self._api_key,
                "secret": self._api_secret,
                "password": self._password,
                "enableRateLimit": self._rate_limit,
                "options": {
                    "defaultType": self._default_type,
                },
            }

            self._exchange = exchange_class(config)
            if self._sandbox:
                self._exchange.set_sandbox_mode(True)

            # WebSocket instance
            ws_config = {
                "apiKey": self._api_key,
                "secret": self._api_secret,
                "password": self._password,
                "enableRateLimit": self._rate_limit,
            }
            self._ws_exchange = exchange_class(ws_config)
            if self._sandbox:
                self._ws_exchange.set_sandbox_mode(True)

            await self._exchange.load_markets()

            self._initialized = True
            self._initialized_at = datetime.now(timezone.utc)

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
        """Close all exchange connections."""
        try:
            if self._exchange:
                await self._exchange.close()
            if self._ws_exchange:
                await self._ws_exchange.close()
            self._initialized = False

            logger.info(
                "Exchange connections closed",
                exchange=self.exchange_id,
                total_requests=self._request_count,
                total_errors=self._error_count,
            )
        except Exception as e:
            logger.error("Error closing exchange connections", error=str(e))

    async def health_check(self) -> bool:
        """Check if exchange connection is healthy."""
        if not self._initialized or not self._exchange:
            return False
        try:
            await self._exchange.fetch_time()
            return True
        except Exception as e:
            logger.warning("Exchange health check failed", error=str(e))
            return False

    # =========================================================================
    # Rate Limiting (async, non-blocking)
    # =========================================================================

    async def _handle_rate_limit(self) -> None:
        """Async rate limiting — does not block the event loop."""
        if not self._rate_limit:
            return

        async with self._rate_lock:
            current_time = time.monotonic()
            elapsed = current_time - self._last_request_time

            if elapsed < self._adaptive_interval:
                await asyncio.sleep(self._adaptive_interval - elapsed)

            self._last_request_time = time.monotonic()

    def _on_rate_limit_hit(self) -> None:
        """Adaptively increase interval on rate limit hits."""
        self._rate_limit_hits += 1
        self._adaptive_interval = min(self._adaptive_interval * 1.5, 2.0)
        logger.warning(
            "Rate limit hit, increasing interval",
            new_interval=self._adaptive_interval,
            total_hits=self._rate_limit_hits,
        )

    def _on_request_success(self) -> None:
        """Gradually reduce interval on success."""
        if self._adaptive_interval > self._min_request_interval:
            self._adaptive_interval = max(
                self._adaptive_interval * 0.95,
                self._min_request_interval,
            )

    # =========================================================================
    # Exception Mapping
    # =========================================================================

    def _map_ccxt_exception(self, e: Exception) -> ExchangeAPIError:
        """Map CCXT exceptions to custom exceptions."""
        self._last_error = str(e)
        self._last_error_time = datetime.now(timezone.utc)

        # Check more specific subclasses before their parents
        if isinstance(e, ccxtpro.RateLimitExceeded):
            self._on_rate_limit_hit()
            return RateLimitError(f"Rate limit exceeded: {e}")
        elif isinstance(e, ccxtpro.AuthenticationError):
            return AuthenticationError(f"Authentication failed: {e}")
        elif isinstance(e, ccxtpro.InsufficientFunds):
            return InsufficientFundsError(f"Insufficient funds: {e}")
        elif isinstance(e, ccxtpro.OrderNotFound):
            return OrderError(f"Order not found: {e}")
        elif isinstance(e, ccxtpro.InvalidOrder):
            return InvalidOrderError(f"Invalid order: {e}")
        elif isinstance(e, ccxtpro.ExchangeNotAvailable):
            return ExchangeNotAvailableError(f"Exchange not available: {e}")
        elif isinstance(e, ccxtpro.NetworkError):
            return NetworkError(f"Network error: {e}")
        else:
            return ExchangeAPIError(f"Exchange API error: {e}")

    def _ensure_initialized(self) -> None:
        """Raise if exchange is not initialized."""
        if not self._exchange:
            raise ExchangeAPIError("Exchange not initialized")

    async def _tracked_request(self, coro):
        """Execute a request with rate limiting, stats tracking, and latency measurement."""
        await self._handle_rate_limit()
        self._request_count += 1
        start = time.monotonic()
        try:
            result = await coro
            latency = (time.monotonic() - start) * 1000  # ms
            self._latencies.append(latency)
            self._on_request_success()
            return result
        except Exception as e:
            self._error_count += 1
            raise self._map_ccxt_exception(e) from e

    # =========================================================================
    # Market Data
    # =========================================================================

    @retry(
        retry=retry_if_exception_type((NetworkError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def fetch_balance(self) -> dict[str, Any]:
        """Fetch account balance."""
        self._ensure_initialized()
        return await self._tracked_request(self._exchange.fetch_balance())

    @retry(
        retry=retry_if_exception_type((NetworkError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def fetch_ticker(self, symbol: str) -> dict[str, Any]:
        """Fetch ticker data for a symbol."""
        self._ensure_initialized()
        return await self._tracked_request(self._exchange.fetch_ticker(symbol))

    @retry(
        retry=retry_if_exception_type((NetworkError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        since: int | None = None,
        limit: int | None = None,
        params: dict[str, Any] | None = None,
    ) -> list[list]:
        """
        Fetch OHLCV candlestick data.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            timeframe: Candle timeframe (e.g., '1m', '5m', '1h', '1d')
            since: Timestamp in ms to start from
            limit: Maximum number of candles to return
            params: Additional exchange-specific parameters

        Returns:
            List of [timestamp, open, high, low, close, volume] lists.
        """
        self._ensure_initialized()
        return await self._tracked_request(
            self._exchange.fetch_ohlcv(
                symbol, timeframe, since=since, limit=limit, params=params or {}
            )
        )

    @retry(
        retry=retry_if_exception_type((NetworkError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def fetch_order_book(
        self,
        symbol: str,
        limit: int | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Fetch order book for a symbol.

        Args:
            symbol: Trading pair symbol
            limit: Number of order book entries
            params: Additional parameters

        Returns:
            Dictionary with 'bids', 'asks', 'timestamp', etc.
        """
        self._ensure_initialized()
        return await self._tracked_request(
            self._exchange.fetch_order_book(symbol, limit=limit, params=params or {})
        )

    @retry(
        retry=retry_if_exception_type((NetworkError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def fetch_trades(
        self,
        symbol: str,
        since: int | None = None,
        limit: int | None = None,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch recent trades for a symbol."""
        self._ensure_initialized()
        return await self._tracked_request(
            self._exchange.fetch_trades(symbol, since=since, limit=limit, params=params or {})
        )

    # =========================================================================
    # Order Management
    # =========================================================================

    async def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: float | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create an order (limit or market)."""
        if order_type == "limit" and price is not None:
            return await self.create_limit_order(
                symbol=symbol,
                side=side,
                amount=Decimal(str(amount)),
                price=Decimal(str(price)),
                params=params,
            )
        else:
            return await self.create_market_order(
                symbol=symbol,
                side=side,
                amount=Decimal(str(amount)),
                params=params,
            )

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
        """Create a limit order."""
        self._ensure_initialized()
        try:
            result = await self._tracked_request(
                self._exchange.create_limit_order(
                    symbol=symbol,
                    side=side,
                    amount=float(amount),
                    price=float(price),
                    params=params or {},
                )
            )
            logger.info(
                "Created limit order",
                symbol=symbol,
                side=side,
                amount=str(amount),
                price=str(price),
                order_id=result.get("id"),
            )
            return result
        except ExchangeAPIError:
            raise
        except Exception as e:
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
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a market order."""
        self._ensure_initialized()
        try:
            result = await self._tracked_request(
                self._exchange.create_market_order(
                    symbol=symbol,
                    side=side,
                    amount=float(amount),
                    params=params or {},
                )
            )
            logger.info(
                "Created market order",
                symbol=symbol,
                side=side,
                amount=str(amount),
                order_id=result.get("id"),
            )
            return result
        except ExchangeAPIError:
            raise
        except Exception as e:
            raise self._map_ccxt_exception(e) from e

    @retry(
        retry=retry_if_exception_type((NetworkError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def cancel_order(
        self, order_id: str, symbol: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Cancel an order."""
        self._ensure_initialized()
        try:
            result = await self._tracked_request(
                self._exchange.cancel_order(id=order_id, symbol=symbol, params=params or {})
            )
            logger.info("Cancelled order", order_id=order_id, symbol=symbol)
            return result
        except ExchangeAPIError:
            raise
        except Exception as e:
            raise self._map_ccxt_exception(e) from e

    @retry(
        retry=retry_if_exception_type((NetworkError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def cancel_all_orders(self, symbol: str) -> list[dict[str, Any]]:
        """Cancel all open orders for a symbol."""
        self._ensure_initialized()
        try:
            result = await self._tracked_request(self._exchange.cancel_all_orders(symbol))
            logger.info("All orders cancelled", symbol=symbol)
            return result
        except ExchangeAPIError:
            raise
        except Exception as e:
            raise self._map_ccxt_exception(e) from e

    @retry(
        retry=retry_if_exception_type((NetworkError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def fetch_order(
        self, order_id: str, symbol: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Fetch order details."""
        self._ensure_initialized()
        return await self._tracked_request(
            self._exchange.fetch_order(id=order_id, symbol=symbol, params=params or {})
        )

    @retry(
        retry=retry_if_exception_type((NetworkError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def fetch_open_orders(
        self, symbol: str | None = None, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Fetch open orders."""
        self._ensure_initialized()
        return await self._tracked_request(
            self._exchange.fetch_open_orders(symbol=symbol, params=params or {})
        )

    @retry(
        retry=retry_if_exception_type((NetworkError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def fetch_closed_orders(
        self,
        symbol: str | None = None,
        since: int | None = None,
        limit: int | None = None,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch closed/completed orders."""
        self._ensure_initialized()
        return await self._tracked_request(
            self._exchange.fetch_closed_orders(
                symbol=symbol, since=since, limit=limit, params=params or {}
            )
        )

    @retry(
        retry=retry_if_exception_type((NetworkError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def set_leverage(
        self,
        leverage: int,
        symbol: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Set leverage for a symbol (futures/margin)."""
        self._ensure_initialized()
        return await self._tracked_request(
            self._exchange.set_leverage(leverage, symbol, params=params or {})
        )

    # =========================================================================
    # WebSocket Streams
    # =========================================================================

    async def watch_ticker(self, symbol: str) -> dict[str, Any]:
        """Watch ticker updates via WebSocket."""
        if not self._ws_exchange:
            raise ExchangeAPIError("WebSocket exchange not initialized")
        try:
            return await self._ws_exchange.watch_ticker(symbol)
        except Exception as e:
            raise self._map_ccxt_exception(e) from e

    async def watch_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        """Watch order updates via WebSocket."""
        if not self._ws_exchange:
            raise ExchangeAPIError("WebSocket exchange not initialized")
        try:
            return await self._ws_exchange.watch_orders(symbol)
        except Exception as e:
            raise self._map_ccxt_exception(e) from e

    async def watch_ohlcv(self, symbol: str, timeframe: str = "1m") -> list[list]:
        """Watch OHLCV candles via WebSocket."""
        if not self._ws_exchange:
            raise ExchangeAPIError("WebSocket exchange not initialized")
        try:
            return await self._ws_exchange.watch_ohlcv(symbol, timeframe)
        except Exception as e:
            raise self._map_ccxt_exception(e) from e

    async def watch_trades(self, symbol: str) -> list[dict[str, Any]]:
        """Watch trade updates via WebSocket."""
        if not self._ws_exchange:
            raise ExchangeAPIError("WebSocket exchange not initialized")
        try:
            return await self._ws_exchange.watch_trades(symbol)
        except Exception as e:
            raise self._map_ccxt_exception(e) from e

    async def watch_order_book(self, symbol: str, limit: int | None = None) -> dict[str, Any]:
        """Watch order book via WebSocket."""
        if not self._ws_exchange:
            raise ExchangeAPIError("WebSocket exchange not initialized")
        try:
            return await self._ws_exchange.watch_order_book(symbol, limit)
        except Exception as e:
            raise self._map_ccxt_exception(e) from e

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_statistics(self) -> dict[str, Any]:
        """Get comprehensive client statistics."""
        avg_latency = sum(self._latencies) / len(self._latencies) if self._latencies else 0.0
        return {
            "exchange": self.exchange_id,
            "initialized": self._initialized,
            "initialized_at": self._initialized_at.isoformat() if self._initialized_at else None,
            "total_requests": self._request_count,
            "total_errors": self._error_count,
            "rate_limit_hits": self._rate_limit_hits,
            "error_rate": (
                self._error_count / self._request_count if self._request_count > 0 else 0.0
            ),
            "avg_latency_ms": round(avg_latency, 2),
            "adaptive_interval": round(self._adaptive_interval, 4),
            "last_error": self._last_error,
            "last_error_time": self._last_error_time.isoformat() if self._last_error_time else None,
        }
