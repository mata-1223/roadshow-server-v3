from __future__ import annotations
"""
Rule-based Intent Trigger ([2a] reference 모듈)

100개 Rule Intent에 대한 추론.
Rule은 Batch Feature와 Behavioral Pattern Feature를 함께 입력으로 받는다.
- 시연 활성 핵심: 명시적 Rule 함수 (Batch + Pattern Feature 결합식)
- 나머지: baseline (0.05). 행동이 발생하면 동일 features로 다시 호출되어 점수가 갱신된다.
"""
from typing import Any, Callable


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


# ── Public API ────────────────────────────────────────────────

_BASELINE_SCORE = 0.05


def predict(intent_id: str, features: dict[str, Any]) -> float:
    """
    Intent ID에 대해 Rule 기반 Score 산출.

    명시적 Rule이 정의된 Intent → 해당 Rule 함수 실행
    명시적 Rule 없는 Intent → baseline score 반환 (Pattern/Event Feature가 모델 입력에 들어와도 Rule 식이 없으면 baseline 유지)
    """
    rule_fn = RULES.get(intent_id)
    if rule_fn is None:
        return _BASELINE_SCORE
    try:
        score = rule_fn(features)
        return max(0.0, min(1.0, float(score)))
    except Exception:
        return _BASELINE_SCORE


def get_defined_rule_count() -> int:
    """명시적 Rule이 정의된 Intent 수"""
    return len(RULES)
