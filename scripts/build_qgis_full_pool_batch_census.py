#!/usr/bin/env python3
"""Build a source-independent census for the full QGIS Processing pool.

This command combines the authoritative 8,466-row resolution census with the
latest L3 replay summary.  It deliberately does not emit training rows: the
full source replay may be unavailable locally, so this artifact reports the
batch gate and keeps every admission closed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_census(resolution: dict[str, Any], l3_gate: dict[str, Any]) -> dict[str, Any]:
    expected = 8466
    observed = int(resolution.get("input_processing_resolution_records", 0))
    if observed != expected or int(resolution.get("verified_source_records", 0)) != expected:
        raise ValueError(f"resolution census is not the 8,466-row authority: {observed}")
    actions = l3_gate.get("action_counts", {})
    return {
        "schema": "gis_recommend.qgis_full_pool_batch_census.v1",
        "input_rows": expected,
        "verified_source_rows": int(resolution["verified_source_records"]),
        "primary_layers": resolution.get("primary_layer_counts", {}),
        "recovery_opportunities": resolution.get("recovery_opportunity_records", {}),
        "latest_replay": {
            "input_rows": int(l3_gate.get("input_rows", 0)),
            "mapping_complete_rows": int(l3_gate.get("mapping_complete_rows", 0)),
            "mapping_complete_unique_chains": int(l3_gate.get("mapping_complete_unique_chains", 0)),
            "direct_description_ready_rows": int(l3_gate.get("direct_description_ready_rows", 0)),
            "direct_description_ready_unique_chains": int(l3_gate.get("direct_description_ready_unique_chains", 0)),
            "action_counts": actions,
        },
        "batch_gate": {
            "source_authority": "verified_8466_rows",
            "processing_full_pool_replay": "not_replayed_in_current_windows_workspace",
            "training_rows_emitted": 0,
            "training_admission": "not_granted_batch_census_only",
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "llm_called": False,
        },
        "next_batch_actions": [
            "replay_current_rules_against_full_source_manifest",
            "run_description_fidelity_and_four_layer_dedup",
            "keep_recovery_split_and_api_sidecar_out_of_training_until_support_30",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resolution-summary", type=Path, required=True)
    parser.add_argument("--l3-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    census = build_census(_read_json(args.resolution_summary), _read_json(args.l3_summary))
    output = args.output_dir / "full_pool_census_v1.json"
    output.write_text(json.dumps(census, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    hash_ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            "resolution_summary": {"path": str(args.resolution_summary), "sha256": _sha256(args.resolution_summary)},
            "l3_summary": {"path": str(args.l3_summary), "sha256": _sha256(args.l3_summary)},
        },
        "artifacts": {output.name: _sha256(output)},
    }
    (args.output_dir / "hash_ledger_v1.json").write_text(
        json.dumps(hash_ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "report_v1.md").write_text(
        "# QGIS full-pool batch census v1\n\n"
        "This is a source-independent batch census. It does not grant training admission.\n\n"
        f"- Authority rows: **{census['input_rows']}**\n"
        f"- Verified source rows: **{census['verified_source_rows']}**\n"
        f"- Latest replay input: **{census['latest_replay']['input_rows']}**\n"
        f"- Latest mapping-complete rows: **{census['latest_replay']['mapping_complete_rows']}**\n"
        f"- Latest direct description-ready rows: **{census['latest_replay']['direct_description_ready_rows']}**\n"
        "- Training rows emitted: **0**\n\n"
        "A fresh full-source replay is required before any batch export. Recovery, split, and API sidecars remain closed until their source-disjoint support reaches 30 and all fidelity gates pass.\n",
        encoding="utf-8",
    )
    print(json.dumps(census, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
