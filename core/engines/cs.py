from __future__ import annotations
"""
CS(cs-myk-v3) Scenario Engine — self-contained.
builder / pattern / event / rules 를 모두 inline (bundle/worker와 동형).
공통은 common(오케스트레이션)·sklearn_model(raw)·core.extractor(공유 저장소)에 위임.
"""
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from core.engines import config, common
from core.extractor import get_extractor
from core.engines.base import ScenarioEngine
from models import sklearn_model

_DATASET_PATH = Path(__file__).parent.parent.parent / "scenarios" / "cs-myk-v3" / "seed_dataset.json"
_MODEL_PREFIX = "cs-myk-v3__"


# ═════════════════ [1a] Batch Context Feature Builder ═════════════════
# ── 시뮬레이션 보조값 ────────────────────────────────────────
_DEFAULT_FEATURES = {
    "미납 금액":         0,
    "납부 지연 횟수":   0,
    "자동납부 등록 여부": True,
    "부가서비스 수":     1,
    "미사용 쿠폰 수":   3,
}


# ── 사용 패턴별 데이터 사용 가중치 ──────────────────────────
_PATTERN_WEIGHT = {
    "데이터 헤비":   0.90,
    "음성 헤비":     0.20,
    "콘텐츠 헤비":   0.60,
    "업무 헤비":     0.50,
}

# ── 결합 형태별 가중치 (0~1) ───────────────────────────────
_BUNDLE_WEIGHT = {
    "none":         0.0,
    "mobile_only":  0.4,
    "home":         0.7,
    "full":         1.0,
}

_GRADE_BY_TENURE = {6: "Bronze", 24: "Silver", 48: "Gold", 84: "Gold"}


def _load_survey() -> dict:
    return config.get_survey("cs-myk-v3")


def _extract_base(answers: dict[str, str]) -> dict[str, Any]:
    """
    설문 답변 → Base Feature 매핑.

    Q8/Q9/Q10에서 직접 측정되지 않는 Proxy 추정 지표:
      - 비용 부담도     ← 청구 급증 경험 6m + 요금제 월정액
      - 품질 만족도     ← 품질 CS 문의 3m (역수)
      - 멤버십 활용도   ← 멤버십 주간 사용 횟수
      - 30일 상담 횟수  ← 품질 CS 문의 3m / 3 환산
    """
    survey = _load_survey()
    base: dict[str, Any] = dict(_DEFAULT_FEATURES)

    for q in survey["questions"]:
        qid = q["id"]
        answer_code = answers.get(qid)
        if answer_code is None:
            continue
        option = next((o for o in q["options"] if o["code"] == answer_code), None)
        if option is None:
            continue
        base.update(option.get("features", {}))

    # ── 추정 지표 산출 ────────────────────────────────
    # 청구 급증 경험 → 비용 부담도 (요금제 월정액 가산)
    bill_shock = float(base.get("청구 급증 경험 6m", 0))
    fee_norm = float(base.get("요금제 월정액", 55000)) / 100000.0
    if bill_shock >= 3:
        base["비용 부담도"] = min(0.6 + fee_norm * 0.3, 1.0)
    elif bill_shock >= 1:
        base["비용 부담도"] = min(0.4 + fee_norm * 0.2, 0.8)
    else:
        base["비용 부담도"] = max(0.15 + fee_norm * 0.15, 0.15)

    # 품질 CS 문의 → 품질 만족도 (역수)
    quality_cs = float(base.get("품질 CS 문의 3m", 0))
    if quality_cs >= 3:
        base["품질 만족도"] = 0.25
    elif quality_cs >= 1:
        base["품질 만족도"] = 0.55
    else:
        base["품질 만족도"] = 0.85

    # 멤버십 주간 사용 횟수 → 멤버십 활용도 (0~1 정규화)
    member_weekly = float(base.get("멤버십 주간 사용 횟수", 0))
    if member_weekly >= 3:
        base["멤버십 활용도"] = 0.80
    elif member_weekly >= 1:
        base["멤버십 활용도"] = 0.45
    else:
        base["멤버십 활용도"] = 0.10

    # 30일 상담 횟수 추정: 품질 CS 3m → 30일 단위 환산
    base["30일 상담 횟수"] = round(quality_cs / 3.0, 1)

    # 시니어 + 결합 없음 = 자동납부 미등록 + 가끔 지연 시뮬
    if base.get("나이", 35) >= 50 and not base.get("결합 여부", False):
        base["자동납부 등록 여부"] = False
        base["납부 지연 횟수"] = 1

    # 고객 등급 추정 (가입 개월 + 결합 형태)
    tenure = base.get("가입 개월 수", 24)
    base["고객 등급"] = _GRADE_BY_TENURE.get(tenure, "Silver")
    bundle = base.get("결합 형태", "none")
    if base["고객 등급"] == "Gold" and bundle in ("none", "mobile_only"):
        base["고객 등급"] = "Silver"

    return base


def _build_delta(base: dict[str, Any]) -> dict[str, float]:
    """이전 시점 대비 변화량 (시연용 시뮬값)"""
    data_rate = float(base.get("데이터 사용률", 0.4))
    if data_rate >= 0.8:
        data_delta = 0.18
    elif data_rate >= 0.6:
        data_delta = 0.08
    else:
        data_delta = 0.02

    bill = float(base.get("요금제 월정액", 55000))
    avg_bill = bill * 0.92
    bill_delta = (bill - avg_bill) / avg_bill

    return {
        "데이터 사용 증감률": round(data_delta, 4),
        "청구 증감률":        round(bill_delta, 4),
    }


