"""
Tests for CoinClusterizer — volatility-based coin classification.

Tests cover:
- Classification of each cluster type
- Preset retrieval
- ATR%, volume, gap calculations
- Custom thresholds
- Edge cases
"""

import numpy as np
import pandas as pd
import pytest
from grid_backtester.core import GridSpacing
from grid_backtester.engine import (
    ClusterPreset,
    CoinCluster,
    CoinClusterizer,
    CoinProfile,
)

# =============================================================================
# Helpers
# =============================================================================


def make_stable_candles(n: int = 100, center: float = 1.0, noise: float = 0.001) -> pd.DataFrame:
    """Stablecoin-like data — very low volatility (ATR% < 0.5%)."""
    rng = np.random.RandomState(42)
    rows = []
    prev = center
    for _i in range(n):
        change = rng.normal(0, noise)
        close = prev * (1 + change)
        high = close * (1 + abs(rng.normal(0, noise / 2)))
        low = close * (1 - abs(rng.normal(0, noise / 2)))
        rows.append(
            {
                "open": prev,
                "high": max(high, prev, close),
                "low": min(low, prev, close),
                "close": close,
                "volume": rng.uniform(1e6, 5e6),
            }
        )
        prev = close
    return pd.DataFrame(rows)


def make_blue_chip_candles(n: int = 100, center: float = 45000.0) -> pd.DataFrame:
    """BTC/ETH-like data — moderate volatility (ATR% 0.5-2%)."""
    rng = np.random.RandomState(42)
    rows = []
    prev = center
    for _i in range(n):
        change = rng.normal(0, 0.008)  # ~0.8% per candle
        close = prev * (1 + change)
        high = close * (1 + abs(rng.normal(0, 0.004)))
        low = close * (1 - abs(rng.normal(0, 0.004)))
        rows.append(
            {
                "open": prev,
                "high": max(high, prev, close),
                "low": min(low, prev, close),
                "close": close,
                "volume": rng.uniform(100, 1000),
            }
        )
        prev = close
    return pd.DataFrame(rows)


def make_mid_cap_candles(n: int = 100, center: float = 150.0) -> pd.DataFrame:
    """SOL/AVAX-like data — moderate-high volatility (ATR% 2-5%)."""
    rng = np.random.RandomState(42)
    rows = []
    prev = center
    for _i in range(n):
        change = rng.normal(0, 0.025)  # ~2.5% per candle
        close = prev * (1 + change)
        high = close * (1 + abs(rng.normal(0, 0.012)))
        low = close * (1 - abs(rng.normal(0, 0.012)))
        rows.append(
            {
                "open": prev,
                "high": max(high, prev, close),
                "low": min(low, prev, close),
                "close": close,
                "volume": rng.uniform(50000, 200000),
            }
        )
        prev = close
    return pd.DataFrame(rows)


def make_meme_candles(n: int = 100, center: float = 50.0) -> pd.DataFrame:
    """DOGE/SHIB-like data — high volatility (ATR% > 5%)."""
    rng = np.random.RandomState(42)
    rows = []
    prev = center
    for _i in range(n):
        change = rng.normal(0, 0.07)  # ~7% per candle
        close = max(prev * (1 + change), 1.0)
        high = close * (1 + abs(rng.normal(0, 0.04)))
        low = close * (1 - abs(rng.normal(0, 0.04)))
        rows.append(
            {
                "open": prev,
                "high": max(high, prev, close),
                "low": min(low, prev, close),
                "close": close,
                "volume": rng.uniform(1e8, 5e8),
            }
        )
        prev = close
    return pd.DataFrame(rows)


# =============================================================================
# Tests
# =============================================================================


