"""
IndicatorCache — Cache ATR/EMA calculations across trials (Issue #10).

Since multiple optimization trials use the same candle data, indicator
calculations (ATR, EMA, etc.) can be cached and shared between trials
to avoid redundant computation.
"""

import hashlib
import json
from decimal import Decimal
from typing import Any

from grid_backtester.logging import get_logger

logger = get_logger(__name__)


class IndicatorCache:
    """
    In-memory cache for indicator calculations.

    Cache key is derived from the hash of input data + parameters.
    Thread-safe for read operations (shared between ProcessPoolExecutor workers
    via serialization, not shared memory).
    """

    def __init__(self, max_size: int = 1000) -> None:
        self._cache: dict[str, Any] = {}
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        """Get cached value by key."""
        value = self._cache.get(key)
        if value is not None:
            self._hits += 1
        else:
            self._misses += 1
        return value

    def put(self, key: str, value: Any) -> None:
        """Cache a value. Evicts oldest entries if at capacity."""
        if len(self._cache) >= self._max_size:
            # Remove oldest 10%
            remove_count = max(1, self._max_size // 10)
            keys_to_remove = list(self._cache.keys())[:remove_count]
            for k in keys_to_remove:
                del self._cache[k]
            logger.debug("Cache eviction", evicted=remove_count)

        self._cache[key] = value

    def get_or_compute(self, key: str, compute_fn: Any) -> Any:
        """Get cached value or compute and cache it."""
        value = self.get(key)
        if value is not None:
            return value
        value = compute_fn()
        self.put(key, value)
        return value

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    @property
    def stats(self) -> dict[str, Any]:
        """Cache statistics."""
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 4) if total > 0 else 0.0,
        }

    @staticmethod
    def make_key(indicator: str, data_hash: str, **params: Any) -> str:
        """Build a cache key from indicator name, data hash, and parameters."""
        param_str = json.dumps(params, sort_keys=True)
        return f"{indicator}:{data_hash}:{param_str}"

    @staticmethod
    def hash_data(data: list[float] | list[Decimal]) -> str:
        """Generate a short hash of numeric data for cache keys."""
        serialized = ",".join(str(x) for x in data)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
