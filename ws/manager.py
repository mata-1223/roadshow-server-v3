from __future__ import annotations
"""
WebSocket Connection Manager
"""
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections[session_id] = ws

    def disconnect(self, session_id: str) -> None:
        self._connections.pop(session_id, None)

    def get(self, session_id: str) -> WebSocket | None:
        return self._connections.get(session_id)


manager = ConnectionManager()
