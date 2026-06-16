from __future__ import annotations
"""
직장인(worker-v3) 분포 건전성 + 페르소나 유사도 기반 off-persona 평가.

페르소나 기대치(expected_intents)에 의존하지 않는 보조 지표 (sim_health의 worker판).
worker 행동은 단일선택 앱(app_open + entity, app_seqs)이라 bundle의 _behavior_map이 불필요.

[A] 분포 건전성  : top-1 다양성(HHI)·정규화 엔트로피·saturation(raw>0.9)
[B] 설문 민감도  : 답변 1개 변경 시 top-k 변화(turnover)
[C] 페르소나 유사도: 페르소나 표본 self-match(분리도) + off-persona 최근접 유사도
[D] 행동 방향성  : off-persona가 '페르소나 P의 앱'을 쓰면 분포가 P 쪽으로 이동하나
[E] 행동 응답성  : 무작위 프로필 × 무작위 앱 → 그 앱의 신호 intent 순위 상승/Top-5 진입

실행: python scripts/sim_worker_health.py
"""
import math
import random
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.engines import config                              # noqa: E402
from core.extractor import get_extractor                     # noqa: E402
from core.inference import infer_batch, infer_with_behavior, to_probability_dict  # noqa: E402
from scripts.build_worker_dataset import PERSONAS            # noqa: E402

SID = "worker-v3"
_INTENTS = [i["id"] for i in config.get_taxonomy(SID)["intents"]]
_IDX = {iid: i for i, iid in enumerate(_INTENTS)}
_NAMES = {i["id"]: i.get("name", i["id"]) for i in config.get_taxonomy(SID)["intents"]}
_TOPK = min(5, len(_INTENTS))
_EXT = get_extractor()


def _rand_answers(rng: random.Random) -> dict[str, str]:
    """모든 문항을 옵션 중 균등 무작위로 (페르소나 무관)."""
    return {q["id"]: rng.choice([o["code"] for o in q["options"]])
            for q in config.get_survey(SID)["questions"]}


def _sample_answers(dist: dict, rng: random.Random) -> dict[str, str]:
    return {qid: rng.choices(list(d), weights=list(d.values()), k=1)[0] for qid, d in dist.items()}


def _apply_apps(sess: str, seq: list[str]) -> None:
    _EXT.reset(sess)
    for ent in seq:
        _EXT.add_event(sess, "app_open", ent)


def _prob_vec(answers: dict, seq: list[str] | None = None, tag: str = "") -> np.ndarray:
    """초기(seq=None) 또는 행동 반영 분포의 N-차원 확률 벡터."""
    if seq:
        sess = f"__wh_{tag}"
        _apply_apps(sess, seq)
        _, scores = infer_with_behavior(answers, sess, SID)
        _EXT.reset(sess)
    else:
        _, scores = infer_batch(answers, SID)
    v = np.zeros(len(_INTENTS))
    for iid, d in to_probability_dict(scores, scenario_id=SID).items():
        v[_IDX[iid]] = d["p"]
    return v


def _cos(a: np.ndarray, b: np.ndarray) -> float:
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))


# ── [A] 분포 건전성 ─────────────────────────────────────────────
def health(m: int = 150, seed: int = 3) -> None:
    rng = random.Random(seed)
    top1 = Counter()
    ents, sats = [], []
    for _ in range(m):
        ans = _rand_answers(rng)
        _, scores = infer_batch(ans, SID)
        v = np.zeros(len(_INTENTS))
        for iid, d in to_probability_dict(scores, scenario_id=SID).items():
            v[_IDX[iid]] = d["p"]
        top1[_INTENTS[int(np.argmax(v))]] += 1
        p = v[v > 0]
        ents.append(-(p * np.log(p)).sum() / math.log(len(_INTENTS)))
        sats.append(sum(1 for s in scores if s.final_score > 0.9) / len(scores))
    hhi = sum((c / m) ** 2 for c in top1.values())
    mc = top1.most_common(1)[0]
    print("── [A] 분포 건전성 (무작위 %d) ──" % m)
    print(f"   top-1 다양성: 서로 다른 top1 intent {len(top1)}/{len(_INTENTS)}종, HHI={hhi:.3f} "
          f"(최빈 top1 {mc[0]} {mc[1]/m*100:.0f}%)")
    print(f"   정규화 엔트로피 평균: {np.mean(ents):.3f}  (0=스파이크 1=평탄)")
    print(f"   saturation(raw>0.9) 평균: {np.mean(sats)*100:.1f}%")


# ── [B] 설문 민감도 ─────────────────────────────────────────────
def sensitivity(m: int = 60, seed: int = 5) -> None:
    rng = random.Random(seed)
    survey = config.get_survey(SID)["questions"]
    turn = []
    for _ in range(m):
        ans = _rand_answers(rng)
        _, base = infer_batch(ans, SID)
        base_top = {s.intent_id for s in sorted(base, key=lambda s: s.final_score, reverse=True)[:_TOPK]}
        q = rng.choice(survey)
        alts = [o["code"] for o in q["options"] if o["code"] != ans[q["id"]]]
        if not alts:
            continue
        a2 = dict(ans); a2[q["id"]] = rng.choice(alts)
        _, sc2 = infer_batch(a2, SID)
        top2 = {s.intent_id for s in sorted(sc2, key=lambda s: s.final_score, reverse=True)[:_TOPK]}
        jac = len(base_top & top2) / len(base_top | top2)
        turn.append(1 - jac)
    print("\n── [B] 설문 민감도 (답변 1개 변경 시 top-%d 변화) ──" % _TOPK)
    print(f"   평균 turnover: {np.mean(turn)*100:.1f}%  (0=둔감 / 100=과민, 적당한 반응성이 건전)")


