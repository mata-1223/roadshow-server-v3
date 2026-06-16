from __future__ import annotations
"""
직장인(worker-v3) Intent 분포 시뮬레이터 (로직 고도화용).

페르소나가 설문 응답·앱 선택(단일선택, app_open)을 했을 때 기대 intent(expected_intents)가
상위 분포에 뜨는지 점수화. intent가 9개뿐이라 cov@3/cov@5 + avg_rank(/9) 사용.

실행: python scripts/sim_worker.py [--behavior]
"""
import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.engines import config                              # noqa: E402
from core.extractor import get_extractor                     # noqa: E402
from core.inference import infer_batch, infer_with_behavior  # noqa: E402
from scripts.build_worker_dataset import PERSONAS            # noqa: E402

SID = "worker-v3"
N_INTENTS = len(config.get_taxonomy(SID)["intents"])


def _sample_answers(answer_dist: dict, rng: random.Random) -> dict[str, str]:
    return {qid: rng.choices(list(d), weights=list(d.values()), k=1)[0] for qid, d in answer_dist.items()}


def _rank_of(scores: list, intent_id: str) -> int:
    for s in scores:
        if s.intent_id == intent_id:
            return s.rank
    return 999


def run(use_behavior: bool, k: int = 40, seed: int = 7) -> None:
    """페르소나마다 k명 샘플링 → cov@3/cov@5·avg_rank(/9) 평균."""
    ext = get_extractor()
    rng = random.Random(seed)
    p3, p5, rank_all = [], [], []
    for p in PERSONAS:
        expected = p["expected_intents"]
        c3s, c5s, rks = [], [], []
        for j in range(k):
            answers = _sample_answers(p["answer_dist"], rng)
            if use_behavior:
                seq = rng.choice(p["app_seqs"])             # 단일선택 앱 entity 시퀀스
                sess = f"__w__{p['id']}_{j}"
                ext.reset(sess)
                for ent in seq:
                    ext.add_event(sess, "app_open", ent)
                _, scores = infer_with_behavior(answers, sess, SID)
                ext.reset(sess)
            else:
                _, scores = infer_batch(answers, SID)
            top = [s.intent_id for s in sorted(scores, key=lambda s: s.final_score, reverse=True)]
            t3, t5 = set(top[:3]), set(top[:5])
            c3s.append(sum(1 for e in expected if e in t3) / len(expected))
            c5s.append(sum(1 for e in expected if e in t5) / len(expected))
            rks.extend(_rank_of(scores, e) for e in expected)
        cov3, cov5 = sum(c3s) / k, sum(c5s) / k
        p3.append(cov3); p5.append(cov5); rank_all.extend(rks)
        print(f"   {p['id']} {p['name'][:24]:24} cov@3={cov3:.2f} cov@5={cov5:.2f} "
              f"avg_rank={sum(rks)/len(rks):4.1f} (exp={expected})")
    n = len(PERSONAS)
    print("=" * 70)
    print(f"  전체 평균  cov@3={sum(p3)/n:.3f}  cov@5={sum(p5)/n:.3f}  "
          f"avg_rank={sum(rank_all)/len(rank_all):.2f}/{N_INTENTS}  "
          f"({'행동반영' if use_behavior else '설문만'}, k={k})")
    print("=" * 70)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--behavior", action="store_true")
    args = ap.parse_args()
    run(args.behavior)
