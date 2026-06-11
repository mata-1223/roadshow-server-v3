#!/usr/bin/env python3
"""
결합(bundle-v3) 시나리오 카탈로그 생성기.

단일 TAXONOMY 정의(소스 오브 트루스)로부터
  - intents.json          : L3 Intent 카탈로그 (id/name/L1/L2/inference_type/features)
  - actions.json          : Intent별 3채널(push / call_center / agent) 활용 예시
  - behavior_intents.json  : behaviors.json entity → 직접 신호 Intent 매핑
세 파일을 일관되게 생성한다.

PDF [2] 시나리오_결합:
  1.1 결합 Domain Intent Taxonomy / 1.2 Metadata / 4.2 활용 방안 표 기반.

실행:
    cd roadshow-server-v3
    python scripts/build_bundle_scenario.py
"""
from __future__ import annotations

import json
from pathlib import Path

SCENARIO_ID = "bundle-v3"
OUT_DIR = Path(__file__).parent.parent / "scenarios" / SCENARIO_ID

# ── L1 / L2 메타 ─────────────────────────────────────────────
L1 = {
    "1": ("INT-B1000", "가입 확대"),
    "2": ("INT-B2000", "할인 최적화"),
    "3": ("INT-B3000", "회선/서비스 확장"),
    "4": ("INT-B4000", "유지/락인"),
    "5": ("INT-B5000", "이탈 검토"),
}
L2 = {
    "11": ("INT-B1100", "결합 가능 여부 탐색"),
    "12": ("INT-B1200", "결합 상품 탐색"),
    "13": ("INT-B1300", "가입 혜택 탐색"),
    "14": ("INT-B1400", "가입 실행 검토"),
    "21": ("INT-B2100", "현재 혜택 점검"),
    "22": ("INT-B2200", "추가 혜택 탐색"),
    "23": ("INT-B2300", "혜택 활용 최적화"),
    "31": ("INT-B3100", "결합 범위 확대"),
    "32": ("INT-B3200", "디바이스/IoT 확장"),
    "33": ("INT-B3300", "결합 구조 재구성"),
    "41": ("INT-B4100", "재약정 검토"),
    "42": ("INT-B4200", "장기 고객 혜택 확인"),
    "43": ("INT-B4300", "결합 유지 영향 확인"),
    "51": ("INT-B5100", "경쟁사 비교"),
    "52": ("INT-B5200", "혜택/비용 불만"),
    "53": ("INT-B5300", "품질 불만"),
    "54": ("INT-B5400", "해지 검토"),
}