def _build_ratio(base: dict[str, Any]) -> dict[str, float]:
    """구성비"""
    tenure = float(base.get("가입 개월 수", 24))
    contract_total = 24.0
    progress = min(tenure / contract_total, 1.0) if tenure <= contract_total else 1.0

    family = float(base.get("가족 회선 수", 1))
    bundle_score = _BUNDLE_WEIGHT.get(str(base.get("결합 형태", "none")), 0.0)
    extra_lines = bundle_score * 3.0  # 홈상품 결합 시 가상 회선 수
    total_lines = family + extra_lines
    family_ratio = family / total_lines if total_lines > 0 else 1.0

    return {
        "약정 진행률":     round(progress, 4),
        "가족 결합 비중":   round(family_ratio, 4),
    }


def _build_index(base: dict[str, Any], delta: dict[str, float], ratio: dict[str, float]) -> dict[str, float]:
    """정규화 지표 0~100"""
    burden = float(base.get("비용 부담도", 0.5))
    fee = float(base.get("요금제 월정액", 55000)) / 100000.0
    billing_sens = (burden * 0.6 + fee * 0.4) * 100

    tenure = float(base.get("가입 개월 수", 24)) / 84.0
    bundle = _BUNDLE_WEIGHT.get(str(base.get("결합 형태", "none")), 0.0)
    family = float(base.get("가족 회선 수", 1)) / 5.0
    cust_value = (tenure * 0.4 + bundle * 0.3 + min(family, 1.0) * 0.3) * 100

    data_rate = float(base.get("데이터 사용률", 0.4))
    pattern_w = _PATTERN_WEIGHT.get(str(base.get("사용 패턴", "데이터 헤비")), 0.50)
    usage_intensity = (data_rate * 0.5 + pattern_w * 0.5) * 100

    ott = float(base.get("OTT 사용 빈도", 0.50))
    member = float(base.get("멤버십 활용도", 0.45))
    explore = (ott * 0.6 + member * 0.4) * 100

    return {
        "요금 민감도 Index":     round(billing_sens, 2),
        "고객 가치 Index":        round(cust_value, 2),
        "사용 강도 Index":        round(usage_intensity, 2),
        "탐색 성향 Index":        round(explore, 2),
    }


def _build_score(base: dict[str, Any], index: dict[str, float]) -> dict[str, float]:
    """
    ML 예측 점수 (0~1).

    7개 Score:
      1. 이탈 위험 Score      (기존)
      2. 추천 적합도 Score    (기존)
      3. 품질 불만 Score      (기존)
      4. 결합 확장 Score      (기존)
      5. 업셀 적합도 Score    (신설)
      6. 단말 교체 의향 Score (신설)
      7. 로밍 의향 Score      (신설)
    """
    satisfaction = float(base.get("품질 만족도", 0.55))
    burden = float(base.get("비용 부담도", 0.5))
    tenure_pct = min(float(base.get("가입 개월 수", 24)) / 84.0, 1.0)
    cs_count = float(base.get("30일 상담 횟수", 0)) / 5.0
    data_rate = float(base.get("데이터 사용률", 0.4))
    remaining = float(base.get("잔여 데이터 비율", 0.6))
    bundle_w = _BUNDLE_WEIGHT.get(str(base.get("결합 형태", "none")), 0.0)
    ott = float(base.get("OTT 사용 빈도", 0.50))
    member = float(base.get("멤버십 활용도", 0.45))
    age = float(base.get("나이", 35))
    pattern = str(base.get("사용 패턴", "데이터 헤비"))
    device_months = float(base.get("단말 사용 기간", 18))
    contract_pct = min(float(base.get("가입 개월 수", 24)) / 24.0, 1.0)
    roaming_history = float(base.get("로밍 이력", 0))
    overseas_freq = float(base.get("해외 출국 빈도", 0))
    bill_shock = float(base.get("청구 급증 경험 6m", 0))
    quality_cs = float(base.get("품질 CS 문의 3m", 0))

    # 1. 이탈 위험 — 행동 지표 직접 반영 (청구 급증·품질 CS·비용 부담·신규 고객)
    churn = (
        min(quality_cs / 3.0, 1.0) * 0.30
        + min(bill_shock / 3.0, 1.0) * 0.30
        + burden * 0.25
        + (1 - tenure_pct) * 0.15
    )

    # 2. 추천 적합도 — OTT 사용 빈도가 콘텐츠 수용도를 대변
    rec_fit = (
        index["고객 가치 Index"] / 100 * 0.40
        + ott * 0.30
        + index["사용 강도 Index"] / 100 * 0.30
    )

    # 3. 품질 불만 — 품질 CS 문의 직접 활용
    quality_complaint = (
        min(quality_cs / 3.0, 1.0) * 0.7
        + (1 - satisfaction) * 0.3
    )

    # 4. 결합 확장
    bundle_expand = (
        bundle_w * 0.4
        + min(float(base.get("가족 회선 수", 1)) / 5.0, 1.0) * 0.3
        + index["고객 가치 Index"] / 100 * 0.3
    )

    # 5. 업셀 적합도 — 사용량·결합·청구 안정성
    upsell_fit = (
        data_rate * 0.30
        + (1 - remaining) * 0.25
        + bundle_w * 0.20
        + tenure_pct * 0.10
        + max(0, 1 - bill_shock / 3.0) * 0.15
    )

    # 6. 단말 교체 의향
    # 단말 오래 사용 + 약정 진행률 + OTT 시청(콘텐츠 헤비) + 데이터 패턴
    device_score = min(device_months / 36.0, 1.0)
    pattern_for_device = 1.0 if pattern in ("데이터 헤비", "콘텐츠 헤비") else 0.5
    device_change_intent = (
        device_score * 0.40
        + contract_pct * 0.25
        + ott * 0.15
        + pattern_for_device * 0.20
    )

    # 7. 로밍 의향 (신설)
    # 로밍 이력 + 출국 빈도 + 사용 패턴 + 비용 부담 반대
    roaming_intent = (
        min(roaming_history / 3.0, 1.0) * 0.45
        + min(overseas_freq / 3.0, 1.0) * 0.35
        + (1 - burden) * 0.10
        + (0.5 if pattern == "업무 헤비" else 0.2) * 0.10
    )

    return {
        "이탈 위험 Score":         round(churn, 4),
        "추천 적합도 Score":       round(rec_fit, 4),
        "품질 불만 Score":         round(quality_complaint, 4),
        "결합 확장 Score":         round(bundle_expand, 4),
        "업셀 적합도 Score":       round(upsell_fit, 4),
        "단말 교체 의향 Score":    round(device_change_intent, 4),
        "로밍 의향 Score":         round(roaming_intent, 4),
    }


