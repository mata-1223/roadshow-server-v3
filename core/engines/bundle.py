from __future__ import annotations
"""
결합(bundle-v3) Scenario Engine.

[2] 시나리오_결합 명세 구현:
  - 2.2 Batch Context Feature Builder : 설문 → Base/Delta/Ratio/Index/Score
  - 3.3 Behavioral Pattern Extractor  : entity/event_type 흐름 → Pattern Feature
  - 3.2 Event Feature Extractor       : 단일 클릭 즉시 대응 Trigger Action 플래그
  - 1.2 Rule-Based / Predictive 분리  : rule_predict / model_predict
"""
from pathlib import Path
from typing import Any

from core.engines import config, common, extract, formula
from core.extractor import get_extractor
from core.engines.base import ScenarioEngine
from models import sklearn_model

_DATASET_PATH = Path(__file__).parent.parent.parent / "scenarios" / "bundle-v3" / "seed_dataset.json"
_MODEL_PREFIX = "bundle-v3__"


# ─────────────────────────────────────────────────────────────
# 2.2 Batch Context Feature Builder
# ─────────────────────────────────────────────────────────────
def build_batch_features(answers: dict[str, str]) -> dict[str, Any]:
    # 설문 → Base, Index/Score 파생은 L1_feature.json:batch_builder (선언형) → extract 평가.
    base = extract.survey_base(config.get_survey("bundle-v3"), answers)
    return extract.run_batch_builder(base, config.get_batch_builder("bundle-v3"))


# ─────────────────────────────────────────────────────────────
# 3.3 Behavioral Pattern Extractor
# ─────────────────────────────────────────────────────────────
# entity 맵·필드 정의는 L1_feature.json(pattern/event), 평가는 core.engines.extract.
def empty_pattern_features() -> dict[str, Any]:
    return extract.pattern_from_spec([], config.get_pattern_spec("bundle-v3"))


def pattern_features(session_id: str) -> dict[str, Any]:
    spec = config.get_pattern_spec("bundle-v3")
    events = get_extractor().events_within(session_id, window_seconds=spec.get("window_seconds", 300))
    return extract.pattern_from_spec(extract._filter(events, spec.get("filter")), spec)


def empty_event_features() -> dict[str, Any]:
    return extract.event_from_spec(None, config.get_event_spec("bundle-v3"))


def event_features(session_id: str) -> dict[str, Any]:
    events = get_extractor()._events_by_session.get(session_id, [])
    last = events[-1] if events else None
    return extract.event_from_spec(last, config.get_event_spec("bundle-v3"))


# ─────────────────────────────────────────────────────────────
# Rule-Based Intent Trigger (Rule-Based Method)
# ─────────────────────────────────────────────────────────────
# 룰 수식 = L2_inference.json:rule (선언형) → formula.eval_formula + clamp01.
_RULE_SPEC = config.get_rule_spec("bundle-v3")


def rule_predict(intent_id: str, features: dict[str, Any]) -> float:
    return formula.rule_predict(_RULE_SPEC, intent_id, features)



# ─────────────────────────────────────────────────────────────
# Predictive Intent Model (Model-Based Method)
# ─────────────────────────────────────────────────────────────
# 각 Model Intent의 학습 입력 feature (batch Index/Score + 행동 Pattern Feature)
MODEL_TRAINING_DATA: dict[str, dict] = {
    "INT-B1210": {"features": ["Benefit Optimization Index", "non_mobile_cost_gap", "comparison_action_count_5m", "entity_focus_ratio_5m"]},
    "INT-B1220": {"features": ["Benefit Engagement Index", "content_view_mode", "explored_entity_count_5m"]},
    "INT-B1230": {"features": ["plan_tier", "Benefit Engagement Index", "explored_entity_count_5m"]},
    "INT-B1310": {"features": ["Bundle Opportunity Index", "Benefit Optimization Index", "tenure_group"]},
    "INT-B1430": {"features": ["Acquisition Score", "Bundle Opportunity Index", "action_intensity_5m"]},
    "INT-B2220": {"features": ["Benefit Optimization Index", "benefit_utilization", "explored_entity_count_5m"]},
    "INT-B2310": {"features": ["Benefit Engagement Index", "content_view_mode", "explored_entity_count_5m"]},
    "INT-B2320": {"features": ["Benefit Engagement Index", "benefit_utilization", "explored_entity_count_5m"]},
    "INT-B2330": {"features": ["Benefit Engagement Index", "content_view_mode", "explored_entity_count_5m"]},
    "INT-B3140": {"features": ["Home Service Expansion Index", "service_coverage_ratio", "comparison_action_count_5m"]},
    "INT-B3210": {"features": ["plan_tier", "Service Expansion Score", "explored_entity_count_5m"]},
    "INT-B3220": {"features": ["plan_tier", "Service Expansion Score", "explored_entity_count_5m"]},
    "INT-B3230": {"features": ["plan_tier", "Service Expansion Score", "explored_entity_count_5m"]},
    "INT-B3240": {"features": ["plan_tier", "Service Expansion Score", "explored_entity_count_5m"]},
    "INT-B3310": {"features": ["family_line_count", "Bundle Opportunity Index", "household_change"]},
    "INT-B3320": {"features": ["family_line_count", "household_change", "explored_entity_count_5m"]},
    "INT-B3350": {"features": ["household_change", "family_line_count", "explored_entity_count_5m"]},
    "INT-B4120": {"features": ["Retention Readiness Index", "Benefit Engagement Index", "comparison_action_count_5m", "decision_action_count_5m"]},
    "INT-B4310": {"features": ["non_mobile_cost_gap", "Retention Readiness Index", "comparison_action_count_5m"]},
    "INT-B5110": {"features": ["Churn Risk Index", "non_mobile_cost_gap", "churn_action_count_5m", "comparison_action_count_5m"]},
    "INT-B5210": {"features": ["Churn Risk Index", "Benefit Optimization Index", "churn_action_count_5m"]},
    "INT-B5220": {"features": ["Churn Risk Index", "Retention Readiness Index", "churn_action_count_5m"]},
    "INT-B5230": {"features": ["non_mobile_cost_gap", "Churn Risk Index", "churn_action_count_5m"]},
    "INT-B5330": {"features": ["Churn Risk Index", "Churn Defense Score", "churn_action_count_5m"]},
    "INT-B5340": {"features": ["Churn Risk Index", "Churn Defense Score", "churn_action_count_5m"]},
}


# Model 휴리스틱 fallback용 feature 정규화 범위 (미학습 Model intent)
NORM_RANGES = {
    "service_coverage_ratio": (0.0, 1.0),
    "non_mobile_cost_gap":    (0.0, 3.0),
    "content_view_mode":      (0.0, 4.0),
    "benefit_utilization":    (0.0, 3.0),
    "plan_tier":              (0.0, 4.0),
    "family_line_count":      (1.0, 3.0),
    "household_change":       (0.0, 2.0),
    "tenure_group":           (1.0, 3.0),
    "contract_status":        (1.0, 3.0),
}


def model_predict(intent_id: str, features: dict[str, Any]) -> float:
    return common.model_predict(intent_id, features,
                                training_data=MODEL_TRAINING_DATA,
                                dataset_path=_DATASET_PATH,
                                model_prefix=_MODEL_PREFIX,
                                ranges=NORM_RANGES, scale=0.55)


# ─────────────────────────────────────────────────────────────
class BundleEngine(ScenarioEngine):

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
