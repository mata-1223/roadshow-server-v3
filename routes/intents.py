from __future__ import annotations
"""
Intent 조회 라우터
"""
import json
from typing import Optional
from fastapi import APIRouter, HTTPException

from data.executor import get_executor

router = APIRouter()


@router.get("/latest")
async def get_latest_intents(session_id: str, top_n: int = 5) -> dict:
    """세션의 최신 stage에 대한 Intent Top-N을 반환한다.

    세션의 현재 stage를 찾아 해당 stage의 Intent Score를 rank 순으로 조회하고,
    시나리오 카탈로그의 Intent 메타(이름·계층)를 병합한다.

    Args:
        session_id: 조회할 세션 ID (query).
        top_n: 반환할 상위 Intent 개수 (query).

    Returns:
        session_id·stage·intents(메타 병합된 Top-N 항목 목록)를 담은 dict.

    Raises:
        HTTPException: 세션이 없으면 404.
    """
    ex = get_executor()

    # 최신 stage 찾기
    row = ex.fetchone(
        "SELECT stage, scenario_id FROM sessions WHERE id = ?",
        [session_id],
    )
    if row is None:
        raise HTTPException(404, "Session not found")
    stage, scenario_id = row[0], row[1]

    df = ex.to_pandas(
        "SELECT intent_id, baseline_score, final_score, delta_score, "
        "       baseline_rank, rank, rank_change, inference_type "
        "FROM intent_scores WHERE session_id = ? AND stage = ? ORDER BY rank LIMIT ?",
        [session_id, stage, top_n],
    )

    # Intent 메타 조회 (해당 시나리오)
    df_meta = ex.to_pandas(
        "SELECT intent_id, intent_name, L1_id, L1_name, L2_id, L2_name "
        "FROM catalog_intents WHERE scenario_id = ?",
        [scenario_id],
    )
    meta_by_id = {r["intent_id"]: r for _, r in df_meta.iterrows()}

    items = []
    for _, r in df.iterrows():
        meta = meta_by_id.get(r["intent_id"], {})
        items.append({
            "intent_id":      r["intent_id"],
            "intent_name":    meta.get("intent_name"),
            "L1_id":          meta.get("L1_id"),
            "L1_name":        meta.get("L1_name"),
            "L2_id":          meta.get("L2_id"),
            "L2_name":        meta.get("L2_name"),
            "baseline_score": float(r["baseline_score"]),
            "final_score":    float(r["final_score"]),
            "delta_score":    float(r["delta_score"]),
            "baseline_rank":  int(r["baseline_rank"]),
            "rank":           int(r["rank"]),
            "rank_change":    int(r["rank_change"]),
            "inference_type": r["inference_type"],
        })

    return {
        "session_id": session_id,
        "stage":      stage,
        "intents":    items,
    }


@router.get("/context/{session_id}")
async def get_customer_context(session_id: str, stage: Optional[str] = None) -> dict:
    """Customer Context JSON을 조회한다.

    stage가 주어지면 해당 stage의 최신 컨텍스트를, 없으면 세션 전체의 최신 컨텍스트를 반환한다.

    Args:
        session_id: 조회할 세션 ID (path).
        stage: 특정 stage로 한정 (없으면 최신, query).

    Returns:
        파싱된 Customer Context JSON.

    Raises:
        HTTPException: 컨텍스트가 없으면 404.
    """
    ex = get_executor()

    if stage:
        row = ex.fetchone(
            "SELECT context_json FROM customer_contexts "
            "WHERE session_id = ? AND stage = ? ORDER BY created_at DESC LIMIT 1",
            [session_id, stage],
        )
    else:
        row = ex.fetchone(
            "SELECT context_json FROM customer_contexts "
            "WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
            [session_id],
        )
    if row is None:
        raise HTTPException(404, "Context not found")
    return json.loads(row[0])
