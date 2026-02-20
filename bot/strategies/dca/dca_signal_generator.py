"""
DCA Signal Generator — v2.0.

Generates entry signals for DCA deals based on market analysis:
- Trend conditions (EMA crossover, ADX strength)
- Price conditions (target range, distance from support)
- Indicator conditions (RSI oversold, Bollinger Bands, volume)
- Confluence scoring system with weighted conditions
- Risk and timing filters

Usage:
    config = DCASignalConfig(ema_fast=12, ema_slow=26)
    generator = DCASignalGenerator(config)
    state = MarketState(current_price=..., ema_fast=..., ema_slow=..., ...)
    result = generator.evaluate(state)
    if result.should_open:
        # Open DCA deal
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

# =============================================================================
# Enums
# =============================================================================


class TrendDirection(str, Enum):
    """Expected trend direction for DCA entry."""

    DOWN = "down"  # Standard DCA — enter in downtrend
    UP = "up"  # Reverse DCA — enter in uptrend


class ConditionCategory(str, Enum):
    """Category of signal condition for scoring."""

    TREND = "trend"
    PRICE = "price"
    INDICATOR = "indicator"
    RISK = "risk"
    TIMING = "timing"


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class MarketState:
    """
    Snapshot of market data for signal evaluation.

    All fields are optional except current_price — the generator
    evaluates only conditions for which data is provided.
    """

    current_price: Decimal

    # Trend data
    ema_fast: Decimal | None = None
    ema_slow: Decimal | None = None
    adx: float | None = None

    # Indicator data
    rsi: float | None = None
    bb_lower: Decimal | None = None
    bb_upper: Decimal | None = None
    volume_24h: Decimal | None = None
    avg_volume: Decimal | None = None

    # Support/resistance
    nearest_support: Decimal | None = None

    # Account / deal context
    active_deals: int = 0
    daily_pnl: Decimal = Decimal("0")
    available_balance: Decimal = Decimal("0")
    required_capital: Decimal = Decimal("0")

    # Timing context
    last_deal_closed_at: datetime | None = None
    current_time: datetime | None = None


@dataclass
class ConditionResult:
    """Result of a single condition check."""

    category: ConditionCategory
    name: str
    passed: bool
    weight: int
    detail: str = ""


@dataclass
class SignalResult:
    """
    Full evaluation result from DCASignalGenerator.

    Attributes:
        should_open: Whether a new DCA deal should be opened.
        confluence_score: Weighted score 0.0–1.0.
        reason: Human-readable summary.
        conditions: Individual condition results.
        timestamp: When the evaluation was performed.
    """

    should_open: bool
    confluence_score: float
    reason: str
    conditions: list[ConditionResult] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def score_pct(self) -> float:
        """Confluence score as percentage (0–100)."""
        return round(self.confluence_score * 100, 1)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for logging / DB storage."""
        return {
            "should_open": self.should_open,
            "confluence_score": self.confluence_score,
            "score_pct": self.score_pct,
            "reason": self.reason,
            "conditions": [
                {
                    "category": c.category.value,
                    "name": c.name,
                    "passed": c.passed,
                    "weight": c.weight,
                    "detail": c.detail,
                }
                for c in self.conditions
            ],
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class DCASignalConfig:
    """
    Configuration for DCA signal generation.

    Weights determine how much each condition category contributes
    to the confluence score. Default weights follow the spec:
    trend=3, price=2, indicator=2, risk=1, timing=1.
    """

    # Trend parameters
    trend_direction: TrendDirection = TrendDirection.DOWN
    min_trend_strength: float = 20.0  # ADX threshold

    # Price parameters
    entry_price_min: Decimal | None = None
    entry_price_max: Decimal | None = None
    max_distance_from_support: Decimal = Decimal("0.02")  # 2%

    # Indicator parameters
    rsi_oversold_threshold: float = 35.0
    min_volume_multiplier: Decimal = Decimal("1.2")
    bb_tolerance: Decimal = Decimal("0.02")  # 2% tolerance above BB lower

    # Confluence
    require_confluence: bool = True
    min_confluence_score: float = 0.75  # 75%

    # Weights
    weight_trend: int = 3
    weight_price: int = 2
    weight_indicator: int = 2
    weight_risk: int = 1
    weight_timing: int = 1

    # Risk filters
    max_concurrent_deals: int = 3
    max_daily_loss: Decimal = Decimal("500")
    min_available_balance: Decimal = Decimal("0")  # 0 = no check

    # Timing filters
    min_seconds_between_deals: int = 3600  # 1 hour

    def validate(self) -> None:
        """Validate configuration values."""
        if self.min_trend_strength < 0 or self.min_trend_strength > 100:
            raise ValueError("min_trend_strength must be between 0 and 100")
        if self.rsi_oversold_threshold < 0 or self.rsi_oversold_threshold > 100:
            raise ValueError("rsi_oversold_threshold must be between 0 and 100")
        if self.min_confluence_score < 0 or self.min_confluence_score > 1:
            raise ValueError("min_confluence_score must be between 0.0 and 1.0")
        if self.max_concurrent_deals < 0:
            raise ValueError("max_concurrent_deals must be >= 0")
        if self.min_seconds_between_deals < 0:
            raise ValueError("min_seconds_between_deals must be >= 0")
        if self.entry_price_min is not None and self.entry_price_max is not None:
            if self.entry_price_min > self.entry_price_max:
                raise ValueError("entry_price_min must be <= entry_price_max")
        total_weight = (
            self.weight_trend
            + self.weight_price
            + self.weight_indicator
            + self.weight_risk
            + self.weight_timing
        )
        if total_weight <= 0:
            raise ValueError("Total weight must be positive")


# =============================================================================
# DCA Signal Generator
# =============================================================================


class DCASignalGenerator:
    """
    Evaluates market conditions and produces DCA entry signals.

    Checks five condition categories with configurable weights:
    1. Trend — EMA crossover + ADX strength
    2. Price — Target range + distance from support
    3. Indicators — RSI oversold + Bollinger Bands + volume
    4. Risk — Active deals, daily PnL, balance
    5. Timing — Cooldown between deals

    Each category produces a weighted score. The confluence score
    is the sum of passed weights divided by total weight.
    """

    def __init__(self, config: DCASignalConfig | None = None):
        self._config = config or DCASignalConfig()
        self._config.validate()

    @property
    def config(self) -> DCASignalConfig:
        return self._config

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def evaluate(self, state: MarketState) -> SignalResult:
        """
        Evaluate all conditions and return a SignalResult.

        Args:
            state: Current market snapshot.

        Returns:
            SignalResult with should_open decision and details.
        """
        conditions: list[ConditionResult] = []

        # 1. Risk filters (blocking — if fail, no deal regardless of score)
        risk_result = self.check_risk(state)
        conditions.append(risk_result)

        # 2. Timing filters (blocking)
        timing_result = self.check_timing(state)
        conditions.append(timing_result)

        # If blocking filters fail, reject immediately
        if not risk_result.passed or not timing_result.passed:
            blocking_reasons = [c.detail for c in [risk_result, timing_result] if not c.passed]
            return SignalResult(
                should_open=False,
                confluence_score=0.0,
                reason="; ".join(blocking_reasons),
                conditions=conditions,
            )

        # 3. Signal conditions
        conditions.append(self.check_trend(state))
        conditions.append(self.check_price(state))
        conditions.append(self.check_indicators(state))

        # 4. Calculate confluence score
        score, max_score = self._calculate_score(conditions)
        confluence = score / max_score if max_score > 0 else 0.0

        # 5. Decision
        if self._config.require_confluence:
            should_open = confluence >= self._config.min_confluence_score
            if should_open:
                reason = f"Signal confirmed (confluence: {confluence:.2f})"
            else:
                reason = (
                    f"Confluence too low: {confluence:.2f} < {self._config.min_confluence_score}"
                )
        else:
            # Simple AND logic — all signal conditions must pass
            signal_conditions = [
                c
                for c in conditions
                if c.category
                in (
                    ConditionCategory.TREND,
                    ConditionCategory.PRICE,
                    ConditionCategory.INDICATOR,
                )
            ]
            all_passed = all(c.passed for c in signal_conditions)
            should_open = all_passed
            if should_open:
                reason = "All conditions met"
            else:
                failed = [c.name for c in signal_conditions if not c.passed]
                reason = f"Conditions not met: {', '.join(failed)}"

        return SignalResult(
            should_open=should_open,
            confluence_score=round(confluence, 4),
            reason=reason,
            conditions=conditions,
        )

    # -----------------------------------------------------------------
    # Condition Checks
    # -----------------------------------------------------------------

    def check_trend(self, state: MarketState) -> ConditionResult:
        """
        Check trend conditions: EMA crossover + ADX strength.

        For DOWN direction (standard DCA): EMA fast < EMA slow.
        For UP direction (reverse DCA): EMA fast > EMA slow.
        ADX must exceed min_trend_strength.
        """
        cfg = self._config
        reasons: list[str] = []
        passed = True

        # EMA crossover
        if state.ema_fast is not None and state.ema_slow is not None:
            if cfg.trend_direction == TrendDirection.DOWN:
                ema_ok = state.ema_fast < state.ema_slow
            else:
                ema_ok = state.ema_fast > state.ema_slow

            if ema_ok:
                reasons.append(f"EMA crossover OK (fast={state.ema_fast}, slow={state.ema_slow})")
            else:
                passed = False
                reasons.append(
                    f"EMA crossover FAIL (fast={state.ema_fast}, slow={state.ema_slow}, "
                    f"expected {cfg.trend_direction.value})"
                )
        else:
            # No EMA data — skip this sub-condition (don't fail)
            reasons.append("EMA data not available, skipped")

        # ADX strength
        if state.adx is not None:
            if state.adx >= cfg.min_trend_strength:
                reasons.append(f"ADX OK ({state.adx:.1f} >= {cfg.min_trend_strength})")
            else:
                passed = False
                reasons.append(f"ADX weak ({state.adx:.1f} < {cfg.min_trend_strength})")
        else:
            reasons.append("ADX data not available, skipped")

        return ConditionResult(
            category=ConditionCategory.TREND,
            name="trend",
            passed=passed,
            weight=cfg.weight_trend,
            detail="; ".join(reasons),
        )

    def check_price(self, state: MarketState) -> ConditionResult:
        """
        Check price conditions: target range + distance from support.
        """
        cfg = self._config
        reasons: list[str] = []
        passed = True

        # Price range
        if cfg.entry_price_min is not None and cfg.entry_price_max is not None:
            in_range = cfg.entry_price_min <= state.current_price <= cfg.entry_price_max
            if in_range:
                reasons.append(f"Price in range ({cfg.entry_price_min}-{cfg.entry_price_max})")
            else:
                passed = False
                reasons.append(
                    f"Price {state.current_price} outside range "
                    f"({cfg.entry_price_min}-{cfg.entry_price_max})"
                )
        else:
            reasons.append("No price range configured, skipped")

        # Distance from support
        if state.nearest_support is not None and state.nearest_support > 0:
            distance = (state.current_price - state.nearest_support) / state.nearest_support
            if distance <= cfg.max_distance_from_support:
                reasons.append(f"Near support ({distance:.4f} <= {cfg.max_distance_from_support})")
            else:
                passed = False
                reasons.append(
                    f"Too far from support ({distance:.4f} > {cfg.max_distance_from_support})"
                )
        else:
            reasons.append("Support level not available, skipped")

        return ConditionResult(
            category=ConditionCategory.PRICE,
            name="price",
            passed=passed,
            weight=cfg.weight_price,
            detail="; ".join(reasons),
        )

    def check_indicators(self, state: MarketState) -> ConditionResult:
        """
        Check indicator conditions: RSI oversold + Bollinger Bands + volume.
        """
        cfg = self._config
        reasons: list[str] = []
        passed = True

        # RSI
        if state.rsi is not None:
            if state.rsi < cfg.rsi_oversold_threshold:
                reasons.append(f"RSI oversold ({state.rsi:.1f} < {cfg.rsi_oversold_threshold})")
            else:
                passed = False
                reasons.append(
                    f"RSI not oversold ({state.rsi:.1f} >= {cfg.rsi_oversold_threshold})"
                )
        else:
            reasons.append("RSI not available, skipped")

        # Volume
        if state.volume_24h is not None and state.avg_volume is not None:
            if state.avg_volume > 0:
                ratio = state.volume_24h / state.avg_volume
                if ratio >= cfg.min_volume_multiplier:
                    reasons.append(f"Volume confirmed ({ratio:.2f}x avg)")
                else:
                    passed = False
                    reasons.append(f"Volume low ({ratio:.2f}x < {cfg.min_volume_multiplier}x)")
            else:
                reasons.append("Avg volume is zero, skipped")
        else:
            reasons.append("Volume data not available, skipped")

        # Bollinger Bands
        if state.bb_lower is not None:
            tolerance = state.bb_lower * (1 + cfg.bb_tolerance)
            if state.current_price <= tolerance:
                reasons.append(f"At BB lower ({state.current_price} <= {tolerance:.2f})")
            else:
                passed = False
                reasons.append(f"Above BB lower ({state.current_price} > {tolerance:.2f})")
        else:
            reasons.append("BB data not available, skipped")

        return ConditionResult(
            category=ConditionCategory.INDICATOR,
            name="indicators",
            passed=passed,
            weight=cfg.weight_indicator,
            detail="; ".join(reasons),
        )

    def check_risk(self, state: MarketState) -> ConditionResult:
        """
        Check risk filters: concurrent deals, daily PnL, available balance.
        """
        cfg = self._config
        reasons: list[str] = []
        passed = True

        # Max concurrent deals
        if cfg.max_concurrent_deals > 0:
            if state.active_deals >= cfg.max_concurrent_deals:
                passed = False
                reasons.append(
                    f"Max concurrent deals reached ({state.active_deals} >= {cfg.max_concurrent_deals})"
                )
            else:
                reasons.append(f"Deals OK ({state.active_deals}/{cfg.max_concurrent_deals})")

        # Daily PnL
        if cfg.max_daily_loss > 0:
            if state.daily_pnl < -cfg.max_daily_loss:
                passed = False
                reasons.append(f"Daily loss exceeded ({state.daily_pnl} < -{cfg.max_daily_loss})")
            else:
                reasons.append(f"Daily PnL OK ({state.daily_pnl})")

        # Available balance
        if cfg.min_available_balance > 0:
            if state.available_balance < cfg.min_available_balance:
                passed = False
                reasons.append(
                    f"Insufficient balance ({state.available_balance} < {cfg.min_available_balance})"
                )
            else:
                reasons.append(f"Balance OK ({state.available_balance})")

        # Required capital check
        if state.required_capital > 0 and state.available_balance > 0:
            if state.available_balance < state.required_capital:
                passed = False
                reasons.append(
                    f"Not enough capital ({state.available_balance} < {state.required_capital} required)"
                )

        if not reasons:
            reasons.append("No risk filters configured")

        return ConditionResult(
            category=ConditionCategory.RISK,
            name="risk",
            passed=passed,
            weight=cfg.weight_risk,
            detail="; ".join(reasons),
        )

    def check_timing(self, state: MarketState) -> ConditionResult:
        """
        Check timing filters: cooldown between deals.
        """
        cfg = self._config
        reasons: list[str] = []
        passed = True

        if state.last_deal_closed_at is not None and cfg.min_seconds_between_deals > 0:
            now = state.current_time or datetime.now(timezone.utc)
            # Ensure both are timezone-aware
            last_closed = state.last_deal_closed_at
            if last_closed.tzinfo is None:
                last_closed = last_closed.replace(tzinfo=timezone.utc)
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)

            elapsed = (now - last_closed).total_seconds()
            if elapsed < cfg.min_seconds_between_deals:
                passed = False
                remaining = cfg.min_seconds_between_deals - elapsed
                reasons.append(f"Cooldown active ({remaining:.0f}s remaining)")
            else:
                reasons.append(f"Cooldown passed ({elapsed:.0f}s elapsed)")
        else:
            reasons.append("No timing constraint")

        return ConditionResult(
            category=ConditionCategory.TIMING,
            name="timing",
            passed=passed,
            weight=cfg.weight_timing,
            detail="; ".join(reasons),
        )

    # -----------------------------------------------------------------
    # Scoring
    # -----------------------------------------------------------------

    def _calculate_score(self, conditions: list[ConditionResult]) -> tuple[int, int]:
        """
        Calculate weighted score from condition results.

        Returns (achieved_score, max_possible_score).
        """
        score = 0
        max_score = 0
        for cond in conditions:
            max_score += cond.weight
            if cond.passed:
                score += cond.weight
        return score, max_score

    # -----------------------------------------------------------------
    # Utilities
    # -----------------------------------------------------------------

    def get_statistics(self) -> dict[str, Any]:
        """Return config summary for monitoring."""
        cfg = self._config
        return {
            "trend_direction": cfg.trend_direction.value,
            "min_trend_strength": cfg.min_trend_strength,
            "rsi_threshold": cfg.rsi_oversold_threshold,
            "require_confluence": cfg.require_confluence,
            "min_confluence_score": cfg.min_confluence_score,
            "weights": {
                "trend": cfg.weight_trend,
                "price": cfg.weight_price,
                "indicator": cfg.weight_indicator,
                "risk": cfg.weight_risk,
                "timing": cfg.weight_timing,
            },
            "max_concurrent_deals": cfg.max_concurrent_deals,
            "cooldown_seconds": cfg.min_seconds_between_deals,
        }
