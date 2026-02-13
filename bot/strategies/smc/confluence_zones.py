"""
Confluence Zones Module

Detects and manages institutional order zones:
- Order Blocks (OB): Last opposite candle before structure break
- Fair Value Gaps (FVG): 3-candle imbalance patterns
- Zone strength scoring
- Zone invalidation tracking
"""

from decimal import Decimal
from enum import Enum
from typing import List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd
import numpy as np

from bot.utils.logger import get_logger
from bot.strategies.smc.market_structure import (
    MarketStructureAnalyzer,
    StructureEvent,
    StructureBreak,
    TrendDirection,
)

logger = get_logger(__name__)


class ZoneType(str, Enum):
    """Type of confluence zone"""

    ORDER_BLOCK = "order_block"
    FAIR_VALUE_GAP = "fair_value_gap"


class ZoneStatus(str, Enum):
    """Status of a zone"""

    ACTIVE = "active"
    INVALIDATED = "invalidated"
    FILLED = "filled"
    PARTIAL_FILL = "partial_fill"


@dataclass
class OrderBlock:
    """
    Represents an Order Block zone

    Order Block: The last opposite candle before a structure break,
    representing where institutions placed their orders
    """

    zone_type: ZoneType = field(default=ZoneType.ORDER_BLOCK)
    is_bullish: bool = False

    # Price levels
    high: Decimal = Decimal("0")
    low: Decimal = Decimal("0")
    open: Decimal = Decimal("0")
    close: Decimal = Decimal("0")

    # Metadata
    index: int = 0
    timestamp: pd.Timestamp = None
    timeframe: str = ""
    volume: float = 0.0

    # Structure info
    structure_break: Optional[StructureEvent] = None

    # Status tracking
    status: ZoneStatus = ZoneStatus.ACTIVE
    strength_score: float = 0.0
    touch_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    invalidated_at: Optional[datetime] = None

    def get_range(self) -> Decimal:
        """Get the price range of the Order Block"""
        return self.high - self.low

    def get_midpoint(self) -> Decimal:
        """Get the midpoint price of the Order Block"""
        return (self.high + self.low) / Decimal("2")

    def contains_price(self, price: Decimal) -> bool:
        """Check if a price is within the Order Block range"""
        return self.low <= price <= self.high


@dataclass
class FairValueGap:
    """
    Represents a Fair Value Gap (FVG)

    FVG: A 3-candle pattern where price moves so fast it leaves an imbalance,
    creating a gap that price often returns to fill
    """

    zone_type: ZoneType = field(default=ZoneType.FAIR_VALUE_GAP)
    is_bullish: bool = False

    # Gap range
    gap_high: Decimal = Decimal("0")
    gap_low: Decimal = Decimal("0")

    # Candle info
    candle1_index: int = 0
    candle2_index: int = 0
    candle3_index: int = 0
    timestamp: pd.Timestamp = None
    timeframe: str = ""

    # Fill tracking
    status: ZoneStatus = ZoneStatus.ACTIVE
    fill_percentage: float = 0.0  # 0-100%
    filled_at: Optional[datetime] = None

    # Strength
    strength_score: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)

    def get_gap_size(self) -> Decimal:
        """Get the size of the Fair Value Gap"""
        return self.gap_high - self.gap_low

    def get_midpoint(self) -> Decimal:
        """Get the midpoint of the gap"""
        return (self.gap_high + self.gap_low) / Decimal("2")

    def contains_price(self, price: Decimal) -> bool:
        """Check if price is within the gap"""
        return self.gap_low <= price <= self.gap_high


