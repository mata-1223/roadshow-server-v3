from __future__ import annotations
"""
CS(cs-myk-v3) 대규모 랜덤 스트레스 시뮬레이션 — 의도 변화 적절성·이상 케이스 탐지.

- 설문: 무작위 N_SURVEY건 (전수 1,870만은 불가 → 대규모 샘플)
- 행동: N_SESS 세션 × 세션당 최대 MAX_ACT 클릭 (클릭 기반 윈도우 가정)
- 진행바는 /tmp/cs_sim_progress.txt 에 in-place 기록 (tail -f 로 관람)
- 요약은 stdout, 상세는 /tmp/cs_sim_report.json

탐지 이상:
  E1 범위/NaN (score∉[0,1])
  E2 범용 intent(AI추천류) top-5 누출
  E3 상위 동점 (top-1과 동률이 top-5 내 3개 이상)
  E4 행동 무반응 (클릭 entity의 신호 intent가 top-10에도 못 듦)
  E5 stuck (top-1이 ≥STUCK_N 연속 고정)
  + 분포 건전성(top-1 다양성/HHI), entity별 반응률
"""
import json, random, sys, time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.engines import config                              # noqa: E402
from core.extractor import get_extractor                     # noqa: E402
from core.inference import infer_batch, infer_with_behavior  # noqa: E402

SID = "cs-myk-v3"
N_SURVEY = 50_000
N_SESS = 15_000
MAX_ACT = 30
STUCK_N = 15
GENERIC = {"INT-4310", "INT-4320", "INT-4330"}
PROG = "/tmp/cs_sim_progress.txt"
REPORT = "/tmp/cs_sim_report.json"

tax = config.get_taxonomy(SID)["intents"]
NM = {i["id"]: i["name"] for i in tax}
SURVEY = config.get_survey(SID)["questions"]
OPTS = {q["id"]: [o["code"] for o in q["options"]] for q in SURVEY}
SIG = config.get_behavior_signals(SID)

# 행동 트리
_bc = config.get_behaviors(SID)
STEP1 = [(b["event_type"], b["entity"], b["id"]) for b in _bc["step1"]["behaviors"]]
STEP2 = {}
for parent, items in _bc["step2"]["by_parent"].items():
    STEP2[parent] = [(b["event_type"], b["entity"], b["id"]) for b in items]


def _bar(frac, label):
    n = int(frac * 30)
    with open(PROG, "w") as f:
        f.write(f"[{'#'*n}{'.'*(30-n)}] {frac*100:5.1f}%  {label}")


def _rand_survey(rng):
    return {q: rng.choice(OPTS[q]) for q in OPTS}


def _top(scores, k):
    return sorted(scores, key=lambda s: s.final_score, reverse=True)[:k]


def _check_common(scores, anom, tag):
    # E1 범위/NaN
    for s in scores:
        v = s.final_score
        if v != v or v < -1e-9 or v > 1.0001:
            anom["E1"].append((tag, s.intent_id, v)); break
    top = _top(scores, 5)
    top_ids = [s.intent_id for s in top]
    # E2 범용 누출
    g = GENERIC & set(top_ids)
    if g:
        anom["E2"].append((tag, list(g)))
    # E3 상위 동점
    tv = round(top[0].final_score, 2)
    tie = sum(1 for s in top if round(s.final_score, 2) == tv)
    if tie >= 3:
        anom["E3"].append((tag, tv, tie, top_ids[:tie]))
    return top_ids


