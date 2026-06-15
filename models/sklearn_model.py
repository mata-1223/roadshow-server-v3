from __future__ import annotations
"""
Model-based Intent Inference ([2b] reference 모듈)

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

def _train_pipeline(X: list, y: list, seed: int = 42) -> Pipeline:
    """StandardScaler + LogisticRegression 학습 (seed 고정)"""
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(
            random_state=seed,
            max_iter=500,
            C=1.0,
            class_weight="balanced",
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
    """
    seed_dataset.json에서 intent_id에 대한 (X, y) 추출.

    - 양성: sample["intent_labels"]에 intent_id가 있는 경우 (y=1)
    - 음성: 그 외 (y=0)
    - 클래스 불균형 처리: 음성을 neg_pos_ratio × n_pos 까지만 샘플링
    - 양성/음성 둘 다 3건 이상일 때만 반환, 아니면 None
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
) -> Pipeline | None:
    """
    Intent의 학습 데이터로 모델 학습 + MLflow 등록.

    데이터 소스 우선순위:
      1) dataset_path(seed_dataset.json)의 페르소나 시드 데이터셋
      2) training_data[intent_id]의 도메인 지식 X, y

    model_prefix: 시나리오별 MLflow 모델명 네임스페이스. 등록명 = {prefix}{intent_id}_sklearn
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
        data_source = "persona_dataset"
    elif "X" in data and "y" in data:
        X, y = data["X"], data["y"]
        data_source = "domain_knowledge"
    else:
        return None

    pipe = _train_pipeline(X, y, seed=seed)

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
) -> Pipeline | None:
    """캐시→MLflow Registry 로드, 없으면 train_and_register. (프로세스 캐시로 1회만 로드/학습)"""
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
        )

    _model_cache[cache_key] = pipe
    return pipe


def predict(
    intent_id: str,
    features: dict[str, Any],
    training_data: dict,
    dataset_path: Path,
    model_prefix: str,
) -> float:
    """
    Intent ID에 대해 Model 기반 Score 추론.

    features dict에서 학습에 사용된 피처들을 순서대로 추출. 누락된 피처는 0.0으로 처리.
    training_data/dataset_path/model_prefix는 시나리오 엔진이 제공한다.
    """
    pipe = _load_or_train(intent_id, training_data, dataset_path, model_prefix)
    if pipe is None:
        return 0.0

    feature_names = training_data[intent_id]["features"]
    x = np.array([[float(features.get(name, 0.0)) for name in feature_names]])

    proba = pipe.predict_proba(x)[0][1]
    return float(proba)


def train_all(
    training_data: dict,
    dataset_path: Path,
    model_prefix: str,
    seed: int = 42,
) -> dict[str, float]:
    """
    training_data의 Model Intent 전체 학습 + 등록.

    Returns
    -------
    dict : {intent_id: 1.0}
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
