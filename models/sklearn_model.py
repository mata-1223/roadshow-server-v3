from __future__ import annotations
"""
Model-based Intent Inference ([2b] 모듈)

시나리오 무관 sklearn Logistic Regression 추론 머신러리.
- 학습 데이터(training_data)·dataset_path·model_prefix는 호출자(시나리오 엔진)가 주입
- StandardScaler + LogisticRegression Pipeline
- MLflow Registry 등록 (모델명: {model_prefix}{intent_id}_sklearn)
- seed 고정 (42)으로 재현성 확보
"""
import json
import logging
import random
from pathlib import Path
from typing import Any

import numpy as np
import mlflow
import mlflow.sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

from config import settings

logger = logging.getLogger(__name__)
_model_cache: dict[str, Any] = {}


# ── Public API ────────────────────────────────────────────────

def _train_pipeline(X: list, y: list, seed: int = 42, train_params: dict | None = None) -> Pipeline:
    """StandardScaler + LogisticRegression 파이프라인을 학습한다.

    seed를 고정하여 재현성을 확보한다.

    Args:
        X: 특징 행렬.
        y: 레이블 벡터.
        seed: 난수 시드 (재현성).
        train_params: 시나리오 config L2.model.train의 하이퍼파라미터.
            class_weight·C를 override 가능 (기본 balanced·C=1.0).

    Returns:
        학습된 sklearn Pipeline.
    """
    tp = train_params or {}
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(
            random_state=seed,
            max_iter=500,
            C=tp.get("C", 1.0),
            class_weight=tp.get("class_weight", "balanced"),
        )),
    ])
    pipe.fit(np.array(X, dtype=float), np.array(y))
    return pipe


def _extract_from_dataset(
    intent_id: str,
    feature_names: list[str],
    seed: int,
    dataset_path: Path,
    neg_pos_ratio: float = 2.0,
) -> tuple[list[list[float]], list[int]] | None:
    """seed_dataset.json에서 intent_id에 대한 (X, y)를 추출한다.

    양성은 sample["intent_labels"]에 intent_id가 있는 경우(y=1), 음성은 그 외(y=0)이다.
    클래스 불균형 처리를 위해 음성은 neg_pos_ratio × n_pos 까지만 샘플링한다.

    Args:
        intent_id: 추출할 Intent ID.
        feature_names: feature 벡터를 구성할 feature 이름 순서.
        seed: 음성 샘플링에 사용할 난수 시드.
        dataset_path: seed_dataset.json 경로.
        neg_pos_ratio: 양성 대비 음성 샘플 비율 상한.

    Returns:
        (X, y) 튜플. 양성·음성이 각각 3건 미만이거나 데이터셋이 없으면 None.
    """
    if not dataset_path.exists():
        return None
    try:
        with open(dataset_path, encoding="utf-8") as f:
            dataset = json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load seed_dataset.json: {e}")
        return None

    X_pos, X_neg = [], []
    for sample in dataset.get("samples", []):
        # batch + pattern + event 를 합친 전체 feature 벡터 (추론 시점과 동일 공간)
        feats = {
            **sample.get("batch_features", {}),
            **sample.get("pattern_features", {}),
            **sample.get("event_features", {}),
        }
        x = [float(feats.get(name, 0.0)) for name in feature_names]
        if intent_id in sample.get("intent_labels", {}):
            X_pos.append(x)
        else:
            X_neg.append(x)

    if len(X_pos) < 3 or len(X_neg) < 3:
        return None

    rng = random.Random(seed)
    n_neg_target = min(len(X_neg), max(int(len(X_pos) * neg_pos_ratio), 10))
    X_neg_sampled = rng.sample(X_neg, n_neg_target) if len(X_neg) > n_neg_target else X_neg

    X = X_pos + X_neg_sampled
    y = [1] * len(X_pos) + [0] * len(X_neg_sampled)
    return X, y


def train_and_register(
    intent_id: str,
    training_data: dict,
    dataset_path: Path,
    model_prefix: str,
    seed: int = 42,
    train_params: dict | None = None,
) -> Pipeline | None:
    """Intent의 학습 데이터로 모델을 학습하고 MLflow에 등록한다.

    데이터 소스 우선순위:
      1) dataset_path(seed_dataset.json)의 페르소나 시드 데이터셋
      2) training_data[intent_id]의 도메인 지식 X, y

    Args:
        intent_id: 학습할 Intent ID.
        training_data: Intent별 학습 정의(features·X·y 등).
        dataset_path: seed_dataset.json 경로.
        model_prefix: 시나리오별 MLflow 모델명 네임스페이스.
            등록명은 {model_prefix}{intent_id}_sklearn.
        seed: 난수 시드 (재현성).
        train_params: 학습 하이퍼파라미터(class_weight/C).

    Returns:
        학습된 Pipeline. 학습 데이터가 없으면 None.
    """
    data = training_data.get(intent_id)
    if data is None:
        return None

    feature_names = data["features"]
    model_name = f"{model_prefix}{intent_id}_sklearn"

    # 1) 시드 데이터셋 우선
    extracted = _extract_from_dataset(intent_id, feature_names, seed, dataset_path)
    if extracted is not None:
        X, y = extracted
        data_source = "seed_dataset"
    elif "X" in data and "y" in data:
        X, y = data["X"], data["y"]
        data_source = "domain_knowledge"
    else:
        return None

    pipe = _train_pipeline(X, y, seed=seed, train_params=train_params)

    mlflow.set_tracking_uri(settings.MLFLOW_URI)
    with mlflow.start_run(run_name=f"{model_name}_init"):
        mlflow.sklearn.log_model(
            pipe,
            "model",
            registered_model_name=model_name,
        )
        mlflow.log_params({
            "intent_id":     intent_id,
            "n_features":    len(feature_names),
            "n_samples":     len(y),
            "n_positive":    int(sum(y)),
            "seed":          seed,
            "data_source":   data_source,
            "feature_names": ",".join(feature_names),
        })
        train_acc = pipe.score(np.array(X, dtype=float), np.array(y))
        mlflow.log_metric("train_accuracy", train_acc)

    logger.info(f"Trained + registered: {model_name} "
                f"(source={data_source}, n={len(y)}, pos={int(sum(y))}, acc={train_acc:.3f})")
    return pipe


