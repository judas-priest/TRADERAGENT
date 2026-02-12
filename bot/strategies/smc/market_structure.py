"""
Market Structure Analysis Module

Identifies market structure elements:
- Trend direction (bullish/bearish/ranging)
- Swing highs and swing lows
- Break of Structure (BOS)
- Change of Character (CHoCH)
"""

from decimal import Decimal
from enum import Enum
from typing import List, Optional, Tuple
from dataclasses import dataclass

import pandas as pd
import numpy as np


class TrendDirection(str, Enum):
    """Market trend direction"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    RANGING = "ranging"


class StructureBreak(str, Enum):
    """Type of market structure break"""
    BOS = "break_of_structure"  # Continuation
    CHOCH = "change_of_character"  # Reversal


@dataclass
class SwingPoint:
    """Represents a swing high or swing low"""
    index: int
    price: Decimal
    timestamp: pd.Timestamp
    is_high: bool  # True for swing high, False for swing low
    strength: int  # Number of candles on each side


@dataclass
class StructureEvent:
    """Market structure event (BOS or CHoCH)"""
    event_type: StructureBreak
    index: int
    price: Decimal
    timestamp: pd.Timestamp
    previous_swing: SwingPoint
    current_trend: TrendDirection


class MarketStructureAnalyzer:
    """
    Analyzes market structure using swing points and structure breaks

    Based on Smart Money Concepts methodology
    """

    def __init__(self, swing_length: int = 5, trend_period: int = 20):
        """
        Initialize Market Structure Analyzer

        Args:
            swing_length: Number of candles on each side for swing point validation
            trend_period: Lookback period for trend determination
        """
        self.swing_length = swing_length
        self.trend_period = trend_period

        self.swing_highs: List[SwingPoint] = []
        self.swing_lows: List[SwingPoint] = []
        self.structure_events: List[StructureEvent] = []

    def get_current_structure(self) -> dict:
        """Get current market structure summary"""
        return {
            'swing_highs_count': len(self.swing_highs),
            'swing_lows_count': len(self.swing_lows),
            'last_swing_high': self.swing_highs[-1] if self.swing_highs else None,
            'last_swing_low': self.swing_lows[-1] if self.swing_lows else None,
        }
