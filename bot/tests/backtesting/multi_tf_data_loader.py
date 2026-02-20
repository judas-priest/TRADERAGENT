"""
Multi-timeframe data loader for backtesting.

Generates or loads synchronized OHLCV data across D1, H4, H1, M15
timeframes. Data is generated at M15 resolution first, then aggregated
upward using pandas resample to ensure perfect timestamp alignment.

Usage:
    loader = MultiTimeframeDataLoader()
    data = loader.load("BTC/USDT", start, end, trend="up")
    df_d1, df_h4, df_h1, df_m15 = loader.get_context_at(data, m15_index=200, lookback=50)
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import pandas as pd

from bot.tests.backtesting.test_data import HistoricalDataProvider


@dataclass
class MultiTimeframeData:
    """Container for synchronized multi-timeframe OHLCV DataFrames."""

    d1: pd.DataFrame
    h4: pd.DataFrame
    h1: pd.DataFrame
    m15: pd.DataFrame

    def as_tuple(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Return (d1, h4, h1, m15) tuple for unpacking."""
        return (self.d1, self.h4, self.h1, self.m15)


class MultiTimeframeDataLoader:
    """
    Loads/generates synchronized OHLCV data across D1, H4, H1, M15.

    Data is generated at M15 resolution first, then aggregated upward
    to ensure perfect alignment. Every M15 candle has a corresponding
    parent candle in H1, H4, and D1.
    """

    def __init__(self, provider: HistoricalDataProvider | None = None) -> None:
        self._provider = provider or HistoricalDataProvider()

    def load(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        trend: str = "up",
        base_price: Decimal = Decimal("45000"),
    ) -> MultiTimeframeData:
        """
        Generate synchronized multi-TF data.

        1. Generate M15 candles using HistoricalDataProvider.
        2. Convert to DataFrame with DatetimeIndex.
        3. Resample/aggregate into H1, H4, D1.

        Args:
            symbol: Trading pair (e.g. "BTC/USDT").
            start_date: Start datetime.
            end_date: End datetime.
            trend: "up", "down", or "sideways".
            base_price: Starting price for synthetic data.

        Returns:
            MultiTimeframeData with all four aligned DataFrames.
        """
        # Generate M15 candles
        candles = self._provider.generate_trending_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval="15m",
            trend=trend,
            base_price=base_price,
        )

        # Convert to DataFrame with DatetimeIndex
        df_m15 = self._candles_to_dataframe(candles)

        # Resample to higher timeframes
        df_h1 = self._resample(df_m15, "1h")
        df_h4 = self._resample(df_m15, "4h")
        df_d1 = self._resample(df_m15, "1D")

        return MultiTimeframeData(d1=df_d1, h4=df_h4, h1=df_h1, m15=df_m15)

    def _candles_to_dataframe(self, candles: list[dict]) -> pd.DataFrame:
        """Convert list-of-dicts candles to OHLCV DataFrame with DatetimeIndex."""
        df = pd.DataFrame(candles)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp")
        df = df.sort_index()
        return df[["open", "high", "low", "close", "volume"]]

    def _resample(self, df_m15: pd.DataFrame, rule: str) -> pd.DataFrame:
        """
        Resample M15 data to a higher timeframe.

        Uses standard OHLCV aggregation:
          open: first, high: max, low: min, close: last, volume: sum

        Args:
            df_m15: M15 DataFrame with DatetimeIndex.
            rule: Pandas resample rule ('1h', '4h', '1D').

        Returns:
            Resampled DataFrame.
        """
        resampled = (
            df_m15.resample(rule)
            .agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
            .dropna()
        )
        return resampled

    def get_context_at(
        self,
        data: MultiTimeframeData,
        m15_index: int,
        lookback: int = 100,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Get rolling context DataFrames at a specific M15 bar index.

        For each timeframe, returns the last `lookback` completed candles
        as of the M15 timestamp.

        Args:
            data: Full MultiTimeframeData.
            m15_index: Current position in M15 DataFrame (0-based).
            lookback: Number of historical bars to include per TF.

        Returns:
            (df_d1, df_h4, df_h1, df_m15) tuple of rolling windows.
        """
        current_ts = data.m15.index[m15_index]

        # M15: simple slice
        start = max(0, m15_index - lookback + 1)
        df_m15 = data.m15.iloc[start : m15_index + 1]

        # Higher TFs: all candles with timestamp <= current M15 timestamp
        df_h1 = data.h1[data.h1.index <= current_ts].tail(lookback)
        df_h4 = data.h4[data.h4.index <= current_ts].tail(lookback)
        df_d1 = data.d1[data.d1.index <= current_ts].tail(lookback)

        return (df_d1, df_h4, df_h1, df_m15)