# ── Public API ────────────────────────────────────────────────

def build_batch_features(survey_answers: dict[str, str]) -> dict[str, Any]:
    """
    설문 답변(dict) → Batch Feature(dict)

    Parameters
    ----------
    survey_answers : {"Q1": "A", ..., "Q14": "B"}

    Returns
    -------
    dict : Base(~18) + Delta(2) + Ratio(2) + Index(4) + Score(7)
    """
    base = _extract_base(survey_answers)
    delta = _build_delta(base)
    ratio = _build_ratio(base)
    index = _build_index(base, delta, ratio)
    score = _build_score(base, index)

    return {**base, **delta, **ratio, **index, **score}


# ═════════════════ [1c] Behavioral Pattern Extractor ═════════════════
# ── Entity → 카운트 그룹 매핑 ─────────────────────────────────
_ENTITY_GROUP = {
    "data_usage":          ["data_view"],
    "billing":             ["billing_view"],
    "subscription_info":   ["subscription_view"],
    "benefit_membership":  ["benefit_view"],
    "product_explore":     ["product_view"],
    "customer_support":    ["support_view"],
    "data_topup_button":   ["data_topup"],
    "plan_change_button":  ["plan_change"],
    "quality_diagnosis":   ["quality_action", "wifi_diag", "speed_test"],
    "family_bundle":       ["family_bundle"],
    "penalty_calc":        ["churn_view", "penalty_view"],
    "confirm_button":      ["confirm"],
    "coupon_use":          ["coupon_use"],
    "chatbot":             ["support_entry"],
    "call_support":        ["support_entry"],
    "cancel_page":         ["churn_view", "cancel_view"],
}


def empty_pattern_features() -> dict[str, Any]:
    return {
        "repeated_entity_count_5m": 0,
        "support_entry_count_5m":   0,
        "billing_page_view_count":  0,
        "product_explore_count":    0,
        "benefit_explore_count":    0,
        "churn_page_view_count":    0,
        "quality_action_count":     0,
        "last_3_events":            "",
        "WiFi 진단 실행":           0,
        "속도 측정 실행":           0,
        "장애 페이지 체류":         0,
        "가족 결합 관련 행동":      0,
        "위약금 조회 행동":         0,
        "해지 페이지 진입":         0,
        "mnp_benefit_check":        0,
        "할인 페이지 체류":         0,
    }


def pattern_features(session_id: str) -> dict[str, Any]:
    events = get_extractor().events_within(session_id, window_seconds=300)

    group_counts: dict[str, int] = {}
    for ev in events:
        for group in _ENTITY_GROUP.get(ev["entity"], []):
            group_counts[group] = group_counts.get(group, 0) + 1

    entity_counts: dict[str, int] = {}
    for ev in events:
        entity_counts[ev["entity"]] = entity_counts.get(ev["entity"], 0) + 1
    repeated_max = max(entity_counts.values()) if entity_counts else 0

    recent_3 = events[-3:] if events else []
    last_3_events = "→".join(e["event_type"] for e in recent_3)

    return {
        "repeated_entity_count_5m": repeated_max,
        "support_entry_count_5m":   group_counts.get("support_entry", 0),
        "billing_page_view_count":  group_counts.get("billing_view", 0),
        "product_explore_count":    group_counts.get("product_view", 0),
        "benefit_explore_count":    group_counts.get("benefit_view", 0),
        "churn_page_view_count":    group_counts.get("churn_view", 0),
        "quality_action_count":     group_counts.get("quality_action", 0),
        "last_3_events":            last_3_events,
        "WiFi 진단 실행":           group_counts.get("wifi_diag", 0),
        "속도 측정 실행":           group_counts.get("speed_test", 0),
        "장애 페이지 체류":         group_counts.get("support_view", 0) * 60,
        "가족 결합 관련 행동":      1 if group_counts.get("family_bundle", 0) > 0 else 0,
        "위약금 조회 행동":         1 if group_counts.get("penalty_view", 0) > 0 else 0,
        "해지 페이지 진입":         1 if group_counts.get("cancel_view", 0) > 0 else 0,
        "mnp_benefit_check":        0,
        "할인 페이지 체류":         group_counts.get("benefit_view", 0) * 30,
    }


# ═════════════════ [1b] Event Feature Extractor ═════════════════
# Entity 마지막 진입 → 현재 화면 카테고리
_ENTITY_TO_PAGE = {
    "data_usage":         "data",
    "billing":            "billing",
    "subscription_info":  "subscription",
    "benefit_membership": "benefit",
    "product_explore":    "product",
    "customer_support":   "support",
    "data_topup_button":  "data",
    "plan_change_button": "product",
    "quality_diagnosis":  "support",
    "family_bundle":      "subscription",
    "penalty_calc":       "churn",
    "confirm_button":     "confirm",
    "coupon_use":         "benefit",
    "chatbot":            "support",
    "call_support":       "support",
    "cancel_page":        "churn",
}


