from __future__ import annotations
"""
Intent 추론 이유(reasoning) 추출 — 시나리오 무관.

- Rule  : L2 rule 선언형 spec의 top-level 항(terms)별 기여도를 분해.
- Model : sklearn(StandardScaler+LogisticRegression) 선형성을 이용해
          feature별 기여도 = coef × 표준화값 으로 분해 (models.sklearn_model.explain).
- 행동  : rank_change>0면 "최근 행동으로 상승" 노트.

반환 형식(intent별):
  {"type": "Rule"|"Model",
   "factors": [{"label": str, "contribution": float, "direction": "up"|"down"}, ...]}  # |기여| 상위
"""
from typing import Any

from core.engines import config
from core.engines.formula import eval_formula


def _node_label(node: Any) -> str:
    """rule 항 노드 → 사람이 읽을 라벨."""
    if isinstance(node, (int, float, bool)):
        return "기본 점수"
    if not isinstance(node, dict):
        return str(node)[:24]
    if "feat" in node:
        return str(node["feat"])
    if "boost" in node:                       # 행동(윈도우) feature
        return f"행동: {node['boost'].get('feat', '')}"
    if "if" in node:
        cond = node["if"]
        feat = cond.get("feat") or (cond.get("all") or cond.get("any") or [{}])[0].get("feat")
        return f"조건: {feat}" if feat else "조건"
    if "switch" in node:
        c0 = (node["switch"] or [{}])[0].get("if", {})
        return f"조건: {c0.get('feat', '')}"
    if "clamp" in node and "value" in node:
        return _node_label(node["value"])
    if "terms" in node:                        # 중첩 항 → 첫 feature 항으로 대표
        for t in node["terms"]:
            if not isinstance(t, (int, float, bool)):
                return _node_label(t)
        return "복합 항"
    return "항"


def _node_feat(node: Any) -> str | None:
    """rule 항이 참조하는 feature 키 (현재값 조회용)."""
    if not isinstance(node, dict):
        return None
    if "feat" in node:
        return node["feat"]
    if "boost" in node:
        return node["boost"].get("feat")
    if "if" in node:
        c = node["if"]
        return c.get("feat") or (c.get("all") or c.get("any") or [{}])[0].get("feat")
    if "switch" in node:
        return (node["switch"] or [{}])[0].get("if", {}).get("feat")
    if "clamp" in node and "value" in node:
        return _node_feat(node["value"])
    if "terms" in node:
        for t in node["terms"]:
            f = _node_feat(t)
            if f:
                return f
    return None


# 코드값 feature → 실제 의미 (코드가 아닌 실제값 표시)
VALUE_LABELS = {
    "contract_status": {1: "약정 없음", 2: "약정 잔여 6개월+", 3: "약정 만료 임박"},
    "고객 등급": {"Gold": "골드", "Silver": "실버", "Bronze": "브론즈", "VIP": "VIP", "Green": "그린"},
}


def _fmt_value(feat: str | None, v: Any) -> str | None:
    """feature 현재값 표시 문자열. 코드값(contract_status 등)은 실제 의미로 변환."""
    if v is None:
        return None
    if feat in VALUE_LABELS:
        key = int(v) if isinstance(v, (int, float)) and float(v).is_integer() else v
        if key in VALUE_LABELS[feat]:
            return VALUE_LABELS[feat][key]
    if isinstance(v, bool):
        return "예" if v else "아니오"
    if isinstance(v, (int, float)):
        return f"{v:.2f}".rstrip("0").rstrip(".")
    return str(v)


def explain_rule(scenario_id: str, intent_id: str, features: dict, top: int = 3) -> list[dict]:
    """rule spec의 top-level 항별 기여도 → |기여| 상위 top개. 상수(기본 점수) 제외, 한글 라벨·실제값 포함."""
    spec = config.get_rule_spec(scenario_id).get(intent_id)
    if spec is None:
        return []
    terms = spec["terms"] if isinstance(spec, dict) and "terms" in spec else [spec]
    out = []
    for t in terms:
        if isinstance(t, (int, float, bool)):     # 상수 항(기본 점수) 제외
            continue
        val = float(eval_formula(t, features))
        if abs(val) < 1e-9:
            continue
        feat = _node_feat(t)
        out.append({"label": _label_ko(_node_label(t)), "contribution": round(val, 4),
                    "direction": "up" if val >= 0 else "down",
                    "value": _fmt_value(feat, features.get(feat)) if feat else None})
    return sorted(out, key=lambda o: -abs(o["contribution"]))[:top]


def explain_intent(engine, intent_id: str, features: dict, inference_type: str, top: int = 3) -> dict:
    """intent 1개의 추론 이유. inference_type에 따라 rule/model 분해. 라벨 한글화·코드값 변환."""
    if inference_type == "Model":
        factors = engine.explain_model(intent_id, features, top=top)
        for f in factors:                          # 모델 feature명 → 한글, 코드값 → 실제값
            feat = f.get("label", "")
            f["value"] = _fmt_value(feat, f.get("value"))
            f["label"] = _label_ko(feat)
        return {"type": "Model", "factors": factors}
    return {"type": "Rule", "factors": explain_rule(engine.scenario_id, intent_id, features, top=top)}


