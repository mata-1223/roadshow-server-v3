#!/usr/bin/env python3
"""
직장인(worker-v3) 시나리오 카탈로그 생성기.

단일 TAXONOMY 정의로부터 intents.json / actions.json / behavior_intents.json 생성.
시나리오_직장인:
  1.1 직장인 Domain Intent Taxonomy (L1 2 · L2 9)
  3.1 앱 선택지 (10개 앱 단일 선택)
  4.2 활용 방안 (MyKT 앱 Push 단일 채널)

실행:
    cd roadshow-server-v3
    python scripts/build_worker_scenario.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts._scenario_common import emit_layers  # noqa: E402

SCENARIO_ID = "worker-v3"
OUT_DIR = Path(__file__).parent.parent / "scenarios" / SCENARIO_ID

L1 = {
    "1": ("INT-W100", "번아웃 심화"),
    "2": ("INT-W200", "번아웃 완화 시도"),
}

# L3(=L2 수준) Intent:
#   key      : 코드 (앞 1자리가 L1)
#   name     : Intent 명
#   type     : Rule | Model
#   features : 추론 핵심 batch feature (Index/Score)
#   apps     : 이 Intent로 직접 신호를 주는 앱 entity
#   service  : 추천 서비스
#   push     : MyKT 앱 Push 문구
TAX = [
    dict(key="110", name="동굴속 휴식", type="Model",
         features=["Burnout Deep Score", "Isolation Tendency Index", "Sleep Disturbance Index"],
         apps=["music"], service="지니뮤직 힐링·ASMR 콘텐츠",
         push="오늘 하루도 수고하셨습니다. MyKT 지니뮤직 ASMR 플레이리스트로 조용한 휴식 시간을 가져보세요."),
    dict(key="120", name="에너지 최소화", type="Model",
         features=["Fatigue Load Index", "Burnout Deep Score"],
         apps=[], service="배달 제휴 할인 혜택",
         push="지친 저녁, 직접 준비하지 않아도 괜찮아요. MyKT 멤버십 배달 할인 쿠폰이 도착했습니다."),
    dict(key="130", name="수면 회피 / 야간 자극 추구", type="Rule",
         features=["Sleep Disturbance Index", "Digital Escape Score"],
         apps=["sns", "ott"], service="수면·명상 콘텐츠",
         push="늦은 시간까지 깨어 계시네요. 지니뮤직 수면 유도 콘텐츠로 편안한 밤을 준비해보세요."),
    dict(key="140", name="일상 루틴 붕괴", type="Model",
         features=["Fatigue Load Index", "Isolation Tendency Index", "weekend_out"],
         apps=[], service="건강·운동 제휴 혜택",
         push="최근 생활 리듬이 불규칙해 보입니다. 운동·건강 제휴 혜택으로 가벼운 산책부터 시작해보세요."),
    dict(key="210", name="즉각 스트레스 해소", type="Rule",
         features=["Burnout Deep Score", "Fatigue Load Index"],
         apps=["delivery", "shopping"], service="배달·쇼핑 멤버십 할인",
         push="오늘 사용할 수 있는 배달·쇼핑 멤버십 할인 혜택이 있습니다. 작은 보상으로 하루를 마무리해보세요."),
    dict(key="220", name="일탈·환경 전환 욕구", type="Rule",
         features=["Recovery Motivation Score", "Isolation Tendency Index"],
         apps=["travel"], service="여행·숙박 프로모션",
         push="이번 주말 잠시 떠나보는 건 어떨까요? MyKT 전용 숙박 할인 혜택을 확인해보세요."),
    dict(key="230", name="신체 회복 시도", type="Rule",
         features=["Recovery Motivation Score", "Fatigue Load Index"],
         apps=["exercise"], service="헬스·러닝 제휴 쿠폰",
         push="운동을 시작하기 좋은 타이밍입니다. 헬스·러닝 제휴 쿠폰이 준비되어 있습니다."),
    dict(key="240", name="심리·감정 회복", type="Rule",
         features=["Recovery Motivation Score", "Isolation Tendency Index"],
         apps=["mental_recovery", "music"], service="지니뮤직 명상·힐링 콘텐츠",
         push="마음을 쉬게 해줄 시간이 필요해 보입니다. 지니뮤직 명상 콘텐츠를 추천드립니다."),
    dict(key="250", name="일상 회복", type="Rule",
         features=["Recovery Motivation Score", "Isolation Tendency Index"],
         apps=["messenger", "reading"], service="카페·문화 멤버십 혜택",
         push="오랜만에 지인과 연락해보는 건 어떨까요? 카페 멤버십 할인 혜택을 활용해보세요."),
]


def build_intents():
    intents = []
    for t in TAX:
        l1_id, l1_name = L1[t["key"][0]]
        iid = f"INT-W{t['key']}"
        intents.append({
            "id": iid, "name": t["name"],
            "L1_id": l1_id, "L1_name": l1_name,
            "L2_id": iid, "L2_name": t["name"],
            "inference_type": t["type"], "features": t["features"],
        })
    return {"scenario_id": SCENARIO_ID, "version": "0.1.0",
            "description": "직장인 번아웃/회복 시나리오 Intent Taxonomy",
            "intents": intents}


CHANNELS = [
    {"id": "push", "name": "앱 Push", "icon": "📱",
     "characteristic": "고객 상태에 맞는 추천 서비스를 MyKT 앱 Push 메시지로 제공 — 번아웃 완화·일상 회복 지원"},
]


def build_actions():
    actions = {}
    for t in TAX:
        iid = f"INT-W{t['key']}"
        actions[iid] = {"push": t["push"], "service": t["service"]}
    return {"scenario_id": SCENARIO_ID, "version": "0.1.0",
            "description": "직장인 시나리오 Intent별 MyKT 앱 Push 활용 예시",
            "channels": CHANNELS, "actions": actions}


def build_behavior_intents():
    entity_intents = {}
    for t in TAX:
        iid = f"INT-W{t['key']}"
        for app in t["apps"]:
            entity_intents.setdefault(app, []).append(iid)
    return {"scenario_id": SCENARIO_ID, "version": "0.1.0",
            "description": "직장인 앱 선택(entity) → 직접 신호 Intent 매핑",
            "entity_intents": entity_intents}


def main():
    emit_layers(
        OUT_DIR / "engine",
        taxonomy=build_intents(),
        context_library=build_actions(),
        behavior_signals=build_behavior_intents()["entity_intents"],
    )
    from collections import Counter
    ints = build_intents()["intents"]
    print("inference_type:", Counter(i["inference_type"] for i in ints))
    bi = build_behavior_intents()["entity_intents"]
    print("app entities mapped:", list(bi.keys()))


if __name__ == "__main__":
    main()
