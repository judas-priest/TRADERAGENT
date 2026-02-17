"""Tests for CoinClusterizer."""

from decimal import Decimal

import pytest

from grid_backtester.engine.clusterizer import CoinClusterizer
from grid_backtester.engine.models import CoinCluster, CoinProfile
from tests.conftest import make_candles, make_stable_candles, make_meme_candles


class TestCoinClusterizer:

    def test_classify_returns_profile(self):
        clusterizer = CoinClusterizer()
        candles = make_candles(n=50, start_price=45000.0)
        profile = clusterizer.classify("BTCUSDT", candles)

        assert isinstance(profile, CoinProfile)
        assert profile.symbol == "BTCUSDT"
        assert isinstance(profile.cluster, CoinCluster)
        assert profile.atr_pct > 0
        assert profile.volatility_score >= 0

    def test_stable_classification(self):
        clusterizer = CoinClusterizer()
        candles = make_stable_candles(n=50)
        profile = clusterizer.classify("USDCUSDT", candles)

        assert profile.cluster == CoinCluster.STABLE

    def test_meme_classification(self):
        clusterizer = CoinClusterizer()
        # Use higher volatility to ensure MEMES classification (atr_pct >= 5.0)
        candles = make_candles(n=50, start_price=0.1, volatility=0.08, seed=42)
        profile = clusterizer.classify("DOGEUSDT", candles)

        assert profile.cluster == CoinCluster.MEMES

    def test_get_preset(self):
        clusterizer = CoinClusterizer()
        for cluster in CoinCluster:
            preset = clusterizer.get_preset(cluster)
            assert preset.cluster == cluster
            assert len(preset.spacing_options) > 0
            assert preset.levels_range[0] < preset.levels_range[1]

    def test_custom_thresholds(self):
        clusterizer = CoinClusterizer(
            stable_threshold=1.0,
            blue_chips_threshold=3.0,
            memes_threshold=8.0,
        )
        candles = make_candles(n=50)
        profile = clusterizer.classify("BTCUSDT", candles)
        assert isinstance(profile.cluster, CoinCluster)

    def test_insufficient_data_raises(self):
        clusterizer = CoinClusterizer()
        import pandas as pd
        single = pd.DataFrame({
            "open": [100], "high": [101], "low": [99], "close": [100], "volume": [100]
        })
        with pytest.raises(ValueError, match="at least 2 candles"):
            clusterizer.classify("X", single)
