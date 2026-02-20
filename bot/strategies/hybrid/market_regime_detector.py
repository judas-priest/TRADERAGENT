"""
Market Regime Detector — v2.0.

Classifies market conditions into regimes and recommends strategy:
- Sideways (low ADX, narrow BB) → Grid
- Downtrend (high ADX, bearish EMA) → DCA
- Uptrend (high ADX, bullish EMA) → Trend-Follower
- High Volatility (wide BB, volume spike) → Reduce exposure

Uses: ADX, Bollinger Bands width, EMA crossover, RSI, Volume profile.
Tracks regime changes with transition events and cooldown.

Usage:
    detector = MarketRegimeDetectorV2()
    result = detector.evaluate(indicators)
    if result.regime == RegimeType.SIDEWAYS:
        # Use Grid strategy
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any


# =============================================================================
# Enums
# =============================================================================


class RegimeType(str, Enum):
    """Market regime classification."""

    SIDEWAYS = "sideways"  # Range-bound → Grid
    DOWNTREND = "downtrend"  # Bearish → DCA
    UPTREND = "uptrend"  # Bullish → Trend-Follower
    HIGH_VOLATILITY = "high_volatility"  # Extreme → Reduce exposure
    TRANSITIONING = "transitioning"  # Regime change in progress
    UNKNOWN = "unknown"  # Insufficient data


class StrategyRecommendation(str, Enum):
    """Strategy recommended for the detected regime."""

    GRID = "grid"
    DCA = "dca"
    TREND_FOLLOWER = "trend_follower"
    HYBRID = "hybrid"  # Grid + DCA combination
    REDUCE_EXPOSURE = "reduce_exposure"
    HOLD = "hold"


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class BBWidth:
    """Bollinger Bands width metrics."""

    upper: Decimal = Decimal("0")
    lower: Decimal = Decimal("0")
    middle: Decimal = Decimal("0")
    width_pct: Decimal = Decimal("0")  # (upper - lower) / middle * 100


@dataclass
class VolumeProfile:
    """Volume analysis metrics."""

    current_volume: Decimal = Decimal("0")
    avg_volume: Decimal = Decimal("0")
    volume_ratio: Decimal = Decimal("0")  # current / avg


@dataclass
class MarketIndicators:
    """
    Pre-computed market indicators for regime detection.

    The detector does not compute indicators from raw OHLCV —
    the caller provides them (from exchange data or pre-processing).
    """

    current_price: Decimal = Decimal("0")

    # Trend indicators
    ema_fast: Decimal | None = None  # e.g. EMA(20)
    ema_slow: Decimal | None = None  # e.g. EMA(50)
    adx: float | None = None  # Average Directional Index (0-100)
    plus_di: float | None = None  # +DI component
    minus_di: float | None = None  # -DI component

    # Bollinger Bands
    bb_upper: Decimal | None = None
    bb_lower: Decimal | None = None
    bb_middle: Decimal | None = None

    # Momentum
    rsi: float | None = None  # RSI (0-100)
    atr: Decimal | None = None  # Average True Range
    atr_pct: float | None = None  # ATR as % of price

    # Volume
    current_volume: Decimal | None = None
    avg_volume: Decimal | None = None

    # Optional time
    timestamp: datetime | None = None


@dataclass
class RegimeChangeEvent:
    """Records a regime transition."""

    previous_regime: RegimeType
    new_regime: RegimeType
    previous_strategy: StrategyRecommendation
    new_strategy: StrategyRecommendation
    confidence: float
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "previous_regime": self.previous_regime.value,
            "new_regime": self.new_regime.value,
            "previous_strategy": self.previous_strategy.value,
            "new_strategy": self.new_strategy.value,
            "confidence": round(self.confidence, 4),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class RegimeResult:
    """Result of a regime evaluation."""

    regime: RegimeType
    strategy: StrategyRecommendation
    confidence: float  # 0.0 - 1.0
    regime_changed: bool = False
    change_event: RegimeChangeEvent | None = None

    # Detailed scores
    trend_score: float = 0.0  # -1.0 (bearish) to +1.0 (bullish)
    volatility_score: float = 0.0  # 0.0 (low) to 1.0 (extreme)
    range_score: float = 0.0  # 0.0 (trending) to 1.0 (strong range)
    volume_score: float = 0.0  # 0.0 (low) to 1.0 (high)

    warnings: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime.value,
            "strategy": self.strategy.value,
            "confidence": round(self.confidence, 4),
            "regime_changed": self.regime_changed,
            "change_event": self.change_event.to_dict() if self.change_event else None,
            "trend_score": round(self.trend_score, 4),
            "volatility_score": round(self.volatility_score, 4),
            "range_score": round(self.range_score, 4),
            "volume_score": round(self.volume_score, 4),
            "warnings": self.warnings,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class RegimeConfig:
    """Configuration for regime detection thresholds."""

    # ADX thresholds
    adx_trend_threshold: float = 25.0  # ADX > this → trending
    adx_strong_trend: float = 40.0  # ADX > this → strong trend

    # Bollinger Bands
    bb_narrow_pct: Decimal = Decimal("2.0")  # BB width < this → sideways
    bb_wide_pct: Decimal = Decimal("6.0")  # BB width > this → high volatility

    # Volume
    volume_spike_ratio: Decimal = Decimal("2.0")  # vol > 2x avg → spike
    volume_low_ratio: Decimal = Decimal("0.5")  # vol < 0.5x avg → quiet

    # RSI
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0

    # Regime change
    min_regime_duration_seconds: int = 300  # Hold regime for 5 min before switching
    confirmation_count: int = 2  # Require N evaluations before confirming change

    # Strategy mapping
    hybrid_adx_min: float = 20.0  # Min ADX for hybrid mode
    hybrid_adx_max: float = 35.0  # Max ADX for hybrid mode


# =============================================================================
# Market Regime Detector
# =============================================================================


class MarketRegimeDetectorV2:
    """
    Detects market regime from pre-computed indicators.

    Classification logic:
    1. HIGH_VOLATILITY: BB width > wide threshold OR volume spike + wide BB
    2. SIDEWAYS: ADX < trend threshold AND BB width < narrow threshold
    3. UPTREND: ADX > trend threshold AND EMA fast > EMA slow
    4. DOWNTREND: ADX > trend threshold AND EMA fast < EMA slow
    5. TRANSITIONING: Conflicting signals or recent regime change

    Strategy mapping:
    - SIDEWAYS → Grid
    - DOWNTREND → DCA
    - UPTREND → Trend-Follower
    - Moderate ADX between thresholds → Hybrid (Grid + DCA)
    - HIGH_VOLATILITY → Reduce exposure
    """

    def __init__(self, config: RegimeConfig | None = None):
        self._config = config or RegimeConfig()

        # State tracking
        self._current_regime: RegimeType = RegimeType.UNKNOWN
        self._current_strategy: StrategyRecommendation = StrategyRecommendation.HOLD
        self._regime_since: datetime | None = None
        self._pending_regime: RegimeType | None = None
        self._pending_count: int = 0
        self._history: list[RegimeChangeEvent] = []
        self._evaluation_count: int = 0

    @property
    def config(self) -> RegimeConfig:
        return self._config

    @property
    def current_regime(self) -> RegimeType:
        return self._current_regime

    @property
    def current_strategy(self) -> StrategyRecommendation:
        return self._current_strategy

    @property
    def history(self) -> list[RegimeChangeEvent]:
        return self._history.copy()

    # -----------------------------------------------------------------
    # Core Evaluation
    # -----------------------------------------------------------------

    def evaluate(self, indicators: MarketIndicators) -> RegimeResult:
        """
        Evaluate market indicators and determine regime.

        Args:
            indicators: Pre-computed market indicators.

        Returns:
            RegimeResult with regime, strategy, and change detection.
        """
        self._evaluation_count += 1
        now = indicators.timestamp or datetime.now(timezone.utc)
        warnings: list[str] = []

        # Calculate component scores
        trend_score = self._compute_trend_score(indicators)
        volatility_score = self._compute_volatility_score(indicators, warnings)
        range_score = self._compute_range_score(indicators)
        volume_score = self._compute_volume_score(indicators)

        # Classify regime
        raw_regime = self._classify(
            trend_score, volatility_score, range_score, volume_score, indicators
        )

        # Apply regime change detection
        regime_changed, change_event = self._apply_regime_change(raw_regime, now)

        # Determine strategy
        strategy = self._recommend_strategy(self._current_regime, indicators)
        self._current_strategy = strategy

        # Confidence
        confidence = self._compute_confidence(
            self._current_regime, trend_score, volatility_score, range_score
        )

        return RegimeResult(
            regime=self._current_regime,
            strategy=strategy,
            confidence=confidence,
            regime_changed=regime_changed,
            change_event=change_event,
            trend_score=trend_score,
            volatility_score=volatility_score,
            range_score=range_score,
            volume_score=volume_score,
            warnings=warnings,
            timestamp=now,
        )

    # -----------------------------------------------------------------
    # Component Scores
    # -----------------------------------------------------------------

    def _compute_trend_score(self, ind: MarketIndicators) -> float:
        """
        Compute trend score from -1.0 (strong bearish) to +1.0 (strong bullish).

        Uses EMA crossover direction and ADX for strength.
        """
        if ind.ema_fast is None or ind.ema_slow is None:
            return 0.0

        if ind.ema_slow == 0:
            return 0.0

        # EMA divergence direction
        ema_divergence = float((ind.ema_fast - ind.ema_slow) / ind.ema_slow * 100)

        # Scale by ADX strength
        adx = ind.adx if ind.adx is not None else 20.0
        adx_factor = min(adx / self._config.adx_strong_trend, 1.0)

        # Combine direction + strength
        direction = 1.0 if ema_divergence > 0 else -1.0
        magnitude = min(abs(ema_divergence) / 3.0, 1.0)  # Normalize to [-1, 1]

        return direction * magnitude * adx_factor

    def _compute_volatility_score(self, ind: MarketIndicators, warnings: list[str]) -> float:
        """
        Compute volatility score from 0.0 (calm) to 1.0 (extreme).

        Uses BB width and ATR.
        """
        bb_score = 0.0
        atr_score = 0.0
        has_data = False

        # Bollinger Bands width
        if (
            ind.bb_upper is not None
            and ind.bb_lower is not None
            and ind.bb_middle is not None
            and ind.bb_middle > 0
        ):
            bb_width_pct = float((ind.bb_upper - ind.bb_lower) / ind.bb_middle * 100)
            wide = float(self._config.bb_wide_pct)
            bb_score = min(bb_width_pct / wide, 1.0)
            has_data = True

            if bb_width_pct > wide:
                warnings.append(f"BB width {bb_width_pct:.1f}% exceeds threshold {wide}%")

        # ATR percentage
        if ind.atr_pct is not None:
            atr_score = min(ind.atr_pct / 5.0, 1.0)  # 5% ATR = max
            has_data = True

        if not has_data:
            return 0.3  # Default moderate

        return max(bb_score, atr_score)

    def _compute_range_score(self, ind: MarketIndicators) -> float:
        """
        Compute range/sideways score from 0.0 (trending) to 1.0 (strong range).

        Low ADX + narrow BB → high range score.
        """
        scores = []

        # ADX: low ADX → ranging
        if ind.adx is not None:
            threshold = self._config.adx_trend_threshold
            if ind.adx < threshold:
                scores.append(1.0 - (ind.adx / threshold))
            else:
                scores.append(0.0)

        # BB width: narrow → ranging
        if (
            ind.bb_upper is not None
            and ind.bb_lower is not None
            and ind.bb_middle is not None
            and ind.bb_middle > 0
        ):
            bb_width = float((ind.bb_upper - ind.bb_lower) / ind.bb_middle * 100)
            narrow = float(self._config.bb_narrow_pct)
            if bb_width < narrow:
                scores.append(1.0 - (bb_width / narrow))
            else:
                scores.append(0.0)

        if not scores:
            return 0.5  # Default

        return sum(scores) / len(scores)

    def _compute_volume_score(self, ind: MarketIndicators) -> float:
        """
        Compute volume score from 0.0 (quiet) to 1.0 (spike).
        """
        if ind.current_volume is None or ind.avg_volume is None or ind.avg_volume <= 0:
            return 0.5  # Default

        ratio = float(ind.current_volume / ind.avg_volume)
        spike = float(self._config.volume_spike_ratio)
        return min(ratio / spike, 1.0)

    # -----------------------------------------------------------------
    # Classification
    # -----------------------------------------------------------------

    def _classify(
        self,
        trend_score: float,
        volatility_score: float,
        range_score: float,
        volume_score: float,
        ind: MarketIndicators,
    ) -> RegimeType:
        """Classify market regime from component scores."""

        adx = ind.adx if ind.adx is not None else 20.0
        cfg = self._config

        # 1. High volatility check (top priority)
        if volatility_score >= 0.85 or (volatility_score >= 0.7 and volume_score >= 0.8):
            return RegimeType.HIGH_VOLATILITY

        # 2. Sideways: low ADX + high range score
        if adx < cfg.adx_trend_threshold and range_score > 0.4:
            return RegimeType.SIDEWAYS

        # 3. Trending: high ADX
        if adx >= cfg.adx_trend_threshold:
            if trend_score > 0.1:
                return RegimeType.UPTREND
            elif trend_score < -0.1:
                return RegimeType.DOWNTREND

        # 4. Ambiguous signals → transitioning
        if 0.3 <= range_score <= 0.6 and abs(trend_score) < 0.3:
            return RegimeType.TRANSITIONING

        # Fallback based on trend direction
        if trend_score > 0.1:
            return RegimeType.UPTREND
        elif trend_score < -0.1:
            return RegimeType.DOWNTREND

        return RegimeType.SIDEWAYS

    # -----------------------------------------------------------------
    # Strategy Recommendation
    # -----------------------------------------------------------------

    def _recommend_strategy(
        self, regime: RegimeType, ind: MarketIndicators
    ) -> StrategyRecommendation:
        """
        Recommend strategy based on regime.

        Hybrid mode is recommended when ADX is in a moderate zone
        (between min and max thresholds).
        """
        cfg = self._config
        adx = ind.adx if ind.adx is not None else 20.0

        if regime == RegimeType.HIGH_VOLATILITY:
            return StrategyRecommendation.REDUCE_EXPOSURE

        if regime == RegimeType.SIDEWAYS:
            return StrategyRecommendation.GRID

        if regime == RegimeType.DOWNTREND:
            # Moderate ADX → hybrid, strong ADX → pure DCA
            if cfg.hybrid_adx_min <= adx <= cfg.hybrid_adx_max:
                return StrategyRecommendation.HYBRID
            return StrategyRecommendation.DCA

        if regime == RegimeType.UPTREND:
            if cfg.hybrid_adx_min <= adx <= cfg.hybrid_adx_max:
                return StrategyRecommendation.HYBRID
            return StrategyRecommendation.TREND_FOLLOWER

        if regime == RegimeType.TRANSITIONING:
            return StrategyRecommendation.HOLD

        return StrategyRecommendation.HOLD

    # -----------------------------------------------------------------
    # Regime Change Detection
    # -----------------------------------------------------------------

    def _apply_regime_change(
        self, new_regime: RegimeType, now: datetime
    ) -> tuple[bool, RegimeChangeEvent | None]:
        """
        Apply regime change with confirmation and cooldown.

        Returns (regime_changed, change_event).
        """
        # First evaluation — initialize
        if self._current_regime == RegimeType.UNKNOWN:
            self._current_regime = new_regime
            self._regime_since = now
            return False, None

        # Same regime — no change
        if new_regime == self._current_regime:
            self._pending_regime = None
            self._pending_count = 0
            return False, None

        # New candidate detected
        if new_regime != self._pending_regime:
            # Different from pending → restart confirmation
            self._pending_regime = new_regime
            self._pending_count = 1
            return False, None

        # Same pending → increment
        self._pending_count += 1

        # Check confirmation count
        if self._pending_count < self._config.confirmation_count:
            return False, None

        # Check cooldown
        if self._regime_since is not None:
            elapsed = (now - self._regime_since).total_seconds()
            if elapsed < self._config.min_regime_duration_seconds:
                return False, None

        # Confirmed regime change
        old_regime = self._current_regime
        old_strategy = self._current_strategy

        self._current_regime = new_regime
        self._regime_since = now
        self._pending_regime = None
        self._pending_count = 0

        # Determine new strategy (preliminary)
        new_strategy = self._current_strategy  # Will be set by caller

        event = RegimeChangeEvent(
            previous_regime=old_regime,
            new_regime=new_regime,
            previous_strategy=old_strategy,
            new_strategy=new_strategy,
            confidence=0.0,  # Will be updated
            timestamp=now,
        )
        self._history.append(event)

        return True, event

    # -----------------------------------------------------------------
    # Confidence
    # -----------------------------------------------------------------

    def _compute_confidence(
        self,
        regime: RegimeType,
        trend_score: float,
        volatility_score: float,
        range_score: float,
    ) -> float:
        """Compute confidence in the regime classification."""

        if regime == RegimeType.UNKNOWN:
            return 0.0

        if regime == RegimeType.SIDEWAYS:
            return min(0.5 + range_score * 0.5, 1.0)

        if regime in (RegimeType.UPTREND, RegimeType.DOWNTREND):
            return min(0.4 + abs(trend_score) * 0.6, 1.0)

        if regime == RegimeType.HIGH_VOLATILITY:
            return min(0.5 + volatility_score * 0.5, 1.0)

        if regime == RegimeType.TRANSITIONING:
            return 0.3

        return 0.5

    # -----------------------------------------------------------------
    # Queries
    # -----------------------------------------------------------------

    def get_statistics(self) -> dict[str, Any]:
        """Return detector statistics."""
        return {
            "current_regime": self._current_regime.value,
            "current_strategy": self._current_strategy.value,
            "evaluation_count": self._evaluation_count,
            "regime_changes": len(self._history),
            "config": {
                "adx_trend_threshold": self._config.adx_trend_threshold,
                "adx_strong_trend": self._config.adx_strong_trend,
                "bb_narrow_pct": str(self._config.bb_narrow_pct),
                "bb_wide_pct": str(self._config.bb_wide_pct),
                "confirmation_count": self._config.confirmation_count,
            },
        }

    def reset(self) -> None:
        """Reset detector state."""
        self._current_regime = RegimeType.UNKNOWN
        self._current_strategy = StrategyRecommendation.HOLD
        self._regime_since = None
        self._pending_regime = None
        self._pending_count = 0
        self._history.clear()
        self._evaluation_count = 0
