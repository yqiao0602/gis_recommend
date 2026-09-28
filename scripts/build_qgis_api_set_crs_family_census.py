#!/usr/bin/env python3
"""Replay a strict local QGIS layer ``setCrs`` metadata-assignment family."""

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

SCHEMA = "gis_recommend.qgis_api_set_crs_census.v1"
RULE_ID = "qgis-api-local-layer-set-crs-metadata-v1"
L3_CODE = "L3_01_10_02"
LAYER_CONSTRUCTORS = {"qgsvectorlayer", "qgsrasterlayer"}


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
    return ""


def _method(call: ast.Call) -> str:
    return _name(call.func).rsplit(".", 1)[-1].lower()


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }


def _scope(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.AST:
    current: ast.AST | None = node
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return current
        current = parents.get(current)
    current = node
    while current in parents:
        current = parents[current]
    return current


def _scope_name(scope: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    if isinstance(scope, ast.Module):
        return "<module>"
    names: list[str] = []
    current: ast.AST | None = scope
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(current.name)
        elif isinstance(current, ast.Lambda):
            names.append(f"<lambda:{current.lineno}>")
        current = parents.get(current)
    return ".".join(reversed(names))


def _assignment_value(node: ast.AST) -> ast.AST | None:
    if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
        return node.value
    return None


def _target_names(node: ast.AST) -> set[str]:
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
    scope: ast.AST,
    name: str,
    *,
    before_line: int,
    parents: dict[ast.AST, ast.AST],
) -> list[tuple[int, ast.AST]]:
    return sorted(
        (int(node.lineno), value)
        for node in ast.walk(scope)
        if (value := _assignment_value(node)) is not None
        and name in _target_names(node)
        and int(node.lineno) < before_line
        and _scope(node, parents) is scope
    )


def _local_layer_constructor(
    scope: ast.AST,
    receiver: str,
    *,
    before_line: int,
    parents: dict[ast.AST, ast.AST],
) -> tuple[int, ast.Call] | None:
    if not receiver or "." in receiver:
        return None
    definitions = _definitions(
        scope, receiver, before_line=before_line, parents=parents
    )
    if len(definitions) != 1:
        return None
    line, value = definitions[0]
    if not isinstance(value, ast.Call) or _method(value) not in LAYER_CONSTRUCTORS:
        return None
    return line, value


def _fact(
    node: ast.AST | None,
    *,
    scope: ast.AST,
    before_line: int,
    parents: dict[ast.AST, ast.AST],
    visited: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    if node is None:
        return {"status": "missing", "source": ""}
    if isinstance(node, ast.Name) and node.id not in visited:
        definitions = _definitions(
            scope, node.id, before_line=before_line, parents=parents
        )
        signatures = {ast.dump(value, include_attributes=False) for _, value in definitions}
        if len(signatures) == 1:
            line, value = definitions[-1]
            resolved = _fact(
                value,
                scope=scope,
                before_line=line,
                parents=parents,
                visited=visited | {node.id},
            )
            return {
                **resolved,
                "resolved_from": node.id,
                "definition_lines": sorted(
                    {line, *resolved.get("definition_lines", [])}
                ),
            }
        if len(signatures) > 1:
            return {
                "status": "ambiguous_reaching_definitions",
                "source": node.id,
                "definition_lines": sorted(line for line, _ in definitions),
            }
        return {"status": "unresolved_name_reference", "source": node.id}
    if isinstance(node, ast.Constant):
        return {"status": "literal", "source": repr(node.value), "value": node.value}
    if isinstance(node, ast.JoinedStr):
        return {"status": "fstring", "source": ast.unparse(node)}
    if isinstance(node, ast.Call):
        method = _method(node)
        source = ast.unparse(node)
        if method in {"qgscoordinatereferencesystem", "fromepsgid", "fromogcurn"}:
            value_fact = _fact(
                node.args[0] if node.args else None,
                scope=scope,
                before_line=int(node.lineno),
                parents=parents,
                visited=visited,
            )
            return {
                "status": "crs_constructor",
                "constructor": _name(node.func),
                "source": source,
                "value_fact": value_fact,
            }
        if method in {"createfromid", "createfromstring", "createfromwkt"}:
            return {"status": "crs_mutator_expression", "source": source}
        return {"status": "source_expression", "source": source}
    if isinstance(node, ast.Attribute):
        return {"status": "source_expression", "source": ast.unparse(node)}
    if isinstance(node, ast.Subscript):
        return {"status": "dynamic_subscript", "source": ast.unparse(node)}
    return {"status": "unsupported_expression", "source": ast.unparse(node)}


def analyze_source(
    row: dict[str, Any], source_text: str, *, source_bytes: bytes | None = None
) -> list[dict[str, Any]]:
    actual_sha = _sha256_bytes(
        source_bytes if source_bytes is not None else source_text.encode("utf-8")
    )
    if actual_sha != str(row.get("source_sha256") or ""):
        raise ValueError("source SHA mismatch")
    tree = ast.parse(source_text)
    parents = _parents(tree)
    source_lines = source_text.splitlines()
    units: list[dict[str, Any]] = []
    calls = sorted(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and _method(node) == "setcrs"
            and isinstance(node.func, ast.Attribute)
        ),
        key=lambda node: (node.lineno, node.col_offset),
    )
    for call in calls:
        scope = _scope(call, parents)
        receiver = _name(call.func.value)
        constructor = _local_layer_constructor(
            scope,
            receiver,
            before_line=int(call.lineno),
            parents=parents,
        )
        crs_fact = _fact(
            call.args[0] if call.args else None,
            scope=scope,
            before_line=int(call.lineno),
            parents=parents,
        )
        reasons: list[str] = []
        if constructor is None:
            reasons.append("receiver_not_single_local_qgis_layer_constructor")
        if not call.args:
            reasons.append("crs_argument_missing")
        if crs_fact["status"] in {
            "missing",
            "ambiguous_reaching_definitions",
            "dynamic_subscript",
            "unsupported_expression",
            "unresolved_name_reference",
        }:
            reasons.append("crs_provenance_not_deterministic")
        call_start = int(call.lineno)
        call_end = int(call.end_lineno or call.lineno)
        constructor_line = constructor[0] if constructor else call_start
        context_lines = sorted(
            {
                line
                for anchor in {constructor_line, call_start}
                for line in range(
                    max(1, anchor - 2), min(len(source_lines), anchor + 2) + 1
                )
            }
        )
        snippet = "\n".join(
            f"{line} | {source_lines[line - 1]}" for line in context_lines
        )
        identity = {
            "source_authority_key": row.get("source_authority_key"),
            "scope": _scope_name(scope, parents),
            "receiver": receiver,
            "line": call_start,
        }
        units.append(
            {
                "schema": SCHEMA,
                "family_rule_id": RULE_ID,
                "family_id": "set_crs_metadata",
                "semantic_contract": (
                    "define or update QGIS layer CRS metadata without transforming coordinates"
                ),
                "mapping_status": "exact_stable125",
                "candidate_l3_sequence": [L3_CODE],
                "unit_id": _sha256_bytes(
                    json.dumps(identity, sort_keys=True).encode("utf-8")
                ),
                "record_id": row.get("record_id"),
                "source_root_id": row.get("source_root_id"),
                "source_path": row.get("source_path"),
                "source_sha256": row.get("source_sha256"),
                "normalized_source_body_sha256": row.get(
                    "normalized_source_body_sha256"
                ),
                "source_authority_key": row.get("source_authority_key"),
                "lexical_scope": _scope_name(scope, parents),
                "receiver": receiver,
                "receiver_constructor": (
                    _name(constructor[1].func) if constructor else ""
                ),
                "receiver_constructor_line": constructor_line if constructor else 0,
                "terminal_call": _name(call.func),
                "crs_fact": crs_fact,
                "source_span": [call_start, call_end],
                "source_snippet": snippet,
                "source_region_sha256": _sha256_bytes(snippet.encode("utf-8")),
                "macro_status": "complete" if not reasons else "deferred",
                "deferred_reasons": reasons,
                "source_verification": "verified_sha256",
                "description_fidelity": "not_started",
                "deduplication": "not_started",
                "training_admission": "not_granted_family_census_only",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
                "llm_called": False,
            }
        )
    return units


def analyze_path(row: dict[str, Any]) -> list[dict[str, Any]]:
    path = Path(str(row.get("source_path") or ""))
    if not path.is_file():
        return []
    payload = path.read_bytes()
    return analyze_source(
        row, payload.decode("utf-8-sig", errors="replace"), source_bytes=payload
    )


def _candidate_source(row: dict[str, Any]) -> bool:
    return any(
        str(step.get("name") or "").lower().rsplit(".", 1)[-1] == "setcrs"
        for step in row.get("steps") or []
    )


def select_source_disjoint_review(
    rows: list[dict[str, Any]], *, per_split: int, seed: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_source[str(row["source_sha256"])].append(row)
    ordered = sorted(
        by_source.items(),
        key=lambda item: hashlib.sha256(f"{seed}:{item[0]}".encode()).hexdigest(),
    )
    calibration: list[dict[str, Any]] = []
    holdout: list[dict[str, Any]] = []
    for _, source_rows in ordered:
        target = calibration if len(calibration) <= len(holdout) else holdout
        if len(target) >= per_split:
            target = holdout if target is calibration else calibration
        if len(target) >= per_split:
            continue
        row = min(source_rows, key=lambda item: str(item["unit_id"]))
        target.append(
            {
                **row,
                "review_split": (
                    "calibration" if target is calibration else "holdout"
                ),
                "human_boundary_decision": "",
                "human_mapping_decision": "",
                "human_description_fidelity": "",
                "human_notes": "",
                "training_admission": "not_granted_pending_source_review",
            }
        )
    if len(calibration) != per_split or len(holdout) != per_split:
        raise ValueError("insufficient source-disjoint review population")
    if {row["source_sha256"] for row in calibration} & {
        row["source_sha256"] for row in holdout
    }:
        raise ValueError("source SHA leakage")
    if {row["source_authority_key"] for row in calibration} & {
        row["source_authority_key"] for row in holdout
    }:
        raise ValueError("normalized-body leakage")
    return calibration, holdout


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
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--exclude-jsonl", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--minimum-support", type=int, default=30)
    parser.add_argument("--review-per-split", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260805)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows = _read_jsonl(args.candidates)
    excluded = {
        str(row.get("source_authority_key") or "")
        for path in args.exclude_jsonl
        for row in _read_jsonl(path)
    }
    remaining = [
        row for row in rows if str(row.get("source_authority_key") or "") not in excluded
    ]
    prefiltered = [row for row in remaining if _candidate_source(row)]
    units = [unit for row in prefiltered for unit in analyze_path(row)]
    complete = [row for row in units if row["macro_status"] == "complete"]
    authorities = {row["source_authority_key"] for row in complete}
    support_gate = (
        "eligible_for_source_disjoint_calibration"
        if len(authorities) >= args.minimum_support
        else "deferred_support_below_minimum"
    )
    calibration: list[dict[str, Any]] = []
    holdout: list[dict[str, Any]] = []
    if support_gate == "eligible_for_source_disjoint_calibration":
        calibration, holdout = select_source_disjoint_review(
            complete, per_split=args.review_per_split, seed=args.seed
        )
    summary = {
        "schema": "gis_recommend.qgis_api_set_crs_census_summary.v1",
        "family_rule_id": RULE_ID,
        "input_candidate_authorities": len(rows),
        "excluded_authorities": len(excluded),
        "remaining_authorities": len(remaining),
        "prefiltered_authorities": len(prefiltered),
        "source_verified_units": len(units),
        "complete_units": len(complete),
        "complete_source_authorities": len(authorities),
        "deferred_units": len(units) - len(complete),
        "deferred_reason_counts": dict(
            sorted(
                Counter(
                    reason
                    for row in units
                    for reason in row.get("deferred_reasons") or []
                ).items()
            )
        ),
        "minimum_support": args.minimum_support,
        "support_gate": support_gate,
        "candidate_l3_sequence": [L3_CODE],
        "calibration_rows": len(calibration),
        "holdout_rows": len(holdout),
        "calibration_holdout_source_sha_overlap": 0,
        "calibration_holdout_source_authority_overlap": 0,
        "training_admission": "not_granted_family_census_only",
        "training_rows_emitted": 0,
        "llm_called": False,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, Any] = {
        "source_replay_v1.jsonl": units,
        "complete_population_v1.jsonl": complete,
        "calibration_review_v1.jsonl": calibration,
        "holdout_review_v1.jsonl": holdout,
        "summary_v1.json": summary,
    }
    paths: list[Path] = []
    for name, value in outputs.items():
        path = args.output_dir / name
        if name.endswith(".jsonl"):
            _write_jsonl(path, value)
        else:
            _write_json(path, value)
        paths.append(path)
    inputs = [args.candidates, *args.exclude_jsonl]
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                str(index): {"path": str(path), "sha256": _sha256(path)}
                for index, path in enumerate(inputs)
            },
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
                for path in paths
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
