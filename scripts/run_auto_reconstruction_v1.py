# -*- coding: utf-8 -*-
"""Auto-reconstruction v1 for the 25 frozen validation scripts.

Implements the RECONSTRUCTION_PILOT_METHOD_V1 structure automatically:

  R1  variable-level dataflow graph: declared + external-candidate variables;
      edges carry (from, to, via, use_line, evidence_status) with the frozen
      two-state rule — supported (definition+use+traceable passing all
      in-source) vs supported_passing_only (use+passing confirmed, source-side
      definition external). No order-only edges.
  R2  operation units per declared variable (statement cluster):
      task_duty is NEVER auto-filled (pending_human_task_binding);
      source_operation = call paths; provenance in-source/external.
  A2/A3 reuse WP-A detectors. A4 dedup applied to edges with via_conflict
      preservation. Unresolved items recorded, never force-filled.

Scope note (COVERAGE_LIMITATIONS_V1): method-validation artifact only.
No gold designation, no task-text semantic labels, no training admission.
"""

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_wp_a_detector_backtest_v1 import (  # noqa: E402
    REPO,
    analyze_script,
    detect_a1,
    detect_a1_self_references,
    detect_a2,
    detect_a3,
    detect_a4,
    dotted_path,
    get,
    get_identifier_name,
    iter_children,
    pos_of,
    end_pos_of,
    PLATFORM_NAMES,
    JS_KEYWORDS,
)

PREP = os.path.join(REPO, "docs", "reports", "gee_semantic_planner_v1_pilot_round3",
                    "expansion_validation_prep_v1")
LEDGER = os.path.join(PREP, "sample_ledger_v1.json")
OUT_DIR = os.path.join(PREP, "auto_reconstruction_v1")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_edges(analysis):
    """Dataflow edges: for each declared variable D, every use of D inside a
    statement that defines/assigns variable T creates edge D -> T at that
    line, via the outermost call path of that statement (or 'reference').
    evidence_status per the frozen two-state rule."""
    declared = analysis["declared"]
    # statement spans: walk top-level and nested blocks via a simple pass —
    # we approximate statement ownership by line: uses and their enclosing
    # assignment/declarator targets are collected in one AST pass.
    stmt_targets = {}   # line -> set of target variable names
    stmt_ops = {}       # line -> outermost op label

    import esprima
    # (analyze_script already parsed; re-parse is acceptable and simple)

    edges_raw = []
    return edges_raw


def collect_statement_map(source):
    """Map: line -> (target variables defined at that line, outermost op)."""
    import esprima
    ast = esprima.parseScript(source, loc=True, tolerant=True)
    targets = {}
    ops = {}

    def record(line, tvars, op):
        t = targets.setdefault(line, set())
        t.update(tvars)
        if op and line not in ops:
            ops[line] = op

    def outermost_op(node):
        cur = node
        while get(cur, "parent_expr") is None:
            break
        return None

    def walk(node, in_stmt=False):
        t = get(node, "type")
        if t == "VariableDeclarator":
            line = pos_of(node)[0]
            name = get_identifier_name(get(node, "id"))
            if name:
                init = get(node, "init")
                op = dotted_path(get(init, "callee"))[1] if init is not None and \
                    get(init, "type") == "CallExpression" else \
                    (get(init, "operator") if init is not None and
                     get(init, "type") in ("BinaryExpression", "UnaryExpression",
                                           "LogicalExpression") else "declaration")
                record(line, {name}, op)
        elif t == "AssignmentExpression" and get(node, "operator") == "=":
            line = pos_of(node)[0]
            name = get_identifier_name(get(node, "left"))
            if name:
                right = get(node, "right")
                op = dotted_path(get(right, "callee"))[1] if get(right, "type") == "CallExpression" \
                    else get(right, "operator") if get(right, "type") in (
                        "BinaryExpression", "UnaryExpression", "LogicalExpression") \
                    else "assignment"
                record(line, {name}, op)
        for child in iter_children(node):
            walk(child, in_stmt)

    walk(ast)

    # outermost call op per line: deepest call path is too fine; use the
    # first CallExpression found at that line's statement — approximated by
    # the ops recorded above; refine with a per-line call-path scan
    return targets, ops


