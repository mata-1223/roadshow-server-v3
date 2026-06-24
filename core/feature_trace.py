from __future__ import annotations
"""
파생 변수(Index/Score) 산출 근거 trace — 시나리오 무관.

L1 batch_builder 의 선언형 step formula 와 실제 입력값을 풀어,
각 최종 파생 변수가 "어떤 입력으로 어떻게 계산됐는지"를 사람이 읽을 수 있는
구조로 반환한다. (프론트 분석 오버레이의 변수 클릭 → 산식 팝오버용)

반환: { 파생변수명: {
          "value": float,                       # 최종 값
          "clamp": [lo,hi] | None,              # 범위 제한(있으면)
          "kind": "passthrough" | "weighted_sum",
          "terms": [ {                           # 기여 항
              "ref": str,                        # 입력 변수명(base 또는 노출 Index명)
              "ref_value": float,                # 그 입력의 현재 값
              "weight": float | None,            # 가중치(선형 [w,0] 항일 때)
              "contribution": float,             # 이 항이 결과에 더한 값
          }, ... ],
       } }
"""
from typing import Any

from core.engines import config
from core.engines.extract import survey_base
from core.engines.formula import eval_formula, _load_py


def build_feature_trace(scenario_id: str, answers: dict[str, str]) -> dict[str, dict]:
    survey = config.get_survey(scenario_id)
    spec = config.get_batch_builder(scenario_id)
    steps = spec.get("steps", [])
    if not steps:
        return {}

    # 0) base feature → 선택한 응답 라벨 (숫자값 대신 "22시 이후" 같은 의미 표시용)
    base_answer: dict[str, str] = {}
    for q in survey.get("questions", []):
        code = answers.get(q["id"])
        if code is None:
            continue
        opt = next((o for o in q.get("options", []) if o.get("code") == code), None)
        if not opt:
            continue
        for fname in (opt.get("features") or {}):
            base_answer[fname] = opt.get("label")

    # 1) 모든 step을 중간값 포함해 평가 (run_batch_builder 와 동일하되 intermediate 보존)
    feats: dict[str, Any] = dict(survey_base(survey, answers))
    for k, v in spec.get("defaults", {}).items():
        feats.setdefault(k, v)
    if "pre_hook" in spec:
        feats.update(_load_py(spec["pre_hook"])(feats))

    inter_names: set[str] = set()
    step_formula: dict[str, Any] = {}
    label_map: dict[str, str] = {}        # 중간/파생 변수명 → 읽기 쉬운 라벨(step.label)
    for st in steps:
        val = eval_formula(st["formula"], feats)
        if "round" in st:
            val = round(val, st["round"])
        feats[st["name"]] = val
        step_formula[st["name"]] = st["formula"]
        if st.get("label"):
            label_map[st["name"]] = st["label"]
        if st.get("intermediate"):
            inter_names.add(st["name"])

    # 2) 중간값(_FAT 등) → 그것을 그대로 노출하는 최종 Index명 매핑 (passthrough)
    inter_to_final: dict[str, str] = {}
    for st in steps:
        f = st["formula"]
        if (not st.get("intermediate") and isinstance(f, dict) and f.get("feat") in inter_names
                and f.get("linear") == [1, 0] and "div" not in f and "mul" not in f):
            inter_to_final[f["feat"]] = st["name"]

    def _terms(formula):
        if not isinstance(formula, dict):
            return []            # 상수 등 비-dict formula → 기여 항 없음
        if "terms" in formula:
            return formula["terms"]
        return [formula]  # 단일 feat 노드

    def _cond_feat(c):
        # 조건(cond)이 참조하는 입력 feat — 단일/복합(all·any·not) 모두 탐색
        if not isinstance(c, dict):
            return None
        if c.get("feat") is not None:
            return c["feat"]
        for key in ("all", "any"):
            for sub in (c.get(key) or []):
                r = _cond_feat(sub)
                if r:
                    return r
        if "not" in c:
            return _cond_feat(c["not"])
        return None

    def _feat_of(t):
        # 항의 입력 feat — 평면 {feat}, 중첩 {clamp,value:{feat}}, 조건부 {if/switch} 모두 인식
        if not isinstance(t, dict):
            return None
        if t.get("feat") is not None:
            return t["feat"]
        v = t.get("value")
        if isinstance(v, dict) and v.get("feat") is not None:
            return v["feat"]
        if isinstance(t.get("if"), dict):                       # 조건부(if) 항 → 조건이 보는 입력
            return _cond_feat(t["if"])
        if isinstance(t.get("switch"), list) and t["switch"]:   # switch 항 → 첫 분기 조건의 입력
            return _cond_feat(t["switch"][0].get("if", {}))
        return None

    def _weight(term: dict):
        if not isinstance(term, dict):
            return None
        lin = term.get("linear")
        if lin and lin[1] == 0 and "div" not in term and "mul" not in term:
            return lin[0]
        if isinstance(term.get("mul"), (int, float)):   # clamp/value 래퍼 항은 mul이 사실상 가중치
            return term["mul"]
        return None

    def _num(v):
        return round(float(v), 2) if isinstance(v, (int, float)) and not isinstance(v, bool) else v

    trace: dict[str, dict] = {}
    for st in steps:
        if st.get("intermediate"):
            continue
        name = st["name"]
        f = st["formula"]
        # passthrough Index 는 중간값 산식을 인라인해 base 입력까지 노출
        eff = f
        kind = "weighted_sum"
        if isinstance(f, dict) and f.get("feat") in inter_names and f.get("linear") == [1, 0]:
            eff = step_formula[f["feat"]]
            kind = "passthrough"
        clamp = eff["clamp"] if isinstance(eff, dict) and "clamp" in eff else None
        # 외부 배수/제수(예: Index의 mul:100) — 각 항 기여에도 동일 적용해야 합이 value와 일치
        mul_o = eff.get("mul", 1) if isinstance(eff, dict) else 1
        div_o = eff.get("div", 1) if isinstance(eff, dict) else 1
        factor = (mul_o or 1) / (div_o or 1)

        terms = []
        for t in _terms(eff):
            ref = _feat_of(t)
            try:
                contribution = round(eval_formula(t, feats) * factor, 2)
            except Exception:
                contribution = None
            if ref is None:
                # feat 없는 항(상수=기본 점수 / if·switch=조건부) — 합 보존을 위해 포함
                is_cond = isinstance(t, dict) and ("if" in t or "switch" in t)
                terms.append({
                    "ref": "조건부 항" if is_cond else "기본 점수",
                    "ref_value": None, "ref_answer": None,
                    "weight": None, "contribution": contribution,
                })
                continue
            terms.append({
                "ref": label_map.get(ref) or inter_to_final.get(ref, ref),
                "ref_value": _num(feats.get(ref, 0.0)),   # 문자열(범주형) 값은 그대로
                "ref_answer": base_answer.get(ref),        # base 입력이면 선택 응답 라벨
                "weight": _weight(t),
                "contribution": contribution,
            })
        trace[name] = {
            "value": _num(feats[name]),
            "clamp": clamp,
            "kind": kind,
            "terms": terms,
        }
    return trace
