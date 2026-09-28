#!/usr/bin/env python3
"""Census local geometry producers upstream of mutation/export-only QGIS units."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "gis_recommend.qgis_api_mutation_upstream_census.v4"
ANALYSIS_RULE_ID = "control-path-caller-and-terminal-backward-slice-v4"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return _name(node.func)
    if isinstance(node, ast.Subscript):
        return _name(node.value)
    return ""


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }


def _scope_node(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.AST:
    current: ast.AST | None = node
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return current
        current = parents.get(current)
    current = node
    while parents.get(current) is not None:
        current = parents[current]
    return current


def _control_path(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> tuple[str, ...]:
    path = []
    current: ast.AST | None = node
    while current is not None:
        parent = parents.get(current)
        if isinstance(parent, ast.If):
            arm = "body" if current in parent.body else "orelse"
            path.append(f"if:{parent.lineno}:{arm}")
        current = parent
    return tuple(reversed(path))


def _loaded_names(node: ast.AST) -> set[str]:
    return {
        item.id
        for item in ast.walk(node)
        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)
    }


def _assignment_value(node: ast.AST) -> ast.AST | None:
    if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
        return node.value
    return None


def _assignment_targets(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)):
        targets = [node.target]
    else:
        return set()
    return {
        item.id
        for target in targets
        for item in ast.walk(target)
        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store)
    }


def _definitions(
    scope: ast.AST, parents: dict[ast.AST, ast.AST], before_line: int
) -> dict[str, list[dict[str, Any]]]:
    values: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in ast.walk(scope):
        value = _assignment_value(node)
        if value is None or int(getattr(node, "lineno", 0)) >= before_line:
            continue
        if _scope_node(node, parents) is not scope:
            continue
        for name in _assignment_targets(node):
            values[name].append(
                {
                    "line": int(node.lineno),
                    "control_path": _control_path(node, parents),
                    "value": value,
                }
            )
    return {
        name: sorted(rows, key=lambda row: row["line"])
        for name, rows in values.items()
    }


def _reaching_definitions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    unconditional = [row for row in rows if not row["control_path"]]
    if unconditional:
        last = unconditional[-1]
        later = [row for row in rows if row["line"] > last["line"]]
        return later or [last]
    return rows


def _calls_in_expression(node: ast.AST) -> list[ast.Call]:
    calls = [item for item in ast.walk(node) if isinstance(item, ast.Call)]
    return sorted(
        calls,
        key=lambda call: (
            int(call.lineno),
            int(call.col_offset),
            int(call.end_lineno or call.lineno),
            int(call.end_col_offset or call.col_offset),
        ),
    )


def _call_family(call_name: str) -> str:
    lowered = call_name.lower()
    method = lowered.rsplit(".", 1)[-1]
    if lowered.startswith("qgsgeometry.from"):
        return "qgsgeometry_factory"
    if method in {"geometry", "constgeometry"}:
        return "geometry_accessor"
    if method in {
        "buffer",
        "centroid",
        "combine",
        "convexhull",
        "difference",
        "intersection",
        "interpolate",
        "makevalid",
        "offsetcurve",
        "simplify",
        "smooth",
        "symdifference",
        "transform",
        "unaryunion",
    }:
        return "geometry_method"
    if lowered.startswith("qgs"):
        return "qgis_other"
    return "external_or_custom"


def _normalized_call_name(call_name: str) -> str:
    normalized = call_name.lower()
    root = normalized.split(".", 1)[0]
    if root in {"qgsfeature", "qgsgeometry", "qgspoint", "qgspointxy", "qgsrectangle"}:
        return normalized
    return normalized.rsplit(".", 1)[-1]


def _slice_payload(
    expression: ast.AST,
    definitions: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], bool, list[dict[str, Any]]]:
    def collect(
        node: ast.AST, visited: frozenset[str]
    ) -> tuple[dict[tuple[int, str], dict[str, Any]], bool, list[dict[str, Any]]]:
        calls: dict[tuple[int, str], dict[str, Any]] = {}
        ambiguous = False
        equivalent_branches: list[dict[str, Any]] = []
        for call in _calls_in_expression(node):
            call_name = _name(call.func)
            if not call_name:
                continue
            calls[(int(call.lineno), call_name)] = {
                "call_name": call_name,
                "line_start": int(call.lineno),
                "line_end": int(call.end_lineno or call.lineno),
                "call_family": _call_family(call_name),
            }
        for name in sorted(_loaded_names(node)):
            if name in visited or name not in definitions:
                continue
            reaching = _reaching_definitions(definitions[name])
            alternatives = [
                collect(definition["value"], visited | {name})
                for definition in reaching
            ]
            signatures = [
                tuple(
                    _normalized_call_name(item["call_name"])
                    for item in sorted(
                        alternative_calls.values(),
                        key=lambda item: (item["line_start"], item["call_name"]),
                    )
                )
                for alternative_calls, _, _ in alternatives
            ]
            equivalent = (
                len(alternatives) > 1
                and bool(signatures[0])
                and len(set(signatures)) == 1
                and not any(item[1] for item in alternatives)
            )
            selected = alternatives[:1] if equivalent else alternatives
            if len(alternatives) > 1 and not equivalent:
                ambiguous = True
            if equivalent:
                equivalent_branches.append(
                    {
                        "payload_name": name,
                        "alternative_count": len(alternatives),
                        "normalized_call_signature": list(signatures[0]),
                    }
                )
            for alternative_calls, alternative_ambiguous, branch_evidence in selected:
                calls.update(alternative_calls)
                ambiguous = ambiguous or alternative_ambiguous
                equivalent_branches.extend(branch_evidence)
        return calls, ambiguous, equivalent_branches

    calls, ambiguous, equivalent_branches = collect(expression, frozenset())
    ordered = [calls[key] for key in sorted(calls)]
    return ordered, ambiguous, equivalent_branches


def _enclosing_class(
    node: ast.AST, parents: dict[ast.AST, ast.AST]
) -> ast.ClassDef | None:
    current: ast.AST | None = node
    while current is not None:
        if isinstance(current, ast.ClassDef):
            return current
        current = parents.get(current)
    return None


def _caller_argument(
    call: ast.Call, target: ast.FunctionDef | ast.AsyncFunctionDef, parameter: str
) -> ast.AST | None:
    for keyword in call.keywords:
        if keyword.arg == parameter:
            return keyword.value
    positional = [*target.args.posonlyargs, *target.args.args]
    names = [argument.arg for argument in positional]
    if parameter not in names:
        return None
    index = names.index(parameter)
    if (
        names
        and names[0] in {"self", "cls"}
        and isinstance(call.func, ast.Attribute)
    ):
        index -= 1
    return call.args[index] if 0 <= index < len(call.args) else None


def _matching_local_call(
    call: ast.Call,
    target: ast.FunctionDef | ast.AsyncFunctionDef,
    target_class: ast.ClassDef | None,
    parents: dict[ast.AST, ast.AST],
) -> bool:
    if _scope_node(call, parents) is target:
        return False
    if target_class is None:
        return isinstance(call.func, ast.Name) and call.func.id == target.name
    return (
        isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id in {"self", "cls"}
        and call.func.attr == target.name
        and _enclosing_class(call, parents) is target_class
    )


def _slice_caller_payload(
    tree: ast.AST,
    target: ast.FunctionDef | ast.AsyncFunctionDef,
    parameter: str,
    parents: dict[ast.AST, ast.AST],
) -> tuple[list[dict[str, Any]], bool, dict[str, Any] | None]:
    target_class = _enclosing_class(target, parents)
    call_sites = sorted(
        (
            call
            for call in ast.walk(tree)
            if isinstance(call, ast.Call)
            and _matching_local_call(call, target, target_class, parents)
        ),
        key=lambda call: (call.lineno, call.col_offset),
    )
    alternatives = []
    incomplete = 0
    for call in call_sites:
        argument = _caller_argument(call, target, parameter)
        if argument is None:
            incomplete += 1
            continue
        caller_scope = _scope_node(call, parents)
        definitions = _definitions(caller_scope, parents, int(call.lineno))
        calls, ambiguous, branch_evidence = _slice_payload(argument, definitions)
        if not calls:
            incomplete += 1
            continue
        alternatives.append((call, calls, ambiguous, branch_evidence))
    if not call_sites:
        return [], False, None

    signatures = [
        tuple(_normalized_call_name(item["call_name"]) for item in calls)
        for _, calls, _, _ in alternatives
    ]
    equivalent = (
        bool(alternatives)
        and incomplete == 0
        and len(set(signatures)) == 1
        and not any(ambiguous for _, _, ambiguous, _ in alternatives)
    )
    selected = alternatives[:1] if equivalent else alternatives
    merged = {
        (item["line_start"], item["call_name"]): item
        for _, calls, _, _ in selected
        for item in calls
    }
    evidence = {
        "parameter": parameter,
        "local_call_site_count": len(call_sites),
        "recovered_call_site_count": len(alternatives),
        "equivalent_call_sites": equivalent,
        "normalized_call_signatures": [list(signature) for signature in signatures],
    }
    ambiguous = not equivalent
    return [merged[key] for key in sorted(merged)], ambiguous, evidence


def _slice_terminal_payload(
    candidate: dict[str, Any],
    tree: ast.AST,
    parents: dict[ast.AST, ast.AST],
) -> tuple[list[dict[str, Any]], str]:
    terminal_targets = {
        (int(step["line_start"]), str(step.get("call_name") or "").lower())
        for step in candidate.get("steps") or []
        if step.get("call_role") == "sink_output"
    }
    target_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and any(
            int(node.lineno) == line
            and _name(node.func).lower().endswith(call_name.rsplit(".", 1)[-1])
            for line, call_name in terminal_targets
        )
    ]
    upstream: dict[tuple[int, str], dict[str, Any]] = {}
    ambiguous = False
    for call in target_calls:
        if not call.args:
            continue
        definitions = _definitions(_scope_node(call, parents), parents, int(call.lineno))
        calls, payload_ambiguous, _ = _slice_payload(call.args[0], definitions)
        ambiguous = ambiguous or payload_ambiguous
        for item in calls:
            upstream[(item["line_start"], item["call_name"])] = item
    ordered = [upstream[key] for key in sorted(upstream)]
    if ambiguous:
        status = "ambiguous_terminal_payload"
    elif any(
        item["call_family"] in {"geometry_method", "qgsgeometry_factory"}
        for item in ordered
    ):
        status = "known_geometry_semantic_candidate"
    elif ordered:
        status = "support_or_custom_only"
    else:
        status = "no_local_terminal_payload_chain"
    return ordered, status


def analyze_candidate_source(
    candidate: dict[str, Any],
    source_text: str,
    *,
    source_bytes: bytes | None = None,
) -> dict[str, Any]:
    if candidate.get("mapping_status") != "mutation_export_only":
        raise ValueError("expected mutation_export_only candidate")
    actual_sha = _sha256_bytes(
        source_bytes if source_bytes is not None else source_text.encode("utf-8")
    )
    if actual_sha != str(candidate.get("source_sha256") or ""):
        raise ValueError("source SHA mismatch")

    tree = ast.parse(source_text)
    parents = _parents(tree)
    target_lines = {
        int(step["line_start"])
        for step in candidate.get("steps") or []
        if step.get("call_role") == "feature_mutation"
        and str(step.get("call_name") or "").lower().endswith(".setgeometry")
    }
    target_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and int(node.lineno) in target_lines
        and _name(node.func).lower().endswith(".setgeometry")
    ]
    upstream: dict[tuple[int, str], dict[str, Any]] = {}
    payload_names: set[str] = set()
    equivalent_branches: list[dict[str, Any]] = []
    caller_payload_provenance: list[dict[str, Any]] = []
    ambiguous = False
    for call in sorted(target_calls, key=lambda node: (node.lineno, node.col_offset)):
        if not call.args:
            continue
        expression = call.args[0]
        payload_names.update(_loaded_names(expression))
        definitions = _definitions(_scope_node(call, parents), parents, int(call.lineno))
        calls, payload_ambiguous, branch_evidence = _slice_payload(
            expression, definitions
        )
        ambiguous = ambiguous or payload_ambiguous
        equivalent_branches.extend(branch_evidence)
        for item in calls:
            upstream[(item["line_start"], item["call_name"])] = item

        if not calls and not payload_ambiguous:
            target_scope = _scope_node(call, parents)
            if isinstance(target_scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for payload_name in sorted(_loaded_names(expression)):
                    caller_calls, caller_ambiguous, provenance = _slice_caller_payload(
                        tree, target_scope, payload_name, parents
                    )
                    if provenance is not None:
                        caller_payload_provenance.append(provenance)
                    ambiguous = ambiguous or caller_ambiguous
                    for item in caller_calls:
                        upstream[(item["line_start"], item["call_name"])] = item

    ordered = [upstream[key] for key in sorted(upstream)]
    terminal_payload_calls: list[dict[str, Any]] = []
    terminal_payload_status = "not_applicable_setgeometry_present"
    if not target_calls:
        status = "setgeometry_call_span_not_found"
        terminal_payload_calls, terminal_payload_status = _slice_terminal_payload(
            candidate, tree, parents
        )
    elif ambiguous:
        status = "ambiguous_multiple_reaching_definitions"
    elif ordered:
        status = "resolved_local_call_chain"
    else:
        status = "external_payload_no_local_producer"

    return {
        **candidate,
        "schema": SCHEMA,
        "analysis_rule_id": ANALYSIS_RULE_ID,
        "source_verification": "verified_sha256",
        "slice_status": status,
        "geometry_payload_names": sorted(payload_names),
        "equivalent_branch_definitions": equivalent_branches,
        "caller_payload_provenance": caller_payload_provenance,
        "upstream_calls": ordered,
        "upstream_call_names": [item["call_name"] for item in ordered],
        "upstream_call_lines": [item["line_start"] for item in ordered],
        "upstream_signature": [item["call_name"].lower() for item in ordered],
        "upstream_call_families": sorted({item["call_family"] for item in ordered}),
        "terminal_payload_status": terminal_payload_status,
        "terminal_payload_calls": terminal_payload_calls,
        "terminal_payload_signature": [
            _normalized_call_name(item["call_name"])
            for item in terminal_payload_calls
        ],
        "mapping_admission": "not_granted_upstream_census_only",
        "description_fidelity": "not_started",
        "deduplication": "normalized_source_body_clustered_for_census",
        "training_admission": "not_granted_upstream_census_only",
        "training_row_emitted": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }


def analyze_candidate_path(candidate: dict[str, Any]) -> dict[str, Any]:
    source_path = Path(str(candidate.get("source_path") or ""))
    if not source_path.is_file():
        return {
            **candidate,
            "schema": SCHEMA,
            "analysis_rule_id": ANALYSIS_RULE_ID,
            "source_verification": "source_file_missing",
            "slice_status": "source_unavailable",
            "geometry_payload_names": [],
            "equivalent_branch_definitions": [],
            "caller_payload_provenance": [],
            "upstream_calls": [],
            "upstream_call_names": [],
            "upstream_call_lines": [],
            "upstream_signature": [],
            "upstream_call_families": [],
            "terminal_payload_status": "source_unavailable",
            "terminal_payload_calls": [],
            "terminal_payload_signature": [],
            "mapping_admission": "not_granted_source_unavailable",
            "description_fidelity": "not_started",
            "deduplication": "not_started",
            "training_admission": "not_granted_source_unavailable",
            "training_row_emitted": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "llm_called": False,
        }
    payload = source_path.read_bytes()
    return analyze_candidate_source(
        candidate,
        payload.decode("utf-8-sig", errors="replace"),
        source_bytes=payload,
    )


def build_census(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(rows)
    status_counts = Counter(str(row["slice_status"]) for row in rows)
    terminal_status_counts = Counter(
        str(row.get("terminal_payload_status") or "not_recorded")
        for row in rows
        if row["slice_status"] == "setgeometry_call_span_not_found"
    )
    signature_units = Counter(tuple(row["upstream_signature"]) for row in rows)
    signature_authorities: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for row in rows:
        signature_authorities[tuple(row["upstream_signature"])].add(
            str(row["source_authority_key"])
        )
    signatures = [
        {
            "upstream_signature": list(signature),
            "unit_count": count,
            "source_authority_count": len(signature_authorities[signature]),
        }
        for signature, count in sorted(
            signature_units.items(), key=lambda item: (-item[1], item[0])
        )
    ]
    return {
        "schema": "gis_recommend.qgis_api_mutation_upstream_summary.v4",
        "analysis_rule_id": ANALYSIS_RULE_ID,
        "input_units": len(rows),
        "source_authorities": len({str(row["source_authority_key"]) for row in rows}),
        "slice_status_counts": dict(sorted(status_counts.items())),
        "terminal_payload_status_counts": dict(sorted(terminal_status_counts.items())),
        "upstream_signature_count": len(signatures),
        "signature_census": signatures,
        "mapping_rows_emitted": 0,
        "description_fidelity_rows": 0,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_upstream_census_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }


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


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping-deferred", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-rows", type=int, default=2605)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")

    candidates = [
        row
        for row in _read_jsonl(args.mapping_deferred)
        if row.get("mapping_status") == "mutation_export_only"
    ]
    if len(candidates) != args.expected_rows:
        raise ValueError(
            f"mutation/export row count {len(candidates)} != expected {args.expected_rows}"
        )

    analyzed = []
    for candidate in candidates:
        analyzed.append(analyze_candidate_path(candidate))

    summary = build_census(analyzed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows_path = args.output_dir / "mutation_upstream_census_v1.jsonl"
    signatures_path = args.output_dir / "upstream_signature_census_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    _write_jsonl(rows_path, analyzed)
    _write_jsonl(signatures_path, summary.pop("signature_census"))
    _atomic_write(
        summary_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    artifacts = (rows_path, signatures_path, summary_path)
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            "mapping_deferred": {
                "path": str(args.mapping_deferred),
                "bytes": args.mapping_deferred.stat().st_size,
                "sha256": _sha256(args.mapping_deferred),
            }
        },
        "artifacts": {
            path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
            for path in artifacts
        },
    }
    _atomic_write(
        args.output_dir / "hash_ledger_v1.json",
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
