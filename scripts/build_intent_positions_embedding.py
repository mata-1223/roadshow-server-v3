#!/usr/bin/env python3
"""
intent_positions.json (임베딩 + UMAP 기반) 산출 스크립트.

L1 grid 백업과 같은 형식으로 산출하므로 산출 후 덮어쓰면
서버·클라이언트 코드 변경 없이 시연 화면이 새 좌표로 동작.

사전 설치 필요:
    pip install sentence-transformers umap-learn

실행:
    cd roadshow-server-v3
    python scripts/build_intent_positions_embedding.py

옵션:
    --model        sentence-transformer 모델 이름 (기본: jhgan/ko-sroberta-multitask)
    --neighbors    UMAP n_neighbors (기본: 15)
    --min-dist     UMAP min_dist (기본: 0.15)
    --seed         UMAP random_state (기본: 42)
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

L1_COLORS = {
    "INT-1000": "#3b82f6",
    "INT-2000": "#10b981",
    "INT-3000": "#eab308",
    "INT-4000": "#a855f7",
    "INT-5000": "#ef4444",
    "INT-6000": "#f97316",
    "INT-7000": "#1f2937",
}


def _normalize_to_range(values, target_min=-1.0, target_max=1.0):
    import numpy as np
    v = np.asarray(values, dtype=float)
    vmin, vmax = v.min(axis=0), v.max(axis=0)
    span = (vmax - vmin)
    span[span == 0] = 1.0
    return (v - vmin) / span * (target_max - target_min) + target_min


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model",     default="jhgan/ko-sroberta-multitask")
    parser.add_argument("--neighbors", type=int,   default=15)
    parser.add_argument("--min-dist",  type=float, default=0.15)
    parser.add_argument("--seed",      type=int,   default=42)
    args = parser.parse_args()

    try:
        import numpy as np
        from sentence_transformers import SentenceTransformer
        import umap
    except ImportError as e:
        raise SystemExit(
            "Missing dependencies. Install with:\n"
            "    pip install sentence-transformers umap-learn\n"
            f"({e})"
        )

    scenario_dir = Path(__file__).parent.parent / "scenarios" / "cs-myk-v3"
    with open(scenario_dir / "intents.json", encoding="utf-8") as f:
        intents_data = json.load(f)
    intents = intents_data["intents"] if isinstance(intents_data, dict) else intents_data
    print(f"Loaded {len(intents)} intents")

    # 1. 임베딩
    print(f"Loading model: {args.model}")
    model = SentenceTransformer(args.model)
    texts = [f"{it['name']} ({it['L1_name']} > {it['L2_name']})" for it in intents]
    print(f"Encoding {len(texts)} texts ...")
    emb = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
    print(f"Embeddings shape: {emb.shape}")

    # 2. UMAP 차원 축소
    print(f"UMAP: n_neighbors={args.neighbors}, min_dist={args.min_dist}")
    reducer = umap.UMAP(
        n_components=2,
        n_neighbors=args.neighbors,
        min_dist=args.min_dist,
        metric="cosine",
        random_state=args.seed,
    )
    coords = reducer.fit_transform(emb)
    coords_norm = _normalize_to_range(coords, -1.0, 1.0)

    # 3. payload 구성
    intent_positions = [
        {
            "intent_id": it["id"],
            "L1_id":     it["L1_id"],
            "x":         round(float(coords_norm[i, 0]), 4),
            "y":         round(float(coords_norm[i, 1]), 4),
        }
        for i, it in enumerate(intents)
    ]

    # L1 zone centroid (= 같은 L1 점들의 평균)
    from collections import defaultdict
    by_l1: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for p in intent_positions:
        by_l1[p["L1_id"]].append((p["x"], p["y"]))
    l1_zones = []
    seen_l1_names = {it["L1_id"]: it["L1_name"] for it in intents}
    for l1_id, pts in by_l1.items():
        cx = round(sum(x for x, _ in pts) / len(pts), 4)
        cy = round(sum(y for _, y in pts) / len(pts), 4)
        l1_zones.append({
            "L1_id":    l1_id,
            "L1_name":  seen_l1_names.get(l1_id, l1_id),
            "centroid": {"x": cx, "y": cy},
            "color":    L1_COLORS.get(l1_id, "#94a3b8"),
        })

    payload = {
        "scenario_id":      "cs-myk-v3",
        "embedding_model":  args.model,
        "reducer":          "umap",
        "reducer_params":   {
            "n_neighbors":  args.neighbors,
            "min_dist":     args.min_dist,
            "metric":       "cosine",
            "random_state": args.seed,
        },
        "coord_range":      [-1, 1],
        "generated_at":     datetime.utcnow().isoformat() + "Z",
        "intents":          intent_positions,
        "l1_zones":         l1_zones,
    }

    out_path = scenario_dir / "intent_positions.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
