#!/usr/bin/env python3
"""Extract source facts and semantic status for normalized API semantic units.

The Asset Miner matched API semantic calls by *method name only*. Names such as
``buffer``, ``centroid``, ``intersection``, ``contains``, ``distance`` and
``transform`` are shared verbatim by shapely, geopandas, sklearn, pyproj and
numpy, so a method name is not evidence of a QGIS operation. This layer rereads
each source, verifies its SHA256, relocates the single semantic call, and
recovers the facts needed to decide whether a QGIS GIS semantic exists at all.

It records ``semantic_action`` as a lexical-but-evidence-bound label and never an
L3 code, so a later taxonomy change does not require reparsing source. L3
mapping is explicitly not attempted here: every row carries
``l3_mapping_status = not_attempted_phase1``. The only decisions available are
``DEFERRED`` and ``FAIL_CLOSED``; nothing can be QUALIFIED before an L3 proof
layer runs. No training row is emitted and no authority is modified.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, NamedTuple

SCHEMA = "gis_recommend.qgis_api_semantic_unit_facts.v1"
BINDING_RULE = "dominating_same_scope_receiver_v1"

# Role of the call's *return value*, which decides whether the call can be a
# workflow step at all. Predicates and measurements are not transformations.
GEOMETRY_TRANSFORM = frozenset({
    "buffer", "centroid", "combine", "convexhull", "difference", "intersection",
    "interpolate", "makevalid", "offsetcurve", "simplify", "smooth",
    "symdifference", "unaryunion", "splitgeometry",
})
SPATIAL_PREDICATE = frozenset({"contains", "intersects", "within", "touches", "overlaps"})
MEASUREMENT = frozenset({"distance", "nearestneighbor"})
CRS_OR_GEOMETRY_TRANSFORM = frozenset({"transform"})

# Receiver evidence. ``QgsGeometry`` factories and the feature/layer accessors
# that provably return QGIS objects.
QGIS_GEOMETRY_FACTORIES = frozenset({
    "fromwkt", "fromwkb", "frompointxy", "frompoint", "frompolylinexy", "frompolyline",
    "frompolygonxy", "frompolygon", "frommultipointxy", "frommultipolylinexy",
    "frommultipolygonxy", "fromrect", "fromqpointf", "fromqpolygonf", "collectgeometry",
    "createwedgebuffer", "unarygeometry",
})
QGIS_GEOMETRY_ACCESSORS = frozenset({"geometry", "constget", "get", "asgeometry"})
QGIS_CLASS_PREFIX = "qgs"
# Keyword arguments that exist only in the shapely/geopandas buffer and simplify
# signatures. PyQGIS takes positional ``(distance, segments)``, so any of these
# proves the call is not a QGIS one even when the receiver looks plausible.
FOREIGN_ONLY_KEYWORDS = frozenset({
    "cap_style", "join_style", "mitre_limit", "single_sided", "resolution",
    "quad_segs", "preserve_topology", "grid_size", "crs", "epsg", "inplace",
})
NON_QGIS_MODULES = frozenset({
    "shapely", "geopandas", "sklearn", "scipy", "numpy", "pandas", "pyproj", "rasterio",
    "fiona", "cv2", "PIL", "torch", "tensorflow", "matplotlib", "affine", "osgeo",
    "networkx", "pyqtgraph", "skimage", "statsmodels", "xarray",
})


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _segment(source: str, node: ast.AST | None) -> str | None:
    return None if node is None else ast.get_source_segment(source, node)


def _span(node: ast.AST | None) -> dict[str, int] | None:
    if node is None or not hasattr(node, "lineno"):
        return None
    return {
        "line_start": int(node.lineno),
        "line_end": int(getattr(node, "end_lineno", None) or node.lineno),
        "column_start": int(node.col_offset),
        "column_end": int(getattr(node, "end_col_offset", None) or node.col_offset),
    }


def _semantic_role(method: str) -> str:
    if method in GEOMETRY_TRANSFORM:
        return "geometry_transform"
    if method in SPATIAL_PREDICATE:
        return "spatial_predicate"
    if method in MEASUREMENT:
        return "measurement"
    if method in CRS_OR_GEOMETRY_TRANSFORM:
        return "crs_or_geometry_transform"
    return "unclassified_method"


class Context(NamedTuple):
    tree: ast.AST
    parents: dict[ast.AST, ast.AST]
    imported_modules: dict[str, str]


def _context(tree: ast.AST) -> Context:
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    imported: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported[alias.asname or alias.name.split(".")[0]] = alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            for alias in node.names:
                imported[alias.asname or alias.name] = root
    return Context(tree, parents, imported)


def _enclosing_scope(context: Context, node: ast.AST) -> dict[str, Any]:
    current: ast.AST | None = node
    function = None
    klass = None
    while current is not None:
        if function is None and isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function = current
        elif klass is None and isinstance(current, ast.ClassDef):
            klass = current
        current = context.parents.get(current)
    return {
        "function": function.name if function is not None else None,
        "function_lineno": function.lineno if function is not None else None,
        "class": klass.name if klass is not None else None,
        "kind": "function" if function is not None else ("class_body" if klass is not None else "module"),
    }


def _receiver_root(node: ast.AST) -> str | None:
    """Left-most ``Name`` of an attribute/call chain, e.g. ``a`` in ``a.b().c``."""
    current = node
    while True:
        if isinstance(current, ast.Attribute):
            current = current.value
        elif isinstance(current, ast.Call):
            current = current.func
        elif isinstance(current, ast.Subscript):
            current = current.value
        else:
            break
    return current.id if isinstance(current, ast.Name) else None


def _receiver_evidence(source: str, context: Context, receiver: ast.AST) -> dict[str, Any]:
    """Decide whether the receiver is provably a QGIS object.

    A bare local name proves nothing; only an inline QGIS construction, a QGIS
    accessor call, or a dominating same-scope assignment from one of those is
    accepted. Anything rooted in a non-QGIS import is proof of the opposite.
    """
    evidence: dict[str, Any] = {
        "expression": _segment(source, receiver),
        "rule": BINDING_RULE,
        "root_name": _receiver_root(receiver),
        "kind": "unresolved",
        "qgis_type": None,
        "binding_lineno": None,
        "foreign_module": None,
    }
    root = evidence["root_name"]
    scope = _enclosing_scope(context, receiver)

    def dominating_assignment(name: str, before: int) -> ast.Assign | None:
        same = [
            node
            for node in ast.walk(context.tree)
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == name
            and node.lineno < before
            and _enclosing_scope(context, node) == scope
        ]
        return same[0] if len(same) == 1 else None

    def foreign_module_of(node: ast.AST, depth: int = 0) -> str | None:
        """Follow the receiver chain's root name through its provable binding."""
        name = _receiver_root(node)
        if name is None:
            return None
        module = context.imported_modules.get(name)
        if module in NON_QGIS_MODULES:
            return module
        if depth >= 3:
            return None
        binding = dominating_assignment(name, getattr(node, "lineno", 0) or 0)
        return foreign_module_of(binding.value, depth + 1) if binding is not None else None

    foreign = foreign_module_of(receiver)
    if foreign is not None:
        evidence["kind"] = "foreign_library"
        evidence["foreign_module"] = foreign
        return evidence

    def classify(node: ast.AST) -> tuple[str, str | None] | None:
        if isinstance(node, ast.Call):
            function = node.func
            if isinstance(function, ast.Attribute):
                owner = function.value
                if isinstance(owner, ast.Name) and owner.id.lower().startswith(QGIS_CLASS_PREFIX):
                    if function.attr.lower() in QGIS_GEOMETRY_FACTORIES:
                        return "qgis_geometry_factory", f"{owner.id}.{function.attr}"
                    return "qgis_class_call", f"{owner.id}.{function.attr}"
                if function.attr.lower() in QGIS_GEOMETRY_ACCESSORS:
                    return "qgis_geometry_accessor", function.attr
            if isinstance(function, ast.Name) and function.id.lower().startswith(QGIS_CLASS_PREFIX):
                return "qgis_constructor", function.id
        if isinstance(node, ast.Attribute) and node.attr.lower() in QGIS_GEOMETRY_ACCESSORS:
            # A bare ``.geometry`` attribute is the geopandas/GeoDataFrame idiom;
            # PyQGIS exposes ``QgsFeature.geometry()`` as a call. Attribute access
            # alone is therefore not proof of a QGIS receiver.
            return "attribute_accessor_not_a_call", node.attr
        return None

    direct = classify(receiver)
    if direct is not None:
        evidence["kind"], evidence["qgis_type"] = direct
        return evidence
    if isinstance(receiver, ast.Name):
        binding = dominating_assignment(receiver.id, receiver.lineno)
        multiple = [
            node
            for node in ast.walk(context.tree)
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == receiver.id
            and node.lineno < receiver.lineno
            and _enclosing_scope(context, node) == scope
        ]
        if binding is not None:
            classified = classify(binding.value)
            evidence["binding_lineno"] = binding.lineno
            if classified is not None:
                evidence["kind"], evidence["qgis_type"] = classified
                evidence["kind"] += "_via_dominating_assignment"
            else:
                evidence["kind"] = "local_name_non_qgis_binding"
                evidence["binding_expression"] = _segment(source, binding.value)
        elif len(multiple) > 1:
            evidence["kind"] = "local_name_multiple_bindings"
        else:
            evidence["kind"] = "local_name_no_dominating_binding"
    return evidence


