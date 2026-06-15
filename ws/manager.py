from __future__ import annotations
"""
WebSocket Connection Manager
"""
from fastapi import WebSocket


class ConnectionManager:
    """세션 id ↔ 활성 WebSocket 연결 보관."""

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, ws: WebSocket) -> None:
        """연결 수락 후 세션에 등록."""
        await ws.accept()
        self._connections[session_id] = ws

    def disconnect(self, session_id: str) -> None:
        """세션 연결 해제."""
        self._connections.pop(session_id, None)

    def get(self, session_id: str) -> WebSocket | None:
        """세션의 활성 연결 조회 (없으면 None)."""
        return self._connections.get(session_id)


manager = ConnectionManager()
