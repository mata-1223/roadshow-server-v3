from __future__ import annotations
"""
시나리오별 불규칙 batch_builder 훅 (escape hatch).

선언형 수식(eval_formula)으로 표현하기 어려운 로직만 Python으로 격리.
L1_feature.json:batch_builder.pre_hook 에서 "core.engines.hooks:<fn>"으로 참조,
run_batch_builder가 defaults 적용 후 steps 평가 전에 호출한다.
입력 feats = survey base + defaults, 반환 = feats에 병합할 추가 dict.
"""
from typing import Any

# CS 결합 형태별 가중치 / 가입개월→등급
_BUNDLE_WEIGHT = {"none": 0.0, "mobile_only": 0.4, "home": 0.7, "full": 1.0}
_GRADE_BY_TENURE = {6: "Bronze", 24: "Silver", 48: "Gold", 84: "Gold"}


def cs_base(f: dict[str, Any]) -> dict[str, Any]:
    """CS proxy 추정(비용부담도·품질만족도·멤버십활용도·30일상담)·자동납부/등급 시뮬·구성비.
    (구 cs._extract_base 추정부 + _build_ratio)"""
    out: dict[str, Any] = {}

    # 청구 급증 경험 → 비용 부담도 (요금제 월정액 가산)
    bill_shock = float(f.get("청구 급증 경험 6m", 0))
    fee_norm = float(f.get("요금제 월정액", 55000)) / 100000.0
    if bill_shock >= 3:
        out["비용 부담도"] = min(0.6 + fee_norm * 0.3, 1.0)
    elif bill_shock >= 1:
        out["비용 부담도"] = min(0.4 + fee_norm * 0.2, 0.8)
    else:
        out["비용 부담도"] = max(0.15 + fee_norm * 0.15, 0.15)

    # 품질 CS 문의 → 품질 만족도 (역수)
    quality_cs = float(f.get("품질 CS 문의 3m", 0))
    if quality_cs >= 3:
        out["품질 만족도"] = 0.25
    elif quality_cs >= 1:
        out["품질 만족도"] = 0.55
    else:
        out["품질 만족도"] = 0.85

    # 멤버십 주간 사용 횟수 → 멤버십 활용도
    member_weekly = float(f.get("멤버십 주간 사용 횟수", 0))
    if member_weekly >= 3:
        out["멤버십 활용도"] = 0.80
    elif member_weekly >= 1:
        out["멤버십 활용도"] = 0.45
    else:
        out["멤버십 활용도"] = 0.10

    # 30일 상담 횟수 추정
    out["30일 상담 횟수"] = round(quality_cs / 3.0, 1)

    # 시니어 + 결합 없음 = 자동납부 미등록 + 가끔 지연 시뮬
    if f.get("나이", 35) >= 50 and not f.get("결합 여부", False):
        out["자동납부 등록 여부"] = False
        out["납부 지연 횟수"] = 1

    # 고객 등급 추정 (가입 개월 + 결합 형태)
    grade = _GRADE_BY_TENURE.get(f.get("가입 개월 수", 24), "Silver")
    if grade == "Gold" and f.get("결합 형태", "none") in ("none", "mobile_only"):
        grade = "Silver"
    out["고객 등급"] = grade

    # 구성비 (약정 진행률 / 가족 결합 비중)
    tenure = float(f.get("가입 개월 수", 24))
    progress = min(tenure / 24.0, 1.0) if tenure <= 24.0 else 1.0
    family = float(f.get("가족 회선 수", 1))
    total_lines = family + _BUNDLE_WEIGHT.get(str(f.get("결합 형태", "none")), 0.0) * 3.0
    family_ratio = family / total_lines if total_lines > 0 else 1.0
    out["약정 진행률"] = round(progress, 4)
    out["가족 결합 비중"] = round(family_ratio, 4)

    return out
