"""Tests for IndicatorCache — in-memory cache for indicator calculations."""

from decimal import Decimal

import pytest

from grid_backtester.caching.indicator_cache import IndicatorCache


class TestIndicatorCache:

    def test_put_and_get(self):
        cache = IndicatorCache()
        cache.put("key1", 42.0)
        assert cache.get("key1") == 42.0

    def test_get_miss_returns_none(self):
        cache = IndicatorCache()
        assert cache.get("nonexistent") is None

    def test_get_or_compute_caches(self):
        cache = IndicatorCache()
        call_count = 0

        def compute():
            nonlocal call_count
            call_count += 1
            return 99.0

        # First call computes
        result1 = cache.get_or_compute("key", compute)
        assert result1 == 99.0
        assert call_count == 1

        # Second call returns cached
        result2 = cache.get_or_compute("key", compute)
        assert result2 == 99.0
        assert call_count == 1  # Not called again

    def test_stats_tracking(self):
        cache = IndicatorCache()
        cache.put("a", 1)
        cache.get("a")      # hit
        cache.get("a")      # hit
        cache.get("miss")   # miss

        stats = cache.stats
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["size"] == 1
        assert stats["hit_rate"] == pytest.approx(2 / 3, abs=0.01)

    def test_lru_eviction(self):
        cache = IndicatorCache(max_size=10)

        # Fill beyond capacity
        for i in range(12):
            cache.put(f"key_{i}", i)

        stats = cache.stats
        assert stats["size"] <= 11  # Should have evicted some

    def test_clear(self):
        cache = IndicatorCache()
        cache.put("a", 1)
        cache.put("b", 2)

        cache.clear()
        assert cache.get("a") is None
        assert cache.stats["size"] == 0
        assert cache.stats["hits"] == 0
        assert cache.stats["misses"] == 1  # From the get("a") after clear

    def test_make_key(self):
        key = IndicatorCache.make_key("atr", "abc123", period=14)
        assert "atr" in key
        assert "abc123" in key
        assert "14" in key

    def test_make_key_deterministic(self):
        key1 = IndicatorCache.make_key("atr", "hash1", period=14, multiplier=3.0)
        key2 = IndicatorCache.make_key("atr", "hash1", period=14, multiplier=3.0)
        assert key1 == key2

    def test_make_key_different_params(self):
        key1 = IndicatorCache.make_key("atr", "hash1", period=14)
        key2 = IndicatorCache.make_key("atr", "hash1", period=21)
        assert key1 != key2

    def test_hash_data_float(self):
        data = [1.0, 2.0, 3.0]
        h = IndicatorCache.hash_data(data)
        assert isinstance(h, str)
        assert len(h) == 16

    def test_hash_data_decimal(self):
        data = [Decimal("1.0"), Decimal("2.0")]
        h = IndicatorCache.hash_data(data)
        assert isinstance(h, str)
        assert len(h) == 16

    def test_hash_data_deterministic(self):
        data = [45000.0, 45100.0, 44900.0]
        h1 = IndicatorCache.hash_data(data)
        h2 = IndicatorCache.hash_data(data)
        assert h1 == h2

    def test_hash_data_different_for_different_data(self):
        h1 = IndicatorCache.hash_data([1.0, 2.0])
        h2 = IndicatorCache.hash_data([3.0, 4.0])
        assert h1 != h2

    def test_max_size_respected(self):
        cache = IndicatorCache(max_size=5)
        for i in range(10):
            cache.put(f"k{i}", i)
        assert cache.stats["size"] <= 5
