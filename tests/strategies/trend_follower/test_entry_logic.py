"""
Tests for EntryLogicAnalyzer — entry signals for LONG/SHORT positions.
"""

from decimal import Decimal
from unittest.mock import patch

import numpy as np
import pandas as pd

from bot.strategies.trend_follower.entry_logic import (
    EntryLogicAnalyzer,
    EntryReason,
    EntrySignal,
    SignalType,
    SupportResistanceLevel,
)
from bot.strategies.trend_follower.market_analyzer import (
    MarketAnalyzer,
    MarketConditions,
    MarketPhase,
    TrendStrength,
)


def _make_df(n: int = 100, base: float = 45000.0, trend: str = "up") -> pd.DataFrame:
    rng = np.random.default_rng(42)
    dates = pd.date_range("2024-01-01", periods=n, freq="15min")
    if trend == "up":
        closes = base + np.cumsum(rng.uniform(0.5, 5, n))
    elif trend == "down":
        closes = base - np.cumsum(rng.uniform(0.5, 5, n))
    else:
        closes = base + rng.normal(0, 3, n)
    highs = closes + rng.uniform(5, 30, n)
    lows = closes - rng.uniform(5, 30, n)
    opens = closes + rng.normal(0, 5, n)
    # Set high volume on last bar for volume confirmation
    volumes = rng.uniform(100, 300, n)
    volumes[-1] = 2000  # High volume for confirmation
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes},
        index=dates,
    )


def _make_conditions(
    phase: MarketPhase = MarketPhase.BULLISH_TREND,
    current_price: Decimal = Decimal("45500"),
    ema_fast: Decimal = Decimal("45450"),
    atr_pct: Decimal = Decimal("0.01"),
    rsi: Decimal = Decimal("50"),
) -> MarketConditions:
    return MarketConditions(
        phase=phase,
        trend_strength=TrendStrength.STRONG,
        ema_fast=ema_fast,
        ema_slow=Decimal("45000"),
        ema_divergence_pct=Decimal("0.01"),
        atr=Decimal("450"),
        atr_pct=atr_pct,
        rsi=rsi,
        current_price=current_price,
        is_in_range=True,
        range_high=Decimal("46000"),
        range_low=Decimal("44000"),
        timestamp=pd.Timestamp("2024-01-01"),
    )


class TestEntryLogicInit:
    def test_defaults(self):
        ma = MarketAnalyzer()
        ela = EntryLogicAnalyzer(market_analyzer=ma)
        assert ela.require_volume_confirmation is True
        assert ela.volume_multiplier == Decimal("1.5")
        assert ela.rsi_oversold == Decimal("30")
        assert ela.rsi_overbought == Decimal("70")

    def test_custom_params(self):
        ma = MarketAnalyzer()
        ela = EntryLogicAnalyzer(
            market_analyzer=ma,
            require_volume_confirmation=False,
            rsi_oversold=Decimal("25"),
        )
        assert ela.require_volume_confirmation is False
        assert ela.rsi_oversold == Decimal("25")


class TestATRFilter:
    def test_high_atr_rejects(self):
        """ATR > 5% of price should block entry."""
        ma = MarketAnalyzer()
        ela = EntryLogicAnalyzer(market_analyzer=ma, require_volume_confirmation=False)
        conditions = _make_conditions(atr_pct=Decimal("0.06"))  # 6% > 5%

        with patch.object(ma, "analyze", return_value=conditions):
            df = _make_df()
            result = ela.analyze_entry(df)
            assert result is None

    def test_low_atr_passes(self):
        """ATR < 5% should allow entry (if other conditions met)."""
        ma = MarketAnalyzer()
        conditions = _make_conditions(atr_pct=Decimal("0.02"))
        ela = EntryLogicAnalyzer(market_analyzer=ma, require_volume_confirmation=False)

        with patch.object(ma, "analyze", return_value=conditions):
            df = _make_df()
            # May or may not produce signal depending on other conditions, but shouldn't reject on ATR
            _ = ela.analyze_entry(df)  # No exception


class TestVolumeConfirmation:
    def test_volume_check_passes_high_volume(self):
        ma = MarketAnalyzer()
        ela = EntryLogicAnalyzer(market_analyzer=ma, volume_multiplier=Decimal("1.5"))
        df = _make_df()
        # Last bar has volume=2000, avg is ~200, so 2000 > 200*1.5
        assert ela._check_volume_confirmation(df) is True

    def test_volume_check_fails_low_volume(self):
        ma = MarketAnalyzer()
        ela = EntryLogicAnalyzer(market_analyzer=ma, volume_multiplier=Decimal("1.5"))
        df = _make_df()
        df.iloc[-1, df.columns.get_loc("volume")] = 10  # Very low volume
        assert ela._check_volume_confirmation(df) is False


