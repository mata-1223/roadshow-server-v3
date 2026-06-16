from __future__ import annotations
"""
CS(cs-myk-v3) Intent 분포 시뮬레이터 (로직 고도화용).

113개 Intent 규모. 페르소나가 설문 응답 + 대표 행동 시퀀스(behavior tree)를 수행했을 때
기대 intent(expected_intents)가 상위 분포에 뜨는지, 그리고 범용 Intent(AI 추천 등)가
과도하게 상위를 점유하지 않는지 평가한다.

지표:
  - cov@5 / cov@10 : expected_intents 중 final top-5/top-10 비율
  - avg_rank       : expected_intents 평균 final 순위 (낮을수록 좋음, /113)
  - 범용 Intent top-5 점유율 : 무작위 응답에서 GENERIC intent가 top-5에 드는 비율

실행: python scripts/sim_cs.py [--behavior] [--dist]
  --behavior : 대표 행동 시퀀스까지 반영
  --dist     : 무작위 응답 기준 top-1/top-5 분포 + 범용 intent 점유율 진단
"""
import argparse
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.engines import config                              # noqa: E402
from core.extractor import get_extractor                     # noqa: E402
from core.inference import infer_batch, infer_with_behavior  # noqa: E402
from scripts.build_cs_dataset import PERSONAS                # noqa: E402

SID = "cs-myk-v3"
N_INTENTS = len(config.get_taxonomy(SID)["intents"])

# 너무 범용적이라 시연에서 상위 노출을 지양할 Intent (AI 추천류)
GENERIC_INTENTS = {"INT-4310", "INT-4320", "INT-4330"}


def _sample_answers(answer_dist: dict, rng: random.Random) -> dict[str, str]:
    return {qid: rng.choices(list(d), weights=list(d.values()), k=1)[0] for qid, d in answer_dist.items()}


def _behavior_map() -> dict[str, tuple[str, str]]:
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


def _names() -> dict[str, str]:
    return {i["id"]: i["name"] for i in config.get_taxonomy(SID)["intents"]}


def _rank_of(scores: list, intent_id: str) -> int:
    for s in scores:
        if s.intent_id == intent_id:
            return s.rank
    return 999


def _rand_answers(rng: random.Random) -> dict[str, str]:
    return {q["id"]: rng.choice([o["code"] for o in q["options"]])
            for q in config.get_survey(SID)["questions"]}


def run(use_behavior: bool, k: int = 30, seed: int = 7) -> None:
    bmap = _behavior_map()
    ext = get_extractor()
    rng = random.Random(seed)
    p5, p10, rank_all = [], [], []
    gen_in5 = 0  # expected 평가 표본에서 범용 intent가 top-5 점유한 횟수
    n_samples = 0
    for p in PERSONAS:
        expected = p["expected_intents"]
        c5s, c10s, rks = [], [], []
        for j in range(k):
            answers = _sample_answers(p["answer_dist"], rng)
            if use_behavior:
                seq = rng.choice(p["action_seqs"])
                sess = f"__cs__{p['id']}_{j}"
                ext.reset(sess)
                for bid in seq:
                    et, ent = bmap.get(bid, (None, None))
                    if et:
                        ext.add_event(sess, et, ent)
                _, scores = infer_with_behavior(answers, sess, SID)
                ext.reset(sess)
            else:
                _, scores = infer_batch(answers, SID)
            top = [s.intent_id for s in sorted(scores, key=lambda s: s.final_score, reverse=True)]
            t5, t10 = set(top[:5]), set(top[:10])
            c5s.append(sum(1 for e in expected if e in t5) / len(expected))
            c10s.append(sum(1 for e in expected if e in t10) / len(expected))
            rks.extend(_rank_of(scores, e) for e in expected)
            gen_in5 += len(GENERIC_INTENTS & t5); n_samples += 1
        cov5, cov10 = sum(c5s) / k, sum(c10s) / k
        p5.append(cov5); p10.append(cov10); rank_all.extend(rks)
        print(f"   {p['id']} {p['name'][:24]:24} cov@5={cov5:.2f} cov@10={cov10:.2f} avg_rank={sum(rks)/len(rks):5.1f}")
    n = len(PERSONAS)
    print("=" * 70)
    print(f"  전체 평균  cov@5={sum(p5)/n:.3f}  cov@10={sum(p10)/n:.3f}  "
          f"avg_rank={sum(rank_all)/len(rank_all):.1f}/{N_INTENTS}  "
          f"({'행동반영' if use_behavior else '설문만'}, k={k})")
    print(f"  범용 intent(AI 추천류) top-5 평균 점유: {gen_in5/n_samples:.2f}개/표본")
    print("=" * 70)


def dist(m: int = 400, seed: int = 3) -> None:
    """무작위 응답에서 top-1/top-5 분포 + 범용 intent 점유율 진단."""
    names = _names()
    rng = random.Random(seed)
    top1 = Counter()
    top5 = Counter()
    gen5 = 0
    for _ in range(m):
        _, scores = infer_batch(_rand_answers(rng), SID)
        top = [s.intent_id for s in sorted(scores, key=lambda s: s.final_score, reverse=True)]
        top1[top[0]] += 1
        for iid in top[:5]:
            top5[iid] += 1
        gen5 += len(GENERIC_INTENTS & set(top[:5]))
    print(f"── 무작위 응답 {m}건 분포 진단 ──")
    print(f"   서로 다른 top-1 intent: {len(top1)}종")
    print("   top-1 최빈 10:")
    for iid, c in top1.most_common(10):
        flag = " ⚠️범용" if iid in GENERIC_INTENTS else ""
        print(f"      {iid} {names.get(iid,'')[:18]:18} {c/m*100:4.1f}%{flag}")
    print(f"   범용 intent(AI 추천류) top-5 점유: {gen5/m:.2f}개/응답 "
          f"(= 평균 {gen5/m/5*100:.0f}% of top-5 slots)")
    print("   범용 intent별 top-5 등장률:")
    for iid in sorted(GENERIC_INTENTS):
        print(f"      {iid} {names.get(iid,'')[:18]:18} {top5[iid]/m*100:4.1f}%")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--behavior", action="store_true")
    ap.add_argument("--dist", action="store_true")
    args = ap.parse_args()
    if args.dist:
        dist()
    else:
        run(args.behavior)
