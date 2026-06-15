from __future__ import annotations
"""
Scenario Engine 레지스트리.

scenario_id → ScenarioEngine 인스턴스(캐시). inference.py는 get_engine()만 사용한다.
"""
from core.engines.base import ScenarioEngine
from core.engines.generic import GenericEngine

# 모든 시나리오는 config(input/L0~L3 JSON) 기반 GenericEngine으로 동작.
_SCENARIOS = ("cs-myk-v3", "bundle-v3", "worker-v3")

_cache: dict[str, ScenarioEngine] = {}


def get_engine(scenario_id: str) -> ScenarioEngine:
    """scenario_id에 대한 엔진 인스턴스(캐시). 전 시나리오가 GenericEngine."""
    if scenario_id not in _cache:
        _cache[scenario_id] = GenericEngine(scenario_id)
    return _cache[scenario_id]


def available_scenarios() -> list[str]:
    """등록된 시나리오 id 목록."""
    return list(_SCENARIOS)
