#!/usr/bin/env python3
"""
직장인(worker-v3) 페르소나 기반 시드 데이터셋 생성.

단일 앱 선택(app_open) 구조. CS/결합과 달리 2단 트리가 아니라 앱 entity 시퀀스.

실행:
    cd roadshow-server-v3
    python scripts/build_worker_dataset.py --n 500 --seed 42
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.engines import config
from core.engines.worker import build_batch_features, pattern_features  # noqa: E402
from core.extractor import get_extractor  # noqa: E402

SCENARIO_ID = "worker-v3"
SCENARIO_DIR = Path(__file__).parent.parent / "scenarios" / SCENARIO_ID

# 페르소나: answer_dist {qid:{code:w}}, app_seqs [[entity..]], extra_intents
PERSONAS = [
    {
        "id": "W1", "name": "번아웃 심화·동굴형 (집콕·고립)", "weight": 0.14,
        "answer_dist": {"Q1": {"C": 0.4, "D": 0.3, "E": 0.3}, "Q2": {"B": 0.5, "C": 0.5}, "Q3": {"C": 0.4, "D": 0.6},
                        "Q4": {"C": 0.4, "D": 0.6}, "Q5": {"C": 0.4, "D": 0.6}, "Q6": {"A": 0.9, "B": 0.1},
                        "Q7": {"A": 0.8, "B": 0.2}, "Q8": {"A": 0.6, "B": 0.4}, "Q9": {"C": 0.6, "B": 0.4}},
        "app_seqs": [["music"], ["ott", "music"], ["music", "ott"]],
        "extra_intents": ["INT-W110", "INT-W130"],
    },
    {
        "id": "W2", "name": "번아웃 심화·에너지 소진 (무기력)", "weight": 0.13,
        "answer_dist": {"Q1": {"C": 0.4, "D": 0.3, "E": 0.3}, "Q2": {"A": 0.3, "B": 0.7}, "Q3": {"C": 0.5, "D": 0.5},
                        "Q4": {"C": 0.4, "D": 0.6}, "Q5": {"C": 0.5, "D": 0.5}, "Q6": {"A": 0.8, "B": 0.2},
                        "Q7": {"A": 0.7, "B": 0.3}, "Q8": {"A": 0.5, "B": 0.5}, "Q9": {"B": 0.5, "C": 0.5}},
        "app_seqs": [["delivery"], ["delivery", "ott"], ["ott", "delivery"]],
        "extra_intents": ["INT-W120", "INT-W210"],
    },
    {
        "id": "W3", "name": "야간 자극 추구 (수면 붕괴)", "weight": 0.12,
        "answer_dist": {"Q1": {"A": 0.3, "B": 0.3, "C": 0.4}, "Q2": {"B": 0.5, "C": 0.5}, "Q3": {"B": 0.5, "C": 0.5},
                        "Q4": {"C": 0.5, "D": 0.5}, "Q5": {"B": 0.4, "C": 0.6}, "Q6": {"A": 0.6, "B": 0.4},
                        "Q7": {"A": 0.5, "B": 0.5}, "Q8": {"B": 0.5, "C": 0.5}, "Q9": {"C": 0.9, "B": 0.1}},
        "app_seqs": [["sns"], ["ott"], ["sns", "ott"], ["ott", "sns"]],
        "extra_intents": ["INT-W130"],
    },
    {
        "id": "W4", "name": "즉각 보상 추구 (배달·쇼핑)", "weight": 0.12,
        "answer_dist": {"Q1": {"A": 0.4, "B": 0.3, "C": 0.3}, "Q2": {"B": 0.5, "C": 0.5}, "Q3": {"B": 0.5, "C": 0.5},
                        "Q4": {"C": 0.5, "D": 0.5}, "Q5": {"C": 0.5, "D": 0.5}, "Q6": {"A": 0.7, "B": 0.3},
                        "Q7": {"A": 0.5, "B": 0.5}, "Q8": {"B": 0.5, "C": 0.5}, "Q9": {"B": 0.5, "C": 0.5}},
        "app_seqs": [["delivery"], ["shopping"], ["delivery", "shopping"]],
        "extra_intents": ["INT-W210"],
    },
    {
        "id": "W5", "name": "일탈·환경 전환 욕구 (여행)", "weight": 0.10,
        "answer_dist": {"Q1": {"A": 0.4, "B": 0.3, "C": 0.3}, "Q2": {"B": 0.5, "C": 0.5}, "Q3": {"B": 0.5, "C": 0.5},
                        "Q4": {"B": 0.4, "C": 0.6}, "Q5": {"B": 0.5, "C": 0.5}, "Q6": {"A": 0.5, "B": 0.5},
                        "Q7": {"B": 0.5, "C": 0.5}, "Q8": {"B": 0.5, "C": 0.5}, "Q9": {"B": 0.6, "C": 0.4}},
        "app_seqs": [["travel"], ["travel", "shopping"]],
        "extra_intents": ["INT-W220"],
    },
    {
        "id": "W6", "name": "신체 회복 시도 (운동)", "weight": 0.10,
        "answer_dist": {"Q1": {"A": 0.4, "B": 0.3, "C": 0.3}, "Q2": {"B": 0.5, "C": 0.5}, "Q3": {"B": 0.5, "C": 0.5},
                        "Q4": {"B": 0.5, "C": 0.5}, "Q5": {"B": 0.5, "C": 0.5}, "Q6": {"A": 0.5, "B": 0.5},
                        "Q7": {"B": 0.4, "C": 0.6}, "Q8": {"C": 0.5, "B": 0.5}, "Q9": {"A": 0.4, "B": 0.6}},
        "app_seqs": [["exercise"], ["exercise", "music"]],
        "extra_intents": ["INT-W230"],
    },
    {
        "id": "W7", "name": "심리·감정 회복 (명상)", "weight": 0.10,
        "answer_dist": {"Q1": {"B": 0.4, "C": 0.3, "D": 0.3}, "Q2": {"B": 0.5, "C": 0.5}, "Q3": {"B": 0.5, "C": 0.5},
                        "Q4": {"C": 0.5, "D": 0.5}, "Q5": {"B": 0.5, "C": 0.5}, "Q6": {"A": 0.6, "B": 0.4},
                        "Q7": {"A": 0.5, "B": 0.5}, "Q8": {"A": 0.4, "B": 0.6}, "Q9": {"B": 0.6, "C": 0.4}},
        "app_seqs": [["mental_recovery"], ["mental_recovery", "music"], ["music", "mental_recovery"]],
        "extra_intents": ["INT-W240"],
    },
    {
        "id": "W8", "name": "일상 회복 (지인 연락·자기계발)", "weight": 0.10,
        "answer_dist": {"Q1": {"A": 0.4, "B": 0.3, "C": 0.3}, "Q2": {"B": 0.5, "C": 0.5}, "Q3": {"B": 0.5, "C": 0.5},
                        "Q4": {"B": 0.5, "C": 0.5}, "Q5": {"A": 0.4, "B": 0.6}, "Q6": {"B": 0.6, "A": 0.4},
                        "Q7": {"B": 0.4, "C": 0.6}, "Q8": {"C": 0.4, "D": 0.6}, "Q9": {"A": 0.4, "B": 0.6}},
        "app_seqs": [["messenger"], ["reading"], ["messenger", "reading"]],
        "extra_intents": ["INT-W250"],
    },
    {
        "id": "W9", "name": "일상 루틴 붕괴 (불규칙)", "weight": 0.09,
        "answer_dist": {"Q1": {"B": 0.4, "C": 0.3, "D": 0.3}, "Q2": {"B": 0.5, "C": 0.5}, "Q3": {"C": 0.5, "D": 0.5},
                        "Q4": {"C": 0.4, "D": 0.6}, "Q5": {"C": 0.5, "D": 0.5}, "Q6": {"A": 0.7, "B": 0.3},
                        "Q7": {"A": 0.9, "B": 0.1}, "Q8": {"A": 0.6, "B": 0.4}, "Q9": {"B": 0.4, "C": 0.6}},
        "app_seqs": [["ott", "delivery"], ["sns", "delivery"], ["delivery", "ott", "sns"]],
        "extra_intents": ["INT-W140", "INT-W120"],
    },
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    rng = random.Random(args.seed)

    entity_intents = config.get_behavior_signals(SCENARIO_ID)
    ex = get_extractor()

    rows = []
    for i in range(args.n):
        persona = rng.choices(PERSONAS, weights=[p["weight"] for p in PERSONAS], k=1)[0]
        answers = {qid: rng.choices(list(d), weights=list(d.values()), k=1)[0]
                   for qid, d in persona["answer_dist"].items()}
        batch = build_batch_features(answers)
        seq = rng.choice(persona["app_seqs"])
        actions = [{"behavior_id": f"app-{e}", "event_type": "app_open", "entity": e} for e in seq]

        sid = f"WC{i + 1:05d}"
        ex.reset(sid)
        for a in actions:
            ex.add_event(sid, "app_open", a["entity"])
        pat = pattern_features(sid)
        ex.reset(sid)

        positives = set(persona["extra_intents"])
        for a in actions:
            positives.update(entity_intents.get(a["entity"], []))
        labels = {iid: 1 for iid in positives}

        scalar = lambda d: {k: v for k, v in d.items() if not isinstance(v, (list, dict))}
        rows.append({
            "cust_id": sid, "persona_id": persona["id"], "persona_name": persona["name"],
            "survey_answers": answers,
            "batch_features": scalar(batch),
            "pattern_features": scalar(pat),
            "event_features": {},
            "actions": actions,
            "intent_labels": labels,
        })

    out_path = SCENARIO_DIR / "seed_dataset.json"
    json.dump({"scenario_id": "worker-v3", "n_samples": len(rows), "n_personas": len(PERSONAS),
               "seed": args.seed, "samples": rows},
              open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Wrote {out_path} ({len(rows)} samples)")

    label_counts = Counter()
    for r in rows:
        for iid in r["intent_labels"]:
            label_counts[iid] += 1
    print("\n── 양성 라벨 ──")
    for iid, c in label_counts.most_common():
        print(f"  {iid}: {c} ({c/len(rows)*100:.1f}%)")


if __name__ == "__main__":
    main()
