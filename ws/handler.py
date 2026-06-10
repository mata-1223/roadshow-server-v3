from __future__ import annotations
"""
WebSocket Handler

클라이언트 메시지: JOIN | BEHAVIOR
서버 Push:        SESSION_READY | EVENT_ACK | INTENT_UPDATE | ERROR
"""
import json
import logging
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from config import settings
from core.extractor import get_extractor
from core.inference import (
    infer_with_behavior,
    to_customer_context_json,
    to_probability_dict,
    to_topn_with_others,
)
from data.executor import get_executor
from ws.manager import manager

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    session_id: str | None = None

    try:
        await websocket.accept()
        raw = await websocket.receive_json()

        if raw.get("type") != "JOIN":
            await websocket.send_json({"type": "ERROR", "code": "MISSING_JOIN"})
            return

        session_id = raw["session_id"]
        ex = get_executor()
        row = ex.fetchone("SELECT id, scenario_id, stage FROM sessions WHERE id = ?", [session_id])
        if row is None:
            await websocket.send_json({"type": "ERROR", "code": "SESSION_NOT_FOUND"})
            return

        scenario_id = row[1]
        manager._connections[session_id] = websocket
        await websocket.send_json({
            "type":         "SESSION_READY",
            "session_id":   session_id,
            "scenario_id":  scenario_id,
            "stage":        row[2],
        })

        # 설문 답변 캐시 (재추론 시 사용)
        survey_answers = _load_session_answers(session_id)

        while True:
            msg = await websocket.receive_json()
            mtype = msg.get("type")

            if mtype == "BEHAVIOR":
                await _handle_behavior(websocket, session_id, scenario_id, survey_answers, msg)
            else:
                await websocket.send_json({"type": "ERROR", "code": "UNKNOWN_TYPE"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception(f"WS error: {e}")
        try:
            await websocket.send_json({"type": "ERROR", "message": str(e)})
        except Exception:
            pass
    finally:
        if session_id:
            manager.disconnect(session_id)


async def _handle_behavior(
    websocket: WebSocket,
    session_id: str,
    scenario_id: str,
    survey_answers: dict[str, str],
    msg: dict,
) -> None:
    behavior_id = msg.get("behavior_id")
    event_type  = msg.get("event_type")
    entity      = msg.get("entity")
    if not (behavior_id and event_type and entity):
        await websocket.send_json({"type": "ERROR", "code": "MISSING_FIELDS"})
        return

    ex = get_executor()

    # step: behavior_id 접두사로 판정 (1-* = step1, 그 외 step2). 시나리오 무관.
    step = 1 if str(behavior_id).startswith("1-") else 2

    # 이벤트 로그 적재
    ex.execute(
        "INSERT INTO event_log (session_id, scenario_id, step, behavior_id, event_type, entity) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [session_id, scenario_id, step, behavior_id, event_type, entity],
    )
    ex.execute(
        "UPDATE sessions SET last_active_at = CURRENT_TIMESTAMP WHERE id = ?",
        [session_id],
    )

    # Extractor에 이벤트 추가 (app_exit/navigate_back은 Pattern 집계 영향 약함)
    get_extractor().add_event(session_id, event_type, entity)

    await websocket.send_json({
        "type":        "EVENT_ACK",
        "behavior_id": behavior_id,
        "occurred_at": datetime.utcnow().isoformat(),
    })

    # app_exit: 세션 종료. INTENT_UPDATE 미전송. stage='exited' 갱신만.
    if event_type == "app_exit":
        ex.execute("UPDATE sessions SET stage = ? WHERE id = ?", ["exited", session_id])
        return

    # Intent 재추론 (Batch + 누적 행동)
    batch_features, intent_scores = infer_with_behavior(survey_answers, session_id, scenario_id)

    new_stage = f"step_{step}" if step > 0 else "initial"

    # Intent Score 적재
    score_rows = [
        [session_id, new_stage, s.intent_id,
         s.baseline_score, s.final_score, s.delta_score,
         s.baseline_rank, s.rank, s.rank_change, s.inference_type]
        for s in intent_scores
    ]
    ex.executemany(
        "INSERT INTO intent_scores "
        "(session_id, stage, intent_id, baseline_score, final_score, delta_score, "
        " baseline_rank, rank, rank_change, inference_type) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        score_rows,
    )

    # Customer Context 적재
    context = to_customer_context_json(
        session_id=session_id,
        stage=new_stage,
        scenario_id=scenario_id,
        scores=intent_scores,
        batch_features=batch_features,
    )
    ex.execute(
        "INSERT INTO customer_contexts (session_id, scenario_id, stage, context_json) "
        "VALUES (?, ?, ?, ?)",
        [session_id, scenario_id, new_stage, json.dumps(context, ensure_ascii=False)],
    )

    ex.execute("UPDATE sessions SET stage = ? WHERE id = ?", [new_stage, session_id])

    top_n_cnt = settings.TOP_N_INTENT
    top_items, others = to_topn_with_others(intent_scores, top_n=top_n_cnt)
    all_probabilities = to_probability_dict(intent_scores)

    await websocket.send_json({
        "type":              "INTENT_UPDATE",
        "session_id":        session_id,
        "behavior_id":       behavior_id,
        "stage":             new_stage,
        "computed_at":       datetime.utcnow().isoformat(),
        "top_n":             top_items,
        "others":            others,
        "all_probabilities": all_probabilities,
    })


def _load_session_answers(session_id: str) -> dict[str, str]:
    ex = get_executor()
    df = ex.to_pandas(
        "SELECT question_id, answer_code FROM survey_answers WHERE session_id = ?",
        [session_id],
    )
    return {r["question_id"]: r["answer_code"] for _, r in df.iterrows()}
