# -*- coding: utf-8 -*-
"""Expansion validation sampling script v1 (EXPANSION_WP_B_SAMPLING_V1).

DESIGN-FROZEN, NOT EXECUTED in the design phase (owner ruling 2026-10-09:
freeze sampling design first; new-sample extraction requires separate
approval). Running this script WITHOUT --execute prints the frozen design
manifest (deterministic preview, no sampling). With --execute it performs
the one-shot frozen sampling and writes the sample ledger.

Sampling design (frozen in EXPANSION_WP_B_SAMPLING_V1.md):
  - Frame: G0 train split manifest passed via --train-split (path + SHA
    pinned at execution; no preset path).
  - Hard exclusions: six pilot scripts.
  - Groups:
      L1 external dependency   : A1 candidate count >= 1
      L2 dead code             : A2 unconsumed count >= 1 (excluding pure
                                  visualization params: *_vis, *_visParams,
                                  *_params, *_palette, style/color names)
      L3 presentation mixing   : a variable consumed by both presentation
                                  and analysis calls
      L4 repeated subworkflows : >=3 structurally similar statement blocks
                                  (AST shape fingerprint, ≥3 occurrences)
      L5 multi-formula         : a declared variable with >=2 in-source
                                  assignment/definition sites
      C control                : hits none of L1-L5
      R random                 : Algorithm-R reservoir, k>=10, detector-
                                  INDEPENDENT (owner revision: detects
                                  detector misses)
  - Determinism: candidates sorted by script id; seed 20261009; within-stratum
    selection by detector score desc, id asc tie-break; Algorithm-R reservoir
    for R with an independent RNG stream (same seed); zero manual selection.
  - Layer overlap allowed; report per-layer counts AND deduplicated script
    total; every selected script pinned with source sha256.
"""

