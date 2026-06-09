from __future__ import annotations
"""
Intent Inference 통합 ([2] reference Layer)

흐름:
  - infer_batch(survey)  : Batch Feature만으로 baseline Intent Score 산출
  - infer_with_behavior  : Batch + Behavioral Pattern Feature를 합쳐 재추론
                          (boost 누적 방식이 아니라, 모든 피처를 입력으로 다시 모델/룰을 통과시킴)

산출되는 IntentScore는 baseline 대비 변화량(delta_score, rank_change)을 함께 보관한다.
"""
import logging
import math
from dataclasses import dataclass
from typing import Any

# Softmax 분포 sharpness 조절. 작을수록 Top 점수에 분포가 집중.
# T=0.15 → 시연 임팩트(상위 Intent 강조) 우선. Top 5가 분포의 ~60% 점유, 행동 1번에 Δp 수%p
PROBABILITY_TEMPERATURE = 0.15

import json
from pathlib import Path

from config import settings
from core.builder import build_batch_features
from core.event_extractor import extract as extract_event_features
from core.extractor import get_extractor
from data.seed import load_intents_catalog
from models import rule_model, sklearn_model

logger = logging.getLogger(__name__)

# 행동 → 직접 신호 Intent 부스트.
# Rule pattern_boost가 일부 행동만 커버하는 한계를 보완해, behaviors.json의 모든 행동이
# 의미상 연결된 Intent를 끌어올리도록 한다. (final 재추론에만 적용; baseline은 batch만)
ACTION_SIGNAL_SCALE = 0.28   # 행동 1회당 가산
ACTION_SIGNAL_CAP   = 0.55   # 행동 반복 시 상한

_SCENARIO_DIR = Path(__file__).parent.parent / "scenarios" / settings.SCENARIO_ID
_behavior_intent_cache: dict[str, list[str]] | None = None


def _behavior_intent_map() -> dict[str, list[str]]:
    global _behavior_intent_cache
    if _behavior_intent_cache is None:
        try:
            with open(_SCENARIO_DIR / "behavior_intents.json", encoding="utf-8") as f:
                _behavior_intent_cache = json.load(f).get("entity_intents", {})
        except FileNotFoundError:
            _behavior_intent_cache = {}
    return _behavior_intent_cache


def _action_intent_signals(events: list[dict]) -> dict[str, int]:
    """세션 누적 행동에서 entity→intent 매핑으로 직접 신호 카운트 산출."""
    m = _behavior_intent_map()
    counts: dict[str, int] = {}
    for ev in events:
        for iid in m.get(ev.get("entity", ""), []):
            counts[iid] = counts.get(iid, 0) + 1
    return counts


@dataclass
class IntentScore:
    intent_id:       str
    intent_name:     str
    L1_id:           str
    L1_name:         str
    L2_id:           str
    L2_name:         str
    inference_type:  str
    baseline_score:  float   # Batch Feature만으로 추론한 점수
    final_score:     float   # Batch + Behavioral Pattern Feature 합쳐 재추론한 점수
    delta_score:     float   # final - baseline
    baseline_rank:   int     # baseline 기준 rank
    rank:            int     # final_score 기준 rank
    rank_change:     int     # baseline_rank - rank (양수면 상승)


_intents_cache: list[dict] | None = None


def _intents() -> list[dict]:
    global _intents_cache
    if _intents_cache is None:
        _intents_cache = load_intents_catalog()
    return _intents_cache


def infer_batch(survey_answers: dict[str, str]) -> tuple[dict[str, Any], list[IntentScore]]:
    """
    설문 답변만으로 baseline Intent Score 산출 (행동 전).
    """
    batch_features = build_batch_features(survey_answers)
    pattern_features = _empty_pattern_features()
    event_features = _empty_event_features()
    all_features = {**batch_features, **pattern_features, **event_features}

    raw = _score_all(all_features)
    scores = _to_intent_scores(raw, raw)
    return batch_features, scores


