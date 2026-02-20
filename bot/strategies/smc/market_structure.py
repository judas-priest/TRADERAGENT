"""
Market Structure Analysis Module

Identifies market structure elements:
- Trend direction (bullish/bearish/ranging)
- Swing highs and swing lows
- Break of Structure (BOS)
- Change of Character (CHoCH)

Uses the smartmoneyconcepts library for swing/BOS/CHoCH detection.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional

import pandas as pd
import smartmoneyconcepts.smc as smc

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

    Based on Smart Money Concepts methodology.
    Uses smartmoneyconcepts library for detection.
    """

    def __init__(self, swing_length: int = 50, trend_period: int = 20, close_break: bool = True):
        """
        Initialize Market Structure Analyzer

        Args:
            swing_length: Number of candles on each side for swing point validation
            trend_period: Lookback period for trend determination
            close_break: If True, require candle close beyond level for BOS/CHoCH
        """
        self.swing_length = swing_length
        self.trend_period = trend_period
        self.close_break = close_break

        self.swing_highs: list[SwingPoint] = []
        self.swing_lows: list[SwingPoint] = []
        self.structure_events: list[StructureEvent] = []
        self.current_trend: TrendDirection = TrendDirection.RANGING
        self._swings_df: Optional[pd.DataFrame] = None

        logger.info(
            "MarketStructureAnalyzer initialized",
            swing_length=swing_length,
            trend_period=trend_period,
            close_break=close_break,
        )

    @staticmethod
    def _prepare_ohlc_df(df: pd.DataFrame) -> pd.DataFrame:
        """Cast DataFrame columns to float for the library."""
        ohlc = df[["open", "high", "low", "close"]].copy()
        for col in ohlc.columns:
            ohlc[col] = ohlc[col].astype(float)
        if "volume" in df.columns:
            ohlc["volume"] = df["volume"].astype(float)
        return ohlc

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
        Detect swing highs and swing lows using smartmoneyconcepts library.

        Args:
            df: DataFrame with OHLCV data
        """
        self.swing_highs.clear()
        self.swing_lows.clear()

        ohlc = self._prepare_ohlc_df(df)
        self._swings_df = smc.swing_highs_lows(ohlc, swing_length=self.swing_length)

        for i in range(len(self._swings_df)):
            row = self._swings_df.iloc[i]
            if pd.isna(row["HighLow"]):
                continue

            is_high = row["HighLow"] == 1.0
            price = Decimal(str(row["Level"]))
            timestamp = (
                df.index[i]
                if hasattr(df.index[i], "timestamp") or isinstance(df.index[i], pd.Timestamp)
                else pd.Timestamp(df.index[i])
            )

            swing = SwingPoint(
                index=i,
                price=price,
                timestamp=timestamp,
                is_high=is_high,
                strength=self.swing_length,
            )

            if is_high:
                self.swing_highs.append(swing)
            else:
                self.swing_lows.append(swing)

        logger.debug(
            "Swing points detected",
            swing_highs=len(self.swing_highs),
            swing_lows=len(self.swing_lows),
        )

    def _detect_structure_breaks(self, df: pd.DataFrame) -> None:
        """
        Detect Break of Structure (BOS) and Change of Character (CHoCH)
        using smartmoneyconcepts library.

        Args:
            df: DataFrame with OHLCV data
        """
        self.structure_events.clear()

        if self._swings_df is None or not self.swing_highs and not self.swing_lows:
            return

        ohlc = self._prepare_ohlc_df(df)
        bos_choch_df = smc.bos_choch(ohlc, self._swings_df, close_break=self.close_break)

        for i in range(len(bos_choch_df)):
            row = bos_choch_df.iloc[i]
            timestamp = (
                df.index[i] if isinstance(df.index[i], pd.Timestamp) else pd.Timestamp(df.index[i])
            )

            # Process BOS events
            if pd.notna(row["BOS"]):
                is_bullish = row["BOS"] == 1.0
                event_type = StructureBreak.BOS
                trend = TrendDirection.BULLISH if is_bullish else TrendDirection.BEARISH
                price = Decimal(str(row["Level"]))

                broken_idx = int(row["BrokenIndex"]) if pd.notna(row["BrokenIndex"]) else i
                previous_swing = self._find_nearest_swing(broken_idx, is_high=is_bullish)

                if previous_swing is None:
                    previous_swing = SwingPoint(
                        index=broken_idx,
                        price=price,
                        timestamp=timestamp,
                        is_high=is_bullish,
                        strength=self.swing_length,
                    )

                event = StructureEvent(
                    event_type=event_type,
                    index=i,
                    price=price,
                    timestamp=timestamp,
                    previous_swing=previous_swing,
                    current_trend=trend,
                )
                self.structure_events.append(event)

            # Process CHoCH events
            if pd.notna(row["CHOCH"]):
                is_bullish = row["CHOCH"] == 1.0
                event_type = StructureBreak.CHOCH
                trend = TrendDirection.BULLISH if is_bullish else TrendDirection.BEARISH
                price = Decimal(str(row["Level"]))

                broken_idx = int(row["BrokenIndex"]) if pd.notna(row["BrokenIndex"]) else i
                previous_swing = self._find_nearest_swing(broken_idx, is_high=is_bullish)

                if previous_swing is None:
                    previous_swing = SwingPoint(
                        index=broken_idx,
                        price=price,
                        timestamp=timestamp,
                        is_high=is_bullish,
                        strength=self.swing_length,
                    )

                event = StructureEvent(
                    event_type=event_type,
                    index=i,
                    price=price,
                    timestamp=timestamp,
                    previous_swing=previous_swing,
                    current_trend=trend,
                )
                self.structure_events.append(event)

                # Update trend on CHoCH
                self.current_trend = trend

        logger.debug(
            "Structure breaks detected",
            bos=[e for e in self.structure_events if e.event_type == StructureBreak.BOS].__len__(),
            choch=[
                e for e in self.structure_events if e.event_type == StructureBreak.CHOCH
            ].__len__(),
        )

    def _find_nearest_swing(self, target_index: int, is_high: bool) -> Optional[SwingPoint]:
        """Find the closest SwingPoint to a given index."""
        swings = self.swing_highs if is_high else self.swing_lows
        if not swings:
            return None

        best = None
        best_dist = float("inf")
        for s in swings:
            dist = abs(s.index - target_index)
            if dist < best_dist:
                best_dist = dist
                best = s
        return best

    def get_swings_df(self) -> Optional[pd.DataFrame]:
        """Return raw swings DataFrame for downstream consumers (OB, liquidity)."""
        return self._swings_df

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
                swing_length=self.swing_length,
                trend_period=self.trend_period,
                close_break=self.close_break,
            )
            d1_analyzer.analyze(df_d1)
            result["d1_trend"] = d1_analyzer.current_trend

        # Analyze H4 trend
        if len(df_h4) >= self.trend_period:
            h4_analyzer = MarketStructureAnalyzer(
                swing_length=self.swing_length,
                trend_period=self.trend_period,
                close_break=self.close_break,
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

    def get_structure_events(self, limit: int = 10) -> list[StructureEvent]:
        """
        Get recent structure events

        Args:
            limit: Maximum number of events to return

        Returns:
            List of recent StructureEvent objects
        """
        return self.structure_events[-limit:] if self.structure_events else []
