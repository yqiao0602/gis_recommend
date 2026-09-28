#!/usr/bin/env python3
"""Qualify the 875 unique API-pattern chains into L3 sequences under the frozen
binding adjudication and Predicate/Metric Step Policy v1.

This is the pattern-lane qualification layer. It reuses, unchanged, the mapping
classes the user approved for phase 2 (`human_binding_review_2026_09_04`):
``native_operator_slug_equivalence`` (buffer, centroid, intersection, difference,
symdifference, simplify, smooth, makevalid), ``transform_crs_receiver``
(QgsCoordinateTransform.transform = reproject), and
``taxonomy_class_equivalence`` (convexhull -> Minimum Bounding Geometry, combine
-> Collect Features). Actions that adjudication left DEFERRED (interpolate,
offsetcurve, splitgeometry) stay deferred here — entering a multi-step chain does
not upgrade an action.

Predicate/Metric Step Policy v1 (user-approved 2026-09-07): a predicate or
measurement step enters the workflow **sequence** only when its result provably
controls a later *transform* call — i.e. the call sits inside an ``if``/``while``
test whose body or a dominating branch executes another chain call. Otherwise it
is recorded as structural evidence (kept on the row, never dropped silently) but
consumes no sequence slot and no L3 token. Predicates never gain new L3 codes:
``intersects`` and ``contains`` reuse existing spatial-class tokens only where
the taxonomy already defines them; otherwise the chain is L3-incomplete.

Verdicts are three-state. A chain is QUALIFIED only when: it has ≥2 transform
steps, its task owner is domain-named, every transform step carries an approved
L3 binding, and every included predicate is policy-qualified and taxonomy-bound.
No training row is emitted and no authority is modified.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_api_pattern_l3_qualification.v1"

# Frozen from human_binding_review_2026_09_04 — do not extend without a new adjudication.
TRANSFORM_BINDINGS = {
    "buffer": ("L3_02_01_01", "native_operator_slug_equivalence"),
    "centroid": ("L3_02_05_11", "native_operator_slug_equivalence"),
    "intersection": ("L3_02_02_01", "native_operator_slug_equivalence"),
    "difference": ("L3_02_02_04", "native_operator_slug_equivalence"),
    "symdifference": ("L3_02_02_05", "native_operator_slug_equivalence"),
    "simplify": ("L3_02_05_01", "native_operator_slug_equivalence"),
    "smooth": ("L3_02_05_02", "native_operator_slug_equivalence"),
    "makevalid": ("L3_01_05_02", "native_operator_slug_equivalence"),
    "convexhull": ("L3_02_05_12", "taxonomy_class_equivalence"),
    "combine": ("L3_02_03_05", "taxonomy_class_equivalence"),
    "unaryunion": ("L3_02_03_05", "taxonomy_class_equivalence"),
}
PREDICATE_BINDINGS = {"intersects": "L3_02_02_01", "contains": "L3_02_02_01"}
DEFERRED_ACTIONS = frozenset({"interpolate", "offsetcurve", "splitgeometry"})
TRANSFORM_METHODS = frozenset(TRANSFORM_BINDINGS) | {"transform"}
PREDICATE_METHODS = frozenset(PREDICATE_BINDINGS) | {"within", "touches", "overlaps"}
MEASUREMENT_METHODS = frozenset({"distance", "nearestneighbor"})


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _chain_calls(source_path: str) -> tuple[list[ast.Call], dict[ast.AST, ast.AST], list[ast.AST]]:
    """Relocate semantic calls and control-flow tests in one parse."""
    payload = Path(source_path).read_bytes()
    source = payload.decode("utf-8-sig")
    tree = ast.parse(source)
    parents: dict[ast.AST, ast.AST] = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr.lower() in (
            TRANSFORM_METHODS | PREDICATE_METHODS | MEASUREMENT_METHODS | DEFERRED_ACTIONS
        )
    ]
    calls.sort(key=lambda call: (call.lineno, call.col_offset))
    return calls, parents, ast.walk(tree) and list(ast.walk(tree))


def qualify_row(row: dict[str, Any], taxonomy: dict[str, dict[str, Any]]) -> dict[str, Any]:
    declared = str(row.get("source_sha256") or "")
    path = Path(str(row.get("source_path") or ""))
    base: dict[str, Any] = {
        "schema": SCHEMA,
        "record_id": row.get("record_id"),
        "source_sha256": declared,
        "source_root_id": row.get("source_root_id"),
        "chain": row.get("chain"),
        "chain_signature": row.get("chain_signature"),
        "task_owner": row.get("task_owner"),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_pattern_qualification_only",
    }
    if not path.is_file():
        return {**base, "decision": "DEFERRED", "defer_reason": "source_unavailable"}
    payload = path.read_bytes()
    if _sha256(payload) != declared:
        return {**base, "decision": "DEFERRED", "defer_reason": "source_sha_mismatch"}
    try:
        calls, parents, nodes = _chain_calls(str(path))
    except (UnicodeDecodeError, SyntaxError, FileNotFoundError) as exc:
        return {**base, "decision": "DEFERRED", "defer_reason": f"parse_error:{type(exc).__name__}"}

    # Control tests: every if/while test node, and the calls nested under each branch.
    tests: list[ast.AST] = [n for n in nodes if isinstance(n, (ast.If, ast.While))]
    calls_in_branches = {
        id(call)
        for test in tests
        for branch in list(test.orelse) + list(test.body)
        for call in ast.walk(branch)
        if isinstance(call, ast.Call)
    }
    transform_targets = {
        id(call) for call in calls if call.func.attr.lower() in TRANSFORM_METHODS
    }

    sequence: list[dict[str, Any]] = []
    deferred_actions: list[str] = []
    structural_predicates: list[str] = []
    unresolved: list[str] = []
    for call in calls:
        method = call.func.attr.lower()
        if method in DEFERRED_ACTIONS:
            deferred_actions.append(method)
            continue
        if method in MEASUREMENT_METHODS:
            structural_predicates.append(method)  # policy A: metric never takes a sequence slot
            continue
        if method in PREDICATE_METHODS:
            qualifies = id(call) in {id(c) for c in calls if id(c) in calls_in_branches} or _drives_branch(call, parents, tests, transform_targets)
            if not qualifies:
                structural_predicates.append(method)
                continue
            token = PREDICATE_BINDINGS.get(method)
            if token is None:
                structural_predicates.append(method)
                continue
            sequence.append({"method": method, "kind": "predicate_control", "l3": token})
            continue
        if method == "transform":
            receiver = call.func.value
            qgis_type = _receiver_type(receiver)
            if qgis_type == "QgsCoordinateTransform" or (isinstance(receiver, ast.Name) and _binding_is_crs_transform(receiver, parents, nodes)):
                sequence.append({"method": method, "kind": "transform", "l3": "L3_01_10_01", "mapping_kind": "transform_crs_receiver"})
            else:
                unresolved.append(f"transform:{qgis_type or 'unproven_receiver'}")
            continue
        binding = TRANSFORM_BINDINGS.get(method)
        if binding is None:
            unresolved.append(method)
            continue
        sequence.append({"method": method, "kind": "transform", "l3": binding[0], "mapping_kind": binding[1]})

    l3_sequence = [step["l3"] for step in sequence]
    transform_steps = [step for step in sequence if step["kind"] == "transform"]
    complete = not deferred_actions and not unresolved
    entry = {
        **base,
        "sequence": sequence,
        "l3_sequence": l3_sequence,
        "sequence_length": len(sequence),
        "transform_steps": len(transform_steps),
        "deferred_actions": deferred_actions,
        "unresolved_actions": unresolved,
        "structural_predicates": structural_predicates,
        "l3_mapping_status": "complete" if complete else ("deferred_actions" if deferred_actions else "unresolved"),
    }
    for code in l3_sequence:
        if code not in taxonomy:
            entry["l3_mapping_status"] = "l3_target_outside_taxonomy"
            break

    if len(transform_steps) < 2:
        entry.update(decision="DEFERRED", defer_reason="insufficient_transform_steps_after_policy")
    elif not complete:
        entry.update(decision="DEFERRED", defer_reason=entry["l3_mapping_status"])
    elif row.get("task_owner") != "domain_named":
        entry.update(decision="DEFERRED", defer_reason="task_owner_not_domain_named")
    else:
        entry.update(decision="QUALIFIED", defer_reason=None)
    return entry


def _drives_branch(call: ast.Call, parents: dict[ast.AST, ast.AST], tests: list[ast.AST], transform_targets: set[int]) -> bool:
    """True when the predicate call is a test operand of a branch that executes a transform."""
    for test in tests:
        operand = False
        for node in ast.walk(test.test):
            if node is call:
                operand = True
        if not operand:
            continue
        for branch in list(test.body) + list(test.orelse):
            for node in ast.walk(branch):
                if isinstance(node, ast.Call) and id(node) in transform_targets:
                    return True
    return False


def _receiver_type(receiver: ast.AST) -> str | None:
    node = receiver
    while isinstance(node, ast.Call):
        function = node.func
        if isinstance(function, ast.Attribute):
            if isinstance(function.value, ast.Name) and function.value.id == "QgsCoordinateTransform":
                return "QgsCoordinateTransform"
            node = function.value
        else:
            return None
    if isinstance(node, ast.Name):
        return node.id if node.id.lower().startswith("qgs") else None
    return None


def _binding_is_crs_transform(name_node: ast.Name, parents: dict[ast.AST, ast.AST], nodes: list[ast.AST]) -> bool:
    for node in nodes:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name_node.id:
            if "QgsCoordinateTransform" in ast.dump(node.value):
                return True
    return False


def build(census_rows: list[dict[str, Any]], taxonomy: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    scoped = [row for row in census_rows if row.get("stage") == "censused"]
    ledger = [qualify_row(row, taxonomy) for row in scoped]
    missing_defaults = {"sequence": [], "l3_sequence": [], "sequence_length": 0, "deferred_actions": [], "unresolved_actions": [], "structural_predicates": [], "l3_mapping_status": "not_reached"}
    for entry in ledger:
        for key, value in missing_defaults.items():
            entry.setdefault(key, value)
    qualified = [entry for entry in ledger if entry["decision"] == "QUALIFIED"]
    summary = {
        "schema": f"{SCHEMA}.summary",
        "censused_input": len(scoped),
        "decision_counts": dict(sorted(Counter(entry["decision"] for entry in ledger).items())),
        "defer_reason_counts": dict(sorted(Counter(entry.get("defer_reason") for entry in ledger if entry["decision"] == "DEFERRED").items())),
        "l3_mapping_status_counts": dict(sorted(Counter(entry["l3_mapping_status"] for entry in ledger).items())),
        "qualified_rows": len(qualified),
        "qualified_l3_sequence_counts": dict(sorted(Counter("|".join(entry["l3_sequence"]) for entry in qualified).items())),
        "qualified_l3_code_counts": dict(sorted(Counter(code for entry in qualified for code in entry["l3_sequence"]).items())),
        "qualified_length_distribution": dict(sorted(Counter(entry["sequence_length"] for entry in qualified).items())),
        "qualified_with_predicates": sum(bool(entry["structural_predicates"] is not None and any(s["kind"] == "predicate_control" for s in entry["sequence"])) for entry in qualified),
        "structural_predicate_steps_kept_as_evidence": sum(len(entry["structural_predicates"]) for entry in ledger),
        "deferred_action_steps": sum(len(entry["deferred_actions"]) for entry in ledger),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_pattern_qualification_only",
        "formal_authority_modified": False,
    }
    return ledger, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--census-ledger", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    taxonomy = {str(entry["l3_code"]): entry for entry in json.loads(args.taxonomy.read_text(encoding="utf-8"))["classes"]}
    ledger, summary = build(read_jsonl(args.census_ledger), taxonomy)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = args.output_dir / "pattern_qualification_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    ledger_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in ledger), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (ledger_path, summary_path)}
    hashes["census_ledger_input"] = hashlib.sha256(args.census_ledger.read_bytes()).hexdigest()
    hashes["taxonomy_input"] = hashlib.sha256(args.taxonomy.read_bytes()).hexdigest()
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
