from __future__ import annotations
"""
직장인(worker-v3) Scenario Engine.

[3] 시나리오_직장인 명세 구현:
  - 2.2 Batch Context Feature Builder : 설문 → Fatigue/Isolation/Retention/Sleep Index + 4 Score
  - 3.1 앱 선택지                     : 10개 앱 단일 선택 (event_type=app_open)
  - 3.2 Event Feature                 : 미생성 (단일 클릭 즉시 대응 이벤트 부재)
  - 3.3 Behavioral Pattern Extractor  : launch_entity / dominant_entity / transition / last_entity
"""
import json
from pathlib import Path
from typing import Any

from core.engines import config, common, extract, formula
from core.extractor import get_extractor
from core.engines.base import ScenarioEngine
from models import sklearn_model

_DATASET_PATH = Path(__file__).parent.parent.parent / "scenarios" / "worker-v3" / "seed_dataset.json"
_MODEL_PREFIX = "worker-v3__"


# ─────────────────────────────────────────────────────────────
# 2.2 Batch Context Feature Builder
# ─────────────────────────────────────────────────────────────
def build_batch_features(answers: dict[str, str]) -> dict[str, Any]:
    # 설문 → Base, Index/Score 파생은 L1_feature.json:batch_builder (선언형) → extract 평가.
    base = extract.survey_base(config.get_survey("worker-v3"), answers)
    return extract.run_batch_builder(base, config.get_batch_builder("worker-v3"))


# ─────────────────────────────────────────────────────────────
# 3.3 Behavioral Pattern Extractor (app_open)
# ─────────────────────────────────────────────────────────────
# 필드 정의는 L1_feature.json(pattern), 평가는 core.engines.extract. event는 미생성({}).
def empty_pattern_features() -> dict[str, Any]:
    return extract.pattern_from_spec([], config.get_pattern_spec("worker-v3"))


def pattern_features(session_id: str) -> dict[str, Any]:
    spec = config.get_pattern_spec("worker-v3")
    events = get_extractor().events_within(session_id, window_seconds=spec.get("window_seconds", 300))
    return extract.pattern_from_spec(extract._filter(events, spec.get("filter")), spec)


def empty_event_features() -> dict[str, Any]:
    return extract.event_from_spec(None, config.get_event_spec("worker-v3"))


def event_features(session_id: str) -> dict[str, Any]:
    events = get_extractor()._events_by_session.get(session_id, [])
    last = events[-1] if events else None
    return extract.event_from_spec(last, config.get_event_spec("worker-v3"))


# ─────────────────────────────────────────────────────────────
# Rule-Based Intent Trigger (Rule-Based Method)
# ─────────────────────────────────────────────────────────────
# 룰 수식 = L2_inference.json:rule (선언형) → formula.eval_formula + clamp01.
_RULE_SPEC = config.get_rule_spec("worker-v3")


def rule_predict(intent_id: str, features: dict[str, Any]) -> float:
    return formula.rule_predict(_RULE_SPEC, intent_id, features)


# ─────────────────────────────────────────────────────────────
# Predictive Intent Model (Model-Based Method)
# ─────────────────────────────────────────────────────────────
MODEL_TRAINING_DATA: dict[str, dict] = {
    "INT-W110": {"features": ["Burnout Deep Score", "Isolation Tendency Index", "Sleep Disturbance Index"]},
    "INT-W120": {"features": ["Fatigue Load Index", "Burnout Deep Score", "offwork_time"]},
    "INT-W140": {"features": ["Fatigue Load Index", "Isolation Tendency Index", "weekend_out"]},
}


# Model 휴리스틱 fallback용 정규화 범위 + 역방향(INT-W140 weekend_out: 외출 적을수록 강함)
NORM_RANGES = {"offwork_time": (1.0, 4.0), "weekend_out": (1.0, 3.0)}
_INVERT = frozenset({("INT-W140", "weekend_out")})


def model_predict(intent_id: str, features: dict[str, Any]) -> float:
    return common.model_predict(intent_id, features,
                                training_data=MODEL_TRAINING_DATA,
                                dataset_path=_DATASET_PATH,
                                model_prefix=_MODEL_PREFIX,
                                ranges=NORM_RANGES, scale=0.7, invert=_INVERT)


# ─────────────────────────────────────────────────────────────
class WorkerEngine(ScenarioEngine):

    def build_batch_features(self, answers: dict[str, str]) -> dict[str, Any]:
        return build_batch_features(answers)

    def empty_pattern_features(self) -> dict[str, Any]:
        return empty_pattern_features()

    def empty_event_features(self) -> dict[str, Any]:
        return empty_event_features()

    def pattern_features(self, session_id: str) -> dict[str, Any]:
        return pattern_features(session_id)

    def event_features(self, session_id: str) -> dict[str, Any]:
        return event_features(session_id)

    def rule_predict(self, intent_id: str, features: dict[str, Any]) -> float:
        return rule_predict(intent_id, features)

    def model_predict(self, intent_id: str, features: dict[str, Any]) -> float:
        return model_predict(intent_id, features)
