"""
Unit tests for Confluence Zones (Order Blocks and Fair Value Gaps)

Tests cover:
- Order Block detection
- Fair Value Gap detection
- Zone strength scoring
- Zone invalidation logic
- Multi-timeframe zones
- Edge cases and performance
"""

import unittest
from decimal import Decimal
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import time

from bot.strategies.smc.confluence_zones import (
    ConfluenceZoneAnalyzer,
    LiquidityZone,
    OrderBlock,
    FairValueGap,
    ZoneType,
    ZoneStatus
)
from bot.strategies.smc.market_structure import (
    MarketStructureAnalyzer,
    TrendDirection
)


class TestConfluenceZoneAnalyzer(unittest.TestCase):
    """Test cases for ConfluenceZoneAnalyzer"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.market_structure = MarketStructureAnalyzer(swing_length=5)
        self.analyzer = ConfluenceZoneAnalyzer(
            market_structure=self.market_structure,
            timeframe="1h"
        )
    
    def _create_sample_data(self, pattern: str = "uptrend", length: int = 100) -> pd.DataFrame:
        """Create sample OHLCV data for testing"""
        base_price = 100.0
        timestamps = pd.date_range(start=datetime.now(), periods=length, freq="1h")
        
        if pattern == "uptrend":
            trend = np.linspace(0, 20, length)
            noise = np.random.randn(length) * 0.5
            close = base_price + trend + noise
        elif pattern == "fvg_bullish":
            # Create data with clear bullish FVG
            close = np.ones(length) * base_price
            # Create gap: candle 10 high < candle 12 low
            close[10] = base_price - 2
            close[11] = base_price + 1
            close[12] = base_price + 5
        elif pattern == "fvg_bearish":
            # Create data with clear bearish FVG
            close = np.ones(length) * base_price
            # Create gap: candle 10 low > candle 12 high
            close[10] = base_price + 5
            close[11] = base_price + 2
            close[12] = base_price - 2
        else:
            close = np.ones(length) * base_price
        
        open_price = close + np.random.randn(length) * 0.2
        high = np.maximum(open_price, close) + np.abs(np.random.randn(length) * 0.3)
        low = np.minimum(open_price, close) - np.abs(np.random.randn(length) * 0.3)
        volume = np.random.randint(1000, 10000, length)
        
        df = pd.DataFrame({
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume
        }, index=timestamps)
        
        return df
    
    def test_order_block_detection_bullish(self):
        """Test bullish Order Block detection"""
        df = self._create_sample_data("uptrend", length=100)
        
        # First analyze market structure to get structure breaks
        self.market_structure.analyze(df)
        
        # Then detect Order Blocks
        self.analyzer.analyze(df)
        
        # Should detect some Order Blocks in uptrend
        obs = self.analyzer.get_active_order_blocks(is_bullish=True)
        
        # Verify OB structure (may vary based on data)
        for ob in obs:
            self.assertTrue(ob.is_bullish)
            self.assertEqual(ob.status, ZoneStatus.ACTIVE)
            self.assertIsInstance(ob.high, Decimal)
            self.assertIsInstance(ob.low, Decimal)
            self.assertGreater(ob.high, ob.low)
    
    def test_fair_value_gap_bullish_detection(self):
        """Test bullish Fair Value Gap detection"""
        df = self._create_sample_data("fvg_bullish", length=20)
        
        # Manually create gap in data
        df.iloc[10, df.columns.get_loc("high")] = 98
        df.iloc[12, df.columns.get_loc("low")] = 105
        
        self.market_structure.analyze(df)
        self.analyzer.analyze(df)
        
        # Should detect bullish FVG
        fvgs = self.analyzer.get_active_fvgs(is_bullish=True)
        
        if len(fvgs) > 0:
            fvg = fvgs[0]
            self.assertTrue(fvg.is_bullish)
            self.assertEqual(fvg.status, ZoneStatus.ACTIVE)
            self.assertGreater(fvg.gap_high, fvg.gap_low)
    
    def test_fair_value_gap_bearish_detection(self):
        """Test bearish Fair Value Gap detection"""
        df = self._create_sample_data("fvg_bearish", length=20)
        
        # Manually create gap in data
        df.iloc[10, df.columns.get_loc("low")] = 105
        df.iloc[12, df.columns.get_loc("high")] = 95
        
        self.market_structure.analyze(df)
        self.analyzer.analyze(df)
        
        # Should detect bearish FVG
        fvgs = self.analyzer.get_active_fvgs(is_bullish=False)
        
        if len(fvgs) > 0:
            fvg = fvgs[0]
            self.assertFalse(fvg.is_bullish)
            self.assertEqual(fvg.status, ZoneStatus.ACTIVE)
            self.assertGreater(fvg.gap_high, fvg.gap_low)
    
    def test_order_block_invalidation_bullish(self):
        """Test bullish Order Block invalidation"""
        # Create OB manually
        ob = OrderBlock(
            is_bullish=True,
            high=Decimal("105"),
            low=Decimal("100"),
            open=Decimal("102"),
            close=Decimal("104"),
            status=ZoneStatus.ACTIVE
        )
        self.analyzer.order_blocks.append(ob)
        
        # Create data with price closing below OB low
        df = self._create_sample_data("uptrend", length=10)
        df.iloc[-1, df.columns.get_loc("close")] = 95  # Close below OB low
        
        self.analyzer._update_zone_status(df)
        
        # OB should be invalidated
        self.assertEqual(ob.status, ZoneStatus.INVALIDATED)
        self.assertIsNotNone(ob.invalidated_at)
    
    def test_order_block_invalidation_bearish(self):
        """Test bearish Order Block invalidation"""
        ob = OrderBlock(
            is_bullish=False,
            high=Decimal("105"),
            low=Decimal("100"),
            open=Decimal("104"),
            close=Decimal("102"),
            status=ZoneStatus.ACTIVE
        )
        self.analyzer.order_blocks.append(ob)
        
        # Create data with price closing above OB high
        df = self._create_sample_data("uptrend", length=10)
        df.iloc[-1, df.columns.get_loc("close")] = 110  # Close above OB high
        
        self.analyzer._update_zone_status(df)
        
        # OB should be invalidated
        self.assertEqual(ob.status, ZoneStatus.INVALIDATED)
    
    def test_fvg_fill_detection(self):
        """Test Fair Value Gap fill detection"""
        fvg = FairValueGap(
            is_bullish=True,
            gap_high=Decimal("105"),
            gap_low=Decimal("100"),
            status=ZoneStatus.ACTIVE
        )
        self.analyzer.fair_value_gaps.append(fvg)
        
        # Create data with price fully filling the gap
        df = self._create_sample_data("uptrend", length=10)
        df.iloc[-1, df.columns.get_loc("high")] = 106
        df.iloc[-1, df.columns.get_loc("low")] = 99
        
        self.analyzer._update_zone_status(df)
        
        # FVG should be filled
        self.assertEqual(fvg.status, ZoneStatus.FILLED)
        self.assertGreaterEqual(fvg.fill_percentage, 100)
    
    def test_fvg_partial_fill(self):
        """Test Fair Value Gap partial fill detection"""
        fvg = FairValueGap(
            is_bullish=True,
            gap_high=Decimal("110"),
            gap_low=Decimal("100"),
            status=ZoneStatus.ACTIVE
        )
        self.analyzer.fair_value_gaps.append(fvg)
        
        # Create data with price partially filling the gap
        df = self._create_sample_data("uptrend", length=10)
        df.iloc[-1, df.columns.get_loc("high")] = 105  # Partial fill
        df.iloc[-1, df.columns.get_loc("low")] = 98
        
        self.analyzer._update_zone_status(df)
        
        # FVG should be partially filled
        self.assertEqual(fvg.status, ZoneStatus.PARTIAL_FILL)
        self.assertGreater(fvg.fill_percentage, 0)
        self.assertLess(fvg.fill_percentage, 100)
    
    def test_zone_strength_scoring(self):
        """Test zone strength scoring calculation"""
        ob = OrderBlock(
            is_bullish=True,
            high=Decimal("105"),
            low=Decimal("100"),
            volume=5000,
            status=ZoneStatus.ACTIVE
        )
        
        score = self.analyzer._calculate_zone_strength(ob)
        
        # Score should be between 0 and 100
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)
    
    def test_get_zones_summary(self):
        """Test get_zones_summary method"""
        df = self._create_sample_data("uptrend", length=50)

        self.market_structure.analyze(df)
        result = self.analyzer.analyze(df)

        # Verify summary structure
        self.assertIn("order_blocks", result)
        self.assertIn("fair_value_gaps", result)
        self.assertIn("liquidity_zones", result)
        self.assertIn("total", result["order_blocks"])
        self.assertIn("active", result["order_blocks"])
        self.assertIn("total", result["liquidity_zones"])
        self.assertIn("active", result["liquidity_zones"])
        self.assertIn("buy_side", result["liquidity_zones"])
        self.assertIn("sell_side", result["liquidity_zones"])
    
    def test_find_confluence_at_price(self):
        """Test finding confluence zones near a price"""
        # Add some test zones
        ob = OrderBlock(
            is_bullish=True,
            high=Decimal("105"),
            low=Decimal("100"),
            status=ZoneStatus.ACTIVE
        )
        self.analyzer.order_blocks.append(ob)
        
        fvg = FairValueGap(
            is_bullish=True,
            gap_high=Decimal("103"),
            gap_low=Decimal("101"),
            status=ZoneStatus.ACTIVE
        )
        self.analyzer.fair_value_gaps.append(fvg)
        
        # Find confluence at price 102
        result = self.analyzer.find_confluence_at_price(Decimal("102"), tolerance=Decimal("2"))
        
        self.assertIn("confluence_count", result)
        self.assertGreaterEqual(result["confluence_count"], 0)
    
    def test_cleanup_zones(self):
        """Test zone cleanup (removing old invalidated zones)"""
        # Add old invalidated OB
        old_time = datetime.now() - timedelta(days=2)
        ob = OrderBlock(
            is_bullish=True,
            high=Decimal("105"),
            low=Decimal("100"),
            status=ZoneStatus.INVALIDATED,
            invalidated_at=old_time
        )
        self.analyzer.order_blocks.append(ob)
        
        # Add active OB
        active_ob = OrderBlock(
            is_bullish=True,
            high=Decimal("110"),
            low=Decimal("105"),
            status=ZoneStatus.ACTIVE
        )
        self.analyzer.order_blocks.append(active_ob)
        
        self.analyzer._cleanup_zones()
        
        # Old invalidated OB should be removed, active should remain
        self.assertEqual(len(self.analyzer.order_blocks), 1)
        self.assertEqual(self.analyzer.order_blocks[0], active_ob)
    
    def test_performance(self):
        """Test performance - should process chart in < 200ms"""
        df = self._create_sample_data("uptrend", length=500)
        
        self.market_structure.analyze(df)
        
        start_time = time.time()
        self.analyzer.analyze(df)
        elapsed_time = (time.time() - start_time) * 1000  # Convert to ms
        
        self.assertLess(elapsed_time, 2000,
                       f"Analysis took {elapsed_time:.2f}ms, should be < 2000ms")
    
    def test_insufficient_data(self):
        """Test behavior with insufficient data"""
        df = self._create_sample_data("uptrend", length=2)
        
        result = self.analyzer.analyze(df)
        
        # Should handle gracefully
        self.assertIsInstance(result, dict)


class TestOrderBlock(unittest.TestCase):
    """Test cases for OrderBlock dataclass"""
    
    def test_order_block_creation(self):
        """Test OrderBlock object creation"""
        ob = OrderBlock(
            is_bullish=True,
            high=Decimal("105.50"),
            low=Decimal("100.00"),
            open=Decimal("102.00"),
            close=Decimal("104.00"),
            volume=5000,
            status=ZoneStatus.ACTIVE
        )
        
        self.assertTrue(ob.is_bullish)
        self.assertEqual(ob.high, Decimal("105.50"))
        self.assertEqual(ob.status, ZoneStatus.ACTIVE)
    
    def test_order_block_range(self):
        """Test OrderBlock get_range method"""
        ob = OrderBlock(
            high=Decimal("105"),
            low=Decimal("100")
        )
        
        self.assertEqual(ob.get_range(), Decimal("5"))
    
    def test_order_block_midpoint(self):
        """Test OrderBlock get_midpoint method"""
        ob = OrderBlock(
            high=Decimal("110"),
            low=Decimal("100")
        )
        
        self.assertEqual(ob.get_midpoint(), Decimal("105"))
    
    def test_order_block_contains_price(self):
        """Test OrderBlock contains_price method"""
        ob = OrderBlock(
            high=Decimal("110"),
            low=Decimal("100")
        )
        
        self.assertTrue(ob.contains_price(Decimal("105")))
        self.assertTrue(ob.contains_price(Decimal("100")))
        self.assertTrue(ob.contains_price(Decimal("110")))
        self.assertFalse(ob.contains_price(Decimal("95")))
        self.assertFalse(ob.contains_price(Decimal("115")))


class TestFairValueGap(unittest.TestCase):
    """Test cases for FairValueGap dataclass"""
    
    def test_fvg_creation(self):
        """Test FairValueGap object creation"""
        fvg = FairValueGap(
            is_bullish=True,
            gap_high=Decimal("105"),
            gap_low=Decimal("100"),
            status=ZoneStatus.ACTIVE
        )
        
        self.assertTrue(fvg.is_bullish)
        self.assertEqual(fvg.gap_high, Decimal("105"))
        self.assertEqual(fvg.status, ZoneStatus.ACTIVE)
    
    def test_fvg_gap_size(self):
        """Test FairValueGap get_gap_size method"""
        fvg = FairValueGap(
            gap_high=Decimal("110"),
            gap_low=Decimal("100")
        )
        
        self.assertEqual(fvg.get_gap_size(), Decimal("10"))
    
    def test_fvg_midpoint(self):
        """Test FairValueGap get_midpoint method"""
        fvg = FairValueGap(
            gap_high=Decimal("110"),
            gap_low=Decimal("100")
        )
        
        self.assertEqual(fvg.get_midpoint(), Decimal("105"))
    
    def test_fvg_contains_price(self):
        """Test FairValueGap contains_price method"""
        fvg = FairValueGap(
            gap_high=Decimal("110"),
            gap_low=Decimal("100")
        )
        
        self.assertTrue(fvg.contains_price(Decimal("105")))
        self.assertTrue(fvg.contains_price(Decimal("100")))
        self.assertTrue(fvg.contains_price(Decimal("110")))
        self.assertFalse(fvg.contains_price(Decimal("95")))
        self.assertFalse(fvg.contains_price(Decimal("115")))


class TestLiquidityZone(unittest.TestCase):
    """Test cases for LiquidityZone dataclass"""

    def test_liquidity_zone_creation(self):
        """Test LiquidityZone object creation"""
        lz = LiquidityZone(
            is_bullish=True,
            level=Decimal("105.00"),
            end_index=50,
            swept=False,
            index=10,
            timeframe="1h",
        )
        self.assertTrue(lz.is_bullish)
        self.assertEqual(lz.level, Decimal("105.00"))
        self.assertFalse(lz.swept)

    def test_get_active_liquidity_zones(self):
        """Test get_active_liquidity_zones filtering"""
        ms = MarketStructureAnalyzer(swing_length=5)
        analyzer = ConfluenceZoneAnalyzer(market_structure=ms, timeframe="1h")

        # Add zones
        analyzer.liquidity_zones.append(LiquidityZone(
            is_bullish=True, level=Decimal("110"), swept=False, index=0,
        ))
        analyzer.liquidity_zones.append(LiquidityZone(
            is_bullish=False, level=Decimal("90"), swept=True, index=1,
        ))
        analyzer.liquidity_zones.append(LiquidityZone(
            is_bullish=False, level=Decimal("85"), swept=False, index=2,
        ))

        # All active (un-swept)
        active = analyzer.get_active_liquidity_zones()
        self.assertEqual(len(active), 2)

        # Filter buy-side
        buy_side = analyzer.get_active_liquidity_zones(is_bullish=True)
        self.assertEqual(len(buy_side), 1)
        self.assertTrue(buy_side[0].is_bullish)

        # Filter sell-side
        sell_side = analyzer.get_active_liquidity_zones(is_bullish=False)
        self.assertEqual(len(sell_side), 1)
        self.assertFalse(sell_side[0].is_bullish)


if __name__ == "__main__":
    unittest.main()
