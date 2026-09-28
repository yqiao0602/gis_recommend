"""Split repeated GEE workflows into independently gated local units."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
import argparse
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gis_recommend.data.gee_dataflow_slicer import (
    LocalSubworkflowUnit,
    build_local_subworkflow_units,
)
from scripts.build_gee_p4_l3_canonicalization_gate import (
    canonicalize_operator_sequence,
    load_gee_l3_mapping,
    load_gee_operator_catalog,
)
from scripts.build_gee_strict_candidate_source_audit import (
    _atomic_write,
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
DEFAULT_REPLAY = DEFAULT_AUTHORITY_DIR / "strict_candidate_source_replay_60_v1.jsonl"
DEFAULT_ID_MAPPINGS = ROOT / "outputs_v2/id_mappings_v2.json"
DEFAULT_OUTPUT_DIR = DEFAULT_AUTHORITY_DIR / "repeated_subworkflow_split_v1"
OUTPUT_PREFIX = "strict_candidate_repeated_subworkflow_split_rank58_v1"


_REPEATED_TERMINAL_SIGNATURE = ("ee.image.cat", "ee.image.select")
_AUXILIARY_GEOMETRY_PREFIX = "ee.geometry."


def select_repeated_unit_ids(
    units: Iterable[LocalSubworkflowUnit],
    canonical_sequences: Mapping[str, Sequence[str]],
) -> tuple[str, ...]:
    """Select repeated concat terminals and their definition-local ancestors."""

    ordered_units = tuple(units)
    units_by_id = {unit.definition_id: unit for unit in ordered_units}
    selected: set[str] = set()

    def include_ancestors(definition_id: str) -> None:
        if definition_id in selected:
            return
        unit = units_by_id.get(definition_id)
        if unit is None:
            return
        selected.add(definition_id)
        for dependency_id in unit.dependency_ids:
            include_ancestors(dependency_id)

    for unit in ordered_units:
        signature = tuple(canonical_sequences.get(unit.definition_id, ()))
        if signature == _REPEATED_TERMINAL_SIGNATURE and len(unit.dependency_ids) > 1:
            include_ancestors(unit.definition_id)

    return tuple(
        unit.definition_id for unit in ordered_units if unit.definition_id in selected
    )


def propagate_unit_blockers(
    units: Iterable[LocalSubworkflowUnit],
    direct_blockers: Mapping[str, Sequence[str]],
) -> dict[str, tuple[str, ...]]:
    """Combine direct blockers with deterministic downstream blocker propagation."""

    ordered_units = tuple(units)
    units_by_id = {unit.definition_id: unit for unit in ordered_units}
    blockers: dict[str, tuple[str, ...]] = {}
    visiting: set[str] = set()

    def resolve(definition_id: str) -> tuple[str, ...]:
        if definition_id in blockers:
            return blockers[definition_id]
        unit = units_by_id.get(definition_id)
        if unit is None or definition_id in visiting:
            return ()

        visiting.add(definition_id)
        reasons = set(direct_blockers.get(definition_id, ()))
        if unit.unresolved_identifiers:
            reasons.add("unresolved_identifiers")
        for dependency_id in unit.dependency_ids:
            if dependency_id in units_by_id and resolve(dependency_id):
                reasons.add(f"upstream_blocked:{dependency_id}")
        visiting.remove(definition_id)
        blockers[definition_id] = tuple(sorted(reasons))
        return blockers[definition_id]

    for unit in ordered_units:
        resolve(unit.definition_id)
    return blockers


def _canonicalize_unit(
    unit: LocalSubworkflowUnit,
    calls_by_ordinal: Mapping[int, dict[str, Any]],
    mapping: Mapping[str, Any],
    operator_catalog: frozenset[str],
) -> dict[str, list[str]]:
    calls = [
        calls_by_ordinal[ordinal]
        for ordinal in unit.core_call_ordinals
        if ordinal in calls_by_ordinal
    ]
    raw_operators = [
        str(call.get("raw_callee") or "").strip().lower() for call in calls
    ]
    receiver_types = [call.get("receiver_type") for call in calls]
    proven_ee_receivers = [
        call.get("resolution") in {"ee_namespace", "receiver_ee_binding"}
        or raw.startswith("ee.")
        for call, raw in zip(calls, raw_operators)
    ]
    canonicalized = canonicalize_operator_sequence(
        raw_operators,
        dict(mapping),
        proven_ee_receivers=proven_ee_receivers,
        receiver_types=receiver_types,
        operator_catalog=operator_catalog,
    )
    return {
        "raw_operator_sequence": raw_operators,
        "canonical_operator_sequence": canonicalized.canonical_operator_sequence,
        "l3_code_sequence": canonicalized.l3_sequence,
        "skipped_raw_operators": canonicalized.skipped_raw_operators,
        "unmapped_raw_operators": canonicalized.unmapped_raw_operators,
        "canonical_unmapped_l3_operators": (
            canonicalized.canonical_unmapped_l3_operators
        ),
    }


def build_repeated_subworkflow_rows(
    *,
    replay_jsonl: Path,
    id_mappings_json: Path,
    audit_rank: int = 58,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build independently gated repeated-workflow units from one frozen replay row."""

    replay_rows = _load_jsonl(Path(replay_jsonl))
    matches = [row for row in replay_rows if row.get("audit_rank") == audit_rank]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one replay row for audit rank {audit_rank}, got {len(matches)}"
        )
    replay = matches[0]
    ast = _load_json(Path(str(replay["local_ast_path"])))
    local_result = build_local_subworkflow_units(
        ast, replay.get("core_call_evidence", [])
    )
    mapping = load_gee_l3_mapping(Path(id_mappings_json))
    operator_catalog = load_gee_operator_catalog(Path(id_mappings_json))
    calls_by_ordinal = {
        int(call["ordinal"]): call
        for call in replay.get("core_call_evidence", [])
        if isinstance(call, dict) and isinstance(call.get("ordinal"), int)
    }

    canonical_by_id = {
        unit.definition_id: _canonicalize_unit(
            unit, calls_by_ordinal, mapping, operator_catalog
        )
        for unit in local_result.units
    }
    selected_ids = select_repeated_unit_ids(
        local_result.units,
        {
            definition_id: values["canonical_operator_sequence"]
            for definition_id, values in canonical_by_id.items()
        },
    )
    terminal_ids = {
        unit.definition_id
        for unit in local_result.units
        if tuple(canonical_by_id[unit.definition_id]["canonical_operator_sequence"])
        == _REPEATED_TERMINAL_SIGNATURE
        and len(unit.dependency_ids) > 1
    }
    excluded_auxiliary_ids = tuple(
        definition_id
        for definition_id in selected_ids
        if definition_id not in terminal_ids
        and not canonical_by_id[definition_id]["canonical_operator_sequence"]
        and all(
            operator.startswith(_AUXILIARY_GEOMETRY_PREFIX)
            for operator in canonical_by_id[definition_id]["raw_operator_sequence"]
        )
    )
    excluded_auxiliary_set = set(excluded_auxiliary_ids)
    selected_ids = tuple(
        definition_id
        for definition_id in selected_ids
        if definition_id not in excluded_auxiliary_set
    )
    selected_set = set(selected_ids)
    selected_units = tuple(
        unit for unit in local_result.units if unit.definition_id in selected_set
    )

    direct_blockers: dict[str, tuple[str, ...]] = {}
    for unit in selected_units:
        canonical = canonical_by_id[unit.definition_id]
        reasons: list[str] = []
        if canonical["unmapped_raw_operators"]:
            reasons.append("canonicalization_gap")
        if canonical["canonical_unmapped_l3_operators"]:
            reasons.append("l3_mapping_gap")
        if not canonical["canonical_operator_sequence"]:
            reasons.append("empty_canonical_chain")
        direct_blockers[unit.definition_id] = tuple(reasons)
    blockers_by_id = propagate_unit_blockers(selected_units, direct_blockers)

    rows: list[dict[str, Any]] = []
    for unit in selected_units:
        if unit.definition_id not in selected_set:
            continue
        canonical = canonical_by_id[unit.definition_id]
        blockers = blockers_by_id[unit.definition_id]
        rows.append(
            {
                "schema": "gis_recommend.gee_repeated_subworkflow_unit.v1",
                "audit_rank": audit_rank,
                "sample_id": replay.get("sample_id"),
                "script_id": replay.get("script_id"),
                "source_path": replay.get("source_path"),
                "source_sha256": replay.get("source_sha256"),
                "extractor_version": replay.get("extractor_version"),
                "definition_id": unit.definition_id,
                "target": unit.target,
                "definition_kind": unit.kind,
                "start_line": unit.start_line,
                "end_line": unit.end_line,
                "dependency_ids": list(unit.dependency_ids),
                "selected_dependency_ids": [
                    item for item in unit.dependency_ids if item in selected_set
                ],
                "core_call_ordinals": list(unit.core_call_ordinals),
                **canonical,
                "unresolved_identifiers": list(unit.unresolved_identifiers),
                "blocking_reasons": list(blockers),
                "candidate_status": (
                    "complete_pending_fidelity_gate" if not blockers else "fail_closed"
                ),
                "training_admission": "not_granted_repeated_subworkflow_split",
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
                "training_rows_emitted": 0,
            }
        )

    summary = {
        "schema": "gis_recommend.gee_repeated_subworkflow_split_summary.v1",
        "inputs": {
            "replay_jsonl": str(replay_jsonl),
            "replay_jsonl_sha256": _sha256(Path(replay_jsonl)),
            "id_mappings_json": str(id_mappings_json),
            "id_mappings_json_sha256": _sha256(Path(id_mappings_json)),
            "audit_rank": audit_rank,
            "sample_id": replay.get("sample_id"),
            "source_sha256": replay.get("source_sha256"),
        },
        "counts": {
            "local_units": len(local_result.units),
            "selected_units": len(rows),
            "excluded_auxiliary_units": len(excluded_auxiliary_ids),
            "complete_pending_fidelity_gate": sum(
                row["candidate_status"] == "complete_pending_fidelity_gate"
                for row in rows
            ),
            "fail_closed": sum(
                row["candidate_status"] == "fail_closed" for row in rows
            ),
            "training_rows_emitted": 0,
        },
        "dataflow_quality_flags": list(local_result.quality_flags),
        "excluded_auxiliary_unit_ids": list(excluded_auxiliary_ids),
        "decision": {
            "training_admission": "not_granted_repeated_subworkflow_split",
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "training_rows_emitted": 0,
            "next_gate": "source-backed fidelity review of repeated local units",
        },
    }
    return rows, summary


def _render_report(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    return "\n".join(
        [
            "# GEE Repeated Subworkflow Split v1",
            "",
            f"- Local units: {counts['local_units']}",
            f"- Selected raster units: {counts['selected_units']}",
            f"- Excluded auxiliary geometry units: {counts['excluded_auxiliary_units']}",
            f"- Complete pending fidelity gate: {counts['complete_pending_fidelity_gate']}",
            f"- Fail closed: {counts['fail_closed']}",
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
    parser.add_argument("--replay-jsonl", type=Path, default=DEFAULT_REPLAY)
    parser.add_argument("--id-mappings-json", type=Path, default=DEFAULT_ID_MAPPINGS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--audit-rank", type=int, default=58)
    args = parser.parse_args(argv)
    rows, summary = build_repeated_subworkflow_rows(
        replay_jsonl=args.replay_jsonl,
        id_mappings_json=args.id_mappings_json,
        audit_rank=args.audit_rank,
    )
    return write_outputs(rows, summary, args.output_dir)


if __name__ == "__main__":
    main()
