#!/usr/bin/env python3
"""Calibrate deterministic GEE backward slices on routed alignment candidates."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gis_recommend.data.gee_dataflow_slicer import (  # noqa: E402
    BackwardSlice,
    DataflowSliceResult,
    build_backward_slices,
)
from scripts.build_gee_p4_l3_canonicalization_gate import (  # noqa: E402
    canonicalize_operator_sequence,
    load_gee_l3_mapping,
    load_gee_operator_catalog,
)
from scripts.build_gee_strict_candidate_source_audit import (  # noqa: E402
    _atomic_write,
    _json_text,
    _jsonl_text,
    _load_json,
    _load_jsonl,
    _sha256,
)


AUTHORITY_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1/strict_candidate_v1"
    / "source_audit_60_v1/authority_v2_3_0"
)
DEFAULT_REPLAY = AUTHORITY_DIR / "strict_candidate_source_replay_60_v1.jsonl"
DEFAULT_ID_MAPPINGS = ROOT / "outputs_v2/id_mappings_v2.json"
DEFAULT_OUTPUT_DIR = AUTHORITY_DIR / "dataflow_slice_calibration_v1"
DEFAULT_RANKS = (3, 15, 49, 50)
OUTPUT_PREFIX = "strict_candidate_dataflow_slice_calibration_4_v1"


@dataclass(frozen=True)
class SelectedSlice:
    strategy: str
    root_ids: tuple[str, ...]
    definition_ids: tuple[str, ...]
    dependency_edges: tuple[tuple[str, str], ...]
    core_call_ordinals: tuple[int, ...]
    unresolved_identifiers: tuple[str, ...]


def _merge_slices(strategy: str, slices: list[BackwardSlice]) -> SelectedSlice:
    ordered_slices = sorted(slices, key=lambda item: (item.root_line, item.root_id))
    definition_ids: list[str] = []
    edges: set[tuple[str, str]] = set()
    ordinals: set[int] = set()
    unresolved: set[str] = set()
    for item in ordered_slices:
        for definition_id in item.definition_ids:
            if definition_id not in definition_ids:
                definition_ids.append(definition_id)
        edges.update(item.dependency_edges)
        ordinals.update(item.core_call_ordinals)
        unresolved.update(item.unresolved_identifiers)
    return SelectedSlice(
        strategy=strategy,
        root_ids=tuple(item.root_id for item in ordered_slices),
        definition_ids=tuple(definition_ids),
        dependency_edges=tuple(sorted(edges)),
        core_call_ordinals=tuple(sorted(ordinals)),
        unresolved_identifiers=tuple(sorted(unresolved)),
    )


def _connected_component(
    seed: BackwardSlice, slices: tuple[BackwardSlice, ...]
) -> list[BackwardSlice]:
    component: list[BackwardSlice] = [seed]
    known_definitions = set(seed.definition_ids)
    changed = True
    while changed:
        changed = False
        for item in slices:
            if item in component or not known_definitions.intersection(item.definition_ids):
                continue
            component.append(item)
            known_definitions.update(item.definition_ids)
            changed = True
    return component


def select_candidate_slice(result: DataflowSliceResult) -> SelectedSlice:
    """Select a structural calibration candidate without task-text inference."""

    if not result.slices:
        raise ValueError("dataflow result contains no slices")
    leaf_components: list[list[BackwardSlice]] = []
    seen_components: set[tuple[str, ...]] = set()
    for leaf in result.slices:
        if leaf.root_kind != "unconsumed_core_leaf":
            continue
        component = _connected_component(leaf, result.slices)
        signature = tuple(sorted(item.root_id for item in component))
        if signature not in seen_components:
            seen_components.add(signature)
            leaf_components.append(component)
    if leaf_components:
        selected = max(
            leaf_components,
            key=lambda items: (
                len({ordinal for item in items for ordinal in item.core_call_ordinals}),
                len({definition for item in items for definition in item.definition_ids}),
                max(item.root_line for item in items),
            ),
        )
        return _merge_slices("connected_component_with_core_leaves", selected)

    sink_candidates = [
        item
        for item in result.slices
        if item.root_kind in {"presentation_sink", "io_sink", "expression_sink"}
    ]
    if not sink_candidates:
        sink_candidates = list(result.slices)
    selected_sink = max(
        sink_candidates,
        key=lambda item: (
            len(item.definition_ids),
            len(item.core_call_ordinals),
            item.root_line,
            item.root_id,
        ),
    )
    return _merge_slices("maximal_latest_sink", [selected_sink])


def build_calibration_rows(
    *,
    replay_jsonl: Path,
    id_mappings_json: Path,
    ranks: tuple[int, ...] = DEFAULT_RANKS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    replay_rows = _load_jsonl(replay_jsonl)
    mapping = load_gee_l3_mapping(id_mappings_json)
    operator_catalog = load_gee_operator_catalog(id_mappings_json)
    rows_by_rank = {int(row.get("audit_rank")): row for row in replay_rows}
    missing_ranks = sorted(set(ranks) - set(rows_by_rank))
    if missing_ranks:
        raise ValueError(f"replay is missing requested ranks: {missing_ranks}")

    output_rows: list[dict[str, Any]] = []
    for rank in ranks:
        replay = rows_by_rank[rank]
        ast = _load_json(Path(str(replay["local_ast_path"])))
        dataflow = build_backward_slices(ast, replay.get("core_call_evidence", []))
        selected = select_candidate_slice(dataflow)
        calls_by_ordinal = {
            int(call["ordinal"]): call
            for call in replay.get("core_call_evidence", [])
            if isinstance(call, dict) and isinstance(call.get("ordinal"), int)
        }
        selected_calls = [
            calls_by_ordinal[ordinal]
            for ordinal in selected.core_call_ordinals
            if ordinal in calls_by_ordinal
        ]
        raw_operators = [str(call.get("raw_callee") or "").strip().lower() for call in selected_calls]
        receiver_types = [call.get("receiver_type") for call in selected_calls]
        proven_ee_receivers = [
            call.get("resolution") in {"ee_namespace", "receiver_ee_binding"}
            or raw.startswith("ee.")
            for call, raw in zip(selected_calls, raw_operators)
        ]
        canonicalized = canonicalize_operator_sequence(
            raw_operators,
            mapping,
            proven_ee_receivers=proven_ee_receivers,
            receiver_types=receiver_types,
            operator_catalog=operator_catalog,
        )
        blocking_reasons: list[str] = []
        if selected.unresolved_identifiers:
            blocking_reasons.append("unresolved_identifiers")
        if canonicalized.unmapped_raw_operators:
            blocking_reasons.append("canonicalization_gap")
        if canonicalized.canonical_unmapped_l3_operators:
            blocking_reasons.append("l3_mapping_gap")
        if not canonicalized.canonical_operator_sequence:
            blocking_reasons.append("empty_canonical_chain")
        output_rows.append(
            {
                "schema": "gis_recommend.gee_dataflow_slice_calibration.v1",
                "audit_rank": rank,
                "sample_id": replay.get("sample_id"),
                "script_id": replay.get("script_id"),
                "source_path": replay.get("source_path"),
                "source_sha256": replay.get("source_sha256"),
                "extractor_version": replay.get("extractor_version"),
                "slice_strategy": selected.strategy,
                "selected_root_ids": list(selected.root_ids),
                "selected_definition_ids": list(selected.definition_ids),
                "selected_dependency_edges": [list(edge) for edge in selected.dependency_edges],
                "selected_core_call_ordinals": list(selected.core_call_ordinals),
                "selected_raw_operator_sequence": raw_operators,
                "selected_canonical_operator_sequence": canonicalized.canonical_operator_sequence,
                "selected_l3_code_sequence": canonicalized.l3_sequence,
                "skipped_raw_operators": canonicalized.skipped_raw_operators,
                "unmapped_raw_operators": canonicalized.unmapped_raw_operators,
                "canonical_unmapped_l3_operators": canonicalized.canonical_unmapped_l3_operators,
                "unresolved_identifiers": list(selected.unresolved_identifiers),
                "dataflow_quality_flags": list(dataflow.quality_flags),
                "candidate_status": "complete_pending_fidelity_gate" if not blocking_reasons else "fail_closed",
                "blocking_reasons": blocking_reasons,
                "frozen_operator_sequence": replay.get("frozen_operator_sequence", []),
                "task_name": replay.get("task_name"),
                "task_description": replay.get("task_description"),
                "training_admission": "not_granted_dataflow_slice_calibration",
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
                "training_rows_emitted": 0,
            }
        )

    summary = {
        "schema": "gis_recommend.gee_dataflow_slice_calibration_summary.v1",
        "inputs": {
            "replay_jsonl": str(replay_jsonl),
            "replay_jsonl_sha256": _sha256(replay_jsonl),
            "id_mappings_json": str(id_mappings_json),
            "id_mappings_json_sha256": _sha256(id_mappings_json),
            "ranks": list(ranks),
        },
        "counts": {
            "calibration_rows": len(output_rows),
            "complete_pending_fidelity_gate": sum(
                row["candidate_status"] == "complete_pending_fidelity_gate"
                for row in output_rows
            ),
            "fail_closed": sum(row["candidate_status"] == "fail_closed" for row in output_rows),
            "training_rows_emitted": 0,
        },
        "decision": {
            "training_admission": "not_granted_dataflow_slice_calibration",
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "training_rows_emitted": 0,
            "next_gate": "source-backed task fidelity review of structural slice candidates",
        },
    }
    return output_rows, summary


def _report(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    return "\n".join(
        [
            "# GEE Dataflow Slice Calibration v1",
            "",
            f"- Calibration rows: {counts['calibration_rows']}",
            f"- Complete pending fidelity gate: {counts['complete_pending_fidelity_gate']}",
            f"- Fail closed: {counts['fail_closed']}",
            "- Training rows emitted: 0",
            "- Validation/test/production merge: not granted",
            "",
        ]
    )


def write_outputs(
    rows: list[dict[str, Any]], summary: dict[str, Any], output_dir: Path
) -> dict[str, Path]:
    paths = {
        "jsonl": output_dir / f"{OUTPUT_PREFIX}.jsonl",
        "summary": output_dir / f"{OUTPUT_PREFIX}_summary.json",
        "report": output_dir / f"{OUTPUT_PREFIX}_report.md",
        "hash_ledger": output_dir / f"{OUTPUT_PREFIX}_hash_ledger.json",
    }
    _atomic_write(paths["jsonl"], _jsonl_text(rows))
    _atomic_write(paths["summary"], _json_text(summary))
    _atomic_write(paths["report"], _report(summary))
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "artifacts": {
            path.name: {
                "path": str(path),
                "sha256": _sha256(path),
            }
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
    parser.add_argument("--ranks", type=int, nargs="+", default=list(DEFAULT_RANKS))
    args = parser.parse_args(argv)
    rows, summary = build_calibration_rows(
        replay_jsonl=args.replay_jsonl,
        id_mappings_json=args.id_mappings_json,
        ranks=tuple(args.ranks),
    )
    return write_outputs(rows, summary, args.output_dir)


if __name__ == "__main__":
    main()