import argparse
import hashlib
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_wp_a_detector_backtest_v1 import (  # noqa: E402
    analyze_script,
    detect_a1,
    detect_a2,
    detect_a3,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(
    REPO, "docs", "reports", "gee_semantic_planner_v1_pilot_round3",
    "expansion_validation_prep_v1",
)

FROZEN_SEED = 20261009
PILOT_EXCLUSIONS = {
    "script_36595", "script_275285", "script_93009",
    "script_302840", "script_405410", "script_269131",
}
MIN_PER_DIFFICULTY_LAYER = 5
MIN_CONTROL = 10
MIN_RANDOM = 10

VIS_PARAM_SUFFIXES = ("vis", "visparams", "params", "palette",
                      "palette_incidence", "style", "color")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Layer detectors (reusable AST analysis from WP-A; layer rules preregistered)
# ---------------------------------------------------------------------------

def _is_vis_param(name):
    return name.lower().endswith(VIS_PARAM_SUFFIXES)


def detect_l1(analysis):
    return [c["variable"] for c in detect_a1(analysis)]


def detect_l2(analysis):
    return [r["variable"] for r in detect_a2(analysis)
            if r["status"] == "unconsumed" and not _is_vis_param(r["variable"])]


def detect_l3(analysis):
    hits = []
    for r in detect_a2(analysis):
        classes = set(r.get("consuming_call_classes") or [])
        if "presentation" in classes and ("analysis" in classes or "export" in classes):
            hits.append(r["variable"])
    return hits


def _stmt_shape_fingerprint(node):
    """Structural fingerprint of a statement: full ordered AST walk including
    identifiers and literal values, so distinct unique statements produce
    distinct fingerprints while structurally identical repeated blocks match."""
    def shape(n, depth=0):
        if depth > 40:
            return "..."
        if isinstance(n, (list, tuple)):
            return "[" + ">".join(shape(x, depth + 1) for x in n) + "]"
        d = getattr(n, "__dict__", None) or (n if isinstance(n, dict) else None)
        if not d:
            return ""
        t = d.get("type")
        if not t:
            return ""
        parts = [t]
        for key in ("name", "operator", "kind", "raw", "value"):
            v = d.get(key)
            if v is not None and not isinstance(v, (dict, list)) and \
                    not hasattr(v, "__dict__"):
                parts.append(repr(v))
        # ordered structural children only (skip loc/comments metadata)
        for key, v in d.items():
            if key in ("type", "loc", "range", "start", "end", "comments"):
                continue
            if isinstance(v, (list, tuple)) or hasattr(v, "__dict__") or \
                    isinstance(v, dict):
                s = shape(v, depth + 1)
                if s:
                    parts.append(s)
        return "(" + ">".join(parts) + ")"

    return shape(node)


def detect_l4(source, min_repeat=3, min_block_len=200):
    """Statement-block shape fingerprint; a statement shape whose fingerprint
    is structurally substantial (>= min_block_len chars) and appears
    >=min_repeat times counts as a repeated subworkflow. Length floor filters
    trivial single-token statements (assignments, prints)."""
    import esprima
    try:
        ast = esprima.parseScript(source, loc=True, tolerant=True)
    except Exception:
        return []
    from collections import Counter
    fingerprints = []
    for stmt in (ast.body or []):
        fp = _stmt_shape_fingerprint(stmt)
        if fp:
            fingerprints.append((fp, getattr(stmt.loc.start, "line", 0)))
    counter = Counter(fp for fp, _ in fingerprints)
    lines_by_fp = {}
    for fp, line in fingerprints:
        lines_by_fp.setdefault(fp, []).append(line)
    hits = [
        {"shape_hash": hashlib.sha256(fp.encode()).hexdigest()[:12],
         "occurrences": n, "lines": lines_by_fp[fp]}
        for fp, n in counter.items()
        if n >= min_repeat and len(fp) >= min_block_len
    ]
    return sorted(hits, key=lambda h: -h["occurrences"])


def detect_l5(source):
    """Declared variables with >=2 definition sites in-source (multi
    initialization / competing formulas)."""
    import esprima
    try:
        ast = esprima.parseScript(source, loc=True, tolerant=True)
    except Exception:
        return []
    def_sites = {}
    def add(name, line):
        if name and line:
            def_sites.setdefault(name, []).append(line)

    def walk_nodes(root):
        stack = [root]
        while stack:
            node = stack.pop()
            yield node
            d = getattr(node, "__dict__", None)
            if not d:
                continue
            for v in d.values():
                if isinstance(v, list):
                    for item in v:
                        stack.append(item)
                elif hasattr(v, "__dict__"):
                    stack.append(v)

    for node in walk_nodes(ast):
        t = getattr(node, "type", None)
        if t == "VariableDeclarator":
            _id = getattr(node, "id", None)
            add(getattr(_id, "name", None), getattr(getattr(node, "loc", None), "start", None) and node.loc.start.line)
        elif t == "AssignmentExpression" and getattr(node, "operator", None) == "=":
            left = getattr(node, "left", None)
            add(getattr(left, "name", None), getattr(getattr(node, "loc", None), "start", None) and node.loc.start.line)
    return [
        {"variable": name, "definition_lines": lines}
        for name, lines in sorted(def_sites.items()) if len(lines) >= 2
    ]


def classify_script(source):
    """Full detector pass; returns group hits."""
    analysis = analyze_script(source)
    a3 = detect_a3(analysis["calls"])
    return {
        "L1_external_dependency": {"hit": bool(detect_l1(analysis)),
                                   "evidence": detect_l1(analysis)},
        "L2_dead_code": {"hit": bool(detect_l2(analysis)),
                         "evidence": detect_l2(analysis)},
        "L3_presentation_mixing": {"hit": bool(detect_l3(analysis)),
                                   "evidence": detect_l3(analysis)},
        "L4_repeated_subworkflows": {"hit": bool(detect_l4(source)),
                                     "evidence": [h["shape_hash"] for h in detect_l4(source)]},
        "L5_multi_formula": {"hit": bool(detect_l5(source)),
                             "evidence": [h["variable"] for h in detect_l5(source)]},
        "_a3_class_counts": a3["class_counts"],
    }


def algorithm_r_reservoir(stream, k, rng):
    """Vitter Algorithm-R with a dedicated Random instance (independent
    stream, same frozen seed)."""
    reservoir = []
    for i, item in enumerate(stream):
        if len(reservoir) < k:
            reservoir.append(item)
        else:
            j = rng.randint(0, i)
            if j < k:
                reservoir[j] = item
    return reservoir


# ---------------------------------------------------------------------------
# Main sampling
# ---------------------------------------------------------------------------

def _assemble_ledger(records, train_split_path):
    """Apply the frozen selection rules to (id, groups) records.
    Shared by live scan and cache assembly — selection depends only on
    sorted id + group hits, so both paths produce identical ledgers."""
    difficulty_keys = ["L1_external_dependency", "L2_dead_code",
                       "L3_presentation_mixing", "L4_repeated_subworkflows",
                       "L5_multi_formula"]

    def layer_score(row):
        g = row["groups"]
        return sum(1 for k in difficulty_keys if g.get(k, {}).get("hit"))

    selected = {}
    for key in difficulty_keys:
        eligible = [r for r in records if r["groups"].get(key, {}).get("hit")]
        eligible.sort(key=lambda r: (-layer_score(r), r["script"]))
        selected[key] = [r["script"] for r in eligible[:MIN_PER_DIFFICULTY_LAYER]]

    control_eligible = [r for r in records if layer_score(r) == 0]
    control_eligible.sort(key=lambda r: r["script"])
    selected["C_control"] = [r["script"] for r in control_eligible[:MIN_CONTROL]]

    rng = random.Random(FROZEN_SEED)
    reservoir = algorithm_r_reservoir([r["script"] for r in records], MIN_RANDOM, rng)
    selected["R_random_independent"] = reservoir

    sha_by_id = {r["script"]: r.get("sha256") for r in records}
    selected_rows = {
        group: [{"script": sid, "source_sha256": sha_by_id.get(sid)}
                for sid in ids]
        for group, ids in selected.items()
    }
    return {
        "frozen_seed": FROZEN_SEED,
        "train_split": {"path": os.path.abspath(train_split_path),
                        "sha256": sha256_file(train_split_path)},
        "pool_size": len(records),
        "available": sum(1 for r in records if r["available"]),
        "unavailable": sum(1 for r in records if not r["available"]),
        "parse_errors": sum(1 for r in records
                            if "_parse_error" in r.get("groups", {})),
        "selected": selected,
        "selected_rows": selected_rows,
        "deduplicated_script_total": len({s for ids in selected.values() for s in ids}),
        "exclusions": sorted(PILOT_EXCLUSIONS),
    }


def sample_from_cache(cache_path, train_split_path):
    records = [json.loads(l) for l in open(cache_path, encoding="utf-8")
               if l.strip()]
    records.sort(key=lambda r: r["script"])
    return _assemble_ledger(records, train_split_path)


def sample(train_split_path, n_layers=MIN_PER_DIFFICULTY_LAYER,
           n_control=MIN_CONTROL, n_random=MIN_RANDOM):
    with open(train_split_path, "r", encoding="utf-8") as f:
        first = f.read(1)
    with open(train_split_path, "r", encoding="utf-8") as f:
        if first == "[":
            entries = json.load(f)
        else:
            entries = [json.loads(line) for line in f if line.strip()]

    # manifest paths resolve relative to the manifest's directory (portable
    # to any split location; absolute paths used as-is)
    manifest_dir = os.path.dirname(os.path.abspath(train_split_path))

    # candidate pool: sorted by script id, pilot-excluded
    pool = []
    for e in entries:
        sid = e.get("script") or e.get("source_script") or e.get("script_id")
        path = e.get("path") or e.get("source_path")
        if not sid or not path:
            continue
        if sid in PILOT_EXCLUSIONS:
            continue
        pool.append({"script": sid, "path": path})
    pool.sort(key=lambda r: r["script"])

    # detector pass over pool
    scored = []
    for row in pool:
        src_path = row["path"] if os.path.isabs(row["path"]) \
            else os.path.join(REPO, row["path"])
        if not os.path.exists(src_path):
            scored.append({**row, "available": False, "groups": {}})
            continue
        with open(src_path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        try:
            groups = classify_script(source)
        except Exception as exc:  # parse failure is a sample observation,
            # not a crash: record and keep the frozen one-shot going
            groups = {"_parse_error": str(exc)[:200]}
        scored.append({**row, "available": True, "sha256": sha256_file(src_path),
                       "groups": groups})

    return _assemble_ledger(scored, train_split_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-split", help="G0 train split manifest (json/jsonl)")
    ap.add_argument("--execute", action="store_true",
                    help="perform the one-shot frozen sampling (requires owner approval)")
    ap.add_argument("--from-cache", dest="from_cache", metavar="CACHE_JSONL",
                    help="assemble the frozen ledger from a precomputed "
                         "pool-scan cache (same frozen selection rules)")
    ap.add_argument("--design-only", action="store_true",
                    help="print frozen design manifest without sampling")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    if args.from_cache:
        result = sample_from_cache(args.from_cache, args.train_split)
        result["status"] = "EXECUTED_ONE_SHOT"
        result["assembled_from_cache"] = os.path.abspath(args.from_cache)
        out = os.path.join(OUT_DIR, "sample_ledger_v1.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        ledger = {
            "sample_ledger_v1.json": sha256_file(out),
            "train_split_sha256": result["train_split"]["sha256"],
        }
        with open(os.path.join(OUT_DIR, "sample_ledger_hash_v1.json"), "w",
                  encoding="utf-8") as f:
            json.dump(ledger, f, indent=2)
        print(json.dumps({k: v for k, v in result.items()
                          if k != "selected_rows"}, indent=2,
                         ensure_ascii=False))
        return 0
    design = {
        "schema": "expansion_validation_sampling_design_v1",
        "frozen_seed": FROZEN_SEED,
        "exclusions": sorted(PILOT_EXCLUSIONS),
        "min_per_difficulty_layer": MIN_PER_DIFFICULTY_LAYER,
        "min_control": MIN_CONTROL,
        "min_random": MIN_RANDOM,
        "determinism": ("candidates sorted by script id; stratified = detector "
                        "score desc then id asc; R = Algorithm-R reservoir k>=10 "
                        "independent RNG stream, same seed"),
        "status": "DESIGN_FROZEN / NOT_EXECUTED",
    }
    if args.design_only or not args.execute:
        print(json.dumps(design, indent=2))
        with open(os.path.join(OUT_DIR, "sampling_design_manifest_v1.json"), "w",
                  encoding="utf-8") as f:
            json.dump(design, f, indent=2)
        return 0

    if not args.train_split:
        print("--train-split required for --execute", file=sys.stderr)
        return 2
    result = sample(args.train_split)
    result["status"] = "EXECUTED_ONE_SHOT"
    out = os.path.join(OUT_DIR, "sample_ledger_v1.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    ledger = {
        "sample_ledger_v1.json": sha256_file(out),
        "train_split_sha256": result["train_split"]["sha256"],
    }
    with open(os.path.join(OUT_DIR, "sample_ledger_hash_v1.json"), "w",
              encoding="utf-8") as f:
        json.dump(ledger, f, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k != "_rows"}, indent=2,
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
