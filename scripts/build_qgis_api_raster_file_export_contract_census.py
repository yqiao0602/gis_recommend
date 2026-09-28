#!/usr/bin/env python3
"""Classify source-verified ``QgsRasterFileWriter.writeRaster`` contracts."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from scripts.build_qgis_api_remaining_family_census import (
    _control_path,
    _control_paths_compatible,
    _fact,
    _method,
    _name,
    _parents,
    _reaching_values,
    _scope,
    _scope_name,
    select_source_disjoint_review,
)

SCHEMA = "gis_recommend.qgis_api_raster_file_export_contract.v1"
RULE_ID = "qgis-api-raster-file-export-contract-v1"
GEOTIFF_L3 = "L3_07_04_05"

_GEOTIFF_FORMATS = {"gtiff", "geotiff", "cog"}
_GPKG_FORMATS = {"gpkg", "geopackage"}
_IMAGE_FORMATS = {"png", "jpeg", "jpg", "bmp", "webp", "gif"}
_GEOTIFF_SUFFIXES = {".tif", ".tiff"}
_IMAGE_SUFFIXES = {".png", ".jpeg", ".jpg", ".bmp", ".webp", ".gif"}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(
        path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def _unique_reaching_node(
    node: ast.AST,
    *,
    scope: ast.AST,
    before_line: int,
    control_path: tuple[str, ...],
    parents: dict[ast.AST, ast.AST],
    visited: frozenset[str] = frozenset(),
) -> tuple[ast.AST, list[int]]:
    if not isinstance(node, ast.Name) or node.id in visited:
        return node, []
    reaching = _reaching_values(
        scope,
        node.id,
        before_line=before_line,
        use_control_path=control_path,
        parents=parents,
    )
    signatures = {ast.dump(value, include_attributes=False) for _, value in reaching}
    if len(signatures) != 1:
        return node, []
    line, value = reaching[0]
    resolved, nested_lines = _unique_reaching_node(
        value,
        scope=scope,
        before_line=line,
        control_path=control_path,
        parents=parents,
        visited=visited | {node.id},
    )
    return resolved, sorted({line, *nested_lines})


def _string_fragments(
    node: ast.AST | None,
    *,
    scope: ast.AST,
    before_line: int,
    control_path: tuple[str, ...],
    parents: dict[ast.AST, ast.AST],
    visited: frozenset[str] = frozenset(),
) -> tuple[list[str], list[int]]:
    if node is None:
        return [], []
    if isinstance(node, ast.Name) and node.id not in visited:
        resolved, lines = _unique_reaching_node(
            node,
            scope=scope,
            before_line=before_line,
            control_path=control_path,
            parents=parents,
            visited=visited,
        )
        if resolved is node:
            return [], lines
        fragments, nested_lines = _string_fragments(
            resolved,
            scope=scope,
            before_line=min(lines) if lines else before_line,
            control_path=control_path,
            parents=parents,
            visited=visited | {node.id},
        )
        return fragments, sorted({*lines, *nested_lines})
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value], []
    fragments: list[str] = []
    definition_lines: list[int] = []
    for child in ast.iter_child_nodes(node):
        child_fragments, child_lines = _string_fragments(
            child,
            scope=scope,
            before_line=before_line,
            control_path=control_path,
            parents=parents,
            visited=visited,
        )
        fragments.extend(child_fragments)
        definition_lines.extend(child_lines)
    return fragments, sorted(set(definition_lines))


def _setter_calls(
    scope: ast.AST,
    *,
    receiver: str,
    start_line: int,
    end_line: int,
    terminal_control_path: tuple[str, ...],
    parents: dict[ast.AST, ast.AST],
) -> dict[str, list[ast.Call]]:
    setters: dict[str, list[ast.Call]] = defaultdict(list)
    supported = {
        "setoutputformat",
        "setoutputproviderkey",
        "setcreateoptions",
        "setoutputdatasetname",
    }
    for node in ast.walk(scope):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        method = _method(node)
        if (
            method not in supported
            or _name(node.func.value) != receiver
            or not start_line < int(node.lineno) < end_line
            or not _control_paths_compatible(
                _control_path(node, parents), terminal_control_path
            )
        ):
            continue
        setters[method].append(node)
    return dict(setters)


def _literal_values(facts: list[dict[str, Any]]) -> set[str]:
    return {
        str(fact["value"]).strip().lower()
        for fact in facts
        if fact.get("status") == "literal" and isinstance(fact.get("value"), str)
    }


def _format_class(value: str) -> str:
    normalized = value.strip().lower().lstrip(".")
    if normalized in _GEOTIFF_FORMATS:
        return "geotiff"
    if normalized in _GPKG_FORMATS:
        return "gpkg_raster"
    if normalized in _IMAGE_FORMATS:
        return "display_image"
    return "other_raster_format"


def _path_classes(fragments: Iterable[str]) -> set[str]:
    classes: set[str] = set()
    for fragment in fragments:
        value = fragment.strip().lower()
        if "gpkg:" in value or ".gpkg" in value:
            classes.add("gpkg_raster")
        if any(suffix in value for suffix in _GEOTIFF_SUFFIXES):
            classes.add("geotiff")
        if any(suffix in value for suffix in _IMAGE_SUFFIXES):
            classes.add("display_image")
    return classes


def _contract(
    format_values: set[str], path_fragments: list[str]
) -> tuple[str, str, str]:
    explicit_classes = {_format_class(value) for value in format_values}
    path_classes = _path_classes(path_fragments)
    if len(explicit_classes) > 1:
        return "conflicting_format_setters", "deferred", "multiple_output_formats"
    if explicit_classes:
        contract_class = next(iter(explicit_classes))
        if path_classes and contract_class not in path_classes:
            return "conflicting_format_and_path", "deferred", "format_path_conflict"
        return contract_class, "source_backed", "explicit_output_format"
    if len(path_classes) > 1:
        return "conflicting_path_formats", "deferred", "multiple_path_formats"
    if path_classes:
        return next(iter(path_classes)), "source_backed", "output_path_evidence"
    return "dynamic_or_unknown_format", "deferred", "no_static_output_format"


def _evidence_snippet(source: str, lines: set[int]) -> str:
    source_lines = source.splitlines()
    valid = sorted(line for line in lines if 1 <= line <= len(source_lines))
    rendered: list[str] = []
    previous = 0
    for line in valid:
        if previous and line > previous + 1:
            rendered.append("...")
        rendered.append(f"{line} | {source_lines[line - 1]}")
        previous = line
    return "\n".join(rendered)


def classify_unit(row: dict[str, Any], source: str, payload: bytes) -> dict[str, Any]:
    expected_sha = str(row.get("source_sha256") or "")
    if _sha256_bytes(payload) != expected_sha:
        raise ValueError(f"source SHA mismatch for {row.get('unit_id')}")
    tree = ast.parse(source)
    parents = _parents(tree)
    expected_end = int((row.get("source_span") or [0, 0])[1])
    receiver = str(row.get("receiver") or "")
    terminals = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and _method(node) == "writeraster"
        and _name(node.func.value) == receiver
        and int(node.end_lineno or node.lineno) == expected_end
    ]
    if len(terminals) != 1:
        raise ValueError(
            f"expected one matching writeRaster terminal for {row.get('unit_id')}, got {len(terminals)}"
        )
    terminal = terminals[0]
    scope = _scope(terminal, parents)
    if _scope_name(scope, parents) != row.get("lexical_scope"):
        raise ValueError(f"lexical scope mismatch for {row.get('unit_id')}")
    start_line = int((row.get("source_span") or [0, 0])[0])
    constructor = next(
        (
            node
            for node in ast.walk(scope)
            if isinstance(node, ast.Call)
            and _method(node) == "qgsrasterfilewriter"
            and int(node.lineno) == start_line
        ),
        None,
    )
    if constructor is None:
        raise ValueError(f"writer constructor mismatch for {row.get('unit_id')}")

    terminal_path = _control_path(terminal, parents)
    setters = _setter_calls(
        scope,
        receiver=receiver,
        start_line=int(constructor.lineno),
        end_line=int(terminal.lineno),
        terminal_control_path=terminal_path,
        parents=parents,
    )
    fact_kwargs = {
        "scope": scope,
        "use_control_path": terminal_path,
        "parents": parents,
    }
    output_node = constructor.args[0] if constructor.args else None
    output_path_fact = _fact(
        output_node, before_line=int(constructor.lineno), **fact_kwargs
    )
    path_fragments, path_definition_lines = _string_fragments(
        output_node,
        scope=scope,
        before_line=int(constructor.lineno),
        control_path=terminal_path,
        parents=parents,
    )

    terminal_fact_names = (
        "pipe",
        "column_count",
        "row_count",
        "extent",
        "crs",
        "transform_context",
    )
    terminal_facts = {
        name: _fact(
            terminal.args[index] if index < len(terminal.args) else None,
            before_line=int(terminal.lineno),
            **fact_kwargs,
        )
        for index, name in enumerate(terminal_fact_names)
    }
    setter_facts: dict[str, list[dict[str, Any]]] = {}
    evidence_lines = {
        int(constructor.lineno),
        *range(int(terminal.lineno), int(terminal.end_lineno or terminal.lineno) + 1),
        *path_definition_lines,
        *[int(line) for line in output_path_fact.get("definition_lines", [])],
        *[
            int(line)
            for fact in terminal_facts.values()
            for line in fact.get("definition_lines", [])
        ],
    }
    creation_option_strings: list[str] = []
    for method, calls in setters.items():
        facts: list[dict[str, Any]] = []
        for call in calls:
            argument = call.args[0] if call.args else None
            fact = _fact(argument, before_line=int(call.lineno), **fact_kwargs)
            facts.append(fact)
            evidence_lines.update(
                range(int(call.lineno), int(call.end_lineno or call.lineno) + 1)
            )
            evidence_lines.update(int(line) for line in fact.get("definition_lines", []))
            if method == "setcreateoptions":
                fragments, definition_lines = _string_fragments(
                    argument,
                    scope=scope,
                    before_line=int(call.lineno),
                    control_path=terminal_path,
                    parents=parents,
                )
                creation_option_strings.extend(fragments)
                evidence_lines.update(definition_lines)
        setter_facts[method] = facts

    format_values = _literal_values(setter_facts.get("setoutputformat", []))
    contract_class, contract_status, contract_basis = _contract(
        format_values, path_fragments
    )
    exact_mapping = contract_class == "geotiff" and contract_status == "source_backed"
    evidence = _evidence_snippet(source, evidence_lines)
    return {
        **row,
        "schema": SCHEMA,
        "contract_rule_id": RULE_ID,
        "source_verification": "verified_sha256",
        "write_raster_overload": (
            "with_transform_context" if len(terminal.args) >= 6 else "without_transform_context"
        ),
        "write_raster_positional_arg_count": len(terminal.args),
        "output_path_fact": output_path_fact,
        "output_path_string_fragments": path_fragments,
        "output_format_facts": setter_facts.get("setoutputformat", []),
        "output_provider_key_facts": setter_facts.get("setoutputproviderkey", []),
        "creation_options_facts": setter_facts.get("setcreateoptions", []),
        "output_dataset_name_facts": setter_facts.get("setoutputdatasetname", []),
        "pipe_fact": terminal_facts["pipe"],
        "column_count_fact": terminal_facts["column_count"],
        "row_count_fact": terminal_facts["row_count"],
        "extent_fact": terminal_facts["extent"],
        "crs_fact": terminal_facts["crs"],
        "transform_context_fact": terminal_facts["transform_context"],
        "creation_option_strings": sorted(set(creation_option_strings)),
        "contract_class": contract_class,
        "contract_status": contract_status,
        "contract_basis": contract_basis,
        "mapping_status": (
            "exact_stable125_existing_l3" if exact_mapping else "deferred_no_exact_mapping"
        ),
        "candidate_l3_sequence": [GEOTIFF_L3] if exact_mapping else [],
        "contract_evidence_snippet": evidence,
        "contract_evidence_sha256": _sha256_bytes(evidence.encode("utf-8")),
        "training_admission": "not_granted_contract_census_only",
        "training_row_emitted": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }


def classify_path(row: dict[str, Any]) -> dict[str, Any]:
    source_path = Path(str(row.get("source_path") or ""))
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    payload = source_path.read_bytes()
    source = payload.decode("utf-8-sig", errors="replace")
    return classify_unit(row, source, payload)


def build_summary(
    rows: list[dict[str, Any]],
    *,
    existing_train_authorities: set[str],
    minimum_support: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    by_contract: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_contract[str(row["contract_class"])].append(row)
    census: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    for contract_class, contract_rows in sorted(by_contract.items()):
        authorities = {str(row["source_authority_key"]) for row in contract_rows}
        overlap = authorities & existing_train_authorities
        net_new = authorities - overlap
        exact = all(
            row.get("mapping_status") == "exact_stable125_existing_l3"
            for row in contract_rows
        )
        gate = (
            "eligible_for_source_disjoint_calibration"
            if exact and len(net_new) >= minimum_support
            else "deferred"
        )
        census.append(
            {
                "schema": "gis_recommend.qgis_api_raster_file_export_contract_summary.v1",
                "contract_rule_id": RULE_ID,
                "contract_class": contract_class,
                "unit_count": len(contract_rows),
                "source_authority_count": len(authorities),
                "existing_train_authority_overlap": len(overlap),
                "net_new_source_authority_count": len(net_new),
                "mapping_status": (
                    "exact_stable125_existing_l3" if exact else "deferred_mixed_or_unmapped"
                ),
                "candidate_l3_sequence": [GEOTIFF_L3] if exact else [],
                "minimum_support": minimum_support,
                "support_gate": gate,
                "training_admission": "not_granted_contract_census_only",
            }
        )
        if gate == "eligible_for_source_disjoint_calibration":
            eligible.extend(
                row
                for row in contract_rows
                if str(row["source_authority_key"]) in net_new
            )
    summary = {
        "schema": "gis_recommend.qgis_api_raster_file_export_contract_census_summary.v1",
        "contract_rule_id": RULE_ID,
        "input_complete_units": len(rows),
        "input_source_authorities": len(
            {str(row["source_authority_key"]) for row in rows}
        ),
        "source_verified_units": sum(
            row.get("source_verification") == "verified_sha256" for row in rows
        ),
        "contract_class_counts": dict(Counter(row["contract_class"] for row in rows)),
        "contract_status_counts": dict(Counter(row["contract_status"] for row in rows)),
        "eligible_units": len(eligible),
        "eligible_source_authorities": len(
            {str(row["source_authority_key"]) for row in eligible}
        ),
        "minimum_support": minimum_support,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_contract_census_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }
    return census, eligible, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-replay", type=Path, required=True)
    parser.add_argument("--existing-train-jsonl", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-complete-units", type=int, default=89)
    parser.add_argument("--expected-source-authorities", type=int, default=81)
    parser.add_argument("--minimum-support", type=int, default=30)
    parser.add_argument("--review-per-split", type=int, default=15)
    parser.add_argument("--seed", type=int, default=20260805)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")

    source_rows = [
        row
        for row in _read_jsonl(args.source_replay)
        if row.get("family_id") == "raster_file_export"
        and row.get("macro_status") == "complete"
    ]
    if len(source_rows) != args.expected_complete_units:
        raise ValueError(
            f"expected {args.expected_complete_units} complete units, got {len(source_rows)}"
        )
    authority_count = len({row["source_authority_key"] for row in source_rows})
    if authority_count != args.expected_source_authorities:
        raise ValueError(
            f"expected {args.expected_source_authorities} source authorities, got {authority_count}"
        )
    rows = [classify_path(row) for row in source_rows]
    existing_train_authorities = {
        str(row.get("source_authority_key") or "")
        for path in args.existing_train_jsonl
        for row in _read_jsonl(path)
        if row.get("source_authority_key")
    }
    census, eligible, summary = build_summary(
        rows,
        existing_train_authorities=existing_train_authorities,
        minimum_support=args.minimum_support,
    )
    calibration: list[dict[str, Any]] = []
    holdout: list[dict[str, Any]] = []
    if eligible:
        calibration, holdout = select_source_disjoint_review(
            eligible,
            per_split=args.review_per_split,
            seed=args.seed,
            max_units_per_source=1,
        )
    summary.update(
        {
            "review_seed": args.seed,
            "calibration_rows": len(calibration),
            "holdout_rows": len(holdout),
            "calibration_holdout_source_sha_overlap": len(
                {row["source_sha256"] for row in calibration}
                & {row["source_sha256"] for row in holdout}
            ),
            "calibration_holdout_source_authority_overlap": len(
                {row["source_authority_key"] for row in calibration}
                & {row["source_authority_key"] for row in holdout}
            ),
        }
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    artifact_rows = {
        "contract_replay_v1.jsonl": rows,
        "contract_census_v1.jsonl": census,
        "eligible_population_v1.jsonl": eligible,
        "calibration_review_v1.jsonl": calibration,
        "holdout_review_v1.jsonl": holdout,
    }
    paths: list[Path] = []
    for name, values in artifact_rows.items():
        path = args.output_dir / name
        _write_jsonl(path, values)
        paths.append(path)
    summary_path = args.output_dir / "summary_v1.json"
    _write_json(summary_path, summary)
    paths.append(summary_path)
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            "source_replay": {
                "path": str(args.source_replay),
                "sha256": _sha256(args.source_replay),
            },
            **{
                f"existing_train_{index}": {
                    "path": str(path),
                    "sha256": _sha256(path),
                }
                for index, path in enumerate(args.existing_train_jsonl)
            },
        },
        "artifacts": {
            path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
            for path in paths
        },
    }
    _write_json(args.output_dir / "hash_ledger_v1.json", ledger)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
