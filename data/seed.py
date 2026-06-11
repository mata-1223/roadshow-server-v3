from __future__ import annotations
"""
시나리오 카탈로그 시드 (Intent / Action / Behavior)

등록된 모든 시나리오(available_scenarios)를 catalog_* 테이블에 scenario_id와 함께 적재한다.
→ AdminPage가 시나리오별 카탈로그를 올바르게 조회할 수 있게 한다.
"""
import json
import logging

from config import settings
from data.executor import get_executor
from core.engines import config, available_scenarios

logger = logging.getLogger(__name__)

# 시나리오 메타(scenarios 테이블) 표시용 이름
_SCENARIO_NAMES = {
    "cs-myk-v3": "마이K CS 상담 시연",
    "bundle-v3": "결합 상품 추천 시연",
    "worker-v3": "직장인 라이프케어 시연",
}


def seed_catalogs() -> None:
    """등록된 모든 시나리오의 카탈로그를 적재(기존 카탈로그는 전체 교체)."""
    ex = get_executor()
    for tbl in ("catalog_intents", "catalog_actions", "catalog_behaviors"):
        ex.execute(f"DELETE FROM {tbl}")
    for sid in available_scenarios():
        _seed_one(ex, sid)


def _seed_one(ex, scenario_id: str) -> None:
    # ── 시나리오 메타 ────────────────────────────────────────
    taxonomy = config.get_taxonomy(scenario_id)
    description = config.load_layer(scenario_id, "input").get("description", "")
    ex.execute(
        "INSERT OR REPLACE INTO scenarios (id, name, version, description) VALUES (?, ?, ?, ?)",
        [
            scenario_id,
            _SCENARIO_NAMES.get(scenario_id, scenario_id),
            taxonomy.get("version", ""),
            description,
        ],
    )

    # ── Intent 카탈로그 ──────────────────────────────────────
    rows = [
        [
            scenario_id,
            i["id"], i["name"],
            i["L1_id"], i["L1_name"],
            i["L2_id"], i["L2_name"],
            i["inference_type"],
            json.dumps(i.get("features", []), ensure_ascii=False),
        ]
        for i in taxonomy["intents"]
    ]
    ex.executemany(
        "INSERT INTO catalog_intents "
        "(scenario_id, intent_id, intent_name, L1_id, L1_name, L2_id, L2_name, inference_type, features_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )

    # ── Action 카탈로그 ──────────────────────────────────────
    actions_data = config.get_actions(scenario_id)
    a_rows: list[list] = []
    raw_actions = actions_data["actions"]
    if isinstance(raw_actions, dict):
        # v0.2.0: Intent-키 3채널 구조 → intent × channel 로 평면화
        for intent_id, ch_map in raw_actions.items():
            for channel, body in ch_map.items():
                if isinstance(body, dict):  # 고객센터 상담사 컨텍스트 (상황+안내)
                    message = f"상황: {body.get('situation', '')} / 안내: {body.get('guidance', '')}"
                else:
                    message = str(body)
                a_rows.append([
                    scenario_id,
                    f"{intent_id}#{channel}", channel,
                    json.dumps([intent_id], ensure_ascii=False),
                    "", channel, message,
                ])
    else:
        # 구버전: action 리스트
        for a in raw_actions:
            a_rows.append([
                scenario_id,
                a["id"], a["name"],
                json.dumps(a.get("intents", []), ensure_ascii=False),
                a.get("condition", ""), a["channel"], a.get("message", ""),
            ])
    ex.executemany(
        "INSERT INTO catalog_actions "
        "(scenario_id, action_id, action_name, intents_json, condition, channel, message) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        a_rows,
    )

    # ── Behavior 카탈로그 ────────────────────────────────────
    behaviors_data = config.get_behaviors(scenario_id)
    b_rows: list[list] = []
    structure = behaviors_data.get("structure")
    if structure == "tree-2step":
        # 2단계 트리: step1.behaviors + step2.by_parent + step2.common
        for b in behaviors_data["step1"]["behaviors"]:
            b_rows.append([scenario_id, b["id"], 1, b["name"], b["event_type"], b["entity"]])
        for parent_id, items in behaviors_data["step2"]["by_parent"].items():
            for b in items:
                b_rows.append([scenario_id, b["id"], 2, b["name"], b["event_type"], b["entity"]])
        for b in behaviors_data["step2"]["common"]:
            b_rows.append([scenario_id, b["id"], 2, b["name"], b["event_type"], b["entity"]])
    elif structure == "single-select":
        # 단일 선택: apps[] (1단계, app_open 단일화)
        for b in behaviors_data["apps"]:
            b_rows.append([scenario_id, b["id"], 1, b["name"], b["event_type"], b["entity"]])
    else:
        # 옛 양식: steps[] 평면
        for step_block in behaviors_data["steps"]:
            step = step_block["step"]
            for b in step_block["behaviors"]:
                b_rows.append([scenario_id, b["id"], step, b["name"], b["event_type"], b["entity"]])
    ex.executemany(
        "INSERT INTO catalog_behaviors "
        "(scenario_id, behavior_id, step, behavior_name, event_type, entity) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        b_rows,
    )

    logger.info(
        f"Seeded catalog [{scenario_id}]: intents={len(rows)} actions={len(a_rows)} behaviors={len(b_rows)}"
    )


def load_intents_catalog(scenario_id: str = settings.SCENARIO_ID) -> list[dict]:
    """Intent 카탈로그 조회 (시나리오별)"""
    ex = get_executor()
    df = ex.to_pandas(
        "SELECT intent_id, intent_name, L1_id, L1_name, L2_id, L2_name, inference_type, features_json "
        "FROM catalog_intents WHERE scenario_id = ?",
        [scenario_id],
    )
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "id":             r["intent_id"],
            "name":           r["intent_name"],
            "L1_id":          r["L1_id"],
            "L1_name":        r["L1_name"],
            "L2_id":          r["L2_id"],
            "L2_name":        r["L2_name"],
            "inference_type": r["inference_type"],
            "features":       json.loads(r["features_json"]) if r["features_json"] else [],
        })
    return rows


def load_behaviors_catalog(scenario_id: str = settings.SCENARIO_ID) -> dict[str, dict]:
    """behavior_id → behavior info (시나리오별)"""
    ex = get_executor()
    df = ex.to_pandas(
        "SELECT behavior_id, step, behavior_name, event_type, entity "
        "FROM catalog_behaviors WHERE scenario_id = ?",
        [scenario_id],
    )
    result = {}
    for _, r in df.iterrows():
        result[r["behavior_id"]] = {
            "step":          int(r["step"]),
            "name":          r["behavior_name"],
            "event_type":    r["event_type"],
            "entity":        r["entity"],
        }
    return result
