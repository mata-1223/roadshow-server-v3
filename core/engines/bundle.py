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

from core.engines import config, common, extract
from core.engines.common import clamp, clamp01, g
from core.extractor import get_extractor
from core.engines.base import ScenarioEngine
from models import sklearn_model

_DATASET_PATH = Path(__file__).parent.parent.parent / "scenarios" / "bundle-v3" / "seed_dataset.json"
_MODEL_PREFIX = "bundle-v3__"


# ─────────────────────────────────────────────────────────────
# 2.2 Batch Context Feature Builder
# ─────────────────────────────────────────────────────────────
def build_batch_features(answers: dict[str, str]) -> dict[str, Any]:
    survey = config.get_survey("bundle-v3")

    base: dict[str, Any] = {}
    for q in survey["questions"]:
        code = answers.get(q["id"])
        if code is None:
            continue
        opt = next((o for o in q["options"] if o["code"] == code), None)
        if opt:
            base.update(opt.get("features", {}))

    # 기본값
    plan_tier        = float(base.get("plan_tier", 2))
    plan_bill_level  = float(base.get("plan_bill_level", plan_tier))
    family_line      = float(base.get("family_line_count", 1))
    sub_service      = float(base.get("subscribed_service_count", 1))
    household_change = float(base.get("household_change", 0))
    tenure_group     = float(base.get("tenure_group", 2))
    contract_status  = float(base.get("contract_status", 1))
    monthly_bill     = float(base.get("monthly_bill_level", plan_bill_level))
    benefit_util     = float(base.get("benefit_utilization", 2))
    content_view     = float(base.get("content_view_mode", 3))
    dissat           = str(base.get("dissatisfaction_factor", "없음"))

    # Ratio / Delta
    service_coverage_ratio = round(sub_service / 3.0, 4)
    non_mobile_cost_gap    = monthly_bill - plan_bill_level
    base["service_coverage_ratio"] = service_coverage_ratio
    base["non_mobile_cost_gap"]    = non_mobile_cost_gap

    # ── Index (0~100) ────────────────────────────────────────
    bundle_opp = clamp(
        ((family_line - 1) / 3 * 50)
        + ((1 - service_coverage_ratio) * 30)
        + (household_change / 2 * 20)
    )
    benefit_opt = clamp(
        (min(non_mobile_cost_gap, 3) / 3 * 40)
        + ((2 - benefit_util) * 35)
        + ((25 if dissat in ("통신비", "혜택") else 0))
    )
    home_expand = clamp(
        ((1 - service_coverage_ratio) * 50)
        + (content_view / 3 * 30)
        + (20 if household_change >= 1 else 0)
    )
    retention_ready = clamp(
        ((tenure_group - 1) / 2 * 40)
        + (contract_status / 2 * 60)
    )
    churn_risk = clamp(
        (50 if dissat != "없음" else 0)
        + (contract_status / 2 * 30)
        + (min(non_mobile_cost_gap, 3) / 3 * 20)
    )
    benefit_engage = clamp(benefit_util / 2 * 100)

    idx = {
        "Bundle Opportunity Index":     round(bundle_opp, 2),
        "Benefit Optimization Index":   round(benefit_opt, 2),
        "Home Service Expansion Index": round(home_expand, 2),
        "Retention Readiness Index":    round(retention_ready, 2),
        "Churn Risk Index":             round(churn_risk, 2),
        "Benefit Engagement Index":     round(benefit_engage, 2),
    }

    # ── Score (0~100) ────────────────────────────────────────
    score = {
        "Acquisition Score":         round(0.7 * bundle_opp + 0.3 * home_expand, 2),
        "Benefit Optimization Score": round(0.7 * benefit_opt + 0.3 * (100 - benefit_engage), 2),
        "Service Expansion Score":   round(0.7 * home_expand + 0.3 * bundle_opp, 2),
        "Retention Score":           round(0.8 * retention_ready + 0.2 * benefit_engage, 2),
        "Churn Defense Score":       round(0.7 * churn_risk + 0.3 * benefit_opt, 2),
    }

    return {**base, **idx, **score}


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
RULES = {
    # ── 가입 확대 ──
    "INT-B1110": lambda f: clamp01(0.20 + g(f, "Bundle Opportunity Index") / 100 * 0.55
                                    + (0.1 if g(f, "family_line_count") >= 2 else 0)),
    "INT-B1120": lambda f: clamp01(0.15 + (1 - g(f, "service_coverage_ratio", 1)) * 0.6
                                    + g(f, "Bundle Opportunity Index") / 100 * 0.2),
    "INT-B1130": lambda f: clamp01(0.20 + g(f, "Bundle Opportunity Index") / 100 * 0.4),
    "INT-B1410": lambda f: clamp01(0.10 + g(f, "Acquisition Score") / 100 * 0.6),
    "INT-B1420": lambda f: clamp01(0.10 + g(f, "Acquisition Score") / 100 * 0.5),
    # ── 할인 최적화 ──
    "INT-B2110": lambda f: clamp01(0.20 + g(f, "Benefit Engagement Index") / 100 * 0.4
                                    + (0.15 if g(f, "benefit_utilization") >= 2 else 0)),
    "INT-B2210": lambda f: clamp01(0.15 + g(f, "Benefit Optimization Index") / 100 * 0.6),
    "INT-B2230": lambda f: clamp01(0.15 + g(f, "Benefit Optimization Index") / 100 * 0.4
                                    + min(g(f, "non_mobile_cost_gap"), 3) / 3 * 0.2),
    "INT-B2340": lambda f: clamp01(0.15 + (1 - g(f, "benefit_utilization", 2) / 3) * 0.5
                                    + (100 - g(f, "Benefit Engagement Index")) / 100 * 0.2),
    # ── 회선/서비스 확장 ──
    "INT-B3110": lambda f: clamp01(0.15 + (g(f, "family_line_count") - 1) / 2 * 0.5
                                    + g(f, "Bundle Opportunity Index") / 100 * 0.25),
    "INT-B3120": lambda f: clamp01(0.15 + g(f, "Home Service Expansion Index") / 100 * 0.55),
    "INT-B3130": lambda f: clamp01(0.15 + g(f, "Home Service Expansion Index") / 100 * 0.35
                                    + g(f, "content_view_mode") / 4 * 0.25),
    "INT-B3150": lambda f: clamp01(0.10 + g(f, "Home Service Expansion Index") / 100 * 0.4
                                    + (0.2 if g(f, "household_change") >= 1 else 0)),
    "INT-B3330": lambda f: clamp01(0.10 + (0.4 if g(f, "household_change") >= 1 else 0)
                                    + (g(f, "family_line_count") - 1) / 2 * 0.2),
    "INT-B3340": lambda f: clamp01(0.10 + (0.35 if g(f, "household_change") >= 1 else 0)),
    # ── 유지/락인 ──
    "INT-B4110": lambda f: clamp01(0.15 + g(f, "contract_status") / 3 * 0.4
                                    + g(f, "Retention Readiness Index") / 100 * 0.3),
    "INT-B4210": lambda f: clamp01(0.10 + (g(f, "tenure_group") - 1) / 2 * 0.45
                                    + g(f, "Retention Readiness Index") / 100 * 0.25),
    "INT-B4320": lambda f: clamp01(0.10 + g(f, "Churn Risk Index") / 100 * 0.4
                                    + (0.15 if g(f, "contract_status") >= 3 else 0)),
    # ── 이탈 검토 ──
    "INT-B5120": lambda f: clamp01(0.10 + g(f, "Churn Risk Index") / 100 * 0.5),
    "INT-B5310": lambda f: clamp01(0.05 + (0.55 if f.get("dissatisfaction_factor") == "인터넷 품질" else 0)
                                    + g(f, "Churn Risk Index") / 100 * 0.15),
    "INT-B5320": lambda f: clamp01(0.05 + (0.55 if f.get("dissatisfaction_factor") == "IPTV 품질" else 0)
                                    + g(f, "Churn Risk Index") / 100 * 0.15),
    "INT-B5410": lambda f: clamp01(0.05 + g(f, "Churn Risk Index") / 100 * 0.6),
    "INT-B5420": lambda f: clamp01(0.05 + g(f, "Churn Risk Index") / 100 * 0.45
                                    + (0.15 if g(f, "contract_status") >= 2 else 0)),
    "INT-B5430": lambda f: clamp01(0.05 + g(f, "Churn Risk Index") / 100 * 0.5),
    "INT-B5440": lambda f: clamp01(0.05 + g(f, "Churn Risk Index") / 100 * 0.4),
}

def rule_predict(intent_id: str, features: dict[str, Any]) -> float:
    return common.rule_predict(RULES, intent_id, features)



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