# ── 페르소나 레퍼런스 벡터 ──────────────────────────────────────
def _persona_refs(k: int = 25, seed: int = 9):
    rng = random.Random(seed)
    init, beh = {}, {}
    for p in PERSONAS:
        vs_i, vs_b = [], []
        for j in range(k):
            a = _sample_answers(p["answer_dist"], rng)
            vs_i.append(_prob_vec(a))
            vs_b.append(_prob_vec(a, rng.choice(p["app_seqs"]), tag=f"{p['id']}{j}"))
        init[p["id"]] = np.mean(vs_i, axis=0)
        beh[p["id"]] = np.mean(vs_b, axis=0)
    return init, beh


# ── [C] 페르소나 유사도: 검증 + off-persona 매핑 ────────────────
def persona_similarity(init_ref: dict, k: int = 25, m: int = 120, seed: int = 13) -> None:
    rng = random.Random(seed)
    pids = [p["id"] for p in PERSONAS]
    hit = 0; tot = 0
    for p in PERSONAS:
        for _ in range(k):
            v = _prob_vec(_sample_answers(p["answer_dist"], rng))
            nearest = max(pids, key=lambda q: _cos(v, init_ref[q]))
            hit += (nearest == p["id"]); tot += 1
    print("\n── [C] 페르소나 유사도 ──")
    print(f"   검증(분리도): 페르소나 표본의 최근접=자기자신 {hit/tot*100:.1f}%")
    sims = []
    near_cnt = Counter()
    for _ in range(m):
        v = _prob_vec(_rand_answers(rng))
        scored = sorted(((q, _cos(v, init_ref[q])) for q in pids), key=lambda x: -x[1])
        sims.append(scored[0][1]); near_cnt[scored[0][0]] += 1
    print(f"   off-persona 초기분포의 최근접 페르소나 유사도: 평균 {np.mean(sims):.2f}, "
          f"중앙 {np.median(sims):.2f} (≥0.7 비율 {np.mean([s>=0.7 for s in sims])*100:.0f}%)")
    print(f"   → 임의 응답이 페르소나 공간 안에 사상됨. 최근접 분포: "
          + ", ".join(f"{q}:{near_cnt[q]}" for q in pids))


# ── [D] 행동 변화 방향성 ────────────────────────────────────────
def behavior_direction(beh_ref: dict, m: int = 80, seed: int = 21) -> None:
    rng = random.Random(seed)
    moved = 0; tot = 0
    for _ in range(m):
        ans = _rand_answers(rng)
        p = rng.choice(PERSONAS)
        v0 = _prob_vec(ans)
        v1 = _prob_vec(ans, rng.choice(p["app_seqs"]), tag=f"d{tot}")
        before = _cos(v0, beh_ref[p["id"]])
        after = _cos(v1, beh_ref[p["id"]])
        moved += (after > before); tot += 1
    print("\n── [D] 행동 변화 방향성 ──")
    print(f"   off-persona 응답이 '페르소나 P의 앱'을 쓰면 분포가 P 쪽으로 이동: {moved/tot*100:.1f}%")
    print("   (행동이 기대한 의도 변화를 만든다는 페르소나-레퍼런스 기반 검증)")


# ── [E] 행동 응답성 (무작위 프로필 × 무작위 앱) ─────────────────
def behavior_responsiveness(k: int = 300, seed: int = 11) -> None:
    rng = random.Random(seed)
    sig = config.get_behavior_signals(SID)
    apps = [en for en in sig if sig.get(en)]
    rose, in_top5, total = 0, 0, 0
    for i in range(k):
        ans = _rand_answers(rng)
        en = rng.choice(apps)
        targets = sig[en]
        sess = f"__woff_{i}"
        _apply_apps(sess, [en])
        _, scores = infer_with_behavior(ans, sess, SID)
        _EXT.reset(sess)
        smap = {s.intent_id: s for s in scores}
        for t in targets:
            s = smap.get(t)
            if s is None:
                continue
            total += 1
            rose += (s.rank_change > 0)
            in_top5 += (s.rank <= 5)
    print("\n── [E] 행동 응답성 (무작위 프로필 × 무작위 앱, k=%d) ──" % k)
    print(f"   연 앱의 신호 intent가 baseline 대비 순위 상승: {rose/total*100:.1f}%")
    print(f"   연 앱의 신호 intent가 Top-5 진입:           {in_top5/total*100:.1f}%")


if __name__ == "__main__":
    health()
    sensitivity()
    init_ref, beh_ref = _persona_refs()
    persona_similarity(init_ref)
    behavior_direction(beh_ref)
    behavior_responsiveness()
