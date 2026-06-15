#!/usr/bin/env python3
"""
시나리오 생성기 공통 헬퍼 (레이어 파일 출력).

build_<scenario>_scenario.py가 TAX→build_intents/actions/behavior_intents로 만든 산출을
engine 레이어 파일에 기록한다. L0는 전체 교체, L3/L2는 해당 키만 교체(형제 섹션 보존).
"""
from __future__ import annotations

import json
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.load(open(path, encoding="utf-8")) if path.exists() else {}


def dump_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Wrote {path}")


def emit_layers(eng_dir: Path, *, taxonomy: dict, context_library: dict, behavior_signals: dict) -> None:
    """
    L0_taxonomy.json 전체 교체 + L3_serving.json의 context_library + L2_inference.json의
    ranker.behavior_signals 키만 교체(context_manager/action_signal/calibrator 등 형제 보존).
    """
    dump_json(eng_dir / "L0_taxonomy.json", taxonomy)

    l3 = load_json(eng_dir / "L3_serving.json")
    l3["context_library"] = context_library
    dump_json(eng_dir / "L3_serving.json", l3)

    l2 = load_json(eng_dir / "L2_inference.json")
    l2.setdefault("ranker", {})["behavior_signals"] = behavior_signals
    dump_json(eng_dir / "L2_inference.json", l2)
