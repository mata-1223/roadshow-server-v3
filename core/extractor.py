from __future__ import annotations
"""
Behavioral 이벤트 공유 저장소 (시나리오 무관).

세션별 행동 이벤트를 누적하고 5분 window로 조회한다.
Pattern Feature 산출(시나리오별 집계)은 각 엔진(cs/bundle/worker)이 담당.
"""
from datetime import datetime, timedelta
from typing import Any


def _now() -> datetime:
    """현재 UTC 시각 (이벤트 타임스탬프·window 컷오프 기준)."""
    return datetime.utcnow()


class BehavioralPatternExtractor:
    """
    세션별 이벤트를 누적하고 패턴 피처를 산출.

    시연 시: WebSocket 세션 단위로 인스턴스 보존, 매 행동마다 add_event() 호출
    """

    def __init__(self) -> None:
        self._events_by_session: dict[str, list[dict[str, Any]]] = {}

    def add_event(
        self,
        session_id: str,
        event_type: str,
        entity: str,
        occurred_at: datetime | None = None,
    ) -> None:
        """세션에 행동 이벤트 1건 누적 (occurred_at 미지정 시 현재 UTC)."""
        ts = occurred_at or _now()
        self._events_by_session.setdefault(session_id, []).append({
            "event_type":  event_type,
            "entity":      entity,
            "occurred_at": ts,
        })

    def events_within(
        self,
        session_id: str,
        window_seconds: int = 300,
    ) -> list[dict[str, Any]]:
        """세션의 최근 window 내 이벤트 (시나리오 무관 저장소). 엔진별 Pattern 계산 입력."""
        events = self._events_by_session.get(session_id, [])
        cutoff = _now() - timedelta(seconds=window_seconds)
        return [e for e in events if e["occurred_at"] >= cutoff]

    def reset(self, session_id: str) -> None:
        """세션의 누적 이벤트 제거."""
        self._events_by_session.pop(session_id, None)


# ── 싱글톤 인스턴스 ───────────────────────────────────────────
_extractor: BehavioralPatternExtractor | None = None


def get_extractor() -> BehavioralPatternExtractor:
    """공유 이벤트 저장소 싱글톤."""
    global _extractor
    if _extractor is None:
        _extractor = BehavioralPatternExtractor()
    return _extractor
