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
    """레이어 JSON 파일을 로드(프로세스 캐시). layer ∈ _LAYERS."""
    with open(_SCENARIOS / scenario_id / "engine" / f"{layer}.json", encoding="utf-8") as f:
        return json.load(f)


# ── 레이어별 접근자 ──
def get_taxonomy(sid: str) -> dict[str, Any]:
    """[L0] intent 카탈로그 전체."""
    return load_layer(sid, "L0_taxonomy")

def get_survey(sid: str) -> dict[str, Any]:
    """[INPUT] 설문 정의 — 데모의 가상 고객 데이터 생성 INPUT (실과제: 고객 데이터 테이블)."""
    return load_layer(sid, "input")["survey"]

def get_behaviors(sid: str) -> dict[str, Any]:
    """[INPUT] 행동 카탈로그 — 데모의 실시간 행동 INPUT (실과제: 실시간 행동 로그 테이블)."""
    return load_layer(sid, "input")["behavior_catalog"]

def get_behavior_signals(sid: str) -> dict[str, list[str]]:
    """[L2] 행동 entity → 직접 신호 intent 매핑."""
    return load_layer(sid, "L2_inference")["ranker"]["behavior_signals"]

def get_batch_builder(sid: str) -> dict[str, Any]:
    """[L1] Index/Score 파생 빌더 spec (defaults/pre_hook/steps)."""
    return load_layer(sid, "L1_feature").get("batch_builder", {})

def get_rule_spec(sid: str) -> dict[str, Any]:
    """[L2a] intent별 룰 수식 spec (eval_formula 평가)."""
    return load_layer(sid, "L2_inference").get("rule", {})

def get_model_spec(sid: str) -> dict[str, Any]:
    """[L2b] 예측 모델 spec (predictive_model/training_data/ranges/scale/invert/heuristic_fallback)."""
    return load_layer(sid, "L2_inference").get("model", {})

def get_pattern_spec(sid: str) -> dict[str, Any]:
    """[L1] Behavioral Pattern 추출 spec (window/filter/entity_groups/fields)."""
    return load_layer(sid, "L1_feature").get("pattern", {})

def get_event_spec(sid: str) -> dict[str, Any]:
    """[L1] Event Feature 추출 spec (entity_page_map/trigger_by_entity/flags)."""
    return load_layer(sid, "L1_feature").get("event", {})

def get_probability_temperature(sid: str) -> float:
    """[L2] calibrator: raw score → 확률 softmax 온도(작을수록 상위 Intent 집중)."""
    return load_layer(sid, "L2_inference")["calibrator"]["probability_temperature"]

def get_action_signal(sid: str) -> dict[str, float]:
    """[L2] ranker: 최신 행동 → Intent 부스트 파라미터 {scale, cap, decay}."""
    return load_layer(sid, "L2_inference")["ranker"]["action_signal"]

def get_actions(sid: str) -> dict[str, Any]:
    """[L3] intent별 채널 활용(context_library)."""
    return load_layer(sid, "L3_serving")["context_library"]