def _extract_event(event_type: str, entity: str, occurred_at: datetime | None = None) -> dict[str, Any]:
    """단일 이벤트 → Event Feature dict."""
    ts = occurred_at or datetime.now()
    return {
        "last_event_type":  event_type,
        "last_entity":      entity,
        "current_page":     _ENTITY_TO_PAGE.get(entity, "unknown"),
        "is_click":         1 if event_type == "click" else 0,
        "is_page_view":     1 if event_type == "page_view" else 0,
        "is_support_entry": 1 if event_type == "support_entry" else 0,
        "is_churn_signal":  1 if entity in ("penalty_calc", "cancel_page") else 0,
        "is_confirm":       1 if entity == "confirm_button" else 0,
        "last_event_at":    ts.isoformat(),
    }


def empty_event_features() -> dict[str, Any]:
    return {
        "last_event_type":  "",
        "last_entity":      "",
        "current_page":     "",
        "is_click":         0,
        "is_page_view":     0,
        "is_support_entry": 0,
        "is_churn_signal":  0,
        "is_confirm":       0,
        "last_event_at":    "",
    }


def event_features(session_id: str) -> dict[str, Any]:
    events = get_extractor()._events_by_session.get(session_id, [])
    if not events:
        return empty_event_features()
    last = events[-1]
    return _extract_event(last["event_type"], last["entity"], last.get("occurred_at"))


# ═════════════════ [2a] Rule-Based Intent Trigger ═════════════════
PATTERN_BOOST_MULTIPLIER = 1.5  # 시연 임팩트 강화. 1.0=기본, 2.0=두 배 sharp


def _pattern_boost(f: dict, key: str, scale: float = 0.1, cap: float = 0.3) -> float:
    """Pattern Feature count → 0~cap 추가 점수 (PATTERN_BOOST_MULTIPLIER 적용)."""
    try:
        v = float(f.get(key, 0))
    except (TypeError, ValueError):
        v = 0.0
    return min(v * scale * PATTERN_BOOST_MULTIPLIER, cap * PATTERN_BOOST_MULTIPLIER)


# ─────────────────────────────────────────────────────────────
# 시연 활성 핵심 Intent의 명시적 Rule
# (features dict 입력 → 0~1 Score 반환)
# ─────────────────────────────────────────────────────────────
RULES: dict[str, Callable[[dict[str, Any]], float]] = {}


def _register(intent_id: str):
    def decorator(fn):
        RULES[intent_id] = fn
        return fn
    return decorator


# ── INT-1000. My 정보 조회 ────────────────────────────────────

@_register("INT-1110")
def _rule_1110(f):  # 데이터 사용량 조회
    rate = float(f.get("데이터 사용률", 0))
    if rate >= 0.85: return 0.65
    if rate >= 0.65: return 0.45
    if rate >= 0.40: return 0.25
    return 0.10

@_register("INT-1120")
def _rule_1120(f):  # 음성 사용량 조회
    return 0.45 if f.get("사용 패턴") == "음성 헤비" else 0.10

@_register("INT-1140")
def _rule_1140(f):  # 로밍 사용량 조회
    roaming = float(f.get("로밍 이력", 0))
    overseas = float(f.get("해외 출국 빈도", 0))
    if roaming >= 3 or overseas >= 3: return 0.70
    if roaming >= 1 or overseas >= 1: return 0.50
    return 0.05

@_register("INT-1150")
def _rule_1150(f):  # 실시간 사용 패턴 조회
    return 0.40 if float(f.get("데이터 사용 증감률", 0)) >= 0.1 else 0.15

@_register("INT-1210")
def _rule_1210(f):  # 월 요금 조회
    burden = float(f.get("비용 부담도", 0))
    base = 0.50 + burden * 0.2
    return min(base + _pattern_boost(f, "billing_page_view_count", 0.08, 0.20), 0.95)

@_register("INT-1220")
def _rule_1220(f):  # 청구 상세 조회
    sens = float(f.get("요금 민감도 Index", 0)) / 100
    base = min(0.30 + sens * 0.5, 0.80)
    return min(base + _pattern_boost(f, "billing_page_view_count", 0.06, 0.18), 0.95)

@_register("INT-1240")
def _rule_1240(f):  # 미납 요금 조회
    return 0.80 if float(f.get("미납 금액", 0)) > 0 else 0.05

@_register("INT-1250")
def _rule_1250(f):  # 납부 내역 조회
    return 0.35 if not f.get("자동납부 등록 여부", True) else 0.15

@_register("INT-1310")
def _rule_1310(f):  # 가입 요금제 조회
    return 0.40

@_register("INT-1320")
def _rule_1320(f):  # 부가서비스 조회
    return min(0.25 + int(f.get("부가서비스 수", 1)) * 0.05, 0.55)

@_register("INT-1330")
def _rule_1330(f):  # 약정 조회
    prog = float(f.get("약정 진행률", 0))
    if prog >= 0.9:  return 0.60
    if prog >= 0.7:  return 0.40
    return 0.20

@_register("INT-1340")
def _rule_1340(f):  # 결합상품 조회
    return 0.55 if f.get("결합 여부", False) and int(f.get("가족 회선 수", 1)) >= 2 else 0.20

@_register("INT-1410")
def _rule_1410(f):  # 멤버십 조회
    base = 0.30 + float(f.get("멤버십 활용도", 0)) * 0.4
    return min(base + _pattern_boost(f, "benefit_explore_count", 0.08, 0.20), 0.95)

@_register("INT-1430")
def _rule_1430(f):  # 쿠폰 조회
    base = 0.25 + min(int(f.get("미사용 쿠폰 수", 0)) * 0.1, 0.4)
    return min(base + _pattern_boost(f, "benefit_explore_count", 0.08, 0.20), 0.95)

@_register("INT-1440")
def _rule_1440(f):  # VIP 혜택 조회
    return 0.50 if str(f.get("고객 등급", "")) == "Gold" else 0.10

