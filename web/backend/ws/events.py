"""
Redis Pub/Sub → WebSocket bridge.
Subscribes to trading_events:* channels and forwards to WebSocket clients.
"""

import asyncio
import json
import time

import redis.asyncio as aioredis

from bot.utils.logger import get_logger
from web.backend.ws.manager import ConnectionManager

logger = get_logger(__name__)


class RedisBridge:
    """Bridges Redis Pub/Sub events to WebSocket connections."""

    def __init__(self, redis_url: str, manager: ConnectionManager):
        self._redis_url = redis_url
        self._manager = manager
        self._redis: aioredis.Redis | None = None
        self._pubsub: aioredis.client.PubSub | None = None
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self):
        """Start listening to Redis channels."""
        self._redis = aioredis.from_url(self._redis_url)
        self._pubsub = self._redis.pubsub()
        await self._pubsub.psubscribe("trading_events:*")
        self._running = True
        self._task = asyncio.create_task(self._listen())
        logger.info("redis_bridge_started", pattern="trading_events:*")

    async def stop(self):
        """Stop listening."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._pubsub:
            await self._pubsub.punsubscribe("trading_events:*")
            await self._pubsub.close()
        if self._redis:
            await self._redis.close()
        logger.info("redis_bridge_stopped")

    async def _listen(self):
        """Listen for Redis messages and broadcast to WebSocket clients."""
        while self._running:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message and message["type"] == "pmessage":
                    channel = message["channel"]
                    if isinstance(channel, bytes):
                        channel = channel.decode()

                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode()

                    try:
                        event_data = json.loads(data)
                    except json.JSONDecodeError:
                        event_data = {"raw": data}

                    ws_message = {
                        "type": "event",
                        "channel": channel,
                        "data": event_data,
                        "timestamp": time.time(),
                    }

                    # Broadcast to channel subscribers and global listeners
                    await self._manager.broadcast(ws_message, channel=channel)
                    await self._manager.broadcast(ws_message)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("redis_bridge_error", error=str(e))
                await asyncio.sleep(1)
