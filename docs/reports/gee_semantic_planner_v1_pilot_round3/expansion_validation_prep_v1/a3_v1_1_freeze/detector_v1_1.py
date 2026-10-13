# -*- coding: utf-8 -*-
"""Work Package A detector backtest v1 (EXPANSION_DESIGN_V1, owner authorized 2026-10-09).

Implements and back-tests A1-A4 detectors on the SIX pilot scripts ONLY.
No new sampling, no new script reconstruction, no training (per owner scope).

Detectors:
  A1 external prebinding: undeclared-but-used -> CANDIDATE only (three-way
     classification requires evidence: require/import/comment). Undeclared
     alone never counts as external_prebinding (owner revision 1).
  A2 dead code / post-definition uses: counted via AST identifier references
     (direct use + container member + function argument passing all appear as
     Identifier references in the AST). NOT text counting.
  A3 presentation/analysis classification: preregistered static API table.
     Unknown APIs go to a human review queue and are NEVER defaulted to
     analysis. Presentation/export/analysis roles may coexist (owner rev 2).
  A4 duplicate-edge dedup: key (from, to, use_line, via). Merged records keep
     pointers to all original records (owner ruling).

Outputs (small reports only):
  docs/reports/gee_semantic_planner_v1_pilot_round3/wp_a_backtest_v1/
"""

import hashlib
import json
import os
import sys

import esprima

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(
    REPO, "docs", "reports", "gee_semantic_planner_v1_pilot_round3", "wp_a_backtest_v1"
)

SIX_SCRIPTS = {
    "script_36595": os.path.join(".tmp_gee_batch13_sources", "Data", "data40000", "script_36595.txt"),
    "script_275285": os.path.join(".tmp_gee_batch13_sources", "Data", "data280000", "script_275285.txt"),
    "script_93009": os.path.join(".tmp_gee_batch13_sources", "Data", "data100000", "script_93009.txt"),
    "script_302840": os.path.join(".tmp_gee_batch13_sources", "Data", "data300000", "script_302840.txt"),
    "script_405410": os.path.join(".tmp_gee_batch13_sources", "Data", "data400000", "script_405410.txt"),
    "script_269131": os.path.join(".tmp_gee_batch13_sources", "Data", "data270000", "script_269131.txt"),
}

RECON_JSONS = {
    "script_36595": "reconstruction_pilot_v1/reconstruction_trial_36595_v1.json",
    "script_275285": "reconstruction_batch1_v1/reconstruction_275285_v1.json",
    "script_93009": "reconstruction_batch1_v1/reconstruction_93009_v1.json",
    "script_302840": "reconstruction_batch2_v1/reconstruction_302840_v1.json",
    "script_405410": "reconstruction_batch2_v1/reconstruction_405410_v1.json",
    "script_269131": "reconstruction_batch3_v1/reconstruction_269131_v1.json",
}
RECON_BASE = os.path.join(REPO, "docs", "reports", "gee_semantic_planner_v1_pilot_round3")

# --- Preregistered static API classification table (A3, EXPANSION_DESIGN_V1 §1.A3) ---
PLATFORM_NAMES = {
    "ee", "Map", "ui", "Export", "Print", "print", "console", "Date", "Math",
    "JSON", "Number", "String", "parseFloat", "parseInt", "arguments",
}
JS_KEYWORDS = {"true", "false", "null", "undefined", "this", "typeof", "new", "require"}

PRESENTATION_EXACT = {
    "print", "Map.addLayer", "Map.add", "Map.centerObject", "Map.centerMap",
    "Map.setCenter", "Map.remove", "Map.legend", "Map.setControlVisibility",
    "ui.root.add", "ui.panel.add", "Console.widget",
    # a3-fix-round v1.1 additions (owner-approved defect fixes; each is a
    # display/logging API classified by its full call path):
    "console.log", "ui.Map", "Map.setOptions", "Map.layers",
}
EXPORT_PREFIX = "Export."
PRESENTATION_PREFIXES = ("ui.Chart", "ui.Panel", "ui.root", "ui.panel", "ui.Label", "ui.Button")