# ── INT-2000. 상품 탐색/가입 ──────────────────────────────────

@_register("INT-2110")
def _rule_2110(f):  # 요금제 탐색
    sens = float(f.get("요금 민감도 Index", 0)) / 100
    prog = float(f.get("약정 진행률", 0))
    base = min(sens * 0.5 + prog * 0.3, 0.7)
    return min(base + _pattern_boost(f, "product_explore_count", 0.10, 0.25), 0.95)

@_register("INT-2120")
def _rule_2120(f):  # 5G 상품 탐색
    upsell = float(f.get("업셀 적합도 Score", 0))
    fee = float(f.get("요금제 월정액", 0))
    tier = str(f.get("요금제 구간", ""))
    # 5G 추정: premium/mid 구간 또는 월정액 5.5만+
    is_5g_like = tier in ("premium", "mid") or fee >= 55000
    if is_5g_like:
        return min(0.20 + _pattern_boost(f, "product_explore_count", 0.04, 0.10), 0.40)
    base = min(upsell * 0.7 + 0.15, 0.70)
    return min(base + _pattern_boost(f, "product_explore_count", 0.08, 0.20), 0.95)

@_register("INT-2140")
def _rule_2140(f):  # 로밍 상품 탐색
    roaming_intent = float(f.get("로밍 의향 Score", 0))
    if roaming_intent >= 0.6: return 0.65
    if roaming_intent >= 0.3: return 0.40
    return 0.05

@_register("INT-2150")
def _rule_2150(f):  # 실속형 상품 탐색
    sens = float(f.get("요금 민감도 Index", 0)) / 100
    burden = float(f.get("비용 부담도", 0))
    return min(sens * 0.5 + burden * 0.4, 0.75)

@_register("INT-2240")
def _rule_2240(f):  # 결합상품 탐색
    if f.get("결합 여부"):
        return 0.20
    return 0.45 if int(f.get("가족 회선 수", 1)) >= 2 else 0.20

@_register("INT-2310")
def _rule_2310(f):  # OTT 탐색
    return 0.45 if f.get("사용 패턴") in ["데이터 헤비", "콘텐츠 헤비"] else 0.15

@_register("INT-2320")
def _rule_2320(f):  # 데이터 부가서비스 탐색
    rate = float(f.get("데이터 사용률", 0))
    rem = float(f.get("잔여 데이터 비율", 1))
    return min(rate * 0.5 + (1 - rem) * 0.3, 0.75)

@_register("INT-2330")
def _rule_2330(f):  # 보안/안심 서비스 탐색
    age = int(f.get("나이", 35))
    return 0.40 if age >= 50 else 0.15

@_register("INT-2410")
def _rule_2410(f):  # 스마트폰 탐색
    device_intent = float(f.get("단말 교체 의향 Score", 0))
    if device_intent >= 0.7: return 0.70
    if device_intent >= 0.5: return 0.50
    if device_intent >= 0.3: return 0.30
    return 0.10

@_register("INT-2420")
def _rule_2420(f):  # 실속폰 탐색
    sens = float(f.get("요금 민감도 Index", 0)) / 100
    age = int(f.get("나이", 35))
    device_intent = float(f.get("단말 교체 의향 Score", 0))
    return min(sens * 0.35 + (0.25 if age >= 55 else 0.0) + device_intent * 0.25, 0.60)

@_register("INT-2440")
def _rule_2440(f):  # 중고폰 보상 탐색
    device_intent = float(f.get("단말 교체 의향 Score", 0))
    sens = float(f.get("요금 민감도 Index", 0)) / 100
    return min(device_intent * 0.5 + sens * 0.2, 0.65)

@_register("INT-2530")
def _rule_2530(f):  # 단말 구매
    device_intent = float(f.get("단말 교체 의향 Score", 0))
    return min(device_intent * 0.6, 0.65)

@_register("INT-2540")
def _rule_2540(f):  # 로밍 가입
    roaming_intent = float(f.get("로밍 의향 Score", 0))
    if roaming_intent >= 0.6: return 0.60
    if roaming_intent >= 0.3: return 0.35
    return 0.05

# ── INT-3000. 셀프처리 ────────────────────────────────────────

@_register("INT-3110")
def _rule_3110(f):  # 즉시 납부
    if float(f.get("미납 금액", 0)) > 0 and not f.get("자동납부 등록 여부", True):
        return 0.70
    return 0.0

@_register("INT-3120")
def _rule_3120(f):  # 자동이체 변경
    delays = int(f.get("납부 지연 횟수", 0))
    if delays >= 2: return 0.65
    if delays >= 1: return 0.40
    return 0.10

@_register("INT-3140")
def _rule_3140(f):  # 납부확인서 발급
    return 0.15

@_register("INT-3240")
def _rule_3240(f):  # 일시정지 신청
    return 0.25 if int(f.get("로밍 이력", 0)) > 0 else 0.05

@_register("INT-3410")
def _rule_3410(f):  # 본인 인증
    return 0.20

# ── INT-4000. 혜택/프로모션 ───────────────────────────────────

@_register("INT-4110")
def _rule_4110(f):  # 쿠폰 탐색
    sens = float(f.get("요금 민감도 Index", 0)) / 100
    burden = float(f.get("비용 부담도", 0))
    base = min(sens * 0.4 + burden * 0.3, 0.65)
    return min(base + _pattern_boost(f, "benefit_explore_count", 0.08, 0.20), 0.95)

@_register("INT-4120")
def _rule_4120(f):  # 이벤트 탐색
    return 0.20 + float(f.get("탐색 성향 Index", 0)) / 100 * 0.5

@_register("INT-4130")
def _rule_4130(f):  # 제휴 할인 탐색
    return 0.20 + float(f.get("멤버십 활용도", 0)) * 0.4

