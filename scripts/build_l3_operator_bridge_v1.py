#!/usr/bin/env python3
"""Build the frozen L3→QGIS-operator bridge for qgis-planner-benchmark v0.2.1 evaluation.

M1 and M3 both emit L3 chains; the benchmark prediction contract requires
parameter-free QGIS operator ids. The bridge maps each L3 code to exactly one
deterministic representative operator from the benchmark's own mapping
authority, restricted to operators admitted for evaluation (headline_core tier).

Deterministic rule (frozen):
  candidates(l3) = {e : e.stable101_l3 == l3 AND e.operator_admission_tier
                        == 'headline_core'}
  bridge(l3)     = argmax over candidates by (frequency desc, operator_id asc)

Model-emitted L3 codes with no headline_core operator are dropped from the
prediction (they cannot legally enter the benchmark operator universe) and the
drop rate is recorded as a diagnostic, never silently.

Output: docs/reports/qgis_planner_eval_v1/bridge/l3_operator_bridge_v1.json
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY = ROOT / "benchmarks/qgis_planner_v1/authority/qgis_operator_l3_mapping.json"
VOCAB = ROOT / "docs/reports/paper_v1_profile_v1/id_mappings_paper_v1_128.json"
OUT = ROOT / "docs/reports/qgis_planner_eval_v1/bridge/l3_operator_bridge_v1.json"


def main() -> int:
    mapping = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    vocab = json.loads(VOCAB.read_text(encoding="utf-8"))
    vocab_codes = set(vocab["l3"])

    from collections import defaultdict
    by_l3: dict[str, list[dict]] = defaultdict(list)
    for e in mapping["entries"]:
        if e.get("stable101_l3") and e.get("operator_admission_tier") == "headline_core":
            by_l3[e["stable101_l3"]].append(e)

    bridge: dict[str, dict] = {}
    for l3, entries in sorted(by_l3.items()):
        entries.sort(key=lambda e: (-e.get("frequency", 0), e["operator_id"]))
        best = entries[0]
        bridge[l3] = {
            "operator_id": best["operator_id"],
            "frequency": best.get("frequency", 0),
            "n_candidates": len(entries),
        }

    # Assertions — fail closed.
    assert len(bridge) == 50, f"expected 50 headline_core L3 codes, got {len(bridge)}"
    outside = sorted(set(bridge) - vocab_codes)
    assert not outside, f"bridge codes outside paper_v1_128 vocab: {outside}"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "schema": "gis_recommend.qgis_planner_l3_operator_bridge.v1",
        "rule": "headline_core tier; max frequency; operator_id lexicographic tie-break",
        "authority": "benchmarks/qgis_planner_v1/authority/qgis_operator_l3_mapping.json",
        "l3_to_operator": bridge,
        "stats": {
            "bridge_size": len(bridge),
            "multi_candidate_codes": sum(1 for v in bridge.values() if v["n_candidates"] > 1),
            "paper_v1_128_vocab_size": len(vocab_codes),
            "vocab_codes_without_bridge": len(vocab_codes - set(bridge)),
        },
        "unmapped_policy": "drop from prediction; record drop rate as diagnostic",
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    stats = json.loads(OUT.read_text(encoding="utf-8"))["stats"]
    print(json.dumps(stats, indent=2))
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