# ── L3 Intent 정의 ───────────────────────────────────────────
# 각 항목:
#   key       : L3 코드 3자리 (앞 2자리가 L2)
#   name      : Intent 한글명
#   type      : Rule | Model
#   features  : 추론 핵심 batch feature 명 (PDF 1.2 표 기반)
#   entities  : 이 Intent로 직접 신호를 주는 behavior entity (behavior_intents)
#   push      : 앱 Push 문구
#   cc        : (상황, 안내) 상담사 컨텍스트
#   agent     : AI Agent 발화
TAX: list[dict] = [
    # ── L1=1 가입 확대 ───────────────────────────────────────
    dict(key="111", name="가족 결합 가능 여부 확인", type="Rule",
         features=["family_line_count", "Bundle Opportunity Index"],
         entities=["bundle_eligibility", "family_bundle"],
         push="가족 결합 시 받을 수 있는 할인 혜택을 확인해보세요",
         cc=("가족 결합 가능 여부 탐색", "가족 결합 가능 여부와 예상 할인 금액을 안내"),
         agent="가족 회선을 결합하면 얼마나 절약되는지 계산해볼까요?"),
    dict(key="112", name="인터넷/IPTV 결합 가능 여부 확인", type="Rule",
         features=["service_coverage_ratio", "Bundle Opportunity Index"],
         entities=["internet_iptv_bundle"],
         push="인터넷·TV 결합 시 추가 혜택을 받을 수 있어요",
         cc=("인터넷/IPTV 결합 가능 여부 탐색", "현재 이용 상품 기준 결합 가능 상품을 안내"),
         agent="인터넷과 TV를 함께 이용하면 어떤 혜택이 생기는지 알아볼까요?"),
    dict(key="113", name="현재 요금제 기반 결합 가능 여부 확인", type="Rule",
         features=["plan_tier", "Bundle Opportunity Index"],
         entities=[],
         push="지금 요금제로 받을 수 있는 결합 혜택을 확인해보세요",
         cc=("현재 요금제 기반 결합 가능 여부 확인", "현재 요금제 기준 적용 가능한 결합을 안내"),
         agent="지금 쓰시는 요금제로 결합하면 어떤 혜택이 있는지 볼까요?"),
    dict(key="121", name="할인 중심 결합 상품 탐색", type="Model",
         features=["non_mobile_cost_gap", "Benefit Optimization Index"],
         entities=["discount_calc", "total_bundle"],
         push="할인 혜택이 큰 결합 상품을 추천해드립니다",
         cc=("할인 중심 결합 상품 탐색", "고객님 조건에 맞는 결합 상품을 안내"),
         agent="가장 유리한 결합 상품을 함께 찾아볼까요?"),
    dict(key="122", name="데이터 혜택 중심 결합 상품 탐색", type="Model",
         features=["content_view_mode", "Benefit Engagement Index"],
         entities=[],
         push="데이터 혜택이 큰 결합 상품을 확인해보세요",
         cc=("데이터 혜택 중심 결합 상품 탐색", "데이터 활용이 많은 고객 대상 결합을 안내"),
         agent="데이터를 더 넉넉히 쓸 수 있는 결합을 찾아볼까요?"),
    dict(key="123", name="프리미엄 혜택 중심 결합 상품 탐색", type="Model",
         features=["plan_tier", "Benefit Engagement Index"],
         entities=[],
         push="프리미엄 혜택 중심 결합 상품을 확인해보세요",
         cc=("프리미엄 혜택 중심 결합 상품 탐색", "상위 요금제 기반 프리미엄 결합을 안내"),
         agent="프리미엄 혜택까지 포함된 결합을 살펴볼까요?"),
    dict(key="131", name="신규 가입 혜택 확인", type="Model",
         features=["Bundle Opportunity Index", "Benefit Optimization Index"],
         entities=["internet_signup_benefit"],
         push="신규 가입 고객 전용 혜택을 확인해보세요",
         cc=("신규 가입 혜택 탐색", "현재 가입 가능한 혜택을 안내"),
         agent="가입 시 받을 수 있는 혜택을 정리해볼까요?"),
    dict(key="141", name="온라인 가입 검토", type="Rule",
         features=["Bundle Opportunity Index", "Acquisition Score"],
         entities=["bundle_apply"],
         push="온라인으로 간편하게 가입해보세요",
         cc=("온라인 가입 검토", "온라인 가입 절차를 안내"),
         agent="가입까지 필요한 단계를 안내해드릴까요?"),
    dict(key="142", name="상담 기반 가입 검토", type="Rule",
         features=["Bundle Opportunity Index", "Acquisition Score"],
         entities=["support_consult", "bundle_apply"],
         push="상담사와 함께 가입을 진행해보세요",
         cc=("상담 기반 가입 검토 (상담 인입)", "고객 조건 확인 후 맞춤 결합 가입을 안내"),
         agent="상담사 연결 전에 필요한 정보를 미리 정리해드릴까요?"),
    dict(key="143", name="매장 방문 가입 검토", type="Model",
         features=["Bundle Opportunity Index", "Acquisition Score"],
         entities=[],
         push="가까운 매장에서 가입 상담을 받아보세요",
         cc=("매장 방문 가입 검토", "방문 가능 매장과 준비 서류를 안내"),
         agent="방문 가입 시 필요한 준비물을 안내해드릴까요?"),

    # ── L1=2 할인 최적화 ─────────────────────────────────────
    dict(key="211", name="현재 적용 혜택 확인", type="Rule",
         features=["Benefit Engagement Index", "benefit_utilization"],
         entities=["current_bundle_benefit"],
         push="현재 받고 있는 할인·결합 혜택을 확인해보세요",
         cc=("현재 적용 혜택 확인", "현재 적용 중인 할인 내역을 안내"),
         agent="지금 받고 있는 혜택을 한 번에 정리해드릴까요?"),
    dict(key="221", name="추가 할인 가능 여부 확인", type="Rule",
         features=["Benefit Optimization Index", "non_mobile_cost_gap"],
         entities=["discount_calc"],
         push="추가로 받을 수 있는 할인 혜택이 있는지 확인해보세요",
         cc=("추가 혜택 탐색", "적용 가능한 할인 항목을 안내"),
         agent="현재 조건에서 추가 할인이 가능한지 확인해볼까요?"),
    dict(key="222", name="프로모션/이벤트 혜택 탐색", type="Model",
         features=["Benefit Optimization Index", "benefit_utilization"],
         entities=["promotion_benefit"],
         push="진행 중인 이벤트 혜택을 확인해보세요",
         cc=("프로모션/이벤트 혜택 탐색", "참여 가능한 프로모션을 안내"),
         agent="지금 받을 수 있는 이벤트 혜택을 찾아볼까요?"),
    dict(key="223", name="카드 제휴 혜택 탐색", type="Rule",
         features=["Benefit Optimization Index", "non_mobile_cost_gap"],
         entities=["card_benefit"],
         push="카드 제휴 시 추가 할인 혜택을 받을 수 있어요",
         cc=("카드 제휴 혜택 탐색", "적용 가능한 카드 혜택을 안내"),
         agent="카드 할인 적용 시 얼마나 절약되는지 계산해볼까요?"),
    dict(key="231", name="데이터 혜택 활용 검토", type="Model",
         features=["Benefit Engagement Index", "content_view_mode"],
         entities=[],
         push="아직 활용하지 않은 데이터 혜택을 확인해보세요",
         cc=("데이터 혜택 활용 검토", "미활용 데이터 혜택을 안내"),
         agent="놓치고 있는 데이터 혜택이 있는지 함께 볼까요?"),
    dict(key="232", name="멤버십 혜택 활용 검토", type="Model",
         features=["Benefit Engagement Index", "benefit_utilization"],
         entities=["membership_benefit"],
         push="아직 사용하지 않은 멤버십 혜택을 확인해보세요",
         cc=("멤버십 혜택 활용 검토", "이용 가능한 멤버십 혜택을 안내"),
         agent="멤버십에서 놓치고 있는 혜택을 정리해드릴까요?"),
    dict(key="233", name="OTT/콘텐츠 혜택 활용 검토", type="Model",
         features=["Benefit Engagement Index", "content_view_mode"],
         entities=[],
         push="이용 가능한 OTT 혜택을 확인해보세요",
         cc=("OTT/콘텐츠 혜택 활용 검토", "현재 이용 가능한 콘텐츠 혜택을 안내"),
         agent="아직 쓰지 않은 OTT 혜택이 있는지 확인해볼까요?"),
    dict(key="234", name="미사용 혜택 확인", type="Rule",
         features=["Benefit Engagement Index", "benefit_utilization"],
         entities=["unused_benefit"],
         push="아직 사용하지 않은 혜택이 있습니다",
         cc=("미사용 혜택 확인", "미사용 혜택을 정리해 안내"),
         agent="놓치고 있는 혜택이 있는지 함께 확인해볼까요?"),

    # ── L1=3 회선/서비스 확장 ────────────────────────────────
    dict(key="311", name="가족 회선 추가 검토", type="Rule",
         features=["family_line_count", "Bundle Opportunity Index"],
         entities=["family_bundle"],
         push="가족 회선을 추가하면 할인 혜택이 더 커질 수 있어요",
         cc=("가족 회선 추가 검토", "가족 회선 추가 시 예상 혜택을 안내"),
         agent="가족 회선을 추가하면 얼마나 절약되는지 계산해볼까요?"),
    dict(key="312", name="인터넷 결합 추가 검토", type="Rule",
         features=["Home Service Expansion Index", "service_coverage_ratio"],
         entities=["internet"],
         push="인터넷 결합 시 추가 혜택을 받을 수 있어요",
         cc=("인터넷 결합 추가 검토", "인터넷 결합 상품을 안내"),
         agent="인터넷을 함께 이용하면 얼마나 절약되는지 알아볼까요?"),
    dict(key="313", name="IPTV 결합 추가 검토", type="Rule",
         features=["Home Service Expansion Index", "content_view_mode"],
         entities=["iptv"],
         push="IPTV 결합 시 콘텐츠 혜택을 받을 수 있어요",
         cc=("IPTV 결합 추가 검토", "IPTV 결합 상품과 콘텐츠 혜택을 안내"),
         agent="TV까지 결합하면 어떤 콘텐츠 혜택이 생기는지 볼까요?"),
    dict(key="314", name="인터넷+IPTV 통합 이용 검토", type="Model",
         features=["Home Service Expansion Index", "service_coverage_ratio"],
         entities=["internet_iptv_bundle"],
         push="인터넷+TV 통합 결합 혜택을 확인해보세요",
         cc=("인터넷+IPTV 통합 이용 검토", "통합 결합 시 혜택을 안내"),
         agent="인터넷과 TV를 묶으면 얼마나 유리한지 비교해볼까요?"),
    dict(key="315", name="홈 WiFi 추가 검토", type="Rule",
         features=["Home Service Expansion Index", "household_change"],
         entities=["wifi"],
         push="홈 WiFi 추가 시 더 편리하게 이용할 수 있어요",
         cc=("홈 WiFi 추가 검토", "홈 WiFi 결합 혜택을 안내"),
         agent="홈 WiFi를 추가하면 어떤 점이 좋아지는지 알려드릴까요?"),
    dict(key="321", name="워치 회선 추가 검토", type="Model",
         features=["plan_tier", "Service Expansion Score"],
         entities=[],
         push="워치 전용 회선 혜택을 안내해드릴게요",
         cc=("워치 회선 추가 검토", "워치 전용 회선 혜택을 안내"),
         agent="스마트워치 연결 시 이용 가능한 혜택을 확인해볼까요?"),
    dict(key="322", name="태블릿 결합 추가 검토", type="Model",
         features=["plan_tier", "Service Expansion Score"],
         entities=[],
         push="태블릿 결합 혜택을 확인해보세요",
         cc=("태블릿 결합 추가 검토", "태블릿 결합 회선 혜택을 안내"),
         agent="태블릿을 결합하면 어떤 혜택이 있는지 볼까요?"),
    dict(key="323", name="세컨드 디바이스 연결 검토", type="Model",
         features=["plan_tier", "Service Expansion Score"],
         entities=[],
         push="세컨드 디바이스 연결 혜택을 확인해보세요",
         cc=("세컨드 디바이스 연결 검토", "추가 디바이스 연결 혜택을 안내"),
         agent="추가 디바이스를 연결하면 어떤 혜택이 있는지 알아볼까요?"),
    dict(key="324", name="IoT 기기 연계 검토", type="Model",
         features=["plan_tier", "Service Expansion Score"],
         entities=[],
         push="IoT 기기 연계 혜택을 확인해보세요",
         cc=("IoT 기기 연계 검토", "IoT 기기 연계 결합 혜택을 안내"),
         agent="IoT 기기를 연계하면 어떤 혜택이 있는지 볼까요?"),
    dict(key="331", name="가족 회선 통합 검토", type="Model",
         features=["family_line_count", "Bundle Opportunity Index"],
         entities=[],
         push="가족 회선을 통합하면 더 유리한 결합을 받을 수 있어요",
         cc=("가족 회선 통합 검토", "가족 회선 통합 시 결합 구성을 안내"),
         agent="가족 회선을 통합하면 어떤 혜택이 생기는지 비교해볼까요?"),
    dict(key="332", name="가족 회선 분리 검토", type="Model",
         features=["family_line_count", "household_change"],
         entities=[],
         push="가족 회선 분리 시 변동되는 혜택을 확인해보세요",
         cc=("가족 회선 분리 검토", "회선 분리 시 혜택 변동을 안내"),
         agent="회선을 분리하면 혜택이 어떻게 달라지는지 확인해볼까요?"),
    dict(key="333", name="명의 변경 검토", type="Rule",
         features=["household_change", "family_line_count"],
         entities=[],
         push="결합 구조를 변경하면 더 유리한 혜택을 받을 수 있습니다",
         cc=("명의 변경 검토", "명의 변경 가능한 결합 구성을 안내"),
         agent="현재 상황에 맞게 결합을 다시 구성해볼까요?"),
    dict(key="334", name="대표 회선 변경 검토", type="Rule",
         features=["household_change", "family_line_count"],
         entities=[],
         push="대표 회선 변경 시 결합 혜택을 확인해보세요",
         cc=("대표 회선 변경 검토", "대표 회선 변경 시 혜택 변동을 안내"),
         agent="대표 회선을 바꾸면 결합 혜택이 어떻게 달라지는지 볼까요?"),
    dict(key="335", name="회선 이동 검토", type="Model",
         features=["household_change", "family_line_count"],
         entities=[],
         push="회선 이동 시 결합 구성을 확인해보세요",
         cc=("회선 이동 검토", "회선 이동 시 결합 구성을 안내"),
         agent="회선을 이동하면 결합이 어떻게 바뀌는지 확인해볼까요?"),

    # ── L1=4 유지/락인 ───────────────────────────────────────
    dict(key="411", name="약정 상태 및 연장 혜택 확인", type="Rule",
         features=["contract_status", "Retention Readiness Index"],
         entities=["contract_status"],
         push="약정 상태와 연장 시 받을 수 있는 혜택을 확인해보세요",
         cc=("약정 상태 및 연장 혜택 확인", "현재 약정 상태와 연장 혜택을 안내"),
         agent="약정 연장 시 받을 수 있는 혜택을 정리해드릴까요?"),
    dict(key="412", name="재약정 혜택 비교", type="Model",
         features=["Retention Readiness Index", "Benefit Engagement Index"],
         entities=["renewal_benefit", "renewal_consult"],
         push="재약정 시 받을 수 있는 혜택을 확인해보세요",
         cc=("재약정 검토 (상담 인입)", "현재 재약정 가능 혜택을 비교 안내"),
         agent="재약정과 현재 조건을 비교해볼까요?"),
    dict(key="421", name="장기 혜택 확인", type="Rule",
         features=["tenure_group", "Retention Readiness Index"],
         entities=["long_term_benefit"],
         push="장기 고객 전용 혜택을 확인해보세요",
         cc=("장기 고객 혜택 확인", "고객이 받을 수 있는 장기 혜택을 안내"),
         agent="장기 이용 고객 혜택을 정리해드릴까요?"),
    dict(key="431", name="요금제 변경 영향 확인", type="Model",
         features=["non_mobile_cost_gap", "Retention Readiness Index"],
         entities=[],
         push="요금제 변경 시 결합 혜택 변동을 확인해보세요",
         cc=("요금제 변경 영향 확인", "요금제 변경 시 결합 혜택 변동을 안내"),
         agent="요금제를 바꾸면 결합 혜택에 어떤 영향이 있는지 볼까요?"),
    dict(key="432", name="결합 해지 영향 확인", type="Rule",
         features=["Retention Readiness Index", "Churn Risk Index"],
         entities=["penalty"],
         push="결합 해지 시 변경되는 혜택을 확인해보세요",
         cc=("결합 유지 영향 확인", "결합 해지 시 변동되는 할인 혜택을 안내"),
         agent="결합을 해지하면 어떤 영향이 있는지 비교해볼까요?"),

    # ── L1=5 이탈 검토 ───────────────────────────────────────
    dict(key="511", name="타사 결합 혜택/가격 비교", type="Model",
         features=["Churn Risk Index", "non_mobile_cost_gap"],
         entities=["competitor_compare"],
         push="현재 혜택과 타사 혜택을 비교해보세요",
         cc=("경쟁사 비교", "경쟁사 상품과 비교 안내"),
         agent="현재 혜택과 타사 혜택을 나란히 비교해볼까요?"),
    dict(key="512", name="번호이동 기반 혜택 비교", type="Rule",
         features=["Churn Risk Index", "contract_status"],
         entities=["mnp"],
         push="번호이동 시 받을 수 있는 혜택을 비교해보세요",
         cc=("번호이동 기반 혜택 비교", "번호이동 시 혜택을 비교 안내"),
         agent="번호이동 시 혜택을 현재와 비교해볼까요?"),
    dict(key="521", name="혜택 부족 체감", type="Model",
         features=["dissatisfaction_factor", "Benefit Optimization Index"],
         entities=[],
         push="더 받을 수 있는 혜택이 있는지 확인해보세요",
         cc=("혜택 부족 체감", "추가 적용 가능한 혜택을 안내"),
         agent="지금 받을 수 있는 혜택을 한 번에 정리해드릴까요?"),
    dict(key="522", name="결합 유지 가치 하락", type="Model",
         features=["dissatisfaction_factor", "Retention Readiness Index"],
         entities=[],
         push="결합 유지 시 받을 수 있는 가치를 확인해보세요",
         cc=("결합 유지 가치 하락", "결합 유지 가치를 재안내"),
         agent="결합을 유지하면 어떤 점이 유리한지 다시 정리해드릴까요?"),
    dict(key="523", name="통신비 부담 증가", type="Model",
         features=["non_mobile_cost_gap", "dissatisfaction_factor"],
         entities=[],
         push="통신비를 줄일 수 있는 방법을 확인해보세요",
         cc=("통신비 부담 증가", "비용 부담을 줄일 수 있는 상품을 안내"),
         agent="지금보다 통신비를 절약할 수 있는 방법을 찾아볼까요?"),
    dict(key="531", name="인터넷 품질 불만", type="Rule",
         features=["dissatisfaction_factor", "Churn Risk Index"],
         entities=[],
         push="인터넷 품질 개선 방법을 확인해보세요",
         cc=("인터넷 품질 불만", "현재 인터넷 품질 상태를 점검 안내"),
         agent="인터넷 이용 환경을 함께 점검해볼까요?"),
    dict(key="532", name="IPTV 품질 불만", type="Rule",
         features=["dissatisfaction_factor", "Churn Risk Index"],
         entities=[],
         push="IPTV 품질 개선 방법을 확인해보세요",
         cc=("IPTV 품질 불만", "IPTV 품질 상태를 점검 안내"),
         agent="TV 이용 환경을 함께 점검해볼까요?"),
    dict(key="533", name="모바일 데이터 품질 불만", type="Model",
         features=["dissatisfaction_factor", "Churn Risk Index"],
         entities=[],
         push="모바일 데이터 품질 개선 방법을 확인해보세요",
         cc=("모바일 데이터 품질 불만", "데이터 품질 상태를 점검 안내"),
         agent="데이터 이용 환경을 함께 점검해볼까요?"),
    dict(key="534", name="장애 반복 불만", type="Model",
         features=["dissatisfaction_factor", "Churn Risk Index"],
         entities=[],
         push="반복되는 장애 개선 방법을 확인해보세요",
         cc=("장애 반복 불만", "반복 장애 이력을 점검 안내"),
         agent="장애 이력을 점검하고 개선 방법을 안내해드릴까요?"),
    dict(key="541", name="해지 절차 확인", type="Rule",
         features=["Churn Risk Index", "Retention Readiness Index"],
         entities=["penalty"],
         push="해지 전 절차와 변동 혜택을 미리 확인해보세요",
         cc=("해지 검토", "해지 절차와 해지 시 변동 사항을 안내"),
         agent="해지 시 변경되는 부분을 미리 정리해드릴까요?"),
    dict(key="542", name="위약금 확인", type="Rule",
         features=["Churn Risk Index", "contract_status"],
         entities=["penalty"],
         push="해지 전 위약금 정보를 미리 확인해보세요",
         cc=("위약금 확인", "해지 시 발생 가능한 위약금을 안내"),
         agent="지금 해지하면 위약금이 얼마나 발생하는지 확인해볼까요?"),
    dict(key="543", name="해지 영향 확인", type="Rule",
         features=["Churn Risk Index", "Retention Readiness Index"],
         entities=[],
         push="해지 시 변동되는 혜택과 영향을 확인해보세요",
         cc=("해지 영향 확인", "해지 시 변동되는 결합 혜택을 안내"),
         agent="해지하면 어떤 혜택이 사라지는지 비교해볼까요?"),
    dict(key="544", name="번호이동 절차 확인", type="Rule",
         features=["Churn Risk Index", "contract_status"],
         entities=["mnp"],
         push="번호이동 절차를 미리 확인해보세요",
         cc=("번호이동 절차 확인", "번호이동 절차와 준비 사항을 안내"),
         agent="번호이동 시 필요한 절차를 안내해드릴까요?"),
]


