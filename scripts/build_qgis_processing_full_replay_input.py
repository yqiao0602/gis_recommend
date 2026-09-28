#!/usr/bin/env python3
"""Join the 8,466 source authority rows with existing replay evidence.

This is a replay input artifact only.  It never infers an L3 mapping for a
record that is absent from the reviewed replay ledger.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build(source_manifest: Path, prior_replay: Path, output: Path) -> dict[str, Any]:
    sources = _read(source_manifest)
    prior = _read(prior_replay)
    by_id = {str(row.get("record_id")): row for row in prior}
    if len(by_id) != len(prior):
        raise ValueError("prior replay contains duplicate record IDs")
    result: list[dict[str, Any]] = []
    inherited = 0
    for source in sources:
        record_id = str(source["record_id"])
        evidence = by_id.get(record_id, {})
        row = {
            "schema": "gis_recommend.qgis_processing_full_replay_input.v1",
            "record_id": record_id,
            "source_root_id": source.get("source_root_id", ""),
            "source_path": source["source_path"],
            "source_sha256": source["source_sha256"],
            "ordered_operator_ids": evidence.get("ordered_operator_ids") or source.get("operator_evidence") or [],
            "operator_ids": evidence.get("operator_ids") or source.get("operator_evidence") or [],
            "mapped_l3_chain": evidence.get("mapped_l3_chain") or [],
            "prior_action": evidence.get("action", "not_in_prior_replay"),
            "prior_mapping_authority": evidence.get("mapping_authority", ""),
            "training_admission": "not_granted",
            "training_row_emitted": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "llm_called": False,
        }
        # The route layer evaluates all literal calls itself.  Overlay call
        # sites are recovery-layer spans the route extractor cannot align, and
        # an explicit empty list would select zero operators; so no call_sites
        # field is written and the extractor takes its all-literal-calls path.
        if evidence.get("call_sites"):
            inherited += 1
        result.append(row)
    result.sort(key=lambda row: row["record_id"])
    if len(result) != 8466 or len({row["record_id"] for row in result}) != 8466:
        raise ValueError("full replay input must contain 8,466 unique records")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in result), encoding="utf-8")
    return {
        "schema": "gis_recommend.qgis_processing_full_replay_input_summary.v1",
        "input_rows": len(result),
        "prior_replay_rows": len(prior),
        "rows_with_verified_call_spans": inherited,
        "rows_without_prior_mapping": sum(not row["mapped_l3_chain"] for row in result),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_replay_input_only",
        "production_merge": "not_granted",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--prior-replay", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source_manifest, args.prior_replay, args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
