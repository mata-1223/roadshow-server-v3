from __future__ import annotations
"""
Predictive Model 레지스트리 (ML/DL 구현 교체 지점).

predictive_model = 아래 인터페이스를 만족하는 객체/모듈 (시나리오 무관):
    predict(intent_id, features, *, training_data, dataset_path, model_prefix) -> float

- "predictive_model"은 ML(sklearn)·DL(torch 등)을 아우르는 [2b] 예측 모델 구현을 가리킨다.
- config L2.model.predictive_model 로 선택 (없으면 "sklearn").
- 새 구현은 register_predictive_model("torch", <obj>)로 등록.
- common.model_predict / GenericEngine.model_predict 는 특정 구현을 직접 import하지 않고
  이 레지스트리로 predictive_model을 받아 호출한다.
"""
from typing import Any, Protocol


class PredictiveModel(Protocol):
    """예측 모델 구현 인터페이스 (sklearn/torch… 공통). intent별 0~1 점수를 반환."""
    def predict(self, intent_id: str, features: dict[str, Any], *,
                training_data: dict, dataset_path, model_prefix: str) -> float: ...


_PREDICTIVE_MODELS: dict[str, Any] = {}


def register_predictive_model(name: str, predictive_model: Any) -> None:
    """예측 모델 구현을 name으로 등록 (예: "torch")."""
    _PREDICTIVE_MODELS[name] = predictive_model


def get_predictive_model(name: str = "sklearn") -> Any:
    """name에 등록된 예측 모델 구현을 반환. "sklearn"은 최초 호출 시 lazy 등록."""
    if name == "sklearn" and "sklearn" not in _PREDICTIVE_MODELS:
        from models import sklearn_model            # 기본 구현 lazy 등록
        _PREDICTIVE_MODELS["sklearn"] = sklearn_model
    try:
        return _PREDICTIVE_MODELS[name]
    except KeyError:
        raise ValueError(f"unknown predictive_model: {name!r} (등록됨: {sorted(_PREDICTIVE_MODELS)})")
