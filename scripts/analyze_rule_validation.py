#!/usr/bin/env python3
"""
가상 시드 데이터셋(seed_dataset.json)으로 Rule 출력의 합리성 검증.

산출:
  1. Rule 출력 vs 양성 라벨: ROC-like 통계 (양성 평균 score vs 비양성 평균 score)
  2. 페르소나별 Top 5 Rule Intent 분포 — 의도된 Intent가 상위에 오는지
  3. Rule이 정의된 Intent와 baseline(0.05)만 반환하는 Intent 비율

실행:
    cd roadshow-server-v3
    python scripts/analyze_rule_validation.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.executor import init_db, get_executor  # noqa: E402
from data.seed import load_intents_catalog       # noqa: E402
from core.engines import config, formula         # noqa: E402

_CS_RULE_SPEC = config.get_rule_spec("cs-myk-v3")


def _load_dataset(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)["samples"]


def _score_with_rules(features: dict, intents: list[dict]) -> dict[str, float]:
    f = dict(features)
    if isinstance(f.get("결합 여부"), bool):
        f["결합 여부"] = 1 if f["결합 여부"] else 0
    out = {}
    for intent in intents:
        if intent["inference_type"] != "Rule":
            continue
        out[intent["id"]] = formula.rule_predict(_CS_RULE_SPEC, intent["id"], f)
    return out


def main() -> None:
    init_db()
    intents = load_intents_catalog()
    intent_meta = {i["id"]: i for i in intents}
    rule_intent_ids = [i["id"] for i in intents if i["inference_type"] == "Rule"]

    dataset_path = Path(__file__).parent.parent / "scenarios" / "cs-myk-v3" / "seed_dataset.json"
    samples = _load_dataset(dataset_path)

    # ── 1. 양성/비양성 평균 score 비교 ────────────────────────
    print("=" * 72)
    print("  Rule 검증: 양성 라벨 vs 비양성 라벨의 평균 Rule score")
    print("=" * 72)

    pos_scores: dict[str, list[float]] = defaultdict(list)
    neg_scores: dict[str, list[float]] = defaultdict(list)

    for s in samples:
        scores = _score_with_rules(s["batch_features"], intents)
        positives = set(s["intent_labels"].keys())
        for iid, sc in scores.items():
            if iid in positives:
                pos_scores[iid].append(sc)
            else:
                neg_scores[iid].append(sc)

    # 양성 빈도가 충분한 Intent만
    rows = []
    for iid in rule_intent_ids:
        pos = pos_scores.get(iid, [])
        neg = neg_scores.get(iid, [])
        if len(pos) < 5:
            continue
        pos_mean = mean(pos)
        neg_mean = mean(neg) if neg else 0.0
        rows.append((iid, len(pos), pos_mean, neg_mean, pos_mean - neg_mean))

    rows.sort(key=lambda r: r[4], reverse=True)

    print(f"\n  {'Intent':10s} {'n(+)':>5s} {'pos_avg':>8s} {'neg_avg':>8s} {'gap':>7s}  L3")
    print(f"  {'-'*10} {'-'*5} {'-'*8} {'-'*8} {'-'*7}  {'-'*30}")
    good, bad = 0, 0
    for iid, n_pos, p, n, gap in rows[:30]:
        name = intent_meta[iid]["name"]
        flag = "✓" if gap > 0.05 else ("·" if gap > 0 else "✗")
        if gap > 0.05: good += 1
        elif gap <= 0: bad += 1
        print(f"  {iid:10s} {n_pos:>5d} {p:>8.3f} {n:>8.3f} {gap:>+7.3f} {flag} {name}")

    print(f"\n  (전체 {len(rows)}개 중) Rule이 양성을 잘 구분: {good}개, 양성↔비양성 격차 부족 또는 역전: {bad}개")

    # ── 2. 페르소나별 Rule Top 5 일치도 ───────────────────────
    print("\n" + "=" * 72)
    print("  페르소나별 Rule Top 5 Intent — 의도된 Intent가 상위에 오는가?")
    print("=" * 72)

    persona_top: dict[str, Counter] = defaultdict(Counter)
    persona_labels: dict[str, Counter] = defaultdict(Counter)
    persona_hits: dict[str, list[int]] = defaultdict(list)

    for s in samples:
        scores = _score_with_rules(s["batch_features"], intents)
        top5 = [iid for iid, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:5]]
        positives = set(s["intent_labels"].keys())
        hit = sum(1 for iid in top5 if iid in positives)
        pid = s["persona_id"]
        persona_hits[pid].append(hit)
        for iid in top5:
            persona_top[pid][iid] += 1
        for iid in positives:
            persona_labels[pid][iid] += 1

    for pid in sorted(persona_top.keys()):
        top_intents = persona_top[pid].most_common(5)
        avg_hit = mean(persona_hits[pid]) if persona_hits[pid] else 0
        top_labels = persona_labels[pid].most_common(5)
        print(f"\n  [{pid}] 평균 Top5 hit (양성과 일치): {avg_hit:.2f}/5")
        print(f"       Rule Top5 :  {', '.join(f'{iid}({c})' for iid, c in top_intents)}")
        print(f"       양성 Top5 :  {', '.join(f'{iid}({c})' for iid, c in top_labels)}")

    # ── 3. Rule 정의 vs baseline-only 분포 ────────────────────
    print("\n" + "=" * 72)
    print("  Rule 정의 통계")
    print("=" * 72)
    defined = len(_CS_RULE_SPEC)
    rule_n = len(rule_intent_ids)
    print(f"\n  Rule Intent 총: {rule_n} (Model 제외)")
    print(f"  명시적 Rule 함수 정의: {defined}개")
    print(f"  baseline(0.05)만 반환: {rule_n - defined}개")
    print(f"  → 향후 ~{rule_n - defined}개 Intent에 명시적 Rule 추가 또는 Model로 전환 검토")


if __name__ == "__main__":
    main()
