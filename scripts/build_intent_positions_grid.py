#!/usr/bin/env python3
"""
intent_positions.json (L1 grid 백업 좌표) 산출 스크립트.

의존성 없이 즉시 실행. 임베딩 품질이 보장되기 전 시연 가능한 좌표를
L1 zone 7개로 분리해 배치.

추후 임베딩+UMAP으로 교체 시 같은 형식의 intent_positions.json만 덮어쓰면 됨
(클라이언트·서버 코드 변경 불필요).

실행:
    cd roadshow-server-v3
    python scripts/build_intent_positions_grid.py
"""
import json
import math
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.engines import config

SCENARIO_ID = "cs-myk-v3"
SCENARIO_DIR = Path(__file__).parent.parent / "scenarios" / SCENARIO_ID

# ── L1 zone 정의 ──────────────────────────────────────────────
# (x_center, y_center) — 좌표 범위 [-1, 1]
L1_ZONES = {
    "INT-1000": {"L1_name": "My 정보 조회",   "centroid": (-0.55,  0.55), "color": "#3b82f6"},
    "INT-2000": {"L1_name": "상품 탐색/가입", "centroid": ( 0.05,  0.70), "color": "#10b981"},
    "INT-3000": {"L1_name": "셀프처리",       "centroid": ( 0.60,  0.45), "color": "#eab308"},
    "INT-4000": {"L1_name": "혜택/프로모션",  "centroid": (-0.55, -0.25), "color": "#a855f7"},
    "INT-5000": {"L1_name": "문제 해결/상담", "centroid": (-0.30,  0.10), "color": "#ef4444"},
    "INT-6000": {"L1_name": "관계/공유",      "centroid": ( 0.45, -0.05), "color": "#f97316"},
    "INT-7000": {"L1_name": "이탈/전환",      "centroid": ( 0.65, -0.65), "color": "#1f2937"},
}

# zone 안에서 Intent 배치 반경 (작을수록 밀집)
ZONE_RADIUS = 0.18

# 모든 Intent를 zone centroid 중심으로 동심원에 배치
def _place_in_zone(idx_in_zone: int, total_in_zone: int, centroid: tuple[float, float]) -> tuple[float, float]:
    cx, cy = centroid
    if total_in_zone == 1:
        return cx, cy
    angle = 2 * math.pi * idx_in_zone / total_in_zone
    # 동심원 2개 (내·외)로 분산
    if idx_in_zone < total_in_zone / 2:
        r = ZONE_RADIUS * 0.45
    else:
        r = ZONE_RADIUS * 0.95
    x = cx + r * math.cos(angle)
    y = cy + r * math.sin(angle)
    return round(x, 4), round(y, 4)


def build(scenario_id: Path) -> dict:
    intents_data = config.get_taxonomy(scenario_id)
    intents = intents_data.get("intents", intents_data) if isinstance(intents_data, dict) else intents_data

    # L1별 그룹화
    by_l1: dict[str, list[dict]] = {}
    for intent in intents:
        by_l1.setdefault(intent["L1_id"], []).append(intent)

    intent_positions: list[dict] = []
    for l1_id, group in by_l1.items():
        zone = L1_ZONES.get(l1_id)
        if zone is None:
            raise ValueError(f"Unknown L1: {l1_id}")
        centroid = zone["centroid"]
        for i, intent in enumerate(group):
            x, y = _place_in_zone(i, len(group), centroid)
            intent_positions.append({
                "intent_id": intent["id"],
                "L1_id":     intent["L1_id"],
                "x":         x,
                "y":         y,
            })

    l1_zones_out = [
        {
            "L1_id":    l1_id,
            "L1_name":  meta["L1_name"],
            "centroid": {"x": meta["centroid"][0], "y": meta["centroid"][1]},
            "color":    meta["color"],
        }
        for l1_id, meta in L1_ZONES.items()
    ]

    return {
        "scenario_id":      "cs-myk-v3",
        "embedding_model":  "(backup: L1 grid)",
        "reducer":          "(none)",
        "reducer_params":   {},
        "coord_range":      [-1, 1],
        "generated_at":     datetime.utcnow().isoformat() + "Z",
        "note":             "L1 카테고리별 동심원 배치 백업 좌표. 임베딩+UMAP 산출 시 덮어쓰기 가능.",
        "intents":          intent_positions,
        "l1_zones":         l1_zones_out,
    }


def main() -> None:
    out_path = SCENARIO_DIR / "intent_positions.json"
    payload = build(SCENARIO_ID)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"Wrote {out_path} (intents={len(payload['intents'])}, l1_zones={len(payload['l1_zones'])})")


if __name__ == "__main__":
    main()
