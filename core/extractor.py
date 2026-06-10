from __future__ import annotations
"""
Behavioral Pattern Extractor ([1c] reference 모듈)

실시간 행동 로그(event_type/entity)에서 5분 window aggregation으로
행동 구조 기반 Pattern Feature 8개 생성.
"""
from datetime import datetime, timedelta
from typing import Any


# ── Entity → 카운트 그룹 매핑 ─────────────────────────────────
_ENTITY_GROUP = {
    "data_usage":          ["data_view"],
    "billing":             ["billing_view"],
    "subscription_info":   ["subscription_view"],
    "benefit_membership":  ["benefit_view"],
    "product_explore":     ["product_view"],
    "customer_support":    ["support_view"],
    "data_topup_button":   ["data_topup"],
    "plan_change_button":  ["plan_change"],
    "quality_diagnosis":   ["quality_action", "wifi_diag", "speed_test"],
    "family_bundle":       ["family_bundle"],
    "penalty_calc":        ["churn_view", "penalty_view"],
    "confirm_button":      ["confirm"],
    "coupon_use":          ["coupon_use"],
    "chatbot":             ["support_entry"],
    "call_support":        ["support_entry"],
    "cancel_page":         ["churn_view", "cancel_view"],
}


def _now() -> datetime:
    return datetime.utcnow()


class BehavioralPatternExtractor:
    """
    세션별 이벤트를 누적하고 패턴 피처를 산출.

    시연 시: WebSocket 세션 단위로 인스턴스 보존, 매 행동마다 add_event() 호출
    """

    def __init__(self):
        self._events_by_session: dict[str, list[dict[str, Any]]] = {}

    def add_event(
        self,
        session_id: str,
        event_type: str,
        entity: str,
        occurred_at: datetime | None = None,
    ) -> None:
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

    # 하위 호환 alias
    _events_within = events_within

    def get_pattern_features(self, session_id: str) -> dict[str, Any]:
        """
        세션의 누적 이벤트에서 8개 Pattern Feature 산출.
        """
        events = self._events_within(session_id, window_seconds=300)

        # 그룹별 카운트
        group_counts: dict[str, int] = {}
        for ev in events:
            for group in _ENTITY_GROUP.get(ev["entity"], []):
                group_counts[group] = group_counts.get(group, 0) + 1

        # entity 별 반복 횟수
        entity_counts: dict[str, int] = {}
        for ev in events:
            entity_counts[ev["entity"]] = entity_counts.get(ev["entity"], 0) + 1
        repeated_max = max(entity_counts.values()) if entity_counts else 0

        # 최근 3 이벤트
        recent_3 = events[-3:] if events else []
        last_3_events = "→".join(e["event_type"] for e in recent_3)

        return {
            # 표준 Pattern Feature (8개)
            "repeated_entity_count_5m": repeated_max,
            "support_entry_count_5m":   group_counts.get("support_entry", 0),
            "billing_page_view_count":  group_counts.get("billing_view", 0),
            "product_explore_count":    group_counts.get("product_view", 0),
            "benefit_explore_count":    group_counts.get("benefit_view", 0),
            "churn_page_view_count":    group_counts.get("churn_view", 0),
            "quality_action_count":     group_counts.get("quality_action", 0),
            "last_3_events":            last_3_events,

            # Model 입력으로 쓰이는 보조 행동 피처
            "WiFi 진단 실행":           group_counts.get("wifi_diag", 0),
            "속도 측정 실행":           group_counts.get("speed_test", 0),
            "장애 페이지 체류":         group_counts.get("support_view", 0) * 60,
            "가족 결합 관련 행동":      1 if group_counts.get("family_bundle", 0) > 0 else 0,
            "위약금 조회 행동":         1 if group_counts.get("penalty_view", 0) > 0 else 0,
            "해지 페이지 진입":         1 if group_counts.get("cancel_view", 0) > 0 else 0,
            "mnp_benefit_check":        0,
            "할인 페이지 체류":         group_counts.get("benefit_view", 0) * 30,
        }

    def reset(self, session_id: str) -> None:
        self._events_by_session.pop(session_id, None)


# ── 싱글톤 인스턴스 ───────────────────────────────────────────
_extractor: BehavioralPatternExtractor | None = None


def get_extractor() -> BehavioralPatternExtractor:
    global _extractor
    if _extractor is None:
        _extractor = BehavioralPatternExtractor()
    return _extractor
