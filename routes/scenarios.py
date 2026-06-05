from __future__ import annotations
"""
Scenario 메타 라우터
"""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from config import settings

router = APIRouter()
_SCENARIO_DIR = Path(__file__).parent.parent / "scenarios"


@router.get("/{scenario_id}")
async def get_scenario(scenario_id: str) -> dict:
    scenario_path = _SCENARIO_DIR / scenario_id
    if not scenario_path.exists():
        raise HTTPException(404, f"Scenario not found: {scenario_id}")

    def _load(filename: str) -> dict:
        p = scenario_path / filename
        if not p.exists():
            return {}
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    return {
        "scenario_id":  scenario_id,
        "intents":      _load("intents.json"),
        "survey":       _load("survey.json"),
        "behaviors":    _load("behaviors.json"),
        "actions":      _load("actions.json"),
    }