class TestCoinClusterizer:
    """Test coin classification by volatility."""

    def test_classify_stable(self):
        """Stablecoin data classifies as STABLE."""
        clusterizer = CoinClusterizer()
        candles = make_stable_candles()

        profile = clusterizer.classify("USDTUSDC", candles)

        assert isinstance(profile, CoinProfile)
        assert profile.cluster == CoinCluster.STABLE
        assert profile.atr_pct < 0.5
        assert profile.symbol == "USDTUSDC"

    def test_classify_blue_chips(self):
        """BTC-like data classifies as BLUE_CHIPS."""
        clusterizer = CoinClusterizer()
        candles = make_blue_chip_candles()

        profile = clusterizer.classify("BTCUSDT", candles)

        assert profile.cluster == CoinCluster.BLUE_CHIPS
        assert 0.5 <= profile.atr_pct < 2.0

    def test_classify_mid_caps(self):
        """SOL-like data classifies as MID_CAPS."""
        clusterizer = CoinClusterizer()
        candles = make_mid_cap_candles()

        profile = clusterizer.classify("SOLUSDT", candles)

        assert profile.cluster == CoinCluster.MID_CAPS
        assert 2.0 <= profile.atr_pct < 5.0

    def test_classify_memes(self):
        """DOGE-like data classifies as MEMES."""
        clusterizer = CoinClusterizer()
        candles = make_meme_candles()

        profile = clusterizer.classify("DOGEUSDT", candles)

        assert profile.cluster == CoinCluster.MEMES
        assert profile.atr_pct >= 5.0

    def test_get_preset_for_each_cluster(self):
        """Each cluster has a valid preset with correct spacing options."""
        clusterizer = CoinClusterizer()

        for cluster in CoinCluster:
            preset = clusterizer.get_preset(cluster)
            assert isinstance(preset, ClusterPreset)
            assert preset.cluster == cluster
            assert len(preset.spacing_options) >= 1
            assert preset.levels_range[0] < preset.levels_range[1]
            assert preset.profit_per_grid_range[0] < preset.profit_per_grid_range[1]

    def test_memes_preset_geometric_only(self):
        """MEMES preset only allows geometric spacing."""
        clusterizer = CoinClusterizer()
        preset = clusterizer.get_preset(CoinCluster.MEMES)

        assert preset.spacing_options == [GridSpacing.GEOMETRIC]

    def test_stable_preset_arithmetic_only(self):
        """STABLE preset only allows arithmetic spacing."""
        clusterizer = CoinClusterizer()
        preset = clusterizer.get_preset(CoinCluster.STABLE)

        assert preset.spacing_options == [GridSpacing.ARITHMETIC]

    def test_blue_chips_preset_both_spacings(self):
        """BLUE_CHIPS preset allows both arithmetic and geometric."""
        clusterizer = CoinClusterizer()
        preset = clusterizer.get_preset(CoinCluster.BLUE_CHIPS)

        assert GridSpacing.ARITHMETIC in preset.spacing_options
        assert GridSpacing.GEOMETRIC in preset.spacing_options

    def test_custom_thresholds(self):
        """Custom thresholds change classification."""
        # Make thresholds very tight so blue_chip data becomes mid_caps
        clusterizer = CoinClusterizer(
            stable_threshold=0.1,
            blue_chips_threshold=0.5,
            memes_threshold=3.0,
        )
        candles = make_blue_chip_candles()

        profile = clusterizer.classify("BTCUSDT", candles)

        # With tighter thresholds, blue chip data (ATR% ~1%) should become MID_CAPS
        assert profile.cluster == CoinCluster.MID_CAPS

    def test_volatility_score_range(self):
        """Volatility score is in 0-100 range."""
        clusterizer = CoinClusterizer()

        for make_fn, name in [
            (make_stable_candles, "STABLE"),
            (make_blue_chip_candles, "BTC"),
            (make_mid_cap_candles, "SOL"),
            (make_meme_candles, "DOGE"),
        ]:
            candles = make_fn()
            profile = clusterizer.classify(name, candles)
            assert 0 <= profile.volatility_score <= 100, f"{name}: score={profile.volatility_score}"

    def test_max_gap_calculated(self):
        """Max gap is non-negative and reasonable."""
        clusterizer = CoinClusterizer()
        candles = make_meme_candles()

        profile = clusterizer.classify("DOGEUSDT", candles)

        assert profile.max_gap_pct >= 0
        # Meme coins should have noticeable gaps
        assert profile.max_gap_pct > 0

    def test_insufficient_data_raises(self):
        """Less than 2 candles raises ValueError."""
        clusterizer = CoinClusterizer()
        bad_df = pd.DataFrame(
            {"open": [1], "high": [2], "low": [0.5], "close": [1.5], "volume": [100]}
        )

        with pytest.raises(ValueError, match="at least 2"):
            clusterizer.classify("TEST", bad_df)
