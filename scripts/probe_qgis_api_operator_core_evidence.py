#!/usr/bin/env python3
"""Probe how many sink-anchored API sources have provable operator cores.

Statistics only - no training rows, no L3 admission.  Tiers:

  T1: source contains at least one core operator call (geometry construction /
      geometry processing / attribute mutation / file export) plus a sink.
  T2: T1 and at least one core call has a literal-provable key argument
      (numeric/string constant, literal QgsField name, feature.attributes()
      copy, or literal geometry constructor payload).
  T3: T2 rows that also satisfy the strict mined-macro rules (already covered
      by existing replays) - approximated here as same-scope sink+core with
      literal arguments inside one function scope.

T2 - T3 estimates the pool an LLM-assisted candidate generator with a
deterministic verifier could unlock.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scripts.analyze_qgis_api_mutation_upstream import (  # noqa: E402
    _name,
    _parents,
    _scope_node,
)

SINKS = {"addfeature", "addfeatures", "writeraster", "writeasvectorformat", "writeasvectorformatv2", "writeasvectorformatv3"}
CORE_METHODS = {
    # geometry construction
    "frompoint", "frompointxy", "frompolyline", "frompolylinexy",
    "frompolygon", "frompolygonxy", "fromwkt", "fromrect",
    "frommultipoint", "frommultipointxy", "frommultipolygon", "frommultipolygonxy",
    "frommultipolyline", "frommultipolylinexy", "fromwkb", "fromjson", "fromqpolygonf",
    # geometry processing
    "buffer", "centroid", "clip", "combine", "convexhull", "densifybycount",
    "difference", "interpolate", "intersection", "intersects", "makevalid",
    "offsetcurve", "pointonsurface", "simplify", "smooth", "symdifference",
    "transform", "translate", "unaryunion",
    # attribute mutation
    "addattribute", "addattributes", "changeattributevalue", "changeattributevalues",
    "setattribute", "setattributes",
    # file export
    "writeasvectorformat", "writeasvectorformatv2", "writeasvectorformatv3", "writeraster",
}
LITERAL_HEAVY = {
    "frompoint", "frompointxy", "frompolygon", "frompolygonxy", "fromwkt",
    "fromrect", "buffer", "simplify", "setattribute", "setattributes",
    "addattribute", "addattributes", "transform", "intersects", "intersection",
    "translate", "centroid", "clip", "difference", "symdifference",
}


def _method(node: ast.Call) -> str:
    return _name(node.func).rsplit(".", 1)[-1].lower()


def _has_literal_key_argument(call: ast.Call, method: str) -> bool:
    """One argument is a literal constant, a QgsField/QgsPoint-ish literal,
    an attributes() copy, or a constant list/tuple element."""
    if not call.args:
        return False
    for argument in call.args:
        if isinstance(argument, ast.Constant):
            return True
        if isinstance(argument, (ast.List, ast.Tuple)) and argument.elts:
            if any(isinstance(element, ast.Constant) for element in argument.elts):
                return True
            if any(
                isinstance(element, ast.Call)
                and _name(element.func).rsplit(".", 1)[-1].lower() in {"qgsfield", "qgspoint", "qgspointxy", "qgsgeometry"}
                and element.args
                for element in argument.elts
            ):
                return True
        if isinstance(argument, ast.Call) and _name(argument.func).rsplit(".", 1)[-1].lower() == "attributes":
            return True
        if isinstance(argument, ast.Call) and _name(argument.func).rsplit(".", 1)[-1].lower() in {"qgsfield", "qgspoint", "qgspointxy", "qgsgeometry", "qgsrectangle", "qgscoordinatetransform"}:
            return True
    return False


def _core_calls(tree: ast.AST) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (method := _method(node)) in CORE_METHODS
    ]


def probe_source(text: str) -> dict[str, bool]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {"parse_fail": True}
    parents = _parents(tree)
    sinks = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and _method(node) in SINKS]
    if not sinks:
        return {"no_sink": True}
    core = _core_calls(tree)
    if not core:
        return {"sink_only": True}
    literal_cores = [call for call in core if _has_literal_key_argument(call, _method(call))]
    # T3 approximation: strict mined-macro = one function scope contains a sink
    # and a literal-provable core with the sink in the same scope and control path.
    strict_scope = False
    for sink in sinks:
        scope = _scope_node(sink, parents)
        if any(call for call in literal_cores if _scope_node(call, parents) is scope):
            strict_scope = True
            break
    return {
        "t1_core_present": True,
        "t2_literal_core": bool(literal_cores),
        "t3_same_scope_strict": strict_scope,
    }


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-rows", type=int, default=6873)
    args = parser.parse_args()
    rows = [
        json.loads(line)
        for line in args.manifest.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) != args.expected_rows:
        raise ValueError(f"manifest rows {len(rows)} != {args.expected_rows}")
    stats: Counter[str] = Counter()
    detail: list[dict[str, Any]] = []
    for row in rows:
        path = Path(str(row["source_path"]))
        if not path.is_file():
            stats["source_missing"] += 1
            continue
        actual = _sha256(path.read_bytes())
        if actual != str(row.get("source_sha256") or ""):
            stats["sha_mismatch"] += 1
            continue
        result = probe_source(path.read_text(encoding="utf-8-sig", errors="replace"))
        stats.update(result)
        detail.append({**row, **result})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in detail),
        encoding="utf-8",
    )
    total = len(rows)
    summary = {
        "schema": "gis_recommend.qgis_api_operator_core_evidence_probe.v1",
        "input_rows": total,
        "stats": dict(sorted(stats.items())),
        "t1_core_present": stats["t1_core_present"],
        "t2_literal_core": stats["t2_literal_core"],
        "t3_same_scope_strict": stats["t3_same_scope_strict"],
        "t2_minus_t3_pool": stats["t2_literal_core"] - stats["t3_same_scope_strict"],
    }
    (args.output.with_name("summary_v1.json")).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
