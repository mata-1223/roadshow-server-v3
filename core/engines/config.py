from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path

_SCENARIOS = Path(__file__).parent.parent.parent / "scenarios"
# input = 데이터 소스 정의(데모: survey/behavior 선택 → 테이블 적재 / 실과제: 테이블 로드)
# L0~L3 = Taxonomy → Feature Foundation → Inference → Serving
_LAYERS = ("input", "L0_taxonomy", "L1_feature", "L2_inference", "L3_serving")

@lru_cache(maxsize=None)
def load_layer(scenario_id: str, layer: str) -> dict:
    with open(_SCENARIOS / scenario_id / "engine" / f"{layer}.json", encoding="utf-8") as f:
        return json.load(f)

# ── 레이어별 접근자 ──
def get_taxonomy(sid):
    return load_layer(sid, "L0_taxonomy")
def get_survey(sid):
    # survey = 데모의 가상 고객 데이터 생성 INPUT (실과제: 고객 데이터 테이블)
    return load_layer(sid, "input")["survey"]
def get_behaviors(sid):
    # behavior_catalog = 데모의 실시간 행동 INPUT (실과제: 실시간 행동 로그 테이블)
    return load_layer(sid, "input")["behavior_catalog"]
def get_behavior_signals(sid):
    return load_layer(sid, "L2_inference")["ranker"]["behavior_signals"]
def get_probability_temperature(sid):
    # calibrator: raw score → 확률 softmax 온도(작을수록 상위 Intent 집중)
    return load_layer(sid, "L2_inference")["calibrator"]["probability_temperature"]
def get_action_signal(sid):
    # ranker: 최신 행동 → Intent 부스트 파라미터 {scale, cap, decay}
    return load_layer(sid, "L2_inference")["ranker"]["action_signal"]
def get_actions(sid):
    return load_layer(sid, "L3_serving")["context_library"]