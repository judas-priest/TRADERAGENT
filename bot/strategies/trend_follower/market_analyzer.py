"""
Market Analyzer Module

Calculates technical indicators and determines market phase:
- EMA (Exponential Moving Average)
- ATR (Average True Range)
- RSI (Relative Strength Index)
- Market Phase Detection (Bullish/Bearish Trend, Sideways)
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional

import pandas as pd

from bot.utils.logger import get_logger

logger = get_logger(__name__)


class MarketPhase(str, Enum):
    """Market phase classification"""

    BULLISH_TREND = "bullish_trend"
    BEARISH_TREND = "bearish_trend"
    SIDEWAYS = "sideways"
    UNKNOWN = "unknown"


class TrendStrength(str, Enum):
    """Trend strength classification"""

    STRONG = "strong"
    WEAK = "weak"
    NONE = "none"


@dataclass
class MarketConditions:
    """Current market conditions"""

    phase: MarketPhase
    trend_strength: TrendStrength
    ema_fast: Decimal
    ema_slow: Decimal
    ema_divergence_pct: Decimal
    atr: Decimal
    atr_pct: Decimal
    rsi: Decimal
    current_price: Decimal
    is_in_range: bool
    range_high: Optional[Decimal]
    range_low: Optional[Decimal]
    timestamp: pd.Timestamp


class MarketAnalyzer:
    """
    Analyzes market conditions and calculates technical indicators

    Implements the market analysis requirements from Issue #124:
    - Calculate indicators in real-time: EMA(20), EMA(50), ATR(14), RSI(14)
    - Determine market phase:
        * Bullish: (EMA20 > EMA50) AND (price > EMA20) AND (divergence > 0.5%)
        * Bearish: (EMA20 < EMA50) AND (price < EMA20) AND (divergence > 0.5%)
        * Sideways: (EMA difference < 0.5%) AND (price in High-Low range of last 50 candles)
    """

    def __init__(
        self,
        ema_fast_period: int = 20,
        ema_slow_period: int = 50,
        atr_period: int = 14,
        rsi_period: int = 14,
        ema_divergence_threshold: Decimal = Decimal("0.005"),
        ranging_lookback: int = 50,
        weak_trend_threshold: Decimal = Decimal("0.01"),
        strong_trend_threshold: Decimal = Decimal("0.02"),
    ):
        """
        Initialize Market Analyzer

        Args:
            ema_fast_period: Fast EMA period (default: 20)
            ema_slow_period: Slow EMA period (default: 50)
            atr_period: ATR period (default: 14)
            rsi_period: RSI period (default: 14)
            ema_divergence_threshold: Min EMA divergence for trend (default: 0.5%)
            ranging_lookback: Candles for range detection (default: 50)
            weak_trend_threshold: EMA divergence for weak trend (default: 1%)
            strong_trend_threshold: EMA divergence for strong trend (default: 2%)
        """
        self.ema_fast_period = ema_fast_period
        self.ema_slow_period = ema_slow_period
        self.atr_period = atr_period
        self.rsi_period = rsi_period
        self.ema_divergence_threshold = ema_divergence_threshold
        self.ranging_lookback = ranging_lookback
        self.weak_trend_threshold = weak_trend_threshold
        self.strong_trend_threshold = strong_trend_threshold

        logger.info(
            "MarketAnalyzer initialized",
            ema_periods=(ema_fast_period, ema_slow_period),
            atr_period=atr_period,
            rsi_period=rsi_period,
        )

    def analyze(self, df: pd.DataFrame) -> MarketConditions:
        """
        Analyze market conditions on given dataframe

        Args:
            df: DataFrame with OHLCV data (columns: open, high, low, close, volume)

        Returns:
            MarketConditions object with current market analysis

        Raises:
            ValueError: If dataframe is invalid or has insufficient data
        """
        self._validate_dataframe(df)

        # Calculate all indicators
        ema_fast = self._calculate_ema(df, self.ema_fast_period)
        ema_slow = self._calculate_ema(df, self.ema_slow_period)
        atr = self._calculate_atr(df, self.atr_period)
        rsi = self._calculate_rsi(df, self.rsi_period)

        current_price = Decimal(str(df["close"].iloc[-1]))
        ema_fast_val = Decimal(str(ema_fast.iloc[-1]))
        ema_slow_val = Decimal(str(ema_slow.iloc[-1]))
        atr_val = Decimal(str(atr.iloc[-1]))
        rsi_val = Decimal(str(rsi.iloc[-1]))

        # Calculate EMA divergence percentage
        ema_divergence_pct = abs((ema_fast_val - ema_slow_val) / ema_slow_val)

        # Calculate ATR as percentage of price
        atr_pct = atr_val / current_price

        # Determine if price is in range
        is_in_range, range_high, range_low = self._detect_ranging(df, current_price)

        # Determine market phase
        phase = self._determine_market_phase(
            current_price, ema_fast_val, ema_slow_val, ema_divergence_pct, is_in_range
        )

        # Determine trend strength
        trend_strength = self._determine_trend_strength(ema_divergence_pct, phase)

        conditions = MarketConditions(
            phase=phase,
            trend_strength=trend_strength,
            ema_fast=ema_fast_val,
            ema_slow=ema_slow_val,
            ema_divergence_pct=ema_divergence_pct,
            atr=atr_val,
            atr_pct=atr_pct,
            rsi=rsi_val,
            current_price=current_price,
            is_in_range=is_in_range,
            range_high=range_high,
            range_low=range_low,
            timestamp=df.index[-1],
        )

        logger.debug(
            "Market analyzed",
            phase=phase,
            trend_strength=trend_strength,
            price=float(current_price),
            ema_divergence=float(ema_divergence_pct),
            rsi=float(rsi_val),
        )

        return conditions

    def _validate_dataframe(self, df: pd.DataFrame) -> None:
        """Validate input dataframe"""
        required_columns = ["open", "high", "low", "close", "volume"]
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")

        min_required = max(
            self.ema_slow_period, self.atr_period, self.rsi_period, self.ranging_lookback
        )
        if len(df) < min_required:
            raise ValueError(f"Insufficient data: need {min_required} candles, got {len(df)}")

    def _calculate_ema(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calculate Exponential Moving Average"""
        return df["close"].ewm(span=period, adjust=False).mean()

    def _calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        """
        Calculate Average True Range

        ATR = Average of True Range over period
        True Range = max(high - low, abs(high - prev_close), abs(low - prev_close))
        """
        high = df["high"]
        low = df["low"]
        close = df["close"]
        prev_close = close.shift(1)

        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)

        true_range = pd.DataFrame({"tr1": tr1, "tr2": tr2, "tr3": tr3}).max(axis=1)
        atr = true_range.rolling(window=period).mean()

        return atr

    def _calculate_rsi(self, df: pd.DataFrame, period: int) -> pd.Series:
        """
        Calculate Relative Strength Index

        RSI = 100 - (100 / (1 + RS))
        RS = Average Gain / Average Loss over period
        """
        close = df["close"]
        delta = close.diff()

        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _detect_ranging(
        self, df: pd.DataFrame, current_price: Decimal
    ) -> tuple[bool, Optional[Decimal], Optional[Decimal]]:
        """
        Detect if market is in ranging (sideways) mode

        Returns:
            Tuple of (is_in_range, range_high, range_low)
        """
        lookback_data = df.tail(self.ranging_lookback)
        range_high = Decimal(str(lookback_data["high"].max()))
        range_low = Decimal(str(lookback_data["low"].min()))

        # Check if current price is within the range
        is_in_range = range_low <= current_price <= range_high

        return is_in_range, range_high, range_low

    def _determine_market_phase(
        self,
        price: Decimal,
        ema_fast: Decimal,
        ema_slow: Decimal,
        ema_divergence_pct: Decimal,
        is_in_range: bool,
    ) -> MarketPhase:
        """
        Determine current market phase based on Issue #124 rules:

        - Bullish: (EMA20 > EMA50) AND (price > EMA20) AND (divergence > 0.5%)
        - Bearish: (EMA20 < EMA50) AND (price < EMA20) AND (divergence > 0.5%)
        - Sideways: (EMA difference < 0.5%) AND (price in range)
        """
        # Sideways detection
        if ema_divergence_pct < self.ema_divergence_threshold and is_in_range:
            return MarketPhase.SIDEWAYS

        # Bullish trend detection
        if (
            ema_fast > ema_slow
            and price > ema_fast
            and ema_divergence_pct > self.ema_divergence_threshold
        ):
            return MarketPhase.BULLISH_TREND

        # Bearish trend detection
        if (
            ema_fast < ema_slow
            and price < ema_fast
            and ema_divergence_pct > self.ema_divergence_threshold
        ):
            return MarketPhase.BEARISH_TREND

        # If no clear phase matches
        return MarketPhase.UNKNOWN

    def _determine_trend_strength(
        self, ema_divergence_pct: Decimal, phase: MarketPhase
    ) -> TrendStrength:
        """
        Determine trend strength based on EMA divergence

        - Strong trend: divergence > 2%
        - Weak trend: 1% < divergence <= 2%
        - No trend: divergence <= 1% or sideways
        """
        if phase == MarketPhase.SIDEWAYS or phase == MarketPhase.UNKNOWN:
            return TrendStrength.NONE

        if ema_divergence_pct >= self.strong_trend_threshold:
            return TrendStrength.STRONG
        elif ema_divergence_pct >= self.weak_trend_threshold:
            return TrendStrength.WEAK
        else:
            return TrendStrength.NONE
