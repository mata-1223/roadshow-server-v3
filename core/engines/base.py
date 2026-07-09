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
def load_scenario_intents(scenario_id: str) -> tuple[dict, ...]:
    """[L0] taxonomy를 intent 메타 튜플로 변환해 반환한다(프로세스 캐시).

    각 dict는 id/name/L1·L2/inference_type/features 키를 가진다.

    Args:
        scenario_id: taxonomy를 로드할 시나리오 id.

    Returns:
        intent 메타 dict들의 튜플(해시 가능).
    """
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
def load_behavior_intent_map(scenario_id: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """[L2] 행동 entity → 직접 신호 intent 매핑을 해시 가능한 튜플로 반환한다(프로세스 캐시).

    Args:
        scenario_id: 매핑을 로드할 시나리오 id.

    Returns:
        (entity, intent id 튜플) 쌍들의 튜플.
    """
    m = config.get_behavior_signals(scenario_id)
    return tuple((k, tuple(v)) for k, v in m.items())


class ScenarioEngine:
    """시나리오 전용 추론 로직 인터페이스."""

    scenario_id: str

    def __init__(self, scenario_id: str):
        """엔진을 시나리오 id에 바인딩한다.

        Args:
            scenario_id: 이 엔진이 담당할 시나리오 id.
        """
        self.scenario_id = scenario_id

    # ── Feature 생성 ──────────────────────────────────────────
    def build_batch_features(self, answers: dict[str, str]) -> dict[str, Any]:
        """[L1] 설문 답변을 Batch Context Feature(Base/Index/Score)로 변환한다.

        Args:
            answers: 질문 id → 선택 옵션 코드 매핑.

        Returns:
            Batch Context Feature dict.

        Raises:
            NotImplementedError: 하위 엔진이 구현하지 않은 경우.
        """
        raise NotImplementedError

    def empty_pattern_features(self) -> dict[str, Any]:
        """행동 없음 상태의 Pattern Feature(0/빈값)를 반환한다.

        Returns:
            기본값으로 채운 Pattern Feature dict.

        Raises:
            NotImplementedError: 하위 엔진이 구현하지 않은 경우.
        """
        raise NotImplementedError

    def empty_event_features(self) -> dict[str, Any]:
        """행동 없음 상태의 Event Feature(0/빈값)를 반환한다.

        Returns:
            기본값으로 채운 Event Feature dict.

        Raises:
            NotImplementedError: 하위 엔진이 구현하지 않은 경우.
        """
        raise NotImplementedError

    def pattern_features(self, session_id: str) -> dict[str, Any]:
        """[L1] 공유 extractor 저장소의 세션 이벤트를 Pattern Feature로 계산한다.

        Args:
            session_id: 이벤트를 조회할 세션 id.

        Returns:
            시나리오 전용 계산이 적용된 Pattern Feature dict.

        Raises:
            NotImplementedError: 하위 엔진이 구현하지 않은 경우.
        """
        raise NotImplementedError

    def event_features(self, session_id: str) -> dict[str, Any]:
        """[L1] 세션 최신 이벤트를 Event Feature(트리거 플래그 등)로 변환한다.

        Args:
            session_id: 최신 이벤트를 조회할 세션 id.

        Returns:
            Event Feature dict.

        Raises:
            NotImplementedError: 하위 엔진이 구현하지 않은 경우.
        """
        raise NotImplementedError

    # ── Intent 추론 ───────────────────────────────────────────
    def rule_predict(self, intent_id: str, features: dict[str, Any]) -> float:
        """[L2a] Rule Intent 점수(0~1)를 반환한다.

        Args:
            intent_id: 점수를 계산할 intent id.
            features: 평가에 사용할 feature dict.

        Returns:
            0~1 범위의 Rule Intent 점수.

        Raises:
            NotImplementedError: 하위 엔진이 구현하지 않은 경우.
        """
        raise NotImplementedError

    def model_predict(self, intent_id: str, features: dict[str, Any]) -> float:
        """[L2b] Model Intent 점수(0~1)를 반환한다.

        Args:
            intent_id: 점수를 계산할 intent id.
            features: 추론에 사용할 feature dict.

        Returns:
            0~1 범위의 Model Intent 점수.

        Raises:
            NotImplementedError: 하위 엔진이 구현하지 않은 경우.
        """
        raise NotImplementedError

    # ── 카탈로그 / 매핑 ───────────────────────────────────────
    def intents(self) -> list[dict]:
        """[L0] intent 카탈로그(메타 dict 리스트)를 반환한다.

        Returns:
            intent 메타 dict들의 리스트.
        """
        return [dict(i) for i in load_scenario_intents(self.scenario_id)]

    def behavior_intent_map(self) -> dict[str, list[str]]:
        """[L2] 행동 entity → 직접 신호 intent 매핑을 반환한다.

        Returns:
            entity → intent id 리스트 매핑 dict.
        """
        return {k: list(v) for k, v in load_behavior_intent_map(self.scenario_id)}
