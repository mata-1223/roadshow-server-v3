#!/usr/bin/env python3
"""
직장인(worker-v3) 페르소나 기반 시드 데이터셋 생성.

단일 앱 선택(app_open) 구조. CS/결합과 달리 2단 트리가 아니라 앱 entity 시퀀스.

실행:
    cd roadshow-server-v3
    python scripts/build_worker_dataset.py --n 500 --seed 42
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.engines import config, worker  # noqa: E402
from scripts._dataset_common import (  # noqa: E402
    parse_args, build_samples, app_action_resolver, write_dataset, print_label_stats,
)

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
    args = parse_args()
    entity_intents = config.get_behavior_signals(SCENARIO_ID)

    rows = build_samples(
        n=args.n, seed=args.seed, personas=PERSONAS, engine=worker,
        seq_key="app_seqs", action_resolver=app_action_resolver,
        entity_intents=entity_intents, cust_prefix="WC",
    )

    write_dataset(SCENARIO_DIR / "seed_dataset.json", rows, SCENARIO_ID, len(PERSONAS), args.seed)
    print_label_stats(rows)


if __name__ == "__main__":
    main()