def _l1_of(key: str) -> str:
    return key[0]


def _l2_of(key: str) -> str:
    return key[:2]


def build_intents() -> dict:
    intents = []
    for t in TAX:
        key = t["key"]
        l1_id, l1_name = L1[_l1_of(key)]
        l2_id, l2_name = L2[_l2_of(key)]
        intents.append({
            "id":             f"INT-B{key}0",
            "name":           t["name"],
            "L1_id":          l1_id,
            "L1_name":        l1_name,
            "L2_id":          l2_id,
            "L2_name":        l2_name,
            "inference_type": t["type"],
            "features":       t["features"],
        })
    return {
        "scenario_id": SCENARIO_ID,
        "version":     "0.1.0",
        "description": "결합 상품 활성화 시나리오 Intent Taxonomy (PDF [2] 기반, 5 L1 · {} L3)".format(len(intents)),
        "intents":     intents,
    }


CHANNELS = [
    {"id": "push", "name": "앱 Push", "icon": "📱",
     "characteristic": "고객에게 직접 노출되는 알림 메시지 — 행동 유도·혜택 안내"},
    {"id": "call_center", "name": "고객센터 상담사 컨텍스트", "icon": "📞",
     "characteristic": "콜·채팅 인입 시 상담사 화면 컨텍스트 — 상황 + 안내 가이드(고객 대상 문장 아님)"},
    {"id": "agent", "name": "AI Agent", "icon": "🤖",
     "characteristic": "AI Agent가 고객에게 던지는 개인화 제안·비교·분석 발화"},
]


