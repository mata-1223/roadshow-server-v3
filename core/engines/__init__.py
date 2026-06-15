from __future__ import annotations
"""
Scenario Engine 레지스트리.

scenario_id → ScenarioEngine 인스턴스(캐시). inference.py는 get_engine()만 사용한다.
"""
from core.engines.base import ScenarioEngine
from core.engines.cs import CSEngine
from core.engines.bundle import BundleEngine
from core.engines.worker import WorkerEngine

_FACTORIES = {
    "cs-myk-v3": CSEngine,
    "bundle-v3": BundleEngine,
    "worker-v3": WorkerEngine,
}

_cache: dict[str, ScenarioEngine] = {}


def get_engine(scenario_id: str) -> ScenarioEngine:
    if scenario_id not in _cache:
        factory = _FACTORIES.get(scenario_id)
        if factory is None:
            # 미정의 시나리오는 CS 엔진으로 fallback
            factory = CSEngine
        _cache[scenario_id] = factory(scenario_id)
    return _cache[scenario_id]


def available_scenarios() -> list[str]:
    return list(_FACTORIES.keys())
