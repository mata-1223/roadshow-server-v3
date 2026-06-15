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

from core.engines import config, common
from core.engines.common import clamp, clamp01, g
from core.extractor import get_extractor
from core.engines.base import ScenarioEngine
from models import sklearn_model

_DATASET_PATH = Path(__file__).parent.parent.parent / "scenarios" / "worker-v3" / "seed_dataset.json"
_MODEL_PREFIX = "worker-v3__"


# ─────────────────────────────────────────────────────────────
# 2.2 Batch Context Feature Builder
# ─────────────────────────────────────────────────────────────
def build_batch_features(answers: dict[str, str]) -> dict[str, Any]:
    survey = config.get_survey("worker-v3")

    base: dict[str, Any] = {}
    for q in survey["questions"]:
        code = answers.get(q["id"])
        if code is None:
            continue
        opt = next((o for o in q["options"] if o["code"] == code), None)
        if opt:
            base.update(opt.get("features", {}))

    plan_tier   = float(base.get("plan_tier", 2))
    tenure      = float(base.get("tenure_group", 2))
    offwork     = float(base.get("offwork_time", 2))
    overtime    = float(base.get("overtime_freq", 1))
    move        = float(base.get("move_pattern", 1))
    weekend_out = float(base.get("weekend_out", 2))
    social      = float(base.get("social_contact", 3))
    night_phone = float(base.get("night_phone_usage", 1))

    fatigue = clamp(((offwork - 1) / 3 * 50) + ((overtime - 1) / 3 * 50))
    isolation = clamp(((2 - move) * 25) + ((3 - weekend_out) / 2 * 35) + ((4 - social) / 3 * 40))
    retention = clamp(((5 - plan_tier) / 4 * 60) + ((tenure - 1) / 4 * 40))
    sleep = clamp(((night_phone - 1) / 2 * 70) + ((offwork - 1) / 3 * 30))

    idx = {
        "Fatigue Load Index":      round(fatigue, 2),
        "Isolation Tendency Index": round(isolation, 2),
        "Retention Value Index":   round(retention, 2),
        "Sleep Disturbance Index": round(sleep, 2),
    }
    score = {
        "Burnout Deep Score":       round(0.4 * fatigue + 0.3 * isolation + 0.3 * sleep, 2),
        "Recovery Motivation Score": round(0.6 * fatigue + 0.4 * isolation, 2),
        "Digital Escape Score":     round(0.7 * sleep + 0.3 * isolation, 2),
        "Retention Value Score":    round(retention, 2),
    }
    return {**base, **idx, **score}


# ─────────────────────────────────────────────────────────────
# 3.3 Behavioral Pattern Extractor (app_open)
# ─────────────────────────────────────────────────────────────
def empty_pattern_features() -> dict[str, Any]:
    return {
        "launch_entity_count_5m":   0,
        "action_intensity_5m":      0,
        "dominant_entity_5m":       "",
        "entity_transition_pattern": "",
        "last_entity":              "",
    }


def pattern_features(session_id: str) -> dict[str, Any]:
    events = get_extractor().events_within(session_id, window_seconds=300)
    real = [e for e in events if e["event_type"] == "app_open"]
    if not real:
        return empty_pattern_features()
    entity_counts: dict[str, int] = {}
    for e in real:
        entity_counts[e["entity"]] = entity_counts.get(e["entity"], 0) + 1
    dominant = max(entity_counts.items(), key=lambda kv: kv[1])[0]
    recent = real[-3:]
    return {
        "launch_entity_count_5m":   len(entity_counts),
        "action_intensity_5m":      len(real),
        "dominant_entity_5m":       dominant,
        "entity_transition_pattern": "→".join(e["entity"] for e in recent),
        "last_entity":              real[-1]["entity"],
    }


# 3.2 Event Feature 미생성 → 빈 dict
def empty_event_features() -> dict[str, Any]:
    return {}


def event_features(session_id: str) -> dict[str, Any]:
    return {}


# ─────────────────────────────────────────────────────────────
# Rule-Based Intent Trigger (Rule-Based Method)
# ─────────────────────────────────────────────────────────────
RULES = {
    # 수면 회피 / 야간 자극 추구
    "INT-W130": lambda f: clamp01(0.10 + g(f, "Sleep Disturbance Index") / 100 * 0.5
                                   + g(f, "Digital Escape Score") / 100 * 0.25),
    # 즉각 스트레스 해소
    "INT-W210": lambda f: clamp01(0.10 + g(f, "Burnout Deep Score") / 100 * 0.45
                                   + g(f, "Fatigue Load Index") / 100 * 0.2),
    # 일탈·환경 전환 욕구
    "INT-W220": lambda f: clamp01(0.08 + g(f, "Recovery Motivation Score") / 100 * 0.4
                                   + g(f, "Isolation Tendency Index") / 100 * 0.2),
    # 신체 회복 시도
    "INT-W230": lambda f: clamp01(0.08 + g(f, "Recovery Motivation Score") / 100 * 0.35
                                   + (0.12 if g(f, "weekend_out") >= 2 else 0)),
    # 심리·감정 회복
    "INT-W240": lambda f: clamp01(0.08 + g(f, "Recovery Motivation Score") / 100 * 0.35
                                   + g(f, "Isolation Tendency Index") / 100 * 0.25),
    # 일상 회복
    "INT-W250": lambda f: clamp01(0.08 + g(f, "Recovery Motivation Score") / 100 * 0.3
                                   + (0.15 if g(f, "social_contact") >= 3 else 0)),
}

def rule_predict(intent_id: str, features: dict[str, Any]) -> float:
    return common.rule_predict(RULES, intent_id, features)


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
