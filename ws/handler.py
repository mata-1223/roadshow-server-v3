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
    """WebSocket 엔드포인트.

    첫 메시지로 JOIN을 받아 세션에 결합하고 SESSION_READY를 보낸 뒤,
    이후 BEHAVIOR 메시지마다 재추론하여 INTENT_UPDATE를 Push한다.
    연결 종료 시 매니저에서 연결을 해제한다.

    Args:
        websocket: 클라이언트 WebSocket 연결.
    """
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
    """BEHAVIOR 메시지를 처리한다.

    이벤트를 event_log와 extractor에 적재하고 EVENT_ACK를 보낸다.
    app_exit이면 세션을 종료(stage='exited')하고 INTENT_UPDATE 없이 반환한다.
    그 외에는 누적 행동 기반으로 재추론하여 intent_scores·customer_contexts에 저장하고
    INTENT_UPDATE를 Push한다.

    Args:
        websocket: 응답을 보낼 WebSocket 연결.
        session_id: 대상 세션 ID.
        scenario_id: 세션의 시나리오 ID.
        survey_answers: 재추론에 사용할 설문 답변 ({question_id: answer_code}).
        msg: BEHAVIOR 메시지 (behavior_id·event_type·entity 포함).
    """
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
    top_items, others = to_topn_with_others(intent_scores, top_n=top_n_cnt, scenario_id=scenario_id)
    # 추론 이유(reasoning) 첨부 — 결합 feature(batch+누적 pattern+최신 event)
    from core.engines import get_engine
    from core import explain as _explain
    _eng = get_engine(scenario_id)
    _combined = {**batch_features, **_eng.pattern_features(session_id), **_eng.event_features(session_id)}
    _explain.attach_reasoning(_eng, _combined, top_items)
    all_probabilities = to_probability_dict(intent_scores, scenario_id=scenario_id)

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
    """세션의 설문 답변을 DB에서 로드한다.

    Args:
        session_id: 답변을 조회할 세션 ID.

    Returns:
        {question_id: answer_code} 형태의 설문 답변 dict.
    """
    ex = get_executor()
    df = ex.to_pandas(
        "SELECT question_id, answer_code FROM survey_answers WHERE session_id = ?",
        [session_id],
    )
    return {r["question_id"]: r["answer_code"] for _, r in df.iterrows()}