def _argument_facts(source: str, call: ast.Call) -> dict[str, Any]:
    def describe(node: ast.AST) -> dict[str, Any]:
        try:
            value = ast.literal_eval(node)
            return {"expression": _segment(source, node), "kind": "literal", "literal_value": value}
        except (ValueError, TypeError, SyntaxError):
            return {"expression": _segment(source, node), "kind": "expression", "literal_value": None}

    positional = [describe(node) for node in call.args]
    keyword = {str(kw.arg): describe(kw.value) for kw in call.keywords if kw.arg}
    return {
        "positional": positional,
        "keyword": keyword,
        "positional_count": len(positional),
        "all_literal": bool(positional or keyword)
        and all(item["kind"] == "literal" for item in positional)
        and all(item["kind"] == "literal" for item in keyword.values()),
    }


def _return_target(source: str, context: Context, call: ast.Call) -> dict[str, Any]:
    """Where the call's value goes: assignment, condition, return, or discarded."""
    parent = context.parents.get(call)
    chain: list[ast.AST] = []
    while parent is not None and not isinstance(parent, ast.stmt):
        chain.append(parent)
        parent = context.parents.get(parent)
    if isinstance(parent, ast.Assign):
        return {"kind": "assignment", "target": _segment(source, parent.targets[0]), "statement": _segment(source, parent)}
    if isinstance(parent, ast.Return):
        return {"kind": "return", "target": None, "statement": _segment(source, parent)}
    if isinstance(parent, (ast.If, ast.While, ast.Assert)):
        return {"kind": "condition", "target": None, "statement": None}
    if isinstance(parent, ast.Expr):
        return {"kind": "discarded_expression_statement", "target": None, "statement": _segment(source, parent)}
    used_as_argument = any(isinstance(node, ast.Call) and call in node.args for node in chain)
    if used_as_argument:
        return {"kind": "nested_argument", "target": None, "statement": None}
    if isinstance(parent, ast.stmt):
        return {"kind": f"other_statement:{type(parent).__name__}", "target": None, "statement": None}
    return {"kind": "unresolved", "target": None, "statement": None}


