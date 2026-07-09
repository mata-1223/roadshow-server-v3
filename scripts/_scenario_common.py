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


# 한 노드를 인라인(한 줄)으로 유지할 최대 폭. 초과하면 자식별로 펼친다.
# worker-v3/engine/L1_feature.json의 "항 단위 인라인" 손맛을 자동 재현하는 기준.
_INLINE_WIDTH = 100


def compact_json(data, *, indent: int = 2, width: int = _INLINE_WIDTH) -> str:
    """
    "항(leaf) 단위 인라인" JSON 직렬화.

    표준 indent=2는 작은 배열·leaf 객체까지 한 원소씩 펼쳐 수식 파악이 어렵다.
    이 포매터는 노드를 먼저 한 줄(json.dumps)로 만들어보고, width 이하면 인라인 유지,
    초과하면 dict/list의 자식별로 줄바꿈 펼친다. → terms/steps/rule 맵 같은 구조는
    항당 한 줄, linear[1,0]·작은 leaf 객체는 한 줄로 모인다. (값은 표준과 1:1 동일)
    """
    def fmt(node, level: int) -> str:
        pad = " " * (indent * level)
        child_pad = " " * (indent * (level + 1))

        # 인라인 후보: 한 줄로 합쳤을 때 폭 이하면 그대로 사용 (스칼라는 항상 인라인)
        inline = json.dumps(node, ensure_ascii=False, separators=(", ", ": "))
        if not isinstance(node, (dict, list)) or len(pad) + len(inline) <= width:
            return inline

        if isinstance(node, dict):
            if not node:
                return "{}"
            items = [f'{child_pad}{json.dumps(k, ensure_ascii=False)}: {fmt(v, level + 1)}'
                     for k, v in node.items()]
            return "{\n" + ",\n".join(items) + "\n" + pad + "}"

        # list
        if not node:
            return "[]"
        items = [child_pad + fmt(v, level + 1) for v in node]
        return "[\n" + ",\n".join(items) + "\n" + pad + "]"

    return fmt(data, 0)


def dump_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(compact_json(data) + "\n", encoding="utf-8")
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
