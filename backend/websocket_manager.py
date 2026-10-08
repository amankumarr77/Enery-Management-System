"""
WebSocket Connection Manager
Handles multiple simultaneous WebSocket clients with channel-based routing.
"""
import asyncio
import json
import logging
from typing import Dict, List, Set
from datetime import datetime
from fastapi import WebSocket

logger = logging.getLogger("emsjb.ws")


class ConnectionManager:
    """Manages WebSocket connections with channel-based pub/sub."""

    def __init__(self):
        # channel_name -> set of WebSocket connections
        self._channels: Dict[str, Set[WebSocket]] = {
            "market": set(),
            "trading": set(),
        }
        self._all_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, channel: str = "market"):
        """Accept a new WebSocket connection and add to channel."""
        await websocket.accept()
        self._all_connections.add(websocket)
        if channel not in self._channels:
            self._channels[channel] = set()
        self._channels[channel].add(websocket)
        logger.info(f"WS connected: channel={channel}, total={len(self._all_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection from all channels."""
        self._all_connections.discard(websocket)
        for channel_conns in self._channels.values():
            channel_conns.discard(websocket)
        logger.info(f"WS disconnected: total={len(self._all_connections)}")

    async def broadcast(self, channel: str, message: dict):
        """Send a message to all connections in a channel."""
        if channel not in self._channels:
            return

        dead_connections = []
        payload = json.dumps(message, default=str)

        for ws in self._channels[channel]:
            try:
                await ws.send_text(payload)
            except Exception:
                dead_connections.append(ws)

        # Clean up dead connections
        for ws in dead_connections:
            self.disconnect(ws)

    async def broadcast_all(self, message: dict):
        """Send a message to ALL connected clients."""
        dead_connections = []
        payload = json.dumps(message, default=str)

        for ws in self._all_connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead_connections.append(ws)

        for ws in dead_connections:
            self.disconnect(ws)

    async def send_price_tick(self, tick: dict):
        """Broadcast a market price tick to the market channel."""
        await self.broadcast("market", {
            "type": "price_tick",
            "data": tick,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def send_order_update(self, order: dict):
        """Broadcast an order status update to the trading channel."""
        await self.broadcast("trading", {
            "type": "order_update",
            "data": order,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def send_trade_fill(self, trade: dict):
        """Broadcast a trade fill notification."""
        await self.broadcast("trading", {
            "type": "trade_fill",
            "data": trade,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def send_position_update(self, position: dict):
        """Broadcast updated position/P&L data."""
        await self.broadcast("trading", {
            "type": "position_update",
            "data": position,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def send_alert(self, alert: dict):
        """Broadcast a risk/system alert."""
        await self.broadcast_all({
            "type": "alert",
            "data": alert,
            "timestamp": datetime.utcnow().isoformat(),
        })

    @property
    def connection_count(self) -> int:
        return len(self._all_connections)

    @property
    def channel_counts(self) -> Dict[str, int]:
        return {ch: len(conns) for ch, conns in self._channels.items()}


# Singleton instance
ws_manager = ConnectionManager()
