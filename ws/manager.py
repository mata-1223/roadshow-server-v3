from __future__ import annotations
"""
WebSocket Connection Manager
"""
from fastapi import WebSocket


class ConnectionManager:
    """세션 id ↔ 활성 WebSocket 연결 보관."""

    def __init__(self) -> None:
        """빈 연결 맵(session_id → WebSocket)으로 초기화한다."""
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, ws: WebSocket) -> None:
        """연결을 수락한 뒤 세션에 등록한다.

        Args:
            session_id: 등록할 세션 ID.
            ws: 수락할 WebSocket 연결.
        """
        await ws.accept()
        self._connections[session_id] = ws

    def disconnect(self, session_id: str) -> None:
        """세션의 연결을 해제한다.

        Args:
            session_id: 해제할 세션 ID.
        """
        self._connections.pop(session_id, None)

    def get(self, session_id: str) -> WebSocket | None:
        """세션의 활성 연결을 조회한다.

        Args:
            session_id: 조회할 세션 ID.

        Returns:
            등록된 WebSocket 연결, 없으면 None.
        """
        return self._connections.get(session_id)


manager = ConnectionManager()
