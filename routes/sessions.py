from __future__ import annotations
"""
세션 생성 + 설문 제출
"""
import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import settings
from core.inference import infer_batch, to_customer_context_json
from data.executor import get_executor

router = APIRouter()


class CreateSessionResponse(BaseModel):
    session_id:  str
    scenario_id: str


class SurveySubmission(BaseModel):
    answers: dict[str, str]  # {"Q1": "A", ...}


@router.post("", response_model=CreateSessionResponse)
async def create_session() -> CreateSessionResponse:
    session_id = f"S-{uuid.uuid4().hex[:12]}"
    ex = get_executor()
    ex.execute(
        "INSERT INTO sessions (id, scenario_id, stage) VALUES (?, ?, ?)",
        [session_id, settings.SCENARIO_ID, "initial"],
    )
    return CreateSessionResponse(
        session_id=session_id,
        scenario_id=settings.SCENARIO_ID,
    )


@router.post("/{session_id}/survey")
async def submit_survey(session_id: str, submission: SurveySubmission) -> dict[str, Any]:
    ex = get_executor()

    # 세션 검증
    row = ex.fetchone("SELECT id FROM sessions WHERE id = ?", [session_id])
    if row is None:
        raise HTTPException(404, "Session not found")

    # 답변 적재
    answer_rows = [
        [session_id, qid, code] for qid, code in submission.answers.items()
    ]
    ex.executemany(
        "INSERT INTO survey_answers (session_id, question_id, answer_code) VALUES (?, ?, ?)",
        answer_rows,
    )

    # Base Intent 추론
    batch_features, intent_scores = infer_batch(submission.answers)

    # Intent Score 적재
    score_rows = [
        [session_id, "initial", s.intent_id, s.batch_score, s.realtime_boost,
         s.final_score, s.rank, s.inference_type]
        for s in intent_scores
    ]
    ex.executemany(
        "INSERT INTO intent_scores "
        "(session_id, stage, intent_id, batch_score, realtime_boost, final_score, rank, inference_type) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        score_rows,
    )

    # Customer Context JSON 적재
    context = to_customer_context_json(
        session_id=session_id,
        stage="initial",
        scenario_id=settings.SCENARIO_ID,
        scores=intent_scores,
        batch_features=batch_features,
    )
    ex.execute(
        "INSERT INTO customer_contexts (session_id, scenario_id, stage, context_json) "
        "VALUES (?, ?, ?, ?)",
        [session_id, settings.SCENARIO_ID, "initial", json.dumps(context, ensure_ascii=False)],
    )

    # 세션 stage 갱신
    ex.execute("UPDATE sessions SET stage = ?, last_active_at = CURRENT_TIMESTAMP WHERE id = ?",
               ["initial", session_id])

    top_n = settings.TOP_N_INTENT
    return {
        "session_id":     session_id,
        "stage":          "initial",
        "batch_features": batch_features,
        "top_n":          [_score_to_dict(s) for s in intent_scores[:top_n]],
        "total_intents":  len(intent_scores),
    }


def _score_to_dict(s) -> dict:
    return {
        "intent_id":      s.intent_id,
        "intent_name":    s.intent_name,
        "L1_id":          s.L1_id,
        "L1_name":        s.L1_name,
        "L2_id":          s.L2_id,
        "L2_name":        s.L2_name,
        "batch_score":    s.batch_score,
        "realtime_boost": s.realtime_boost,
        "final_score":    s.final_score,
        "rank":           s.rank,
        "inference_type": s.inference_type,
    }