# --- a3-fix-round v1.1: preregistered additions for nested-call fallback ---
# A rendering API whose own role is presentation regardless of the root
# object it is invoked on (annotator principle: "API 自身角色不被消费场景改变").
NESTED_PRESENTATION_METHODS = {"visualize"}
# GEE server-side data-processing method names: a call node whose root cannot
# be resolved to a namespace but whose immediate method is one of these is
# classified analysis. Unknown methods stay unknown (no forced classification).
GEE_DATA_METHODS = {
    "filter", "filterDate", "filterBounds", "filterMetadata", "select", "clip",
    "mean", "median", "sum", "min", "max", "first", "map", "sort", "limit",
    "addBands", "updateMask", "mask", "normalizedDifference", "multiply",
    "divide", "subtract", "expression", "selfMask", "unmask", "iterate",
    "remap", "flatten", "cat", "reduceRegion", "reduceColumns",
    "reduceToVectors", "rename", "where", "classify", "sampleRegions",
    "qualityMosaic", "mosaic", "randomColumn", "sin", "cos", "sqrt", "abs",
    "round", "pow", "and", "or", "not", "gt", "gte", "lt", "lte", "eq",
    "bitwiseAnd", "distinct", "geometry", "bounds", "buffer", "projection",
    "coveringGrid", "toDictionary", "toList", "size", "get", "getInfo", "set",
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------
# AST utilities
# --------------------------------------------------------------------------

def iter_children(node):
    if node is None:
        return
    if isinstance(node, (list, tuple)):
        for item in node:
            yield from iter_children(item)
        return
    d = getattr(node, "__dict__", None)
    if not d:
        return
    for value in d.values():
        if isinstance(value, (list, tuple)):
            for item in value:
                yield item
        elif getattr(value, "__dict__", None) or isinstance(value, dict):
            yield value


def walk(root):
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        for child in iter_children(node):
            stack.append(child)


def is_node(x):
    return getattr(x, "__dict__", None) is not None or isinstance(x, dict)


def get(node, key):
    if node is None:
        return None
    if isinstance(node, dict):
        return node.get(key)
    return getattr(node, key, None)


def pos_of(node):
    loc = get(node, "loc")
    if not loc:
        return None
    start = get(loc, "start")
    return (get(start, "line"), get(start, "column"))


def end_pos_of(node):
    loc = get(node, "loc")
    if not loc:
        return None
    end = get(loc, "end")
    return (get(end, "line"), get(end, "column"))


def dotted_path(node):
    """Resolve a callee expression to ('root', 'full.path') when composed of
    identifiers only; otherwise root of the chain and None path."""
    parts = []
    cur = node
    while True:
        if get(cur, "type") == "MemberExpression":
            if get(cur, "computed"):
                return get_identifier_name(get(cur, "object")), None
            prop_name = get_identifier_name(get(cur, "property"))
            if prop_name is None:
                return get_identifier_name(get(cur, "object")), None
            parts.append(prop_name)
            cur = get(cur, "object")
        elif get(cur, "type") == "Identifier":
            parts.append(get(cur, "name"))
            break
        else:
            return None, None
    parts.reverse()
    return parts[0], ".".join(parts)


def get_identifier_name(node):
    if node is None:
        return None
    if get(node, "type") == "Identifier":
        return get(node, "name")
    return None


# --------------------------------------------------------------------------
# Shared per-script AST analysis
# --------------------------------------------------------------------------

def resolve_call_root_and_method(callee):
    """a3-fix-round v1.1: walk a callee expression to (root_identifier,
    immediate_method), skipping nested CallExpressions in the object chain.
    Each call node is classified by its own root and method — a statement's
    outer role is never propagated to inner nodes."""
    method = None
    cur = callee
    while True:
        t = get(cur, "type")
        if t == "MemberExpression":
            if get(cur, "computed"):
                return None, method
            prop = get_identifier_name(get(cur, "property"))
            if method is None:
                method = prop
            cur = get(cur, "object")
        elif t == "CallExpression":
            cur = get(cur, "callee")
        elif t == "Identifier":
            return get(cur, "name"), method
        else:
            return None, method


def classify_call_fallback(root, method, declared_names):
    """a3-fix-round v1.1 fallback for calls whose strict dotted path is
    unresolved (nested chains) or whose root is not a resolvable namespace
    (e.g. A1 candidate variables). Preregistered additions only; unknown
    methods stay unknown."""
    if method in NESTED_PRESENTATION_METHODS:
        return "presentation"
    if root == "ee" or root in declared_names:
        return "analysis"
    if root in PLATFORM_NAMES:
        return "analysis"
    # unresolved/undeclared root: classify by the API method itself
    if method in GEE_DATA_METHODS:
        return "analysis"
    return "unknown"


def collect_call_records(ast, declared_names=frozenset()):
    """Classify every CallExpression via the preregistered table."""
    records = []
    for node in walk(ast):
        if get(node, "type") != "CallExpression":
            continue
        root, path = dotted_path(get(node, "callee"))
        arg_names = []
        for arg in (get(node, "arguments") or []):
            for sub in walk(arg):
                name = get_identifier_name(sub)
                if name:
                    arg_names.append(name)
        classification = classify_call(root, path, declared_names)
        if classification == "unknown":
            # a3-fix-round v1.1: targeted fallbacks for the three audited
            # defect classes (nested chains / candidate roots). Full paths
            # resolved above keep priority; unknowns may remain unknown.
            froot, fmethod = resolve_call_root_and_method(get(node, "callee"))
            fallback = classify_call_fallback(froot, fmethod, declared_names)
            if fallback != "unknown":
                classification = fallback
        records.append({
            "path": path,
            "root": root,
            "line": pos_of(node)[0] if pos_of(node) else None,
            "classification": classification,
            "arg_names": arg_names,
        })
    return records


def classify_call(root, path, declared_names=frozenset()):
    if root == "require":
        return "import"
    if path and path in PRESENTATION_EXACT:
        return "presentation"
    if path and path.startswith(EXPORT_PREFIX):
        return "export"
    if path and any(path.startswith(p) for p in PRESENTATION_PREFIXES):
        return "presentation"
    # analysis only when the callee root is a known platform namespace, the
    # ee module, or a locally defined data variable (method call on declared
    # data = core chain); unknown roots go to the human review queue.
    if root in PLATFORM_NAMES or root == "ee" or root in declared_names:
        return "analysis"
    return "unknown"


def analyze_script(source):
    """One AST pass producing declarations, identifier uses, calls, comments."""
    ast = esprima.parseScript(source, loc=True, tolerant=True)
    comments = getattr(ast, "comments", []) or []
    comment_text = " ".join(get(c, "value", "") or "" for c in comments)

    declared = {}  # name -> {"def_line", "kind"}
    def declare(name, line, kind):
        if name is None:
            return
        if name not in declared or declared[name]["kind"] == "param":
            declared[name] = {"def_line": line, "kind": kind}

    uses = []  # {"name","line","col"}
    assignments_global = {}  # name -> first assignment line

    for node in walk(ast):
        ntype = get(node, "type")
        if ntype == "VariableDeclarator":
            name = get_identifier_name(get(node, "id"))
            if name:
                declare(name, pos_of(node)[0], "declaration")
        elif ntype == "FunctionDeclaration":
            declare(get_identifier_name(get(node, "id")), pos_of(node)[0], "function")
            for p in (get(node, "params") or []):
                pname = get_identifier_name(p) or (
                    get_identifier_name(get(p, "left"))
                    if get(p, "type") == "AssignmentPattern" else None)
                declare(pname, pos_of(p)[0], "param")
        elif ntype in ("FunctionExpression", "ArrowFunctionExpression"):
            for p in (get(node, "params") or []):
                pname = get_identifier_name(p) or (
                    get_identifier_name(get(p, "left"))
                    if get(p, "type") == "AssignmentPattern" else None)
                declare(pname, pos_of(p)[0], "param")
        elif ntype == "CatchClause":
            declare(get_identifier_name(get(node, "param")), pos_of(node)[0], "param")
        elif ntype == "AssignmentExpression" and get(node, "operator") == "=":
            name = get_identifier_name(get(node, "left"))
            if name:
                line = pos_of(node)[0]
                if name not in assignments_global:
                    assignments_global[name] = {
                        "line": line,
                        "init_end": end_pos_of(get(node, "right")),
                    }
        elif ntype == "Identifier":
            name = get(node, "name")
            uses.append({"name": name, "pos": pos_of(node)})

    # assignment-created globals define from that line onward (JS implicit
    # globals). A self-reference inside the initializing assignment's RHS is
    # a use WITHOUT a completed definition -> A1 candidate (owner revision 1:
    # undeclared use never silently becomes a definition).
    for name, info in assignments_global.items():
        if name not in declared:
            declared[name] = {"def_line": info["line"], "kind": "assignment",
                              "init_end": info["init_end"]}

    filtered_uses = collect_uses_with_context(ast)

    return {
        "declared": declared,
        "uses": filtered_uses,
        "calls": collect_call_records(ast, frozenset(declared)),
        "comment_text": comment_text,
        "parse_comments": [get(c, "value", "") for c in comments],
    }


def collect_uses_with_context(ast):
    """Identifier references excluding declaration sites and non-computed
    member properties / object keys / function parameters."""
    out = []

    def visit(node, parent):
        if not is_node(node):
            return
        ntype = get(node, "type")
        if ntype == "Identifier":
            skip = False
            if parent is not None:
                ptype = get(parent, "type")
                if ptype == "MemberExpression" and get(parent, "property") is node \
                        and not get(parent, "computed"):
                    skip = True
                elif ptype == "Property" and get(parent, "key") is node \
                        and not get(parent, "computed"):
                    skip = True
                elif ptype in ("VariableDeclarator",) and get(parent, "id") is node:
                    skip = True
                elif ptype == "FunctionDeclaration" and get(parent, "id") is node:
                    skip = True
                elif ptype in ("FunctionDeclaration", "FunctionExpression",
                               "ArrowFunctionExpression") and \
                        node in (get(parent, "params") or []):
                    skip = True
                elif ptype == "CatchClause" and get(parent, "param") is node:
                    skip = True
                elif ptype == "AssignmentPattern" and get(parent, "left") is node:
                    skip = True
                elif ptype == "AssignmentExpression" and get(parent, "left") is node:
                    skip = True  # assignment target, not a use
                elif ptype in ("LabeledStatement", "BreakStatement", "ContinueStatement"):
                    skip = True
            if not skip:
                out.append({"name": get(node, "name"), "pos": pos_of(node),
                            "parent_type": ptype if parent else None})
        for child in iter_children(node):
            visit(child, node)

    visit(ast, None)
    return out


# --------------------------------------------------------------------------
# Detector A1: external prebinding candidates
# --------------------------------------------------------------------------

def detect_a1(analysis):
    declared = analysis["declared"]
    candidates = {}
    for u in analysis["uses"]:
        name = u["name"]
        if name in declared or name in PLATFORM_NAMES or name in JS_KEYWORDS:
            continue
        entry = candidates.setdefault(name, {
            "variable": name,
            "definition_location": "unavailable_in_source",
            "use_lines": [],
            "use_count": 0,
            "evidence": [],
            # Undeclared-but-used is a CANDIDATE only; final three-way
            # classification is a human ruling (owner revision 1).
            "classification": "candidate_pending_human",
        })
        entry["use_lines"].append(u["pos"][0])
        entry["use_count"] += 1

    for entry in candidates.values():
        entry["use_lines"] = sorted(set(entry["use_lines"]))
        entry["first_use_line"] = entry["use_lines"][0] if entry["use_lines"] else None
        del entry["use_count"]
        name = entry["variable"]
        if name in analysis["comment_text"]:
            entry["evidence"].append("mentioned_in_source_comment")
        # require-based externals are declared via var; no extra rule needed.
    return sorted(candidates.values(), key=lambda e: e["first_use_line"] or 0)


def detect_a1_self_references(analysis, candidates):
    """Assignment-defined names whose initializing RHS references themselves
    (e.g. `soil = soil.select(...)`) -> the RHS self-reference is an
    undeclared use; surface it as a candidate, never as a definition."""
    declared = analysis["declared"]
    extra = []
    for name, info in declared.items():
        if info.get("kind") != "assignment":
            continue
        init_end = info.get("init_end")
        if not init_end:
            continue
        rhs_uses = [u for u in analysis["uses"]
                    if u["name"] == name and u["pos"] and u["pos"] < init_end]
        if rhs_uses:
            extra.append({
                "variable": name,
                "definition_location": "unavailable_in_source_at_first_use",
                "use_lines": sorted({u["pos"][0] for u in rhs_uses}),
                "first_use_line": rhs_uses[0]["pos"][0],
                "evidence": ["self_reference_in_initializing_assignment"],
                "classification": "candidate_pending_human",
                "note": "RHS self-reference precedes completed definition; "
                        "assignment defines only from its own line onward",
            })
    return extra


# --------------------------------------------------------------------------
# Detector A2: post-definition uses / dead code (AST-based, not text counting)
# --------------------------------------------------------------------------

def detect_a2(analysis):
    """For each declared data variable: count identifier uses occurring after
    the definition position, and classify downstream consumption by the API
    class of the calls that consume the variable (as argument or callee base)."""
    declared = analysis["declared"]
    uses = analysis["uses"]
    calls = analysis["calls"]

    # map variable -> list of consuming call records
    consumers = {name: [] for name in declared}
    for call in calls:
        involved = set(call["arg_names"])
        root = call["root"]
        base = call["path"].split(".")[0] if call["path"] else root
        if base in consumers:
            involved.add(base)
        for v in involved:
            if v in consumers:
                consumers[v].append(call)

    results = []
    for name, info in sorted(declared.items(), key=lambda kv: kv[1]["def_line"]):
        if name in PLATFORM_NAMES:
            continue
        def_pos = (info["def_line"], -1)
        post = [u for u in uses if u["name"] == name and u["pos"] and u["pos"] > def_pos]
        use_lines = sorted({u["pos"][0] for u in post})
        call_classes = sorted({c["classification"] for c in consumers[name]})
        if not post:
            status = "unconsumed"
        elif call_classes and set(call_classes) <= {"presentation"}:
            status = "presentation_only"
        elif "analysis" in call_classes or "export" in call_classes or \
                "unknown" in call_classes or not call_classes:
            status = "analysis_chain"
        else:
            status = "analysis_chain"
        results.append({
            "variable": name,
            "kind": info["kind"],
            "def_line": info["def_line"],
            "post_definition_uses": len(post),
            "use_lines": use_lines,
            "consuming_call_classes": call_classes,
            "status": status,
        })
    return results


# --------------------------------------------------------------------------
# Detector A3 summary: roles per script + unknown review queue
# --------------------------------------------------------------------------

def detect_a3(calls):
    class_counts = {}
    unknown_calls = []
    for c in calls:
        class_counts[c["classification"]] = class_counts.get(c["classification"], 0) + 1
        if c["classification"] == "unknown":
            unknown_calls.append(c)
    # role coexistence: lines carrying both presentation and analysis calls
    by_line = {}
    for c in calls:
        by_line.setdefault(c["line"], set()).add(c["classification"])
    coexist_lines = sorted(
        line for line, cls in by_line.items()
        if {"presentation", "analysis"} <= cls
    )
    return {
        "class_counts": class_counts,
        "unknown_review_queue": [
            {"path": c["path"], "root": c["root"], "line": c["line"]}
            for c in unknown_calls
        ],
        "presentation_analysis_coexist_lines": coexist_lines,
    }


# --------------------------------------------------------------------------
# Detector A4: duplicate-edge dedup over the six reconstruction JSONs
# --------------------------------------------------------------------------

def detect_a4(edges):
    """Two-level dedup. Primary key (from, to, use_line): the same source
    variable consumed at the same operation position is one logical edge.
    Differing `via` values are a via_conflict: both strings preserved inside
    the merged record (never silently dropped - owner ruling). Strict
    four-tuple (with via) merges nothing here but is reported for audit."""
    seen_logical = {}
    seen_strict = set()
    deduped = []
    dups_logical = dups_strict = 0
    for e in edges:
        strict = (e.get("from"), e.get("to"), e.get("use_line"), e.get("via"))
        if strict in seen_strict:
            dups_strict += 1
            seen_logical[strict[:3]].setdefault("merged_originals", []).append(e)
            continue
        seen_strict.add(strict)
        logical = strict[:3]
        if logical in seen_logical:
            dups_logical += 1
            rec = seen_logical[logical]
            if rec.get("via") != e.get("via"):
                rec["via_conflict"] = True
                rec.setdefault("via_all", []).append(e.get("via"))
            rec.setdefault("merged_originals", []).append(e)
        else:
            rec = dict(e)
            rec["merged_originals"] = []
            seen_logical[logical] = rec
            deduped.append(rec)
    return deduped, dups_logical, dups_strict


# --------------------------------------------------------------------------
# Back-test driver
# --------------------------------------------------------------------------

# Preregistered back-test expectations (EXPANSION_DESIGN_V1 §1 acceptance)
# CORRECTED during back-test against source (fail-closed divergence records,
# originals preserved): the frozen 36595 reconstruction marked elevation
# (line 63) and lulc (line 139) as unavailable_in_source, but both carry
# explicit `var` declarations in source; soil (line 27) and s2 (line 83) are
# assignment-defined implicit globals whose RHS self-references are undeclared
# uses. CHIRPS/DEM/modis are genuine external prebindings the manual
# reconstruction did not record. Ground-truth corrections are logged as
# findings, never patched into the frozen artifact.
EXPECTED_A1_IN_CANDIDATES = {
    "script_36595": {"CHIRPS", "DEM", "modis", "soil", "s2"},
    "script_275285": {"geometry"},
    "script_93009": set(),
    "script_302840": {"ftTrain", "bands", "predLst", "tfoiLst", "stK"},
    "script_405410": set(),
    "script_269131": {"AOI", "image", "HP_11_09_2019"},
}
# A2 acceptance anchors. CORRECTED: the batch-3 narrative said Fire_Sus had
# "12 subsequent uses"; AST-verified source truth is 11 identifier occurrences
# (class1..class5 chains = 8, min/max reduceRegion = 2, chart image = 1).
# The 12 is not reproducible from source and is recorded as a human-count
# divergence case; the detector is not forced to match it.
EXPECTED_A2 = {
    "script_269131": {
        "pi_all": {"status": "unconsumed", "post_definition_uses": 0},
        "Fire_Sus": {"status": "analysis_chain", "post_definition_uses": 11},
    },
}
# A4 acceptance anchors (logical level; via conflicts preserved, not dropped)
EXPECTED_A4 = {
    "script_269131": {"raw": 40, "deduped": 38, "dups": 2},
}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    report = {"schema": "wp_a_detector_backtest_v1", "date": "2026-10-09",
              "scope": "six pilot scripts only; no new sampling or reconstruction",
              "scripts": {}}

    # ---- A1 / A2 / A3 per script ----
    for script, rel in SIX_SCRIPTS.items():
        path = os.path.join(REPO, rel)
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
        analysis = analyze_script(source)
        a1 = detect_a1(analysis)
        a1 += detect_a1_self_references(analysis, a1)
        a1.sort(key=lambda e: e["first_use_line"] or 0)
        a2 = detect_a2(analysis)
        a3 = detect_a3(analysis["calls"])

        a1_names = {e["variable"] for e in a1}
        self_ref_names = {e["variable"] for e in a1
                          if "self_reference_in_initializing_assignment" in e["evidence"]}
        expected = EXPECTED_A1_IN_CANDIDATES.get(script, set())
        missing = sorted(expected - a1_names)
        # false positive: a candidate that is declared in-source WITHOUT the
        # self-reference justification (RHS self-reference candidates are
        # legitimate uses before a completed definition - owner revision 1)
        false_pos = sorted(n for n in a1_names
                           if n in analysis["declared"] and n not in self_ref_names)

        a2_checks = {}
        for var, exp in EXPECTED_A2.get(script, {}).items():
            match = [r for r in a2 if r["variable"] == var]
            got = match[0] if match else None
            a2_checks[var] = {
                "expected": exp,
                "got": {k: got[k] for k in ("status", "post_definition_uses")} if got else None,
                "pass": bool(got) and got["status"] == exp["status"] and
                        got["post_definition_uses"] == exp["post_definition_uses"],
            }

        report["scripts"][script] = {
            "source_sha256": sha256_file(path),
            "A1": {
                "candidates": a1,
                "expected_in_candidates": sorted(expected),
                "missing_expected": missing,
                "declared_false_positives": false_pos,
                "pass": not missing and not false_pos,
            },
            "A2": {
                "unconsumed": [r for r in a2 if r["status"] == "unconsumed"],
                "presentation_only": [r for r in a2 if r["status"] == "presentation_only"],
                "analysis_chain_count": sum(1 for r in a2 if r["status"] == "analysis_chain"),
                "all_variables": a2,
                "anchor_checks": a2_checks,
                "pass": all(v["pass"] for v in a2_checks.values()),
            },
            "A3": {**a3, "pass": True},  # pass judged below from C2 anchor
        }

    # A3 anchor: 269131 chart calls must be presentation, not analysis
    b3 = report["scripts"]["script_269131"]
    chart_unknown = [u for u in b3["A3"]["unknown_review_queue"]
                     if u["path"] and u["path"].startswith("ui.Chart")]
    b3["A3"]["anchor_check_c2"] = {
        "requirement": "ui.Chart calls classified presentation; never defaulted to analysis",
        "chart_calls_in_unknown_queue": len(chart_unknown),
        "presentation_calls_present": b3["A3"]["class_counts"].get("presentation", 0) > 0,
    }
    b3["A3"]["pass"] = len(chart_unknown) == 0 and \
        b3["A3"]["class_counts"].get("presentation", 0) > 0

    # ---- A4 over reconstruction JSONs ----
    a4_summary = {}
    for script, rel in RECON_JSONS.items():
        with open(os.path.join(RECON_BASE, rel), "r", encoding="utf-8") as f:
            data = json.load(f)
        edges = data["R1_dataflow_edges"]
        deduped, dups_logical, dups_strict = detect_a4(edges)
        a4_summary[script] = {
            "raw_records": len(edges),
            "deduped_logical_edges": len(deduped),
            "duplicates_merged_logical": dups_logical,
            "duplicates_merged_strict": dups_strict,
            "via_conflicts_preserved": sum(
                1 for r in deduped if r.get("via_conflict")),
        }
        exp = EXPECTED_A4.get(script)
        if exp:
            a4_summary[script]["expected"] = exp
            a4_summary[script]["pass"] = (
                len(edges) == exp["raw"] and len(deduped) == exp["deduped"]
                and dups_logical == exp["dups"]
                and a4_summary[script]["via_conflicts_preserved"] == exp["dups"])
        else:
            a4_summary[script]["pass"] = dups_logical == 0
    report["A4"] = a4_summary

    # ---- overall ----
    report["overall"] = {
        "A1_pass": all(v["A1"]["pass"] for v in report["scripts"].values()),
        "A2_pass": all(v["A2"]["pass"] for v in report["scripts"].values()),
        "A3_pass": all(v["A3"]["pass"] for v in report["scripts"].values()),
        "A4_pass": all(v["pass"] for v in a4_summary.values()),
    }
    report["overall"]["all_pass"] = all(report["overall"].values())

    results_path = os.path.join(OUT_DIR, "wp_a_backtest_results_v1.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    # hash ledger: results + all six sources + six reconstruction inputs
    ledger = {
        "wp_a_backtest_results_v1.json": sha256_file(results_path),
        "sources": {s: v["source_sha256"] for s, v in report["scripts"].items()},
        "reconstruction_inputs": {
            s: sha256_file(os.path.join(RECON_BASE, r)) for s, r in RECON_JSONS.items()
        },
    }
    with open(os.path.join(OUT_DIR, "wp_a_backtest_hash_ledger_v1.json"), "w",
              encoding="utf-8") as f:
        json.dump(ledger, f, indent=2)

    # ---- console summary ----
    print(json.dumps(report["overall"], indent=2))
    for script, v in report["scripts"].items():
        print(f"\n=== {script} ===")
        print(f"  A1 pass={v['A1']['pass']} candidates={len(v['A1']['candidates'])} "
              f"missing={v['A1']['missing_expected']} false_pos={v['A1']['declared_false_positives']}")
        if v["A1"]["candidates"]:
            for c in v["A1"]["candidates"]:
                print(f"    - {c['variable']}: first_use={c['first_use_line']} "
                      f"uses_at={c['use_lines']} evidence={c['evidence']} "
                      f"[{c['classification']}]")
        print(f"  A2 pass={v['A2']['pass']} unconsumed="
              f"{[r['variable'] for r in v['A2']['unconsumed']]} "
              f"presentation_only={[r['variable'] for r in v['A2']['presentation_only']]}")
        for var, chk in v["A2"]["anchor_checks"].items():
            print(f"    anchor {var}: expected={chk['expected']} got={chk['got']} pass={chk['pass']}")
        print(f"  A3 pass={v['A3']['pass']} classes={v['A3']['class_counts']} "
              f"unknown_queue={len(v['A3']['unknown_review_queue'])} "
              f"coexist_lines={v['A3']['presentation_analysis_coexist_lines']}")
    print("\n=== A4 ===")
    for script, s in a4_summary.items():
        print(f"  {script}: {s['raw_records']} -> {s['deduped_logical_edges']} "
              f"(logical_dups={s['duplicates_merged_logical']}, "
              f"strict_dups={s['duplicates_merged_strict']}, "
              f"via_conflicts_preserved={s['via_conflicts_preserved']}) pass={s['pass']}")
    return 0 if report["overall"]["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
