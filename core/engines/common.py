from __future__ import annotations
"""
엔진 공유 메커니즘 (시나리오 무관).

- micro-helper: clamp / clamp01 / g
- Model 오케스트레이션: model_predict(...)        — 백엔드 predict + 휴리스틱 폴백
  (Rule 오케스트레이션은 formula.rule_predict — 선언형 spec 평가로 이전)

시나리오 차이(training_data/ranges/scale/invert)와 ML 백엔드(backend)는 인자로 주입한다.
특정 ML 구현(sklearn/torch…)에 의존하지 않는다 — 백엔드는 models.get_backend로 호출자가 해결.
"""
from typing import Any


# ── micro-helper ──────────────────────────────────────────────
def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def clamp01(v: float) -> float:
    return clamp(v, 0.0, 1.0)


def g(f: dict, k: str, d: float = 0.0) -> float:
    try:
        return float(f.get(k, d))
    except (TypeError, ValueError):
        return d


# ── Model 오케스트레이션 (raw predict + 휴리스틱 폴백) ─────────
def norm_feature(name: str, value: float, ranges: dict) -> float:
    """Model 휴리스틱용 0~1 정규화."""
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
    backend: Any,
    training_data: dict,
    dataset_path,
    model_prefix: str,
    ranges: dict,
    scale: float,
    invert: frozenset = frozenset(),
) -> float:
    """학습된 모델(backend.predict) 우선, 없으면 휴리스틱 폴백. backend는 호출자가 주입(sklearn/torch…)."""
    def heur():
        return model_heuristic(intent_id, features, training_data=training_data,
                               ranges=ranges, scale=scale, invert=invert)

    if not dataset_path.exists():
        return heur()
    try:
        p = backend.predict(intent_id, features, training_data=training_data,
                            dataset_path=dataset_path, model_prefix=model_prefix)
        return p if p > 0.0 else heur()
    except Exception:
        return heur()
