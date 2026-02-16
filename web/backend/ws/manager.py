"""
WebSocket connection manager with per-channel fan-out.
"""

import asyncio
import json
import time
from collections import defaultdict

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from bot.utils.logger import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections with channel subscriptions."""

    def __init__(self, heartbeat_interval: float = 30.0):
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._all_connections: set[WebSocket] = set()
        self._heartbeat_interval = heartbeat_interval
        self._heartbeat_task: asyncio.Task | None = None

    async def connect(self, websocket: WebSocket, channels: list[str] | None = None):
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        self._all_connections.add(websocket)

        if channels:
            for channel in channels:
                self._connections[channel].add(websocket)

        logger.info(
            "websocket_connected",
            channels=channels or ["all"],
            total=len(self._all_connections),
        )

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        self._all_connections.discard(websocket)
        for channel_sockets in self._connections.values():
            channel_sockets.discard(websocket)

    async def broadcast(self, message: dict, channel: str | None = None):
        """Send message to all connections on a channel (or all)."""
        data = json.dumps(message, default=str)

        if channel and channel in self._connections:
            targets = self._connections[channel]
        else:
            targets = self._all_connections

        stale = []
        for ws in targets:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(data)
                else:
                    stale.append(ws)
            except Exception:
                stale.append(ws)

        for ws in stale:
            self.disconnect(ws)

    async def send_personal(self, websocket: WebSocket, message: dict):
        """Send message to a specific connection."""
        try:
            await websocket.send_json(message)
        except Exception:
            self.disconnect(websocket)

    def start_heartbeat(self):
        """Start heartbeat task."""
        if not self._heartbeat_task:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    def stop_heartbeat(self):
        """Stop heartbeat task."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

    async def _heartbeat_loop(self):
        """Send periodic pings to detect stale connections."""
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            stale = []
            for ws in list(self._all_connections):
                try:
                    if ws.client_state == WebSocketState.CONNECTED:
                        await ws.send_json({"type": "ping", "timestamp": time.time()})
                    else:
                        stale.append(ws)
                except Exception:
                    stale.append(ws)

            for ws in stale:
                self.disconnect(ws)

    @property
    def connection_count(self) -> int:
        return len(self._all_connections)
