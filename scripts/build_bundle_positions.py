#!/usr/bin/env python3
"""결합(bundle-v3) intent_positions.json (L1 grid 백업 좌표) 산출. 5개 L1 zone."""
import json
import math
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.engines import config

L1_ZONES = {
    "INT-B1000": {"L1_name": "가입 확대",       "centroid": (-0.55,  0.55), "color": "#10b981"},
    "INT-B2000": {"L1_name": "할인 최적화",     "centroid": ( 0.55,  0.55), "color": "#a855f7"},
    "INT-B3000": {"L1_name": "회선/서비스 확장", "centroid": ( 0.00, -0.05), "color": "#3b82f6"},
    "INT-B4000": {"L1_name": "유지/락인",       "centroid": (-0.55, -0.55), "color": "#eab308"},
    "INT-B5000": {"L1_name": "이탈 검토",       "centroid": ( 0.60, -0.55), "color": "#1f2937"},
}
ZONE_RADIUS = 0.22

SCENARIO_ID = "bundle-v3"


def _place(i: int, total: int, centroid):
    cx, cy = centroid
    if total == 1:
        return cx, cy
    angle = 2 * math.pi * i / total
    r = ZONE_RADIUS * (0.45 if i < total / 2 else 0.95)
    return round(cx + r * math.cos(angle), 4), round(cy + r * math.sin(angle), 4)


def main():
    sdir = Path(__file__).parent.parent / "scenarios" / SCENARIO_ID
    intents = config.get_taxonomy(SCENARIO_ID)["intents"]
    by_l1 = {}
    for it in intents:
        by_l1.setdefault(it["L1_id"], []).append(it)

    positions = []
    for l1_id, group in by_l1.items():
        c = L1_ZONES[l1_id]["centroid"]
        for i, it in enumerate(group):
            x, y = _place(i, len(group), c)
            positions.append({"intent_id": it["id"], "L1_id": l1_id, "x": x, "y": y})

    payload = {
        "scenario_id": "bundle-v3",
        "embedding_model": "(backup: L1 grid)",
        "reducer": "(none)", "reducer_params": {}, "coord_range": [-1, 1],
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "note": "L1 5개 zone 동심원 배치 백업 좌표.",
        "intents": positions,
        "l1_zones": [
            {"L1_id": k, "L1_name": v["L1_name"],
             "centroid": {"x": v["centroid"][0], "y": v["centroid"][1]}, "color": v["color"]}
            for k, v in L1_ZONES.items()
        ],
    }
    out = sdir / "intent_positions.json"
    json.dump(payload, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Wrote {out} (intents={len(positions)}, zones={len(L1_ZONES)})")


if __name__ == "__main__":
    main()
