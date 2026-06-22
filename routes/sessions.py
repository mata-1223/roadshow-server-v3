from __future__ import annotations
"""
세션 생성 + 설문 제출
"""
import json
import uuid
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import settings
from core.inference import (
    infer_batch,
    to_customer_context_json,
    to_probability_dict,
    to_topn_with_others,
)
from data.executor import get_executor

router = APIRouter()


class CreateSessionResponse(BaseModel):
    """세션 생성 응답."""
    session_id:  str
    scenario_id: str


class SurveySubmission(BaseModel):
    """설문 제출 본문 ({question_id: answer_code})."""
    answers: dict[str, str]  # {"Q1": "A", ...}


class CreateSessionRequest(BaseModel):
    """세션 생성 요청 (scenario_id 미지정 시 기본 시나리오)."""
    scenario_id: Optional[str] = None


@router.post("", response_model=CreateSessionResponse)
async def create_session(req: Optional[CreateSessionRequest] = None) -> CreateSessionResponse:
    """새 세션 생성 (scenario_id 검증 후 sessions에 적재)."""
    from core.engines import available_scenarios
    scenario_id = (req.scenario_id if req and req.scenario_id else None) or settings.SCENARIO_ID
    if scenario_id not in available_scenarios():
        raise HTTPException(400, f"Unknown scenario: {scenario_id}")

    session_id = f"S-{uuid.uuid4().hex[:12]}"
    ex = get_executor()
    ex.execute(
        "INSERT INTO sessions (id, scenario_id, stage) VALUES (?, ?, ?)",
        [session_id, scenario_id, "initial"],
    )
    return CreateSessionResponse(
        session_id=session_id,
        scenario_id=scenario_id,
    )


@router.post("/{session_id}/survey")
async def submit_survey(session_id: str, submission: SurveySubmission) -> dict[str, Any]:
    """설문 제출 → baseline Intent 추론·적재 → Top-N·확률 분포 응답."""
    ex = get_executor()

    # 세션 검증 + scenario_id 조회
    row = ex.fetchone("SELECT id, scenario_id FROM sessions WHERE id = ?", [session_id])
    if row is None:
        raise HTTPException(404, "Session not found")
    scenario_id = row[1]

    # 답변 적재
    answer_rows = [
        [session_id, qid, code] for qid, code in submission.answers.items()
    ]
    ex.executemany(
        "INSERT INTO survey_answers (session_id, question_id, answer_code) VALUES (?, ?, ?)",
        answer_rows,
    )

    # Base Intent 추론
    batch_features, intent_scores = infer_batch(submission.answers, scenario_id)

    # Intent Score 적재
    score_rows = [
        [session_id, "initial", s.intent_id,
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

    # Customer Context JSON 적재
    context = to_customer_context_json(
        session_id=session_id,
        stage="initial",
        scenario_id=scenario_id,
        scores=intent_scores,
        batch_features=batch_features,
    )
    ex.execute(
        "INSERT INTO customer_contexts (session_id, scenario_id, stage, context_json) "
        "VALUES (?, ?, ?, ?)",
        [session_id, scenario_id, "initial", json.dumps(context, ensure_ascii=False)],
    )

    # 세션 stage 갱신
    ex.execute("UPDATE sessions SET stage = ?, last_active_at = CURRENT_TIMESTAMP WHERE id = ?",
               ["initial", session_id])

    top_items, others = to_topn_with_others(intent_scores, top_n=settings.TOP_N_INTENT, scenario_id=scenario_id)
    # 추론 이유(reasoning) 첨부 — 설문만이므로 pattern/event는 빈 상태
    from core.engines import get_engine
    from core import explain as _explain
    _eng = get_engine(scenario_id)
    _combined = {**batch_features, **_eng.empty_pattern_features(), **_eng.empty_event_features()}
    _explain.attach_reasoning(_eng, _combined, top_items)
    all_probabilities = to_probability_dict(intent_scores, scenario_id=scenario_id)

    # 파생 변수 산출 근거(분석 오버레이의 변수 클릭 → 산식 표시)
    from core.feature_trace import build_feature_trace
    feature_trace = build_feature_trace(scenario_id, submission.answers)

    return {
        "session_id":        session_id,
        "stage":             "initial",
        "batch_features":    batch_features,
        "feature_trace":     feature_trace,
        "top_n":             top_items,
        "others":            others,
        "all_probabilities": all_probabilities,
        "total_intents":     len(intent_scores),
    }
