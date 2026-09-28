"""Replay confirmed GEE semantic patterns on held-out frozen authorities.

The calibration source(s) are excluded by source SHA.  This command performs a
source-backed census only and never emits training data or task text.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gis_recommend.data.gee_dataflow_slicer import build_local_subworkflow_units  # noqa: E402
from scripts.audit_gee_repeated_subworkflow_semantic_completeness import (  # noqa: E402
    review_semantic_rows,
)
from scripts.build_gee_p4_l3_canonicalization_gate import (  # noqa: E402
    load_gee_l3_mapping,
    load_gee_operator_catalog,
)
from scripts.build_gee_strict_candidate_source_audit import (  # noqa: E402
    _atomic_write,
    _filesystem_path,
    _json_text,
    _jsonl_text,
    _load_json,
    _load_jsonl,
    _sha256,
)
from scripts.review_gee_repeated_subworkflow_structure import (  # noqa: E402
    _pattern_for,
    _semantic_context,
    _source_snippet,
)
from scripts.split_gee_repeated_subworkflows import _canonicalize_unit  # noqa: E402


AUTHORITY_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1/strict_candidate_v1"
    / "source_audit_60_v1/authority_v2_3_0"
)
DEFAULT_REPLAY = AUTHORITY_DIR / "strict_candidate_source_replay_60_v1.jsonl"
DEFAULT_CALIBRATION = (
    AUTHORITY_DIR
    / "repeated_subworkflow_structure_review_v1/repeated_subworkflow_semantic_review_v1"
    / "strict_candidate_repeated_subworkflow_semantic_review_rank58_v1.jsonl"
)
DEFAULT_ID_MAPPINGS = ROOT / "outputs_v2/id_mappings_v2.json"
DEFAULT_OUTPUT_DIR = AUTHORITY_DIR / "repeated_subworkflow_semantic_heldout_replay_v1"
OUTPUT_PREFIX = "strict_candidate_repeated_subworkflow_semantic_heldout_replay_v1"


def _read_source(path: Path) -> str:
    with open(_filesystem_path(path), encoding="utf-8") as handle:
        return handle.read()


def replay_heldout_patterns(
    *,
    replay_jsonl: Path,
    calibration_jsonl: Path,
    id_mappings_json: Path,
    source_hash_override: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    replay_rows = _load_jsonl(Path(replay_jsonl))
    calibration_rows = _load_jsonl(Path(calibration_jsonl))
    if not calibration_rows or any(
        row.get("semantic_status") != "accepted_proposal" for row in calibration_rows
    ):
        raise ValueError("calibration input must contain only accepted semantic proposals")

    calibration_source_shas = {
        str(row.get("source_sha256") or "") for row in calibration_rows
    }
    calibration_patterns = {
        str(row.get("pattern") or "") for row in calibration_rows
    }
    if "" in calibration_source_shas or "" in calibration_patterns:
        raise ValueError("calibration rows must have source SHA and pattern")

    mapping = load_gee_l3_mapping(Path(id_mappings_json))
    catalog = load_gee_operator_catalog(Path(id_mappings_json))
    overrides = source_hash_override or {}
    proposals: list[dict[str, Any]] = []
    source_hash_failures: list[dict[str, Any]] = []
    heldout_rows = [
        row
        for row in replay_rows
        if str(row.get("source_sha256") or "") not in calibration_source_shas
    ]
    local_units_scanned = 0
    verified_authorities = 0

    for replay in heldout_rows:
        sample_id = str(replay.get("sample_id") or "")
        local_source_path = Path(str(replay["local_source_path"]))
        expected_sha = overrides.get(sample_id, str(replay.get("source_sha256") or ""))
        actual_sha = _sha256(local_source_path)
        if actual_sha != expected_sha or not replay.get("source_sha256_verified"):
            source_hash_failures.append(
                {
                    "audit_rank": replay.get("audit_rank"),
                    "sample_id": sample_id,
                    "expected_sha256": expected_sha,
                    "actual_sha256": actual_sha,
                }
            )
            continue
        verified_authorities += 1
        ast = _load_json(Path(str(replay["local_ast_path"])))
        source_text = _read_source(local_source_path)
        local = build_local_subworkflow_units(ast, replay.get("core_call_evidence", []))
        local_units_scanned += len(local.units)
        calls_by_ordinal = {
            int(call["ordinal"]): call
            for call in replay.get("core_call_evidence", [])
            if isinstance(call, dict) and isinstance(call.get("ordinal"), int)
        }
        canonical_by_id = {
            unit.definition_id: _canonicalize_unit(unit, calls_by_ordinal, mapping, catalog)
            for unit in local.units
        }
        candidate_patterns: dict[str, str] = {}
        for unit in local.units:
            canonical = canonical_by_id[unit.definition_id]
            try:
                pattern = _pattern_for(canonical["canonical_operator_sequence"])
            except ValueError:
                continue
            if pattern in calibration_patterns:
                candidate_patterns[unit.definition_id] = pattern
        candidate_ids = set(candidate_patterns)

        for unit in local.units:
            pattern = candidate_patterns.get(unit.definition_id)
            if pattern is None:
                continue
            canonical = canonical_by_id[unit.definition_id]
            call_sites: list[dict[str, Any]] = []
            for index, ordinal in enumerate(unit.core_call_ordinals):
                call = calls_by_ordinal.get(ordinal)
                if call is None:
                    continue
                call_sites.append(
                    {
                        "ordinal": ordinal,
                        "source_location": call.get("source_location"),
                        "raw_callee": call.get("raw_callee"),
                        "canonical_operator": canonical["canonical_operator_sequence"][index],
                        "l3_code": canonical["l3_code_sequence"][index],
                    }
                )
            proposals.append(
                {
                    "schema": "gis_recommend.gee_repeated_subworkflow_heldout_proposal.v1",
                    "audit_rank": replay.get("audit_rank"),
                    "sample_id": replay.get("sample_id"),
                    "script_id": replay.get("script_id"),
                    "source_path": replay.get("source_path"),
                    "source_sha256": replay.get("source_sha256"),
                    "definition_id": unit.definition_id,
                    "definition_kind": unit.kind,
                    "start_line": unit.start_line,
                    "end_line": unit.end_line,
                    "dependency_ids": list(unit.dependency_ids),
                    "selected_dependency_ids": [
                        value for value in unit.dependency_ids if value in candidate_ids
                    ],
                    "core_call_ordinals": list(unit.core_call_ordinals),
                    **canonical,
                    "unresolved_identifiers": list(unit.unresolved_identifiers),
                    "pattern": pattern,
                    **_semantic_context(unit.target, pattern),
                    "source_snippet": _source_snippet(
                        source_text, unit.start_line, unit.end_line
                    ),
                    "call_site_evidence": call_sites,
                    "replay_scope": "frozen_60_heldout_by_calibration_source_sha",
                    "training_admission": "not_granted_heldout_semantic_replay",
                    "validation_eligible": False,
                    "test_eligible": False,
                    "production_merge": "not_granted",
                    "training_rows_emitted": 0,
                }
            )

    reviewed, semantic_summary = review_semantic_rows(proposals)
    matched_source_shas = {
        str(row.get("source_sha256") or "") for row in reviewed
    }
    matched_ranks = sorted(
        {int(row["audit_rank"]) for row in reviewed if isinstance(row.get("audit_rank"), int)}
    )
    pattern_counts = Counter(str(row.get("pattern") or "") for row in reviewed)
    accepted_pattern_counts = Counter(
        str(row.get("pattern") or "")
        for row in reviewed
        if row.get("semantic_status") == "accepted_proposal"
    )
    generalization_status = (
        "insufficient_independent_authority_support"
        if len(matched_source_shas) <= 1
        else "heldout_replay_completed_pending_rule_owner_threshold"
    )
    summary = {
        "schema": "gis_recommend.gee_repeated_subworkflow_semantic_heldout_replay_summary.v1",
        "inputs": {
            "replay_jsonl": str(replay_jsonl),
            "replay_jsonl_sha256": _sha256(Path(replay_jsonl)),
            "calibration_jsonl": str(calibration_jsonl),
            "calibration_jsonl_sha256": _sha256(Path(calibration_jsonl)),
            "id_mappings_json": str(id_mappings_json),
            "id_mappings_json_sha256": _sha256(Path(id_mappings_json)),
        },
        "calibration": {
            "accepted_rows": len(calibration_rows),
            "excluded_source_shas": sorted(calibration_source_shas),
            "confirmed_patterns": sorted(calibration_patterns),
            "confirmation_scope": "source_visible_core_semantics_for_rule_replay_only",
            "human_training_approval": False,
        },
        "counts": {
            "frozen_replay_rows": len(replay_rows),
            "heldout_authorities": len(heldout_rows),
            "source_hash_verified_authorities": verified_authorities,
            "source_hash_failures": len(source_hash_failures),
            "local_units_scanned": local_units_scanned,
            "signature_matches": len(reviewed),
            "matched_independent_authorities": len(matched_source_shas),
            "semantic_accepted_proposal": semantic_summary["counts"]["accepted_proposal"],
            "semantic_fail_closed": semantic_summary["counts"]["fail_closed"],
            "training_rows_emitted": 0,
        },
        "matched_audit_ranks": matched_ranks,
        "pattern_counts": dict(sorted(pattern_counts.items())),
        "accepted_pattern_counts": dict(sorted(accepted_pattern_counts.items())),
        "source_hash_failure_rows": source_hash_failures,
        "decision": {
            "generalization_status": generalization_status,
            "reason": f"{len(matched_source_shas)} held-out source authorities matched the confirmed patterns",
            "training_admission": "not_granted_heldout_semantic_replay",
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "next_gate": "expand source-backed rule census beyond the frozen 60 before any export",
        },
    }
    return reviewed, summary


def _render_report(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    return "\n".join(
        [
            "# GEE Semantic Pattern Held-out Replay v1",
            "",
            f"- Held-out authorities: {counts['heldout_authorities']}",
            f"- Source hashes verified: {counts['source_hash_verified_authorities']}",
            f"- Local units scanned: {counts['local_units_scanned']}",
            f"- Exact signature matches: {counts['signature_matches']}",
            f"- Matched independent authorities: {counts['matched_independent_authorities']}",
            f"- Semantic accepted proposals: {counts['semantic_accepted_proposal']}",
            f"- Semantic fail-closed: {counts['semantic_fail_closed']}",
            f"- Pattern counts: {summary['pattern_counts']}",
            f"- Generalization status: {summary['decision']['generalization_status']}",
            "- Training rows emitted: 0",
            "- Training/validation/test/production admission: not granted",
            "",
        ]
    )


def write_outputs(rows: list[dict[str, Any]], summary: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    paths = {
        "jsonl": output_dir / f"{OUTPUT_PREFIX}.jsonl",
        "summary": output_dir / f"{OUTPUT_PREFIX}_summary.json",
        "report": output_dir / f"{OUTPUT_PREFIX}_report.md",
        "hash_ledger": output_dir / f"{OUTPUT_PREFIX}_hash_ledger.json",
    }
    _atomic_write(paths["jsonl"], _jsonl_text(rows))
    _atomic_write(paths["summary"], _json_text(summary))
    _atomic_write(paths["report"], _render_report(summary))
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": summary["inputs"],
        "artifacts": {
            path.name: {"path": str(path), "sha256": _sha256(path)}
            for key, path in paths.items()
            if key != "hash_ledger"
        },
    }
    _atomic_write(paths["hash_ledger"], _json_text(ledger))
    return paths


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-jsonl", type=Path, default=DEFAULT_REPLAY)
    parser.add_argument("--calibration-jsonl", type=Path, default=DEFAULT_CALIBRATION)
    parser.add_argument("--id-mappings-json", type=Path, default=DEFAULT_ID_MAPPINGS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    rows, summary = replay_heldout_patterns(
        replay_jsonl=args.replay_jsonl,
        calibration_jsonl=args.calibration_jsonl,
        id_mappings_json=args.id_mappings_json,
    )
    return write_outputs(rows, summary, args.output_dir)


if __name__ == "__main__":
    main()
