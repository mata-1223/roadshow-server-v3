#!/usr/bin/env python3
"""
결합(bundle-v3) 페르소나 기반 시드 데이터셋 생성.

CS의 build_cs_dataset.py와 동일 구조이나 결합 엔진/행동/매핑을 사용한다.
  1. 8개 결합 페르소나 정의 (답변 분포·선호 행동 시퀀스·expected_intents)
  2. 가중치 샘플링 → 설문 답변·batch/pattern/event feature·양성 Intent 라벨 생성
  3. scenarios/bundle-v3/seed_dataset.json 적재

실행:
    cd roadshow-server-v3
    python scripts/build_bundle_dataset.py --n 500 --seed 42
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.engines import config, get_engine  # noqa: E402
from scripts._dataset_common import (  # noqa: E402
    parse_args, build_samples, tree_action_resolver, write_dataset, print_label_stats,
)


SCENARIO_ID = "bundle-v3"
SCENARIO_DIR = Path(__file__).parent.parent / "scenarios" / SCENARIO_ID


# 결합 페르소나: answer_dist {qid: {code: w}}, action_seqs [[behavior_id..]], expected_intents
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
        "expected_intents": ["INT-B1110", "INT-B1210", "INT-B1310", "INT-B1410"],
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
        "expected_intents": ["INT-B3110", "INT-B1110", "INT-B3310", "INT-B3140"],
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
        "expected_intents": ["INT-B2210", "INT-B2340", "INT-B2110"],
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
        "expected_intents": ["INT-B4110", "INT-B4120", "INT-B4210", "INT-B4320"],
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
        "action_seqs": [["1-E", "2-E4"], ["1-E", "2-E4"], ["1-E", "2-E2"], ["1-E", "2-E4", "BACK", "1-E", "2-E4", "EXIT"]],
        "expected_intents": ["INT-B5410", "INT-B5420", "INT-B5120"],
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
        "action_seqs": [["1-A", "2-A2"], ["1-A", "2-A4"], ["1-D", "2-D2"], ["1-A", "2-A2", "BACK", "1-D", "2-D2"]],
        "expected_intents": ["INT-B1230", "INT-B2310"],
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
        "action_seqs": [["1-C", "2-C3"], ["1-C", "2-C1", "BACK", "1-C", "2-C2"], ["1-C", "2-C3", "BACK", "1-C", "2-C4"], ["1-C", "2-C2", "BACK", "1-C", "2-C4"]],
        "expected_intents": ["INT-B3120", "INT-B3130", "INT-B3140", "INT-B3150"],
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
        "action_seqs": [["1-A", "2-A1"], ["1-C", "2-C5"], ["1-A", "2-A3"], ["1-E", "2-E4"]],
        "expected_intents": ["INT-B2210", "INT-B5230", "INT-B2340", "INT-B1210"],
    },
]


def main():
    args = parse_args()
    behaviors = config.get_behaviors(SCENARIO_ID)
    entity_intents = config.get_behavior_signals(SCENARIO_ID)

    rows = build_samples(
        n=args.n, seed=args.seed, personas=PERSONAS, engine=get_engine(SCENARIO_ID),
        behavior_labels=False,   # 행동→intent는 ranker(behavior_signals)가 담당 → 모델은 프로필 affinity만 학습
        seq_key="action_seqs", action_resolver=tree_action_resolver(behaviors),
        entity_intents=entity_intents, cust_prefix="BC",
    )

    write_dataset(SCENARIO_DIR / "seed_dataset.json", rows, SCENARIO_ID, len(PERSONAS), args.seed)
    print_label_stats(rows, total=43, top_n=20)


if __name__ == "__main__":
    main()
