from __future__ import annotations
"""
Model 백엔드 레지스트리 (ML 구현 교체 지점).

백엔드 = 아래 인터페이스를 만족하는 객체/모듈 (시나리오 무관):
    predict(intent_id, features, *, training_data, dataset_path, model_prefix) -> float

- config L2.model.backend 로 선택 (없으면 "sklearn").
- sklearn 외 DL 백엔드(torch 등)는 register_backend("torch", <obj>)로 등록.
- common.model_predict / GenericEngine.model_predict 는 sklearn을 직접 import하지 않고
  이 레지스트리로 백엔드를 받아 호출한다.
"""
from typing import Any, Protocol


class ModelBackend(Protocol):
    def predict(self, intent_id: str, features: dict[str, Any], *,
                training_data: dict, dataset_path, model_prefix: str) -> float: ...


_BACKENDS: dict[str, Any] = {}


def register_backend(name: str, backend: Any) -> None:
    _BACKENDS[name] = backend


def get_backend(name: str = "sklearn") -> Any:
    if name == "sklearn" and "sklearn" not in _BACKENDS:
        from models import sklearn_model            # 기본 백엔드 lazy 등록
        _BACKENDS["sklearn"] = sklearn_model
    try:
        return _BACKENDS[name]
    except KeyError:
        raise ValueError(f"unknown model backend: {name!r} (등록됨: {sorted(_BACKENDS)})")