def run():
    ext = get_extractor()
    rng = random.Random(20240601)
    t0 = time.time()
    anom = defaultdict(list)
    # 설문 sweep
    top1_survey = Counter()
    for i in range(N_SURVEY):
        a = _rand_survey(rng)
        try:
            _, sc = infer_batch(a, SID)
        except Exception as e:
            anom["E1"].append(("survey", "EXCEPTION", str(e)[:80])); continue
        top_ids = _check_common(sc, anom, "survey")
        top1_survey[top_ids[0]] += 1
        if i % 500 == 0:
            _bar(i / (N_SURVEY + N_SESS), f"설문 {i:,}/{N_SURVEY:,}")
    # 행동 sweep
    ent_rise = defaultdict(lambda: [0, 0])   # entity → [신호상승, 시도]
    stuck_runs = []
    top1_beh = Counter()
    for j in range(N_SESS):
        a = _rand_survey(rng)
        sess = f"__st_{j}"
        ext.reset(sess)
        cur_parent = None
        last_top1 = None; run_len = 0; max_run = 0
        n_act = rng.randint(5, MAX_ACT)
        for _ in range(n_act):
            # 트리 네비게이션
            r = rng.random()
            if cur_parent is None or r < 0.35:
                et, en, bid = rng.choice(STEP1); cur_parent = bid
            elif r < 0.5 and cur_parent:
                cur_parent = None; ext.add_event(sess, "navigate_back", "back_to_step1"); continue
            else:
                items = STEP2.get(cur_parent) or STEP1
                et, en, bid = rng.choice(items)
            ext.add_event(sess, et, en)
            try:
                _, sc = infer_with_behavior(a, sess, SID)
            except Exception as e:
                anom["E1"].append((f"beh_{j}", "EXCEPTION", str(e)[:80])); break
            top_ids = _check_common(sc, anom, f"beh_{j}")
            # E4 반응성 (신호 entity가 top-10에)
            targets = SIG.get(en, [])
            if targets:
                ent_rise[en][1] += 1
                if set(targets) & set([s.intent_id for s in _top(sc, 10)]):
                    ent_rise[en][0] += 1
            # E5 stuck
            if top_ids[0] == last_top1:
                run_len += 1; max_run = max(max_run, run_len)
            else:
                last_top1 = top_ids[0]; run_len = 1
            top1_beh[top_ids[0]] += 1
        if max_run >= STUCK_N:
            stuck_runs.append((f"beh_{j}", last_top1, max_run))
        ext.reset(sess)
        if j % 150 == 0:
            _bar((N_SURVEY + j) / (N_SURVEY + N_SESS), f"행동 {j:,}/{N_SESS:,}")
    _bar(1.0, "완료")
    dt = time.time() - t0

    # ── 집계/요약 ──
    n_surv_top1 = sum(top1_survey.values())
    hhi = sum((c / n_surv_top1) ** 2 for c in top1_survey.values()) if n_surv_top1 else 0
    low_ent = {e: f"{v[0]}/{v[1]}={v[0]/v[1]*100:.0f}%" for e, v in ent_rise.items() if v[1] and v[0]/v[1] < 0.9}
    summary = {
        "elapsed_sec": round(dt, 1),
        "n_survey": N_SURVEY, "n_sess": N_SESS, "max_act": MAX_ACT,
        "E1_range_nan": len(anom["E1"]),
        "E2_generic_leak": len(anom["E2"]),
        "E3_top_tie(>=3)": len(anom["E3"]),
        "E5_stuck(>=%d)" % STUCK_N: len(stuck_runs),
        "survey_top1_distinct": len(top1_survey),
        "survey_top1_HHI": round(hhi, 4),
        "survey_top1_top8": [(NM[i][:14], f"{c/n_surv_top1*100:.1f}%") for i, c in top1_survey.most_common(8)],
        "entity_low_responsiveness(<90%)": low_ent,
        "stuck_samples": stuck_runs[:10],
        "E1_samples": anom["E1"][:5],
        "E2_samples": anom["E2"][:5],
        "E3_samples": anom["E3"][:5],
    }
    json.dump({"summary": summary,
               "anom_E1": anom["E1"][:200], "anom_E2": anom["E2"][:200],
               "anom_E3": anom["E3"][:200], "stuck": stuck_runs[:200]},
              open(REPORT, "w"), ensure_ascii=False, indent=1)

    print("=" * 64)
    print(f"CS 스트레스 시뮬 완료 — {dt/60:.1f}분 (설문 {N_SURVEY:,} + 행동 {N_SESS:,}×≤{MAX_ACT})")
    print("=" * 64)
    print(f"  [E1] 범위/NaN/예외      : {len(anom['E1'])} 건")
    print(f"  [E2] 범용 intent 누출   : {len(anom['E2'])} 건")
    print(f"  [E3] 상위 동점(≥3)      : {len(anom['E3'])} 건")
    print(f"  [E5] stuck(top1 ≥{STUCK_N}연속): {len(stuck_runs)} 세션")
    print(f"  설문 top-1 다양성: {len(top1_survey)}종, HHI={hhi:.3f}")
    print(f"  설문 top-1 최빈: " + ", ".join(f"{NM[i][:10]} {c/n_surv_top1*100:.0f}%" for i, c in top1_survey.most_common(5)))
    print(f"  행동 반응률<90% entity: {low_ent if low_ent else '없음 ✓'}")
    if stuck_runs:
        print("  stuck 샘플:", [(s[1], s[2]) for s in stuck_runs[:5]])
    print(f"\n상세 리포트: {REPORT}")


if __name__ == "__main__":
    run()
