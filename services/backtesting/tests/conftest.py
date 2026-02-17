"""Shared test fixtures and helpers for grid backtester tests."""

import numpy as np
import pandas as pd
import pytest


def make_candles(
    n: int = 100,
    start_price: float = 45000.0,
    volatility: float = 0.01,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate synthetic OHLCV candles with realistic price movement."""
    rng = np.random.RandomState(seed)
    prices = [start_price]
    for _ in range(n - 1):
        change = rng.normal(0, volatility)
        prices.append(prices[-1] * (1 + change))

    rows = []
    for i, close in enumerate(prices):
        high = close * (1 + abs(rng.normal(0, volatility / 2)))
        low = close * (1 - abs(rng.normal(0, volatility / 2)))
        open_price = prices[i - 1] if i > 0 else close
        rows.append({
            "timestamp": f"2025-01-01T{i:04d}",
            "open": open_price,
            "high": max(high, open_price, close),
            "low": min(low, open_price, close),
            "close": close,
            "volume": float(rng.uniform(100, 1000)),
        })

    return pd.DataFrame(rows)


def make_ranging_candles(
    n: int = 100,
    center: float = 45000.0,
    spread: float = 500.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate candles oscillating within a tight range (ideal for grid)."""
    rng = np.random.RandomState(seed)
    rows = []
    prev_close = center

    for i in range(n):
        target = center + rng.uniform(-spread, spread)
        close = prev_close + (target - prev_close) * 0.3
        high = close + abs(rng.normal(0, spread * 0.1))
        low = close - abs(rng.normal(0, spread * 0.1))
        open_price = prev_close

        rows.append({
            "timestamp": f"2025-01-01T{i:04d}",
            "open": open_price,
            "high": max(high, open_price, close),
            "low": min(low, open_price, close),
            "close": close,
            "volume": float(rng.uniform(100, 1000)),
        })
        prev_close = close

    return pd.DataFrame(rows)


def make_stable_candles(n: int = 100, seed: int = 42) -> pd.DataFrame:
    """Generate candles with very low volatility (stablecoin-like)."""
    return make_candles(n=n, start_price=1.0, volatility=0.0005, seed=seed)


def make_meme_candles(n: int = 100, seed: int = 42) -> pd.DataFrame:
    """Generate candles with very high volatility (meme coin-like)."""
    return make_candles(n=n, start_price=0.1, volatility=0.05, seed=seed)


@pytest.fixture
def candles_100():
    return make_candles(n=100)


@pytest.fixture
def ranging_candles_200():
    return make_ranging_candles(n=200, center=45000.0, spread=800.0)
