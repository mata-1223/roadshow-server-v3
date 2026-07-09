from __future__ import annotations
"""
레이어 config 단일 진입점.

모든 reader(엔진/inference/seed/route/스크립트)는 raw JSON을 직접 읽지 않고 이 접근자만 호출한다.
레이어 파일: scenarios/{sid}/engine/{input,L0_taxonomy,L1_feature,L2_inference,L3_serving}.json.
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_SCENARIOS = Path(__file__).parent.parent.parent / "scenarios"
# input = 데이터 소스 정의(데모: survey/behavior 선택 → 테이블 적재 / 실과제: 테이블 로드)
# L0~L3 = Taxonomy → Feature Foundation → Inference → Serving
_LAYERS = ("input", "L0_taxonomy", "L1_feature", "L2_inference", "L3_serving")


@lru_cache(maxsize=None)
def load_layer(scenario_id: str, layer: str) -> dict[str, Any]:
    """레이어 JSON 파일을 로드해 반환한다(프로세스 캐시).

    Args:
        scenario_id: 레이어를 로드할 시나리오 id.
        layer: 로드할 레이어 이름(_LAYERS 중 하나).

    Returns:
        파싱된 레이어 JSON dict.
    """
    with open(_SCENARIOS / scenario_id / "engine" / f"{layer}.json", encoding="utf-8") as f:
        return json.load(f)


# ── 레이어별 접근자 ──
def get_taxonomy(sid: str) -> dict[str, Any]:
    """[L0] intent 카탈로그 전체를 반환한다.

    Args:
        sid: 시나리오 id.

    Returns:
        L0_taxonomy 레이어 dict.
    """
    return load_layer(sid, "L0_taxonomy")

def get_survey(sid: str) -> dict[str, Any]:
    """[INPUT] 설문 정의를 반환한다.

    데모에서는 가상 고객 데이터 생성 INPUT이며, 실과제에서는 고객 데이터 테이블에 해당한다.

    Args:
        sid: 시나리오 id.

    Returns:
        설문 정의 dict.
    """
    return load_layer(sid, "input")["survey"]

def get_behaviors(sid: str) -> dict[str, Any]:
    """[INPUT] 행동 카탈로그를 반환한다.

    데모에서는 실시간 행동 INPUT이며, 실과제에서는 실시간 행동 로그 테이블에 해당한다.

    Args:
        sid: 시나리오 id.

    Returns:
        행동 카탈로그 dict.
    """
    return load_layer(sid, "input")["behavior_catalog"]

def get_behavior_signals(sid: str) -> dict[str, list[str]]:
    """[L2] 행동 entity → 직접 신호 intent 매핑을 반환한다.

    Args:
        sid: 시나리오 id.

    Returns:
        entity → intent id 리스트 매핑 dict.
    """
    return load_layer(sid, "L2_inference")["ranker"]["behavior_signals"]

def get_batch_builder(sid: str) -> dict[str, Any]:
    """[L1] Index/Score 파생 빌더 spec을 반환한다(defaults/pre_hook/steps).

    Args:
        sid: 시나리오 id.

    Returns:
        batch_builder spec dict. 없으면 빈 dict.
    """
    return load_layer(sid, "L1_feature").get("batch_builder", {})

def get_rule_spec(sid: str) -> dict[str, Any]:
    """[L2a] intent별 룰 수식 spec을 반환한다(eval_formula 평가용).

    Args:
        sid: 시나리오 id.

    Returns:
        rule spec dict. 없으면 빈 dict.
    """
    return load_layer(sid, "L2_inference").get("rule", {})

def get_model_spec(sid: str) -> dict[str, Any]:
    """[L2b] 예측 모델 spec을 반환한다.

    predictive_model/training_data/ranges/scale/invert/heuristic_fallback 등을 포함한다.

    Args:
        sid: 시나리오 id.

    Returns:
        model spec dict. 없으면 빈 dict.
    """
    return load_layer(sid, "L2_inference").get("model", {})

def get_pattern_spec(sid: str) -> dict[str, Any]:
    """[L1] Behavioral Pattern 추출 spec을 반환한다(window/filter/entity_groups/fields).

    Args:
        sid: 시나리오 id.

    Returns:
        pattern spec dict. 없으면 빈 dict.
    """
    return load_layer(sid, "L1_feature").get("pattern", {})

def get_event_spec(sid: str) -> dict[str, Any]:
    """[L1] Event Feature 추출 spec을 반환한다(entity_page_map/trigger_by_entity/flags).

    Args:
        sid: 시나리오 id.

    Returns:
        event spec dict. 없으면 빈 dict.
    """
    return load_layer(sid, "L1_feature").get("event", {})

def get_probability_temperature(sid: str) -> float:
    """[L2] calibrator의 softmax 온도를 반환한다.

    raw score를 확률로 변환하는 softmax 온도이며, 작을수록 상위 Intent에 집중된다.

    Args:
        sid: 시나리오 id.

    Returns:
        softmax 온도 값.
    """
    return load_layer(sid, "L2_inference")["calibrator"]["probability_temperature"]

def get_action_signal(sid: str) -> dict[str, float]:
    """[L2] ranker의 최신 행동 기반 Intent 부스트 파라미터를 반환한다.

    Args:
        sid: 시나리오 id.

    Returns:
        부스트 파라미터 dict {scale, cap, decay}.
    """
    return load_layer(sid, "L2_inference")["ranker"]["action_signal"]

def get_actions(sid: str) -> dict[str, Any]:
    """[L3] intent별 채널 활용 정의(context_library)를 반환한다.

    Args:
        sid: 시나리오 id.

    Returns:
        context_library dict.
    """
    return load_layer(sid, "L3_serving")["context_library"]