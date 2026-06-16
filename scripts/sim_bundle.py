from __future__ import annotations
"""
결합(bundle-v3) Intent 분포 시뮬레이터 (로직 고도화용).

각 페르소나가 설문(대표 답변)에 응답하고 대표 행동 시퀀스를 수행했을 때,
기대 intent(expected_intents)가 상위 분포에 뜨는지 점수화해 "납득 가능한 분포"인지 평가한다.

지표:
  - cov@5 / cov@10 : expected_intents 중 final top-5/top-10에 든 비율
  - avg_rank       : expected_intents의 평균 final 순위 (낮을수록 좋음)
  - 페르소나별 + 전체 평균

실행: python scripts/sim_bundle.py [--behavior]   (--behavior: 대표 행동 시퀀스까지 반영)
"""
import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.engines import config                              # noqa: E402
from core.extractor import get_extractor                     # noqa: E402
from core.inference import infer_batch, infer_with_behavior, to_topn_with_others  # noqa: E402
from scripts.build_bundle_dataset import PERSONAS            # noqa: E402

SID = "bundle-v3"


def _sample_answers(answer_dist: dict, rng: random.Random) -> dict[str, str]:
    """answer_dist 분포에서 1명의 응답을 샘플링 (실제 시연자 응답을 모사)."""
    return {qid: rng.choices(list(d), weights=list(d.values()), k=1)[0]
            for qid, d in answer_dist.items()}


def _behavior_map() -> dict[str, tuple[str, str]]:
    """behavior_id → (event_type, entity). BACK/EXIT 포함."""
    bc = config.get_behaviors(SID)
    m: dict[str, tuple[str, str]] = {}
    for b in bc["step1"]["behaviors"]:
        m[b["id"]] = (b["event_type"], b["entity"])
    for items in bc["step2"]["by_parent"].values():
        for b in items:
            m[b["id"]] = (b["event_type"], b["entity"])
    for b in bc["step2"].get("common", []):
        m[b["id"]] = (b["event_type"], b["entity"])
    m.setdefault("BACK", ("navigate_back", "back_to_step1"))
    m.setdefault("EXIT", ("app_exit", "session_end"))
    return m


def _intent_names() -> dict[str, str]:
    return {i["id"]: i["name"] for i in config.get_taxonomy(SID)["intents"]}


def _rank_of(scores: list, intent_id: str) -> int:
    """final 순위(1-기반). 없으면 999."""
    for s in scores:
        if s.intent_id == intent_id:
            return s.rank
    return 999


def run(use_behavior: bool, k: int = 40, seed: int = 7) -> None:
    """페르소나마다 answer_dist에서 k명을 샘플링해 cov@5/10·avg_rank 평균 (분포 충실)."""
    bmap = _behavior_map()
    ext = get_extractor()
    rng = random.Random(seed)

    p_cov5, p_cov10, rank_all = [], [], []
    for p in PERSONAS:
        expected = p["expected_intents"]
        c5s, c10s, rks = [], [], []
        for j in range(k):
            answers = _sample_answers(p["answer_dist"], rng)
            if use_behavior:
                seq = rng.choice(p["action_seqs"])
                sess = f"__sim__{p['id']}_{j}"
                ext.reset(sess)
                for bid in seq:
                    et, ent = bmap.get(bid, (None, None))
                    if et:
                        ext.add_event(sess, et, ent)
                _, scores = infer_with_behavior(answers, sess, SID)
                ext.reset(sess)
            else:
                _, scores = infer_batch(answers, SID)

            top_ids = [s.intent_id for s in sorted(scores, key=lambda s: s.final_score, reverse=True)]
            top5, top10 = set(top_ids[:5]), set(top_ids[:10])
            c5s.append(sum(1 for e in expected if e in top5) / len(expected))
            c10s.append(sum(1 for e in expected if e in top10) / len(expected))
            rks.extend(_rank_of(scores, e) for e in expected)

        cov5, cov10 = sum(c5s) / k, sum(c10s) / k
        p_cov5.append(cov5); p_cov10.append(cov10); rank_all.extend(rks)
        print(f"   {p['id']} {p['name'][:22]:22} cov@5={cov5:.2f} cov@10={cov10:.2f} "
              f"avg_rank={sum(rks)/len(rks):4.1f}")

    n = len(PERSONAS)
    print("=" * 64)
    print(f"  전체 평균  cov@5={sum(p_cov5)/n:.3f}  cov@10={sum(p_cov10)/n:.3f}  "
          f"avg_rank={sum(rank_all)/len(rank_all):.1f}  ({'행동반영' if use_behavior else '설문만'}, k={k})")
    print("=" * 64)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--behavior", action="store_true", help="대표 행동 시퀀스까지 반영")
    args = ap.parse_args()
    run(args.behavior)