def build_actions() -> dict:
    actions = {}
    for t in TAX:
        iid = f"INT-B{t['key']}0"
        situation, guidance = t["cc"]
        actions[iid] = {
            "push": t["push"],
            "call_center": {"situation": situation, "guidance": guidance},
            "agent": t["agent"],
        }
    return {
        "scenario_id": SCENARIO_ID,
        "version":     "0.1.0",
        "description": "결합 시나리오 Intent별 3채널 활용 예시 (PDF [2] 4.2 기반)",
        "channels":    CHANNELS,
        "actions":     actions,
    }


# Step1(목적형) behavior entity → 대표 L3 Intent 그룹.
# Step1 클릭도 의도를 끌어올리도록(behaviors.json step1 entity 커버).
STEP1_ENTITY_INTENTS = {
    "benefit_check":         ["INT-B2110", "INT-B2210", "INT-B2340"],
    "bundle_discount_check": ["INT-B1110", "INT-B1210", "INT-B3110"],
    "home_service_explore":  ["INT-B1120", "INT-B3120", "INT-B3130", "INT-B3140"],
    "contract_benefit_check": ["INT-B4110", "INT-B4120", "INT-B4210"],
    "competitor_explore":    ["INT-B5110", "INT-B5410", "INT-B5420"],
}


