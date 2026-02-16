"""
WebSocket endpoints.
"""

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from web.backend.auth.service import decode_access_token
from web.backend.ws.manager import ConnectionManager

router = APIRouter(tags=["websocket"])

# Global connection manager (initialized in app lifespan)
manager = ConnectionManager()


@router.websocket("/ws/events")
async def ws_events(
    websocket: WebSocket,
    token: str = Query(default=""),
    bot_name: str | None = Query(default=None),
):
    """
    WebSocket endpoint for trading events.
    Authenticate via ?token=<jwt_access_token>.
    Optionally filter by ?bot_name=<name>.
    """
    # Validate JWT token
    if not token:
        await websocket.close(code=4001, reason="Token required")
        return

    payload = decode_access_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Subscribe to specific bot channel or all
    channels = None
    if bot_name:
        channels = [f"trading_events:{bot_name}"]

    await manager.connect(websocket, channels=channels)

    try:
        while True:
            # Keep connection alive, handle client messages
            data = await websocket.receive_text()
            # Client can send pong or subscribe commands
            if data == "pong":
                continue
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.websocket("/ws/bots/{bot_name}")
async def ws_bot(
    websocket: WebSocket,
    bot_name: str,
    token: str = Query(default=""),
):
    """WebSocket endpoint for a specific bot's events."""
    if not token:
        await websocket.close(code=4001, reason="Token required")
        return

    payload = decode_access_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Invalid token")
        return

    channel = f"trading_events:{bot_name}"
    await manager.connect(websocket, channels=[channel])

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
