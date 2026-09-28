"""Audit source and chain fidelity for the deterministic GEE repeated-unit split."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gis_recommend.data.gee_dataflow_slicer import (  # noqa: E402
    build_backward_slices,
    build_local_subworkflow_units,
)
from scripts.build_gee_p4_l3_canonicalization_gate import (  # noqa: E402
    canonicalize_operator_sequence,
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


DEFAULT_AUTHORITY_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1/strict_candidate_v1"
    / "source_audit_60_v1/authority_v2_3_0"
)
DEFAULT_SPLIT = (
    DEFAULT_AUTHORITY_DIR
    / "repeated_subworkflow_split_v1"
    / "strict_candidate_repeated_subworkflow_split_rank58_v1.jsonl"
)
DEFAULT_REPLAY = DEFAULT_AUTHORITY_DIR / "strict_candidate_source_replay_60_v1.jsonl"
DEFAULT_ID_MAPPINGS = ROOT / "outputs_v2/id_mappings_v2.json"
DEFAULT_OUTPUT_DIR = DEFAULT_AUTHORITY_DIR / "repeated_subworkflow_fidelity_gate_v1"
OUTPUT_PREFIX = "strict_candidate_repeated_subworkflow_fidelity_rank58_v1"


def _unique_reasons(reasons: list[str]) -> list[str]:
    return sorted({reason for reason in reasons if reason})


def _canonical_for_calls(
    calls: list[dict[str, Any]], mapping: dict[str, Any], catalog: frozenset[str]
) -> dict[str, list[str]]:
    raw = [str(call.get("raw_callee") or "").strip().lower() for call in calls]
    receiver_types = [call.get("receiver_type") for call in calls]
    proven = [
        call.get("resolution") in {"ee_namespace", "receiver_ee_binding"}
        or operator.startswith("ee.")
        for call, operator in zip(calls, raw)
    ]
    result = canonicalize_operator_sequence(
        raw,
        mapping,
        proven_ee_receivers=proven,
        receiver_types=receiver_types,
        operator_catalog=catalog,
    )
    return {
        "raw_operator_sequence": raw,
        "canonical_operator_sequence": result.canonical_operator_sequence,
        "l3_code_sequence": result.l3_sequence,
        "skipped_raw_operators": result.skipped_raw_operators,
        "unmapped_raw_operators": result.unmapped_raw_operators,
        "canonical_unmapped_l3_operators": result.canonical_unmapped_l3_operators,
    }


def _read_source(path: Path) -> str:
    with open(_filesystem_path(path), encoding="utf-8") as handle:
        return handle.read()


def audit_fidelity_rows(
    *,
    split_jsonl: Path,
    replay_jsonl: Path,
    id_mappings_json: Path,
    audit_rank: int = 58,
    source_hash_override: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    split_rows = _load_jsonl(Path(split_jsonl))
    replay_rows = _load_jsonl(Path(replay_jsonl))
    candidates = [row for row in split_rows if row.get("audit_rank") == audit_rank]
    replay_matches = [row for row in replay_rows if row.get("audit_rank") == audit_rank]
    if len(replay_matches) != 1:
        raise ValueError(f"expected one replay row for rank {audit_rank}")
    replay = replay_matches[0]
    if not candidates:
        raise ValueError(f"split contains no rows for rank {audit_rank}")

    ast = _load_json(Path(str(replay["local_ast_path"])))
    source_text = _read_source(Path(str(replay["local_source_path"])))
    calls = [
        call
        for call in replay.get("core_call_evidence", [])
        if isinstance(call, dict) and call.get("classification", "core") == "core"
    ]
    calls_by_ordinal = {
        int(call["ordinal"]): call
        for call in calls
        if isinstance(call.get("ordinal"), int)
    }
    local_result = build_local_subworkflow_units(ast, calls)
    units_by_id = {unit.definition_id: unit for unit in local_result.units}
    dataflow = build_backward_slices(ast, calls)
    mapping = load_gee_l3_mapping(Path(id_mappings_json))
    catalog = load_gee_operator_catalog(Path(id_mappings_json))
    definitions = {definition.definition_id for definition in dataflow.definitions}
    source_sha_actual = _sha256(Path(str(replay["local_source_path"])))
    expected_replay_sha = str(replay.get("source_sha256") or "")
    override = source_hash_override or {}
    expected_source_sha = override.get(str(replay.get("sample_id")), expected_replay_sha)
    source_hash_verified = source_sha_actual == expected_replay_sha

    source_line_count = len(source_text.splitlines())
    output_rows: list[dict[str, Any]] = []
    for candidate in candidates:
        definition_id = str(candidate.get("definition_id") or "")
        unit = units_by_id.get(definition_id)
        reasons: list[str] = []
        if candidate.get("source_sha256") != expected_replay_sha:
            reasons.append("candidate_source_sha256_mismatch")
        if source_sha_actual != expected_source_sha:
            reasons.append("source_sha256_mismatch")
        if not replay.get("source_sha256_verified"):
            reasons.append("replay_source_hash_not_verified")
        if not isinstance(ast, dict) or ast.get("type") != "Program":
            reasons.append("ast_not_program")
        start_line = candidate.get("start_line")
        end_line = candidate.get("end_line")
        if (
            not isinstance(start_line, int)
            or not isinstance(end_line, int)
            or start_line < 1
            or end_line < start_line
            or end_line > source_line_count
        ):
            reasons.append("source_span_invalid")
        if unit is None:
            reasons.append("definition_missing_from_ast")
        else:
            if (unit.start_line, unit.end_line) != (start_line, end_line):
                reasons.append("definition_span_mismatch")
            if tuple(candidate.get("dependency_ids") or ()) != unit.dependency_ids:
                reasons.append("dependency_ids_mismatch")
            if tuple(candidate.get("unresolved_identifiers") or ()) != unit.unresolved_identifiers:
                reasons.append("unresolved_identifiers_mismatch")
            missing_dependencies = [
                dependency
                for dependency in unit.dependency_ids
                if dependency not in definitions
            ]
            if missing_dependencies:
                reasons.append("dependency_definition_missing")

        ordinals = tuple(candidate.get("core_call_ordinals") or ())
        if ordinals != tuple(sorted(set(ordinals))):
            reasons.append("call_ordinals_not_strictly_ordered")
        selected_calls: list[dict[str, Any]] = []
        for ordinal in ordinals:
            if not isinstance(ordinal, int) or ordinal not in calls_by_ordinal:
                reasons.append("call_ordinal_missing_from_replay")
                continue
            selected_calls.append(calls_by_ordinal[ordinal])
        for call in selected_calls:
            location = call.get("source_location") or {}
            call_start = location.get("start_line")
            call_end = location.get("end_line")
            if (
                not isinstance(call_start, int)
                or not isinstance(call_end, int)
                or not isinstance(start_line, int)
                or not isinstance(end_line, int)
                or call_start < start_line
                or call_end > end_line
            ):
                reasons.append("call_outside_definition_span")
        canonical = _canonical_for_calls(selected_calls, mapping, catalog)
        for field in (
            "raw_operator_sequence",
            "canonical_operator_sequence",
            "l3_code_sequence",
            "skipped_raw_operators",
            "unmapped_raw_operators",
            "canonical_unmapped_l3_operators",
        ):
            if list(candidate.get(field) or []) != canonical[field]:
                reasons.append(f"{field}_mismatch")
        if len(canonical["canonical_operator_sequence"]) != len(canonical["l3_code_sequence"]):
            reasons.append("canonical_l3_length_mismatch")
        if candidate.get("candidate_status") != "complete_pending_fidelity_gate":
            reasons.append("candidate_blocked_before_fidelity")
        if candidate.get("blocking_reasons"):
            reasons.append("candidate_has_blocking_reasons")
        if candidate.get("unresolved_identifiers"):
            reasons.append("unresolved_identifiers")

        fidelity_reasons = _unique_reasons(reasons)
        blocked = candidate.get("candidate_status") != "complete_pending_fidelity_gate"
        if blocked:
            status = "blocked_upstream_or_unresolved"
        else:
            status = "passed" if not fidelity_reasons else "fail_closed"
        output_rows.append(
            {
                **candidate,
                "schema": "gis_recommend.gee_repeated_subworkflow_fidelity.v1",
                "fidelity_status": status,
                "fidelity_reasons": fidelity_reasons,
                "source_hash_actual": source_sha_actual,
                "source_hash_verified": source_hash_verified,
                "training_admission": "not_granted_repeated_subworkflow_fidelity_gate",
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
                "training_rows_emitted": 0,
            }
        )

    summary = {
        "schema": "gis_recommend.gee_repeated_subworkflow_fidelity_summary.v1",
        "inputs": {
            "split_jsonl": str(split_jsonl),
            "split_jsonl_sha256": _sha256(Path(split_jsonl)),
            "replay_jsonl": str(replay_jsonl),
            "replay_jsonl_sha256": _sha256(Path(replay_jsonl)),
            "id_mappings_json": str(id_mappings_json),
            "id_mappings_json_sha256": _sha256(Path(id_mappings_json)),
            "audit_rank": audit_rank,
            "sample_id": replay.get("sample_id"),
            "source_sha256": expected_replay_sha,
        },
        "counts": {
            "candidate_rows": len(output_rows),
            "source_hash_verified": int(source_hash_verified) * len(output_rows),
            "fidelity_passed": sum(row["fidelity_status"] == "passed" for row in output_rows),
            "blocked_upstream_or_unresolved": sum(
                row["candidate_status"] != "complete_pending_fidelity_gate"
                for row in output_rows
            ),
            "fidelity_failed": sum(row["fidelity_status"] == "fail_closed" for row in output_rows),
            "training_rows_emitted": 0,
        },
        "decision": {
            "training_admission": "not_granted_repeated_subworkflow_fidelity_gate",
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "training_rows_emitted": 0,
            "next_gate": "source-backed review of fidelity-passed local units",
        },
    }
    return output_rows, summary


def _render_report(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    return "\n".join(
        [
            "# GEE Repeated Subworkflow Fidelity Gate v1",
            "",
            f"- Candidate rows: {counts['candidate_rows']}",
            f"- Source hash verified: {counts['source_hash_verified']}",
            f"- Fidelity passed: {counts['fidelity_passed']}",
            f"- Blocked upstream or unresolved: {counts['blocked_upstream_or_unresolved']}",
            f"- Fidelity failed: {counts['fidelity_failed']}",
            "- Training rows emitted: 0",
            "- Training/validation/test/production admission: not granted",
            "",
        ]
    )


def write_outputs(
    rows: list[dict[str, Any]], summary: dict[str, Any], output_dir: Path
) -> dict[str, Path]:
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
    parser.add_argument("--split-jsonl", type=Path, default=DEFAULT_SPLIT)
    parser.add_argument("--replay-jsonl", type=Path, default=DEFAULT_REPLAY)
    parser.add_argument("--id-mappings-json", type=Path, default=DEFAULT_ID_MAPPINGS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--audit-rank", type=int, default=58)
    args = parser.parse_args(argv)
    rows, summary = audit_fidelity_rows(
        split_jsonl=args.split_jsonl,
        replay_jsonl=args.replay_jsonl,
        id_mappings_json=args.id_mappings_json,
        audit_rank=args.audit_rank,
    )
    return write_outputs(rows, summary, args.output_dir)


if __name__ == "__main__":
    main()
