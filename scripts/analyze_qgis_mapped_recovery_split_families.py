#!/usr/bin/env python3
"""Census mapped QGIS recovery/split rows by static recovery mechanism."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
import tempfile
import warnings
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from gis_recommend.data.qgis_conversion_features import (  # noqa: E402
    _is_processing_call,
    _lexical_scope,
    _operator_id,
    _parents,
    _reference_keys,
    _target_key,
)
from gis_recommend.data.qgis_source_authority import source_authority  # noqa: E402
from gis_recommend.data.qgis_subworkflow_splitter import (  # noqa: E402
    literalize_processing_operator_ids,
    split_candidate_into_local_units,
)
from scripts.build_qgis_recovery_local_dag_units import (  # noqa: E402
    classify_recovery_unit,
)


DEFAULT_MANIFEST = Path(
    "/home/qy/system_redesign/diagnostics/qgis_legacy_provider_recovery_v2/"
    "l3_gate_v3/l3_gated_manifest_v1.jsonl"
)
DEFAULT_OUTPUT_DIR = Path(
    "/home/qy/system_redesign/diagnostics/qgis_legacy_provider_recovery_v2/"
    "mapped_recovery_split_family_census_v1"
)
SUPPORTED_ACTIONS = {"recover_call_graph", "split_subworkflow"}
MIN_SUPPORT = 30
MIN_PRECISION = 0.95
MIN_WILSON_LOWER = 0.80


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _assignment_parts(node: ast.AST) -> tuple[list[ast.AST], ast.AST] | None:
    if isinstance(node, ast.Assign):
        return list(node.targets), node.value
    if isinstance(node, ast.AnnAssign) and node.value is not None:
        return [node.target], node.value
    return None


def _assignment_targets(node: ast.AST) -> list[str]:
    parts = _assignment_parts(node)
    if parts is None:
        return []
    return [key for target in parts[0] if (key := _target_key(target))]


def _contains_processing_call(node: ast.AST) -> bool:
    return any(_is_processing_call(child) for child in ast.walk(node))


def _references_key(references: set[str], key: str) -> bool:
    return any(reference == key or reference.startswith(key + ".") for reference in references)


def _aligned_calls(
    tree: ast.AST, call_sites: Sequence[Mapping[str, Any]]
) -> list[ast.Call]:
    literal_calls = sorted(
        (
            node
            for node in ast.walk(tree)
            if _is_processing_call(node) and _operator_id(node)
        ),
        key=lambda node: (node.lineno, node.col_offset),
    )
    aligned: list[ast.Call] = []
    used: set[int] = set()
    for site in call_sites:
        operator_id = str(site.get("operator_id") or "").strip().lower()
        start = int(site.get("line_start") or 0)
        end = int(site.get("line_end") or start)
        candidates = [
            call
            for call in literal_calls
            if id(call) not in used
            and _operator_id(call) == operator_id
            and int(call.lineno) <= end
            and int(call.end_lineno or call.lineno) >= start
        ]
        if len(candidates) != 1:
            raise ValueError(f"cannot uniquely align call site: {operator_id}@{start}-{end}")
        used.add(id(candidates[0]))
        aligned.append(candidates[0])
    return aligned


def detect_recovery_families(
    source_text: str, *, call_sites: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Return overlapping syntax families; presence does not imply a blocker."""

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        tree = ast.parse(source_text)
    parents = _parents(tree)
    calls = _aligned_calls(tree, call_sites)
    evidence: Counter[str] = Counter()
    result_targets: dict[ast.AST, set[str]] = defaultdict(set)
    derived_depth: dict[ast.AST, dict[str, int]] = defaultdict(dict)
    parameter_dict_uses: list[tuple[ast.Call, str]] = []

    for call in calls:
        scope = _lexical_scope(call, parents)
        if len(call.args) > 1 and not isinstance(call.args[1], ast.Dict):
            evidence["parameter_dictionary"] += 1
            if key := _target_key(call.args[1]):
                parameter_dict_uses.append((call, key))

        current: ast.AST = call
        parent = parents.get(current)
        immediate_output = isinstance(parent, ast.Subscript) and parent.value is call
        if immediate_output:
            current = parent
            parent = parents.get(current)
        if isinstance(parent, (ast.Assign, ast.AnnAssign)):
            targets = _assignment_targets(parent)
            if immediate_output:
                evidence["immediate_output_extract"] += 1
                for key in targets:
                    derived_depth[scope][key] = 0
            else:
                evidence["result_dictionary"] += 1
                for key in targets:
                    result_targets[scope].add(key)
                    derived_depth[scope][key] = 0

    assignments = sorted(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            and _assignment_parts(node) is not None
        ),
        key=lambda node: int(getattr(node, "lineno", 0)),
    )
    output_alias_keys: set[tuple[ast.AST, str]] = set()
    for assignment in assignments:
        targets, value = _assignment_parts(assignment) or ([], assignment)
        if _contains_processing_call(value):
            continue
        scope = _lexical_scope(assignment, parents)
        target_keys = [key for target in targets if (key := _target_key(target))]
        references = _reference_keys(value)
        source_keys = [
            key
            for key in derived_depth[scope]
            if _references_key(references, key)
        ]
        if not source_keys or not target_keys:
            continue
        is_output_alias = isinstance(value, ast.Subscript) and any(
            key in result_targets[scope] for key in source_keys
        )
        if is_output_alias:
            evidence["output_alias"] += 1
            for key in target_keys:
                derived_depth[scope][key] = 0
                output_alias_keys.add((scope, key))
            continue
        depth = max(derived_depth[scope][key] for key in source_keys) + 1
        for key in target_keys:
            derived_depth[scope][key] = depth

    consumed_backward_aliases: set[tuple[ast.AST, str]] = set()
    for call in calls:
        scope = _lexical_scope(call, parents)
        references = {
            reference
            for argument in [*call.args[1:], *(item.value for item in call.keywords)]
            for reference in _reference_keys(argument)
        }
        consumed_backward_aliases.update(
            (scope, key)
            for key, depth in derived_depth[scope].items()
            if depth >= 1 and _references_key(references, key)
        )
    if consumed_backward_aliases:
        evidence["backward_slice_alias"] = len(consumed_backward_aliases)

    for call, parameter_key in parameter_dict_uses:
        scope = _lexical_scope(call, parents)
        before_line = int(call.lineno)
        mutations = 0
        for assignment in assignments:
            if _lexical_scope(assignment, parents) is not scope:
                continue
            if int(getattr(assignment, "lineno", 0)) >= before_line:
                continue
            mutations += sum(
                key.startswith(parameter_key + ".key:")
                for key in _assignment_targets(assignment)
            )
        evidence["parameter_dictionary_mutation"] += mutations

    selected_call_ids = {id(call) for call in calls}
    helper_functions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(
            id(child) in selected_call_ids
            for child in ast.walk(node)
            if isinstance(child, ast.Call)
        )
    }
    helper_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in helper_functions
        and _lexical_scope(node, parents) is not helper_functions[node.func.id]
    ]
    if helper_calls:
        evidence["helper_function_call"] = len(helper_calls)
    cross_function = 0
    for helper_call in helper_calls:
        scope = _lexical_scope(helper_call, parents)
        references = {
            reference
            for argument in [*helper_call.args, *(item.value for item in helper_call.keywords)]
            for reference in _reference_keys(argument)
        }
        if any(
            _references_key(references, key) for key in derived_depth[scope]
        ):
            cross_function += 1
    if cross_function:
        evidence["cross_function_dataflow"] = cross_function

    counts = {key: value for key, value in sorted(evidence.items()) if value}
    return {
        "families": sorted(counts),
        "family_evidence_counts": counts,
        "selected_processing_call_count": len(calls),
        "output_alias_key_count": len(output_alias_keys),
    }


