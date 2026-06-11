from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path

_SCENARIOS = Path(__file__).parent.parent.parent / "scenarios"
_LAYERS = ("L0_taxonomy", "L1_feature", "L2_inference", "L3_serving")

@lru_cache(maxsize=None)
def load_layer(scenario_id: str, layer: str) -> dict:
    with open(_SCENARIOS / scenario_id / "engine" / f"{layer}.json", encoding="utf-8") as f:
        return json.load(f)

# ── 레이어별 접근자 ──
def get_taxonomy(sid):
    return load_layer(sid, "L0_taxonomy")
def get_survey(sid):
    return load_layer(sid, "L1_feature")["preprocessing"]["survey"]
def get_behaviors(sid):
    return load_layer(sid, "L1_feature")["behavior_catalog"]
def get_behavior_signals(sid):
    return load_layer(sid, "L2_inference")["ranker"]["behavior_signals"]
def get_actions(sid):
    return load_layer(sid, "L3_serving")["context_library"]