@_register("INT-4140")
def _rule_4140(f):  # 시즌 프로모션 탐색
    return 0.15 + float(f.get("탐색 성향 Index", 0)) / 100 * 0.4

@_register("INT-4210")
def _rule_4210(f):  # 영화 혜택 탐색
    member = float(f.get("멤버십 활용도", 0))
    age = int(f.get("나이", 35))
    return min(member * 0.5 + (0.2 if 20 <= age <= 40 else 0.0), 0.55)

@_register("INT-4220")
def _rule_4220(f):  # 외식 혜택 탐색
    return 0.20 + float(f.get("멤버십 활용도", 0)) * 0.35

@_register("INT-4230")
def _rule_4230(f):  # 쇼핑 혜택 탐색
    return 0.20 + float(f.get("멤버십 활용도", 0)) * 0.35

@_register("INT-4240")
def _rule_4240(f):  # VIP 혜택 탐색
    return 0.50 if float(f.get("고객 가치 Index", 0)) >= 70 else 0.10

# ── INT-5000. 문제 해결/상담 ─────────────────────────────────

@_register("INT-5140")
def _rule_5140(f):  # IPTV 장애 해결
    bundle = str(f.get("결합 형태", "none"))
    if bundle in ("home", "full") and float(f.get("품질 만족도", 1)) <= 0.4:
        return min(0.55 + _pattern_boost(f, "quality_action_count", 0.10, 0.25), 0.95)
    return 0.05

@_register("INT-5150")
def _rule_5150(f):  # QoE 문제 해결
    sat = float(f.get("품질 만족도", 1))
    if sat <= 0.3: base = 0.45
    elif sat <= 0.5: base = 0.25
    else: base = 0.05
    return min(base + _pattern_boost(f, "quality_action_count", 0.12, 0.25), 0.95)

@_register("INT-5310")
def _rule_5310(f):  # 챗봇 상담
    cs = int(f.get("30일 상담 횟수", 0))
    if cs >= 2: base = 0.55
    elif cs >= 1: base = 0.35
    else: base = 0.10
    return min(base + _pattern_boost(f, "support_entry_count_5m", 0.15, 0.30), 0.95)

@_register("INT-5320")
def _rule_5320(f):  # 채팅 상담
    cs = int(f.get("30일 상담 횟수", 0))
    base = 0.30 if cs >= 1 else 0.10
    return min(base + _pattern_boost(f, "support_entry_count_5m", 0.10, 0.25), 0.95)

@_register("INT-5330")
def _rule_5330(f):  # 전화 상담
    cs = int(f.get("30일 상담 횟수", 0))
    age = int(f.get("나이", 35))
    base = 0.50 if cs >= 2 else (0.30 if cs >= 1 else 0.05)
    if age >= 55: base += 0.10
    base = min(base, 0.75)
    return min(base + _pattern_boost(f, "support_entry_count_5m", 0.12, 0.25), 0.95)

@_register("INT-5350")
def _rule_5350(f):  # 카카오 상담
    return 0.25 if int(f.get("30일 상담 횟수", 0)) >= 1 else 0.05

@_register("INT-5410")
def _rule_5410(f):  # AS 신청
    quality_complaint = float(f.get("품질 불만 Score", 0))
    base = min(quality_complaint * 0.7, 0.70) if quality_complaint >= 0.5 else 0.10
    return min(base + _pattern_boost(f, "quality_action_count", 0.10, 0.20), 0.95)

@_register("INT-5420")
def _rule_5420(f):  # 장애 신고
    return 0.45 if float(f.get("품질 만족도", 1)) <= 0.3 else 0.05

# ── INT-6000. 관계/공유 ───────────────────────────────────────

@_register("INT-6120")
def _rule_6120(f):  # 자녀 회선 관리
    family = int(f.get("가족 회선 수", 1))
    age = int(f.get("나이", 35))
    return min(family * 0.10 + (0.20 if 35 <= age <= 55 else 0.0), 0.55)

@_register("INT-6130")
def _rule_6130(f):  # 가족 데이터 공유
    family = int(f.get("가족 회선 수", 1))
    rem = float(f.get("잔여 데이터 비율", 1))
    if family >= 2: return 0.30 + (1 - rem) * 0.3
    return 0.05

@_register("INT-6140")
def _rule_6140(f):  # 가족 혜택 관리
    family = int(f.get("가족 회선 수", 1))
    cv = float(f.get("고객 가치 Index", 0)) / 100
    return min(family * 0.10 + cv * 0.3, 0.55)

@_register("INT-6210")
def _rule_6210(f):  # 데이터 선물
    family = int(f.get("가족 회선 수", 1))
    return 0.30 if family >= 2 else 0.05

# ── INT-7000. 이탈/전환 ───────────────────────────────────────

@_register("INT-7110")
def _rule_7110(f):  # 위약금 확인
    base = 0.05
    if int(f.get("is_churn_signal", 0)) == 1:
        base = 0.50
    return min(base + _pattern_boost(f, "churn_page_view_count", 0.12, 0.30), 0.95)

@_register("INT-7120")
def _rule_7120(f):  # 해지 절차 확인
    churn = float(f.get("이탈 위험 Score", 0))
    base = min(churn * 0.7, 0.60)
    if int(f.get("is_churn_signal", 0)) == 1:
        base = max(base, 0.55)
    return min(base + _pattern_boost(f, "churn_page_view_count", 0.15, 0.30), 0.95)

@_register("INT-7130")
def _rule_7130(f):  # 해지 신청
    churn = float(f.get("이탈 위험 Score", 0))
    base = min(churn * 0.5, 0.50)
    if f.get("last_entity") == "cancel_page":
        base = max(base, 0.65)
    return min(base + _pattern_boost(f, "churn_page_view_count", 0.10, 0.25), 0.95)