def _load_or_train(
    intent_id: str,
    training_data: dict,
    dataset_path: Path,
    model_prefix: str,
    train_params: dict | None = None,
) -> Pipeline | None:
    """모델을 캐시→MLflow Registry 순으로 로드하고, 없으면 학습·등록한다.

    프로세스 캐시(_model_cache)를 사용해 intent별로 1회만 로드/학습한다.

    Args:
        intent_id: 로드/학습할 Intent ID.
        training_data: Intent별 학습 정의.
        dataset_path: seed_dataset.json 경로.
        model_prefix: 시나리오별 MLflow 모델명 네임스페이스.
        train_params: 학습 하이퍼파라미터.

    Returns:
        로드 또는 학습된 Pipeline. 학습 정의가 없으면 None.
    """
    cache_key = f"{model_prefix}{intent_id}"
    if cache_key in _model_cache:
        return _model_cache[cache_key]

    if intent_id not in training_data:
        return None

    mlflow.set_tracking_uri(settings.MLFLOW_URI)
    uri = f"models:/{model_prefix}{intent_id}_sklearn/latest"
    try:
        pipe = mlflow.sklearn.load_model(uri)
    except Exception:
        pipe = train_and_register(
            intent_id, training_data=training_data,
            dataset_path=dataset_path, model_prefix=model_prefix,
            train_params=train_params,
        )

    _model_cache[cache_key] = pipe
    return pipe


def predict(
    intent_id: str,
    features: dict[str, Any],
    training_data: dict,
    dataset_path: Path,
    model_prefix: str,
    train_params: dict | None = None,
) -> float:
    """Intent ID에 대해 Model 기반 Score를 추론한다.

    features dict에서 학습에 사용된 피처들을 순서대로 추출하며,
    누락된 피처는 0.0으로 처리한다.

    Args:
        intent_id: 추론할 Intent ID.
        features: 추론에 사용할 feature dict.
        training_data: Intent별 학습 정의(시나리오 엔진 제공).
        dataset_path: seed_dataset.json 경로(시나리오 엔진 제공).
        model_prefix: 시나리오별 모델명 네임스페이스(시나리오 엔진 제공).
        train_params: 학습 하이퍼파라미터(class_weight/C, config L2.model.train).

    Returns:
        0~1 범위의 예측 점수. 모델이 없으면 0.0.
    """
    pipe = _load_or_train(intent_id, training_data, dataset_path, model_prefix, train_params)
    if pipe is None:
        return 0.0

    feature_names = training_data[intent_id]["features"]
    x = np.array([[float(features.get(name, 0.0)) for name in feature_names]])

    proba = pipe.predict_proba(x)[0][1]
    return float(proba)


def explain(
    intent_id: str,
    features: dict[str, Any],
    training_data: dict,
    dataset_path: Path,
    model_prefix: str,
    top: int = 3,
) -> list[dict]:
    """Model 추론의 feature 기여도를 분해한다.

    선형 파이프라인(StandardScaler + LogisticRegression)에서
    기여_i = coef_i × ((x_i - mean_i) / scale_i)로 계산하고,
    |기여| 상위 top개를 반환한다.

    Args:
        intent_id: 기여도를 분해할 Intent ID.
        features: 추론에 사용한 feature dict.
        training_data: Intent별 학습 정의.
        dataset_path: seed_dataset.json 경로.
        model_prefix: 시나리오별 모델명 네임스페이스.
        top: 반환할 상위 기여 feature 개수.

    Returns:
        feature별 기여 정보(label·contribution·direction·value) dict의 목록.
        모델이 없거나 분해에 실패하면 빈 목록.
    """
    pipe = _load_or_train(intent_id, training_data, dataset_path, model_prefix)
    if pipe is None or intent_id not in training_data:
        return []
    feats = training_data[intent_id]["features"]
    x = np.array([float(features.get(n, 0.0)) for n in feats])
    try:
        scaler = pipe.named_steps["scaler"]
        lr = pipe.named_steps["lr"]
        xs = (x - scaler.mean_) / scaler.scale_
        contrib = lr.coef_[0] * xs
    except Exception:
        return []
    items = sorted(zip(feats, contrib, x), key=lambda t: -abs(t[1]))[:top]
    return [{"label": n, "contribution": round(float(c), 4),
             "direction": "up" if c >= 0 else "down", "value": round(float(v), 2)}
            for n, c, v in items]


def train_all(
    training_data: dict,
    dataset_path: Path,
    model_prefix: str,
    seed: int = 42,
) -> dict[str, float]:
    """training_data의 모든 Model Intent를 학습·등록한다.

    Args:
        training_data: Intent별 학습 정의.
        dataset_path: seed_dataset.json 경로.
        model_prefix: 시나리오별 MLflow 모델명 네임스페이스.
        seed: 난수 시드 (재현성).

    Returns:
        학습에 성공한 Intent에 대한 {intent_id: 1.0} 매핑.
    """
    results = {}
    for intent_id in training_data.keys():
        pipe = train_and_register(
            intent_id, training_data=training_data, seed=seed,
            dataset_path=dataset_path, model_prefix=model_prefix,
        )
        if pipe is not None:
            results[intent_id] = 1.0
    return results
