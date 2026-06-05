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
    """세션의 최신 stage Intent Top-N"""
    ex = get_executor()

    # 최신 stage 찾기
    row = ex.fetchone(
        "SELECT stage FROM sessions WHERE id = ?",
        [session_id],
    )
    if row is None:
        raise HTTPException(404, "Session not found")
    stage = row[0]

    df = ex.to_pandas(
        "SELECT intent_id, batch_score, realtime_boost, final_score, rank, inference_type "
        "FROM intent_scores WHERE session_id = ? AND stage = ? ORDER BY rank LIMIT ?",
        [session_id, stage, top_n],
    )

    # Intent 메타 조회
    df_meta = ex.to_pandas(
        "SELECT intent_id, intent_name, L1_id, L1_name, L2_id, L2_name FROM catalog_intents"
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
            "batch_score":    float(r["batch_score"]),
            "realtime_boost": float(r["realtime_boost"]),
            "final_score":    float(r["final_score"]),
            "rank":           int(r["rank"]),
            "inference_type": r["inference_type"],
        })

    return {
        "session_id": session_id,
        "stage":      stage,
        "intents":    items,
    }


@router.get("/context/{session_id}")
async def get_customer_context(session_id: str, stage: Optional[str] = None) -> dict:
    """Customer Context JSON 조회 (최신 또는 특정 stage)"""
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