@_register("INT-7140")
def _rule_7140(f):  # 미사용 서비스 정리
    burden = float(f.get("비용 부담도", 0))
    svc = int(f.get("부가서비스 수", 1))
    base = min(burden * 0.4 + min(svc, 5) * 0.05, 0.55)
    return min(base + _pattern_boost(f, "churn_page_view_count", 0.08, 0.20), 0.95)

@_register("INT-7210")
def _rule_7210(f):  # Model이지만 Rule fallback (Model 학습 전)
    churn = float(f.get("이탈 위험 Score", 0))
    return min(churn * 0.6, 0.55)

@_register("INT-7240")
def _rule_7240(f):  # 이동 조건 검토
    prog = float(f.get("약정 진행률", 0))
    return 0.40 if prog >= 0.85 else 0.10

@_register("INT-7330")
def _rule_7330(f):  # 혜택 최적화 검토
    explore = float(f.get("탐색 성향 Index", 0)) / 100
    burden = float(f.get("비용 부담도", 0))
    return min(explore * 0.4 + burden * 0.3, 0.55)

@_register("INT-7340")
def _rule_7340(f):  # 불필요 서비스 제거
    svc = int(f.get("부가서비스 수", 1))
    burden = float(f.get("비용 부담도", 0))
    return min(min(svc, 5) * 0.05 + burden * 0.3, 0.45)


def rule_predict(intent_id: str, features: dict[str, Any]) -> float:
    return common.rule_predict(RULES, intent_id, features)


