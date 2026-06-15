from __future__ import annotations
"""
리팩토링 회귀 스냅샷 하니스 (Step A).

config-driven 수렴 리팩토링(Phase 3~4)의 안전망.
"리팩토링 전 == 후"를 기계적으로 증명한다 — 3시나리오 전체 intent score + feature dict 1:1 비교.

두 스냅샷 패밀리:
  1. scores   : seed_dataset의 (중복 제거된) survey_answers → infer_batch → {intent_id: score}.
                build_batch_features(Index/Score) + rule_predict + model_predict 전체 경로 커버.
  2. features : 고정 합성 이벤트 시퀀스 → engine.pattern_features/event_features dict.
                pattern/event 추출기(엔티티→그룹·플래그 맵) 커버. (타임스탬프류 필드는 비교 제외)

사용법:
  python scripts/regression_snapshot.py --save     # 현재 동작을 baseline으로 저장
  python scripts/regression_snapshot.py --check     # 현재 동작 vs baseline (불일치 시 exit 1)

baseline: .documents/_snapshots/{scenario_id}.json  (gitignore 경로)
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.engines import available_scenarios, get_engine, config  # noqa: E402
from core.extractor import get_extractor                           # noqa: E402
from core.inference import infer_batch                             # noqa: E402

_SNAPSHOT_DIR = Path(__file__).parent.parent / ".documents" / "_snapshots"

# infer 결과의 비결정적/무관 필드 (스냅샷 비교 제외)
_VOLATILE_KEYS = {"last_event_at"}

_ROUND = 6


# ── 정규화 (부동소수·타입 안정화) ───────────────────────────────
def _norm(v):
    if isinstance(v, float):
        return round(v, _ROUND)
    if isinstance(v, bool):
        return v
    return v


def _norm_dict(d: dict) -> dict:
    return {k: _norm(v) for k, v in sorted(d.items()) if k not in _VOLATILE_KEYS}


# ── 1. scores 스냅샷 ────────────────────────────────────────────
def _unique_answers(scenario_id: str) -> list[dict]:
    """seed_dataset의 survey_answers를 중복 제거하여 결정적 순서로 반환."""
    path = Path(__file__).parent.parent / "scenarios" / scenario_id / "seed_dataset.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    seen: dict[tuple, dict] = {}
    for s in data["samples"]:
        ans = s["survey_answers"]
        key = tuple(sorted(ans.items()))
        seen.setdefault(key, ans)
    # 답변 키 정렬 문자열로 결정적 정렬
    return [seen[k] for k in sorted(seen.keys())]


def _scores_snapshot(scenario_id: str) -> list[dict]:
    out = []
    for ans in _unique_answers(scenario_id):
        _, scores = infer_batch(ans, scenario_id)
        out.append({
            "answers": {k: ans[k] for k in sorted(ans)},
            "scores": {s.intent_id: round(s.final_score, _ROUND) for s in scores},
        })
    return out


# ── 2. features 스냅샷 (pattern/event 추출기 커버) ──────────────
def _synthetic_sequence(scenario_id: str) -> list[tuple[str, str]]:
    """behavior_signals의 entity 전체를 (click, entity) 이벤트로 — 매핑 테이블 전수 커버.
    마지막 entity를 한 번 더 반복해 repeated/dominant 집계도 자극."""
    entities = sorted(config.get_behavior_signals(scenario_id).keys())
    seq = [("click", e) for e in entities]
    if entities:
        seq.append(("click", entities[0]))  # 반복 1건
    return seq


def _features_snapshot(scenario_id: str) -> dict:
    engine = get_engine(scenario_id)
    ext = get_extractor()
    session = f"__snapshot__{scenario_id}"
    ext.reset(session)
    for event_type, entity in _synthetic_sequence(scenario_id):
        ext.add_event(session, event_type, entity)  # occurred_at=now → window 내

    snap = {
        "empty_pattern": _norm_dict(engine.empty_pattern_features()),
        "empty_event":   _norm_dict(engine.empty_event_features()),
        "pattern":       _norm_dict(engine.pattern_features(session)),
        "event":         _norm_dict(engine.event_features(session)),
    }
    ext.reset(session)
    return snap


# ── 스냅샷 빌드 ─────────────────────────────────────────────────
def _build(scenario_id: str) -> dict:
    return {
        "scenario_id": scenario_id,
        "scores": _scores_snapshot(scenario_id),
        "features": _features_snapshot(scenario_id),
    }


# ── diff ────────────────────────────────────────────────────────
def _diff(old: dict, new: dict, scenario_id: str) -> list[str]:
    errs: list[str] = []

    # features
    for fam in ("empty_pattern", "empty_event", "pattern", "event"):
        o, n = old["features"].get(fam, {}), new["features"].get(fam, {})
        for k in sorted(set(o) | set(n)):
            if o.get(k) != n.get(k):
                errs.append(f"[{scenario_id}] features.{fam}.{k}: {o.get(k)} → {n.get(k)}")

    # scores (answers 정렬 동일 가정, 길이/순서 검증)
    o_cases, n_cases = old["scores"], new["scores"]
    if len(o_cases) != len(n_cases):
        errs.append(f"[{scenario_id}] scores 케이스 수: {len(o_cases)} → {len(n_cases)}")
    for i, (oc, nc) in enumerate(zip(o_cases, n_cases)):
        if oc["answers"] != nc["answers"]:
            errs.append(f"[{scenario_id}] scores[{i}] answers 불일치")
            continue
        os_, ns_ = oc["scores"], nc["scores"]
        for iid in sorted(set(os_) | set(ns_)):
            if os_.get(iid) != ns_.get(iid):
                errs.append(f"[{scenario_id}] scores[{i}].{iid}: {os_.get(iid)} → {ns_.get(iid)}")
    return errs


# ── main ────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--save", action="store_true", help="baseline 저장")
    g.add_argument("--check", action="store_true", help="baseline 대비 검증")
    ap.add_argument("--scenarios", nargs="*", default=None, help="대상 시나리오(기본: 전체)")
    args = ap.parse_args()

    _SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    scenarios = args.scenarios or available_scenarios()

    if args.save:
        for sid in scenarios:
            snap = _build(sid)
            path = _SNAPSHOT_DIR / f"{sid}.json"
            path.write_text(json.dumps(snap, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            print(f"saved {path}  (scores={len(snap['scores'])} cases)")
        return

    # --check
    all_errs: list[str] = []
    for sid in scenarios:
        path = _SNAPSHOT_DIR / f"{sid}.json"
        if not path.exists():
            print(f"❌ baseline 없음: {path} (먼저 --save)")
            sys.exit(2)
        old = json.loads(path.read_text(encoding="utf-8"))
        new = _build(sid)
        errs = _diff(old, new, sid)
        if errs:
            all_errs.extend(errs)
        print(f"{'❌' if errs else '✅'} {sid}: {len(errs)} diff (scores={len(new['scores'])} cases)")

    if all_errs:
        print("\n── 불일치 상세 (최대 50건) ──")
        for e in all_errs[:50]:
            print("  " + e)
        print(f"\n총 {len(all_errs)}건 불일치 → 회귀 발생")
        sys.exit(1)
    print("\n✅ 무손상 — 전 시나리오 score·feature 1:1 일치")


if __name__ == "__main__":
    main()
