"""
Indicator Cache — In-memory cache for computed indicators.

Avoids re-computing expensive indicators (SMA, RSI, etc.) when
the same data and parameters are used across multiple backtests.

Usage:
    cache = IndicatorCache(max_size=1000)
    key = cache.make_key("sma", data_hash, period=20)
    result = cache.get_or_compute(key, lambda: compute_sma(data, 20))
"""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from decimal import Decimal
from typing import Any


class IndicatorCache:
    """In-memory cache with FIFO eviction for indicator computations."""

    def __init__(self, max_size: int = 1000) -> None:
        self.max_size = max_size
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        """Get cached value by key, or None if not found."""
        if key in self._cache:
            self._hits += 1
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return self._cache[key]
        self._misses += 1
        return None

    def put(self, key: str, value: Any) -> None:
        """Store a value in the cache."""
        if key in self._cache:
            self._cache.move_to_end(key)
            self._cache[key] = value
            return

        if len(self._cache) >= self.max_size:
            self._evict()

        self._cache[key] = value

    def get_or_compute(self, key: str, compute_fn: callable) -> Any:
        """Get from cache or compute and store."""
        result = self.get(key)
        if result is not None:
            return result

        result = compute_fn()
        self.put(key, result)
        return result

    def _evict(self) -> None:
        """Remove oldest 10% of entries."""
        n_remove = max(1, len(self._cache) // 10)
        for _ in range(n_remove):
            if self._cache:
                self._cache.popitem(last=False)

    @property
    def stats(self) -> dict[str, Any]:
        """Cache statistics."""
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0.0,
        }

    @staticmethod
    def make_key(indicator: str, data_hash: str, **params: Any) -> str:
        """Create a cache key from indicator name, data hash, and parameters."""
        param_str = json.dumps(params, sort_keys=True, default=str)
        return f"{indicator}:{data_hash}:{param_str}"

    @staticmethod
    def hash_data(data: Any) -> str:
        """Hash data for cache key generation."""
        if hasattr(data, "to_json"):
            # pandas DataFrame
            content = data.to_json()
        elif isinstance(data, (list, dict)):
            content = json.dumps(data, sort_keys=True, default=str)
        else:
            content = str(data)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        """Serialize cache to dict (Decimal-safe)."""
        serialized: dict[str, Any] = {}
        for key, value in self._cache.items():
            serialized[key] = self._serialize_value(value)
        return serialized

    @classmethod
    def from_dict(cls, data: dict[str, Any], max_size: int = 1000) -> IndicatorCache:
        """Deserialize cache from dict."""
        cache = cls(max_size=max_size)
        for key, value in data.items():
            cache._cache[key] = cls._deserialize_value(value)
        return cache

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        """Serialize a value, handling Decimal types."""
        if isinstance(value, Decimal):
            return {"__decimal__": str(value)}
        if isinstance(value, list):
            return [IndicatorCache._serialize_value(v) for v in value]
        if isinstance(value, dict):
            return {k: IndicatorCache._serialize_value(v) for k, v in value.items()}
        return value

    @staticmethod
    def _deserialize_value(value: Any) -> Any:
        """Deserialize a value, restoring Decimal types."""
        if isinstance(value, dict) and "__decimal__" in value:
            return Decimal(value["__decimal__"])
        if isinstance(value, list):
            return [IndicatorCache._deserialize_value(v) for v in value]
        if isinstance(value, dict):
            return {k: IndicatorCache._deserialize_value(v) for k, v in value.items()}
        return value
