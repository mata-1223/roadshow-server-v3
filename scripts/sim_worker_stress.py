from __future__ import annotations
"""
직장인(worker-v3) 대규모 랜덤 스트레스 시뮬레이션 — 의도 변화 적절성·이상 케이스 탐지.

worker는 single-select(앱 app_open). intent 9개라 반응성은 top-3 기준.
진행바 /tmp/worker_sim_progress.txt, 요약 stdout, 상세 /tmp/worker_sim_report.json.

탐지: E1 범위/NaN, E3 상위 동점, E4 행동반응(top-3), E5 stuck + 분포건전성/앱별 반응률.
(E2 범용 intent 누출은 worker에 범용 intent 없어 N/A)
"""
import json, random, sys, time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.engines import config                              # noqa: E402
from core.extractor import get_extractor                     # noqa: E402
from core.inference import infer_batch, infer_with_behavior  # noqa: E402

SID = "worker-v3"
N_SURVEY = 50_000
N_SESS = 8_000
MAX_ACT = 30
STUCK_N = 15
TOPK_RESP = 3            # 9 intent → top-3 기준 반응성
PROG = "/tmp/worker_sim_progress.txt"
REPORT = "/tmp/worker_sim_report.json"

tax = config.get_taxonomy(SID)["intents"]
NM = {i["id"]: i["name"] for i in tax}
SURVEY = config.get_survey(SID)["questions"]
OPTS = {q["id"]: [o["code"] for o in q["options"]] for q in SURVEY}
SIG = config.get_behavior_signals(SID)
APPS = config.get_behaviors(SID)["apps"]


def _bar(frac, label):
    n = int(frac * 30)
    with open(PROG, "w") as f:
        f.write(f"[{'#'*n}{'.'*(30-n)}] {frac*100:5.1f}%  {label}")


def _rand_survey(rng):
    return {q: rng.choice(OPTS[q]) for q in OPTS}


def _top(scores, k):
    return sorted(scores, key=lambda s: s.final_score, reverse=True)[:k]


def _check_common(scores, anom, tag):
    for s in scores:
        v = s.final_score
        if v != v or v < -1e-9 or v > 1.0001:
            anom["E1"].append((tag, s.intent_id, v)); break
    top = _top(scores, 5)
    top_ids = [s.intent_id for s in top]
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
    top1_survey = Counter()
    for i in range(N_SURVEY):
        a = _rand_survey(rng)
        try:
            _, sc = infer_batch(a, SID)
        except Exception as e:
            anom["E1"].append(("survey", "EXCEPTION", str(e)[:80])); continue
        top1_survey[_check_common(sc, anom, "survey")[0]] += 1
        if i % 1000 == 0:
            _bar(i / (N_SURVEY + N_SESS), f"설문 {i:,}/{N_SURVEY:,}")
    app_rise = defaultdict(lambda: [0, 0])
    stuck_runs = []
    for j in range(N_SESS):
        a = _rand_survey(rng)
        sess = f"__ws_{j}"
        ext.reset(sess)
        last_top1 = None; run_len = 0; max_run = 0
        for _ in range(rng.randint(5, MAX_ACT)):
            app = rng.choice(APPS)
            en = app["entity"]
            ext.add_event(sess, app.get("event_type", "app_open"), en)
            try:
                _, sc = infer_with_behavior(a, sess, SID)
            except Exception as e:
                anom["E1"].append((f"beh_{j}", "EXCEPTION", str(e)[:80])); break
            top_ids = _check_common(sc, anom, f"beh_{j}")
            targets = SIG.get(en, [])
            if targets:
                app_rise[en][1] += 1
                if set(targets) & set([s.intent_id for s in _top(sc, TOPK_RESP)]):
                    app_rise[en][0] += 1
            if top_ids[0] == last_top1:
                run_len += 1; max_run = max(max_run, run_len)
            else:
                last_top1 = top_ids[0]; run_len = 1
        if max_run >= STUCK_N:
            stuck_runs.append((f"beh_{j}", last_top1, max_run))
        ext.reset(sess)
        if j % 100 == 0:
            _bar((N_SURVEY + j) / (N_SURVEY + N_SESS), f"행동 {j:,}/{N_SESS:,}")
    _bar(1.0, "완료")
    dt = time.time() - t0

    n = sum(top1_survey.values())
    hhi = sum((c / n) ** 2 for c in top1_survey.values()) if n else 0
    low = {e: f"{v[0]}/{v[1]}={v[0]/v[1]*100:.0f}%" for e, v in app_rise.items() if v[1] and v[0]/v[1] < 0.9}
    summary = {
        "elapsed_sec": round(dt, 1), "n_survey": N_SURVEY, "n_sess": N_SESS, "topk_resp": TOPK_RESP,
        "E1_range_nan": len(anom["E1"]), "E3_top_tie(>=3)": len(anom["E3"]),
        "E5_stuck(>=%d)" % STUCK_N: len(stuck_runs),
        "survey_top1_distinct": len(top1_survey), "survey_top1_HHI": round(hhi, 4),
        "survey_top1": [(NM[i][:16], f"{c/n*100:.1f}%") for i, c in top1_survey.most_common()],
        "app_low_responsiveness(<90%)": low,
        "stuck_samples": stuck_runs[:10], "E3_samples": anom["E3"][:5], "E1_samples": anom["E1"][:5],
    }
    json.dump({"summary": summary, "anom_E1": anom["E1"][:200],
               "anom_E3": anom["E3"][:300], "stuck": stuck_runs[:300]},
              open(REPORT, "w"), ensure_ascii=False, indent=1)

    print("=" * 64)
    print(f"직장인 스트레스 시뮬 완료 — {dt/60:.1f}분 (설문 {N_SURVEY:,} + 행동 {N_SESS:,}×≤{MAX_ACT})")
    print("=" * 64)
    print(f"  [E1] 범위/NaN/예외      : {len(anom['E1'])} 건")
    print(f"  [E3] 상위 동점(≥3)      : {len(anom['E3'])} 건")
    print(f"  [E5] stuck(top1 ≥{STUCK_N}연속): {len(stuck_runs)} 세션")
    print(f"  설문 top-1 다양성: {len(top1_survey)}/9종, HHI={hhi:.3f}")
    print("  설문 top-1: " + ", ".join(f"{NM[i][:8]} {c/n*100:.0f}%" for i, c in top1_survey.most_common(6)))
    print(f"  앱 반응률(<90%, top-{TOPK_RESP}): {low if low else '없음 ✓'}")
    if stuck_runs:
        print("  stuck 샘플:", [(NM[s[1]][:10], s[2]) for s in stuck_runs[:5]])
    print(f"\n상세: {REPORT}")


if __name__ == "__main__":
    run()