# feature 내부명 → 상담사용 한글 라벨
FEATURE_LABELS = {
    "이탈 위험 Score": "이탈 위험도", "Churn Risk Index": "이탈 위험도",
    "요금 민감도 Index": "요금 민감도", "비용 부담도": "비용 부담", "요금제 월정액": "요금제 금액",
    "약정 진행률": "약정 진행 정도", "contract_status": "약정 상태",
    "데이터 사용 증감률": "데이터 사용 증가세", "데이터 사용률": "데이터 사용량",
    "업셀 적합도 Score": "상위 상품 적합도", "사용 강도 Index": "사용 강도",
    "단말 교체 의향 Score": "단말 교체 의향", "멤버십 주간 사용 횟수": "멤버십 사용 빈도",
    "고객 가치 Index": "고객 가치", "멤버십 활용도": "멤버십 활용도", "고객 등급": "고객 등급",
    "가족 회선 수": "가족 회선 수", "non_mobile_cost_gap": "결합 비용 격차",
    "mnp_benefit_check": "번호이동 혜택 조회", "위약금 조회 행동": "위약금 페이지 조회",
    "해지 페이지 진입": "해지 페이지 방문", "churn_page_view_count": "해지 관련 페이지 조회",
    "dissatisfaction_factor": "서비스 불만 요인", "support_entry_count_5m": "상담 진입",
    "quality_action_count": "품질 진단 실행", "benefit_explore_count": "혜택 탐색",
    "billing_page_view_count": "요금 조회", "product_explore_count": "상품 탐색",
    "social_contact": "사회적 접촉", "weekend_out": "주말 외출", "night_phone_usage": "야간 스마트폰 사용",
    "move_pattern": "퇴근 후 이동", "Isolation Tendency Index": "고립 성향",
    "Sleep Disturbance Index": "수면 방해", "Burnout Deep Score": "번아웃 정도",
    "Recovery Motivation Score": "회복 동기", "Fatigue Load Index": "피로 누적",
    "Digital Escape Score": "디지털 도피 성향", "Retention Value Index": "유지 가치",
    "Benefit Engagement Index": "혜택 참여도",
    # bundle 모델 Index/Score
    "Bundle Opportunity Index": "결합 기회 지수", "Home Service Expansion Index": "홈 서비스 확장 지수",
    "Benefit Optimization Index": "혜택 최적화 지수", "Benefit Optimization Score": "혜택 최적화 점수",
    "Service Expansion Score": "서비스 확장 점수", "Acquisition Score": "신규 획득 점수",
    "Retention Readiness Index": "유지 준비 지수", "Retention Value Index": "유지 가치 지수",
    "Retention Value Score": "유지 가치 점수", "Retention Score": "유지 점수",
    "Churn Defense Score": "이탈 방어 점수",
    # 행동/이벤트 윈도우 feature (상담사 [상황]에 등장)
    "churn_action_count_5m": "최근 해지 관련 행동", "comparison_action_count_5m": "최근 비교 행동",
    "decision_action_count_5m": "최근 가입·결정 행동", "entity_focus_ratio_5m": "특정 메뉴 집중도",
    "WiFi 진단 실행": "WiFi 진단 실행", "속도 측정 실행": "속도 측정 실행",
    "장애 페이지 체류": "장애 페이지 체류", "할인 페이지 체류": "할인 페이지 조회",
    "가족 결합 관련 행동": "가족 결합 페이지 조회",
    # 프로필 snake_case
    "benefit_utilization": "혜택 활용도", "content_view_mode": "영상 소비 강도",
    "family_line_count": "가족 회선 수", "household_change": "가구 변화", "offwork_time": "퇴근 시간",
    "overtime_freq": "야근 빈도", "plan_tier": "요금제 등급", "plan_bill_level": "요금제 금액대",
    "monthly_bill_level": "월 요금 수준", "service_coverage_ratio": "서비스 커버리지 비율",
    "tenure_group": "가입 기간대", "age_group": "연령대", "subscribed_service_count": "가입 부가서비스 수",
}


def _label_ko(raw: str) -> str:
    """factor 라벨 → 자연스러운 한글. '조건:/행동:' 접두 제거 후 매핑, 미등록은 접미사 정리."""
    s = raw.replace("조건: ", "").replace("행동: ", "").strip()
    if s in FEATURE_LABELS:
        return FEATURE_LABELS[s]
    return s.replace(" Index", "").replace(" Score", "").strip() or s


def _situation_text(intent_name: str, r: dict) -> str:
    """상담사 콘솔 [상황]용 — 이 고객 특성으로 intent가 추론된 이유를 자연어 한 문장으로."""
    facts = [f for f in r.get("factors", []) if f.get("label") != "기본 점수"]
    facts = [f for f in facts if f.get("direction") == "up"] or facts   # 의도를 끌어올린 특성 우선
    labels = []
    for f in facts[:3]:
        lab = _label_ko(f["label"])
        if lab and lab not in labels:
            labels.append(lab)
    if not labels:
        head = f"고객 응답을 종합해 '{intent_name}' 의도가 추론되었습니다"
    else:
        head = f"이 고객은 {' · '.join(labels)} 측면이 두드러져 '{intent_name}' 의도가 추론되었습니다"
    return head + "."   # 순위 변동(behavior_note)은 상담사 [상황]에서 제외


def attach_reasoning(engine, features: dict, top_items: list[dict], top: int = 3) -> None:
    """서빙 top_items 각 항목에 reasoning 첨부 (in-place).
    features는 추론에 쓰인 결합 feature(batch+pattern+event).
    reasoning.situation_text: 상담사 콘솔 [상황]용 동적 추론 이유 문장."""
    for it in top_items:
        r = explain_intent(engine, it["intent_id"], features, it.get("inference_type", "Rule"), top=top)
        rc = it.get("rank_change", 0)
        if rc and rc > 0:
            r["behavior_note"] = f"최근 행동으로 {rc}위 상승"
        elif rc and rc < 0:
            r["behavior_note"] = f"최근 행동으로 {abs(rc)}위 하락"
        r["situation_text"] = _situation_text(it.get("intent_nm_ko", it["intent_id"]), r)
        it["reasoning"] = r
