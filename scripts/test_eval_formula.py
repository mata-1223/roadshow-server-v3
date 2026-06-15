from __future__ import annotations
"""
eval_formula 등가성 단위 테스트 (Step B).

기존 Python 수식(bundle Index / cs rule·boost)을 spec으로 표기하고
무작위 feature 입력에서 eval_formula == 원식 임을 확정한다.

- affine(연산순서 변환) : |diff| < 1e-9
- 동일 상수/임계/조건/boost : 완전 일치 (==)

실행: python scripts/test_eval_formula.py   (실패 시 AssertionError + exit 1)
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.engines.common import clamp, clamp01           # noqa: E402
from core.engines.formula import eval_formula            # noqa: E402

EPS = 1e-9
_fails: list[str] = []


def _approx(a, b, tol=EPS) -> bool:
    return abs(a - b) <= tol


def check(name, ref, spec, feats, *, exact=False):
    got = eval_formula(spec, feats)
    ok = (got == ref) if exact else _approx(got, ref)
    if not ok:
        _fails.append(f"{name}: ref={ref!r} got={got!r} feats={feats}")


# ── 1. bundle: Bundle Opportunity Index (affine 합 + clamp) ──────
# 원식(bundle.py:59): clamp( (fl-1)/3*50 + (1-scr)*30 + hc/2*20 )
def ref_bundle_opp(f):
    fl  = float(f.get("family_line_count", 1))
    scr = float(f.get("service_coverage_ratio", 0.0))
    hc  = float(f.get("household_change", 0))
    return clamp(((fl - 1) / 3 * 50) + ((1 - scr) * 30) + (hc / 2 * 20))

SPEC_BUNDLE_OPP = {
    "clamp": [0, 100],
    "terms": [
        {"feat": "family_line_count",      "default": 1, "linear": [50 / 3, -50 / 3]},
        {"feat": "service_coverage_ratio", "linear": [-30, 30]},
        {"feat": "household_change",       "linear": [10, 0]},
    ],
}

# ── 2. bundle: Benefit Optimization Index (min/clip + 조건) ──────
# 원식(bundle.py:64): clamp( min(gap,3)/3*40 + (2-bu)*35 + (25 if dissat in (통신비,혜택) else 0) )
def ref_benefit_opt(f):
    gap = float(f.get("non_mobile_cost_gap", 0))
    bu  = float(f.get("benefit_utilization", 2))
    dissat = str(f.get("dissatisfaction_factor", "없음"))
    return clamp((min(gap, 3) / 3 * 40) + ((2 - bu) * 35) + (25 if dissat in ("통신비", "혜택") else 0))

SPEC_BENEFIT_OPT = {
    "clamp": [0, 100],
    "terms": [
        {"feat": "non_mobile_cost_gap", "clip": [None, 3], "linear": [40 / 3, 0]},
        {"feat": "benefit_utilization", "default": 2, "linear": [-35, 70]},
        {"if": {"feat": "dissatisfaction_factor", "in": ["통신비", "혜택"]}, "then": 25},
    ],
}

# ── 3. cs: _rule_1110 (다분기 threshold) ────────────────────────
# 원식(cs.py:478): rate>=.85→.65 / >=.65→.45 / >=.40→.25 / else .10
def ref_rule_1110(f):
    rate = float(f.get("데이터 사용률", 0))
    if rate >= 0.85: return 0.65
    if rate >= 0.65: return 0.45
    if rate >= 0.40: return 0.25
    return 0.10

SPEC_RULE_1110 = {
    "feat": "데이터 사용률",
    "threshold": [[0.85, 0.65], [0.65, 0.45], [0.40, 0.25]],
    "default": 0.10,
}

# ── 4. cs: _pattern_boost (boost, mult=1.5) ─────────────────────
# 원식(cs.py:452): min(v*scale*1.5, cap*1.5)
PBM = 1.5
def ref_boost(f):
    v = float(f.get("churn_page_view_count", 0))
    return min(v * 0.12 * PBM, 0.30 * PBM)

SPEC_BOOST = {"boost": {"feat": "churn_page_view_count", "scale": 0.12, "cap": 0.30, "mult": PBM}}

# ── 5. bundle: 룰 INT-B1110 (affine + clamp01 + 조건) ────────────
# 원식(bundle.py:199): clamp01(0.20 + BOI/100*0.55 + (0.1 if fl>=2 else 0))
def ref_b1110(f):
    boi = float(f.get("Bundle Opportunity Index", 0))
    fl  = float(f.get("family_line_count", 0))
    return clamp01(0.20 + boi / 100 * 0.55 + (0.1 if fl >= 2 else 0))

SPEC_B1110 = {
    "clamp": [0, 1],
    "terms": [
        0.20,
        {"feat": "Bundle Opportunity Index", "linear": [0.55 / 100, 0]},
        {"if": {"feat": "family_line_count", "gte": 2}, "then": 0.1},
    ],
}

# ── 6. py escape hatch ──────────────────────────────────────────
def custom_formula(features):
    return features.get("x", 0) * 2 + 1
SPEC_PY = {"py": "scripts.test_eval_formula:custom_formula"}


# ══════════════ 확장 노드: 복합 조건 / 분기 식 (cs 룰 6종) ══════════════
PBM = 1.5  # PATTERN_BOOST_MULTIPLIER
def _boost(f, key, scale, cap):
    return min(float(f.get(key, 0)) * scale * PBM, cap * PBM)

# 7. _rule_1340: AND 조건 (cs.py:537)
def ref_1340(f):
    return 0.55 if f.get("결합 여부", False) and int(f.get("가족 회선 수", 1)) >= 2 else 0.20
SPEC_1340 = {
    "if": {"all": [{"feat": "결합 여부", "gte": 1}, {"feat": "가족 회선 수", "gte": 2}]},
    "then": 0.55, "else": 0.20,
}

# 8. _rule_3110: AND + bool not (cs.py:645)
def ref_3110(f):
    if float(f.get("미납 금액", 0)) > 0 and not f.get("자동납부 등록 여부", True):
        return 0.70
    return 0.0
SPEC_3110 = {
    "if": {"all": [{"feat": "미납 금액", "gt": 0}, {"feat": "자동납부 등록 여부", "eq": False}]},
    "then": 0.70, "else": 0.0,
}

# 9. _rule_5140: AND + then이 식(boost+clamp) (cs.py:710)
def ref_5140(f):
    bundle = str(f.get("결합 형태", "none"))
    if bundle in ("home", "full") and float(f.get("품질 만족도", 1)) <= 0.4:
        return min(0.55 + _boost(f, "quality_action_count", 0.10, 0.25), 0.95)
    return 0.05
SPEC_5140 = {
    "if": {"all": [{"feat": "결합 형태", "in": ["home", "full"]}, {"feat": "품질 만족도", "lte": 0.4}]},
    "then": {"clamp": [0, 0.95], "terms": [
        0.55, {"boost": {"feat": "quality_action_count", "scale": 0.10, "cap": 0.25, "mult": PBM}}]},
    "else": 0.05,
}

# 10. _rule_6130: then이 affine 식 (cs.py:?)
def ref_6130(f):
    family = int(f.get("가족 회선 수", 1))
    rem = float(f.get("잔여 데이터 비율", 1))
    if family >= 2:
        return 0.30 + (1 - rem) * 0.3
    return 0.05
SPEC_6130 = {
    "if": {"feat": "가족 회선 수", "gte": 2},
    "then": {"terms": [0.30, {"feat": "잔여 데이터 비율", "linear": [-0.3, 0.3]}]},
    "else": 0.05,
}

# 11. _rule_2240: 중첩 분기 → switch (cs.py:?)
def ref_2240(f):
    if f.get("결합 여부"):
        return 0.20
    return 0.45 if int(f.get("가족 회선 수", 1)) >= 2 else 0.20
SPEC_2240 = {
    "switch": [
        {"if": {"feat": "결합 여부", "gte": 1}, "then": 0.20},
        {"if": {"feat": "가족 회선 수", "gte": 2}, "then": 0.45},
    ],
    "else": 0.20,
}

# 12. _rule_2120: OR 조건 + 분기마다 다른 식 (cs.py:563)
def ref_2120(f):
    upsell = float(f.get("업셀 적합도 Score", 0))
    fee = float(f.get("요금제 월정액", 0))
    tier = str(f.get("요금제 구간", ""))
    is_5g_like = tier in ("premium", "mid") or fee >= 55000
    if is_5g_like:
        return min(0.20 + _boost(f, "product_explore_count", 0.04, 0.10), 0.40)
    base = min(upsell * 0.7 + 0.15, 0.70)
    return min(base + _boost(f, "product_explore_count", 0.08, 0.20), 0.95)
SPEC_2120 = {
    "if": {"any": [{"feat": "요금제 구간", "in": ["premium", "mid"]}, {"feat": "요금제 월정액", "gte": 55000}]},
    "then": {"clamp": [0, 0.40], "terms": [
        0.20, {"boost": {"feat": "product_explore_count", "scale": 0.04, "cap": 0.10, "mult": PBM}}]},
    "else": {"clamp": [0, 0.95], "terms": [
        {"clamp": [0, 0.70], "value": {"terms": [{"feat": "업셀 적합도 Score", "linear": [0.7, 0]}, 0.15]}},
        {"boost": {"feat": "product_explore_count", "scale": 0.08, "cap": 0.20, "mult": PBM}}]},
}


def _rand_feats(rng):
    return {
        "family_line_count":        rng.choice([1, 2, 3]),
        "service_coverage_ratio":   round(rng.uniform(0, 1), 4),
        "household_change":         rng.choice([0, 1, 2]),
        "non_mobile_cost_gap":      round(rng.uniform(-1, 5), 3),
        "benefit_utilization":      rng.choice([0, 1, 2, 3]),
        "dissatisfaction_factor":   rng.choice(["없음", "통신비", "혜택", "IPTV 품질"]),
        "데이터 사용률":             round(rng.uniform(0, 1), 4),
        "churn_page_view_count":    rng.choice([0, 1, 2, 3, 5]),
        "Bundle Opportunity Index": round(rng.uniform(0, 100), 2),
        "x":                        rng.randint(0, 10),
        # 확장 노드 테스트용
        "결합 여부":                 rng.choice([0, 1]),
        "가족 회선 수":              rng.choice([1, 2, 3, 4, 5]),
        "미납 금액":                 rng.choice([0, 0, 12000, 50000]),
        "자동납부 등록 여부":         rng.choice([True, False]),
        "결합 형태":                 rng.choice(["none", "mobile_only", "home", "full"]),
        "품질 만족도":               round(rng.uniform(0, 1), 4),
        "quality_action_count":     rng.choice([0, 1, 2, 3, 5]),
        "잔여 데이터 비율":           round(rng.uniform(0, 1), 4),
        "업셀 적합도 Score":          round(rng.uniform(0, 1), 4),
        "요금제 월정액":             rng.choice([35000, 55000, 80000, 100000]),
        "요금제 구간":               rng.choice(["premium", "mid", "standard", "lite"]),
        "product_explore_count":    rng.choice([0, 1, 2, 4]),
    }


def main():
    rng = random.Random(42)
    for _ in range(2000):
        f = _rand_feats(rng)
        check("bundle_opp",  ref_bundle_opp(f),  SPEC_BUNDLE_OPP,  f)            # affine 변환 → tol
        check("benefit_opt", ref_benefit_opt(f), SPEC_BENEFIT_OPT, f)            # min/clip+조건 → tol
        check("rule_1110",   ref_rule_1110(f),   SPEC_RULE_1110,   f, exact=True)
        check("boost",       ref_boost(f),       SPEC_BOOST,       f, exact=True)
        check("b1110",       ref_b1110(f),        SPEC_B1110,       f)
        check("py_escape",   custom_formula(f),  SPEC_PY,          f, exact=True)
        # 확장 노드 (복합 조건 / 분기 식)
        check("rule_1340",   ref_1340(f),  SPEC_1340, f, exact=True)
        check("rule_3110",   ref_3110(f),  SPEC_3110, f, exact=True)
        check("rule_5140",   ref_5140(f),  SPEC_5140, f)             # then에 affine 없음 → 사실상 exact지만 boost*1.5 안전 tol
        check("rule_6130",   ref_6130(f),  SPEC_6130, f)             # affine 변환 → tol
        check("rule_2240",   ref_2240(f),  SPEC_2240, f, exact=True)
        check("rule_2120",   ref_2120(f),  SPEC_2120, f)             # affine(upsell*0.7) 변환 → tol

    if _fails:
        print(f"❌ {len(_fails)}건 불일치 (최대 10건):")
        for e in _fails[:10]:
            print("  " + e)
        sys.exit(1)
    print("✅ eval_formula 등가성 통과 — 12개 수식 패턴(복합조건·분기 포함) × 2000 무작위 케이스")


if __name__ == "__main__":
    main()
