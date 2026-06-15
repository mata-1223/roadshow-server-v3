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
  • {"feat": n, "linear": [a,b] [, "default": d] [, "clip": [lo,hi]]} → a*x + b
                              (x = features[n], 없으면 d; clip=[lo,hi] 면 x 선-clamp, null=무경계 → min/max 단방향)
  • {"feat": n, "threshold": [[t,v],...], "default": d}        → x>=t 인 첫 v, 없으면 d (내림차순 가정)
  • {"boost": {"feat": n, "scale": s, "cap": c [, "mult": m]}} → min(x*s*m, c*m)
  • {"if": <cond>, "then": c [, "else": e]}                    → cond면 c, 아니면 e(기본 0)
  cond: {"feat": n, "in": [...]} | {"gte"|"gt"|"lte"|"lt"|"eq": v}

설계 규약: 시나리오 차이(수식)는 spec, 평가 메커니즘은 여기 한 곳.
"""
from importlib import import_module
from typing import Any

from core.engines.common import g, clamp


def _load_py(ref: str):
    mod_name, _, fn_name = ref.partition(":")
    return getattr(import_module(mod_name), fn_name)


def _cond(spec: dict, features: dict) -> bool:
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
    """수식 spec → float. (시나리오 무관)"""
    if isinstance(node, bool):
        return float(node)
    if isinstance(node, (int, float)):
        return float(node)
    if not isinstance(node, dict):
        raise ValueError(f"invalid formula node: {node!r}")

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

    if "if" in node:
        return float(node["then"]) if _cond(node["if"], features) else float(node.get("else", 0.0))

    if "feat" in node and "threshold" in node:
        x = g(features, node["feat"], node.get("default", 0.0))
        for t, v in node["threshold"]:
            if x >= t:
                return float(v)
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
