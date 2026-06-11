#!/usr/bin/env python3
"""
결합(bundle-v3) 페르소나 기반 시드 데이터셋 생성.

CS의 build_persona_dataset.py와 동일 구조이나 결합 엔진/행동/매핑을 사용한다.
  1. 8개 결합 페르소나 정의 (답변 분포·선호 행동 시퀀스·extra_intents)
  2. 가중치 샘플링 → 설문 답변·batch/pattern/event feature·양성 Intent 라벨 생성
  3. scenarios/bundle-v3/seed_dataset.json 적재

실행:
    cd roadshow-server-v3
    python scripts/build_bundle_dataset.py --n 500 --seed 42
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
from core.engines.bundle import build_batch_features, pattern_features, event_features  # noqa: E402
from core.extractor import get_extractor  # noqa: E402


SCENARIO_ID = "bundle-v3"
SCENARIO_DIR = Path(__file__).parent.parent / "scenarios" / SCENARIO_ID


# 결합 페르소나: answer_dist {qid: {code: w}}, action_seqs [[behavior_id..]], extra_intents
PERSONAS = [
    {
        "id": "B1", "name": "신규 가입 검토 (결합 미보유)", "weight": 0.13,
        "answer_dist": {
            "Q1": {"A": 0.5, "B": 0.5}, "Q2": {"A": 0.5, "B": 0.4, "C": 0.1},
            "Q3": {"B": 0.4, "C": 0.5, "D": 0.1}, "Q4": {"B": 0.5, "C": 0.5},
            "Q5": {"A": 0.8, "B": 0.2}, "Q6": {"A": 0.4, "B": 0.3, "C": 0.3},
            "Q7": {"A": 0.6, "B": 0.4}, "Q8": {"A": 0.7, "C": 0.3},
            "Q9": {"B": 0.5, "C": 0.5}, "Q10": {"B": 0.5, "C": 0.5},
            "Q11": {"A": 0.4, "B": 0.4, "F": 0.2}, "Q12": {"B": 0.4, "C": 0.6},
        },
        "action_seqs": [["1-B", "2-B3"], ["1-B", "2-B1"], ["1-B", "2-B4"], ["1-A", "2-A1"]],
        "extra_intents": ["INT-B1110", "INT-B1210", "INT-B1310", "INT-B1410"],
    },
    {
        "id": "B2", "name": "가족 결합 활용 (회선 확장)", "weight": 0.14,
        "answer_dist": {
            "Q1": {"A": 0.5, "B": 0.5}, "Q2": {"C": 0.5, "D": 0.5},
            "Q3": {"C": 0.5, "D": 0.5}, "Q4": {"B": 0.4, "C": 0.6},
            "Q5": {"B": 0.4, "C": 0.6}, "Q6": {"A": 0.4, "C": 0.6},
            "Q7": {"B": 0.5, "C": 0.5}, "Q8": {"A": 0.4, "B": 0.6},
            "Q9": {"C": 0.5, "B": 0.5}, "Q10": {"B": 0.5, "C": 0.5},
            "Q11": {"B": 0.4, "F": 0.6}, "Q12": {"A": 0.4, "C": 0.6},
        },
        "action_seqs": [["1-B", "2-B1"], ["1-C", "2-C1"], ["1-C", "2-C3"], ["1-B", "2-B1", "BACK", "1-C", "2-C3"]],
        "extra_intents": ["INT-B3110", "INT-B1110", "INT-B3310", "INT-B3140"],
    },
    {
        "id": "B3", "name": "할인·혜택 추구 (할인 최적화)", "weight": 0.13,
        "answer_dist": {
            "Q1": {"A": 0.5, "B": 0.5}, "Q2": {"B": 0.4, "C": 0.4, "D": 0.2},
            "Q3": {"B": 0.3, "C": 0.4, "D": 0.3}, "Q4": {"A": 0.5, "B": 0.5},
            "Q5": {"A": 0.5, "B": 0.5}, "Q6": {"A": 0.7, "B": 0.3},
            "Q7": {"B": 0.5, "C": 0.5}, "Q8": {"A": 0.5, "B": 0.5},
            "Q9": {"C": 0.4, "D": 0.4, "B": 0.2}, "Q10": {"A": 0.6, "B": 0.4},
            "Q11": {"A": 0.5, "B": 0.5}, "Q12": {"B": 0.4, "C": 0.4, "D": 0.2},
        },
        "action_seqs": [["1-A", "2-A1"], ["1-A", "2-A2"], ["1-A", "2-A3"], ["1-A", "2-A1", "BACK", "1-A", "2-A2"]],
        "extra_intents": ["INT-B2210", "INT-B2230", "INT-B2340", "INT-B2110"],
    },
    {
        "id": "B4", "name": "재약정 임박 (유지/락인)", "weight": 0.12,
        "answer_dist": {
            "Q1": {"A": 0.5, "B": 0.5}, "Q2": {"C": 0.4, "D": 0.6},
            "Q3": {"C": 0.5, "D": 0.5}, "Q4": {"B": 0.5, "C": 0.5},
            "Q5": {"B": 0.5, "C": 0.5}, "Q6": {"A": 0.8, "B": 0.2},
            "Q7": {"C": 0.8, "B": 0.2}, "Q8": {"C": 0.8, "B": 0.2},
            "Q9": {"B": 0.5, "C": 0.5}, "Q10": {"B": 0.5, "C": 0.5},
            "Q11": {"A": 0.3, "B": 0.3, "F": 0.4}, "Q12": {"A": 0.5, "C": 0.5},
        },
        "action_seqs": [["1-D", "2-D1"], ["1-D", "2-D3"], ["1-D", "2-D4"], ["1-D", "2-D1", "BACK", "1-D", "2-D3"]],
        "extra_intents": ["INT-B4110", "INT-B4120", "INT-B4210", "INT-B4320"],
    },
    {
        "id": "B5", "name": "이탈 고위험 (해지 검토)", "weight": 0.12,
        "answer_dist": {
            "Q1": {"A": 0.5, "B": 0.5}, "Q2": {"C": 0.4, "D": 0.6},
            "Q3": {"B": 0.4, "C": 0.4, "D": 0.2}, "Q4": {"A": 0.6, "B": 0.4},
            "Q5": {"A": 0.5, "B": 0.5}, "Q6": {"A": 0.6, "B": 0.4},
            "Q7": {"C": 0.6, "B": 0.4}, "Q8": {"C": 0.6, "A": 0.4},
            "Q9": {"C": 0.4, "D": 0.4, "B": 0.2}, "Q10": {"A": 0.6, "B": 0.4},
            "Q11": {"A": 0.3, "C": 0.3, "D": 0.2, "E": 0.2}, "Q12": {"B": 0.4, "C": 0.4, "D": 0.2},
        },
        "action_seqs": [["1-E", "2-E1"], ["1-E", "2-E4"], ["1-E", "2-E2"], ["1-E", "2-E1", "BACK", "1-E", "2-E4", "EXIT"]],
        "extra_intents": ["INT-B5110", "INT-B5410", "INT-B5420", "INT-B5120"],
    },
    {
        "id": "B6", "name": "프리미엄 혜택 활용 VIP", "weight": 0.10,
        "answer_dist": {
            "Q1": {"A": 0.5, "B": 0.5}, "Q2": {"C": 0.4, "D": 0.4, "B": 0.2},
            "Q3": {"D": 0.8, "C": 0.2}, "Q4": {"B": 0.4, "C": 0.6},
            "Q5": {"C": 0.7, "B": 0.3}, "Q6": {"A": 0.7, "C": 0.3},
            "Q7": {"C": 0.7, "B": 0.3}, "Q8": {"A": 0.4, "B": 0.6},
            "Q9": {"C": 0.4, "D": 0.6}, "Q10": {"C": 0.8, "B": 0.2},
            "Q11": {"B": 0.4, "F": 0.6}, "Q12": {"B": 0.4, "C": 0.6},
        },
        "action_seqs": [["1-A", "2-A2"], ["1-D", "2-D2"], ["1-A", "2-A4"], ["1-C", "2-C3"]],
        "extra_intents": ["INT-B1230", "INT-B2310", "INT-B2320", "INT-B2330"],
    },
    {
        "id": "B7", "name": "콘텐츠 헤비 (홈서비스 확장)", "weight": 0.13,
        "answer_dist": {
            "Q1": {"A": 0.5, "B": 0.5}, "Q2": {"A": 0.5, "B": 0.5},
            "Q3": {"C": 0.5, "D": 0.5}, "Q4": {"A": 0.5, "B": 0.5},
            "Q5": {"A": 0.6, "B": 0.4}, "Q6": {"A": 0.5, "B": 0.5},
            "Q7": {"A": 0.4, "B": 0.6}, "Q8": {"A": 0.6, "C": 0.4},
            "Q9": {"B": 0.5, "C": 0.5}, "Q10": {"B": 0.5, "C": 0.5},
            "Q11": {"C": 0.3, "D": 0.3, "F": 0.4}, "Q12": {"B": 0.5, "C": 0.5},
        },
        "action_seqs": [["1-C", "2-C2"], ["1-C", "2-C1"], ["1-C", "2-C4"], ["1-C", "2-C3"]],
        "extra_intents": ["INT-B3120", "INT-B3130", "INT-B3140", "INT-B3150"],
    },
    {
        "id": "B8", "name": "비용 민감 절감 추구", "weight": 0.13,
        "answer_dist": {
            "Q1": {"A": 0.5, "B": 0.5}, "Q2": {"B": 0.4, "C": 0.4, "D": 0.2},
            "Q3": {"A": 0.4, "B": 0.4, "C": 0.2}, "Q4": {"A": 0.5, "B": 0.5},
            "Q5": {"A": 0.6, "B": 0.4}, "Q6": {"A": 0.7, "B": 0.3},
            "Q7": {"B": 0.5, "C": 0.5}, "Q8": {"A": 0.4, "C": 0.6},
            "Q9": {"A": 0.4, "B": 0.4, "C": 0.2}, "Q10": {"A": 0.5, "B": 0.5},
            "Q11": {"A": 0.6, "B": 0.4}, "Q12": {"A": 0.4, "D": 0.6},
        },
        "action_seqs": [["1-A", "2-A1"], ["1-E", "2-E3"], ["1-A", "2-A3"], ["1-E", "2-E1"]],
        "extra_intents": ["INT-B2210", "INT-B5230", "INT-B2340", "INT-B1210"],
    },
]


def _resolve_entities(behaviors, seq):
    by_id = {b["id"]: b for b in behaviors["step1"]["behaviors"]}
    for items in behaviors["step2"]["by_parent"].values():
        for b in items:
            by_id[b["id"]] = b
    for b in behaviors["step2"]["common"]:
        by_id[b["id"]] = b
    out = []
    for bid in seq:
        b = by_id.get(bid)
        if b:
            out.append({"behavior_id": b["id"], "event_type": b["event_type"], "entity": b["entity"]})
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    rng = random.Random(args.seed)

    behaviors = config.get_behaviors(SCENARIO_ID)
    entity_intents = config.get_behavior_signals(SCENARIO_ID)
    ex = get_extractor()

    rows = []
    for i in range(args.n):
        persona = rng.choices(PERSONAS, weights=[p["weight"] for p in PERSONAS], k=1)[0]
        answers = {qid: rng.choices(list(d), weights=list(d.values()), k=1)[0]
                   for qid, d in persona["answer_dist"].items()}
        batch = build_batch_features(answers)
        seq = rng.choice(persona["action_seqs"])
        actions = _resolve_entities(behaviors, seq)

        sid = f"BC{i + 1:05d}"
        ex.reset(sid)
        for a in actions:
            ex.add_event(sid, a["event_type"], a["entity"])
        pat = pattern_features(sid)
        evt = event_features(sid)
        ex.reset(sid)

        # 양성 라벨: 행동 entity 매핑 + persona extra_intents
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
            "event_features": scalar(evt),
            "actions": actions,
            "intent_labels": labels,
        })

    out_path = SCENARIO_DIR / "seed_dataset.json"
    json.dump({"scenario_id": "bundle-v3", "n_samples": len(rows), "n_personas": len(PERSONAS),
               "seed": args.seed, "samples": rows},
              open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Wrote {out_path} ({len(rows)} samples)")

    # 통계
    label_counts = Counter()
    for r in rows:
        for iid in r["intent_labels"]:
            label_counts[iid] += 1
    print("\n── 양성 라벨 Top 20 ──")
    for iid, c in label_counts.most_common(20):
        print(f"  {iid}: {c} ({c/len(rows)*100:.1f}%)")
    print(f"\n  총 양성 라벨 Intent 종류: {len(label_counts)} / 50")


if __name__ == "__main__":
    main()
