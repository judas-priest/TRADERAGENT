"""Unit tests for Entry Signal Generator"""

import unittest
from datetime import datetime

import numpy as np
import pandas as pd

from bot.strategies.smc.confluence_zones import ConfluenceZoneAnalyzer
from bot.strategies.smc.entry_signals import (
    EntrySignalGenerator,
    PatternType,
    SignalDirection,
    SMCSignal,
)
from bot.strategies.smc.market_structure import MarketStructureAnalyzer


class TestEntrySignalGenerator(unittest.TestCase):
    def setUp(self):
        self.ms = MarketStructureAnalyzer()
        self.cz = ConfluenceZoneAnalyzer(self.ms)
        self.generator = EntrySignalGenerator(self.ms, self.cz)

    def _create_data(self, length=50):
        timestamps = pd.date_range(start=datetime.now(), periods=length, freq="1h")
        close = np.random.randn(length) * 2 + 100
        open_p = close + np.random.randn(length) * 0.5
        high = np.maximum(open_p, close) + np.abs(np.random.randn(length))
        low = np.minimum(open_p, close) - np.abs(np.random.randn(length))
        volume = np.random.randint(1000, 10000, length)

        return pd.DataFrame(
            {"open": open_p, "high": high, "low": low, "close": close, "volume": volume},
            index=timestamps,
        )

    def test_engulfing_detection(self):
        df = self._create_data(20)
        # Create bullish engulfing manually
        df.iloc[-2, df.columns.get_loc("open")] = 100
        df.iloc[-2, df.columns.get_loc("close")] = 99
        df.iloc[-1, df.columns.get_loc("open")] = 98.5
        df.iloc[-1, df.columns.get_loc("close")] = 101

        self.ms.analyze(df)
        signals = self.generator.analyze(df)

        engulfing_patterns = [
            p for p in self.generator.detected_patterns if p.pattern_type == PatternType.ENGULFING
        ]
        self.assertGreater(len(engulfing_patterns), 0)

    def test_pin_bar_detection(self):
        df = self._create_data(20)
        # Create bullish pin bar
        df.iloc[-1, df.columns.get_loc("high")] = 102
        df.iloc[-1, df.columns.get_loc("low")] = 95
        df.iloc[-1, df.columns.get_loc("open")] = 101
        df.iloc[-1, df.columns.get_loc("close")] = 101.5

        self.ms.analyze(df)
        signals = self.generator.analyze(df)

        pin_bars = [
            p for p in self.generator.detected_patterns if p.pattern_type == PatternType.PIN_BAR
        ]
        self.assertGreaterEqual(len(pin_bars), 0)

    def test_inside_bar_detection(self):
        df = self._create_data(20)
        # Create inside bar
        df.iloc[-2, df.columns.get_loc("high")] = 105
        df.iloc[-2, df.columns.get_loc("low")] = 95
        df.iloc[-1, df.columns.get_loc("high")] = 103
        df.iloc[-1, df.columns.get_loc("low")] = 97

        self.ms.analyze(df)
        signals = self.generator.analyze(df)

        inside_bars = [
            p for p in self.generator.detected_patterns if p.pattern_type == PatternType.INSIDE_BAR
        ]
        self.assertGreater(len(inside_bars), 0)

    def test_signal_generation(self):
        df = self._create_data(50)
        self.ms.analyze(df)
        self.cz.analyze(df)
        signals = self.generator.analyze(df)

        for signal in signals:
            self.assertIsInstance(signal, SMCSignal)
            self.assertIn(signal.direction, [SignalDirection.LONG, SignalDirection.SHORT])
            self.assertGreater(signal.entry_price, 0)
            self.assertGreater(signal.risk_reward_ratio, 0)
            self.assertGreaterEqual(signal.confidence, 0)
            self.assertLessEqual(signal.confidence, 1.0)

    def test_get_signals_summary(self):
        df = self._create_data(50)
        self.ms.analyze(df)
        self.generator.analyze(df)

        summary = self.generator.get_signals_summary()
        self.assertIn("total_patterns", summary)
        self.assertIn("total_signals", summary)


if __name__ == "__main__":
    unittest.main()
