"""
Confluence Zones Module

Detects and manages institutional order zones:
- Order Blocks (OB): Last opposite candle before structure break
- Fair Value Gaps (FVG): 3-candle imbalance patterns
- Liquidity Zones: Clusters of swing highs/lows where stop orders accumulate
- Zone strength scoring
- Zone invalidation tracking

Uses the smartmoneyconcepts library for OB/FVG/Liquidity detection.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

import pandas as pd
import smartmoneyconcepts.smc as smc

from bot.strategies.smc.market_structure import (
    MarketStructureAnalyzer,
    StructureEvent,
)
from bot.utils.logger import get_logger

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


@dataclass
class LiquidityZone:
    """
    Represents a liquidity zone (cluster of swing highs/lows).

    Buy-side liquidity sits above swing highs (stop-losses for shorts).
    Sell-side liquidity sits below swing lows (stop-losses for longs).
    """

    is_bullish: bool = False  # True = buy-side (above highs), False = sell-side (below lows)
    level: Decimal = Decimal("0")
    end_index: int = 0
    swept: bool = False
    index: int = 0
    timestamp: pd.Timestamp = None
    timeframe: str = ""
    strength_score: float = 0.0


class ConfluenceZoneAnalyzer:
    """
    Analyzes and manages confluence zones (Order Blocks, Fair Value Gaps, Liquidity)

    Uses smartmoneyconcepts library for detection.
    """

    def __init__(
        self,
        market_structure: MarketStructureAnalyzer,
        timeframe: str = "1h",
        max_active_zones: int = 20,
        close_mitigation: bool = False,
        join_consecutive_fvg: bool = False,
        liquidity_range_percent: float = 0.01,
    ):
        """
        Initialize Confluence Zone Analyzer

        Args:
            market_structure: MarketStructureAnalyzer instance for structure breaks
            timeframe: Timeframe for zone detection
            max_active_zones: Maximum number of active zones to track
            close_mitigation: If True, require close through OB for mitigation
            join_consecutive_fvg: If True, merge adjacent same-direction FVGs
            liquidity_range_percent: Percentage range for grouping swing clusters
        """
        self.market_structure = market_structure
        self.timeframe = timeframe
        self.max_active_zones = max_active_zones
        self.close_mitigation = close_mitigation
        self.join_consecutive_fvg = join_consecutive_fvg
        self.liquidity_range_percent = liquidity_range_percent

        self.order_blocks: list[OrderBlock] = []
        self.fair_value_gaps: list[FairValueGap] = []
        self.liquidity_zones: list[LiquidityZone] = []

        logger.info(
            "ConfluenceZoneAnalyzer initialized",
            timeframe=timeframe,
            max_zones=max_active_zones,
            close_mitigation=close_mitigation,
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

        # Detect Liquidity Zones
        self._detect_liquidity_zones(df)

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
            liquidity_zones=len([lz for lz in self.liquidity_zones if not lz.swept]),
        )

        return self.get_zones_summary()

    def _detect_order_blocks(self, df: pd.DataFrame) -> None:
        """
        Detect Order Blocks using smartmoneyconcepts library.
        """
        swings_df = self.market_structure.get_swings_df()
        if swings_df is None:
            return

        ohlc = self._prepare_ohlc_df(df)

        try:
            ob_df = smc.ob(ohlc, swings_df, close_mitigation=self.close_mitigation)
        except Exception as e:
            logger.warning("OB detection failed", error=str(e))
            return

        for i in range(len(ob_df)):
            row = ob_df.iloc[i]
            if pd.isna(row["OB"]):
                continue

            # Check if we already have an OB at this index
            existing = any(ob.index == i for ob in self.order_blocks)
            if existing:
                continue

            is_bullish = row["OB"] == 1.0
            top = Decimal(str(row["Top"]))
            bottom = Decimal(str(row["Bottom"]))
            ob_volume = float(row["OBVolume"]) if pd.notna(row["OBVolume"]) else 0.0
            mitigated_idx = row["MitigatedIndex"] if pd.notna(row["MitigatedIndex"]) else None

            # Determine status: if mitigated at a valid future index, mark as invalidated
            status = ZoneStatus.ACTIVE
            if mitigated_idx is not None and int(mitigated_idx) > i:
                status = ZoneStatus.INVALIDATED

            timestamp = (
                df.index[i] if isinstance(df.index[i], pd.Timestamp) else pd.Timestamp(df.index[i])
            )

            candle = df.iloc[i]
            order_block = OrderBlock(
                is_bullish=is_bullish,
                high=top,
                low=bottom,
                open=Decimal(str(candle["open"])),
                close=Decimal(str(candle["close"])),
                index=i,
                timestamp=timestamp,
                timeframe=self.timeframe,
                volume=ob_volume,
                status=status,
            )

            self.order_blocks.append(order_block)

            logger.debug(
                "Order Block detected",
                is_bullish=is_bullish,
                price_range=f"{float(bottom)}-{float(top)}",
            )

    def _detect_fair_value_gaps(self, df: pd.DataFrame) -> None:
        """
        Detect Fair Value Gaps using smartmoneyconcepts library.
        """
        ohlc = self._prepare_ohlc_df(df)

        try:
            fvg_df = smc.fvg(ohlc, join_consecutive=self.join_consecutive_fvg)
        except Exception as e:
            logger.warning("FVG detection failed", error=str(e))
            return

        for i in range(len(fvg_df)):
            row = fvg_df.iloc[i]
            if pd.isna(row["FVG"]):
                continue

            # Check if we already have this FVG
            existing = any(fvg.candle2_index == i for fvg in self.fair_value_gaps)
            if existing:
                continue

            is_bullish = row["FVG"] == 1.0
            gap_high = Decimal(str(row["Top"]))
            gap_low = Decimal(str(row["Bottom"]))
            mitigated_idx = row["MitigatedIndex"] if pd.notna(row["MitigatedIndex"]) else None

            # Determine status
            status = ZoneStatus.ACTIVE
            if mitigated_idx is not None and int(mitigated_idx) > i:
                status = ZoneStatus.FILLED

            timestamp = (
                df.index[i] if isinstance(df.index[i], pd.Timestamp) else pd.Timestamp(df.index[i])
            )

            fvg_obj = FairValueGap(
                is_bullish=is_bullish,
                gap_high=gap_high,
                gap_low=gap_low,
                candle1_index=max(0, i - 1),
                candle2_index=i,
                candle3_index=min(len(df) - 1, i + 1),
                timestamp=timestamp,
                timeframe=self.timeframe,
                status=status,
            )

            self.fair_value_gaps.append(fvg_obj)

            direction = "Bullish" if is_bullish else "Bearish"
            logger.debug(
                f"{direction} FVG detected",
                gap_size=float(gap_high - gap_low),
                range=f"{float(gap_low)}-{float(gap_high)}",
            )

    def _detect_liquidity_zones(self, df: pd.DataFrame) -> None:
        """
        Detect Liquidity Zones using smartmoneyconcepts library.
        """
        swings_df = self.market_structure.get_swings_df()
        if swings_df is None:
            return

        ohlc = self._prepare_ohlc_df(df)

        try:
            liq_df = smc.liquidity(ohlc, swings_df, range_percent=self.liquidity_range_percent)
        except Exception as e:
            logger.warning("Liquidity detection failed", error=str(e))
            return

        self.liquidity_zones.clear()

        for i in range(len(liq_df)):
            row = liq_df.iloc[i]
            if pd.isna(row["Liquidity"]):
                continue

            is_bullish = row["Liquidity"] == 1.0  # 1.0 = buy-side, -1.0 = sell-side
            level = Decimal(str(row["Level"])) if pd.notna(row["Level"]) else Decimal("0")
            end_index = int(row["End"]) if pd.notna(row["End"]) else i
            swept = pd.notna(row["Swept"])

            timestamp = (
                df.index[i] if isinstance(df.index[i], pd.Timestamp) else pd.Timestamp(df.index[i])
            )

            liq_zone = LiquidityZone(
                is_bullish=is_bullish,
                level=level,
                end_index=end_index,
                swept=swept,
                index=i,
                timestamp=timestamp,
                timeframe=self.timeframe,
            )

            self.liquidity_zones.append(liq_zone)

        logger.debug(
            "Liquidity zones detected",
            total=len(self.liquidity_zones),
            active=len([lz for lz in self.liquidity_zones if not lz.swept]),
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
        active_liq = [lz for lz in self.liquidity_zones if not lz.swept]

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
            "liquidity_zones": {
                "total": len(self.liquidity_zones),
                "active": len(active_liq),
                "buy_side": len([lz for lz in active_liq if lz.is_bullish]),
                "sell_side": len([lz for lz in active_liq if not lz.is_bullish]),
            },
        }

    def get_active_order_blocks(self, is_bullish: Optional[bool] = None) -> list[OrderBlock]:
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

    def get_active_fvgs(self, is_bullish: Optional[bool] = None) -> list[FairValueGap]:
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

    def get_active_liquidity_zones(self, is_bullish: Optional[bool] = None) -> list[LiquidityZone]:
        """
        Get active (un-swept) liquidity zones.

        Args:
            is_bullish: Filter by buy-side (True) or sell-side (False), None for all

        Returns:
            List of active LiquidityZone objects
        """
        zones = [lz for lz in self.liquidity_zones if not lz.swept]

        if is_bullish is not None:
            zones = [lz for lz in zones if lz.is_bullish == is_bullish]

        return zones

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
