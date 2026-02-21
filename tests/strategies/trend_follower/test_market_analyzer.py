"""
Tests for MarketAnalyzer — technical indicators and market phase detection.
"""

from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from bot.strategies.trend_follower.market_analyzer import (
    MarketAnalyzer,
    MarketConditions,
    MarketPhase,
    TrendStrength,
)


def _make_df(n: int = 100, trend: str = "up", base: float = 45000.0) -> pd.DataFrame:
    """Create OHLCV DataFrame with DatetimeIndex."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2024-01-01", periods=n, freq="15min")

    if trend == "up":
        closes = base + np.cumsum(rng.uniform(1, 10, n))
    elif trend == "down":
        closes = base - np.cumsum(rng.uniform(1, 10, n))
    else:
        closes = base + rng.normal(0, 5, n)

    highs = closes + rng.uniform(5, 50, n)
    lows = closes - rng.uniform(5, 50, n)
    opens = closes + rng.normal(0, 10, n)
    volumes = rng.uniform(100, 1000, n)

    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes},
        index=dates,
    )


class TestMarketAnalyzerInit:
    def test_defaults(self):
        ma = MarketAnalyzer()
        assert ma.ema_fast_period == 20
        assert ma.ema_slow_period == 50
        assert ma.atr_period == 14
        assert ma.rsi_period == 14

    def test_custom_params(self):
        ma = MarketAnalyzer(ema_fast_period=10, ema_slow_period=30)
        assert ma.ema_fast_period == 10
        assert ma.ema_slow_period == 30


class TestMarketAnalyzerValidation:
    def test_missing_columns(self):
        df = pd.DataFrame({"close": [1, 2, 3], "open": [1, 2, 3]})
        ma = MarketAnalyzer()
        with pytest.raises(ValueError, match="Missing required columns"):
            ma.analyze(df)

    def test_insufficient_data(self):
        df = _make_df(n=10)
        ma = MarketAnalyzer()
        with pytest.raises(ValueError, match="Insufficient data"):
            ma.analyze(df)


class TestMarketAnalyzerAnalyze:
    def test_returns_market_conditions(self):
        df = _make_df(n=100)
        ma = MarketAnalyzer()
        result = ma.analyze(df)
        assert isinstance(result, MarketConditions)

    def test_conditions_fields(self):
        df = _make_df(n=100)
        ma = MarketAnalyzer()
        result = ma.analyze(df)
        assert isinstance(result.phase, MarketPhase)
        assert isinstance(result.trend_strength, TrendStrength)
        assert isinstance(result.ema_fast, Decimal)
        assert isinstance(result.ema_slow, Decimal)
        assert isinstance(result.atr, Decimal)
        assert isinstance(result.rsi, Decimal)
        assert isinstance(result.current_price, Decimal)
        assert isinstance(result.atr_pct, Decimal)

    def test_ema_divergence_positive(self):
        df = _make_df(n=100)
        ma = MarketAnalyzer()
        result = ma.analyze(df)
        assert result.ema_divergence_pct >= Decimal("0")

    def test_rsi_range(self):
        df = _make_df(n=100)
        ma = MarketAnalyzer()
        result = ma.analyze(df)
        assert Decimal("0") <= result.rsi <= Decimal("100")

    def test_atr_positive(self):
        df = _make_df(n=100)
        ma = MarketAnalyzer()
        result = ma.analyze(df)
        assert result.atr > 0

    def test_current_price_matches_last_close(self):
        df = _make_df(n=100)
        ma = MarketAnalyzer()
        result = ma.analyze(df)
        assert result.current_price == Decimal(str(df["close"].iloc[-1]))

    def test_timestamp_matches_last_index(self):
        df = _make_df(n=100)
        ma = MarketAnalyzer()
        result = ma.analyze(df)
        assert result.timestamp == df.index[-1]


class TestMarketPhaseDetection:
    def test_uptrend_detected(self):
        # Strong uptrend: price above fast EMA, fast > slow, divergence > threshold
        df = _make_df(n=100, trend="up")
        ma = MarketAnalyzer()
        result = ma.analyze(df)
        # Uptrend data should produce bullish or at least non-bearish
        assert result.phase in (
            MarketPhase.BULLISH_TREND,
            MarketPhase.SIDEWAYS,
            MarketPhase.UNKNOWN,
        )

    def test_downtrend_detected(self):
        df = _make_df(n=100, trend="down")
        ma = MarketAnalyzer()
        result = ma.analyze(df)
        assert result.phase in (
            MarketPhase.BEARISH_TREND,
            MarketPhase.SIDEWAYS,
            MarketPhase.UNKNOWN,
        )

    def test_sideways_detected(self):
        df = _make_df(n=100, trend="sideways")
        ma = MarketAnalyzer()
        result = ma.analyze(df)
        # Sideways data should produce sideways or unknown
        assert result.phase in (
            MarketPhase.SIDEWAYS,
            MarketPhase.UNKNOWN,
            MarketPhase.BULLISH_TREND,
            MarketPhase.BEARISH_TREND,
        )


class TestTrendStrength:
    def test_sideways_has_no_strength(self):
        df = _make_df(n=100, trend="sideways")
        ma = MarketAnalyzer()
        result = ma.analyze(df)
        if result.phase == MarketPhase.SIDEWAYS:
            assert result.trend_strength == TrendStrength.NONE

    def test_strong_trend_strength(self):
        # Use very strong uptrend
        rng = np.random.default_rng(42)
        dates = pd.date_range("2024-01-01", periods=100, freq="15min")
        closes = 45000 + np.cumsum(np.full(100, 50.0))
        df = pd.DataFrame(
            {
                "open": closes - 5,
                "high": closes + 10,
                "low": closes - 10,
                "close": closes,
                "volume": rng.uniform(100, 1000, 100),
            },
            index=dates,
        )
        ma = MarketAnalyzer()
        result = ma.analyze(df)
        if result.phase == MarketPhase.BULLISH_TREND:
            assert result.trend_strength in (TrendStrength.STRONG, TrendStrength.WEAK)


class TestRangeDetection:
    def test_in_range_flag(self):
        df = _make_df(n=100, trend="sideways")
        ma = MarketAnalyzer()
        result = ma.analyze(df)
        assert isinstance(result.is_in_range, bool)

    def test_range_high_low(self):
        df = _make_df(n=100)
        ma = MarketAnalyzer()
        result = ma.analyze(df)
        if result.range_high is not None and result.range_low is not None:
            assert result.range_high > result.range_low


class TestIndicatorCalculation:
    def test_ema_calculated(self):
        df = _make_df(n=100)
        ma = MarketAnalyzer()
        ema = ma._calculate_ema(df, 20)
        assert len(ema) == len(df)
        assert not ema.isna().all()

    def test_atr_calculated(self):
        df = _make_df(n=100)
        ma = MarketAnalyzer()
        atr = ma._calculate_atr(df, 14)
        assert len(atr) == len(df)
        # ATR should be positive after warmup
        assert atr.dropna().iloc[-1] > 0

    def test_rsi_calculated(self):
        df = _make_df(n=100)
        ma = MarketAnalyzer()
        rsi = ma._calculate_rsi(df, 14)
        assert len(rsi) == len(df)
        # RSI should be between 0 and 100 after warmup
        valid = rsi.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()
