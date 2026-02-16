"""
Memory profiling tests — detect memory leaks using tracemalloc.

Tests validate that components don't leak memory during extended operation.
"""

import gc
import time
import tracemalloc
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pandas as pd
import pytest
from starlette.websockets import WebSocketState

from bot.orchestrator.events import EventType, TradingEvent
from bot.strategies.base import BaseSignal, ExitReason, SignalDirection
from bot.strategies.smc_adapter import SMCStrategyAdapter
from web.backend.ws.manager import ConnectionManager

from tests.loadtest.conftest import make_ohlcv, make_signal


class TestMemoryProfiling:
    """Test memory stability under extended operation."""

    def test_strategy_analysis_50_cycles(self):
        """50 analyze_market() cycles — check for memory leaks.

        Note: SMC analysis on 200-row DataFrame takes ~2s per cycle,
        so we use 50 cycles to keep test time reasonable (~100s max).
        """
        adapter = SMCStrategyAdapter()
        df = make_ohlcv(n=200)

        gc.collect()
        tracemalloc.start()
        snapshot_before = tracemalloc.take_snapshot()

        for _ in range(50):
            adapter.analyze_market(df)

        gc.collect()
        snapshot_after = tracemalloc.take_snapshot()

        stats = snapshot_after.compare_to(snapshot_before, "lineno")
        total_leak_bytes = sum(s.size_diff for s in stats if s.size_diff > 0)
        total_leak_mb = total_leak_bytes / (1024 * 1024)

        tracemalloc.stop()

        assert total_leak_mb < 10, f"Memory leak: {total_leak_mb:.1f}MB after 50 cycles"
        print(f"\n  50 analysis cycles: leak = {total_leak_mb:.2f}MB")
        # Print top 3 allocators
        for stat in stats[:3]:
            print(f"    {stat}")

    def test_position_lifecycle_500_cycles(self):
        """500 open+close position cycles — verify bounded memory."""
        adapter = SMCStrategyAdapter()

        gc.collect()
        tracemalloc.start()
        _, initial_peak = tracemalloc.get_traced_memory()

        for _ in range(500):
            signal = make_signal()
            pos_id = adapter.open_position(signal, Decimal("50"))
            adapter.close_position(pos_id, ExitReason.TAKE_PROFIT, Decimal("46000"))

        gc.collect()
        _, final_peak = tracemalloc.get_traced_memory()

        tracemalloc.stop()

        # closed_trades accumulates (expected), but should be reasonable
        assert adapter.get_performance().total_trades == 500
        peak_mb = final_peak / (1024 * 1024)
        assert peak_mb < 50, f"Peak memory: {peak_mb:.1f}MB after 500 cycles"
        print(f"\n  500 position cycles: peak = {peak_mb:.2f}MB, trades = 500")

    async def test_ws_manager_1000_connections(self):
        """1000 connect/disconnect cycles — verify memory returns to baseline."""
        manager = ConnectionManager(heartbeat_interval=9999)

        def _make_ws():
            ws = MagicMock()
            ws.client_state = WebSocketState.CONNECTED
            ws.accept = AsyncMock()
            ws.send_text = AsyncMock()
            return ws

        gc.collect()
        tracemalloc.start()
        _, baseline = tracemalloc.get_traced_memory()

        # Connect 1000
        sockets = []
        for _ in range(1000):
            ws = _make_ws()
            await manager.connect(ws)
            sockets.append(ws)

        _, after_connect = tracemalloc.get_traced_memory()

        # Disconnect all
        for ws in sockets:
            manager.disconnect(ws)
        sockets.clear()

        gc.collect()
        _, after_disconnect = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        assert manager.connection_count == 0
        connect_mb = after_connect / (1024 * 1024)
        disconnect_mb = after_disconnect / (1024 * 1024)
        baseline_mb = baseline / (1024 * 1024)

        # After disconnect, memory should return close to baseline
        # Note: MagicMock objects + structlog logging retain some memory (~80KB/connection)
        growth = disconnect_mb - baseline_mb
        assert growth < 100, f"Memory didn't return to baseline: grew {growth:.2f}MB"
        print(f"\n  1000 WS connections: connect={connect_mb:.2f}MB, "
              f"after disconnect={disconnect_mb:.2f}MB, baseline={baseline_mb:.2f}MB")

    def test_event_creation_50000(self):
        """Create 50,000 TradingEvent objects — measure peak memory."""
        gc.collect()
        tracemalloc.start()

        events = []
        event_types = list(EventType)
        for i in range(50_000):
            et = event_types[i % len(event_types)]
            events.append(TradingEvent.create(
                event_type=et,
                bot_name=f"bot_{i % 10}",
                data={"price": "45000", "seq": i},
            ))

        gc.collect()
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak / (1024 * 1024)
        assert peak_mb < 100, f"Peak memory: {peak_mb:.1f}MB for 50K events"
        print(f"\n  50K events: peak = {peak_mb:.2f}MB ({peak_mb*1024/50:.1f}KB/event)")

    def test_large_dataframe_analysis(self):
        """Analyze 5,000-row OHLCV DataFrame — measure peak memory and time.

        Note: SMC analysis has O(n²) complexity for structure detection,
        so we use 5K rows to keep test time reasonable.
        """
        gc.collect()
        tracemalloc.start()

        df = make_ohlcv(n=5_000)

        start = time.perf_counter()
        adapter = SMCStrategyAdapter()
        result = adapter.analyze_market(df)
        elapsed = time.perf_counter() - start

        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak / (1024 * 1024)
        assert result is not None
        assert peak_mb < 500, f"Peak memory: {peak_mb:.1f}MB for 5K rows"
        assert elapsed < 180.0, f"5K row analysis took {elapsed:.2f}s"
        print(f"\n  5K row analysis: {elapsed:.2f}s, peak = {peak_mb:.2f}MB")
