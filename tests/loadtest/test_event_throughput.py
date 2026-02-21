"""
Event system throughput testing — TradingEvent creation/serialization + broadcast.

Tests validate event pipeline performance under high volume.
"""

import time
from unittest.mock import AsyncMock, MagicMock

from starlette.websockets import WebSocketState

from bot.orchestrator.events import EventType, TradingEvent
from web.backend.ws.manager import ConnectionManager


def _make_mock_ws():
    """Create a mock WebSocket for broadcast tests."""
    ws = MagicMock()
    ws.client_state = WebSocketState.CONNECTED
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


class TestEventThroughput:
    """Test event creation, serialization, and broadcast throughput."""

    def test_event_creation_10000(self):
        """Create and serialize 10,000 TradingEvent objects."""
        event_types = list(EventType)
        n = 10_000

        start = time.perf_counter()
        events = []
        for i in range(n):
            et = event_types[i % len(event_types)]
            event = TradingEvent.create(
                event_type=et,
                bot_name=f"bot_{i % 10}",
                data={"price": "45000.50", "amount": "0.001", "index": i},
            )
            events.append(event.to_json())
        elapsed = time.perf_counter() - start

        throughput = n / elapsed
        assert elapsed < 2.0, f"10K event create+serialize took {elapsed:.2f}s"
        assert throughput > 5000, f"Throughput: {throughput:.0f} events/s (need >5000)"
        print(f"\n  10K event create+serialize: {elapsed:.2f}s ({throughput:.0f}/s)")

    def test_event_deserialization_10000(self):
        """Deserialize 10,000 TradingEvent JSON strings."""
        # Pre-create JSON strings
        event_types = list(EventType)
        json_strings = []
        for i in range(10_000):
            et = event_types[i % len(event_types)]
            event = TradingEvent.create(
                event_type=et,
                bot_name=f"bot_{i % 10}",
                data={"price": "45000", "index": i},
            )
            json_strings.append(event.to_json())

        start = time.perf_counter()
        events = []
        for js in json_strings:
            events.append(TradingEvent.from_json(js))
        elapsed = time.perf_counter() - start

        assert len(events) == 10_000
        assert elapsed < 2.0, f"10K deserialization took {elapsed:.2f}s"
        print(f"\n  10K event deserialization: {elapsed:.2f}s ({10_000/elapsed:.0f}/s)")

    async def test_broadcast_100_sub_1000_msg(self):
        """100 WebSocket subscribers × 1000 messages broadcast."""
        manager = ConnectionManager(heartbeat_interval=9999)
        sockets = [_make_mock_ws() for _ in range(100)]
        for ws in sockets:
            await manager.connect(ws)

        start = time.perf_counter()
        for i in range(1000):
            await manager.broadcast({"type": "event", "seq": i})
        elapsed = time.perf_counter() - start

        # Each socket should have received 1000 messages
        for ws in sockets:
            assert ws.send_text.call_count == 1000

        total_sends = 100 * 1000
        assert elapsed < 10.0, f"100×1000 broadcast took {elapsed:.2f}s"
        print(
            f"\n  100 sub × 1000 msg ({total_sends:,} sends): {elapsed:.2f}s ({total_sends/elapsed:,.0f} sends/s)"
        )

    async def test_channel_broadcast_50ch_100msg(self):
        """50 channels × 10 subscribers × 100 messages — correct routing."""
        manager = ConnectionManager(heartbeat_interval=9999)
        channel_sockets: dict[str, list] = {}

        for ch in range(50):
            ch_name = f"ch_{ch}"
            sockets = [_make_mock_ws() for _ in range(10)]
            channel_sockets[ch_name] = sockets
            for ws in sockets:
                await manager.connect(ws, channels=[ch_name])

        start = time.perf_counter()
        for ch in range(50):
            ch_name = f"ch_{ch}"
            for msg_i in range(100):
                await manager.broadcast({"type": "event", "ch": ch, "seq": msg_i}, channel=ch_name)
        elapsed = time.perf_counter() - start

        # Each socket in each channel should receive exactly 100 messages
        for ch_name, sockets in channel_sockets.items():
            for ws in sockets:
                assert (
                    ws.send_text.call_count == 100
                ), f"{ch_name}: expected 100 calls, got {ws.send_text.call_count}"

        total_sends = 50 * 10 * 100  # 50,000
        assert elapsed < 10.0, f"50ch×100msg broadcast took {elapsed:.2f}s"
        print(
            f"\n  50 ch × 10 sub × 100 msg ({total_sends:,} sends): {elapsed:.2f}s ({total_sends/elapsed:,.0f} sends/s)"
        )
