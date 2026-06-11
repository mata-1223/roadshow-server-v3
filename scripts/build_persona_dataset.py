#!/usr/bin/env python3
"""
페르소나 기반 가상 시드 데이터셋 생성.

흐름:
  1. 8개 페르소나 정의 (가중치·답변 분포·선호 행동 시퀀스)
  2. 가중치에 따라 N명 샘플링
  3. 각 고객의 설문 답변·batch feature·행동 시퀀스 시뮬레이션
  4. config.behavior_signals(entity→Intent) 매핑으로 양성 Intent 라벨 산출
  5. scenarios/cs-myk-v3/seed_dataset.json 적재

실행:
    cd roadshow-server-v3
    python scripts/build_persona_dataset.py --n 500 --seed 42
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.engines import config, cs  # noqa: E402
from scripts._dataset_common import (  # noqa: E402
    parse_args, build_samples, tree_action_resolver, write_dataset, print_label_stats,
)

SCENARIO_ID = "cs-myk-v3"
SCENARIO_DIR = Path(__file__).parent.parent / "scenarios" / SCENARIO_ID

# ─────────────────────────────────────────────────────────────
# 페르소나 정의
#   weight        : 전체 데이터셋에서 차지하는 비율
#   answer_dist   : {question_id: {answer_code: weight}}
#   action_seqs   : 선호 행동 시퀀스 후보들 (각각 [behavior_id, ...])
#   extra_intents : 행동 매핑 외에 활성으로 표시할 Intent (도메인 지식)
# ─────────────────────────────────────────────────────────────
PERSONAS = [
    {
        "id": "P1",
        "name": "데이터 헤비 + 안정 (추천 수용형)",
        "weight": 0.15,
        "answer_dist": {
            "Q1": {"A": 0.3, "B": 0.5, "C": 0.2},        # 20~40대
            "Q2": {"B": 0.3, "C": 0.4, "D": 0.3},        # 1년~5년+
            "Q3": {"A": 0.2, "B": 0.5, "C": 0.3},        # 5~10만원+
            "Q4": {"C": 0.4, "D": 0.6},                  # 인터넷+IPTV 또는 풀결합
            "Q5": {"B": 0.5, "C": 0.5},                  # 2~4회선+
            "Q6": {"A": 0.7, "C": 0.3},                  # 데이터/콘텐츠 헤비
            "Q7": {"B": 0.4, "C": 0.6},                  # 가끔/매달 부족
            "Q8": {"A": 0.7, "B": 0.3},                  # 청구 안정
            "Q9": {"A": 0.8, "B": 0.2},                  # 품질 안정
            "Q10": {"B": 0.4, "C": 0.6},                 # 멤버십 활용
            "Q11": {"A": 0.6, "B": 0.4},                 # OTT 매일/주2~4
            "Q12": {"B": 0.4, "C": 0.4, "D": 0.2},       # 단말 1~3년
            "Q13": {"A": 0.5, "B": 0.4, "C": 0.1},
        },
        "action_seqs": [
            ["1-E", "2-E1"], ["1-E", "2-E2"], ["1-A", "2-A2"],
            ["1-D", "2-D2"], ["1-E", "2-E3"],
        ],
        "extra_intents": ["INT-4310", "INT-4320", "INT-4330", "INT-2130"],
    },
    {
        "id": "P2",
        "name": "청구 급증 + 품질 불만 (이탈 고위험)",
        "weight": 0.12,
        "answer_dist": {
            "Q1": {"B": 0.3, "C": 0.4, "D": 0.3},
            "Q2": {"C": 0.4, "D": 0.6},                  # 장기 사용자
            "Q3": {"A": 0.2, "B": 0.5, "C": 0.3},
            "Q4": {"A": 0.4, "B": 0.4, "C": 0.2},        # 결합 약함
            "Q5": {"A": 0.6, "B": 0.4},
            "Q6": {"A": 0.4, "B": 0.3, "D": 0.3},
            "Q7": {"B": 0.5, "C": 0.5},
            "Q8": {"B": 0.4, "C": 0.6},                  # 청구 급증
            "Q9": {"B": 0.5, "C": 0.5},                  # 품질 CS 많음
            "Q10": {"A": 0.7, "B": 0.3},
            "Q11": {"B": 0.5, "C": 0.5},
            "Q12": {"C": 0.4, "D": 0.6},                 # 단말 노후
            "Q13": {"A": 0.7, "B": 0.3},
        },
        "action_seqs": [
            ["1-B", "2-B1"], ["1-C", "2-C2"], ["1-C", "2-C3"],
            ["1-B", "2-B1", "BACK", "1-C", "2-C2"],
            ["1-F", "2-F3"],
        ],
        "extra_intents": ["INT-7110", "INT-7120", "INT-7310", "INT-5410", "INT-3210"],
    },
    {
        "id": "P3",
        "name": "시니어 저사용 (음성 헤비)",
        "weight": 0.12,
        "answer_dist": {
            "Q1": {"D": 0.4, "E": 0.6},                  # 50~60대+
            "Q2": {"C": 0.3, "D": 0.7},                  # 장기
            "Q3": {"C": 0.3, "D": 0.7},                  # 3~6만원
            "Q4": {"A": 0.6, "B": 0.4},                  # 결합 약함
            "Q5": {"A": 0.8, "B": 0.2},
            "Q6": {"B": 0.8, "D": 0.2},                  # 음성 헤비
            "Q7": {"A": 0.9, "B": 0.1},
            "Q8": {"A": 0.7, "B": 0.3},
            "Q9": {"A": 0.6, "B": 0.4},
            "Q10": {"A": 0.9, "B": 0.1},                 # 멤버십 안 씀
            "Q11": {"D": 0.8, "C": 0.2},                 # OTT 안 봄
            "Q12": {"D": 0.7, "C": 0.3},                 # 단말 오래
            "Q13": {"A": 0.95, "B": 0.05},
        },
        "action_seqs": [
            ["1-B", "2-B2"], ["1-B", "2-B3"], ["1-F", "2-F3"],
            ["1-A", "2-A3"], ["1-C", "2-C1"],
        ],
        "extra_intents": ["INT-2150", "INT-2420", "INT-1240", "INT-5330", "INT-3110"],
    },
    {
        "id": "P4",
        "name": "출장 잦은 직장인 (로밍 의향)",
        "weight": 0.08,
        "answer_dist": {
            "Q1": {"B": 0.5, "C": 0.5},                  # 30~40대
            "Q2": {"B": 0.3, "C": 0.4, "D": 0.3},
            "Q3": {"A": 0.3, "B": 0.5, "C": 0.2},
            "Q4": {"C": 0.3, "D": 0.7},
            "Q5": {"B": 0.6, "C": 0.4},
            "Q6": {"D": 0.7, "A": 0.3},                  # 업무 헤비
            "Q7": {"B": 0.5, "C": 0.5},
            "Q8": {"A": 0.5, "B": 0.5},
            "Q9": {"A": 0.7, "B": 0.3},
            "Q10": {"B": 0.5, "C": 0.5},
            "Q11": {"A": 0.4, "B": 0.5, "C": 0.1},
            "Q12": {"B": 0.4, "C": 0.4, "D": 0.2},
            "Q13": {"B": 0.5, "C": 0.5},                 # 해외 출국
        },
        "action_seqs": [
            ["1-A", "2-A3"], ["1-E", "2-E2"], ["1-E", "2-E3"],
            ["1-D", "2-D2"],
        ],
        "extra_intents": ["INT-2140", "INT-2540", "INT-1140", "INT-2410"],
    },
    {
        "id": "P5",
        "name": "가족 결합 활용 가족",
        "weight": 0.13,
        "answer_dist": {
            "Q1": {"C": 0.6, "D": 0.4},                  # 40~50대
            "Q2": {"C": 0.3, "D": 0.7},
            "Q3": {"B": 0.4, "C": 0.6},
            "Q4": {"D": 0.8, "C": 0.2},                  # 풀결합 위주
            "Q5": {"B": 0.4, "C": 0.6},                  # 가족 많음
            "Q6": {"A": 0.5, "C": 0.5},
            "Q7": {"B": 0.4, "C": 0.6},
            "Q8": {"A": 0.4, "B": 0.6},
            "Q9": {"A": 0.5, "B": 0.5},
            "Q10": {"B": 0.4, "C": 0.6},
            "Q11": {"A": 0.5, "B": 0.5},
            "Q12": {"B": 0.4, "C": 0.4, "D": 0.2},
            "Q13": {"A": 0.6, "B": 0.4},
        },
        "action_seqs": [
            ["1-E", "2-E3"], ["1-C", "2-C1"], ["1-D", "2-D1"],
            ["1-D", "2-D2"],
        ],
        "extra_intents": ["INT-6110", "INT-6120", "INT-6210", "INT-4210", "INT-1340"],
    },
    {
        "id": "P6",
        "name": "이탈 의향 강 (해지 검토)",
        "weight": 0.08,
        "answer_dist": {
            "Q1": {"B": 0.4, "C": 0.4, "D": 0.2},
            "Q2": {"C": 0.4, "D": 0.6},                  # 장기 후 이탈
            "Q3": {"A": 0.4, "B": 0.4, "C": 0.2},
            "Q4": {"A": 0.5, "B": 0.5},                  # 결합 약함
            "Q5": {"A": 0.7, "B": 0.3},
            "Q6": {"A": 0.4, "B": 0.3, "D": 0.3},
            "Q7": {"B": 0.4, "C": 0.6},
            "Q8": {"B": 0.4, "C": 0.6},
            "Q9": {"B": 0.4, "C": 0.6},
            "Q10": {"A": 0.8, "B": 0.2},                 # 혜택 못 챙김
            "Q11": {"C": 0.4, "D": 0.6},
            "Q12": {"C": 0.4, "D": 0.6},
            "Q13": {"A": 0.6, "B": 0.4},
        },
        "action_seqs": [
            ["1-C", "2-C2"], ["1-C", "2-C3"],
            ["1-C", "2-C2", "BACK", "1-C", "2-C3"],
            ["1-B", "2-B1", "BACK", "1-C", "2-C2", "EXIT"],
        ],
        "extra_intents": ["INT-7110", "INT-7120", "INT-7130", "INT-7210", "INT-7310"],
    },
    {
        "id": "P7",
        "name": "신규 가입 콘텐츠 헤비",
        "weight": 0.10,
        "answer_dist": {
            "Q1": {"A": 0.7, "B": 0.3},                  # 20~30대
            "Q2": {"A": 0.7, "B": 0.3},                  # 1년 미만
            "Q3": {"B": 0.3, "C": 0.5, "D": 0.2},
            "Q4": {"A": 0.6, "B": 0.4},                  # 결합 없음
            "Q5": {"A": 0.7, "B": 0.3},
            "Q6": {"A": 0.5, "C": 0.5},
            "Q7": {"B": 0.3, "C": 0.7},
            "Q8": {"A": 0.6, "B": 0.4},
            "Q9": {"A": 0.8, "B": 0.2},
            "Q10": {"B": 0.5, "C": 0.5},
            "Q11": {"A": 0.7, "B": 0.3},                 # OTT 매일
            "Q12": {"A": 0.4, "B": 0.6},                 # 신단말
            "Q13": {"A": 0.7, "B": 0.3},
        },
        "action_seqs": [
            ["1-D", "2-D2"], ["1-D", "2-D3"], ["1-E", "2-E1"],
            ["1-A", "2-A1"],
        ],
        "extra_intents": ["INT-4310", "INT-2310", "INT-2410", "INT-1410"],
    },
    {
        "id": "P8",
        "name": "단말 교체 임박 (약정 만료)",
        "weight": 0.10,
        "answer_dist": {
            "Q1": {"B": 0.3, "C": 0.5, "D": 0.2},
            "Q2": {"C": 0.4, "D": 0.6},                  # 약정 후반
            "Q3": {"B": 0.4, "C": 0.4, "D": 0.2},
            "Q4": {"C": 0.4, "D": 0.6},
            "Q5": {"B": 0.5, "C": 0.5},
            "Q6": {"A": 0.5, "C": 0.5},
            "Q7": {"B": 0.5, "C": 0.5},
            "Q8": {"A": 0.5, "B": 0.5},
            "Q9": {"A": 0.7, "B": 0.3},
            "Q10": {"B": 0.5, "C": 0.5},
            "Q11": {"A": 0.4, "B": 0.5, "C": 0.1},
            "Q12": {"D": 0.8, "C": 0.2},                 # 3년+
            "Q13": {"A": 0.6, "B": 0.4},
        },
        "action_seqs": [
            ["1-E", "2-E2"], ["1-C", "2-C1"], ["1-E", "2-E2", "BACK", "1-D", "2-D1"],
            ["1-A", "2-A1"],
        ],
        "extra_intents": ["INT-2410", "INT-2440", "INT-2530", "INT-1330", "INT-2110"],
    },
    {
        "id": "P9",
        "name": "비용 민감 절감 추구",
        "weight": 0.07,
        "answer_dist": {
            "Q1": {"B": 0.3, "C": 0.4, "D": 0.3},
            "Q2": {"B": 0.3, "C": 0.4, "D": 0.3},
            "Q3": {"D": 0.6, "C": 0.3, "E": 0.1},        # 저가
            "Q4": {"A": 0.5, "B": 0.5},
            "Q5": {"A": 0.7, "B": 0.3},
            "Q6": {"B": 0.4, "A": 0.3, "C": 0.3},
            "Q7": {"A": 0.4, "B": 0.4, "C": 0.2},
            "Q8": {"A": 0.4, "B": 0.4, "C": 0.2},
            "Q9": {"A": 0.7, "B": 0.3},
            "Q10": {"A": 0.5, "B": 0.4, "C": 0.1},
            "Q11": {"B": 0.4, "C": 0.4, "D": 0.2},
            "Q12": {"C": 0.4, "D": 0.6},
            "Q13": {"A": 0.8, "B": 0.2},
        },
        "action_seqs": [
            ["1-E", "2-E1"], ["1-D", "2-D1"], ["1-B", "2-B1"],
            ["1-D", "2-D3"],
        ],
        "extra_intents": ["INT-7310", "INT-2150", "INT-4110", "INT-4120", "INT-7340"],
    },
    {
        "id": "P10",
        "name": "혜택 적극 활용 VIP",
        "weight": 0.05,
        "answer_dist": {
            "Q1": {"C": 0.4, "D": 0.4, "B": 0.2},
            "Q2": {"D": 0.9, "C": 0.1},                  # 장기 우수 고객
            "Q3": {"A": 0.5, "B": 0.5},                  # 고액 요금제
            "Q4": {"D": 0.9, "C": 0.1},
            "Q5": {"C": 0.7, "B": 0.3},
            "Q6": {"A": 0.4, "C": 0.4, "D": 0.2},
            "Q7": {"B": 0.5, "C": 0.5},
            "Q8": {"A": 0.7, "B": 0.3},
            "Q9": {"A": 0.7, "B": 0.3},
            "Q10": {"C": 0.9, "B": 0.1},                 # 멤버십 적극
            "Q11": {"A": 0.6, "B": 0.4},
            "Q12": {"B": 0.4, "C": 0.4, "D": 0.2},
            "Q13": {"B": 0.5, "C": 0.5},
        },
        "action_seqs": [
            ["1-D", "2-D2"], ["1-D", "2-D1"], ["1-D", "2-D3"],
            ["1-E", "2-E2"],
        ],
        "extra_intents": ["INT-1440", "INT-4240", "INT-4220", "INT-4230", "INT-4320"],
    },
]


# entity → 양성 Intent 매핑은 config.get_behavior_signals("cs-myk-v3")
# (= L2_inference.ranker.behavior_signals)를 단일 소스로 사용 — bundle/worker와 동일.


def main() -> None:
    args = parse_args()
    behaviors = config.get_behaviors(SCENARIO_ID)

    rows = build_samples(
        n=args.n, seed=args.seed, personas=PERSONAS, engine=cs,
        seq_key="action_seqs", action_resolver=tree_action_resolver(behaviors),
        entity_intents=config.get_behavior_signals(SCENARIO_ID),   # 단일 소스(bundle/worker와 동일)
        cust_prefix="C",
    )

    write_dataset(SCENARIO_DIR / "seed_dataset.json", rows, SCENARIO_ID, len(PERSONAS), args.seed)

    # CS 상세: Persona 분포
    persona_counts = Counter(r["persona_id"] for r in rows)
    print(f"\n── Persona 분포 ────────────────────────────────────────")
    for pid, cnt in sorted(persona_counts.items()):
        name = next(p["name"] for p in PERSONAS if p["id"] == pid)
        print(f"  {pid:4s} {name:32s} : {cnt:4d} ({cnt/len(rows)*100:5.1f}%)")
    print_label_stats(rows, top_n=20)


if __name__ == "__main__":
    main()
