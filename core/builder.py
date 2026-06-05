from __future__ import annotations
"""
Batch Context Feature Builder ([1a] reference 모듈)

설문 답변 → Base Feature 14개 시뮬레이션 → Delta/Ratio/Index/Score 파생
총 26개 Batch Feature 산출.
"""
import json
from pathlib import Path
from typing import Any

from config import settings

_SCENARIO_DIR = Path(__file__).parent.parent / "scenarios" / settings.SCENARIO_ID


# ── 시연 시뮬레이션 보조값 ────────────────────────────────────
# 설문에 직접 매핑되지 않지만 시연용으로 필요한 보조 Base Feature
_DEFAULT_FEATURES = {
    "미납 금액":         0,
    "납부 지연 횟수":   0,
    "자동납부 등록 여부": True,
    "로밍 이력":         0,
    "부가서비스 수":     1,
    "미사용 쿠폰 수":   3,
}


# ── 사용 패턴별 데이터 사용 가중치 ────────────────────────────
_PATTERN_WEIGHT = {
    "데이터 헤비":   0.90,
    "음성 헤비":     0.20,
    "콘텐츠 헤비":   0.60,
    "업무 헤비":     0.50,
}

_GRADE_BY_TENURE = {6: "Bronze", 24: "Silver", 48: "Gold", 84: "Gold"}


def _load_survey() -> dict:
    with open(_SCENARIO_DIR / "survey.json", encoding="utf-8") as f:
        return json.load(f)


def _extract_base(answers: dict[str, str]) -> dict[str, Any]:
    """
    설문 답변 dict({"Q1": "A", ...}) → Base Feature 14개

    survey.json의 options[].features 값을 그대로 매핑.
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

    # 미납 금액·납부 지연: 자동납부 여부로 추정 (Q4 정보 활용)
    # 자동납부면 미납·지연 없음, 자동납부 아니면 일부 지연 가능
    # (간단한 시뮬, 실제는 별도 답변 필요)
    if base.get("나이", 35) >= 50 and not base.get("결합 여부", False):
        base["자동납부 등록 여부"] = False
        base["납부 지연 횟수"] = 1

    # 고객 등급은 가입 개월 + 결합 여부로 추정
    tenure = base.get("가입 개월 수", 24)
    base["고객 등급"] = _GRADE_BY_TENURE.get(tenure, "Silver")
    if base["고객 등급"] == "Gold" and not base.get("결합 여부", False):
        base["고객 등급"] = "Silver"

    return base


def _build_delta(base: dict[str, Any]) -> dict[str, float]:
    """이전 시점 대비 변화량 (시연용 시뮬값)"""
    data_rate = float(base.get("데이터 사용률", 0.4))
    # 데이터 사용 패턴에 따라 증감 시뮬
    if data_rate >= 0.8:
        data_delta = 0.18  # 매달 부족 → 증가 추세
    elif data_rate >= 0.6:
        data_delta = 0.08
    else:
        data_delta = 0.02

    bill = float(base.get("요금제 월정액", 55000))
    avg_bill = bill * 0.92  # 평균 대비 8% 증가로 시뮬
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
    total_lines = family + (3.0 if base.get("결합 여부") else 0.0)  # 인터넷·IPTV 포함
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
    bundle = 1.0 if base.get("결합 여부") else 0.0
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

    시연 단순화를 위해 가중 합계로 산출.
    실제 운영 시 MLflow에 등록된 Score 모델로 교체 가능 (interface 동일).
    """
    satisfaction = float(base.get("품질 만족도", 0.55))
    burden = float(base.get("비용 부담도", 0.5))
    tenure_pct = min(float(base.get("가입 개월 수", 24)) / 84.0, 1.0)
    cs_count = float(base.get("30일 상담 횟수", 0)) / 5.0

    churn = (
        (1 - satisfaction) * 0.35
        + burden * 0.30
        + (1 - tenure_pct) * 0.15
        + min(cs_count, 1.0) * 0.20
    )

    rec_fit = (
        index["고객 가치 Index"] / 100 * 0.4
        + float(base.get("푸시 오픈율", 0.45)) * 0.3
        + index["사용 강도 Index"] / 100 * 0.3
    )

    quality_complaint = (
        (1 - satisfaction) * 0.6
        + min(cs_count, 1.0) * 0.4
    )

    bundle_expand = (
        (1.0 if base.get("결합 여부") else 0.5) * 0.4
        + min(float(base.get("가족 회선 수", 1)) / 5.0, 1.0) * 0.3
        + index["고객 가치 Index"] / 100 * 0.3
    )

    return {
        "이탈 위험 Score":     round(churn, 4),
        "추천 적합도 Score":   round(rec_fit, 4),
        "품질 불만 Score":     round(quality_complaint, 4),
        "결합 확장 Score":     round(bundle_expand, 4),
    }


# ── Public API ────────────────────────────────────────────────

def build_batch_features(survey_answers: dict[str, str]) -> dict[str, Any]:
    """
    설문 답변(dict) → 26개 Batch Feature(dict)

    Parameters
    ----------
    survey_answers : {"Q1": "A", "Q2": "B", ..., "Q12": "C"}

    Returns
    -------
    dict : Base(14) + Delta(2) + Ratio(2) + Index(4) + Score(4)
    """
    base = _extract_base(survey_answers)
    delta = _build_delta(base)
    ratio = _build_ratio(base)
    index = _build_index(base, delta, ratio)
    score = _build_score(base, index)

    return {**base, **delta, **ratio, **index, **score}
