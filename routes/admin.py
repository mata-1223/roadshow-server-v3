from __future__ import annotations
"""
Admin 테이블 조회 API
DuckDB의 모든 user 테이블을 동적으로 노출.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from data.executor import get_executor

router = APIRouter()


# ── 사용자 친화 라벨/설명 (있으면 사용, 없으면 자동 생성) ──
_TABLE_META = {
    "sessions": {
        "label":       "세션",
        "description": "시연 세션 메타 (참여자별 1행)",
        "kind":        "runtime",
    },
    "survey_answers": {
        "label":       "설문 답변",
        "description": "참여자가 제출한 설문 답변 (참여자 × 문항)",
        "kind":        "runtime",
    },
    "event_log": {
        "label":       "행동 이벤트 로그",
        "description": "마이K 앱 행동 이벤트 (참여자 × 행동)",
        "kind":        "runtime",
    },
    "intent_scores": {
        "label":       "Intent Score",
        "description": "Intent 추론 결과 — 매 단계마다 116개 적재",
        "kind":        "runtime",
    },
    "customer_contexts": {
        "label":       "Customer Context",
        "description": "Customer Context JSON 적재 (매 단계 1행, 116개 Intent 포함)",
        "kind":        "runtime",
    },
    "scenarios": {
        "label":       "시나리오 메타",
        "description": "등록된 시나리오 카탈로그",
        "kind":        "catalog",
    },
    "catalog_intents": {
        "label":       "Intent 카탈로그",
        "description": "시연 대상 116개 Intent 정의 (소액결제 제외)",
        "kind":        "catalog",
    },
    "catalog_actions": {
        "label":       "Action 카탈로그",
        "description": "Intent별 추천 Action 정의",
        "kind":        "catalog",
    },
    "catalog_behaviors": {
        "label":       "Behavior 카탈로그",
        "description": "마이K 앱 행동 정의 (3단계 × 17개)",
        "kind":        "catalog",
    },
}

# 정렬 우선 순위 컬럼 (있으면 사용)
_PREFERRED_ORDER_COLS = ["id", "intent_id", "behavior_id", "action_id"]

# 노출 제외 (시스템 테이블 등)
_HIDDEN_PREFIXES = ("information_schema", "pg_", "sqlite_")


def _list_user_tables() -> list[str]:
    """DuckDB의 모든 user 테이블 이름"""
    ex = get_executor()
    rows = ex.fetchall(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_type = 'BASE TABLE' "
        "ORDER BY table_name"
    )
    names = []
    for r in rows:
        name = r[0]
        if any(name.startswith(p) for p in _HIDDEN_PREFIXES):
            continue
        names.append(name)
    return names


def _table_columns(table_name: str) -> list[str]:
    """테이블의 컬럼 목록 (선언 순서)"""
    ex = get_executor()
    rows = ex.fetchall(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'main' AND table_name = ? "
        "ORDER BY ordinal_position",
        [table_name],
    )
    return [r[0] for r in rows]


def _order_clause(columns: list[str]) -> str:
    """기본 정렬: 가능한 가장 의미 있는 컬럼 desc"""
    for c in _PREFERRED_ORDER_COLS:
        if c in columns:
            return f"{c} DESC"
    # 'created_at', 'occurred_at' 같은 timestamp 있으면 사용
    for c in columns:
        if c.endswith("_at"):
            return f"{c} DESC"
    return columns[0] if columns else "1"


@router.get("/tables")
async def list_tables() -> list[dict]:
    """모든 user 테이블 + 행 수 + 분류(runtime/catalog)"""
    ex = get_executor()
    result = []
    for name in _list_user_tables():
        meta = _TABLE_META.get(name, {})
        row = ex.fetchone(f"SELECT COUNT(*) FROM {name}")
        count = int(row[0]) if row else 0
        result.append({
            "name":        name,
            "label":       meta.get("label", name),
            "description": meta.get("description", ""),
            "kind":        meta.get("kind", "other"),
            "row_count":   count,
        })
    return result


@router.get("/tables/{table_name}")
async def query_table(
    table_name: str,
    session_id: Optional[str] = Query(None, description="세션 ID로 필터링 (있는 경우만)"),
    limit:  int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    """테이블 조회 (페이징 + 세션 필터)"""
    if table_name not in _list_user_tables():
        raise HTTPException(404, f"Table not found: {table_name}")

    columns = _table_columns(table_name)
    if not columns:
        raise HTTPException(500, "Failed to read columns")

    meta = _TABLE_META.get(table_name, {})
    col_list = ", ".join(columns)
    order_by = _order_clause(columns)

    where_sql = ""
    params: list = []
    if session_id and "session_id" in columns:
        where_sql = "WHERE session_id = ?"
        params.append(session_id)

    # 행 수
    cnt_sql = f"SELECT COUNT(*) FROM {table_name} {where_sql}"
    row = get_executor().fetchone(cnt_sql, params)
    total = int(row[0]) if row else 0

    # 데이터
    data_sql = f"SELECT {col_list} FROM {table_name} {where_sql} ORDER BY {order_by} LIMIT ? OFFSET ?"
    df = get_executor().to_pandas(data_sql, params + [limit, offset])

    rows = []
    for _, r in df.iterrows():
        row_dict = {}
        for c in columns:
            v = r[c]
            if hasattr(v, "isoformat"):
                v = v.isoformat()
            elif v is None or (hasattr(v, "__class__") and v.__class__.__name__ == "NAType"):
                v = None
            elif isinstance(v, float):
                v = round(v, 4)
            elif hasattr(v, "item"):
                v = v.item()
            elif isinstance(v, str) and len(v) > 200:
                # 매우 긴 문자열 (JSON 등) 잘라서 노출
                v = v[:200] + "...(+%d)" % (len(v) - 200)
            row_dict[c] = v
        rows.append(row_dict)

    return {
        "table":       table_name,
        "label":       meta.get("label", table_name),
        "kind":        meta.get("kind", "other"),
        "columns":     columns,
        "total":       total,
        "limit":       limit,
        "offset":      offset,
        "page":        (offset // limit) + 1,
        "page_count":  (total + limit - 1) // limit if limit > 0 else 1,
        "session_id":  session_id,
        "rows":        rows,
    }


@router.get("/tables/customer_contexts/{ctx_id}")
async def get_context_detail(ctx_id: int) -> dict:
    """customer_contexts JSON 본문 조회"""
    ex = get_executor()
    row = ex.fetchone(
        "SELECT id, session_id, scenario_id, stage, context_json, created_at "
        "FROM customer_contexts WHERE id = ?",
        [ctx_id],
    )
    if row is None:
        raise HTTPException(404, "Context not found")
    import json as _json
    return {
        "id":           int(row[0]),
        "session_id":   row[1],
        "scenario_id":  row[2],
        "stage":        row[3],
        "context_json": _json.loads(row[4]),
        "created_at":   row[5].isoformat() if row[5] else None,
    }


@router.get("/cell/{table_name}/{row_id}/{column}")
async def get_cell_full(table_name: str, row_id: str, column: str) -> dict:
    """긴 문자열(JSON 등) 전체 값 조회"""
    if table_name not in _list_user_tables():
        raise HTTPException(404, f"Table not found: {table_name}")
    columns = _table_columns(table_name)
    if column not in columns:
        raise HTTPException(404, "Column not found")
    if "id" not in columns:
        raise HTTPException(400, "Table has no id column")
    ex = get_executor()
    r = ex.fetchone(f"SELECT {column} FROM {table_name} WHERE id = ?", [row_id])
    if r is None:
        raise HTTPException(404, "Row not found")
    return {"table": table_name, "row_id": row_id, "column": column, "value": r[0]}
