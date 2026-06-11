#!/usr/bin/env python3
"""
113개 Intent 전체에 대한 Metadata 표를 마크다운으로 산출.

§1.2 메타데이터 표(~35개 발췌)와 동일 양식.
컬럼: L1 / L2 / L3 / Batch Feature / Event Feature / Behavioral Pattern Feature / 방법론

Event Feature·Behavioral Pattern Feature는 entity 매핑(build_persona_dataset.py의
ENTITY_TO_INTENTS)을 역매핑하여 자동 산출. 매핑이 없으면 "-".

산출: .symposium/intent-taxonomy-full.md
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.engines import config
from scripts.build_persona_dataset import ENTITY_TO_INTENTS  # noqa: E402

SCENARIO_ID = "cs-myk-v3"
SCENARIO_DIR = Path(__file__).parent.parent / "scenarios" / SCENARIO_ID

# ── entity → event-feature/pattern-feature 매핑 ───────────
# build_persona_dataset.py의 ENTITY_TO_INTENTS와 시나리오 §3.3의 entity 그룹을 종합.
ENTITY_META = {
    # entity:               (current_page, group(s), pattern_feature(s))
    "data_usage":           ("data",        ["data_view"],                    ["repeated_entity_count_5m"]),
    "data_topup_button":    (None,          ["data_action"],                  []),
    "data_addon_page":      ("data",        ["data_view", "product_view"],    ["product_explore_count"]),
    "usage_detail_chart":   ("data",        ["data_view"],                    []),
    "billing":              ("billing",     ["billing_view"],                 ["billing_page_view_count"]),
    "billing_detail":       ("billing",     ["billing_view"],                 ["billing_page_view_count"]),
    "pay_now_button":       (None,          ["billing_action"],               []),
    "auto_pay_setting":     ("billing",     ["billing_view"],                 ["billing_page_view_count"]),
    "subscription_info":    ("subscription",["subscription_view"],            []),
    "plan_change_button":   (None,          ["subscription_action"],          []),
    "penalty_calc":         ("churn",       ["churn_view"],                   ["churn_page_view_count"]),
    "cancel_page":          ("churn",       ["churn_view"],                   ["churn_page_view_count"]),
    "benefit_membership":   ("benefit",     ["benefit_view"],                 ["benefit_explore_count"]),
    "coupon_use":           ("benefit",     ["benefit_action"],               ["benefit_explore_count"]),
    "membership_tier":      ("benefit",     ["benefit_view"],                 ["benefit_explore_count"]),
    "promotion_event":      ("benefit",     ["benefit_view"],                 ["benefit_explore_count"]),
    "product_explore":      ("product",     ["product_view"],                 ["product_explore_count"]),
    "plan_explore":         ("product",     ["product_view"],                 ["product_explore_count"]),
    "device_explore":       ("product",     ["product_view"],                 ["product_explore_count"]),
    "family_bundle":        ("subscription",["bundle_view"],                  ["dominant_entity_5m=family_bundle"]),
    "customer_support":     ("support",     ["support_view"],                 []),
    "quality_diagnosis":    ("support",     ["quality_action"],               ["quality_action_count"]),
    "chatbot":              ("support",     ["support_entry"],                ["support_entry_count_5m"]),
    "call_support":         ("support",     ["support_entry"],                ["support_entry_count_5m"]),
}

# ── 카테고리 추가 시그널 (도메인 판단) ──────────────────────
# Rule/Model 정의에서 보통 함께 쓰이는 신호들을 카테고리별로 추가.
L2_FALLBACK_PATTERN = {
    # L2_id : 기본 추정 Pattern Feature (entity 매핑 없을 때 적용)
    "INT-5100": "quality_action_count",          # 품질 문제 해결
    "INT-5300": "support_entry_count_5m",        # 상담 채널
    "INT-7100": "churn_page_view_count",         # 해지 검토
}


def _reverse_entity_map() -> dict[str, list[str]]:
    """Intent ID → 매핑된 entity 목록."""
    out: dict[str, list[str]] = defaultdict(list)
    for entity, intents in ENTITY_TO_INTENTS.items():
        for iid in intents:
            out[iid].append(entity)
    return out


def _event_feature_for(intent_id: str, entities: list[str]) -> str:
    if not entities:
        return "-"
    pages, last_entities = set(), set()
    for e in entities:
        meta = ENTITY_META.get(e)
        if not meta:
            continue
        page, _, _ = meta
        if page:
            pages.add(page)
        last_entities.add(e)
    # is_* 카테고리 추정
    sigs = []
    if any(ENTITY_META.get(e, (None, [], []))[1] and "churn_view" in ENTITY_META[e][1] for e in entities):
        sigs.append("is_churn_signal")
    if any(ENTITY_META.get(e, (None, [], []))[1] and "support_entry" in ENTITY_META[e][1] for e in entities):
        sigs.append("is_support_entry")
    if pages:
        page_str = "/".join(sorted(pages))
        sigs.insert(0, f"current_page={page_str}")
    if last_entities and not sigs:
        sigs.append(f"last_entity={'/'.join(sorted(last_entities))}")
    return ", ".join(sigs) if sigs else "-"


def _pattern_feature_for(intent_id: str, l2_id: str, entities: list[str]) -> str:
    feats: set[str] = set()
    for e in entities:
        meta = ENTITY_META.get(e)
        if not meta:
            continue
        for f in meta[2]:
            feats.add(f)
    # L2 fallback
    if not feats and l2_id in L2_FALLBACK_PATTERN:
        feats.add(L2_FALLBACK_PATTERN[l2_id])
    return ", ".join(sorted(feats)) if feats else "-"


def _format_batch_features(features: list[str]) -> str:
    if not features:
        return "-"
    return ", ".join(features)


def main() -> None:
    SCENARIO_DIR = Path(__file__).parent.parent / "scenarios" / SCENARIO_ID
    intents = config.get_taxonomy["intents"]

    rev = _reverse_entity_map()

    # L1 정렬용 정의된 순서
    L1_ORDER = ["INT-1000", "INT-2000", "INT-3000", "INT-4000",
                "INT-5000", "INT-6000", "INT-7000"]
    intents.sort(key=lambda i: (L1_ORDER.index(i["L1_id"]) if i["L1_id"] in L1_ORDER else 99,
                                i["L2_id"], i["id"]))

    out: list[str] = []
    out.append("# Intent Taxonomy — 113개 전체 메타데이터\n")
    out.append("> CS Domain (cs-myk-v3) 시나리오의 113개 Intent 전체 메타데이터.\n")
    out.append("> §1.2 메타데이터 표(시연 활성 핵심 ~35개 발췌)와 **동일 양식**.\n")
    out.append("> Event Feature·Behavioral Pattern Feature는 entity 매핑(역매핑) + L2 fallback 기반 자동 산출.\n")
    out.append("> 매핑 없는 Intent는 '-'로 표시 — 실시간 신호에는 영향받지 않고 Batch Feature만으로 활성화.\n")
    out.append("\n---\n")

    # 통계
    n_rule = sum(1 for i in intents if i["inference_type"] == "Rule")
    n_model = sum(1 for i in intents if i["inference_type"] == "Model")
    n_with_event = sum(1 for i in intents if i["id"] in rev)
    out.append("## 개요\n")
    out.append(f"- **전체 Intent**: {len(intents)}개\n")
    out.append(f"- **추론 방식**: Rule {n_rule} / Model {n_model}\n")
    out.append(f"- **Event/Pattern Feature 매핑된 Intent**: {n_with_event}개\n")
    out.append(f"- **Batch Feature만으로 활성화되는 Intent**: {len(intents) - n_with_event}개\n")
    out.append("\n---\n\n")

    # L1별로 묶어서 표 출력
    out.append("## Metadata 표\n\n")
    out.append("| L1 | L2 | L3 | Batch Feature | Event Feature | Behavioral Pattern Feature | 방법론 |\n")
    out.append("|---|---|---|---|---|---|---|\n")

    prev_l1 = None
    prev_l2 = None
    for i in intents:
        l1 = i["L1_name"]    if i["L1_name"]    != prev_l1 else ""
        l2 = i["L2_name"]    if i["L2_name"]    != prev_l2 else ""
        prev_l1 = i["L1_name"]
        prev_l2 = i["L2_name"]

        entities = rev.get(i["id"], [])
        event_f = _event_feature_for(i["id"], entities)
        pattern_f = _pattern_feature_for(i["id"], i["L2_id"], entities)
        batch_f = _format_batch_features(i.get("features", []))

        out.append(f"| {l1} | {l2} | {i['name']} | {batch_f} | {event_f} | {pattern_f} | {i['inference_type']} |\n")

    out.append("\n---\n\n")
    out.append("## 비고\n")
    out.append(f"- **Batch Feature**: `scenarios/{SCENARIO_ID}/intents.json`의 `features` 필드 그대로.\n")
    out.append("- **Event Feature**: `current_page`, `last_entity`, `is_churn_signal`, `is_support_entry` 등으로 표현. 시나리오 §3.2 정의 참고.\n")
    out.append("- **Behavioral Pattern Feature**: 5분 window 집계 카운트. 시나리오 §3.3 정의 참고.\n")
    out.append("- **방법론 분포**: Rule 99개 / Model 14개. Rule 중 ~61개는 명시 함수 정의, 나머지는 baseline(0.05).\n")
    out.append("- **시연 활성 핵심 ~35개**: `confluence-cs-scenario.md` §1.2 표 참고.\n")

    out_path = Path(__file__).parent.parent.parent / ".symposium" / "intent-taxonomy-full.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.writelines(out)
    print(f"Wrote {out_path} ({len(intents)} rows)")


if __name__ == "__main__":
    main()
