"""
Walk-Forward Analysis — Rolling train/test window validation.

Splits multi-timeframe data into successive train/test windows,
runs a strategy on each, and aggregates out-of-sample results
to assess robustness.

Usage:
    wf = WalkForwardAnalysis(config=WalkForwardConfig(n_splits=5))
    result = await wf.run(strategy, data)
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

import pandas as pd

from bot.strategies.base import BaseStrategy
from bot.tests.backtesting.backtesting_engine import BacktestResult
from bot.tests.backtesting.multi_tf_data_loader import (
    MultiTimeframeData,
    MultiTimeframeDataLoader,
)
from bot.tests.backtesting.multi_tf_engine import (
    MultiTFBacktestConfig,
    MultiTimeframeBacktestEngine,
)


@dataclass
class WalkForwardConfig:
    """Configuration for walk-forward analysis."""

    n_splits: int = 5
    train_pct: float = 0.7
    backtest_config: MultiTFBacktestConfig = field(
        default_factory=MultiTFBacktestConfig
    )


@dataclass
class WalkForwardWindow:
    """Results for a single walk-forward window."""

    window_index: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    train_result: BacktestResult
    test_result: BacktestResult


@dataclass
class WalkForwardResult:
    """Aggregated walk-forward analysis results."""

    windows: list[WalkForwardWindow]
    aggregate_test_return_pct: Decimal
    aggregate_test_sharpe: Decimal | None
    consistency_ratio: float
    avg_test_win_rate: Decimal
    avg_test_drawdown_pct: Decimal

    def is_robust(self, min_consistency: float = 0.5) -> bool:
        """Strategy is considered robust if consistency ratio >= threshold."""
        return self.consistency_ratio >= min_consistency


class WalkForwardAnalysis:
    """
    Walk-forward analysis: split data into rolling train/test windows,
    run strategy on each, measure out-of-sample performance.
    """

    def __init__(self, config: WalkForwardConfig | None = None) -> None:
        self.config = config or WalkForwardConfig()

    async def run(
        self,
        strategy: BaseStrategy,
        data: MultiTimeframeData,
    ) -> WalkForwardResult:
        """
        Run walk-forward analysis.

        Splits M15 data into n_splits windows. For each window:
        - Train on first train_pct of the window.
        - Test on remaining (1-train_pct).
        - Record both train and test results.

        Args:
            strategy: BaseStrategy to evaluate.
            data: Full MultiTimeframeData.

        Returns:
            WalkForwardResult with per-window and aggregate metrics.
        """
        windows = self._split_windows(data)
        loader = MultiTimeframeDataLoader()
        results: list[WalkForwardWindow] = []

        for i, (train_slice, test_slice) in enumerate(windows):
            # Build MultiTimeframeData for each slice
            train_data = self._build_slice_data(data, train_slice)
            test_data = self._build_slice_data(data, test_slice)

            engine = MultiTimeframeBacktestEngine(config=self.config.backtest_config)

            # Run on train window
            train_result = await engine.run(strategy, train_data)
            # Run on test window
            test_result = await engine.run(strategy, test_data)

            ts = data.m15.index
            results.append(WalkForwardWindow(
                window_index=i,
                train_start=ts[train_slice.start].to_pydatetime(),
                train_end=ts[train_slice.stop - 1].to_pydatetime(),
                test_start=ts[test_slice.start].to_pydatetime(),
                test_end=ts[test_slice.stop - 1].to_pydatetime(),
                train_result=train_result,
                test_result=test_result,
            ))

        return self._aggregate(results)

    def _split_windows(
        self, data: MultiTimeframeData
    ) -> list[tuple[slice, slice]]:
        """Split M15 index range into n_splits train/test pairs."""
        total = len(data.m15)
        warmup = self.config.backtest_config.warmup_bars
        n = self.config.n_splits

        # Usable range after warmup
        usable = total - warmup
        window_size = usable // n

        windows = []
        for i in range(n):
            start = warmup + i * window_size
            end = start + window_size if i < n - 1 else total

            # Split window into train/test
            train_size = int((end - start) * self.config.train_pct)
            train_slice = slice(start, start + train_size)
            test_slice = slice(start + train_size, end)

            # Ensure minimum sizes
            if (train_slice.stop - train_slice.start) > warmup and \
               (test_slice.stop - test_slice.start) > warmup:
                windows.append((train_slice, test_slice))

        return windows

    def _build_slice_data(
        self, data: MultiTimeframeData, s: slice
    ) -> MultiTimeframeData:
        """
        Build a MultiTimeframeData for a sub-range of M15 indices.

        Higher timeframes are filtered to match the M15 time range.
        """
        m15 = data.m15.iloc[s.start : s.stop]
        if m15.empty:
            return MultiTimeframeData(
                d1=pd.DataFrame(),
                h4=pd.DataFrame(),
                h1=pd.DataFrame(),
                m15=m15,
            )

        start_ts = m15.index[0]
        end_ts = m15.index[-1]

        d1 = data.d1[(data.d1.index >= start_ts) & (data.d1.index <= end_ts)]
        h4 = data.h4[(data.h4.index >= start_ts) & (data.h4.index <= end_ts)]
        h1 = data.h1[(data.h1.index >= start_ts) & (data.h1.index <= end_ts)]

        return MultiTimeframeData(d1=d1, h4=h4, h1=h1, m15=m15)

    def _aggregate(
        self, windows: list[WalkForwardWindow]
    ) -> WalkForwardResult:
        """Aggregate walk-forward window results."""
        if not windows:
            return WalkForwardResult(
                windows=[],
                aggregate_test_return_pct=Decimal("0"),
                aggregate_test_sharpe=None,
                consistency_ratio=0.0,
                avg_test_win_rate=Decimal("0"),
                avg_test_drawdown_pct=Decimal("0"),
            )

        n = len(windows)

        # Aggregate test returns (compounding)
        compound = Decimal("1")
        positive_windows = 0
        win_rates = []
        drawdowns = []
        sharpes = []

        for w in windows:
            ret_pct = w.test_result.total_return_pct / Decimal("100")
            compound *= (Decimal("1") + ret_pct)

            if w.test_result.total_return_pct > 0:
                positive_windows += 1

            win_rates.append(w.test_result.win_rate)
            drawdowns.append(w.test_result.max_drawdown_pct)
            if w.test_result.sharpe_ratio is not None:
                sharpes.append(w.test_result.sharpe_ratio)

        total_return_pct = (compound - Decimal("1")) * Decimal("100")
        consistency = positive_windows / n if n > 0 else 0.0
        avg_win_rate = sum(win_rates) / n if n > 0 else Decimal("0")
        avg_drawdown = sum(drawdowns) / n if n > 0 else Decimal("0")
        avg_sharpe = (
            sum(sharpes) / len(sharpes) if sharpes else None
        )

        return WalkForwardResult(
            windows=windows,
            aggregate_test_return_pct=total_return_pct,
            aggregate_test_sharpe=avg_sharpe,
            consistency_ratio=consistency,
            avg_test_win_rate=avg_win_rate,
            avg_test_drawdown_pct=avg_drawdown,
        )
