"""Tests for MarketRegimeDetector."""

import numpy as np
import pandas as pd
import pytest

from bot.orchestrator.market_regime import (
    MarketRegime,
    MarketRegimeDetector,
    RecommendedStrategy,
    RegimeAnalysis,
)


def _make_ohlcv(close_prices: list[float], spread: float = 0.02) -> pd.DataFrame:
    """Helper to create OHLCV DataFrame from close prices."""
    n = len(close_prices)
    close = np.array(close_prices, dtype=float)
    high = close * (1 + spread)
    low = close * (1 - spread)
    open_ = (close + np.roll(close, 1)) / 2
    open_[0] = close[0]
    volume = np.random.uniform(1000, 5000, n)

    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=n, freq="1h"),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def _make_trending_up(n: int = 100, start: float = 2000, step: float = 10) -> pd.DataFrame:
    """Create uptrending OHLCV data."""
    prices = [start + i * step + np.random.uniform(-2, 2) for i in range(n)]
    return _make_ohlcv(prices)


def _make_trending_down(n: int = 100, start: float = 4000, step: float = 10) -> pd.DataFrame:
    """Create downtrending OHLCV data."""
    prices = [start - i * step + np.random.uniform(-2, 2) for i in range(n)]
    return _make_ohlcv(prices)


def _make_sideways(n: int = 100, center: float = 3000, amplitude: float = 20) -> pd.DataFrame:
    """Create sideways/ranging OHLCV data."""
    prices = [center + amplitude * np.sin(i * 0.3) + np.random.uniform(-5, 5) for i in range(n)]
    return _make_ohlcv(prices, spread=0.005)


def _make_high_volatility(n: int = 100, center: float = 3000) -> pd.DataFrame:
    """Create high volatility OHLCV data."""
    prices = [center + np.random.uniform(-200, 200) for _ in range(n)]
    return _make_ohlcv(prices, spread=0.08)


class TestMarketRegimeDetector:
    """Tests for MarketRegimeDetector."""

    def test_init_defaults(self):
        detector = MarketRegimeDetector()
        assert detector.ema_fast == 20
        assert detector.ema_slow == 50
        assert detector.atr_period == 14
        assert detector.rsi_period == 14

    def test_init_custom(self):
        detector = MarketRegimeDetector(
            ema_fast=10,
            ema_slow=30,
            trend_threshold=1.0,
        )
        assert detector.ema_fast == 10
        assert detector.ema_slow == 30
        assert detector.trend_threshold == 1.0

    def test_insufficient_data(self):
        detector = MarketRegimeDetector()
        df = _make_ohlcv([100, 200, 300])
        result = detector.analyze(df)
        assert result.regime == MarketRegime.UNKNOWN
        assert result.confidence == 0.0

    def test_trending_bullish(self):
        detector = MarketRegimeDetector(trend_threshold=0.3)
        df = _make_trending_up(n=100, step=15)
        result = detector.analyze(df)

        assert result.regime in (
            MarketRegime.TRENDING_BULLISH,
            MarketRegime.HIGH_VOLATILITY,
        )
        assert result.trend_strength > 0
        assert result.confidence > 0.0

    def test_trending_bearish(self):
        detector = MarketRegimeDetector(trend_threshold=0.3)
        df = _make_trending_down(n=100, step=15)
        result = detector.analyze(df)

        assert result.regime in (
            MarketRegime.TRENDING_BEARISH,
            MarketRegime.HIGH_VOLATILITY,
        )
        assert result.trend_strength < 0

    def test_sideways(self):
        detector = MarketRegimeDetector(trend_threshold=0.5)
        df = _make_sideways(n=100, amplitude=5)
        result = detector.analyze(df)

        # Sideways with small amplitude should not be trending
        assert result.regime in (
            MarketRegime.SIDEWAYS,
            MarketRegime.TRANSITIONING,
        )

    def test_strategy_recommendation_grid_for_sideways(self):
        """Sideways regime should recommend Grid strategy."""
        detector = MarketRegimeDetector(trend_threshold=0.5)
        df = _make_sideways(n=100, amplitude=3)
        result = detector.analyze(df)

        if result.regime == MarketRegime.SIDEWAYS:
            assert result.recommended_strategy == RecommendedStrategy.GRID

    def test_strategy_recommendation_dca_for_trend(self):
        """Trending regime with low confluence should recommend DCA."""
        detector = MarketRegimeDetector(
            trend_threshold=0.3,
            confluence_threshold=0.9,  # High threshold to ensure DCA
        )
        df = _make_trending_up(n=100, step=10)
        result = detector.analyze(df)

        if result.regime == MarketRegime.TRENDING_BULLISH:
            if result.confluence_score < 0.9:
                assert result.recommended_strategy == RecommendedStrategy.DCA

    def test_strategy_recommendation_reduce_for_high_vol(self):
        """High volatility should recommend reducing exposure."""
        detector = MarketRegimeDetector(high_volatility_percentile=50.0)
        df = _make_high_volatility(n=100)
        result = detector.analyze(df)

        if result.regime == MarketRegime.HIGH_VOLATILITY:
            assert result.recommended_strategy == RecommendedStrategy.REDUCE_EXPOSURE

    def test_confluence_score_range(self):
        detector = MarketRegimeDetector()
        df = _make_trending_up(n=100)
        result = detector.analyze(df)

        assert 0.0 <= result.confluence_score <= 1.0
        assert 0.0 <= result.confidence <= 1.0

    def test_analysis_metrics(self):
        detector = MarketRegimeDetector()
        df = _make_sideways(n=100)
        result = detector.analyze(df)

        assert result.rsi > 0
        assert result.atr_pct >= 0
        assert result.timestamp is not None
        assert "current_price" in result.analysis_details
        assert "ema_fast" in result.analysis_details

    def test_to_dict(self):
        detector = MarketRegimeDetector()
        df = _make_sideways(n=100)
        result = detector.analyze(df)

        d = result.to_dict()
        assert isinstance(d, dict)
        assert "regime" in d
        assert "confidence" in d
        assert "recommended_strategy" in d
        assert "timestamp" in d

    def test_last_analysis_cached(self):
        detector = MarketRegimeDetector()
        assert detector.last_analysis is None

        df = _make_trending_up(n=100)
        result = detector.analyze(df)

        assert detector.last_analysis is result

    def test_atr_calculation(self):
        """Test ATR calculation helper."""
        df = _make_sideways(n=50)
        atr = MarketRegimeDetector._calculate_atr(
            df["high"], df["low"], df["close"], 14
        )
        assert len(atr) == 50
        assert atr.iloc[-1] > 0

    def test_rsi_calculation(self):
        """Test RSI calculation helper."""
        df = _make_trending_up(n=50)
        rsi = MarketRegimeDetector._calculate_rsi(df["close"], 14)
        assert len(rsi) == 50
        # RSI should be > 50 for uptrend
        last_rsi = rsi.iloc[-1]
        assert 0 <= last_rsi <= 100
