from __future__ import annotations
"""
Model-based Intent Inference ([2b] reference 모듈)

16개 Model Intent에 대한 sklearn Logistic Regression 추론.
- 도메인 지식 기반 학습 데이터 (각 Intent당 양성 5 + 음성 5)
- StandardScaler + LogisticRegression Pipeline
- MLflow Pyfunc Registry에 등록 (모델명: {intent_id}_sklearn)
- seed 고정 (42)으로 재현성 확보
"""
import logging
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


# ─────────────────────────────────────────────────────────────
# 16개 Model Intent의 도메인 지식 기반 학습 데이터
# ─────────────────────────────────────────────────────────────
INTENT_TRAINING_DATA: dict[str, dict] = {

    # ── INT-2130. 데이터 상품 탐색 ─────────────────────────────
    "INT-2130": {
        "features": ["데이터 사용률", "데이터 사용 증감률", "잔여 데이터 비율", "사용 강도 Index", "업셀 적합도 Score"],
        "X": [
            # 양성: 데이터 부족 + 증가 추세 + 업셀 적합도 높음
            [0.90, 0.18, 0.10, 88, 0.85], [0.85, 0.20, 0.15, 82, 0.78],
            [0.92, 0.22, 0.08, 90, 0.88], [0.78, 0.15, 0.22, 75, 0.65],
            [0.95, 0.25, 0.05, 92, 0.90],
            # 음성: 데이터 충분 + 업셀 적합도 낮음
            [0.30, 0.02, 0.70, 28, 0.25], [0.40, 0.03, 0.60, 35, 0.30],
            [0.25, 0.01, 0.75, 22, 0.20], [0.20, 0.00, 0.80, 18, 0.15],
            [0.45, 0.05, 0.55, 40, 0.35],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },

    # ── INT-3210. 요금제 변경 ──────────────────────────────────
    "INT-3210": {
        "features": ["요금 민감도 Index", "비용 부담도", "약정 진행률", "이탈 위험 Score"],
        "X": [
            # 양성: 민감도 + 부담 + 약정 진행 + 이탈 위험
            [75, 0.7, 0.85, 0.6], [68, 0.6, 0.90, 0.55], [82, 0.8, 0.80, 0.7],
            [60, 0.5, 0.95, 0.5], [78, 0.75, 0.75, 0.65],
            # 음성: 안정적
            [25, 0.2, 0.30, 0.15], [35, 0.3, 0.40, 0.20], [30, 0.2, 0.20, 0.10],
            [40, 0.3, 0.50, 0.25], [20, 0.1, 0.10, 0.05],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },

    # ── INT-4310. AI 추천 탐색 ─────────────────────────────────
    "INT-4310": {
        "features": ["고객 가치 Index", "비용 부담도", "데이터 사용률", "푸시 오픈율"],
        "X": [
            # 양성: 가치 높음 + 활발 사용 + 푸시 자주 봄
            [78, 0.5, 0.75, 0.80], [85, 0.6, 0.85, 0.75], [72, 0.5, 0.70, 0.70],
            [80, 0.4, 0.80, 0.85], [88, 0.5, 0.90, 0.80],
            # 음성: 무관심
            [30, 0.3, 0.30, 0.10], [40, 0.4, 0.40, 0.15], [25, 0.2, 0.25, 0.05],
            [45, 0.3, 0.45, 0.20], [35, 0.5, 0.30, 0.12],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },

    # ── INT-4320. 개인화 혜택 탐색 ─────────────────────────────
    "INT-4320": {
        "features": ["고객 가치 Index", "멤버십 활용도", "탐색 성향 Index"],
        "X": [
            [75, 0.80, 80], [82, 0.75, 75], [70, 0.70, 70], [85, 0.85, 82], [78, 0.65, 68],
            [35, 0.10, 15], [40, 0.20, 25], [25, 0.05, 10], [50, 0.30, 30], [38, 0.15, 20],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },

    # ── INT-4330. 추천 요금제 검토 ─────────────────────────────
    "INT-4330": {
        "features": ["요금 민감도 Index", "데이터 사용률", "가입 개월 수", "약정 진행률"],
        "X": [
            [70, 0.80, 36, 0.90], [65, 0.70, 48, 0.85], [78, 0.85, 24, 0.95],
            [60, 0.75, 60, 0.80], [72, 0.65, 30, 0.92],
            [25, 0.30, 6,  0.15], [30, 0.40, 12, 0.25], [22, 0.25, 3,  0.10],
            [35, 0.35, 18, 0.30], [28, 0.45, 9,  0.20],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },


    # ── INT-5110. 인터넷 장애 해결 ─────────────────────────────
    "INT-5110": {
        "features": ["품질 만족도", "결합 여부", "quality_action_count", "장애 페이지 체류"],
        "X": [
            # 양성: 만족도 낮음 + 결합 (홈) + 진단 행동 + 체류 김
            [0.25, 1, 3, 180], [0.30, 1, 4, 220], [0.20, 1, 2, 150],
            [0.35, 1, 3, 165], [0.25, 1, 5, 250],
            # 음성: 만족 + 진단 행동 없음
            [0.85, 0, 0, 0],  [0.80, 1, 0, 0],   [0.90, 0, 0, 0],
            [0.75, 1, 0, 10], [0.85, 0, 0, 5],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },

    # ── INT-5120. WiFi 문제 해결 ───────────────────────────────
    "INT-5120": {
        "features": ["품질 만족도", "WiFi 진단 실행", "결합 여부"],
        "X": [
            [0.30, 2, 1], [0.25, 3, 1], [0.35, 2, 1], [0.20, 1, 1], [0.30, 4, 1],
            [0.85, 0, 0], [0.80, 0, 1], [0.90, 0, 0], [0.75, 0, 1], [0.85, 0, 0],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },

    # ── INT-5130. 속도 저하 해결 ───────────────────────────────
    "INT-5130": {
        "features": ["품질 만족도", "속도 측정 실행", "데이터 사용률"],
        "X": [
            [0.25, 3, 0.85], [0.30, 2, 0.75], [0.20, 4, 0.90],
            [0.35, 2, 0.70], [0.25, 3, 0.80],
            [0.85, 0, 0.30], [0.80, 0, 0.40], [0.90, 0, 0.25],
            [0.75, 0, 0.45], [0.85, 0, 0.35],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },

    # ── INT-6110. 가족결합 관리 ────────────────────────────────
    "INT-6110": {
        "features": ["결합 여부", "가족 회선 수", "가족 결합 관련 행동"],
        "X": [
            [1, 3, 1], [1, 4, 1], [1, 5, 1], [1, 3, 1], [1, 2, 1],
            [0, 1, 0], [0, 1, 0], [1, 1, 0], [0, 2, 0], [1, 2, 0],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },

    # ── INT-7110. 위약금 조회 ──────────────────────────────────
    "INT-7110": {
        "features": ["약정 진행률", "이탈 위험 Score", "위약금 조회 행동"],
        "X": [
            [0.85, 0.65, 1], [0.90, 0.70, 1], [0.80, 0.60, 1],
            [0.95, 0.75, 1], [0.88, 0.55, 1],
            [0.20, 0.15, 0], [0.30, 0.20, 0], [0.15, 0.10, 0],
            [0.40, 0.25, 0], [0.25, 0.18, 0],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },

    # ── INT-7130. 해지 상담 요청 ───────────────────────────────
    "INT-7130": {
        "features": ["이탈 위험 Score", "30일 상담 횟수", "해지 페이지 진입"],
        "X": [
            [0.70, 3, 1], [0.65, 2, 1], [0.75, 4, 1], [0.60, 2, 1], [0.80, 5, 1],
            [0.15, 0, 0], [0.20, 0, 0], [0.10, 0, 0], [0.25, 1, 0], [0.18, 0, 0],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },

    # ── INT-7210. 번호이동 탐색 — KT 앱 내 번호이동 안내 페이지 진입 행동 활용 ──
    "INT-7210": {
        "features": ["이탈 위험 Score", "비용 부담도", "mnp_benefit_check"],
        "X": [
            [0.65, 0.75, 1], [0.70, 0.80, 1], [0.60, 0.70, 1],
            [0.75, 0.85, 1], [0.55, 0.65, 1],
            [0.15, 0.20, 0], [0.20, 0.25, 0], [0.10, 0.15, 0],
            [0.25, 0.30, 0], [0.18, 0.22, 0],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },

    # ── INT-7310. 저가 요금 탐색 ───────────────────────────────
    "INT-7310": {
        "features": ["요금 민감도 Index", "비용 부담도", "요금제 월정액"],
        "X": [
            [75, 0.7, 75000], [80, 0.8, 90000], [70, 0.65, 65000],
            [85, 0.75, 85000], [78, 0.7, 80000],
            [25, 0.2, 33000], [30, 0.3, 35000], [22, 0.15, 30000],
            [35, 0.3, 40000], [28, 0.25, 38000],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },

    # ── INT-7320. 할인 탐색 ────────────────────────────────────
    "INT-7320": {
        "features": ["요금 민감도 Index", "미사용 쿠폰 수", "할인 페이지 체류"],
        "X": [
            [70, 5, 120], [75, 6, 150], [65, 4, 100], [80, 7, 180], [72, 5, 130],
            [25, 0, 0],   [30, 1, 5],   [22, 0, 0],   [35, 2, 10],  [28, 1, 8],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },
}


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


def train_and_register(intent_id: str, seed: int = 42) -> Pipeline | None:
    """
    Intent의 학습 데이터로 모델 학습 + MLflow 등록.
    학습 데이터가 없으면 None 반환.
    """
    data = INTENT_TRAINING_DATA.get(intent_id)
    if data is None:
        return None

    pipe = _train_pipeline(data["X"], data["y"], seed=seed)

    mlflow.set_tracking_uri(settings.MLFLOW_URI)
    with mlflow.start_run(run_name=f"{intent_id}_sklearn_init"):
        mlflow.sklearn.log_model(
            pipe,
            "model",
            registered_model_name=f"{intent_id}_sklearn",
        )
        mlflow.log_params({
            "intent_id":    intent_id,
            "n_features":   len(data["features"]),
            "n_samples":    len(data["y"]),
            "n_positive":   int(sum(data["y"])),
            "seed":         seed,
            "data_source":  "domain_knowledge",
            "feature_names": ",".join(data["features"]),
        })
        train_acc = pipe.score(np.array(data["X"], dtype=float), np.array(data["y"]))
        mlflow.log_metric("train_accuracy", train_acc)

    logger.info(f"Trained + registered: {intent_id}_sklearn (acc={train_acc:.3f})")
    return pipe


def _load_or_train(intent_id: str) -> Pipeline | None:
    if intent_id in _model_cache:
        return _model_cache[intent_id]

    if intent_id not in INTENT_TRAINING_DATA:
        return None

    mlflow.set_tracking_uri(settings.MLFLOW_URI)
    uri = f"models:/{intent_id}_sklearn/latest"
    try:
        pipe = mlflow.sklearn.load_model(uri)
    except Exception:
        pipe = train_and_register(intent_id)

    _model_cache[intent_id] = pipe
    return pipe


def predict(intent_id: str, features: dict[str, Any]) -> float:
    """
    Intent ID에 대해 Model 기반 Score 추론.

    features dict에서 학습에 사용된 피처들을 순서대로 추출.
    누락된 피처는 0.0으로 처리.
    """
    pipe = _load_or_train(intent_id)
    if pipe is None:
        return 0.0

    data = INTENT_TRAINING_DATA[intent_id]
    feature_names = data["features"]
    x = np.array([[float(features.get(name, 0.0)) for name in feature_names]])

    proba = pipe.predict_proba(x)[0][1]
    return float(proba)


def train_all(seed: int = 42) -> dict[str, float]:
    """
    16개 Model Intent 모두 학습 + 등록.

    Returns
    -------
    dict : {intent_id: train_accuracy}
    """
    results = {}
    for intent_id in INTENT_TRAINING_DATA.keys():
        pipe = train_and_register(intent_id, seed=seed)
        if pipe is not None:
            data = INTENT_TRAINING_DATA[intent_id]
            acc = pipe.score(np.array(data["X"], dtype=float), np.array(data["y"]))
            results[intent_id] = acc
    return results


def get_model_intent_count() -> int:
    return len(INTENT_TRAINING_DATA)
