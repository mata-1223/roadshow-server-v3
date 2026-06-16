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
    if "terms" in node:
        return "복합 항"
    return "항"


def explain_rule(scenario_id: str, intent_id: str, features: dict, top: int = 3) -> list[dict]:
    """rule spec의 top-level 항별 기여도 → |기여| 상위 top개."""
    spec = config.get_rule_spec(scenario_id).get(intent_id)
    if spec is None:
        return []
    terms = spec["terms"] if isinstance(spec, dict) and "terms" in spec else None
    if terms is None:                          # 단일 노드 룰 (if/threshold/feat 등)
        return [{"label": _node_label(spec), "contribution": round(float(eval_formula(spec, features)), 4),
                 "direction": "up"}]
    out = []
    for t in terms:
        val = float(eval_formula(t, features))
        if abs(val) < 1e-9:
            continue
        out.append({"label": _node_label(t), "contribution": round(val, 4),
                    "direction": "up" if val >= 0 else "down"})
    return sorted(out, key=lambda o: -abs(o["contribution"]))[:top]


def explain_intent(engine, intent_id: str, features: dict, inference_type: str, top: int = 3) -> dict:
    """intent 1개의 추론 이유. inference_type에 따라 rule/model 분해."""
    if inference_type == "Model":
        return {"type": "Model", "factors": engine.explain_model(intent_id, features, top=top)}
    return {"type": "Rule", "factors": explain_rule(engine.scenario_id, intent_id, features, top=top)}


def attach_reasoning(engine, features: dict, top_items: list[dict], top: int = 3) -> None:
    """서빙 top_items 각 항목에 reasoning 첨부 (in-place).
    features는 추론에 쓰인 결합 feature(batch+pattern+event)."""
    for it in top_items:
        r = explain_intent(engine, it["intent_id"], features, it.get("inference_type", "Rule"), top=top)
        if it.get("rank_change", 0) and it["rank_change"] > 0:   # 행동으로 상승
            r["behavior_note"] = f"최근 행동으로 순위 +{it['rank_change']} 상승"
        it["reasoning"] = r
