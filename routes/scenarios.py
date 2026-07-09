from __future__ import annotations
"""
Scenario 메타 라우터
"""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from config import settings
from core.engines import config

router = APIRouter()
_SCENARIO_DIR = Path(__file__).parent.parent / "scenarios"


@router.get("/{scenario_id}")
async def get_scenario(scenario_id: str) -> dict:
    """시나리오 메타를 config 레이어에서 재조립하여 반환한다.

    intents(L0)·survey(L1.preprocessing)·behaviors(L1.behavior_catalog)·
    actions(L3.context_library)를 FE 계약 형태로 합쳐 반환한다.

    Args:
        scenario_id: 조회할 시나리오 ID (path).

    Returns:
        scenario_id·intents·survey·behaviors·actions를 담은 dict.

    Raises:
        HTTPException: 시나리오 정의 파일이 없으면 404.
    """
    try:
        return {
            "scenario_id": scenario_id,
            "intents":     config.get_taxonomy(scenario_id),       # L0
            "survey":      config.get_survey(scenario_id),         # L1.preprocessing
            "behaviors":   config.get_behaviors(scenario_id),      # L1.behavior_catalog
            "actions":     config.get_actions(scenario_id),        # L3.context_library
        }
    except FileNotFoundError:
        raise HTTPException(404, f"Scenario not found: {scenario_id}")


@router.get("/{scenario_id}/intent-positions")
async def get_intent_positions(scenario_id: str) -> dict:
    """Vector Space 시각화용 사전 산출 좌표를 반환한다.

    시나리오 디렉터리의 intent_positions.json을 그대로 로드한다.

    Args:
        scenario_id: 좌표를 조회할 시나리오 ID (path).

    Returns:
        intent_positions.json의 내용.

    Raises:
        HTTPException: 좌표 파일이 없으면 404.
    """
    path = _SCENARIO_DIR / scenario_id / "intent_positions.json"
    if not path.exists():
        raise HTTPException(404, f"intent_positions not found for: {scenario_id}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)