def _population(
    rows: list[dict[str, Any]], field: str
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for value in row.get(field) or []:
            grouped[str(value)].append(row)
    return {
        name: {
            "raw_rows": len(group_rows),
            "source_authorities": len(
                {row["source_authority_key"] for row in group_rows}
            ),
            "by_action": dict(
                sorted(Counter(row["action"] for row in group_rows).items())
            ),
            "rows_with_multi_step_local_units": sum(
                row["multi_step_local_unit_count"] > 0 for row in group_rows
            ),
            "rows_with_current_eligible_units": sum(
                row["current_eligible_unit_count"] > 0 for row in group_rows
            ),
            "current_eligible_units": sum(
                row["current_eligible_unit_count"] for row in group_rows
            ),
        }
        for name, group_rows in sorted(grouped.items())
    }


def build_family_census(
    manifest_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    inputs = [row for row in manifest_rows if row.get("action") in SUPPORTED_ACTIONS]
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for parent in inputs:
        source_path = Path(str(parent.get("source_path") or ""))
        source_sha = str(parent.get("source_sha256") or "")
        record_id = str(parent.get("record_id") or "")
        if not source_path.is_file():
            failures.append({"record_id": record_id, "reason": "source_file_missing"})
            continue
        if _sha256(source_path) != source_sha:
            failures.append({"record_id": record_id, "reason": "source_sha256_mismatch"})
            continue
        source_text = source_path.read_text(encoding="utf-8-sig", errors="replace")
        analysis_source = source_text
        try:
            if parent.get("provider_migrations") or parent.get(
                "resolution_status"
            ) == "fixed_chain_recovered":
                analysis_source = literalize_processing_operator_ids(
                    source_text,
                    call_sites=parent.get("call_sites") or [],
                    require_full_coverage=not bool(parent.get("provider_migrations")),
                )
            family_evidence = detect_recovery_families(
                analysis_source, call_sites=parent.get("call_sites") or []
            )
            units = split_candidate_into_local_units(
                analysis_source, call_sites=parent.get("call_sites") or []
            )
        except (SyntaxError, ValueError) as exc:
            failures.append({"record_id": record_id, "reason": str(exc)})
            continue

        multi_units = [
            unit for unit in units if unit.get("split_class") == "multi_step_local_dag"
        ]
        eligible_units = []
        for unit in multi_units:
            if parent["action"] == "recover_call_graph":
                classification = classify_recovery_unit(
                    unit, parent_rule_id=str(parent.get("rule_id") or "")
                )
                if classification["recovery_structure_status"] == "eligible":
                    eligible_units.append(unit)
            elif unit.get("local_structure_status") == "eligible":
                eligible_units.append(unit)
        blockers = sorted(
            {
                str(reason)
                for unit in multi_units
                for reason in unit.get("local_structure_reasons") or []
            }
        )
        authority = source_authority(source_path, source_sha256=source_sha)
        rows.append(
            {
                "schema": "gis_recommend.qgis_mapped_recovery_split_family_census.v1",
                "record_id": record_id,
                "action": parent["action"],
                "rule_id": parent.get("rule_id"),
                "source_root_id": parent.get("source_root_id"),
                "source_path": str(source_path),
                "source_sha256": source_sha,
                **authority,
                **family_evidence,
                "cross_scope_candidate": parent["action"] == "split_subworkflow",
                "local_unit_count": len(units),
                "multi_step_local_unit_count": len(multi_units),
                "current_eligible_unit_count": len(eligible_units),
                "blocker_reasons": blockers,
                "training_admission": "not_granted_census_only",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )

    family_populations = _population(rows, "families")
    blocker_populations = _population(rows, "blocker_reasons")
    calibration_queue = {
        family: {
            "source_authority_support": counts["source_authorities"],
            "minimum_support": MIN_SUPPORT,
            "measured_precision": None,
            "minimum_precision": MIN_PRECISION,
            "wilson_lower_95": None,
            "minimum_wilson_lower_95": MIN_WILSON_LOWER,
            "promotion_eligible": False,
            "status": (
                "pending_source_disjoint_precision_calibration"
                if counts["source_authorities"] >= MIN_SUPPORT
                else "frozen_support_below_30"
            ),
        }
        for family, counts in family_populations.items()
    }
    summary = {
        "schema": "gis_recommend.qgis_mapped_recovery_split_family_census.summary.v1",
        "input_rows": len(inputs),
        "verified_rows": len(rows),
        "failed_rows": len(failures),
        "failures": failures,
        "unique_source_authorities": len(
            {row["source_authority_key"] for row in rows}
        ),
        "action_counts": dict(sorted(Counter(row["action"] for row in rows).items())),
        "family_populations": family_populations,
        "blocker_populations": blocker_populations,
        "local_units": sum(row["local_unit_count"] for row in rows),
        "multi_step_local_units": sum(
            row["multi_step_local_unit_count"] for row in rows
        ),
        "current_eligible_units": sum(
            row["current_eligible_unit_count"] for row in rows
        ),
        "current_eligible_authorities": len(
            {
                row["source_authority_key"]
                for row in rows
                if row["current_eligible_unit_count"]
            }
        ),
        "calibration_queue": calibration_queue,
        "decision": {
            "training_admission": "not_granted_census_only",
            "training_rows_emitted": 0,
            "next_gate": (
                "source-disjoint calibration for support>=30 families; require "
                "precision>=0.95 and Wilson lower>=0.80"
            ),
        },
    }
    return rows, summary


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# QGIS Mapped Recovery/Split Family Census v1",
        "",
        "This is an overlapping mechanism census, not training admission.",
        "",
        f"- Input rows: {summary['input_rows']}",
        f"- Verified rows: {summary['verified_rows']}",
        f"- Independent source authorities: {summary['unique_source_authorities']}",
        f"- Multi-step local units: {summary['multi_step_local_units']}",
        f"- Currently eligible units: {summary['current_eligible_units']}",
        "- Training rows emitted: 0",
        "",
        "## Recovery Mechanisms",
        "",
        "| Family | Rows | Authorities | Rows with multi-step | Current eligible units | Calibration status |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for family, counts in sorted(
        summary["family_populations"].items(),
        key=lambda item: (-item[1]["source_authorities"], item[0]),
    ):
        lines.append(
            f"| {family} | {counts['raw_rows']} | {counts['source_authorities']} | "
            f"{counts['rows_with_multi_step_local_units']} | "
            f"{counts['current_eligible_units']} | "
            f"{summary['calibration_queue'][family]['status']} |"
        )
    lines.extend(
        [
            "",
            "## Structural Blockers",
            "",
            "| Blocker | Rows | Authorities |",
            "|---|---:|---:|",
        ]
    )
    for reason, counts in sorted(
        summary["blocker_populations"].items(),
        key=lambda item: (-item[1]["source_authorities"], item[0]),
    ):
        lines.append(
            f"| {reason} | {counts['raw_rows']} | {counts['source_authorities']} |"
        )
    return "\n".join(lines) + "\n"


def write_outputs(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    manifest_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    ledger_path = output_dir / "family_census_v1.jsonl"
    summary_path = output_dir / "summary_v1.json"
    report_path = output_dir / "report_v1.md"
    hash_path = output_dir / "hash_ledger_v1.json"
    _atomic_write(
        ledger_path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
    )
    _atomic_write(
        summary_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _atomic_write(report_path, _render_report(summary))
    hashes = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            manifest_path.name: {
                "path": str(manifest_path),
                "sha256": _sha256(manifest_path),
            }
        },
        "artifacts": {
            path.name: {"path": str(path), "sha256": _sha256(path)}
            for path in (ledger_path, summary_path, report_path)
        },
    }
    _atomic_write(
        hash_path,
        json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return {
        "ledger": ledger_path,
        "summary": summary_path,
        "report": report_path,
        "hash_ledger": hash_path,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows, summary = build_family_census(list(_load_jsonl(args.manifest)))
    return write_outputs(
        rows, summary, manifest_path=args.manifest, output_dir=args.output_dir
    )


if __name__ == "__main__":
    main()