def _decide(
    role: str,
    receiver: dict[str, Any],
    return_target: dict[str, Any],
    arguments: dict[str, Any],
) -> tuple[str, str, str]:
    """Return ``(decision, semantic_status, reason)``. QUALIFIED is unreachable here."""
    if receiver["kind"] == "foreign_library":
        return "FAIL_CLOSED", "not_qgis_semantics", f"receiver_from_non_qgis_module:{receiver['foreign_module']}"
    foreign_keyword = sorted(set(arguments["keyword"]) & FOREIGN_ONLY_KEYWORDS)
    if foreign_keyword:
        return "FAIL_CLOSED", "not_qgis_semantics", f"foreign_only_keyword_argument:{foreign_keyword[0]}"
    if role == "unclassified_method":
        return "FAIL_CLOSED", "not_qgis_semantics", "method_outside_semantic_vocabulary"
    qgis_proven = receiver["kind"].startswith(("qgis_geometry_factory", "qgis_class_call", "qgis_constructor", "qgis_geometry_accessor"))
    if not qgis_proven:
        return "DEFERRED", "ambiguous_receiver", f"receiver_not_proven_qgis:{receiver['kind']}"
    if role in {"spatial_predicate", "measurement"}:
        return "DEFERRED", "not_a_workflow_step", f"{role}_returns_scalar_not_geometry"
    if return_target["kind"] in {"discarded_expression_statement", "condition"}:
        return "DEFERRED", "result_unused", f"result_not_retained:{return_target['kind']}"
    return "DEFERRED", "candidate_geometry_semantic", "awaiting_l3_mapping_proof_phase2"