def build_behavior_intents() -> dict:
    entity_intents: dict[str, list[str]] = {}
    for t in TAX:
        iid = f"INT-B{t['key']}0"
        for ent in t["entities"]:
            entity_intents.setdefault(ent, []).append(iid)
    # Step1 목적형 entity 매핑 병합
    for ent, iids in STEP1_ENTITY_INTENTS.items():
        entity_intents.setdefault(ent, [])
        for iid in iids:
            if iid not in entity_intents[ent]:
                entity_intents[ent].append(iid)
    # behaviors.json 공통(BACK/EXIT) entity는 무효과
    entity_intents.setdefault("back_to_step1", [])
    entity_intents.setdefault("session_end", [])
    return {
        "scenario_id": SCENARIO_ID,
        "version":     "0.1.0",
        "description": "결합 behaviors.json entity → 직접 신호 Intent 매핑",
        "entity_intents": entity_intents,
    }


def _load(path):
    return json.load(open(path, encoding="utf-8")) if path.exists() else {}


def _dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Wrote {path}")


def main() -> None:
    eng = OUT_DIR / "engine"
    # L0: Intent Taxonomy (전체)
    _dump(eng / "L0_taxonomy.json", build_intents())
    # L3: context_library 키만 교체 (context_manager 등 형제 섹션 보존)
    l3 = _load(eng / "L3_serving.json")
    l3["context_library"] = build_actions()
    _dump(eng / "L3_serving.json", l3)
    # L2: ranker.behavior_signals만 교체 (action_signal/model/calibrator 보존)
    l2 = _load(eng / "L2_inference.json")
    l2.setdefault("ranker", {})["behavior_signals"] = build_behavior_intents()["entity_intents"]
    _dump(eng / "L2_inference.json", l2)

    # 요약
    intents = build_intents()["intents"]
    from collections import Counter
    print("\n── L1 분포 ──")
    for (lid, lname), c in sorted(Counter((i["L1_id"], i["L1_name"]) for i in intents).items()):
        print(f"  {lid} {lname}: {c}")
    print("── inference_type ──")
    print(" ", Counter(i["inference_type"] for i in intents))
    bi = build_behavior_intents()["entity_intents"]
    print(f"── behavior entities mapped: {len([k for k,v in bi.items() if v])} ──")


if __name__ == "__main__":
    main()
