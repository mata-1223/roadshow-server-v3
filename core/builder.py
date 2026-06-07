from __future__ import annotations
"""
Batch Context Feature Builder ([1a] reference 모듈)

설문 14문항 답변 → Base Feature 시뮬레이션 → Delta/Ratio/Index/Score 파생.

Base Feature (16개): 설문에서 직접 매핑
  나이, 가입 개월 수, 요금제 유형, 요금제 월정액, 결합 여부, 결합 형태,
  가족 회선 수, 사용 패턴, 데이터 사용률, 잔여 데이터 비율,
  비용 부담도, 품질 만족도, 멤버십 활용도, 푸시 오픈율,
  30일 상담 횟수, 단말 사용 기간, 로밍 이력, 해외 출국 빈도

파생 (Builder):
  Delta (2)  — 청구/데이터 증감률 시뮬
  Ratio (2)  — 약정 진행률, 가족 결합 비중
  Index (4)  — 요금 민감도, 고객 가치, 사용 강도, 탐색 성향
  Score (7)  — 이탈 위험, 추천 적합도, 품질 불만, 결합 확장,
               업셀 적합도(신설), 단말 교체 의향(신설), 로밍 의향(신설)
"""
import json
from pathlib import Path
from typing import Any

from config import settings

_SCENARIO_DIR = Path(__file__).parent.parent / "scenarios" / settings.SCENARIO_ID


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
    with open(_SCENARIO_DIR / "survey.json", encoding="utf-8") as f:
        return json.load(f)


def _extract_base(answers: dict[str, str]) -> dict[str, Any]:
    """
    설문 답변 → Base Feature 매핑.

    Q8/Q9/Q10/Q12 변경에 따라 직접 매핑되지 않는 다음 3개 값은
    행동 지표에서 추정 (KFM Proxy 정합성 + 기존 Rule/Model 입력 호환).
      - 비용 부담도     ← 청구 급증 경험 6m
      - 품질 만족도     ← 품질 CS 문의 3m (역수)
      - 멤버십 활용도   ← 멤버십 주간 사용 횟수
    30일 상담 횟수    ← 품질 CS 문의 3m + 푸시 동의 (전체 CS 접점 합산 추정)
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

    # ── 행동 지표 → 기존 호환 Feature 추정 ──────────────────
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

    # 30일 상담 횟수 추정: 품질 CS 3m → 30일로 환산 + 푸시 비동의 가산
    base["30일 상담 횟수"] = round(quality_cs / 3.0, 1)
    if not bool(base.get("푸시 동의", True)):
        base["30일 상담 횟수"] = base["30일 상담 횟수"] + 0.5

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

    push = float(base.get("푸시 오픈율", 0.45))
    member = float(base.get("멤버십 활용도", 0.45))
    explore = (push * 0.6 + member * 0.4) * 100

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
    push = float(base.get("푸시 오픈율", 0.45))
    member = float(base.get("멤버십 활용도", 0.45))
    age = float(base.get("나이", 35))
    pattern = str(base.get("사용 패턴", "데이터 헤비"))
    device_months = float(base.get("단말 사용 기간", 18))
    contract_pct = min(float(base.get("가입 개월 수", 24)) / 24.0, 1.0)
    roaming_history = float(base.get("로밍 이력", 0))
    overseas_freq = float(base.get("해외 출국 빈도", 0))
    # 새 행동 지표
    bill_shock = float(base.get("청구 급증 경험 6m", 0))
    quality_cs = float(base.get("품질 CS 문의 3m", 0))
    push_optin = 1.0 if bool(base.get("푸시 동의", True)) else 0.0

    # 1. 이탈 위험 — 행동 지표 직접 반영 (청구 급증·품질 CS·푸시 비동의)
    churn = (
        min(quality_cs / 3.0, 1.0) * 0.25
        + min(bill_shock / 3.0, 1.0) * 0.25
        + burden * 0.20
        + (1 - tenure_pct) * 0.15
        + (1 - push_optin) * 0.15
    )

    # 2. 추천 적합도 — 푸시 동의 추가
    rec_fit = (
        index["고객 가치 Index"] / 100 * 0.35
        + push * 0.25
        + index["사용 강도 Index"] / 100 * 0.25
        + push_optin * 0.15
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

    # 5. 업셀 적합도 (신설) — 청구 급증 적음 (안정적) + 푸시 동의 추가
    upsell_fit = (
        data_rate * 0.25
        + (1 - remaining) * 0.20
        + bundle_w * 0.15
        + tenure_pct * 0.10
        + max(0, 1 - bill_shock / 3.0) * 0.15  # 청구 안정적
        + push_optin * 0.15  # 푸시 수용
    )

    # 6. 단말 교체 의향 (신설)
    # 단말 오래 사용 + 약정 진행률 높음 + 탐색 성향 + 데이터 헤비
    device_score = min(device_months / 36.0, 1.0)
    pattern_for_device = 1.0 if pattern in ("데이터 헤비", "콘텐츠 헤비") else 0.5
    device_change_intent = (
        device_score * 0.40
        + contract_pct * 0.25
        + push * 0.15
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
