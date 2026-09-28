#!/usr/bin/env python3
"""Replay source-backed Add Field local macros with alias and scope evidence."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import tempfile
import tokenize
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_api_add_field_local_macro.v1"
SUMMARY_SCHEMA = "gis_recommend.qgis_api_add_field_local_macro_summary.v1"
RULE_ID = "add-field-existing-layer-local-macro-v1"
FAMILY_ID = "add_field_existing_layer"
L3_CODE = "L3_01_02_01"
L3_NAME = "Add Field"
MAX_MACRO_LINE_SPAN = 30
ADD_METHODS = {"addattribute", "addattributes"}
ADDITIONAL_SCOPE_SEMANTIC_METHODS = {
    "addfeature",
    "addfeatures",
    "buffer",
    "centroid",
    "changeattributevalue",
    "changeattributevalues",
    "deletefeature",
    "deletefeatures",
    "difference",
    "getfeatures",
    "intersection",
    "intersects",
    "setattribute",
    "setattributes",
    "setgeometry",
    "setrenderer",
    "simplify",
    "transform",
    "unaryunion",
    "updatefeature",
    "updatefeatures",
    "writeasvectorformat",
    "writeasvectorformatv2",
    "writeasvectorformatv3",
}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _source_text(raw: bytes) -> str:
    encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
    return raw.decode(encoding)


def _expr_name(node: ast.AST | None) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _expr_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _method_name(call: ast.Call) -> str:
    return call.func.attr.lower() if isinstance(call.func, ast.Attribute) else ""


def _receiver(call: ast.Call) -> ast.AST | None:
    return call.func.value if isinstance(call.func, ast.Attribute) else None


def _literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_memory_layer_constructor(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call) or _expr_name(node.func).lower() != "qgsvectorlayer":
        return False
    provider = _literal_string(node.args[2]) if len(node.args) >= 3 else None
    if provider and provider.lower() == "memory":
        return True
    for keyword in node.keywords:
        if keyword.arg in {"providerLib", "provider"}:
            value = _literal_string(keyword.value)
            if value and value.lower() == "memory":
                return True
    return False


def _field_names(call: ast.Call) -> list[str]:
    names: set[str] = set()
    for node in ast.walk(call):
        if not isinstance(node, ast.Call):
            continue
        if _expr_name(node.func).lower() != "qgsfield" or not node.args:
            continue
        name = _literal_string(node.args[0])
        if name:
            names.add(name)
    return sorted(names)


@dataclass(frozen=True)
class CallEvidence:
    call: ast.Call
    scope: str
    control_path: tuple[str, ...]


class EvidenceVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.scope_stack: list[str] = ["<module>"]
        self.control_stack: list[str] = []
        self.calls: list[CallEvidence] = []
        self.provider_bindings: dict[tuple[str, str], list[tuple[int, str]]] = {}
        self.memory_layer_bindings: set[tuple[str, str]] = set()

    @property
    def scope(self) -> str:
        return ".".join(self.scope_stack[1:]) or "<module>"

    def _visit_scope(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.scope_stack.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_scope(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_scope(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope_stack.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.scope_stack.pop()

    def _visit_control(self, node: ast.AST, label: str) -> None:
        self.control_stack.append(f"{label}@{getattr(node, 'lineno', 0)}")
        self.generic_visit(node)
        self.control_stack.pop()

    def visit_If(self, node: ast.If) -> None:
        self.visit(node.test)
        self.control_stack.append(f"if-body@{node.lineno}")
        for statement in node.body:
            self.visit(statement)
        self.control_stack.pop()
        self.control_stack.append(f"if-else@{node.lineno}")
        for statement in node.orelse:
            self.visit(statement)
        self.control_stack.pop()

    def visit_For(self, node: ast.For) -> None:
        self._visit_control(node, "for")

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._visit_control(node, "async-for")

    def visit_While(self, node: ast.While) -> None:
        self._visit_control(node, "while")

    def visit_Try(self, node: ast.Try) -> None:
        self._visit_control(node, "try")

    def visit_With(self, node: ast.With) -> None:
        self._visit_control(node, "with")

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self._visit_control(node, "async-with")

    def visit_Assign(self, node: ast.Assign) -> None:
        targets = [_expr_name(target) for target in node.targets]
        targets = [target for target in targets if target]
        value = node.value
        if isinstance(value, ast.Call) and _method_name(value) == "dataprovider":
            layer = _expr_name(_receiver(value))
            if layer:
                for target in targets:
                    self.provider_bindings.setdefault((self.scope, target), []).append(
                        (int(node.lineno), layer)
                    )
        if _is_memory_layer_constructor(value):
            for target in targets:
                self.memory_layer_bindings.add((self.scope, target))
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        target = _expr_name(node.target)
        value = node.value
        if target and value is not None and _is_memory_layer_constructor(value):
            self.memory_layer_bindings.add((self.scope, target))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        self.calls.append(
            CallEvidence(node, self.scope, tuple(self.control_stack))
        )
        self.generic_visit(node)


def _provider_layer(
    visitor: EvidenceVisitor,
    evidence: CallEvidence,
) -> tuple[str, str]:
    receiver = _receiver(evidence.call)
    if isinstance(receiver, ast.Call) and _method_name(receiver) == "dataprovider":
        layer = _expr_name(_receiver(receiver))
        return layer, "inline_data_provider"
    provider = _expr_name(receiver)
    if not provider:
        return "", "unresolved_provider_receiver"
    bindings = [
        (line, layer)
        for line, layer in visitor.provider_bindings.get((evidence.scope, provider), [])
        if line < int(evidence.call.lineno)
    ]
    if not bindings:
        return "", "unresolved_provider_alias"
    latest_line = max(line for line, _ in bindings)
    latest_layers = {layer for line, layer in bindings if line == latest_line}
    if len(latest_layers) != 1:
        return "", "ambiguous_provider_alias"
    return next(iter(latest_layers)), "provider_assignment"


def _snippet(text: str, start: int, end: int) -> str:
    lines = text.splitlines()
    first = max(1, start - 3)
    last = min(len(lines), end + 3)
    return "\n".join(
        f"{line_number} | {lines[line_number - 1]}"
        for line_number in range(first, last + 1)
    )


def _base_result(row: dict[str, Any], status: str) -> dict[str, Any]:
    return {
        **row,
        "schema": SCHEMA,
        "family_rule_id": RULE_ID,
        "selected_family_id": FAMILY_ID,
        "proposed_l3_code": L3_CODE,
        "proposed_l3_name": L3_NAME,
        "semantic_contract": (
            "add one or more fields with explicit properties to an existing "
            "vector layer and commit the schema update"
        ),
        "macro_boundary_status": status,
        "source_verification": "not_verified",
        "lexical_scope": "",
        "layer_alias": "",
        "provider_alias_provenance": "",
        "control_path": [],
        "field_names": [],
        "macro_line_start": 0,
        "macro_line_end": 0,
        "macro_line_span": 0,
        "source_snippet": "",
        "mapping_status": "existing_stable125_l3",
        "description_fidelity": "not_started",
        "deduplication": "not_started",
        "training_admission": "not_granted_source_replay_only",
        "training_row_emitted": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def replay_row(row: dict[str, Any]) -> list[dict[str, Any]]:
    path = Path(str(row.get("source_path") or ""))
    if not path.is_file():
        return [_base_result(row, "source_missing")]
    raw = path.read_bytes()
    actual_sha = _sha256_bytes(raw)
    if actual_sha != str(row.get("source_sha256") or ""):
        result = _base_result(row, "source_sha256_mismatch")
        result["actual_source_sha256"] = actual_sha
        return [result]
    try:
        text = _source_text(raw)
        tree = ast.parse(text, filename=str(path))
    except (SyntaxError, UnicodeDecodeError, LookupError) as error:
        result = _base_result(row, "source_parse_failure")
        result["source_parse_error"] = f"{type(error).__name__}: {error}"
        return [result]

    visitor = EvidenceVisitor()
    visitor.visit(tree)
    add_calls = [
        evidence
        for evidence in visitor.calls
        if _method_name(evidence.call) in ADD_METHODS
    ]
    update_calls = [
        evidence
        for evidence in visitor.calls
        if _method_name(evidence.call) == "updatefields"
    ]
    units: list[dict[str, Any]] = []
    deferred_reasons: Counter[str] = Counter()
    resolved_adds: list[tuple[CallEvidence, str, str, list[str]]] = []
    for add in add_calls:
        layer, provenance = _provider_layer(visitor, add)
        if not layer:
            deferred_reasons[provenance] += 1
            continue
        if (add.scope, layer) in visitor.memory_layer_bindings:
            deferred_reasons["local_memory_layer_creation"] += 1
            continue
        resolved_adds.append((add, layer, provenance, _field_names(add.call)))

    for update in update_calls:
        layer = _expr_name(_receiver(update.call))
        if not layer:
            continue
        update_line = int(update.call.lineno)
        previous_updates = [
            int(other.call.lineno)
            for other in update_calls
            if other.scope == update.scope
            and other.control_path == update.control_path
            and _expr_name(_receiver(other.call)) == layer
            and int(other.call.lineno) < update_line
        ]
        previous_update_line = max(previous_updates, default=0)
        committed_adds = [
            item
            for item in resolved_adds
            if item[0].scope == update.scope
            and item[0].control_path == update.control_path
            and item[1] == layer
            and previous_update_line < int(item[0].call.lineno) <= update_line
            and update_line - int(item[0].call.lineno) <= MAX_MACRO_LINE_SPAN
        ]
        if not committed_adds:
            continue
        start = min(int(item[0].call.lineno) for item in committed_adds)
        end = int(update.call.end_lineno or update.call.lineno)
        field_names = sorted(
            {name for _, _, _, names in committed_adds for name in names}
        )
        all_field_names_literal = all(names for _, _, _, names in committed_adds)
        scope_methods = {
            _method_name(evidence.call)
            for evidence in visitor.calls
            if evidence.scope == update.scope and _method_name(evidence.call)
        }
        additional_semantics = sorted(
            scope_methods & ADDITIONAL_SCOPE_SEMANTIC_METHODS
        )
        unit_key = (
            f"{row.get('source_authority_key')}:{update.scope}:{layer}:{start}:{end}"
        )
        result = _base_result(row, "verified_complete_existing_layer_macro")
        result.update(
            {
                "source_verification": "verified_sha256",
                "lexical_scope": update.scope,
                "layer_alias": layer,
                "provider_alias_provenance": "+".join(
                    sorted({item[2] for item in committed_adds})
                ),
                "control_path": list(update.control_path),
                "field_names": field_names,
                "field_name_fidelity": (
                    "literal_names_verified"
                    if all_field_names_literal
                    else "dynamic_names_deferred"
                ),
                "schema_add_call_count": len(committed_adds),
                "scope_semantic_methods": sorted(scope_methods),
                "excluded_additional_scope_semantics": additional_semantics,
                "macro_line_start": start,
                "macro_line_end": end,
                "macro_line_span": end - start + 1,
                "source_snippet": _snippet(text, start, end),
                "candidate_unit_id": hashlib.sha256(unit_key.encode()).hexdigest()[:24],
            }
        )
        if not all_field_names_literal:
            result["macro_boundary_status"] = "deferred_dynamic_field_names"
        elif additional_semantics:
            result["macro_boundary_status"] = "deferred_additional_scope_semantics"
        units.append(result)

    matched_add_ids = {
        id(item[0].call)
        for unit in units
        for item in resolved_adds
        if item[0].scope == unit["lexical_scope"]
        and item[1] == unit["layer_alias"]
        and int(unit["macro_line_start"])
        <= int(item[0].call.lineno)
        <= int(unit["macro_line_end"])
    }
    unmatched_adds = [item for item in resolved_adds if id(item[0].call) not in matched_add_ids]
    if unmatched_adds:
        deferred_reasons["missing_same_alias_ordered_update"] += len(unmatched_adds)

    if units:
        unique: dict[str, dict[str, Any]] = {}
        for unit in units:
            key = str(unit.get("candidate_unit_id") or "")
            unique[key] = unit
        return list(unique.values())
    result = _base_result(row, "deferred_no_complete_existing_layer_macro")
    result["source_verification"] = "verified_sha256"
    result["deferred_reason_counts"] = dict(sorted(deferred_reasons.items()))
    result["add_call_count"] = len(add_calls)
    result["update_fields_call_count"] = len(update_calls)
    return [result]


def _rank(row: dict[str, Any], seed: int) -> tuple[str, str]:
    authority = str(row.get("source_authority_key") or "")
    unit = str(row.get("candidate_unit_id") or "")
    return hashlib.sha256(f"{seed}:{authority}:{unit}".encode()).hexdigest(), unit


def select_source_disjoint_review(
    rows: list[dict[str, Any]], *, per_split: int, seed: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eligible = [
        row
        for row in rows
        if row.get("macro_boundary_status")
        == "verified_complete_existing_layer_macro"
    ]
    eligible.sort(key=lambda row: _rank(row, seed))
    selected: list[dict[str, Any]] = []
    used_sources: set[str] = set()
    used_bodies: set[str] = set()
    for row in eligible:
        source_sha = str(row.get("source_sha256") or "")
        body_sha = str(row.get("normalized_source_body_sha256") or "")
        if not source_sha or not body_sha:
            continue
        if source_sha in used_sources or body_sha in used_bodies:
            continue
        selected.append(row)
        used_sources.add(source_sha)
        used_bodies.add(body_sha)
        if len(selected) == per_split * 2:
            break
    if len(selected) < per_split * 2:
        raise ValueError(
            f"need {per_split * 2} source-disjoint rows, found {len(selected)}"
        )
    calibration = [
        {**row, "review_split": "calibration"} for row in selected[:per_split]
    ]
    holdout = [
        {**row, "review_split": "holdout"} for row in selected[per_split:]
    ]
    return calibration, holdout


def replay_rows(
    rows: Iterable[dict[str, Any]], *, review_per_split: int = 0, seed: int = 20260805
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    population = [result for row in rows for result in replay_row(row)]
    status_counts = Counter(str(row["macro_boundary_status"]) for row in population)
    calibration: list[dict[str, Any]] = []
    holdout: list[dict[str, Any]] = []
    if review_per_split:
        calibration, holdout = select_source_disjoint_review(
            population, per_split=review_per_split, seed=seed
        )
    input_authorities = {
        str(row.get("source_authority_key") or "") for row in population
    }
    complete = [
        row
        for row in population
        if row["macro_boundary_status"]
        == "verified_complete_existing_layer_macro"
    ]
    summary = {
        "schema": SUMMARY_SCHEMA,
        "family_rule_id": RULE_ID,
        "input_authorities": len(input_authorities),
        "population_rows": len(population),
        "source_replay_status_counts": dict(sorted(status_counts.items())),
        "verified_source_sha256_authorities": len(
            {
                str(row.get("source_authority_key") or "")
                for row in population
                if row.get("source_verification") == "verified_sha256"
            }
        ),
        "complete_macro_units": len(complete),
        "complete_macro_source_authorities": len(
            {str(row.get("source_authority_key") or "") for row in complete}
        ),
        "literal_field_name_units": sum(bool(row.get("field_names")) for row in complete),
        "proposed_l3_code": L3_CODE,
        "calibration_rows": len(calibration),
        "holdout_rows": len(holdout),
        "calibration_holdout_source_sha_overlap": len(
            {str(row["source_sha256"]) for row in calibration}
            & {str(row["source_sha256"]) for row in holdout}
        ),
        "calibration_holdout_normalized_body_overlap": len(
            {str(row["normalized_source_body_sha256"]) for row in calibration}
            & {str(row["normalized_source_body_sha256"]) for row in holdout}
        ),
        "review_seed": seed,
        "description_fidelity_rows": 0,
        "training_admission": "not_granted_source_replay_only",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }
    return population, calibration, holdout, summary


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _recorded_method_set(row: dict[str, Any]) -> set[str]:
    return {
        str(step.get("name") or "").rsplit(".", 1)[-1].lower()
        for step in row.get("steps") or []
    }


def _is_recorded_family_candidate(row: dict[str, Any]) -> bool:
    methods = _recorded_method_set(row)
    return bool(methods & ADD_METHODS) and "updatefields" in methods


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def _write_review_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "review_split",
        "candidate_unit_id",
        "record_id",
        "source_root_id",
        "source_path",
        "source_sha256",
        "normalized_source_body_sha256",
        "source_authority_key",
        "lexical_scope",
        "layer_alias",
        "provider_alias_provenance",
        "control_path",
        "field_names",
        "macro_line_start",
        "macro_line_end",
        "proposed_l3_code",
        "macro_boundary_status",
        "source_snippet",
        "human_boundary_decision",
        "human_mapping_decision",
        "human_description_fidelity",
        "human_notes",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "control_path": json.dumps(row.get("control_path") or []),
                    "field_names": json.dumps(row.get("field_names") or [], ensure_ascii=False),
                    "human_boundary_decision": "",
                    "human_mapping_decision": "",
                    "human_description_fidelity": "",
                    "human_notes": "",
                }
            )
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-jsonl", type=Path, required=True)
    parser.add_argument("--exclude-jsonl", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-input-authorities", type=int)
    parser.add_argument("--expected-classified-authorities", type=int)
    parser.add_argument("--review-per-split", type=int, default=0)
    parser.add_argument("--seed", type=int, default=20260805)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows = _read_jsonl(args.input_jsonl)
    if args.expected_input_authorities is not None and len(rows) != args.expected_input_authorities:
        raise ValueError(
            f"expected {args.expected_input_authorities} rows, got {len(rows)}"
        )
    excluded = {
        str(row.get("source_authority_key") or "")
        for path in args.exclude_jsonl
        for row in _read_jsonl(path)
        if row.get("source_authority_key")
    }
    classified_rows = [
        row
        for row in rows
        if str(row.get("source_authority_key") or "") not in excluded
    ]
    if (
        args.expected_classified_authorities is not None
        and len(classified_rows) != args.expected_classified_authorities
    ):
        raise ValueError(
            f"expected {args.expected_classified_authorities} classified authorities, "
            f"got {len(classified_rows)}"
        )
    screened_rows = [row for row in classified_rows if _is_recorded_family_candidate(row)]
    population, calibration, holdout, summary = replay_rows(
        screened_rows, review_per_split=args.review_per_split, seed=args.seed
    )
    summary.update(
        {
            "input_candidate_authorities": len(rows),
            "excluded_authorities": len(excluded),
            "classified_authorities": len(classified_rows),
            "recorded_method_screened_authorities": len(screened_rows),
        }
    )
    artifacts: list[Path] = []
    for name, values in (
        ("population_v1.jsonl", population),
        ("calibration_review_v1.jsonl", calibration),
        ("holdout_review_v1.jsonl", holdout),
    ):
        path = args.output_dir / name
        _write_jsonl(path, values)
        artifacts.append(path)
    for name, values in (
        ("calibration_review_v1.csv", calibration),
        ("holdout_review_v1.csv", holdout),
    ):
        path = args.output_dir / name
        _write_review_csv(path, values)
        artifacts.append(path)
    summary_path = args.output_dir / "summary_v1.json"
    _write_json(summary_path, summary)
    artifacts.append(summary_path)
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            args.input_jsonl.name: {
                "path": str(args.input_jsonl),
                "sha256": _sha256(args.input_jsonl),
            },
            **{
                path.name: {"path": str(path), "sha256": _sha256(path)}
                for path in args.exclude_jsonl
            },
        },
        "artifacts": {
            path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
            for path in artifacts
        },
    }
    _write_json(args.output_dir / "hash_ledger_v1.json", ledger)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