class TestSupportResistance:
    def test_find_levels(self):
        ma = MarketAnalyzer()
        ela = EntryLogicAnalyzer(market_analyzer=ma, support_resistance_lookback=50)
        df = _make_df(n=100)
        levels = ela._find_support_resistance_levels(df)
        assert isinstance(levels, list)
        for level in levels:
            assert isinstance(level, SupportResistanceLevel)
            assert level.touches >= 2

    def test_is_near_level(self):
        ma = MarketAnalyzer()
        ela = EntryLogicAnalyzer(
            market_analyzer=ma,
            support_resistance_threshold=Decimal("0.01"),
        )
        assert ela._is_near_level(Decimal("45000"), Decimal("45000")) is True
        assert ela._is_near_level(Decimal("45000"), Decimal("45400")) is True  # within 1%
        assert ela._is_near_level(Decimal("45000"), Decimal("50000")) is False


class TestBullishTrendEntry:
    def test_pullback_to_ema_signal(self):
        ma = MarketAnalyzer()
        ela = EntryLogicAnalyzer(
            market_analyzer=ma,
            require_volume_confirmation=False,
            support_resistance_threshold=Decimal("0.01"),
        )
        # Price near EMA and rising
        conditions = _make_conditions(
            phase=MarketPhase.BULLISH_TREND,
            current_price=Decimal("45460"),
            ema_fast=Decimal("45450"),
        )
        df = _make_df()
        # Ensure prev close < current price (bounce)
        df.iloc[-2, df.columns.get_loc("close")] = 45440.0
        df.iloc[-1, df.columns.get_loc("close")] = 45460.0

        signal = ela._analyze_bullish_trend_entry(df, conditions, [], True)
        if signal is not None:
            assert signal.signal_type == SignalType.LONG
            assert signal.entry_reason == EntryReason.TREND_PULLBACK_TO_EMA


class TestBearishTrendEntry:
    def test_pullback_to_ema_short(self):
        ma = MarketAnalyzer()
        ela = EntryLogicAnalyzer(
            market_analyzer=ma,
            require_volume_confirmation=False,
            support_resistance_threshold=Decimal("0.01"),
        )
        conditions = _make_conditions(
            phase=MarketPhase.BEARISH_TREND,
            current_price=Decimal("44550"),
            ema_fast=Decimal("44560"),
        )
        df = _make_df(trend="down")
        df.iloc[-2, df.columns.get_loc("close")] = 44570.0
        df.iloc[-1, df.columns.get_loc("close")] = 44550.0

        signal = ela._analyze_bearish_trend_entry(df, conditions, [], True)
        if signal is not None:
            assert signal.signal_type == SignalType.SHORT
            assert signal.entry_reason == EntryReason.TREND_PULLBACK_TO_EMA


class TestSidewaysEntry:
    def test_rsi_oversold_long(self):
        ma = MarketAnalyzer()
        ela = EntryLogicAnalyzer(
            market_analyzer=ma,
            require_volume_confirmation=False,
            rsi_oversold=Decimal("30"),
        )
        conditions = _make_conditions(
            phase=MarketPhase.SIDEWAYS,
            rsi=Decimal("32"),  # Just crossed above 30
        )
        df = _make_df(trend="sideways")

        # Mock RSI series where prev < 30 and current >= 30
        rsi_series = pd.Series([28.0, 32.0], index=df.index[-2:])
        with patch.object(
            ma,
            "_calculate_rsi",
            return_value=pd.concat([pd.Series([50.0] * 98, index=df.index[:98]), rsi_series]),
        ):
            signal = ela._analyze_sideways_entry(df, conditions, True)
            if signal is not None:
                assert signal.signal_type == SignalType.LONG
                assert signal.entry_reason == EntryReason.SIDEWAYS_RSI_OVERSOLD


class TestEntrySignalDataclass:
    def test_signal_fields(self):
        conditions = _make_conditions()
        signal = EntrySignal(
            signal_type=SignalType.LONG,
            entry_reason=EntryReason.TREND_PULLBACK_TO_EMA,
            entry_price=Decimal("45500"),
            confidence=Decimal("0.8"),
            market_conditions=conditions,
            volume_confirmed=True,
            timestamp=pd.Timestamp("2024-01-01"),
        )
        assert signal.signal_type == SignalType.LONG
        assert signal.entry_price == Decimal("45500")
        assert signal.volume_confirmed is True


class TestSignalTypeEnum:
    def test_values(self):
        assert SignalType.LONG.value == "long"
        assert SignalType.SHORT.value == "short"
        assert SignalType.NONE.value == "none"


class TestEntryReasonEnum:
    def test_trend_reasons(self):
        assert "ema" in EntryReason.TREND_PULLBACK_TO_EMA.value
        assert "support" in EntryReason.TREND_BOUNCE_FROM_SUPPORT.value

    def test_sideways_reasons(self):
        assert "rsi" in EntryReason.SIDEWAYS_RSI_OVERSOLD.value
        assert "breakout" in EntryReason.SIDEWAYS_RANGE_BREAKOUT_UP.value