# ═════════════════ [2b] Predictive Intent Model ═════════════════
MODEL_TRAINING_DATA: dict[str, dict] = {

    # ── INT-2130. 데이터 상품 탐색 ─────────────────────────────
    "INT-2130": {
        "features": ["데이터 사용률", "데이터 사용 증감률", "잔여 데이터 비율", "사용 강도 Index", "업셀 적합도 Score"],
        "X": [
            # 양성: 데이터 부족 + 증가 추세 + 업셀 적합도 높음
            [0.90, 0.18, 0.10, 88, 0.85], [0.85, 0.20, 0.15, 82, 0.78],
            [0.92, 0.22, 0.08, 90, 0.88], [0.78, 0.15, 0.22, 75, 0.65],
            [0.95, 0.25, 0.05, 92, 0.90],
            # 음성: 데이터 충분 + 업셀 적합도 낮음
            [0.30, 0.02, 0.70, 28, 0.25], [0.40, 0.03, 0.60, 35, 0.30],
            [0.25, 0.01, 0.75, 22, 0.20], [0.20, 0.00, 0.80, 18, 0.15],
            [0.45, 0.05, 0.55, 40, 0.35],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },

    # ── INT-3210. 요금제 변경 ──────────────────────────────────
    "INT-3210": {
        "features": ["요금 민감도 Index", "비용 부담도", "약정 진행률", "이탈 위험 Score"],
        "X": [
            # 양성: 민감도 + 부담 + 약정 진행 + 이탈 위험
            [75, 0.7, 0.85, 0.6], [68, 0.6, 0.90, 0.55], [82, 0.8, 0.80, 0.7],
            [60, 0.5, 0.95, 0.5], [78, 0.75, 0.75, 0.65],
            # 음성: 안정적
            [25, 0.2, 0.30, 0.15], [35, 0.3, 0.40, 0.20], [30, 0.2, 0.20, 0.10],
            [40, 0.3, 0.50, 0.25], [20, 0.1, 0.10, 0.05],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },

    # ── INT-4310. AI 추천 탐색 ─────────────────────────────────
    "INT-4310": {
        "features": ["고객 가치 Index", "비용 부담도", "데이터 사용률", "OTT 사용 빈도"],
        "X": [
            # 양성: 가치 높음 + 활발 사용 + 푸시 자주 봄
            [78, 0.5, 0.75, 0.80], [85, 0.6, 0.85, 0.75], [72, 0.5, 0.70, 0.70],
            [80, 0.4, 0.80, 0.85], [88, 0.5, 0.90, 0.80],
            # 음성: 무관심
            [30, 0.3, 0.30, 0.10], [40, 0.4, 0.40, 0.15], [25, 0.2, 0.25, 0.05],
            [45, 0.3, 0.45, 0.20], [35, 0.5, 0.30, 0.12],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },

    # ── INT-4320. 개인화 혜택 탐색 ─────────────────────────────
    "INT-4320": {
        "features": ["고객 가치 Index", "멤버십 활용도", "탐색 성향 Index"],
        "X": [
            [75, 0.80, 80], [82, 0.75, 75], [70, 0.70, 70], [85, 0.85, 82], [78, 0.65, 68],
            [35, 0.10, 15], [40, 0.20, 25], [25, 0.05, 10], [50, 0.30, 30], [38, 0.15, 20],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },

    # ── INT-4330. 추천 요금제 검토 ─────────────────────────────
    "INT-4330": {
        "features": ["요금 민감도 Index", "데이터 사용률", "가입 개월 수", "약정 진행률"],
        "X": [
            [70, 0.80, 36, 0.90], [65, 0.70, 48, 0.85], [78, 0.85, 24, 0.95],
            [60, 0.75, 60, 0.80], [72, 0.65, 30, 0.92],
            [25, 0.30, 6,  0.15], [30, 0.40, 12, 0.25], [22, 0.25, 3,  0.10],
            [35, 0.35, 18, 0.30], [28, 0.45, 9,  0.20],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },


    # ── INT-5110. 인터넷 장애 해결 ─────────────────────────────
    "INT-5110": {
        "features": ["품질 만족도", "결합 여부", "quality_action_count", "장애 페이지 체류"],
        "X": [
            # 양성: 만족도 낮음 + 결합 (홈) + 진단 행동 + 체류 김
            [0.25, 1, 3, 180], [0.30, 1, 4, 220], [0.20, 1, 2, 150],
            [0.35, 1, 3, 165], [0.25, 1, 5, 250],
            # 음성: 만족 + 진단 행동 없음
            [0.85, 0, 0, 0],  [0.80, 1, 0, 0],   [0.90, 0, 0, 0],
            [0.75, 1, 0, 10], [0.85, 0, 0, 5],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },

    # ── INT-5120. WiFi 문제 해결 ───────────────────────────────
    "INT-5120": {
        "features": ["품질 만족도", "WiFi 진단 실행", "결합 여부"],
        "X": [
            [0.30, 2, 1], [0.25, 3, 1], [0.35, 2, 1], [0.20, 1, 1], [0.30, 4, 1],
            [0.85, 0, 0], [0.80, 0, 1], [0.90, 0, 0], [0.75, 0, 1], [0.85, 0, 0],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },

    # ── INT-5130. 속도 저하 해결 ───────────────────────────────
    "INT-5130": {
        "features": ["품질 만족도", "속도 측정 실행", "데이터 사용률"],
        "X": [
            [0.25, 3, 0.85], [0.30, 2, 0.75], [0.20, 4, 0.90],
            [0.35, 2, 0.70], [0.25, 3, 0.80],
            [0.85, 0, 0.30], [0.80, 0, 0.40], [0.90, 0, 0.25],
            [0.75, 0, 0.45], [0.85, 0, 0.35],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },

    # ── INT-6110. 가족결합 관리 ────────────────────────────────
    "INT-6110": {
        "features": ["결합 여부", "가족 회선 수", "가족 결합 관련 행동"],
        "X": [
            [1, 3, 1], [1, 4, 1], [1, 5, 1], [1, 3, 1], [1, 2, 1],
            [0, 1, 0], [0, 1, 0], [1, 1, 0], [0, 2, 0], [1, 2, 0],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },

    # ── INT-7110. 위약금 조회 ──────────────────────────────────
    "INT-7110": {
        "features": ["약정 진행률", "이탈 위험 Score", "위약금 조회 행동"],
        "X": [
            [0.85, 0.65, 1], [0.90, 0.70, 1], [0.80, 0.60, 1],
            [0.95, 0.75, 1], [0.88, 0.55, 1],
            [0.20, 0.15, 0], [0.30, 0.20, 0], [0.15, 0.10, 0],
            [0.40, 0.25, 0], [0.25, 0.18, 0],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },

    # ── INT-7130. 해지 상담 요청 ───────────────────────────────
    "INT-7130": {
        "features": ["이탈 위험 Score", "30일 상담 횟수", "해지 페이지 진입"],
        "X": [
            [0.70, 3, 1], [0.65, 2, 1], [0.75, 4, 1], [0.60, 2, 1], [0.80, 5, 1],
            [0.15, 0, 0], [0.20, 0, 0], [0.10, 0, 0], [0.25, 1, 0], [0.18, 0, 0],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },

    # ── INT-7210. 번호이동 탐색 — KT 앱 내 번호이동 안내 페이지 진입 행동 활용 ──
    "INT-7210": {
        "features": ["이탈 위험 Score", "비용 부담도", "mnp_benefit_check"],
        "X": [
            [0.65, 0.75, 1], [0.70, 0.80, 1], [0.60, 0.70, 1],
            [0.75, 0.85, 1], [0.55, 0.65, 1],
            [0.15, 0.20, 0], [0.20, 0.25, 0], [0.10, 0.15, 0],
            [0.25, 0.30, 0], [0.18, 0.22, 0],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },

    # ── INT-7310. 저가 요금 탐색 ───────────────────────────────
    "INT-7310": {
        "features": ["요금 민감도 Index", "비용 부담도", "요금제 월정액"],
        "X": [
            [75, 0.7, 75000], [80, 0.8, 90000], [70, 0.65, 65000],
            [85, 0.75, 85000], [78, 0.7, 80000],
            [25, 0.2, 33000], [30, 0.3, 35000], [22, 0.15, 30000],
            [35, 0.3, 40000], [28, 0.25, 38000],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },

    # ── INT-7320. 할인 탐색 ────────────────────────────────────
    "INT-7320": {
        "features": ["요금 민감도 Index", "미사용 쿠폰 수", "할인 페이지 체류"],
        "X": [
            [70, 5, 120], [75, 6, 150], [65, 4, 100], [80, 7, 180], [72, 5, 130],
            [25, 0, 0],   [30, 1, 5],   [22, 0, 0],   [35, 2, 10],  [28, 1, 8],
        ],
        "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    },
}


def model_predict(intent_id: str, features: dict[str, Any]) -> float:
    return sklearn_model.predict(intent_id, features,
                                 training_data=MODEL_TRAINING_DATA,
                                 dataset_path=_DATASET_PATH,
                                 model_prefix=_MODEL_PREFIX)


class CSEngine(ScenarioEngine):

    def build_batch_features(self, answers: dict[str, str]) -> dict[str, Any]:
        return build_batch_features(answers)

    def empty_pattern_features(self) -> dict[str, Any]:
        return empty_pattern_features()

    def empty_event_features(self) -> dict[str, Any]:
        return empty_event_features()

    def pattern_features(self, session_id: str) -> dict[str, Any]:
        return pattern_features(session_id)

    def event_features(self, session_id: str) -> dict[str, Any]:
        return event_features(session_id)

    def rule_predict(self, intent_id: str, features: dict[str, Any]) -> float:
        return rule_predict(intent_id, features)

    def model_predict(self, intent_id: str, features: dict[str, Any]) -> float:
        return model_predict(intent_id, features)
