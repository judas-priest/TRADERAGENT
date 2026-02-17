"""
CoinClusterizer — Classify coins by volatility for grid parameter selection.

Uses ATR%, average daily volume, and max gap% to assign coins
to clusters: BLUE_CHIPS, MID_CAPS, MEMES, STABLE.
"""

from decimal import Decimal

import pandas as pd

from grid_backtester.engine.models import (
    CLUSTER_PRESETS,
    CoinCluster,
    CoinProfile,
    ClusterPreset,
)
from grid_backtester.core.calculator import GridCalculator
from grid_backtester.caching.indicator_cache import IndicatorCache
from grid_backtester.logging import get_logger

logger = get_logger(__name__)


class CoinClusterizer:
    """Classifies coins by volatility characteristics."""

    STABLE_THRESHOLD = 0.5
    BLUE_CHIPS_THRESHOLD = 2.0
    MEMES_THRESHOLD = 5.0

    def __init__(
        self,
        stable_threshold: float = 0.5,
        blue_chips_threshold: float = 2.0,
        memes_threshold: float = 5.0,
        indicator_cache: IndicatorCache | None = None,
    ) -> None:
        self.stable_threshold = stable_threshold
        self.blue_chips_threshold = blue_chips_threshold
        self.memes_threshold = memes_threshold
        self.indicator_cache = indicator_cache

    def classify(self, symbol: str, candles: pd.DataFrame) -> CoinProfile:
        """Classify a coin based on its OHLCV data."""
        if len(candles) < 2:
            raise ValueError("Need at least 2 candles for classification")

        atr_pct = self._calculate_atr_pct(candles)
        avg_daily_volume = self._calculate_avg_volume(candles)
        max_gap_pct = self._calculate_max_gap(candles)
        volatility_score = self._calculate_volatility_score(atr_pct, max_gap_pct)

        cluster = self._assign_cluster(atr_pct)

        logger.info(
            "Coin classified",
            symbol=symbol,
            cluster=cluster.value,
            atr_pct=round(atr_pct, 4),
            volatility_score=volatility_score,
        )

        return CoinProfile(
            symbol=symbol,
            cluster=cluster,
            atr_pct=atr_pct,
            avg_daily_volume=avg_daily_volume,
            max_gap_pct=max_gap_pct,
            volatility_score=volatility_score,
        )

    def get_preset(self, cluster: CoinCluster) -> ClusterPreset:
        """Get recommended parameter ranges for a cluster."""
        return CLUSTER_PRESETS[cluster]

    def _calculate_atr_pct(self, candles: pd.DataFrame) -> float:
        highs = candles["high"].astype(float).values
        lows = candles["low"].astype(float).values
        closes = candles["close"].astype(float).values

        period = min(14, len(candles) - 1)

        def _compute_atr_pct() -> float:
            # Calculate ATR as percentage directly to avoid quantization issues
            # with low-price assets (e.g., meme coins at $0.01)
            true_ranges = []
            for i in range(1, len(highs)):
                high_low = highs[i] - lows[i]
                high_prev_close = abs(highs[i] - closes[i - 1])
                low_prev_close = abs(lows[i] - closes[i - 1])
                tr = max(high_low, high_prev_close, low_prev_close)
                true_ranges.append(tr)

            if not true_ranges:
                return 0.0

            use_count = min(period, len(true_ranges))
            recent_tr = true_ranges[-use_count:]
            atr = sum(recent_tr) / use_count

            avg_price = float(sum(closes) / len(closes))
            if avg_price == 0:
                return 0.0

            return (atr / avg_price) * 100

        if self.indicator_cache is not None:
            data_hash = IndicatorCache.hash_data(closes.tolist())
            cache_key = IndicatorCache.make_key("atr_pct", data_hash, period=period)
            return self.indicator_cache.get_or_compute(cache_key, _compute_atr_pct)

        return _compute_atr_pct()

    def _calculate_avg_volume(self, candles: pd.DataFrame) -> float:
        if "volume" not in candles.columns:
            return 0.0

        volumes = candles["volume"].astype(float)
        avg_volume = volumes.mean()

        if "close" in candles.columns:
            avg_price = candles["close"].astype(float).mean()
            return avg_volume * avg_price

        return avg_volume

    def _calculate_max_gap(self, candles: pd.DataFrame) -> float:
        closes = candles["close"].astype(float).values
        if len(closes) < 2:
            return 0.0

        max_gap = 0.0
        for i in range(1, len(closes)):
            if closes[i - 1] != 0:
                gap = abs(closes[i] - closes[i - 1]) / closes[i - 1] * 100
                max_gap = max(max_gap, gap)

        return max_gap

    def _calculate_volatility_score(self, atr_pct: float, max_gap_pct: float) -> float:
        atr_score = min(atr_pct * 10, 100)
        gap_score = min(max_gap_pct * 5, 100)
        return round(atr_score * 0.7 + gap_score * 0.3, 2)

    def _assign_cluster(self, atr_pct: float) -> CoinCluster:
        if atr_pct < self.stable_threshold:
            return CoinCluster.STABLE
        elif atr_pct < self.blue_chips_threshold:
            return CoinCluster.BLUE_CHIPS
        elif atr_pct >= self.memes_threshold:
            return CoinCluster.MEMES
        else:
            return CoinCluster.MID_CAPS
