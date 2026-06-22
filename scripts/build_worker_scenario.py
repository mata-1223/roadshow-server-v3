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
#   key       : 코드 (앞 1자리가 L1)
#   name      : Intent 명
#   type      : Rule | Model
#   features  : 추론 핵심 batch feature (Index/Score)
#   apps      : 이 Intent로 직접 신호를 주는 앱 entity
#   service   : 추천 서비스
#   push      : MyKT 앱 Push 문구
#   gmusic    : 🎵 지니뮤직 채널 — {playlist, desc} (없으면 생략)
#   genie     : 🏠 기가지니·홈IoT 채널 — {command, devices[], desc} (없으면 생략)
#   biz       : 💼 비즈니스 임팩트 — {tag, kpi, note}
TAX = [
    dict(key="110", name="동굴속 휴식", type="Model",
         features=["Burnout Deep Score", "Isolation Tendency Index", "Sleep Disturbance Index"],
         apps=[], service="지니뮤직 힐링·ASMR 콘텐츠",
         push="오늘 하루도 수고하셨습니다. MyKT 지니뮤직 ASMR 플레이리스트로 조용한 휴식 시간을 가져보세요.",
         genie=dict(command="동굴 모드 켜줘",
                    devices=["🪟 커튼 닫기", "💡 조명 어둡게", "🔒 도어락 이중잠금"],
                    desc="외부를 닫고 아늑하게 — 혼자 있고 싶은 상태를 집 환경으로 받쳐줍니다."),
         biz=dict(tag="홈IoT 활용", kpi="기가지니 사용 ↑", note="동굴 모드 자동 세팅으로 기가지니 활용")),
    dict(key="120", name="에너지 절약 모드", type="Model",
         features=["Fatigue Load Index", "Burnout Deep Score"],
         apps=["delivery"], service="배달 제휴 할인 혜택",
         push="지친 저녁, 직접 준비하지 않아도 괜찮아요. MyKT 멤버십 배달 할인 쿠폰이 도착했습니다.",
         genie=dict(command="청소 좀 해줘",
                    devices=["🤖 로봇청소기 가동"],
                    desc="기력이 없을 때 집안일을 대신 — 최소한의 부담으로 정돈된 환경 유지."),
         biz=dict(tag="제휴수익", kpi="멤버십 ↑", note="배달·생활 제휴 전환")),
    dict(key="130", name="늦은 밤 디지털 활동", type="Rule",
         features=["Sleep Disturbance Index", "Digital Escape Score"],
         apps=["sns", "ott"], service="수면·명상 콘텐츠",
         push="늦은 시간까지 깨어 계시네요. 지니뮤직 수면 유도 콘텐츠로 편안한 밤을 준비해보세요.",
         gmusic=dict(playlist="수면 플레이리스트",
                     desc="새벽 시간대 청취 이력을 바탕으로 잠들기 좋은 사운드를 큐레이션."),
         genie=dict(command="취침 환경으로 바꿔줘",
                    devices=["📺 올레tv OFF", "🎵 지니뮤직 수면사운드", "🛏️ 모션베드 콰이어트 슬립"],
                    desc="TV에서 수면 음악으로 자연스럽게 핸드오프 — 화면을 끄고 숙면 모드로."),
         biz=dict(tag="구독 ARPU", kpi="지니뮤직 ↑", note="수면 콘텐츠 구독 전환")),
    dict(key="140", name="생활 리듬 불규칙", type="Model",
         features=["Fatigue Load Index", "Isolation Tendency Index", "weekend_out"],
         apps=["sns", "ott"], service="건강·운동 제휴 혜택",
         push="최근 생활 리듬이 불규칙해 보입니다. 운동·건강 제휴 혜택으로 가벼운 산책부터 시작해보세요.",
         genie=dict(command="아침 루틴 규칙적으로",
                    devices=["⏰ 7시 알람", "🪟 7시 블라인드 열기", "💡 조명 점등"],
                    desc="아침을 일정하게 — 불규칙해진 생활 리듬을 환경으로 다잡습니다."),
         biz=dict(tag="홈IoT 활용", kpi="기가지니 사용 ↑", note="아침 루틴 자동화로 기가지니를 매일 활용")),
    dict(key="210", name="즉각 스트레스 해소", type="Rule",
         features=["Burnout Deep Score", "Fatigue Load Index"],
         apps=["delivery", "shopping"], service="배달·쇼핑 멤버십 할인",
         push="오늘 사용할 수 있는 배달·쇼핑 멤버십 할인 혜택이 있습니다. 작은 보상으로 하루를 마무리해보세요.",
         gmusic=dict(playlist="신나는 플리",
                     desc="기분 전환용 업비트 — 도파민을 끌어올리는 플레이리스트."),
         biz=dict(tag="구독 ARPU", kpi="지니뮤직 ↑", note="기분 전환 플레이리스트로 지니뮤직 활용")),
    dict(key="220", name="환경 전환 욕구", type="Rule",
         features=["Recovery Motivation Score", "Isolation Tendency Index"],
         apps=["travel"], service="여행·숙박 프로모션",
         push="이번 주말 잠시 떠나보는 건 어떨까요? MyKT 전용 숙박 할인 혜택을 확인해보세요.",
         genie=dict(command="외출모드로 바꿔줘",
                    devices=["💡 조명 OFF", "🔌 플러그 OFF", "🔒 도어락 잠금"],
                    desc="즉흥 나들이를 가볍게 — 길안내·날씨와 함께 외출 환경을 한 번에 정리."),
         biz=dict(tag="제휴수익", kpi="여행·숙박 ↑", note="여행·숙박 제휴 프로모션 전환")),
    dict(key="230", name="신체 회복 시도", type="Rule",
         features=["Recovery Motivation Score", "Fatigue Load Index"],
         apps=["exercise"], service="헬스·러닝 제휴 쿠폰",
         push="운동을 시작하기 좋은 타이밍입니다. 헬스·러닝 제휴 쿠폰이 준비되어 있습니다.",
         gmusic=dict(playlist="운동할 때 듣는 음악",
                     desc="러닝·홈트 템포에 맞춘 운동 플레이리스트."),
         genie=dict(command="운동 타이머 맞춰줘",
                    devices=["⏱️ 운동 타이머 설정"],
                    desc="가볍게 몸을 움직이는 루틴을 지원."),
         biz=dict(tag="제휴수익", kpi="헬스 제휴 ↑", note="헬스·러닝 제휴 전환")),
    dict(key="240", name="심리·감정 회복", type="Rule",
         features=["Recovery Motivation Score", "Isolation Tendency Index"],
         apps=["mental_recovery", "music"], service="지니뮤직 명상·힐링 콘텐츠",
         push="마음을 쉬게 해줄 시간이 필요해 보입니다. 지니뮤직 명상 콘텐츠를 추천드립니다.",
         gmusic=dict(playlist="힐링 음악",
                     desc="마음을 가라앉히는 명상·힐링 사운드."),
         genie=dict(command="힐링 모드로 바꿔줘",
                    devices=["🌫️ 디퓨저 ON", "💡 조명 따뜻하게·낮춤"],
                    desc="감정을 쉬게 하는 분위기로 — 향과 빛으로 안정감을 더합니다."),
         biz=dict(tag="구독 ARPU", kpi="지니뮤직 ↑", note="힐링·명상 구독 전환")),
    dict(key="250", name="일상 회복", type="Rule",
         features=["Recovery Motivation Score", "Isolation Tendency Index"],
         apps=["messenger", "reading", "exercise"], service="카페·문화 멤버십 혜택",
         push="오랜만에 지인과 연락해보는 건 어떨까요? 카페 멤버십 할인 혜택을 활용해보세요.",
         genie=dict(command="안부 챙기기 일정 추가해줘",
                    devices=["📅 캘린더: 이번 주말 친구 만나기"],
                    desc="관계 회복의 첫걸음을 일정으로 — 일상으로 돌아오는 작은 계기."),
         biz=dict(tag="홈IoT 활용", kpi="기가지니 사용 ↑", note="안부 일정 등록으로 기가지니 활용")),
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


# 채널 — kind: 프론트의 범용 렌더러가 채널 종류별 목업을 결정 (시나리오 특화 코드 지양)
#   phone-push  : 휴대폰 락스크린 푸시 목업
#   music-card  : 지니뮤직 플레이리스트 카드
#   device-voice: 기가지니 음성 명령 + 홈IoT 기기 동작 칩
CHANNELS = [
    {"id": "push", "name": "앱 Push", "icon": "📱", "kind": "phone-push",
     "characteristic": "고객 상태에 맞는 추천 서비스를 MyKT 앱 Push 메시지로 제공 — 번아웃 완화·일상 회복 지원"},
    {"id": "genie_music", "name": "지니뮤직", "icon": "🎵", "kind": "music-card",
     "characteristic": "평소 청취 이력·시간대 취향을 바탕으로 지금 상태에 맞는 플레이리스트를 큐레이션"},
    {"id": "gigagenie", "name": "기가지니 · 홈IoT", "icon": "🏠", "kind": "device-voice",
     "characteristic": "음성 한마디로 집안 환경(조명·커튼·도어락·가전)을 상태에 맞게 자동 세팅"},
]


def build_actions():
    actions = {}
    for t in TAX:
        iid = f"INT-W{t['key']}"
        act = {"push": t["push"], "service": t["service"]}
        if t.get("gmusic"):
            act["genie_music"] = t["gmusic"]
        if t.get("genie"):
            act["gigagenie"] = t["genie"]
        if t.get("biz"):
            act["business_value"] = t["biz"]
        actions[iid] = act
    return {"scenario_id": SCENARIO_ID, "version": "0.1.0",
            "description": "직장인 시나리오 Intent별 멀티채널 활용 예시 (Push·지니뮤직·기가지니) + 비즈니스 임팩트",
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
