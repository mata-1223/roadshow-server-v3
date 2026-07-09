from __future__ import annotations
"""
Behavioral 이벤트 공유 저장소 (시나리오 무관).

세션별 행동 이벤트를 누적하고 5분 window로 조회한다.
Pattern Feature 산출(시나리오별 집계)은 각 엔진(cs/bundle/worker)이 담당.
"""
from datetime import datetime, timedelta
from typing import Any


def _now() -> datetime:
    """현재 UTC 시각을 반환한다 (이벤트 타임스탬프·window 컷오프 기준).

    Returns:
        현재 UTC datetime.
    """
    return datetime.utcnow()


class BehavioralPatternExtractor:
    """세션별 행동 이벤트를 누적하고 window 단위로 조회한다.

    WebSocket 세션 단위로 인스턴스를 보존하며, 매 행동마다 add_event()를 호출한다.
    Pattern Feature 산출은 각 시나리오 엔진이 담당한다.
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
        """세션에 행동 이벤트 1건을 누적한다.

        Args:
            session_id: 이벤트를 누적할 세션 ID.
            event_type: 이벤트 종류.
            entity: 이벤트 대상 엔티티.
            occurred_at: 이벤트 발생 시각. 미지정 시 현재 UTC.
        """
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
        """세션의 최근 window 내 이벤트를 조회한다.

        엔진별 Pattern 계산 입력으로 사용된다.

        Args:
            session_id: 조회할 세션 ID.
            window_seconds: 컷오프 window 길이(초).

        Returns:
            컷오프 이후 발생한 이벤트 리스트.
        """
        events = self._events_by_session.get(session_id, [])
        cutoff = _now() - timedelta(seconds=window_seconds)
        return [e for e in events if e["occurred_at"] >= cutoff]

    def recent_events(self, session_id: str, n: int) -> list[dict[str, Any]]:
        """세션의 최근 n개 이벤트를 조회한다 (클릭 기반 윈도우).

        Args:
            session_id: 조회할 세션 ID.
            n: 조회할 최근 이벤트 개수. 0 이하이면 전체.

        Returns:
            최근 n개 이벤트 리스트.
        """
        events = self._events_by_session.get(session_id, [])
        return events[-n:] if n and n > 0 else list(events)

    def reset(self, session_id: str) -> None:
        """세션의 누적 이벤트를 제거한다.

        Args:
            session_id: 초기화할 세션 ID.
        """
        self._events_by_session.pop(session_id, None)


# ── 싱글톤 인스턴스 ───────────────────────────────────────────
_extractor: BehavioralPatternExtractor | None = None


def get_extractor() -> BehavioralPatternExtractor:
    """공유 이벤트 저장소 싱글톤을 반환한다.

    Returns:
        프로세스 전역 BehavioralPatternExtractor 인스턴스.
    """
    global _extractor
    if _extractor is None:
        _extractor = BehavioralPatternExtractor()
    return _extractor
