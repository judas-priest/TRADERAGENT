"""Integration tests for complete SMC Strategy"""

import unittest
from decimal import Decimal
from datetime import datetime
import pandas as pd
import numpy as np

from bot.strategies.smc import SMCStrategy, SMCConfig


class TestSMCIntegration(unittest.TestCase):
    def setUp(self):
        self.strategy = SMCStrategy(account_balance=Decimal("10000"))
    
    def _create_sample_data(self, length=100, timeframe="1h"):
        timestamps = pd.date_range(start=datetime.now(), periods=length, freq=timeframe)
        
        # Create uptrend with some noise
        trend = np.linspace(0, 20, length)
        noise = np.random.randn(length) * 2
        close = 100 + trend + noise
        
        open_p = close + np.random.randn(length) * 0.5
        high = np.maximum(open_p, close) + np.abs(np.random.randn(length))
        low = np.minimum(open_p, close) - np.abs(np.random.randn(length))
        volume = np.random.randint(1000, 10000, length)
        
        return pd.DataFrame({
            "open": open_p,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume
        }, index=timestamps)
    
    def test_full_pipeline(self):
        """Test complete signal generation pipeline"""
        # Create multi-timeframe data
        df_d1 = self._create_sample_data(50, "1d")
        df_h4 = self._create_sample_data(100, "4h")
        df_h1 = self._create_sample_data(200, "1h")
        df_m15 = self._create_sample_data(500, "15min")
        
        # Analyze market
        analysis = self.strategy.analyze_market(df_d1, df_h4, df_h1, df_m15)
        
        self.assertIn("market_structure", analysis)
        self.assertIn("trend_analysis", analysis)
        self.assertIn("confluence_zones", analysis)
        
        # Generate signals
        signals = self.strategy.generate_signals(df_h1, df_m15)
        
        # Signals may or may not be generated depending on patterns
        self.assertIsInstance(signals, list)
        
        for signal in signals:
            self.assertGreater(signal.confidence, 0)
            self.assertLess(signal.confidence, 1.1)
            self.assertGreater(signal.risk_reward_ratio, 0)
    
    def test_strategy_state(self):
        """Test get_strategy_state returns complete info"""
        df_d1 = self._create_sample_data(50, "1d")
        df_h4 = self._create_sample_data(100, "4h")
        df_h1 = self._create_sample_data(200, "1h")
        df_m15 = self._create_sample_data(500, "15min")
        
        self.strategy.analyze_market(df_d1, df_h4, df_h1, df_m15)
        
        state = self.strategy.get_strategy_state()
        
        self.assertIn("strategy", state)
        self.assertIn("current_trend", state)
        self.assertIn("position_summary", state)
        self.assertIn("signal_summary", state)
    
    def test_performance_report(self):
        """Test performance report generation"""
        report = self.strategy.get_performance_report()
        
        self.assertIn("total_trades", report)
        self.assertIn("win_rate", report)
        self.assertIn("profit_factor", report)
        self.assertIn("account_balance", report)
    
    def test_strategy_reset(self):
        """Test strategy reset functionality"""
        # Generate some state
        df = self._create_sample_data(100)
        self.strategy.market_structure.analyze(df)
        
        # Reset
        self.strategy.reset()
        
        # Check state cleared
        self.assertEqual(len(self.strategy.active_signals), 0)
        self.assertEqual(len(self.strategy.market_structure.swing_highs), 0)


if __name__ == "__main__":
    unittest.main()