class ConfluenceZoneAnalyzer:
    """
    Analyzes and manages confluence zones (Order Blocks and Fair Value Gaps)
    """

    def __init__(
        self,
        market_structure: MarketStructureAnalyzer,
        timeframe: str = "1h",
        max_active_zones: int = 20,
    ):
        """
        Initialize Confluence Zone Analyzer

        Args:
            market_structure: MarketStructureAnalyzer instance for structure breaks
            timeframe: Timeframe for zone detection
            max_active_zones: Maximum number of active zones to track
        """
        self.market_structure = market_structure
        self.timeframe = timeframe
        self.max_active_zones = max_active_zones

        self.order_blocks: List[OrderBlock] = []
        self.fair_value_gaps: List[FairValueGap] = []

        logger.info(
            "ConfluenceZoneAnalyzer initialized", timeframe=timeframe, max_zones=max_active_zones
        )

    def analyze(self, df: pd.DataFrame) -> dict:
        """
        Analyze price data for confluence zones

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Dictionary with zone analysis results
        """
        if len(df) < 3:
            logger.warning("Insufficient data for zone analysis")
            return self.get_zones_summary()

        # Detect Order Blocks from structure breaks
        self._detect_order_blocks(df)

        # Detect Fair Value Gaps
        self._detect_fair_value_gaps(df)

        # Update zone status (check invalidations)
        self._update_zone_status(df)

        # Calculate strength scores
        self._calculate_all_zone_scores()

        # Cleanup old/invalidated zones
        self._cleanup_zones()

        logger.debug(
            "Confluence zones analyzed",
            order_blocks=len([ob for ob in self.order_blocks if ob.status == ZoneStatus.ACTIVE]),
            fvgs=len([fvg for fvg in self.fair_value_gaps if fvg.status == ZoneStatus.ACTIVE]),
        )

        return self.get_zones_summary()

    def _detect_order_blocks(self, df: pd.DataFrame) -> None:
        """
        Detect Order Blocks from structure breaks

        Order Block: The last opposite-direction candle before a structure break
        """
        structure_events = self.market_structure.structure_events

        for event in structure_events:
            # Check if we already have an OB for this event
            existing = any(ob.structure_break == event for ob in self.order_blocks)
            if existing:
                continue

            # Get the candle at the structure break
            break_index = event.index
            if break_index < 1 or break_index >= len(df):
                continue

            # Look back to find the last opposite candle
            ob_index = self._find_order_block_candle(df, break_index, event)

            if ob_index is not None:
                candle = df.iloc[ob_index]

                # Determine if bullish or bearish OB
                is_bullish = event.current_trend == TrendDirection.BULLISH

                order_block = OrderBlock(
                    is_bullish=is_bullish,
                    high=Decimal(str(candle["high"])),
                    low=Decimal(str(candle["low"])),
                    open=Decimal(str(candle["open"])),
                    close=Decimal(str(candle["close"])),
                    index=ob_index,
                    timestamp=candle.name,
                    timeframe=self.timeframe,
                    volume=float(candle["volume"]) if "volume" in candle else 0.0,
                    structure_break=event,
                    status=ZoneStatus.ACTIVE,
                )

                self.order_blocks.append(order_block)

                logger.debug(
                    "Order Block detected",
                    is_bullish=is_bullish,
                    price_range=f"{float(order_block.low)}-{float(order_block.high)}",
                )

    def _find_order_block_candle(
        self, df: pd.DataFrame, break_index: int, event: StructureEvent
    ) -> Optional[int]:
        """
        Find the Order Block candle (last opposite candle before break)

        Args:
            df: DataFrame with OHLCV data
            break_index: Index where structure break occurred
            event: StructureEvent object

        Returns:
            Index of Order Block candle, or None
        """
        # Look back up to 20 candles
        lookback = min(20, break_index)

        is_bullish_break = event.current_trend == TrendDirection.BULLISH

        # Search backwards for last opposite candle
        for i in range(break_index - 1, break_index - lookback - 1, -1):
            if i < 0:
                break

            candle = df.iloc[i]

            if is_bullish_break:
                # For bullish break, find last bearish (red) candle
                if candle["close"] < candle["open"]:
                    return i
            else:
                # For bearish break, find last bullish (green) candle
                if candle["close"] > candle["open"]:
                    return i

        return None

    def _detect_fair_value_gaps(self, df: pd.DataFrame) -> None:
        """
        Detect Fair Value Gaps (3-candle imbalance patterns)

        Bullish FVG: candle[0].high < candle[2].low (gap up)
        Bearish FVG: candle[0].low > candle[2].high (gap down)
        """
        # Need at least 3 candles
        for i in range(len(df) - 2):
            candle0 = df.iloc[i]
            candle1 = df.iloc[i + 1]
            candle2 = df.iloc[i + 2]

            # Check for bullish FVG
            if candle0["high"] < candle2["low"]:
                gap_low = Decimal(str(candle0["high"]))
                gap_high = Decimal(str(candle2["low"]))

                # Check if we already have this FVG
                existing = any(
                    fvg.candle1_index == i and fvg.is_bullish for fvg in self.fair_value_gaps
                )

                if not existing and gap_high > gap_low:
                    fvg = FairValueGap(
                        is_bullish=True,
                        gap_high=gap_high,
                        gap_low=gap_low,
                        candle1_index=i,
                        candle2_index=i + 1,
                        candle3_index=i + 2,
                        timestamp=candle2.name,
                        timeframe=self.timeframe,
                        status=ZoneStatus.ACTIVE,
                    )

                    self.fair_value_gaps.append(fvg)

                    logger.debug(
                        "Bullish FVG detected",
                        gap_size=float(gap_high - gap_low),
                        range=f"{float(gap_low)}-{float(gap_high)}",
                    )

            # Check for bearish FVG
            elif candle0["low"] > candle2["high"]:
                gap_high = Decimal(str(candle0["low"]))
                gap_low = Decimal(str(candle2["high"]))

                existing = any(
                    fvg.candle1_index == i and not fvg.is_bullish for fvg in self.fair_value_gaps
                )

                if not existing and gap_high > gap_low:
                    fvg = FairValueGap(
                        is_bullish=False,
                        gap_high=gap_high,
                        gap_low=gap_low,
                        candle1_index=i,
                        candle2_index=i + 1,
                        candle3_index=i + 2,
                        timestamp=candle2.name,
                        timeframe=self.timeframe,
                        status=ZoneStatus.ACTIVE,
                    )

                    self.fair_value_gaps.append(fvg)

                    logger.debug(
                        "Bearish FVG detected",
                        gap_size=float(gap_high - gap_low),
                        range=f"{float(gap_low)}-{float(gap_high)}",
                    )

    def _update_zone_status(self, df: pd.DataFrame) -> None:
        """
        Update status of all zones (check invalidations and fills)

        Args:
            df: DataFrame with OHLCV data
        """
        if len(df) == 0:
            return

        current_candle = df.iloc[-1]
        current_price = Decimal(str(current_candle["close"]))
        current_high = Decimal(str(current_candle["high"]))
        current_low = Decimal(str(current_candle["low"]))

        # Check Order Block invalidations
        for ob in self.order_blocks:
            if ob.status != ZoneStatus.ACTIVE:
                continue

            if ob.is_bullish:
                # Bullish OB invalidated if price closes below OB low
                if current_price < ob.low:
                    ob.status = ZoneStatus.INVALIDATED
                    ob.invalidated_at = datetime.now()
                    logger.debug(f"Bullish OB invalidated at {float(current_price)}")
                # Count touches
                elif current_low <= ob.high:
                    ob.touch_count += 1
            else:
                # Bearish OB invalidated if price closes above OB high
                if current_price > ob.high:
                    ob.status = ZoneStatus.INVALIDATED
                    ob.invalidated_at = datetime.now()
                    logger.debug(f"Bearish OB invalidated at {float(current_price)}")
                # Count touches
                elif current_high >= ob.low:
                    ob.touch_count += 1

        # Check FVG fills
        for fvg in self.fair_value_gaps:
            if fvg.status == ZoneStatus.FILLED:
                continue

            # Check if price has entered the gap
            if current_low <= fvg.gap_high and current_high >= fvg.gap_low:
                # Calculate fill percentage
                gap_size = fvg.get_gap_size()

                if fvg.is_bullish:
                    # For bullish FVG, fill from below
                    filled_amount = min(current_high, fvg.gap_high) - fvg.gap_low
                else:
                    # For bearish FVG, fill from above
                    filled_amount = fvg.gap_high - max(current_low, fvg.gap_low)

                fvg.fill_percentage = float((filled_amount / gap_size) * 100)

                if fvg.fill_percentage >= 100:
                    fvg.status = ZoneStatus.FILLED
                    fvg.filled_at = datetime.now()
                    logger.debug(f"FVG fully filled at {float(current_price)}")
                elif fvg.fill_percentage > 0:
                    fvg.status = ZoneStatus.PARTIAL_FILL

    def _calculate_all_zone_scores(self) -> None:
        """Calculate strength scores for all active zones"""
        for ob in self.order_blocks:
            if ob.status == ZoneStatus.ACTIVE:
                ob.strength_score = self._calculate_zone_strength(ob)

        for fvg in self.fair_value_gaps:
            if fvg.status == ZoneStatus.ACTIVE:
                fvg.strength_score = self._calculate_zone_strength(fvg)

    def _calculate_zone_strength(self, zone) -> float:
        """
        Calculate strength score for a zone (0-100)

        Scoring factors:
        - Volume: 0-30 points
        - Size: 0-20 points
        - Timeframe: H4=30, H1=20, M15=10 points
        - Age: Fresher = higher (0-20 points)
        - Touch count: Fewer = stronger (0-10 points)

        Args:
            zone: OrderBlock or FairValueGap object

        Returns:
            Strength score (0-100)
        """
        score = 0.0

        # Timeframe score
        tf_scores = {"4h": 30, "1h": 20, "15m": 10, "5m": 5}
        score += tf_scores.get(self.timeframe, 15)

        if isinstance(zone, OrderBlock):
            # Volume score (0-30)
            if zone.volume > 0:
                # Normalize volume (assuming typical volume range)
                volume_score = min(30, (zone.volume / 10000) * 30)
                score += volume_score

            # Size score (0-20)
            zone_size = float(zone.get_range())
            size_score = min(20, (zone_size / 10) * 20)  # Normalize by typical size
            score += size_score

            # Touch count (0-10, fewer = better)
            touch_penalty = min(10, zone.touch_count * 2)
            score += 10 - touch_penalty

        elif isinstance(zone, FairValueGap):
            # Gap size score (0-30)
            gap_size = float(zone.get_gap_size())
            size_score = min(30, (gap_size / 5) * 30)
            score += size_score

            # Fill percentage penalty
            fill_penalty = zone.fill_percentage / 10  # 0-10 penalty
            score -= fill_penalty

        # Age score (0-20, fresher = higher)
        age_hours = (datetime.now() - zone.created_at).total_seconds() / 3600
        age_score = max(0, 20 - (age_hours / 24) * 20)  # Decay over days
        score += age_score

        return max(0.0, min(100.0, score))

    def _cleanup_zones(self) -> None:
        """Remove old invalidated zones to keep list manageable"""
        # Keep only active zones and recent invalidated ones
        self.order_blocks = [
            ob
            for ob in self.order_blocks
            if ob.status == ZoneStatus.ACTIVE
            or (ob.invalidated_at and (datetime.now() - ob.invalidated_at).days < 1)
        ][: self.max_active_zones]

        self.fair_value_gaps = [
            fvg
            for fvg in self.fair_value_gaps
            if fvg.status in [ZoneStatus.ACTIVE, ZoneStatus.PARTIAL_FILL]
            or (fvg.filled_at and (datetime.now() - fvg.filled_at).days < 1)
        ][: self.max_active_zones]

    def get_zones_summary(self) -> dict:
        """Get summary of all confluence zones"""
        active_obs = [ob for ob in self.order_blocks if ob.status == ZoneStatus.ACTIVE]
        active_fvgs = [fvg for fvg in self.fair_value_gaps if fvg.status == ZoneStatus.ACTIVE]

        return {
            "order_blocks": {
                "total": len(self.order_blocks),
                "active": len(active_obs),
                "bullish": len([ob for ob in active_obs if ob.is_bullish]),
                "bearish": len([ob for ob in active_obs if not ob.is_bullish]),
            },
            "fair_value_gaps": {
                "total": len(self.fair_value_gaps),
                "active": len(active_fvgs),
                "bullish": len([fvg for fvg in active_fvgs if fvg.is_bullish]),
                "bearish": len([fvg for fvg in active_fvgs if not fvg.is_bullish]),
            },
        }

    def get_active_order_blocks(self, is_bullish: Optional[bool] = None) -> List[OrderBlock]:
        """
        Get active Order Blocks

        Args:
            is_bullish: Filter by bullish (True) or bearish (False), None for all

        Returns:
            List of active OrderBlock objects
        """
        obs = [ob for ob in self.order_blocks if ob.status == ZoneStatus.ACTIVE]

        if is_bullish is not None:
            obs = [ob for ob in obs if ob.is_bullish == is_bullish]

        # Sort by strength score (highest first)
        obs.sort(key=lambda x: x.strength_score, reverse=True)

        return obs

    def get_active_fvgs(self, is_bullish: Optional[bool] = None) -> List[FairValueGap]:
        """
        Get active Fair Value Gaps

        Args:
            is_bullish: Filter by bullish (True) or bearish (False), None for all

        Returns:
            List of active FairValueGap objects
        """
        fvgs = [fvg for fvg in self.fair_value_gaps if fvg.status == ZoneStatus.ACTIVE]

        if is_bullish is not None:
            fvgs = [fvg for fvg in fvgs if fvg.is_bullish == is_bullish]

        # Sort by strength score (highest first)
        fvgs.sort(key=lambda x: x.strength_score, reverse=True)

        return fvgs

    def find_confluence_at_price(self, price: Decimal, tolerance: Decimal = Decimal("0.5")) -> dict:
        """
        Find confluence zones near a given price

        Args:
            price: Target price to check
            tolerance: Price tolerance (percentage)

        Returns:
            Dictionary with zones near the price
        """
        tolerance_range = price * (tolerance / Decimal("100"))
        price_low = price - tolerance_range
        price_high = price + tolerance_range

        nearby_obs = []
        nearby_fvgs = []

        for ob in self.get_active_order_blocks():
            if ob.low <= price_high and ob.high >= price_low:
                nearby_obs.append(ob)

        for fvg in self.get_active_fvgs():
            if fvg.gap_low <= price_high and fvg.gap_high >= price_low:
                nearby_fvgs.append(fvg)

        return {
            "price": float(price),
            "order_blocks": nearby_obs,
            "fair_value_gaps": nearby_fvgs,
            "confluence_count": len(nearby_obs) + len(nearby_fvgs),
        }
