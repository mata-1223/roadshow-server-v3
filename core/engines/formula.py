from __future__ import annotations
"""
선언형 수식 평가기 (Step B / Phase 4 토대).

config의 수식 spec(JSON)을 Python 수식과 수치 동일하게 평가한다.
design 문서 `engines-layered-config-design.md` §5 규약 구현.

노드 종류 (eval_formula 가 재귀 평가):
  • 숫자                      → 그 값
  • {"py": "mod:fn"}          → import 후 fn(features) 호출 (불규칙 로직 escape hatch)
  • {"clamp": [lo,hi], "terms":[...]}  → clamp(Σ terms, lo, hi)
  • {"clamp": [lo,hi], "value": <node>} → clamp(eval(node), lo, hi)
  • {"terms": [...]}          → Σ eval(term)
  • {"feat": n, "linear": [a,b] [, "default": d] [, "clip": [lo,hi]] [, "div": k] [, "mul": m]}
        → ((a*x + b) / k) * m   (div/mul은 순서대로, 원본 연산순서 재현용 — float 1:1)
        (x = features[n], 없으면 d; clip=[lo,hi] 면 x 선-clamp, null=무경계 → min/max 단방향)
  • {"feat": n, "threshold": [[t,v],...], "default": d}        → x>=t 인 첫 v, 없으면 d (내림차순 가정)
  • {"boost": {"feat": n, "scale": s, "cap": c [, "mult": m]}} → min(x*s*m, c*m)
  • {"if": <cond>, "then": <node> [, "else": <node>]}          → cond면 then, 아니면 else(기본 0). then/else는 식 노드.
  • {"switch": [{"if": <cond>, "then": <node>}, ...] [, "else": <node>]} → 첫 매칭 then, 없으면 else (if-elif-else)
  cond: {"feat": n, "in": [...]} | {"gte"|"gt"|"lte"|"lt"|"eq": v}
        | {"all": [<cond>,...]} | {"any": [<cond>,...]} | {"not": <cond>}   (복합 조건)

설계 규약: 시나리오 차이(수식)는 spec, 평가 메커니즘은 여기 한 곳.
"""
from importlib import import_module
from typing import Any, Callable

from core.engines.common import g, clamp, clamp01


def _load_py(ref: str) -> Callable[..., Any]:
    """"module.path:function" 문자열 → 임포트한 콜러블 (py escape / pre_hook 해석)."""
    mod_name, _, fn_name = ref.partition(":")
    return getattr(import_module(mod_name), fn_name)


def rule_predict(rules_spec: dict, intent_id: str, features: dict) -> float:
    """[L2a] 선언형 룰: spec 평가 후 clamp01.
    미등록 intent는 baseline 반환 — 시나리오가 rule spec에 "_default"(메타키)를 주면 그 값,
    없으면 0.05. (bundle/worker는 미지정 → 0.05 유지)"""
    spec = rules_spec.get(intent_id)
    if spec is None:
        return rules_spec.get("_default", 0.05)
    return clamp01(eval_formula(spec, features))


def _cond(spec: dict, features: dict) -> bool:
    """조건 spec 평가 → bool. 복합(all/any/not) + 비교(in/gte/gt/lte/lt/eq)."""
    if "all" in spec:
        return all(_cond(c, features) for c in spec["all"])
    if "any" in spec:
        return any(_cond(c, features) for c in spec["any"])
    if "not" in spec:
        return not _cond(spec["not"], features)
    feat = spec["feat"]
    if "in" in spec:
        return features.get(feat) in spec["in"]
    x = g(features, feat)
    if "gte" in spec: return x >= spec["gte"]
    if "gt"  in spec: return x >  spec["gt"]
    if "lte" in spec: return x <= spec["lte"]
    if "lt"  in spec: return x <  spec["lt"]
    if "eq"  in spec: return features.get(feat) == spec["eq"]
    raise ValueError(f"unknown cond: {spec}")


def eval_formula(node: Any, features: dict) -> float:
    """수식 spec → float. (시나리오 무관). dict 노드는 결과에 div→mul 후처리(연산순서 재현)."""
    if isinstance(node, bool):
        return float(node)
    if isinstance(node, (int, float)):
        return float(node)
    if not isinstance(node, dict):
        raise ValueError(f"invalid formula node: {node!r}")
    v = _raw(node, features)
    if "div" in node:                      # 후처리 (a*x+b)/div*mul 등 원본 연산순서 재현
        v = v / node["div"]
    if "mul" in node:
        v = v * node["mul"]
    return v


def _raw(node: dict, features: dict) -> float:
    """노드 타입별 원시값 계산 (div/mul 후처리 전). eval_formula 내부용."""
    if "py" in node:
        return float(_load_py(node["py"])(features))

    if "clamp" in node:
        lo, hi = node["clamp"]
        if "terms" in node:
            inner = sum(eval_formula(t, features) for t in node["terms"])
        else:
            inner = eval_formula(node["value"], features)
        return clamp(inner, lo, hi)

    if "terms" in node:
        return sum(eval_formula(t, features) for t in node["terms"])

    if "boost" in node:
        b = node["boost"]
        x = g(features, b["feat"])
        mult = b.get("mult", 1.0)
        return min(x * b["scale"] * mult, b["cap"] * mult)

    if "switch" in node:
        for case in node["switch"]:
            if _cond(case["if"], features):
                return eval_formula(case["then"], features)
        return eval_formula(node.get("else", 0.0), features)

    if "if" in node:
        branch = node["then"] if _cond(node["if"], features) else node.get("else", 0.0)
        return eval_formula(branch, features)

    if "feat" in node and "map" in node:           # 범주값 → 가중치 lookup
        return float(node["map"].get(features.get(node["feat"]), node.get("default", 0.0)))

    if "feat" in node and "threshold" in node:
        x = g(features, node["feat"], node.get("default", 0.0))
        for t, val in node["threshold"]:
            if x >= t:
                return float(val)
        return float(node.get("default", 0.0))

    if "feat" in node and "linear" in node:
        a, b = node["linear"]
        x = g(features, node["feat"], node.get("default", 0.0))
        if "clip" in node:
            lo, hi = node["clip"]          # null = 무경계 (min/max 단방향 표현)
            if lo is not None:
                x = max(lo, x)
            if hi is not None:
                x = min(hi, x)
        return a * x + b

    raise ValueError(f"unknown formula node: {node!r}")

    raise ValueError(f"unknown formula node: {node!r}")