def infer_with_behavior(
    survey_answers: dict[str, str],
    session_id: str,
) -> tuple[dict[str, Any], list[IntentScore]]:
    """
    Batch Feature + 누적 Behavioral Pattern Feature + 최신 Event Feature를 합쳐 재추론.

    baseline(행동 없는 상태) 점수를 함께 산출해 delta_score / rank_change를 채운다.
    """
    batch_features = build_batch_features(survey_answers)

    # baseline: Pattern/Event Feature를 0으로 둔 상태
    baseline_features = {
        **batch_features,
        **_empty_pattern_features(),
        **_empty_event_features(),
    }
    baseline_raw = _score_all(baseline_features)

    # final: 실제 누적 Pattern + 최신 Event Feature 반영
    extractor = get_extractor()
    pattern_features = extractor.get_pattern_features(session_id)
    events = extractor._events_by_session.get(session_id, [])
    if events:
        last = events[-1]
        event_features = extract_event_features(
            last["event_type"], last["entity"], last.get("occurred_at"),
        )
    else:
        event_features = _empty_event_features()

    combined_features = {**batch_features, **pattern_features, **event_features}
    final_raw = _score_all(combined_features)

    # 행동이 직접 가리키는 Intent를 끌어올림 (final 에만 적용 → Δ·rank_change가 행동에 귀속)
    for iid, cnt in _action_intent_signals(events).items():
        if iid in final_raw:
            boost = min(cnt * ACTION_SIGNAL_SCALE, ACTION_SIGNAL_CAP)
            final_raw[iid] = min(final_raw[iid] + boost, 0.97)

    scores = _to_intent_scores(baseline_raw, final_raw)
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
        "mnp_benefit_check":        0,
        "할인 페이지 체류":         0,
    }


def _empty_event_features() -> dict[str, Any]:
    return {
        "last_event_type":  "",
        "last_entity":      "",
        "current_page":     "",
        "is_click":         0,
        "is_page_view":     0,
        "is_support_entry": 0,
        "is_churn_signal":  0,
        "is_confirm":       0,
        "last_event_at":    "",
    }


def _score_all(features: dict[str, Any]) -> dict[str, float]:
    """모든 Intent에 대해 점수만 산출 (intent_id → score)."""
    f = dict(features)
    if isinstance(f.get("결합 여부"), bool):
        f["결합 여부"] = 1 if f["결합 여부"] else 0

    out: dict[str, float] = {}
    for intent in _intents():
        iid = intent["id"]
        itype = intent["inference_type"]
        if itype == "Model":
            score = sklearn_model.predict(iid, f)
        else:
            score = rule_model.predict(iid, f)
        out[iid] = float(score)
    return out


def _rank_map(raw: dict[str, float]) -> dict[str, int]:
    ordered = sorted(raw.items(), key=lambda kv: kv[1], reverse=True)
    return {iid: i for i, (iid, _) in enumerate(ordered, start=1)}


def _to_intent_scores(
    baseline_raw: dict[str, float],
    final_raw: dict[str, float],
) -> list[IntentScore]:
    baseline_ranks = _rank_map(baseline_raw)
    final_ranks    = _rank_map(final_raw)

    results: list[IntentScore] = []
    for intent in _intents():
        iid = intent["id"]
        b = baseline_raw.get(iid, 0.0)
        f = final_raw.get(iid, 0.0)
        br = baseline_ranks.get(iid, 0)
        fr = final_ranks.get(iid, 0)
        results.append(IntentScore(
            intent_id=iid,
            intent_name=intent["name"],
            L1_id=intent["L1_id"],
            L1_name=intent["L1_name"],
            L2_id=intent["L2_id"],
            L2_name=intent["L2_name"],
            inference_type=intent["inference_type"],
            baseline_score=round(b, 4),
            final_score=round(f, 4),
            delta_score=round(f - b, 4),
            baseline_rank=br,
            rank=fr,
            rank_change=br - fr,
        ))

    results.sort(key=lambda s: s.final_score, reverse=True)
    return results


# ── WebSocket 페이로드 헬퍼 ───────────────────────────────────

