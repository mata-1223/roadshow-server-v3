from __future__ import annotations
"""
GenericEngine — config-driven 단일 시나리오 엔진 (Phase 4 수렴).

cs/bundle/worker 전용 엔진을 대체. 모든 시나리오 차이는 config(input/L0~L3 JSON)에 있고,
이 엔진은 sid로 config를 읽어 공통 메커니즘(extract/formula/common/models predictive_model)에 위임만 한다.

  L1 batch_builder : extract.survey_base + run_batch_builder (불규칙은 batch_builder.pre_hook 격리)
  L1 pattern/event : extract.pattern_from_spec / event_from_spec
  L2 rule          : formula.rule_predict
  L2 model         : models.get_predictive_model(config.model.predictive_model)로 구현 해결 →
                     heuristic_fallback 면 common.model_predict, 아니면 predictive_model.predict 직접
"""
from pathlib import Path
from typing import Any

import models
from core.engines import config, common, extract, formula
from core.engines.base import ScenarioEngine
from core.extractor import get_extractor

_SCENARIOS = Path(__file__).parent.parent.parent / "scenarios"


class GenericEngine(ScenarioEngine):

    def __init__(self, scenario_id: str):
        """seed_dataset 경로·MLflow 모델 prefix를 sid로 결정."""
        super().__init__(scenario_id)
        self._dataset_path = _SCENARIOS / scenario_id / "seed_dataset.json"
        self._model_prefix = f"{scenario_id}__"

    # ── [1a] Batch ────────────────────────────────────────────
    def build_batch_features(self, answers: dict[str, str]) -> dict[str, Any]:
        """설문 → Base + L1.batch_builder(선언형) 파생 → Batch Feature."""
        base = extract.survey_base(config.get_survey(self.scenario_id), answers)
        return extract.run_batch_builder(base, config.get_batch_builder(self.scenario_id))

    # ── [1c] Pattern / [1b] Event ─────────────────────────────
    def empty_pattern_features(self) -> dict[str, Any]:
        """행동 없음 상태의 Pattern Feature (pattern spec 기준 0/빈값)."""
        return extract.pattern_from_spec([], config.get_pattern_spec(self.scenario_id))

    def pattern_features(self, session_id: str) -> dict[str, Any]:
        """세션의 윈도우 내 이벤트 → L1.pattern spec으로 Pattern Feature."""
        spec = config.get_pattern_spec(self.scenario_id)
        events = get_extractor().events_within(session_id, window_seconds=spec.get("window_seconds", 300))
        return extract.pattern_from_spec(extract._filter(events, spec.get("filter")), spec)

    def empty_event_features(self) -> dict[str, Any]:
        """행동 없음 상태의 Event Feature (event spec 기준 0/빈값)."""
        return extract.event_from_spec(None, config.get_event_spec(self.scenario_id))

    def event_features(self, session_id: str) -> dict[str, Any]:
        """세션 최신 이벤트 → L1.event spec으로 Event Feature."""
        events = get_extractor()._events_by_session.get(session_id, [])
        last = events[-1] if events else None
        return extract.event_from_spec(last, config.get_event_spec(self.scenario_id))

    # ── [2a] Rule / [2b] Model ────────────────────────────────
    def rule_predict(self, intent_id: str, features: dict[str, Any]) -> float:
        """L2.rule 선언형 spec 평가 → Rule Intent 점수(0~1)."""
        return formula.rule_predict(config.get_rule_spec(self.scenario_id), intent_id, features)

    def model_predict(self, intent_id: str, features: dict[str, Any]) -> float:
        """L2.model spec의 predictive_model로 추론. heuristic_fallback이면 휴리스틱 폴백 포함."""
        m = config.get_model_spec(self.scenario_id)
        predictive_model = models.get_predictive_model(m.get("predictive_model", "sklearn"))  # sklearn/torch… config 선택
        training_data = m.get("training_data", {})
        train_params = m.get("train")     # 학습 하이퍼파라미터(class_weight/C), 없으면 backend 기본
        if m.get("heuristic_fallback"):
            invert = frozenset(tuple(x) for x in m.get("invert", []))
            return common.model_predict(
                intent_id, features,
                predictive_model=predictive_model,
                training_data=training_data,
                dataset_path=self._dataset_path,
                model_prefix=self._model_prefix,
                ranges=m.get("ranges", {}), scale=m.get("scale", 0.5), invert=invert,
                train_params=train_params,
            )
        # 휴리스틱 폴백 없이 predictive_model 직접 (cs: 충분한 학습 데이터)
        return predictive_model.predict(
            intent_id, features,
            training_data=training_data,
            dataset_path=self._dataset_path,
            model_prefix=self._model_prefix,
            train_params=train_params,
        )
