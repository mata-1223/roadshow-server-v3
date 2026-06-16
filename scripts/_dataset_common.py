#!/usr/bin/env python3
"""
페르소나 기반 seed_dataset 생성 공통 프레임워크 (시나리오 무관).

각 시나리오 스크립트(build_persona/bundle/worker_dataset.py)는 PERSONAS·엔진·파라미터만
주입하고 build_samples()를 호출한다. 동작은 기존 3개 스크립트와 byte-identical.

핵심:
  - build_samples(): persona 샘플링 → 답변 → batch → 행동 시퀀스 → pattern/event → 라벨 (RNG 순서 보존)
  - tree_action_resolver(): behavior_id 2단 트리 → actions (CS/bundle)
  - app_action_resolver(): 앱 entity 시퀀스 → actions (worker 등 단일선택)
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.extractor import get_extractor  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n",    type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


# ── 행동 시퀀스 → actions 변환 ────────────────────────────────
def tree_action_resolver(behaviors_data: dict) -> Callable[[list[str]], list[dict]]:
    """behavior_id 2단 트리(step1 + step2.by_parent + step2.common) → resolver(seq)->actions."""
    by_id = {b["id"]: b for b in behaviors_data["step1"]["behaviors"]}
    for items in behaviors_data["step2"]["by_parent"].values():
        for b in items:
            by_id[b["id"]] = b
    for b in behaviors_data["step2"]["common"]:
        by_id[b["id"]] = b

    def resolve(seq: list[str]) -> list[dict]:
        out = []
        for bid in seq:
            b = by_id.get(bid)
            if b is None:
                continue
            out.append({"behavior_id": b["id"], "event_type": b["event_type"], "entity": b["entity"]})
        return out

    return resolve


def app_action_resolver(seq: list[str]) -> list[dict]:
    """앱 entity 시퀀스 → actions (event_type=app_open 단일화)."""
    return [{"behavior_id": f"app-{e}", "event_type": "app_open", "entity": e} for e in seq]


def _scalar(d: dict) -> dict:
    """스칼라 feature만(키 정렬). list/dict·wall-clock(*_at, 모델 feature 아님) 제외.
    엔진의 set 기반 키 순서(예: bundle event 트리거)까지 정렬로 흡수 → 완전 결정적 출력."""
    return {k: d[k] for k in sorted(d)
            if not isinstance(d[k], (list, dict)) and not k.endswith("_at")}


# ── 샘플 생성 루프 (RNG 호출 순서 고정) ───────────────────────
def build_samples(
    *,
    n: int,
    seed: int,
    personas: list[dict],
    engine: Any,                       # build_batch_features/pattern_features/event_features 보유 모듈
    seq_key: str,                      # "action_seqs" | "app_seqs"
    action_resolver: Callable[[list[str]], list[dict]],
    entity_intents: dict[str, list[str]],
    cust_prefix: str,                  # "C" | "BC" | "WC"
    behavior_labels: bool = True,      # False면 모델 라벨에 행동 신호 intent 제외 (행동→intent는 ranker 담당)
) -> list[dict]:
    rng = random.Random(seed)
    ex = get_extractor()

    rows = []
    for i in range(n):
        persona = rng.choices(personas, weights=[p["weight"] for p in personas], k=1)[0]
        answers = {qid: rng.choices(list(d), weights=list(d.values()), k=1)[0]
                   for qid, d in persona["answer_dist"].items()}
        batch = engine.build_batch_features(answers)
        seq = rng.choice(persona[seq_key])
        actions = action_resolver(seq)

        # 행동 시퀀스를 공유 저장소에 통과시켜 Pattern/Event Feature 산출(추론 시점과 동일 경로)
        sid = f"{cust_prefix}{i + 1:05d}"
        ex.reset(sid)
        for a in actions:
            ex.add_event(sid, a["event_type"], a["entity"])
        pattern = engine.pattern_features(sid)
        event = engine.event_features(sid) if actions else {}
        ex.reset(sid)

        # 양성 라벨: persona expected_intents (+ behavior_labels=True면 행동 신호 intent도)
        positives = set(persona["expected_intents"])
        if behavior_labels:
            for a in actions:
                positives.update(entity_intents.get(a["entity"], []))
        labels = {iid: 1 for iid in sorted(positives)}   # 정렬 → 결정적 키 순서

        rows.append({
            "cust_id":          sid,
            "persona_id":       persona["id"],
            "persona_name":     persona["name"],
            "survey_answers":   answers,
            "batch_features":   _scalar(batch),
            "pattern_features": _scalar(pattern),
            "event_features":   _scalar(event),
            "actions":          actions,
            "intent_labels":    labels,
        })
    return rows


def write_dataset(out_path: Path, rows: list[dict], scenario_id: str, n_personas: int, seed: int) -> None:
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "scenario_id": scenario_id,
            "n_samples":   len(rows),
            "n_personas":  n_personas,
            "seed":        seed,
            "samples":     rows,
        }, f, ensure_ascii=False, indent=2)
    print(f"Wrote {out_path} ({len(rows)} samples)")


def print_label_stats(rows: list[dict], *, total: int | None = None, top_n: int | None = None) -> None:
    label_counts = Counter()
    for r in rows:
        for iid in r["intent_labels"]:
            label_counts[iid] += 1

    title = f"양성 라벨 Top {top_n}" if top_n else "양성 라벨"
    print(f"\n── {title} ──")
    items = label_counts.most_common(top_n) if top_n else label_counts.most_common()
    for iid, c in items:
        print(f"  {iid}: {c} ({c / len(rows) * 100:.1f}%)")
    suffix = f" / {total}" if total else ""
    print(f"\n  총 양성 라벨 Intent 종류: {len(label_counts)}{suffix}")
