#!/usr/bin/env python3
"""
시연 흐름 스모크 테스트.

서버를 띄우지 않고도 실제 시연에서 일어나는 추론 흐름을 그대로 호출해
각 단계의 Top 5 / Vector Space 위치 / Δ Probability 변화를 출력.

흐름:
  1) 설문 제출 (infer_batch)
  2) 행동 시퀀스: 1-B → 2-B1 → BACK → 1-C → 2-C2
  3) 각 단계 후 Top 5 + customer position + baseline position 출력
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.executor import init_db, get_executor
from core.extractor import get_extractor
from core.inference import (
    infer_batch,
    infer_with_behavior,
    to_probability_dict,
    to_topn_with_others,
)


# ── 시연 케이스 A: 데이터 헤비 + 안정 고객 (베이스라인은 추천/상품 영역)
#   → 행동 누적으로 이탈/전환 영역으로 이동하는 임팩트를 보여주기 위한 케이스
ANSWERS = {
    "Q1":"B", "Q2":"C", "Q3":"B", "Q4":"D", "Q5":"B",
    "Q6":"A", "Q7":"C",
    "Q8":"A", "Q9":"A", "Q10":"C", "Q11":"A",
    "Q12":"C", "Q13":"A",
}

BEHAVIORS = [
    ("1-B",  "page_view", "billing",            "요금/청구 페이지"),
    ("2-B1", "page_view", "billing_detail",     "청구 상세 항목"),
    ("BACK", "navigate_back", "back_to_step1",  "뒤로가기"),
    ("1-C",  "page_view", "subscription_info",  "가입정보 페이지"),
    ("2-C2", "page_view", "penalty_calc",       "위약금 계산"),
]


def _load_positions() -> tuple[dict, list]:
    pos_path = Path(__file__).parent.parent / "scenarios" / "cs-myk-v3" / "intent_positions.json"
    with open(pos_path, encoding="utf-8") as f:
        data = json.load(f)
    pos_map = {p["intent_id"]: (p["x"], p["y"]) for p in data["intents"]}
    zones = data["l1_zones"]
    return pos_map, zones


def _weighted_center(all_probs: dict, pos_map: dict, key: str) -> tuple[float, float]:
    x = y = w = 0.0
    for iid, pr in all_probs.items():
        pos = pos_map.get(iid)
        if pos is None:
            continue
        v = pr.get(key, 0.0)
        x += v * pos[0]
        y += v * pos[1]
        w += v
    if w == 0:
        return 0.0, 0.0
    return x / w, y / w


def _nearest_zone(pos: tuple[float, float], zones: list) -> str:
    cx, cy = pos
    best, best_d = None, 1e9
    for z in zones:
        dx = cx - z["centroid"]["x"]
        dy = cy - z["centroid"]["y"]
        d = (dx * dx + dy * dy) ** 0.5
        if d < best_d:
            best, best_d = z["L1_name"], d
    return f"{best} (거리 {best_d:.3f})"


def _print_stage(label: str, scores: list, pos_map: dict, zones: list) -> tuple[float, float]:
    all_probs = to_probability_dict(scores)
    top, others = to_topn_with_others(scores, top_n=5)
    cur = _weighted_center(all_probs, pos_map, "p")
    base = _weighted_center(all_probs, pos_map, "p0")

    print(f"\n{'=' * 70}")
    print(f"  {label}")
    print(f"{'=' * 70}")
    print(f"  Top 5:")
    for t in top:
        rc = f"{t['rank_change']:+d}" if t['rank_change'] else "0"
        print(f"    {t['rank']}. {t['intent_id']:9s} {t['intent_nm_ko']:18s} "
              f"p={t['probability']*100:5.1f}%  Δp={t['delta_probability']*100:+5.1f}%p  "
              f"rank_change={rc}")
    print(f"    -.            기타 (n={others['count']:3d})         "
          f"p={others['probability']*100:5.1f}%  Δp={others['delta_probability']*100:+5.1f}%p")
    print(f"  Vector Space:")
    print(f"    customer pos = ({cur[0]:+.3f}, {cur[1]:+.3f})  → {_nearest_zone(cur, zones)}")
    print(f"    baseline pos = ({base[0]:+.3f}, {base[1]:+.3f}) → {_nearest_zone(base, zones)}")
    print(f"    이동 거리: {((cur[0]-base[0])**2 + (cur[1]-base[1])**2)**0.5:.3f}")
    return cur


def main() -> None:
    print("Initializing DB ...")
    init_db()

    session_id = "SMOKE-DEMO-001"
    ex = get_executor()
    # 기존 더미 세션 정리
    ex.execute("DELETE FROM sessions WHERE id = ?", [session_id])
    ex.execute(
        "INSERT INTO sessions (id, scenario_id, stage) VALUES (?, ?, ?)",
        [session_id, "cs-myk-v3", "initial"],
    )

    pos_map, zones = _load_positions()

    # ── Step 0: 설문 제출 (initial) ────────────────────────────
    print("\n[Step 0] 설문 제출 (infer_batch)")
    _, scores = infer_batch(ANSWERS)
    path = [_print_stage("Initial (행동 없음)", scores, pos_map, zones)]

    # ── Step 1+: 행동 시뮬레이션 ──────────────────────────────
    extractor = get_extractor()
    for bid, etype, entity, name in BEHAVIORS:
        # app_exit이면 종료
        if etype == "app_exit":
            print(f"\n[{bid}] {name} — 세션 종료")
            break

        extractor.add_event(session_id, etype, entity)
        _, scores = infer_with_behavior(ANSWERS, session_id)
        cur = _print_stage(f"After {bid} ({name})", scores, pos_map, zones)
        path.append(cur)

    # ── 경로 요약 ──────────────────────────────────────────────
    print(f"\n{'#' * 70}")
    print(f"  Vector Space 이동 경로 ({len(path)} 시점)")
    print(f"{'#' * 70}")
    for i, p in enumerate(path):
        label = "initial" if i == 0 else BEHAVIORS[i-1][0]
        print(f"  [{i}] {label:6s} → ({p[0]:+.3f}, {p[1]:+.3f})  {_nearest_zone(p, zones)}")


if __name__ == "__main__":
    main()
