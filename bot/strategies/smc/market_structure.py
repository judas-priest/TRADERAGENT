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

from bot.utils.logger import get_logger

logger = get_logger(__name__)


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
        self.current_trend: TrendDirection = TrendDirection.RANGING

        logger.info(
            "MarketStructureAnalyzer initialized",
            swing_length=swing_length,
            trend_period=trend_period,
        )

    def analyze(self, df: pd.DataFrame) -> dict:
        """
        Analyze market structure on given dataframe

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Dictionary with structure analysis results
        """
        if len(df) < self.swing_length * 2 + 1:
            logger.warning(
                "Insufficient data for structure analysis",
                required=self.swing_length * 2 + 1,
                available=len(df),
            )
            return self.get_current_structure()

        # Detect swing points
        self._detect_swing_points(df)

        # Determine current trend
        self._determine_trend(df)

        # Detect structure breaks
        self._detect_structure_breaks(df)

        logger.debug(
            "Market structure analyzed",
            swing_highs=len(self.swing_highs),
            swing_lows=len(self.swing_lows),
            trend=self.current_trend,
            events=len(self.structure_events),
        )

        return self.get_current_structure()

    def _detect_swing_points(self, df: pd.DataFrame) -> None:
        """
        Detect swing highs and swing lows in price data

        A swing high is a candle high that is higher than N candles before and after it.
        A swing low is a candle low that is lower than N candles before and after it.

        Args:
            df: DataFrame with OHLCV data
        """
        self.swing_highs.clear()
        self.swing_lows.clear()

        # Need at least swing_length candles on each side plus the middle candle
        for i in range(self.swing_length, len(df) - self.swing_length):
            # Check for swing high
            if self._is_swing_high(df, i):
                swing_high = SwingPoint(
                    index=i,
                    price=Decimal(str(df.iloc[i]["high"])),
                    timestamp=df.iloc[i].name,
                    is_high=True,
                    strength=self.swing_length,
                )
                self.swing_highs.append(swing_high)

            # Check for swing low
            if self._is_swing_low(df, i):
                swing_low = SwingPoint(
                    index=i,
                    price=Decimal(str(df.iloc[i]["low"])),
                    timestamp=df.iloc[i].name,
                    is_high=False,
                    strength=self.swing_length,
                )
                self.swing_lows.append(swing_low)

        logger.debug(
            "Swing points detected",
            swing_highs=len(self.swing_highs),
            swing_lows=len(self.swing_lows),
        )

    def _is_swing_high(self, df: pd.DataFrame, index: int) -> bool:
        """
        Check if the candle at given index is a swing high

        Args:
            df: DataFrame with OHLCV data
            index: Index to check

        Returns:
            True if it's a swing high, False otherwise
        """
        current_high = df.iloc[index]["high"]

        # Check left side
        for i in range(index - self.swing_length, index):
            if df.iloc[i]["high"] >= current_high:
                return False

        # Check right side
        for i in range(index + 1, index + self.swing_length + 1):
            if df.iloc[i]["high"] >= current_high:
                return False

        return True

    def _is_swing_low(self, df: pd.DataFrame, index: int) -> bool:
        """
        Check if the candle at given index is a swing low

        Args:
            df: DataFrame with OHLCV data
            index: Index to check

        Returns:
            True if it's a swing low, False otherwise
        """
        current_low = df.iloc[index]["low"]

        # Check left side
        for i in range(index - self.swing_length, index):
            if df.iloc[i]["low"] <= current_low:
                return False

        # Check right side
        for i in range(index + 1, index + self.swing_length + 1):
            if df.iloc[i]["low"] <= current_low:
                return False

        return True

    def _determine_trend(self, df: pd.DataFrame) -> None:
        """
        Determine current market trend based on swing points

        Bullish: Higher highs and higher lows
        Bearish: Lower highs and lower lows
        Ranging: Mixed or unclear pattern

        Args:
            df: DataFrame with OHLCV data
        """
        if len(self.swing_highs) < 2 or len(self.swing_lows) < 2:
            self.current_trend = TrendDirection.RANGING
            return

        # Get last two swing highs and lows
        last_high = self.swing_highs[-1]
        prev_high = self.swing_highs[-2]
        last_low = self.swing_lows[-1]
        prev_low = self.swing_lows[-2]

        # Check for bullish trend (higher highs and higher lows)
        higher_highs = last_high.price > prev_high.price
        higher_lows = last_low.price > prev_low.price

        # Check for bearish trend (lower highs and lower lows)
        lower_highs = last_high.price < prev_high.price
        lower_lows = last_low.price < prev_low.price

        if higher_highs and higher_lows:
            self.current_trend = TrendDirection.BULLISH
        elif lower_highs and lower_lows:
            self.current_trend = TrendDirection.BEARISH
        else:
            self.current_trend = TrendDirection.RANGING

        logger.debug("Trend determined", trend=self.current_trend)

    def _detect_structure_breaks(self, df: pd.DataFrame) -> None:
        """
        Detect Break of Structure (BOS) and Change of Character (CHoCH)

        BOS: Price breaks previous swing in direction of trend (continuation)
        CHoCH: Price breaks previous swing against trend (potential reversal)

        Args:
            df: DataFrame with OHLCV data
        """
        self.structure_events.clear()

        if not self.swing_highs or not self.swing_lows:
            return

        # Check for breaks of swing highs (bullish breaks)
        for i in range(len(df)):
            close_price = Decimal(str(df.iloc[i]["close"]))

            # Check if price breaks above recent swing high
            for swing_high in reversed(self.swing_highs):
                if swing_high.index >= i:
                    continue

                if close_price > swing_high.price:
                    # Determine if this is BOS or CHoCH
                    if self.current_trend == TrendDirection.BULLISH:
                        event_type = StructureBreak.BOS
                    elif self.current_trend == TrendDirection.BEARISH:
                        event_type = StructureBreak.CHOCH
                        # Update trend on CHoCH
                        self.current_trend = TrendDirection.BULLISH
                    else:
                        event_type = StructureBreak.BOS

                    event = StructureEvent(
                        event_type=event_type,
                        index=i,
                        price=close_price,
                        timestamp=df.iloc[i].name,
                        previous_swing=swing_high,
                        current_trend=self.current_trend,
                    )
                    self.structure_events.append(event)

                    logger.debug(
                        "Structure break detected",
                        type=event_type,
                        price=float(close_price),
                        swing_price=float(swing_high.price),
                    )
                    break

            # Check if price breaks below recent swing low
            for swing_low in reversed(self.swing_lows):
                if swing_low.index >= i:
                    continue

                if close_price < swing_low.price:
                    # Determine if this is BOS or CHoCH
                    if self.current_trend == TrendDirection.BEARISH:
                        event_type = StructureBreak.BOS
                    elif self.current_trend == TrendDirection.BULLISH:
                        event_type = StructureBreak.CHOCH
                        # Update trend on CHoCH
                        self.current_trend = TrendDirection.BEARISH
                    else:
                        event_type = StructureBreak.BOS

                    event = StructureEvent(
                        event_type=event_type,
                        index=i,
                        price=close_price,
                        timestamp=df.iloc[i].name,
                        previous_swing=swing_low,
                        current_trend=self.current_trend,
                    )
                    self.structure_events.append(event)

                    logger.debug(
                        "Structure break detected",
                        type=event_type,
                        price=float(close_price),
                        swing_price=float(swing_low.price),
                    )
                    break

    def analyze_trend(self, df_d1: pd.DataFrame, df_h4: pd.DataFrame) -> dict:
        """
        Analyze trend across multiple timeframes

        Args:
            df_d1: Daily timeframe data for global trend
            df_h4: 4-hour timeframe data for market structure

        Returns:
            Dictionary with multi-timeframe trend analysis
        """
        result = {
            "d1_trend": TrendDirection.RANGING,
            "h4_trend": TrendDirection.RANGING,
            "trend_strength": 0.0,
            "trend_aligned": False,
        }

        # Analyze D1 trend
        if len(df_d1) >= self.trend_period:
            d1_analyzer = MarketStructureAnalyzer(
                swing_length=self.swing_length, trend_period=self.trend_period
            )
            d1_analyzer.analyze(df_d1)
            result["d1_trend"] = d1_analyzer.current_trend

        # Analyze H4 trend
        if len(df_h4) >= self.trend_period:
            h4_analyzer = MarketStructureAnalyzer(
                swing_length=self.swing_length, trend_period=self.trend_period
            )
            h4_analyzer.analyze(df_h4)
            result["h4_trend"] = h4_analyzer.current_trend

        # Check if trends are aligned
        result["trend_aligned"] = (
            result["d1_trend"] == result["h4_trend"]
            and result["d1_trend"] != TrendDirection.RANGING
        )

        # Calculate trend strength (0.0 to 1.0)
        if result["trend_aligned"]:
            result["trend_strength"] = 1.0
        elif (
            result["d1_trend"] != TrendDirection.RANGING
            or result["h4_trend"] != TrendDirection.RANGING
        ):
            result["trend_strength"] = 0.5
        else:
            result["trend_strength"] = 0.0

        logger.info(
            "Multi-timeframe trend analyzed",
            d1_trend=result["d1_trend"],
            h4_trend=result["h4_trend"],
            strength=result["trend_strength"],
            aligned=result["trend_aligned"],
        )

        return result

    def get_current_structure(self) -> dict:
        """Get current market structure summary"""
        return {
            "swing_highs_count": len(self.swing_highs),
            "swing_lows_count": len(self.swing_lows),
            "last_swing_high": self.swing_highs[-1] if self.swing_highs else None,
            "last_swing_low": self.swing_lows[-1] if self.swing_lows else None,
            "current_trend": self.current_trend,
            "structure_events_count": len(self.structure_events),
            "last_structure_event": self.structure_events[-1] if self.structure_events else None,
        }

    def get_recent_swing_high(self) -> Optional[SwingPoint]:
        """Get most recent swing high"""
        return self.swing_highs[-1] if self.swing_highs else None

    def get_recent_swing_low(self) -> Optional[SwingPoint]:
        """Get most recent swing low"""
        return self.swing_lows[-1] if self.swing_lows else None

    def get_structure_events(self, limit: int = 10) -> List[StructureEvent]:
        """
        Get recent structure events

        Args:
            limit: Maximum number of events to return

        Returns:
            List of recent StructureEvent objects
        """
        return self.structure_events[-limit:] if self.structure_events else []
