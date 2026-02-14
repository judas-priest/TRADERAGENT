"""
MarketRegimeDetector - Determines current market regime for strategy selection.

Market Regimes:
- TRENDING_BULLISH: Strong upward trend → DCA or Hybrid
- TRENDING_BEARISH: Strong downward trend → DCA or Hybrid
- SIDEWAYS/RANGING: Low volatility consolidation → Grid
- HIGH_VOLATILITY: Extreme moves → Reduce exposure / pause
- TRANSITIONING: Regime change in progress → Monitor

Strategy Selection Logic (v2.0):
- Sideways → Grid Engine
- Trend + Low Confluence (<0.7) → DCA Engine
- Trend + High Confluence (≥0.7) → Hybrid Mode (Grid + DCA)
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

from bot.utils.logger import get_logger

logger = get_logger(__name__)


class MarketRegime(str, Enum):
    """Detected market regime."""

    TRENDING_BULLISH = "trending_bullish"
    TRENDING_BEARISH = "trending_bearish"
    SIDEWAYS = "sideways"
    HIGH_VOLATILITY = "high_volatility"
    TRANSITIONING = "transitioning"
    UNKNOWN = "unknown"


class RecommendedStrategy(str, Enum):
    """Strategy recommendation based on market regime."""

    GRID = "grid"
    DCA = "dca"
    HYBRID = "hybrid"
    REDUCE_EXPOSURE = "reduce_exposure"
    HOLD = "hold"


@dataclass
class RegimeAnalysis:
    """Result of market regime detection."""

    regime: MarketRegime
    confidence: float  # 0.0 - 1.0
    recommended_strategy: RecommendedStrategy
    confluence_score: float  # 0.0 - 1.0

    # Market metrics
    trend_strength: float  # -1.0 (strong bearish) to +1.0 (strong bullish)
    volatility_percentile: float  # 0-100
    ema_divergence_pct: float  # EMA spread as %
    atr_pct: float  # ATR as % of price
    rsi: float  # RSI value

    timestamp: datetime
    analysis_details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "regime": self.regime.value,
            "confidence": round(self.confidence, 4),
            "recommended_strategy": self.recommended_strategy.value,
            "confluence_score": round(self.confluence_score, 4),
            "trend_strength": round(self.trend_strength, 4),
            "volatility_percentile": round(self.volatility_percentile, 2),
            "ema_divergence_pct": round(self.ema_divergence_pct, 4),
            "atr_pct": round(self.atr_pct, 4),
            "rsi": round(self.rsi, 2),
            "timestamp": self.timestamp.isoformat(),
            "analysis_details": self.analysis_details,
        }


class MarketRegimeDetector:
    """
    Detects market regime using technical indicators and recommends trading strategy.

    Uses EMA crossover, ATR volatility, RSI, and volume analysis to determine
    whether the market is trending, ranging, or highly volatile.
    """

    def __init__(
        self,
        ema_fast: int = 20,
        ema_slow: int = 50,
        atr_period: int = 14,
        rsi_period: int = 14,
        trend_threshold: float = 0.5,
        high_volatility_percentile: float = 90.0,
        confluence_threshold: float = 0.7,
    ):
        """
        Args:
            ema_fast: Fast EMA period.
            ema_slow: Slow EMA period.
            atr_period: ATR calculation period.
            rsi_period: RSI calculation period.
            trend_threshold: EMA divergence % threshold for trend detection.
            high_volatility_percentile: ATR percentile for high-volatility regime.
            confluence_threshold: Score above which Hybrid mode is recommended.
        """
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.atr_period = atr_period
        self.rsi_period = rsi_period
        self.trend_threshold = trend_threshold
        self.high_volatility_percentile = high_volatility_percentile
        self.confluence_threshold = confluence_threshold

        self._last_analysis: RegimeAnalysis | None = None

    @property
    def last_analysis(self) -> RegimeAnalysis | None:
        """Return the most recent analysis result."""
        return self._last_analysis

    def analyze(self, df: pd.DataFrame) -> RegimeAnalysis:
        """
        Analyze market data and detect current regime.

        Args:
            df: OHLCV DataFrame with columns: open, high, low, close, volume.
                Must have at least ema_slow + atr_period rows.

        Returns:
            RegimeAnalysis with regime, confidence, and strategy recommendation.
        """
        min_rows = self.ema_slow + self.atr_period
        if len(df) < min_rows:
            logger.warning(
                "insufficient_data",
                required=min_rows,
                received=len(df),
            )
            return self._unknown_analysis("Insufficient data")

        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)

        # Calculate indicators
        ema_fast_vals = close.ewm(span=self.ema_fast, adjust=False).mean()
        ema_slow_vals = close.ewm(span=self.ema_slow, adjust=False).mean()
        atr = self._calculate_atr(high, low, close, self.atr_period)
        rsi = self._calculate_rsi(close, self.rsi_period)

        current_price = float(close.iloc[-1])
        current_ema_fast = float(ema_fast_vals.iloc[-1])
        current_ema_slow = float(ema_slow_vals.iloc[-1])
        current_atr = float(atr.iloc[-1])
        current_rsi = float(rsi.iloc[-1])

        # EMA divergence as percentage
        ema_divergence_pct = (
            (current_ema_fast - current_ema_slow) / current_ema_slow * 100
            if current_ema_slow != 0
            else 0.0
        )

        # ATR as percentage of price
        atr_pct = (current_atr / current_price * 100) if current_price != 0 else 0.0

        # ATR percentile (how volatile relative to recent history)
        atr_values = atr.dropna().values
        if len(atr_values) > 0:
            volatility_percentile = float(
                np.percentile(atr_values, 50)  # median for comparison
            )
            vol_pctile = float(
                (np.sum(atr_values <= current_atr) / len(atr_values)) * 100
            )
        else:
            volatility_percentile = 50.0
            vol_pctile = 50.0

        # Trend strength: normalized EMA divergence [-1.0, 1.0]
        trend_strength = max(-1.0, min(1.0, ema_divergence_pct / 2.0))

        # Detect regime
        regime = self._classify_regime(
            ema_divergence_pct=ema_divergence_pct,
            volatility_percentile=vol_pctile,
            rsi=current_rsi,
            trend_strength=trend_strength,
        )

        # Calculate confluence score
        confluence_score = self._calculate_confluence(
            trend_strength=trend_strength,
            rsi=current_rsi,
            volatility_percentile=vol_pctile,
            ema_divergence_pct=ema_divergence_pct,
        )

        # Determine recommended strategy
        recommended = self._recommend_strategy(regime, confluence_score)

        # Confidence based on signal clarity
        confidence = self._calculate_confidence(
            regime=regime,
            ema_divergence_pct=abs(ema_divergence_pct),
            volatility_percentile=vol_pctile,
            trend_strength=abs(trend_strength),
        )

        analysis = RegimeAnalysis(
            regime=regime,
            confidence=confidence,
            recommended_strategy=recommended,
            confluence_score=confluence_score,
            trend_strength=trend_strength,
            volatility_percentile=vol_pctile,
            ema_divergence_pct=ema_divergence_pct,
            atr_pct=atr_pct,
            rsi=current_rsi,
            timestamp=datetime.now(timezone.utc),
            analysis_details={
                "current_price": current_price,
                "ema_fast": current_ema_fast,
                "ema_slow": current_ema_slow,
                "atr": current_atr,
                "data_points": len(df),
            },
        )

        self._last_analysis = analysis
        logger.info(
            "market_regime_detected",
            regime=regime.value,
            confidence=round(confidence, 3),
            recommended=recommended.value,
            confluence=round(confluence_score, 3),
            trend_strength=round(trend_strength, 3),
        )

        return analysis

    def _classify_regime(
        self,
        ema_divergence_pct: float,
        volatility_percentile: float,
        rsi: float,
        trend_strength: float,
    ) -> MarketRegime:
        """Classify market regime based on indicators."""

        # High volatility override
        if volatility_percentile >= self.high_volatility_percentile:
            return MarketRegime.HIGH_VOLATILITY

        abs_divergence = abs(ema_divergence_pct)

        # Sideways: low EMA divergence
        if abs_divergence < self.trend_threshold:
            # Check if transitioning (RSI extreme but no trend yet)
            if rsi > 70 or rsi < 30:
                return MarketRegime.TRANSITIONING
            return MarketRegime.SIDEWAYS

        # Trending
        if ema_divergence_pct > self.trend_threshold:
            return MarketRegime.TRENDING_BULLISH
        elif ema_divergence_pct < -self.trend_threshold:
            return MarketRegime.TRENDING_BEARISH

        return MarketRegime.TRANSITIONING

    def _calculate_confluence(
        self,
        trend_strength: float,
        rsi: float,
        volatility_percentile: float,
        ema_divergence_pct: float,
    ) -> float:
        """
        Calculate confluence score (0.0 - 1.0).

        Higher score = multiple indicators agree on direction.
        """
        scores = []

        # Trend component (0-1): strong trend = high score
        trend_score = min(abs(trend_strength), 1.0)
        scores.append(trend_score * 0.35)

        # RSI component: extreme RSI in trend direction = higher confluence
        if trend_strength > 0:
            rsi_score = max(0.0, (rsi - 50) / 50)
        elif trend_strength < 0:
            rsi_score = max(0.0, (50 - rsi) / 50)
        else:
            rsi_score = 0.0
        scores.append(rsi_score * 0.25)

        # EMA divergence component: larger divergence = stronger signal
        ema_score = min(abs(ema_divergence_pct) / 3.0, 1.0)
        scores.append(ema_score * 0.25)

        # Volatility component: moderate volatility is best
        if 30 <= volatility_percentile <= 70:
            vol_score = 1.0
        elif volatility_percentile < 30:
            vol_score = volatility_percentile / 30.0
        else:
            vol_score = max(0.0, 1.0 - (volatility_percentile - 70) / 30.0)
        scores.append(vol_score * 0.15)

        return min(sum(scores), 1.0)

    def _recommend_strategy(
        self, regime: MarketRegime, confluence_score: float
    ) -> RecommendedStrategy:
        """
        Recommend trading strategy based on regime and confluence.

        Logic from v2.0 plan:
        - Sideways → Grid
        - Trend + Low Confluence (<0.7) → DCA
        - Trend + High Confluence (≥0.7) → Hybrid
        - High Volatility → Reduce exposure
        """
        if regime == MarketRegime.HIGH_VOLATILITY:
            return RecommendedStrategy.REDUCE_EXPOSURE

        if regime == MarketRegime.SIDEWAYS:
            return RecommendedStrategy.GRID

        if regime in (MarketRegime.TRENDING_BULLISH, MarketRegime.TRENDING_BEARISH):
            if confluence_score >= self.confluence_threshold:
                return RecommendedStrategy.HYBRID
            return RecommendedStrategy.DCA

        if regime == MarketRegime.TRANSITIONING:
            return RecommendedStrategy.HOLD

        return RecommendedStrategy.HOLD

    def _calculate_confidence(
        self,
        regime: MarketRegime,
        ema_divergence_pct: float,
        volatility_percentile: float,
        trend_strength: float,
    ) -> float:
        """Calculate confidence in the regime classification (0.0 - 1.0)."""

        if regime == MarketRegime.UNKNOWN:
            return 0.0

        if regime == MarketRegime.SIDEWAYS:
            # Confidence is high when divergence is close to 0
            return max(0.3, 1.0 - ema_divergence_pct / self.trend_threshold)

        if regime in (MarketRegime.TRENDING_BULLISH, MarketRegime.TRENDING_BEARISH):
            # Confidence grows with trend strength
            return min(0.5 + trend_strength * 0.5, 1.0)

        if regime == MarketRegime.HIGH_VOLATILITY:
            return min(volatility_percentile / 100.0, 1.0)

        return 0.5  # TRANSITIONING

    @staticmethod
    def _calculate_atr(
        high: pd.Series, low: pd.Series, close: pd.Series, period: int
    ) -> pd.Series:
        """Calculate Average True Range."""
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return true_range.rolling(window=period).mean()

    @staticmethod
    def _calculate_rsi(close: pd.Series, period: int) -> pd.Series:
        """Calculate Relative Strength Index."""
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.inf)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _unknown_analysis(self, reason: str) -> RegimeAnalysis:
        """Return unknown analysis for error cases."""
        return RegimeAnalysis(
            regime=MarketRegime.UNKNOWN,
            confidence=0.0,
            recommended_strategy=RecommendedStrategy.HOLD,
            confluence_score=0.0,
            trend_strength=0.0,
            volatility_percentile=0.0,
            ema_divergence_pct=0.0,
            atr_pct=0.0,
            rsi=50.0,
            timestamp=datetime.now(timezone.utc),
            analysis_details={"reason": reason},
        )
