from __future__ import annotations
"""
Intent Inference 통합 ([2] reference Layer)

- 116개 Intent에 대해 Rule 또는 Model로 추론
- batch_score + realtime_boost = final_score 산출
- Top-N + 전체 결과 분리
"""
import json
import logging
from dataclasses import dataclass
from typing import Any

from config import settings
from core.builder import build_batch_features
from core.extractor import get_extractor
from data.seed import load_intents_catalog, load_behaviors_catalog
from models import rule_model, sklearn_model

logger = logging.getLogger(__name__)


@dataclass
class IntentScore:
    intent_id:       str
    intent_name:     str
    L1_id:           str
    L1_name:         str
    L2_id:           str
    L2_name:         str
    inference_type:  str
    batch_score:     float
    realtime_boost:  float
    final_score:     float
    rank:            int


_intents_cache: list[dict] | None = None


def _intents() -> list[dict]:
    global _intents_cache
    if _intents_cache is None:
        _intents_cache = load_intents_catalog()
    return _intents_cache


def infer_batch(survey_answers: dict[str, str]) -> tuple[dict[str, Any], list[IntentScore]]:
    """
    설문 답변만으로 Base Intent Score 산출 (행동 전).

    Returns
    -------
    (batch_features, intent_scores)
        batch_features : Builder가 산출한 26+ 피처 dict
        intent_scores  : 116개 IntentScore (final_score 내림차순)
    """
    batch_features = build_batch_features(survey_answers)
    # 행동 관련 피처는 0으로 초기화
    pattern_features = _empty_pattern_features()
    all_features = {**batch_features, **pattern_features}

    scores = _infer_all(all_features)
    return batch_features, scores


def infer_with_behavior(
    survey_answers: dict[str, str],
    session_id: str,
) -> tuple[dict[str, Any], list[IntentScore]]:
    """
    설문 + 누적 행동(Behavioral Pattern Extractor)을 결합하여 추론.

    매 행동 이후 호출.
    """
    batch_features = build_batch_features(survey_answers)
    pattern_features = get_extractor().get_pattern_features(session_id)
    all_features = {**batch_features, **pattern_features}

    scores = _infer_all(all_features)

    # 행동 boost 적용
    behaviors = load_behaviors_catalog()
    session_events = _get_session_event_history(session_id)
    boost_map = _accumulate_boosts(session_events, behaviors)

    # boost 적용
    for s in scores:
        s.realtime_boost = boost_map.get(s.intent_id, 0.0)
        s.final_score = min(1.0, max(0.0, s.batch_score + s.realtime_boost))

    # 재정렬
    scores.sort(key=lambda s: s.final_score, reverse=True)
    for i, s in enumerate(scores, start=1):
        s.rank = i

    return batch_features, scores


def _empty_pattern_features() -> dict[str, Any]:
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
        "경쟁사 비교 행동":         0,
        "경쟁사 탐색 행동":         0,
        "할인 페이지 체류":         0,
    }


def _infer_all(features: dict[str, Any]) -> list[IntentScore]:
    """116개 Intent 모두에 대해 Score 산출"""
    # Boolean 필드를 0/1로 변환 (Model 입력용)
    f = dict(features)
    if isinstance(f.get("결합 여부"), bool):
        f["결합 여부"] = 1 if f["결합 여부"] else 0

    results: list[IntentScore] = []
    for intent in _intents():
        iid = intent["id"]
        itype = intent["inference_type"]

        if itype == "Model":
            score = sklearn_model.predict(iid, f)
        else:
            score = rule_model.predict(iid, f)

        results.append(IntentScore(
            intent_id=iid,
            intent_name=intent["name"],
            L1_id=intent["L1_id"],
            L1_name=intent["L1_name"],
            L2_id=intent["L2_id"],
            L2_name=intent["L2_name"],
            inference_type=itype,
            batch_score=round(score, 4),
            realtime_boost=0.0,
            final_score=round(score, 4),
            rank=0,
        ))

    results.sort(key=lambda s: s.final_score, reverse=True)
    for i, s in enumerate(results, start=1):
        s.rank = i

    return results


def _get_session_event_history(session_id: str) -> list[dict]:
    """세션의 누적 이벤트 (Extractor 내부 history 활용)"""
    extractor = get_extractor()
    # Extractor 내부 events 직접 참조 (5분 window이 아닌 누적 전체)
    return extractor._events_by_session.get(session_id, [])


def _accumulate_boosts(events: list[dict], behaviors: dict[str, dict]) -> dict[str, float]:
    """
    이벤트 히스토리에서 누적 boost 산출.

    behaviors.json의 boosts 값을 누적 적용 (entity → behavior_id 매칭).
    """
    entity_to_behavior = {b["entity"]: bid for bid, b in behaviors.items()}

    boost_map: dict[str, float] = {}
    for ev in events:
        bid = entity_to_behavior.get(ev["entity"])
        if bid is None:
            continue
        for intent_id, delta in behaviors[bid]["boosts"].items():
            boost_map[intent_id] = boost_map.get(intent_id, 0.0) + float(delta)
    return boost_map


# ── Customer Context JSON 생성 ────────────────────────────────

def to_customer_context_json(
    session_id: str,
    stage: str,
    scenario_id: str,
    scores: list[IntentScore],
    batch_features: dict[str, Any],
) -> dict[str, Any]:
    """
    추론 결과 → Customer Context JSON (DB 적재용).
    """
    intents = []
    for s in scores:
        intents.append({
            "intent_id":         s.intent_id,
            "intent_nm_ko":      s.intent_name,
            "L1":                {"id": s.L1_id, "name": s.L1_name},
            "L2":                {"id": s.L2_id, "name": s.L2_name},
            "batch_score":       s.batch_score,
            "realtime_boost":    s.realtime_boost,
            "final_score":       s.final_score,
            "rank":              s.rank,
            "inference_type":    s.inference_type,
        })

    return {
        "session_id":       session_id,
        "scenario_id":      scenario_id,
        "stage":            stage,
        "intents":          intents,
    }
