from __future__ import annotations
"""
모델 워밍업 — 기동 시 전 시나리오의 Model intent를 학습·MLflow 등록(없으면).

배포 후 시나리오별 첫 설문 제출 없이도 모델이 준비되도록 한다.
멱등적: 레지스트리에 이미 있으면 load만(재학습 X) → 재시작 시 비용 거의 없음.
"""
import logging
import time

from core.engines import available_scenarios, config, get_engine

logger = logging.getLogger(__name__)


def warmup_models() -> dict[str, int]:
    """전 시나리오 Model intent를 load-or-train으로 준비. {scenario: 모델수} 반환."""
    t0 = time.time()
    result: dict[str, int] = {}
    for sid in available_scenarios():
        try:
            m = config.get_model_spec(sid)
        except (KeyError, FileNotFoundError):
            continue
        td = m.get("training_data", {})
        if not td:
            continue
        eng = get_engine(sid)
        ok = 0
        for iid in td:
            try:
                eng.model_predict(iid, {})   # _load_or_train 트리거 (없으면 학습·등록)
                ok += 1
            except Exception as e:               # noqa: BLE001 — 워밍업은 best-effort
                logger.warning("warmup %s/%s 실패: %s", sid, iid, e)
        result[sid] = ok
        logger.info("warmup %s: model intents %d개 준비", sid, ok)
    logger.info("warmup 완료 (%.1fs): %s", time.time() - t0, result)
    return result
