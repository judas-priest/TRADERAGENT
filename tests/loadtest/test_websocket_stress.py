"""
WebSocket stress testing — ConnectionManager fan-out under load.

Tests the ConnectionManager directly with mock WebSocket objects.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

from starlette.websockets import WebSocketState

from web.backend.ws.manager import ConnectionManager


def _make_mock_ws(connected: bool = True):
    """Create a mock WebSocket object."""
    ws = MagicMock()
    ws.client_state = WebSocketState.CONNECTED if connected else WebSocketState.DISCONNECTED
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


class TestWebSocketFanOut:
    """Test WebSocket ConnectionManager under stress."""

    async def test_broadcast_100_connections(self):
        """Fan-out broadcast to 100 connections."""
        manager = ConnectionManager(heartbeat_interval=9999)
        sockets = [_make_mock_ws() for _ in range(100)]

        for ws in sockets:
            await manager.connect(ws)

        start = time.perf_counter()
        await manager.broadcast({"type": "test", "data": "hello"})
        elapsed = time.perf_counter() - start

        for ws in sockets:
            ws.send_text.assert_called_once()

        assert elapsed < 1.0, f"Broadcast to 100 took {elapsed:.2f}s"
        assert manager.connection_count == 100
        print(f"\n  Broadcast 100: {elapsed*1000:.1f}ms")

    async def test_broadcast_500_connections(self):
        """Fan-out broadcast to 500 connections."""
        manager = ConnectionManager(heartbeat_interval=9999)
        sockets = [_make_mock_ws() for _ in range(500)]

        for ws in sockets:
            await manager.connect(ws)

        start = time.perf_counter()
        await manager.broadcast({"type": "test", "data": "hello"})
        elapsed = time.perf_counter() - start

        for ws in sockets:
            ws.send_text.assert_called_once()

        assert elapsed < 3.0, f"Broadcast to 500 took {elapsed:.2f}s"
        assert manager.connection_count == 500
        print(f"\n  Broadcast 500: {elapsed*1000:.1f}ms")

    async def test_channel_fanout_100_channels(self):
        """100 channels × 5 subscribers each — verify correct routing."""
        manager = ConnectionManager(heartbeat_interval=9999)
        channel_sockets: dict[str, list] = {}

        for ch in range(100):
            channel_name = f"channel_{ch}"
            sockets = [_make_mock_ws() for _ in range(5)]
            channel_sockets[channel_name] = sockets
            for ws in sockets:
                await manager.connect(ws, channels=[channel_name])

        assert manager.connection_count == 500

        start = time.perf_counter()
        # Broadcast to a specific channel
        target_channel = "channel_42"
        await manager.broadcast({"type": "test"}, channel=target_channel)
        elapsed = time.perf_counter() - start

        # Only channel_42 subscribers should receive
        for ws in channel_sockets[target_channel]:
            ws.send_text.assert_called_once()

        # Other channels should NOT receive
        for ch_name, sockets in channel_sockets.items():
            if ch_name != target_channel:
                for ws in sockets:
                    ws.send_text.assert_not_called()

        assert elapsed < 2.0, f"Channel fanout took {elapsed:.2f}s"
        print(f"\n  Channel fanout (100ch×5sub): {elapsed*1000:.1f}ms")

    async def test_stale_cleanup_under_load(self):
        """200 connections, 50 go stale — broadcast cleans up stale."""
        manager = ConnectionManager(heartbeat_interval=9999)
        good_sockets = [_make_mock_ws() for _ in range(150)]
        stale_sockets = [_make_mock_ws() for _ in range(50)]

        # Stale sockets raise on send
        for ws in stale_sockets:
            ws.send_text = AsyncMock(side_effect=RuntimeError("connection lost"))

        for ws in good_sockets + stale_sockets:
            await manager.connect(ws)

        assert manager.connection_count == 200

        start = time.perf_counter()
        await manager.broadcast({"type": "cleanup_test"})
        elapsed = time.perf_counter() - start

        # Good sockets received the message
        for ws in good_sockets:
            ws.send_text.assert_called_once()

        # Stale sockets should be cleaned up
        assert manager.connection_count == 150
        assert elapsed < 2.0, f"Stale cleanup took {elapsed:.2f}s"
        print(f"\n  Stale cleanup (200→150): {elapsed*1000:.1f}ms")

    async def test_concurrent_connect_disconnect(self):
        """100 concurrent connect/disconnect cycles."""
        manager = ConnectionManager(heartbeat_interval=9999)

        async def connect_disconnect(i: int):
            ws = _make_mock_ws()
            await manager.connect(ws, channels=[f"ch_{i}"])
            manager.disconnect(ws)

        start = time.perf_counter()
        await asyncio.gather(*[connect_disconnect(i) for i in range(100)])
        elapsed = time.perf_counter() - start

        # All disconnected — should be empty
        assert manager.connection_count == 0
        assert elapsed < 2.0, f"100 connect/disconnect took {elapsed:.2f}s"
        print(f"\n  100 connect/disconnect cycles: {elapsed*1000:.1f}ms")
