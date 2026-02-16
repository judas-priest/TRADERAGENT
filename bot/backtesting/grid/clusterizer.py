"""
CoinClusterizer — Classify coins by volatility for grid parameter selection.

Uses ATR%, average daily volume, and max gap% to assign coins
to clusters: BLUE_CHIPS, MID_CAPS, MEMES, STABLE.

Each cluster maps to a ClusterPreset with recommended parameter ranges
for grid optimization.
"""

from decimal import Decimal

import pandas as pd

from bot.backtesting.grid.models import (
    CLUSTER_PRESETS,
    CoinCluster,
    CoinProfile,
    ClusterPreset,
)
from bot.strategies.grid.grid_calculator import GridCalculator


class CoinClusterizer:
    """
    Classifies coins by volatility characteristics.

    Usage:
        clusterizer = CoinClusterizer()
        profile = clusterizer.classify("BTCUSDT", candles_df)
        preset = clusterizer.get_preset(profile.cluster)
    """

    # Thresholds for ATR% classification
    STABLE_THRESHOLD = 0.5  # ATR% < 0.5% → STABLE
    BLUE_CHIPS_THRESHOLD = 2.0  # ATR% < 2.0% → BLUE_CHIPS
    MEMES_THRESHOLD = 5.0  # ATR% > 5.0% → MEMES
    # Between 2.0% and 5.0% → MID_CAPS

    def __init__(
        self,
        stable_threshold: float = 0.5,
        blue_chips_threshold: float = 2.0,
        memes_threshold: float = 5.0,
    ) -> None:
        self.stable_threshold = stable_threshold
        self.blue_chips_threshold = blue_chips_threshold
        self.memes_threshold = memes_threshold

    def classify(self, symbol: str, candles: pd.DataFrame) -> CoinProfile:
        """
        Classify a coin based on its OHLCV data.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT").
            candles: DataFrame with columns [open, high, low, close, volume].
                     Needs at least 15 rows for ATR calculation.

        Returns:
            CoinProfile with cluster assignment and volatility metrics.
        """
        if len(candles) < 2:
            raise ValueError("Need at least 2 candles for classification")

        atr_pct = self._calculate_atr_pct(candles)
        avg_daily_volume = self._calculate_avg_volume(candles)
        max_gap_pct = self._calculate_max_gap(candles)
        volatility_score = self._calculate_volatility_score(atr_pct, max_gap_pct)

        cluster = self._assign_cluster(atr_pct)

        return CoinProfile(
            symbol=symbol,
            cluster=cluster,
            atr_pct=atr_pct,
            avg_daily_volume=avg_daily_volume,
            max_gap_pct=max_gap_pct,
            volatility_score=volatility_score,
        )

    def get_preset(self, cluster: CoinCluster) -> ClusterPreset:
        """
        Get recommended parameter ranges for a cluster.

        Args:
            cluster: Coin cluster type.

        Returns:
            ClusterPreset with parameter ranges.
        """
        return CLUSTER_PRESETS[cluster]

    # =========================================================================
    # Private Methods
    # =========================================================================

    def _calculate_atr_pct(self, candles: pd.DataFrame) -> float:
        """Calculate ATR as percentage of average close price."""
        highs = [Decimal(str(x)) for x in candles["high"]]
        lows = [Decimal(str(x)) for x in candles["low"]]
        closes = [Decimal(str(x)) for x in candles["close"]]

        period = min(14, len(candles) - 1)
        atr = GridCalculator.calculate_atr(highs, lows, closes, period)

        avg_price = sum(closes) / len(closes)
        if avg_price == 0:
            return 0.0

        return float(atr / avg_price) * 100

    def _calculate_avg_volume(self, candles: pd.DataFrame) -> float:
        """Calculate average daily volume in quote currency."""
        if "volume" not in candles.columns:
            return 0.0

        volumes = candles["volume"].astype(float)
        avg_volume = volumes.mean()

        # Estimate quote volume using close price
        if "close" in candles.columns:
            avg_price = candles["close"].astype(float).mean()
            return avg_volume * avg_price

        return avg_volume

    def _calculate_max_gap(self, candles: pd.DataFrame) -> float:
        """Calculate maximum single-candle gap as percentage."""
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
        """Composite volatility score 0-100."""
        # Weighted combination: 70% ATR, 30% max gap
        atr_score = min(atr_pct * 10, 100)  # 10% ATR = score 100
        gap_score = min(max_gap_pct * 5, 100)  # 20% gap = score 100
        return round(atr_score * 0.7 + gap_score * 0.3, 2)

    def _assign_cluster(self, atr_pct: float) -> CoinCluster:
        """Assign cluster based on ATR%."""
        if atr_pct < self.stable_threshold:
            return CoinCluster.STABLE
        elif atr_pct < self.blue_chips_threshold:
            return CoinCluster.BLUE_CHIPS
        elif atr_pct >= self.memes_threshold:
            return CoinCluster.MEMES
        else:
            return CoinCluster.MID_CAPS
