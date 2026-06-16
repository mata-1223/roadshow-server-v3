from __future__ import annotations
"""
결합(bundle-v3) off-persona 강건성 검증.

페르소나에 매이지 않은 무작위/임의 설문 응답에서도
  A. 초기 분포가 응답(프로필)을 합리적으로 반영하는가
  B. 각 행동이 그 행동의 관련 intent를 끌어올리는가 (의도 변화의 해석가능성)
를 정량·정성으로 확인한다.

실행: python scripts/sim_offpersona.py
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.engines import config, get_engine                  # noqa: E402
from core.extractor import get_extractor                     # noqa: E402
from core.inference import infer_batch, infer_with_behavior  # noqa: E402
from scripts.sim_bundle import _behavior_map, _intent_names, _rank_of, SID  # noqa: E402


def _random_answers(rng: random.Random) -> dict[str, str]:
    """모든 문항을 옵션 중 균등 무작위로 (페르소나 무관)."""
    survey = config.get_survey(SID)
    out = {}
    for q in survey["questions"]:
        out[q["id"]] = rng.choice([o["code"] for o in q["options"]])
    return out


def _rank(scores, iid: str) -> int:
    return _rank_of(scores, iid)


# ── B. 행동 응답성: 무작위 프로필 × 무작위 단일 행동 ─────────────
def behavior_responsiveness(k: int = 300, seed: int = 11) -> None:
    rng = random.Random(seed)
    bmap = _behavior_map()
    sig = config.get_behavior_signals(SID)
    # 신호를 가진 entity만 (back/exit 제외)
    actable = [(bid, et, en) for bid, (et, en) in bmap.items()
               if sig.get(en) and et not in ("navigate_back", "app_exit")]
    ext = get_extractor()

    rose, in_top5, total = 0, 0, 0
    for i in range(k):
        ans = _random_answers(rng)
        bid, et, en = rng.choice(actable)
        targets = sig[en]
        sess = f"__off_{i}"
        ext.reset(sess)
        ext.add_event(sess, et, en)
        _, scores = infer_with_behavior(ans, sess, SID)
        ext.reset(sess)
        smap = {s.intent_id: s for s in scores}
        for t in targets:
            s = smap.get(t)
            if s is None:
                continue
            total += 1
            if s.rank_change > 0:      # baseline 대비 순위 상승
                rose += 1
            if s.rank <= 5:
                in_top5 += 1
    print("── B. 행동 응답성 (무작위 프로필 × 무작위 행동, k=%d) ──" % k)
    print(f"   클릭한 행동의 관련 intent가 baseline 대비 순위 상승: {rose/total*100:.1f}%")
    print(f"   클릭 후 그 intent가 Top-5 진입:                    {in_top5/total*100:.1f}%")


# ── A. 초기 분포의 프로필 반영 (대조 프로필) ────────────────────
def initial_reflects_profile() -> None:
    names = _intent_names()
    eng = get_engine(SID)
    # 의도적으로 대조되는 임의 프로필 (페르소나 정의 아님)
    profiles = {
        "약정만료+품질불만(이탈징후)": {"Q1":"A","Q2":"D","Q3":"C","Q4":"A","Q5":"C","Q6":"A","Q7":"C","Q8":"C","Q9":"D","Q10":"A","Q11":"C","Q12":"A"},
        "결합미보유+가족多(확장여지)": {"Q1":"B","Q2":"B","Q3":"C","Q4":"C","Q5":"A","Q6":"C","Q7":"A","Q8":"A","Q9":"B","Q10":"B","Q11":"F","Q12":"C"},
        "혜택애호+프리미엄(VIP)":     {"Q1":"A","Q2":"C","Q3":"D","Q4":"B","Q5":"C","Q6":"A","Q7":"C","Q8":"B","Q9":"D","Q10":"C","Q11":"F","Q12":"C"},
        "저가+비용민감":              {"Q1":"B","Q2":"B","Q3":"A","Q4":"A","Q5":"A","Q6":"A","Q7":"B","Q8":"A","Q9":"A","Q10":"A","Q11":"A","Q12":"D"},
    }
    print("\n── A. 초기 분포의 프로필 반영 (임의 대조 프로필) ──")
    for label, ans in profiles.items():
        _, scores = infer_batch(ans, SID)
        top = sorted(scores, key=lambda s: s.final_score, reverse=True)[:5]
        print(f"   [{label}]  Top-5: " + ", ".join(f"{s.intent_id} {names[s.intent_id][:12]}" for s in top))


# ── B2. 단일 임의 프로필의 행동별 변화 walkthrough ──────────────
def walkthrough() -> None:
    names = _intent_names()
    bmap = _behavior_map()
    sig = config.get_behavior_signals(SID)
    ext = get_extractor()
    ans = {"Q1":"A","Q2":"C","Q3":"C","Q4":"B","Q5":"B","Q6":"A","Q7":"B","Q8":"B","Q9":"C","Q10":"B","Q11":"F","Q12":"C"}  # 중립적 임의
    seq = ["1-B", "2-B1", "1-C", "2-C2", "1-D", "2-D3"]  # 결합조회→가족결합→홈탐색→IPTV→약정→재약정혜택
    print("\n── B2. 임의 프로필 행동 walkthrough (행동마다 상승 intent) ──")
    _, base = infer_batch(ans, SID)
    base_rank = {s.intent_id: s.rank for s in base}
    sess = "__walk"; ext.reset(sess)
    for bid in seq:
        et, en = bmap.get(bid, (None, None))
        if not et:
            continue
        ext.add_event(sess, et, en)
        _, sc = infer_with_behavior(ans, sess, SID)
        risers = sorted(sc, key=lambda s: s.rank_change, reverse=True)[:3]
        tgt = sig.get(en, [])
        print(f"   click {bid}({en}) → 신호={tgt}")
        print("      최대 상승: " + ", ".join(f"{s.intent_id} {names[s.intent_id][:10]}(↑{s.rank_change},#{s.rank})" for s in risers))
    ext.reset(sess)


if __name__ == "__main__":
    behavior_responsiveness()
    initial_reflects_profile()
    walkthrough()
