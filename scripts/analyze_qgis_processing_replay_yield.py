"""Summarize where the full Processing replay can still yield candidates.

This is a routing census only. It does not promote deferred rows or emit
training data.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def read(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def analyze(rows: list[dict[str, Any]]) -> dict[str, Any]:
    actions = Counter(str(row.get("action") or "unspecified") for row in rows)
    lanes: dict[str, dict[str, Any]] = {}
    for action in sorted(actions):
        subset = [row for row in rows if str(row.get("action") or "unspecified") == action]
        mapped = [row for row in subset if row.get("mapped_l3_chain")]
        ops = [row for row in subset if row.get("ordered_operator_ids")]
        calls = [row for row in subset if row.get("call_sites")]
        lanes[action] = {
            "rows": len(subset),
            "mapped_l3_chain_rows": len(mapped),
            "operator_sequence_rows": len(ops),
            "call_site_rows": len(calls),
            "workflow_unit_scope": dict(Counter(str(row.get("workflow_unit_scope") or "unspecified") for row in subset)),
            "description_requirement": dict(Counter(str(row.get("description_requirement") or "unspecified") for row in subset)),
            "structure_class": dict(Counter(str(row.get("structure_class") or "unspecified") for row in subset)),
        }
    return {
        "schema": "gis_recommend.qgis_processing_replay_yield.v1",
        "input_rows": len(rows),
        "action_counts": dict(actions),
        "lanes": lanes,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_replay_yield_census",
        "next_priority": [
            "review_api_sidecar",
            "recover_call_graph",
            "defer_mapping_rows_with_mapped_l3_chain",
            "remaining_defer_mapping_no_candidate_calls",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(read(args.replay))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"input_rows": result["input_rows"], "lanes": len(result["lanes"]), "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
