from __future__ import annotations
"""
Event Feature Extractor ([1b] reference 모듈)

단일 이벤트(event_type, entity)에서 즉시 파생되는 Feature를 산출.
누적 윈도우 집계가 아닌 "현재 화면/마지막 동작" 같은 즉답 신호용.

[1c] Behavioral Pattern Extractor 와의 차이
- [1b] Event Feature : 1건의 이벤트 → 즉시 파생 (current_page, last_action)
- [1c] Pattern Feature: 5분 윈도우 집계 → count/seq 패턴 (예: support_entry_count_5m)
"""
from datetime import datetime
from typing import Any


# Entity 마지막 진입 → 현재 화면 카테고리
_ENTITY_TO_PAGE = {
    "data_usage":         "data",
    "billing":            "billing",
    "subscription_info":  "subscription",
    "benefit_membership": "benefit",
    "product_explore":    "product",
    "customer_support":   "support",
    "data_topup_button":  "data",
    "plan_change_button": "product",
    "quality_diagnosis":  "support",
    "family_bundle":      "subscription",
    "penalty_calc":       "churn",
    "confirm_button":     "confirm",
    "coupon_use":         "benefit",
    "chatbot":            "support",
    "call_support":       "support",
    "cancel_page":        "churn",
}


def extract(event_type: str, entity: str, occurred_at: datetime | None = None) -> dict[str, Any]:
    """단일 이벤트 → Event Feature dict."""
    ts = occurred_at or datetime.now()
    return {
        "last_event_type":  event_type,
        "last_entity":      entity,
        "current_page":     _ENTITY_TO_PAGE.get(entity, "unknown"),
        "is_click":         1 if event_type == "click" else 0,
        "is_page_view":     1 if event_type == "page_view" else 0,
        "is_support_entry": 1 if event_type == "support_entry" else 0,
        "is_churn_signal":  1 if entity in ("penalty_calc", "cancel_page") else 0,
        "is_confirm":       1 if entity == "confirm_button" else 0,
        "last_event_at":    ts.isoformat(),
    }
