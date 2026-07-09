from __future__ import annotations
"""
엔진 공유 메커니즘 (시나리오 무관).

- micro-helper: clamp / clamp01 / g
- Model 오케스트레이션: model_predict(...)        — 백엔드 predict + 휴리스틱 폴백
  (Rule 오케스트레이션은 formula.rule_predict — 선언형 spec 평가로 이전)

시나리오 차이(training_data/ranges/scale/invert)와 predictive_model(예측 모델 구현)은 인자로 주입한다.
특정 구현(sklearn/torch…)에 의존하지 않는다 — predictive_model은 models.get_predictive_model로 호출자가 해결.
"""
import math
from typing import Any


def recenter_logodds(p: float, base: float, strength: float = 1.0, eps: float = 1e-6) -> float:
    """base-rate 부분 보정으로 확률을 재중심화한다: logit(p) - strength·logit(base) → sigmoid.

    독립 분류기들을 base rate 기준으로 비교 가능하게 한다. strength=1이면 완전
    재중심화(p=base일 때 0.5), strength=0이면 무보정으로 p를 그대로 반환한다.

    Args:
        p: 보정할 확률(0~1).
        base: 기준이 되는 base rate(0~1).
        strength: 재중심화 강도. 1이면 완전, 0이면 무보정.
        eps: p를 (eps, 1-eps)로 클립하기 위한 경계값.

    Returns:
        재중심화된 확률(0~1). base/strength가 무효하면 p를 그대로 반환.
    """
    if base <= 0.0 or base >= 1.0 or strength <= 0.0:
        return p
    p = min(max(p, eps), 1.0 - eps)
    z = math.log(p / (1.0 - p)) - strength * math.log(base / (1.0 - base))
    return 1.0 / (1.0 + math.exp(-z))


# ── micro-helper ──────────────────────────────────────────────
def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    """v를 [lo, hi] 범위로 제한해 반환한다.

    Args:
        v: 제한할 값.
        lo: 하한.
        hi: 상한.

    Returns:
        [lo, hi]로 클램프된 값.
    """
    return max(lo, min(hi, v))


def clamp01(v: float) -> float:
    """v를 [0, 1] 범위로 제한해 반환한다(룰/Score 출력용).

    Args:
        v: 제한할 값.

    Returns:
        [0, 1]로 클램프된 값.
    """
    return clamp(v, 0.0, 1.0)


def g(f: dict, k: str, d: float = 0.0) -> float:
    """feature dict에서 k를 float로 안전 조회한다.

    값이 없거나 float 변환에 실패하면 기본값 d를 반환한다.

    Args:
        f: 조회할 feature dict.
        k: 조회할 키.
        d: 값이 없거나 변환 실패 시 반환할 기본값.

    Returns:
        float로 변환된 값 또는 기본값 d.
    """
    try:
        return float(f.get(k, d))
    except (TypeError, ValueError):
        return d


# ── Model 오케스트레이션 (raw predict + 휴리스틱 폴백) ─────────
def norm_feature(name: str, value: float, ranges: dict) -> float:
    """Model 휴리스틱용으로 feature 값을 0~1로 정규화한다.

    Index/Score 접미사면 100으로, ranges에 정의된 feature면 그 범위로, 그 외에는
    3.0 기준으로 정규화한다.

    Args:
        name: feature 이름.
        value: 정규화할 원본 값.
        ranges: feature 이름 → (lo, hi) 범위 매핑.

    Returns:
        0~1로 정규화된 값.
    """
    if name.endswith("Index") or name.endswith("Score"):
        return clamp(value) / 100
    if name in ranges:
        lo, hi = ranges[name]
        return max(0.0, min(1.0, (value - lo) / (hi - lo) if hi > lo else 0.0))
    return max(0.0, min(1.0, value / 3.0))


def model_heuristic(
    intent_id: str,
    features: dict[str, Any],
    *,
    training_data: dict,
    ranges: dict,
    scale: float,
    base: float = 0.04,
    invert: frozenset = frozenset(),
) -> float:
    """미학습 Model intent에 대한 휴리스틱 폴백 점수를 계산한다.

    학습 피처들을 0~1로 정규화한 평균에 scale을 곱하고 base를 더한다. invert에
    (intent_id, feature)가 있으면 해당 피처는 (1 - 정규화값)으로 역방향 반영한다.

    Args:
        intent_id: 점수를 계산할 intent id.
        features: 추론에 사용할 feature dict.
        training_data: intent별 학습 spec(features 키 포함).
        ranges: feature 정규화에 사용할 범위 매핑.
        scale: 정규화 평균에 곱할 스케일.
        base: 결과에 더할 기준값.
        invert: 역방향으로 반영할 (intent_id, feature) 쌍의 집합.

    Returns:
        0에 가까운 base~base+scale 범위의 휴리스틱 점수. spec/피처가 없으면 0.05.
    """
    spec = training_data.get(intent_id)
    if not spec:
        return 0.05
    vals = []
    for n in spec["features"]:
        v = norm_feature(n, g(features, n), ranges)
        if (intent_id, n) in invert:
            v = 1 - v
        vals.append(v)
    if not vals:
        return 0.05
    return round(base + (sum(vals) / len(vals)) * scale, 4)


def model_predict(
    intent_id: str,
    features: dict[str, Any],
    *,
    predictive_model: Any,
    training_data: dict,
    dataset_path,
    model_prefix: str,
    ranges: dict,
    scale: float,
    invert: frozenset = frozenset(),
    train_params: dict | None = None,
) -> float:
    """학습된 predictive_model로 추론하되, 불가하면 휴리스틱으로 폴백한다.

    dataset_path가 없거나 예측이 실패/0 이하이면 model_heuristic으로 폴백한다.
    predictive_model 구현은 호출자가 주입한다(sklearn/torch 등).

    Args:
        intent_id: 점수를 계산할 intent id.
        features: 추론에 사용할 feature dict.
        predictive_model: predict 메서드를 가진 예측 모델 구현.
        training_data: intent별 학습 spec.
        dataset_path: seed 데이터셋 경로. 없으면 휴리스틱으로 폴백.
        model_prefix: 모델 식별 prefix.
        ranges: 휴리스틱 정규화에 사용할 범위 매핑.
        scale: 휴리스틱 스케일.
        invert: 휴리스틱에서 역방향 반영할 (intent_id, feature) 쌍의 집합.
        train_params: 학습 하이퍼파라미터. 없으면 backend 기본값 사용.

    Returns:
        0~1 범위의 Model Intent 점수.
    """
    def heur():
        return model_heuristic(intent_id, features, training_data=training_data,
                               ranges=ranges, scale=scale, invert=invert)

    if not dataset_path.exists():
        return heur()
    try:
        p = predictive_model.predict(intent_id, features, training_data=training_data,
                                     dataset_path=dataset_path, model_prefix=model_prefix,
                                     train_params=train_params)
        return p if p > 0.0 else heur()
    except Exception:
        return heur()
