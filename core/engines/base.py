from __future__ import annotations
"""
Scenario Engine 추상 베이스.

각 시나리오(CS / 결합 / 직장인)는 추론에 필요한 시나리오 전용 로직을 구현한다:
  - Batch Context Feature Builder    : build_batch_features
  - Behavioral Pattern Extractor     : pattern_features (+ empty_pattern_features)
  - Event Feature Extractor          : event_features (+ empty_event_features)
  - Rule-Based Intent Trigger        : rule_predict
  - Predictive Intent Model          : model_predict
  - 행동 → 직접 신호 Intent 매핑      : behavior_intent_map
  - Intent 카탈로그                   : intents

inference.py는 scenario_id로 엔진을 받아 이 인터페이스만 호출한다.
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from core.engines import config

@lru_cache(maxsize=None)
def load_scenario_intents(scenario_id):
    data = config.get_taxonomy(scenario_id)
    return tuple({ "id": i["id"],
                  "name": i["name"],
                  "L1_id": i["L1_id"],
                  "L1_name": i["L1_name"],
                   "L2_id": i["L2_id"],
                   "L2_name": i["L2_name"],
                   "inference_type": i["inference_type"],
                   "features": i.get("features", [])} for i in data["intents"]
                   )

@lru_cache(maxsize=None)
def load_behavior_intent_map(scenario_id):
    m = config.get_behavior_signals(scenario_id)
    return tuple((k, tuple(v)) for k, v in m.items())


class ScenarioEngine:
    """시나리오 전용 추론 로직 인터페이스."""

    scenario_id: str

    def __init__(self, scenario_id: str):
        self.scenario_id = scenario_id

    # ── Feature 생성 ──────────────────────────────────────────
    def build_batch_features(self, answers: dict[str, str]) -> dict[str, Any]:
        raise NotImplementedError

    def empty_pattern_features(self) -> dict[str, Any]:
        raise NotImplementedError

    def empty_event_features(self) -> dict[str, Any]:
        raise NotImplementedError

    def pattern_features(self, session_id: str) -> dict[str, Any]:
        """공유 extractor 저장소의 세션 이벤트 → Pattern Feature (시나리오 전용 계산)."""
        raise NotImplementedError

    def event_features(self, session_id: str) -> dict[str, Any]:
        raise NotImplementedError

    # ── Intent 추론 ───────────────────────────────────────────
    def rule_predict(self, intent_id: str, features: dict[str, Any]) -> float:
        raise NotImplementedError

    def model_predict(self, intent_id: str, features: dict[str, Any]) -> float:
        raise NotImplementedError

    # ── 카탈로그 / 매핑 ───────────────────────────────────────
    def intents(self) -> list[dict]:
        return [dict(i) for i in load_scenario_intents(self.scenario_id)]

    def behavior_intent_map(self) -> dict[str, list[str]]:
        return {k: list(v) for k, v in load_behavior_intent_map(self.scenario_id)}