def _semantic_calls(context: Context, methods: set[str]) -> list[ast.Call]:
    calls = [
        node
        for node in ast.walk(context.tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr.lower() in methods
    ]
    return sorted(calls, key=lambda call: (call.lineno, call.col_offset))


def extract_row(row: dict[str, Any]) -> dict[str, Any]:
    methods = {str(value).strip().lower() for value in row.get("api_methods") or [] if str(value).strip()}
    source_path = Path(str(row.get("source_path") or ""))
    declared = str(row.get("source_sha256") or "")
    base: dict[str, Any] = {
        "schema": SCHEMA,
        "record_id": row.get("record_id"),
        "source_path": str(source_path),
        "source_sha256": declared,
        "source_root_id": row.get("source_root_id"),
        "api_methods": sorted(methods),
        "source_verified": False,
        "l3_mapping_status": "not_attempted_phase1",
        "l3_candidate": None,
        "parameter_evidence": None,
        "input_evidence": None,
        "output_evidence": None,
        "training_admission": "not_granted_api_semantic_facts_v1",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "provenance": {"normalized_schema": row.get("schema"), "candidate_only": True},
    }
    if not source_path.is_file():
        return {**base, "decision": "DEFERRED", "semantic_status": "source_unavailable", "decision_reason": "source_file_missing"}
    payload = source_path.read_bytes()
    if _sha256(payload) != declared:
        return {**base, "decision": "DEFERRED", "semantic_status": "source_sha256_mismatch", "decision_reason": "source_changed_since_manifest"}
    base["source_verified"] = True
    try:
        source = payload.decode("utf-8-sig")
        tree = ast.parse(source, filename=str(source_path))
    except (UnicodeDecodeError, SyntaxError) as exc:
        return {**base, "decision": "DEFERRED", "semantic_status": "source_parse_error", "decision_reason": type(exc).__name__}
    context = _context(tree)
    calls = _semantic_calls(context, methods)
    if not calls:
        return {**base, "decision": "DEFERRED", "semantic_status": "call_not_relocated", "decision_reason": "no_matching_semantic_call_in_source"}
    if len(calls) > 1:
        base["relocated_call_count"] = len(calls)
    call = calls[0]
    method = str(call.func.attr).lower()
    role = _semantic_role(method)
    receiver = _receiver_evidence(source, context, call.func.value)
    arguments = _argument_facts(source, call)
    return_target = _return_target(source, context, call)
    decision, status, reason = _decide(role, receiver, return_target, arguments)
    return {
        **base,
        "call_span": _span(call),
        "call_text": _segment(source, call),
        "method": method,
        "receiver": receiver,
        "argument_facts": arguments,
        "return_target": return_target,
        "enclosing_scope": _enclosing_scope(context, call),
        "semantic_action": f"{role}:{method}",
        "semantic_role": role,
        "semantic_status": status,
        "decision": decision,
        "decision_reason": reason,
    }


def build(rows: list[dict[str, Any]], *, asset_type: str = "api_semantic_unit") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    scoped = [row for row in rows if not asset_type or str(row.get("asset_type") or "") == asset_type]
    facts = [extract_row(row) for row in scoped]
    candidates = [row for row in facts if row["semantic_status"] == "candidate_geometry_semantic"]
    summary = {
        "schema": f"{SCHEMA}.summary",
        "input_rows": len(rows),
        "semantic_unit_rows": len(scoped),
        "fact_rows": len(facts),
        "source_verified_rows": sum(row["source_verified"] for row in facts),
        "call_relocated_rows": sum("call_span" in row for row in facts),
        "decision_counts": dict(sorted(Counter(row["decision"] for row in facts).items())),
        "semantic_status_counts": dict(sorted(Counter(row["semantic_status"] for row in facts).items())),
        "semantic_role_counts": dict(sorted(Counter(row.get("semantic_role", "not_reached") for row in facts).items())),
        "receiver_kind_counts": dict(sorted(Counter((row.get("receiver") or {}).get("kind", "not_reached") for row in facts).items())),
        "return_target_counts": dict(sorted(Counter((row.get("return_target") or {}).get("kind", "not_reached") for row in facts).items())),
        "decision_reason_counts": dict(sorted(Counter(row["decision_reason"] for row in facts).items())),
        "unique_semantic_actions": sorted({row["semantic_action"] for row in facts if row.get("semantic_action")}),
        "candidate_semantic_actions": dict(sorted(Counter(row["semantic_action"] for row in candidates).items())),
        "candidate_unique_source_sha256": len({row["source_sha256"] for row in candidates}),
        "multi_call_rows": sum("relocated_call_count" in row for row in facts),
        "l3_mapping": "not_attempted_phase1",
        "training_rows_emitted": 0,
        "training_admission": "not_granted_api_semantic_facts_v1",
        "formal_authority_modified": False,
        "qualified_rows": sum(row["decision"] == "QUALIFIED" for row in facts),
    }
    return facts, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normalized-ledger", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--asset-type", default="api_semantic_unit")
    args = parser.parse_args()
    facts, summary = build(read_jsonl(args.normalized_ledger), asset_type=args.asset_type)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    facts_path = args.output_dir / "semantic_unit_facts_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    facts_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in facts), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {path.name: _sha256(path.read_bytes()) for path in (facts_path, summary_path)}
    hashes["normalized_ledger_input"] = _sha256(args.normalized_ledger.read_bytes())
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())




