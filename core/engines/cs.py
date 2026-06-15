from __future__ import annotations
"""
CS(cs-myk-v3) Scenario Engine — self-contained.
builder / pattern / event / rules 를 모두 inline (bundle/worker와 동형).
공통은 common(오케스트레이션)·sklearn_model(raw)·core.extractor(공유 저장소)에 위임.
"""
from pathlib import Path
from typing import Any

from core.engines import config, extract, formula
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


# ── Public API ────────────────────────────────────────────────

def build_batch_features(survey_answers: dict[str, str]) -> dict[str, Any]:
    """
    설문 답변(dict) → Batch Feature(dict).

    Base(proxy 추정·자동납부/등급 시뮬)와 가족결합비중은 불규칙 → Python(_extract_base/_build_ratio).
    Delta·Index·Score(선언형 수식)는 L1_feature.json:batch_builder → extract.run_batch_builder.
    """
    base = _extract_base(survey_answers)
    ratio = _build_ratio(base)
    return extract.run_batch_builder({**base, **ratio}, config.get_batch_builder("cs-myk-v3"))


# ═════════════════ [1c]/[1b] Pattern·Event Extractor (선언형) ═════════════════
# entity 그룹 맵·필드 정의는 L1_feature.json(pattern/event), 평가는 core.engines.extract.
def empty_pattern_features() -> dict[str, Any]:
    return extract.pattern_from_spec([], config.get_pattern_spec("cs-myk-v3"))


def pattern_features(session_id: str) -> dict[str, Any]:
    spec = config.get_pattern_spec("cs-myk-v3")
    events = get_extractor().events_within(session_id, window_seconds=spec.get("window_seconds", 300))
    return extract.pattern_from_spec(extract._filter(events, spec.get("filter")), spec)


def empty_event_features() -> dict[str, Any]:
    return extract.event_from_spec(None, config.get_event_spec("cs-myk-v3"))


def event_features(session_id: str) -> dict[str, Any]:
    events = get_extractor()._events_by_session.get(session_id, [])
    last = events[-1] if events else None
    return extract.event_from_spec(last, config.get_event_spec("cs-myk-v3"))


# ═════════════════ [2a] Rule-Based Intent Trigger (선언형) ═════════════════
# 룰 수식 = L2_inference.json:rule → formula.eval_formula + clamp01.
_RULE_SPEC = config.get_rule_spec("cs-myk-v3")


def rule_predict(intent_id: str, features: dict[str, Any]) -> float:
    return formula.rule_predict(_RULE_SPEC, intent_id, features)


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
