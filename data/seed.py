from __future__ import annotations
"""
시나리오 카탈로그 시드 (Intent / Action / Behavior)
"""
import json
import logging
from pathlib import Path

from config import settings
from data.executor import get_executor

logger = logging.getLogger(__name__)

_SCENARIO_DIR = Path(__file__).parent.parent / "scenarios" / settings.SCENARIO_ID


def _load_json(filename: str) -> dict:
    with open(_SCENARIO_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def seed_catalogs() -> None:
    ex = get_executor()

    # ── 시나리오 메타 ────────────────────────────────────────
    intents_data = _load_json("intents.json")
    ex.execute(
        "INSERT OR REPLACE INTO scenarios (id, name, version, description) VALUES (?, ?, ?, ?)",
        [
            settings.SCENARIO_ID,
            "마이K 앱 Intent Taxonomy 시연",
            intents_data["version"],
            intents_data.get("description", ""),
        ],
    )

    # ── Intent 카탈로그 (116개) ──────────────────────────────
    existing = ex.fetchone("SELECT COUNT(*) FROM catalog_intents")
    if existing and existing[0] > 0:
        ex.execute("DELETE FROM catalog_intents")

    rows = [
        [
            i["id"], i["name"],
            i["L1_id"], i["L1_name"],
            i["L2_id"], i["L2_name"],
            i["inference_type"],
            json.dumps(i.get("features", []), ensure_ascii=False),
        ]
        for i in intents_data["intents"]
    ]
    ex.executemany(
        "INSERT INTO catalog_intents (intent_id, intent_name, L1_id, L1_name, L2_id, L2_name, inference_type, features_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    logger.info(f"Seeded catalog_intents: {len(rows)} rows")

    # ── Action 카탈로그 ──────────────────────────────────────
    actions_data = _load_json("actions.json")
    existing = ex.fetchone("SELECT COUNT(*) FROM catalog_actions")
    if existing and existing[0] > 0:
        ex.execute("DELETE FROM catalog_actions")
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
                    f"{intent_id}#{channel}", channel,
                    json.dumps([intent_id], ensure_ascii=False),
                    "", channel, message,
                ])
    else:
        # 구버전: action 리스트
        for a in raw_actions:
            a_rows.append([
                a["id"], a["name"],
                json.dumps(a.get("intents", []), ensure_ascii=False),
                a.get("condition", ""), a["channel"], a.get("message", ""),
            ])
    ex.executemany(
        "INSERT INTO catalog_actions (action_id, action_name, intents_json, condition, channel, message) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        a_rows,
    )
    logger.info(f"Seeded catalog_actions: {len(a_rows)} rows")

    # ── Behavior 카탈로그 ────────────────────────────────────
    behaviors_data = _load_json("behaviors.json")
    existing = ex.fetchone("SELECT COUNT(*) FROM catalog_behaviors")
    if existing and existing[0] > 0:
        ex.execute("DELETE FROM catalog_behaviors")
    b_rows: list[list] = []
    if behaviors_data.get("structure") == "tree-2step":
        # 새 양식: step1.behaviors + step2.by_parent + step2.common
        for b in behaviors_data["step1"]["behaviors"]:
            b_rows.append([b["id"], 1, b["name"], b["event_type"], b["entity"]])
        for parent_id, items in behaviors_data["step2"]["by_parent"].items():
            for b in items:
                b_rows.append([b["id"], 2, b["name"], b["event_type"], b["entity"]])
        for b in behaviors_data["step2"]["common"]:
            b_rows.append([b["id"], 2, b["name"], b["event_type"], b["entity"]])
    else:
        # 옛 양식: steps[] 평면
        for step_block in behaviors_data["steps"]:
            step = step_block["step"]
            for b in step_block["behaviors"]:
                b_rows.append([b["id"], step, b["name"], b["event_type"], b["entity"]])
    ex.executemany(
        "INSERT INTO catalog_behaviors (behavior_id, step, behavior_name, event_type, entity) "
        "VALUES (?, ?, ?, ?, ?)",
        b_rows,
    )
    logger.info(f"Seeded catalog_behaviors: {len(b_rows)} rows")


def load_intents_catalog() -> list[dict]:
    """Intent 카탈로그 조회 (Intent inference에서 사용)"""
    ex = get_executor()
    df = ex.to_pandas("SELECT intent_id, intent_name, L1_id, L1_name, L2_id, L2_name, inference_type, features_json FROM catalog_intents")
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


def load_behaviors_catalog() -> dict[str, dict]:
    """behavior_id → behavior info"""
    ex = get_executor()
    df = ex.to_pandas("SELECT behavior_id, step, behavior_name, event_type, entity FROM catalog_behaviors")
    result = {}
    for _, r in df.iterrows():
        result[r["behavior_id"]] = {
            "step":          int(r["step"]),
            "name":          r["behavior_name"],
            "event_type":    r["event_type"],
            "entity":        r["entity"],
        }
    return result