def _softmax(values: list[float], temperature: float) -> list[float]:
    """Numerically stable softmax (raw score → 정규화 확률 분포)."""
    if not values:
        return []
    scaled = [v / temperature for v in values]
    m = max(scaled)
    exps = [math.exp(s - m) for s in scaled]
    total = sum(exps) or 1.0
    return [e / total for e in exps]


def to_probability_dict(
    scores: list[IntentScore],
    temperature: float = PROBABILITY_TEMPERATURE,
) -> dict[str, dict[str, float]]:
    """
    113개 Intent raw score → softmax 정규화 확률(p) + baseline 정규화 확률(p0).

    raw score 합 분모 정규화는 분포가 너무 평탄해 시연 임팩트가 약하므로
    softmax(score / T) 분포를 사용. T가 작을수록 상위 Intent에 분포가 집중된다.

    Vector Space 시각화([1-2]) 가중 평균 위치 계산에 사용.
    INTENT_UPDATE 페이로드의 `all_probabilities` 필드.
    """
    p_vals  = _softmax([s.final_score    for s in scores], temperature)
    p0_vals = _softmax([s.baseline_score for s in scores], temperature)
    return {
        s.intent_id: {
            "p":  round(p_vals[i],  6),
            "p0": round(p0_vals[i], 6),
        }
        for i, s in enumerate(scores)
    }


def to_topn_with_others(
    scores: list[IntentScore],
    top_n: int = 5,
) -> tuple[list[dict], dict]:
    """
    Top-N + 기타(others) 페이로드 구성.

    Returns
    -------
    (top_list, others)
        top_list : [ {intent_id, ..., probability, baseline_probability, delta_probability} ]
        others   : { count, probability, baseline_probability, delta_probability }
    """
    probs = to_probability_dict(scores)
    sorted_scores = sorted(scores, key=lambda s: s.final_score, reverse=True)

    top_items: list[dict] = []
    for s in sorted_scores[:top_n]:
        pr = probs[s.intent_id]
        top_items.append({
            "intent_id":            s.intent_id,
            "intent_nm_ko":         s.intent_name,
            "L1_id":                s.L1_id,
            "L1_name":              s.L1_name,
            "L2_id":                s.L2_id,
            "L2_name":              s.L2_name,
            "inference_type":       s.inference_type,
            "rank":                 s.rank,
            "baseline_rank":        s.baseline_rank,
            "rank_change":          s.rank_change,
            "probability":          pr["p"],
            "baseline_probability": pr["p0"],
            "delta_probability":    round(pr["p"] - pr["p0"], 6),
        })

    rest = sorted_scores[top_n:]
    others_p  = sum(probs[s.intent_id]["p"]  for s in rest)
    others_p0 = sum(probs[s.intent_id]["p0"] for s in rest)
    others = {
        "count":                len(rest),
        "probability":          round(others_p,  6),
        "baseline_probability": round(others_p0, 6),
        "delta_probability":    round(others_p - others_p0, 6),
    }
    return top_items, others


# ── Customer Context JSON 생성 ────────────────────────────────

def to_customer_context_json(
    session_id: str,
    stage: str,
    scenario_id: str,
    scores: list[IntentScore],
    batch_features: dict[str, Any],
) -> dict[str, Any]:
    intents = []
    for s in scores:
        intents.append({
            "intent_id":         s.intent_id,
            "intent_nm_ko":      s.intent_name,
            "L1":                {"id": s.L1_id, "name": s.L1_name},
            "L2":                {"id": s.L2_id, "name": s.L2_name},
            "baseline_score":    s.baseline_score,
            "final_score":       s.final_score,
            "delta_score":       s.delta_score,
            "baseline_rank":     s.baseline_rank,
            "rank":              s.rank,
            "rank_change":       s.rank_change,
            "inference_type":    s.inference_type,
        })

    return {
        "session_id":       session_id,
        "scenario_id":      scenario_id,
        "stage":            stage,
        "intents":          intents,
    }
