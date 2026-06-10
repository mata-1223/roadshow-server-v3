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

from config import settings
from core.engines import get_engine
from core.extractor import get_extractor

logger = logging.getLogger(__name__)

# 행동 → 직접 신호 Intent 부스트.
# Rule pattern_boost가 일부 행동만 커버하는 한계를 보완해, behaviors.json의 모든 행동이
# 의미상 연결된 Intent를 끌어올리도록 한다. (final 재추론에만 적용; baseline은 batch만)
ACTION_SIGNAL_SCALE = 0.28   # 최신 행동 1회당 가산 (weight=1.0 기준)
ACTION_SIGNAL_CAP   = 0.55   # 행동 반복 시 상한
ACTION_SIGNAL_DECAY = 0.6    # 위치 기반 recency 감쇠 (최신 age=0 → 1.0, 직전 0.6, 그전 0.36 …)


def _action_intent_signals(events: list[dict], behavior_map: dict[str, list[str]]) -> dict[str, float]:
    """
    세션 누적 행동 → entity→intent 매핑으로 의도별 가중 신호 산출.

    - recency decay: 최신 행동일수록 큰 weight (DECAY^age). 방금 한 행동이 현재 의도를 주도하되,
      같은 행동 반복은 누적되어 강해진다(과거도 0으로 죽이진 않음).
    - BACK(navigate_back)은 메뉴 복귀용 순수 내비게이션 → 신호·aging 모두에서 제외(무효과).
      섹션을 떠난 행동은 이후 다른 행동이 쌓이며 decay로 자연 소멸한다.
    """
    real = [ev for ev in events if ev.get("event_type") != "navigate_back"]
    n = len(real)

    weights: dict[str, float] = {}
    for i, ev in enumerate(real):
        age = (n - 1) - i
        w = ACTION_SIGNAL_DECAY ** age
        for iid in behavior_map.get(ev.get("entity", ""), []):
            weights[iid] = weights.get(iid, 0.0) + w
    return weights


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


def infer_batch(
    survey_answers: dict[str, str],
    scenario_id: str = settings.SCENARIO_ID,
) -> tuple[dict[str, Any], list[IntentScore]]:
    """
    설문 답변만으로 baseline Intent Score 산출 (행동 전).
    """
    engine = get_engine(scenario_id)
    batch_features = engine.build_batch_features(survey_answers)
    all_features = {
        **batch_features,
        **engine.empty_pattern_features(),
        **engine.empty_event_features(),
    }

    raw = _score_all(all_features, engine)
    scores = _to_intent_scores(raw, raw, engine)
    return batch_features, scores


def infer_with_behavior(
    survey_answers: dict[str, str],
    session_id: str,
    scenario_id: str = settings.SCENARIO_ID,
) -> tuple[dict[str, Any], list[IntentScore]]:
    """
    Batch Feature + 누적 Behavioral Pattern Feature + 최신 Event Feature를 합쳐 재추론.

    baseline(행동 없는 상태) 점수를 함께 산출해 delta_score / rank_change를 채운다.
    """
    engine = get_engine(scenario_id)
    batch_features = engine.build_batch_features(survey_answers)

    # baseline: Pattern/Event Feature를 0으로 둔 상태
    baseline_features = {
        **batch_features,
        **engine.empty_pattern_features(),
        **engine.empty_event_features(),
    }
    baseline_raw = _score_all(baseline_features, engine)

    # final: 실제 누적 Pattern + 최신 Event Feature 반영 (엔진 전용 계산)
    pattern_features = engine.pattern_features(session_id)
    event_features = engine.event_features(session_id)
    events = get_extractor()._events_by_session.get(session_id, [])

    combined_features = {**batch_features, **pattern_features, **event_features}
    final_raw = _score_all(combined_features, engine)

    # 행동이 직접 가리키는 Intent를 끌어올림 (final 에만 적용 → Δ·rank_change가 행동에 귀속)
    behavior_map = engine.behavior_intent_map()
    for iid, cnt in _action_intent_signals(events, behavior_map).items():
        if iid in final_raw:
            boost = min(cnt * ACTION_SIGNAL_SCALE, ACTION_SIGNAL_CAP)
            final_raw[iid] = min(final_raw[iid] + boost, 0.97)

    scores = _to_intent_scores(baseline_raw, final_raw, engine)
    return batch_features, scores


def _score_all(features: dict[str, Any], engine) -> dict[str, float]:
    """모든 Intent에 대해 점수만 산출 (intent_id → score)."""
    f = dict(features)
    if isinstance(f.get("결합 여부"), bool):
        f["결합 여부"] = 1 if f["결합 여부"] else 0

    out: dict[str, float] = {}
    for intent in engine.intents():
        iid = intent["id"]
        if intent["inference_type"] == "Model":
            score = engine.model_predict(iid, f)
        else:
            score = engine.rule_predict(iid, f)
        out[iid] = float(score)
    return out


def _rank_map(raw: dict[str, float]) -> dict[str, int]:
    ordered = sorted(raw.items(), key=lambda kv: kv[1], reverse=True)
    return {iid: i for i, (iid, _) in enumerate(ordered, start=1)}


def _to_intent_scores(
    baseline_raw: dict[str, float],
    final_raw: dict[str, float],
    engine,
) -> list[IntentScore]:
    baseline_ranks = _rank_map(baseline_raw)
    final_ranks    = _rank_map(final_raw)

    results: list[IntentScore] = []
    for intent in engine.intents():
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
