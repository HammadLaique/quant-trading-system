"""
WebSocket Handler.
Manages all connected dashboard clients and broadcasts real-time events.
"""

import json
import asyncio
from typing import Set
from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger


class ConnectionManager:
    """Manages all active WebSocket connections from the dashboard."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WS client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WS client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, data: dict):
        """Send data to all connected clients."""
        if not self.active_connections:
            return
        message = json.dumps(data, default=str)
        disconnected = set()
        for ws in self.active_connections:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.add(ws)
        for ws in disconnected:
            self.active_connections.discard(ws)

    async def send_personal(self, websocket: WebSocket, data: dict):
        """Send to a single client."""
        try:
            await websocket.send_text(json.dumps(data, default=str))
        except Exception:
            self.disconnect(websocket)


# Global connection manager
manager = ConnectionManager()


async def broadcast_tick(data: dict):
    """Broadcast a price tick to all clients."""
    await manager.broadcast(data)


async def broadcast_trade_event(data: dict):
    """Broadcast a new trade open/close event."""
    await manager.broadcast({"type": "trade_event", **data})


async def broadcast_portfolio(data: dict):
    """Broadcast portfolio state update."""
    await manager.broadcast(data)


async def websocket_endpoint(websocket: WebSocket):
    """FastAPI WebSocket endpoint handler."""
    await manager.connect(websocket)
    try:
        # Send initial portfolio snapshot
        from core.portfolio import portfolio
        await manager.send_personal(websocket, {
            "type": "init",
            **portfolio.get_stats(),
        })

        # Keep connection alive, listening for client pings
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                # Handle client messages (e.g. ping)
                if data == "ping":
                    await manager.send_personal(websocket, {"type": "pong"})
            except asyncio.TimeoutError:
                # Send keepalive
                await manager.send_personal(websocket, {"type": "ping"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WS error: {e}")
        manager.disconnect(websocket)

