from __future__ import annotations
"""
[L1] pattern / event Feature 추출기 (선언형, 시나리오 무관).

config(L1_feature.json)의 pattern/event spec + 공유 이벤트 → Feature dict.
집계 메커니즘은 여기 한 곳, 시나리오 차이(필터·entity맵·필드정의)는 spec.

핵심: pattern_from_spec([]) == empty_pattern_features() 이므로 "필터 후 빈 경우" 분기 불필요.

── pattern spec ──
{
  "window_seconds": 300,
  "filter": {"exclude": [...]} | {"include": [...]} | 생략(전체),
  "entity_groups": { entity: [group, ...] },          # 선택 (cs)
  "fields": [ {"name": ..., "source": ..., ...}, ... ]
}
  source: const(value) / group_count(key) / type_count(key) / entity_count(key)
          / distinct_entity / repeated_max / total / dominant_entity / last_entity
          / focus_ratio(round) / recent_join(field, n, sep)
  수치 변환: "mult": k  /  "binary": true (>0 → 1)

── event spec ── (없거나 {} 면 빈 dict — worker)
{
  "entity_page_map": {entity: page}, "page_field": "current_page", "page_default": "unknown",  # cs
  "trigger_by_entity": {entity: flag_name},                                                     # bundle
  "flags": [ {"name": ..., "when": {"event_type_eq"|"entity_in"|"entity_eq": ...}} ],
  "timestamp_field": "last_event_at"                                                            # cs (휘발)
}
last_event_type / last_entity 는 항상 포함.
"""
from typing import Any


# ── 이벤트 필터 ─────────────────────────────────────────────────
def _filter(events: list[dict], filt: dict | None) -> list[dict]:
    if not filt:
        return list(events)
    if "exclude" in filt:
        ex = set(filt["exclude"])
        return [e for e in events if e["event_type"] not in ex]
    if "include" in filt:
        inc = set(filt["include"])
        return [e for e in events if e["event_type"] in inc]
    return list(events)


# ── 집계 ────────────────────────────────────────────────────────
def _aggregate(events: list[dict], spec: dict) -> dict:
    entity_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    group_counts: dict[str, int] = {}
    groups = spec.get("entity_groups", {})
    for e in events:
        ent = e["entity"]
        entity_counts[ent] = entity_counts.get(ent, 0) + 1
        type_counts[e["event_type"]] = type_counts.get(e["event_type"], 0) + 1
        for grp in groups.get(ent, []):
            group_counts[grp] = group_counts.get(grp, 0) + 1
    dominant = max(entity_counts.items(), key=lambda kv: kv[1])[0] if entity_counts else ""
    return {
        "entity_counts": entity_counts,
        "type_counts":   type_counts,
        "group_counts":  group_counts,
        "total":         len(events),
        "dominant":      dominant,
        "dom_count":     entity_counts.get(dominant, 0),
        "events":        events,
    }


def _field_value(fld: dict, ctx: dict) -> Any:
    src = fld["source"]

    # 문자열/특수 반환 (변환 미적용)
    if src == "const":
        return fld["value"]
    if src == "dominant_entity":
        return ctx["dominant"]
    if src == "last_entity":
        return ctx["events"][-1]["entity"] if ctx["events"] else ""
    if src == "focus_ratio":
        v = ctx["dom_count"] / ctx["total"] if ctx["total"] else 0.0
        return round(v, fld.get("round", 4))
    if src == "recent_join":
        recent = ctx["events"][-fld.get("n", 3):]
        return fld.get("sep", "→").join(e[fld["field"]] for e in recent)

    # 수치 소스
    if src == "group_count":
        v: float = ctx["group_counts"].get(fld["key"], 0)
    elif src == "type_count":
        v = ctx["type_counts"].get(fld["key"], 0)
    elif src == "entity_count":
        v = ctx["entity_counts"].get(fld["key"], 0)
    elif src == "distinct_entity":
        v = len(ctx["entity_counts"])
    elif src == "repeated_max":
        v = max(ctx["entity_counts"].values()) if ctx["entity_counts"] else 0
    elif src == "total":
        v = ctx["total"]
    else:
        raise ValueError(f"unknown pattern source: {src!r}")

    if "mult" in fld:
        v = v * fld["mult"]
    if fld.get("binary"):
        v = 1 if v > 0 else 0
    return v


def pattern_from_spec(events: list[dict], spec: dict) -> dict[str, Any]:
    ctx = _aggregate(events, spec)
    return {fld["name"]: _field_value(fld, ctx) for fld in spec.get("fields", [])}


# ── event ───────────────────────────────────────────────────────
def _flag_match(when: dict, ev: dict) -> bool:
    if "event_type_eq" in when:
        return ev["event_type"] == when["event_type_eq"]
    if "entity_in" in when:
        return ev["entity"] in when["entity_in"]
    if "entity_eq" in when:
        return ev["entity"] == when["entity_eq"]
    raise ValueError(f"unknown flag cond: {when!r}")


def event_from_spec(last_event: dict | None, spec: dict | None) -> dict[str, Any]:
    if not spec:                       # worker: event feature 미생성
        return {}
    out: dict[str, Any] = {
        "last_event_type": last_event["event_type"] if last_event else "",
        "last_entity":     last_event["entity"] if last_event else "",
    }
    if "entity_page_map" in spec:
        pf = spec.get("page_field", "current_page")
        out[pf] = (spec["entity_page_map"].get(last_event["entity"], spec.get("page_default", "unknown"))
                   if last_event else "")
    triggers = spec.get("trigger_by_entity", {})
    for t in sorted(set(triggers.values())):
        out[t] = 0
    if last_event and triggers.get(last_event["entity"]):
        out[triggers[last_event["entity"]]] = 1
    for flag in spec.get("flags", []):
        out[flag["name"]] = (1 if (last_event and _flag_match(flag["when"], last_event)) else 0)
    if "timestamp_field" in spec:
        ts = last_event["occurred_at"] if last_event else None
        out[spec["timestamp_field"]] = ts.isoformat() if ts else ""
    return out