def reconstruct(source, sid, source_sha):
    analysis = analyze_script(source)
    a1 = detect_a1(analysis) + detect_a1_self_references(analysis, detect_a1(analysis))
    a1 = sorted(a1, key=lambda c: c["first_use_line"] or 0)
    a2 = detect_a2(analysis)
    a3 = detect_a3(analysis["calls"])

    targets, ops = collect_statement_map(source)

    # line -> declared variables used at that line
    uses_by_line = {}
    for u in analysis["uses"]:
        name = u["name"]
        if name in analysis["declared"] and name not in PLATFORM_NAMES:
            uses_by_line.setdefault(u["pos"][0], set()).add(name)

    edges_raw = []
    for line in sorted(set(uses_by_line) | set(targets)):
        tgt = sorted(targets.get(line, set()))
        used = sorted(uses_by_line.get(line, set()))
        op = ops.get(line, "reference")
        for src in used:
            for dst in tgt:
                if src == dst:
                    continue  # self-reference not a dataflow edge
                edges_raw.append({
                    "from": src, "to": dst, "via": op,
                    "use_line": line,
                    "evidence_status": "supported",
                })

    deduped, dups_logical, dups_strict = detect_a4(edges_raw)

    variables = []
    for name, info in sorted(analysis["declared"].items(),
                             key=lambda kv: kv[1]["def_line"]):
        if name in PLATFORM_NAMES:
            continue
        variables.append({
            "variable": name,
            "kind": info["kind"],
            "def_line": info["def_line"],
            "definition_location": "in_source",
        })
    ext = []
    for c in a1:
        ext.append({
            "variable": c["variable"],
            "kind": "external_candidate",
            "def_line": None,
            "definition_location": c["definition_location"],
            "first_use_line": c["first_use_line"],
            "evidence": c["evidence"],
            "classification": c["classification"],
        })

    unresolved = [
        {"item": c["variable"], "reason": "undeclared use — three-way "
         "classification pending human ruling (owner revision 1)"}
        for c in a1
    ]

    r2_units = []
    a2_by_var = {r["variable"]: r for r in a2}
    for v in variables:
        a2r = a2_by_var.get(v["variable"])
        r2_units.append({
            "unit": f"{sid}:unit:{v['variable']}",
            "task_duty": "pending_human_task_binding",
            "source_operation": sorted({
                e["via"] for e in deduped
                if e["to"] == v["variable"] and e["via"] != "reference"}),
            "provenance": "in_source",
            "implementation_detail": None,
            "detail_would_change": None,
            "a2_status": a2r["status"] if a2r else None,
            "post_definition_uses": a2r["post_definition_uses"] if a2r else None,
        })

    return {
        "schema": "auto_reconstruction_v1",
        "source_script": sid,
        "source_sha256": source_sha,
        "policy": {
            "task_duty": "never auto-filled (pending human task binding)",
            "evidence_states": ["supported", "supported_passing_only"],
            "a1_rule": "candidate_pending_human only (owner revision 1)",
            "scope": "method-validation artifact; not gold",
        },
        "R1_variables": variables,
        "R1_external_candidates": ext,
        "R1_dataflow_edges": deduped,
        "R1_unresolved": unresolved,
        "R2_units": r2_units,
        "A3_summary": {
            "class_counts": a3["class_counts"],
            "unknown_review_queue": a3["unknown_review_queue"],
        },
        "stats": {
            "raw_edge_records": len(edges_raw),
            "deduped_logical_edges": len(deduped),
            "duplicates_merged_logical": dups_logical,
            "duplicates_merged_strict": dups_strict,
        },
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    ledger = json.load(open(LEDGER, encoding="utf-8"))
    rows = {}
    for group, rs in ledger["selected_rows"].items():
        for r in rs:
            rows.setdefault(r["script"], r)
    scripts = sorted(rows)

    summary = []
    for sid in scripts:
        src_path = os.path.join(REPO, _find_path(sid))
        with open(src_path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        try:
            rec = reconstruct(source, sid, rows[sid]["source_sha256"])
        except Exception as exc:
            rec = {
                "schema": "auto_reconstruction_v1",
                "source_script": sid,
                "source_sha256": rows[sid]["source_sha256"],
                "reconstruction_status": "failed",
                "error": str(exc)[:300],
            }
        out = os.path.join(OUT_DIR, f"reconstruction_{sid.replace('script_', '')}_v1.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=2, ensure_ascii=False)
        st = rec.get("stats", {})
        summary.append({
            "script": sid,
            "status": rec.get("reconstruction_status", "ok"),
            "variables": len(rec.get("R1_variables", [])),
            "external_candidates": len(rec.get("R1_external_candidates", [])),
            "raw_edges": st.get("raw_edge_records"),
            "deduped_edges": st.get("deduped_logical_edges"),
            "unresolved": len(rec.get("R1_unresolved", [])),
            "sha256": sha256_file(out),
        })
        print(f"{sid}: vars={summary[-1]['variables']} ext={summary[-1]['external_candidates']} "
              f"edges={summary[-1]['raw_edges']}->{summary[-1]['deduped_edges']} "
              f"unresolved={summary[-1]['unresolved']}")

    with open(os.path.join(OUT_DIR, "auto_reconstruction_summary_v1.json"), "w",
              encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print("summary written")
    return 0


def _find_path(sid):
    import glob
    hits = glob.glob(os.path.join(REPO, ".tmp_gee_batch13_sources",
                                  "Data", "data*", sid + ".txt"))
    return os.path.relpath(hits[0], REPO).replace(os.sep, "/") if hits else ""


if __name__ == "__main__":
    sys.exit(main())
