from __future__ import annotations
"""
CS(cs-myk-v3) Scenario Engine.

기존 CS 전용 모듈(core.builder / core.extractor / core.event_extractor /
models.rule_model / models.sklearn_model)을 그대로 감싸 동작을 100% 보존한다.
"""
from typing import Any

from core.builder import build_batch_features as _cs_build_batch
from core.event_extractor import extract as _cs_extract_event
from core.extractor import get_extractor
from core.engines.base import ScenarioEngine
from models import rule_model, sklearn_model


class CSEngine(ScenarioEngine):

    def build_batch_features(self, answers: dict[str, str]) -> dict[str, Any]:
        return _cs_build_batch(answers)

    def empty_pattern_features(self) -> dict[str, Any]:
        return {
            "repeated_entity_count_5m": 0,
            "support_entry_count_5m":   0,
            "billing_page_view_count":  0,
            "product_explore_count":    0,
            "benefit_explore_count":    0,
            "churn_page_view_count":    0,
            "quality_action_count":     0,
            "last_3_events":            "",
            "WiFi 진단 실행":           0,
            "속도 측정 실행":           0,
            "장애 페이지 체류":         0,
            "가족 결합 관련 행동":      0,
            "위약금 조회 행동":         0,
            "해지 페이지 진입":         0,
            "mnp_benefit_check":        0,
            "할인 페이지 체류":         0,
        }

    def empty_event_features(self) -> dict[str, Any]:
        return {
            "last_event_type":  "",
            "last_entity":      "",
            "current_page":     "",
            "is_click":         0,
            "is_page_view":     0,
            "is_support_entry": 0,
            "is_churn_signal":  0,
            "is_confirm":       0,
            "last_event_at":    "",
        }

    def pattern_features(self, session_id: str) -> dict[str, Any]:
        return get_extractor().get_pattern_features(session_id)

    def event_features(self, session_id: str) -> dict[str, Any]:
        events = get_extractor()._events_by_session.get(session_id, [])
        if not events:
            return self.empty_event_features()
        last = events[-1]
        return _cs_extract_event(last["event_type"], last["entity"], last.get("occurred_at"))

    def rule_predict(self, intent_id: str, features: dict[str, Any]) -> float:
        return rule_model.predict(intent_id, features)

    def model_predict(self, intent_id: str, features: dict[str, Any]) -> float:
        return sklearn_model.predict(intent_id, features)
