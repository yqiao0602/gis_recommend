#!/usr/bin/env python3
"""Census the multi-step structure of the 4,880 ``api_pattern`` rows.

This is the first pass of the API multi-step lane: no L3 mapping, no task-text
construction, no admission — only the compression structure the user asked to
see first. For every pattern row we reread its source, verify SHA, relocate the
semantic calls, and recover the chain facts that decide whether a multi-step
*workflow* can exist at all: call order, receiver/return linkage (does one
call's geometry feed the next?), predicate/measurement contamination, and the
task-owner signal proven decisive in the standalone lane (module-level vs
domain-named scope).

Every row leaves a recorded stage reason; nothing is silently dropped. The
output is a census ledger whose summary is the stage table
``4,880 → X → … → X``. Training rows are zero by construction.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_api_pattern_census.v1"

SEMANTIC_METHODS = {
    "buffer", "centroid", "combine", "convexhull", "difference", "intersection",
    "interpolate", "makevalid", "offsetcurve", "simplify", "smooth",
    "symdifference", "transform", "unaryunion", "distance", "nearestneighbor",
    "intersects", "within", "contains", "touches", "overlaps", "splitgeometry",
}
PREDICATE_METHODS = frozenset({"contains", "intersects", "within", "touches", "overlaps"})
MEASUREMENT_METHODS = frozenset({"distance", "nearestneighbor"})
QGIS_GEOMETRY_FACTORIES = frozenset({
    "fromwkt", "fromwkb", "frompointxy", "frompoint", "frompolylinexy", "frompolyline",
    "frompolygonxy", "frompolygon", "frommultipointxy", "frommultipolylinexy",
    "frommultipolygonxy", "fromrect", "createwedgebuffer",
})
QGIS_GEOMETRY_ACCESSORS = frozenset({"geometry", "constget", "asgeometry"})
QGIS_CLASS_PREFIX = "qgs"
NON_QGIS_MODULES = frozenset({
    "shapely", "geopandas", "sklearn", "scipy", "numpy", "pandas", "pyproj", "rasterio",
    "fiona", "cv2", "PIL", "torch", "tensorflow", "matplotlib", "affine", "osgeo",
    "networkx", "pyqtgraph", "skimage", "statsmodels", "xarray",
})
FOREIGN_ONLY_KEYWORDS = frozenset({
    "cap_style", "join_style", "mitre_limit", "single_sided", "resolution",
    "quad_segs", "preserve_topology", "grid_size", "crs", "epsg", "inplace",
})
BARE_VERB_SCOPE = re.compile(r"^(run|main|process|handle|execute|apply|convert|do)_?$", re.I)
DOMAIN_TOKEN = re.compile(
    r"(road|river|build|water|lake|forest|land|parcel|zone|track|line|point|polygon|dem|elev"
    r"|crs|wgs|epsg|utm|grid|region|area|site|buffer|clip|address|plot|field|network|route"
    r"|tract|tree|flood|soil|slope|hill|cadastre|school|hospital|utility|pipe)",
    re.I,
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _segment(source: str, node: ast.AST | None) -> str | None:
    return None if node is None else ast.get_source_segment(source, node)


def _context(tree: ast.AST) -> dict[str, Any]:
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
    return {"parents": parents, "imported": imported, "tree": tree}


def _scope_label(context: dict[str, Any], node: ast.AST) -> dict[str, Any]:
    parents = context["parents"]
    function = klass = None
    current: ast.AST | None = node
    while current is not None:
        if function is None and isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function = current
        elif klass is None and isinstance(current, ast.ClassDef):
            klass = current
        current = parents.get(current)
    return {
        "function": function.name if function else None,
        "class": klass.name if klass else None,
        "kind": "function" if function else ("class_body" if klass else "module"),
    }


def _receiver_root(node: ast.AST) -> str | None:
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


def _is_qgis_receiver(receiver: ast.AST, context: dict[str, Any]) -> bool:
    """Receiver is provably QGIS: inline QGIS construction, QGIS accessor call,
    or a local name assigned from one of those earlier in the file."""
    node = receiver
    if isinstance(node, ast.Call):
        function = node.func
        if isinstance(function, ast.Attribute):
            if isinstance(function.value, ast.Name) and function.value.id.lower().startswith(QGIS_CLASS_PREFIX):
                return True
            if function.attr.lower() in QGIS_GEOMETRY_FACTORIES:
                return True
            if function.attr.lower() in QGIS_GEOMETRY_ACCESSORS:
                return True
        if isinstance(function, ast.Name) and function.id.lower().startswith(QGIS_CLASS_PREFIX):
            return True
    if isinstance(node, ast.Attribute):
        if node.attr.lower() in QGIS_GEOMETRY_ACCESSORS:
            return True
    if isinstance(node, ast.Name):
        bindings = [
            assign for assign in ast.walk(context["tree"])
            if isinstance(assign, ast.Assign)
            and len(assign.targets) == 1
            and isinstance(assign.targets[0], ast.Name)
            and assign.targets[0].id == node.id
            and assign.lineno < getattr(receiver, "lineno", 0)
        ]
        return any(_is_qgis_receiver(assign.value, context) for assign in bindings)
    return False


def _foreign_receiver(receiver: ast.AST, context: dict[str, Any]) -> str | None:
    root = _receiver_root(receiver)
    if root is None:
        return None
    module = context["imported"].get(root)
    return module if module in NON_QGIS_MODULES else None


def _target_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for inner in ast.walk(node):
        if isinstance(inner, ast.Name):
            names.add(inner.id)
    return names


def census_row(row: dict[str, Any]) -> dict[str, Any]:
    declared = str(row.get("source_sha256") or "")
    path = Path(str(row.get("source_path") or ""))
    base: dict[str, Any] = {
        "schema": SCHEMA,
        "record_id": row.get("record_id"),
        "source_sha256": declared,
        "source_root_id": row.get("source_root_id"),
        "declared_semantic_count": row.get("api_semantic_call_count"),
        "declared_methods": row.get("api_methods"),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_census_only",
    }
    if not path.is_file():
        return {**base, "stage": "source_unavailable", "stage_reason": "source_file_missing"}
    payload = path.read_bytes()
    if _sha256(payload) != declared:
        return {**base, "stage": "source_unavailable", "stage_reason": "source_sha_mismatch"}
    try:
        source = payload.decode("utf-8-sig")
        tree = ast.parse(source)
    except (UnicodeDecodeError, SyntaxError) as exc:
        return {**base, "stage": "source_unavailable", "stage_reason": f"parse_error:{type(exc).__name__}"}
    context = _context(tree)

    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr.lower() in SEMANTIC_METHODS:
            calls.append(node)
    calls.sort(key=lambda call: (call.lineno, call.col_offset))
    if len(calls) < 2:
        return {**base, "stage": "structure_invalid", "stage_reason": f"fewer_than_two_semantic_calls:{len(calls)}"}

    foreign = [_foreign_receiver(call.func.value, context) for call in calls]
    if any(foreign):
        return {**base, "stage": "fail_closed", "stage_reason": f"foreign_receiver:{sorted({f for f in foreign if f})[0]}"}
    foreign_kw = sorted({
        kw.arg for call in calls for kw in call.keywords if kw.arg and kw.arg in FOREIGN_ONLY_KEYWORDS
    })
    if foreign_kw:
        return {**base, "stage": "fail_closed", "stage_reason": f"foreign_only_keyword:{foreign_kw[0]}"}

    qgis_calls = [call for call in calls if _is_qgis_receiver(call.func.value, context)]
    unproven = len(calls) - len(qgis_calls)
    if unproven == len(calls):
        return {**base, "stage": "structure_invalid", "stage_reason": "no_receiver_proven_qgis"}

    methods = [call.func.attr.lower() for call in calls]
    predicates = [m for m in methods if m in PREDICATE_METHODS]
    measurements = [m for m in methods if m in MEASUREMENT_METHODS]
    transforms = len(calls) - len(predicates) - len(measurements)
    if transforms < 2:
        return {
            **base,
            "stage": "structure_invalid",
            "stage_reason": f"insufficient_transform_steps:{transforms}+{len(predicates)}P+{len(measurements)}M",
            "chain": methods,
        }

    # dataflow linkage: a later call consumes a name that an earlier call produced.
    produced: dict[str, int] = {}
    linked_pairs = 0
    for index, call in enumerate(calls):
        parent = context["parents"].get(call)
        while parent is not None and not isinstance(parent, ast.stmt):
            parent = context["parents"].get(parent)
        if isinstance(parent, ast.Assign):
            for name in _target_names(parent):
                produced.setdefault(name, index)
        for name in _target_names(call):
            if name in produced and produced[name] < index:
                linked_pairs += 1
                break
    scopes = [_scope_label(context, call) for call in calls]
    distinct_scopes = {(scope["function"], scope["class"]) for scope in scopes}
    chain_signature = tuple(methods)
    entry = {
        **base,
        "stage": "censused",
        "chain": methods,
        "chain_length": len(calls),
        "transform_steps": transforms,
        "predicate_steps": len(predicates),
        "measurement_steps": len(measurements),
        "receiver_proven_calls": len(qgis_calls),
        "receiver_unproven_calls": unproven,
        "linked_call_pairs": linked_pairs,
        "distinct_scopes": len(distinct_scopes),
        "scope_kinds": sorted({scope["kind"] for scope in scopes}),
        "chain_signature": "|".join(chain_signature),
    }
    owner_class = next((scope["class"] for scope in scopes if scope["class"]), None)
    owner_function = scopes[0]["function"]
    if all(scope["kind"] == "module" for scope in scopes):
        entry["task_owner"] = "module_level"
    elif BARE_VERB_SCOPE.match(str(owner_function or "")):
        entry["task_owner"] = "generic_verb"
    elif owner_class and DOMAIN_TOKEN.search(owner_class) or (owner_function and DOMAIN_TOKEN.search(owner_function)):
        entry["task_owner"] = "domain_named"
    else:
        entry["task_owner"] = "plain_scope"
    if linked_pairs == 0:
        entry["stage"] = "structure_invalid"
        entry["stage_reason"] = "no_dataflow_linkage_between_calls"
    return entry


def build(rows: list[dict[str, Any]], *, asset_type: str = "api_pattern") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    scoped = [row for row in rows if str(row.get("asset_type") or "") == asset_type]
    ledger = [census_row(row) for row in scoped]
    censused = [row for row in ledger if row["stage"] == "censused"]
    signatures: dict[str, str] = {}
    for row in censused:
        key = row["chain_signature"]
        if key in signatures:
            row["stage"] = "dedup_internal"
            row["stage_reason"] = f"identical chain signature already kept from {signatures[key]}"
        else:
            signatures[key] = str(row["record_id"])

    def counter(key: str, rows_: list[dict[str, Any]] | None = None) -> dict[str, int]:
        return dict(sorted(Counter(str(r.get(key)) for r in (rows_ or ledger)).items()))

    summary = {
        "schema": f"{SCHEMA}.summary",
        "api_pattern_rows": len(scoped),
        "stage_counts": counter("stage"),
        "stage_reason_counts": counter("stage_reason"),
        "censused_before_dedup": len(censused),
        "unique_chain_signatures": len(signatures),
        "task_owner_counts": counter("task_owner", [r for r in ledger if r["stage"] == "censused"]),
        "chain_length_distribution": dict(sorted(Counter(r.get("chain_length") for r in censused).items())),
        "top_chain_signatures": dict(Counter(r["chain_signature"] for r in censused).most_common(15)),
        "linked_pairs_distribution": dict(sorted(Counter(r.get("linked_call_pairs") for r in censused).items())),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_census_only",
        "formal_authority_modified": False,
    }
    return ledger, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normalized-ledger", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    ledger, summary = build(read_jsonl(args.normalized_ledger))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = args.output_dir / "pattern_census_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    ledger_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in ledger), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (ledger_path, summary_path)}
    hashes["normalized_ledger_input"] = hashlib.sha256(args.normalized_ledger.read_bytes()).hexdigest()
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
