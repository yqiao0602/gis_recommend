#!/usr/bin/env python3
"""V2a Protocol v2 scorer: a pure function of (full-text predictions, gold, catalog).

No GPU, no model — generation is locked once and every metric is reproducible
offline. Spec: docs/plans/v2a_eval_protocol_v2.md (frozen 2026-09-17).

Layers measured separately:
  1. generation ability   -> conditional-on-parse F1 (optimistic, secondary)
  2. generation reliability -> end-to-end F1 (PRIMARY) + failure taxonomy
  3. output legality      -> invalid-operator rate, DAG validity

Canonicalization (--canonicalize) uses ONLY deterministic catalog lookup
(R1 exact / R2 provider-prefix / R3 separator / R4 unique-prefix). No
similarity matching, no per-operator alias tables, no dedup: repairing an
operator name must never turn a wrong choice into a different wrong choice.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path("/home/qy/system_redesign")
OPID_RE = re.compile(r'"operator_id"\s*:\s*"([^"]+)"')
REPEAT_RUN_THRESHOLD = 3          # max consecutive identical operator run >= 3
PROVIDER_FIX = {                  # finite, auditable; no operator-specific rules
    "native:gdal:": "gdal:",
    "grass:": "grass7:",
}


def parse_pred(text: str) -> dict:
    s = text.strip()
    i, j = s.find("{"), s.rfind("}")
    if i < 0 or j <= i:
        return {"ok": False, "reason": "no_json"}
    try:
        obj = json.loads(s[i:j + 1])
    except json.JSONDecodeError:
        return {"ok": False, "reason": "json_error"}
    if not isinstance(obj, dict) or "processes" not in obj:
        return {"ok": False, "reason": "shape"}
    procs = [{"process_id": str(p.get("process_id")), "operator_id": p.get("operator_id")}
             for p in (obj.get("processes") or []) if isinstance(p, dict)]
    if not procs:
        return {"ok": False, "reason": "empty_processes"}
    ids = {p["process_id"] for p in procs}
    links = []
    for l in (obj.get("links") or []):
        if not isinstance(l, dict):
            continue
        a, b = str(l.get("source_process_id")), str(l.get("target_process_id"))
        if a in ids and b in ids and a != b:
            links.append((a, b))
    return {"ok": True, "processes": procs, "links": links}


def parse_route2(text: str) -> dict:
    """Route-2 token surface (P:pid:operator / L:src>dst): first non-empty
    line, fail-closed per line — mirrors evaluate_dev.parse_generation and
    reuses route2_training.harness.text_to_graph verbatim (Gate 2 spec §8).
    Returns the same dict shape as parse_pred; taxonomy rows empty_output /
    malformed_graph replace no_json/json_error/shape."""
    if not text or not text.strip():
        return {"ok": False, "reason": "empty_output"}
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    from route2_training.harness import text_to_graph
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            processes, links = text_to_graph(line)
        except ValueError:
            continue
        procs = [{"process_id": str(p["process_id"]),
                  "operator_id": p["operator_id"]} for p in processes]
        if not procs:
            return {"ok": False, "reason": "empty_processes"}
        ids = {p["process_id"] for p in procs}
        clean = [(l["source_process_id"], l["target_process_id"])
                 for l in links
                 if l["source_process_id"] in ids
                 and l["target_process_id"] in ids and l["source_process_id"] != l["target_process_id"]]
        return {"ok": True, "processes": procs, "links": clean}
    return {"ok": False, "reason": "malformed_graph"}


def canon_factory(catalog: list):
    catset = set(catalog)

    def canon(op):
        """Returns (repaired_or_original, rule)."""
        if not isinstance(op, str) or not op:
            return op, None
        if op in catset:
            return op, "R1_exact"
        for bad, good in PROVIDER_FIX.items():
            if op.startswith(bad):
                fixed = good + op[len(bad):]
                if fixed in catset:
                    return fixed, "R2_provider"
        stripped = op.replace("_", "").replace("-", "")
        if stripped in catset:
            return stripped, "R3_separator"
        if ":" in op:
            cands = [c for c in catalog if c.startswith(op)]
            if len(cands) == 1:
                return cands[0], "R4_prefix"
        return op, "unrepaired"

    return canon


def max_consecutive_run(seq) -> int:
    best = cur = 0
    prev = object()
    for x in seq:
        cur = cur + 1 if x == prev else 1
        best = max(best, cur)
        prev = x
    return best


def dag_has_cycle(edges) -> bool:
    adj = defaultdict(list)
    nodes = set()
    for a, b in edges:
        adj[a].append(b)
        nodes.update((a, b))
    color = {}

    def dfs(u):
        color[u] = 1
        for v in adj[u]:
            if color.get(v, 0) == 1:
                return True
            if color.get(v, 0) == 0 and dfs(v):
                return True
        color[u] = 2
        return False

    return any(dfs(u) for u in list(nodes) if color.get(u, 0) == 0)


def prf(tp, fp, fn):
    p = tp / max(tp + fp, 1)
    r = tp / max(tp + fn, 1)
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": round(p, 4), "recall": round(r, 4),
            "f1": round(2 * p * r / max(p + r, 1e-9), 4)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--predictions", type=Path, required=True,
                    help="v2a_*_predictions.jsonl with full-text raw")
    ap.add_argument("--data", type=Path, required=True, help="gold jsonl")
    ap.add_argument("--catalog", type=Path,
                    default=REPO / "benchmarks/qgis_planner_v1/authority/qgis_catalog.json")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-new-tokens", type=int, default=512)
    ap.add_argument("--canonicalize", action="store_true",
                    help="add the deterministic name-repair column (P0 experiment)")
    ap.add_argument("--parser", choices=["json", "route2"], default="json",
                    help="prediction surface: v2a JSON contract (default) or "
                         "route-2 P:/L: token format (Gate 2)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    catalog = sorted({o["operator_id"] for o in
                      json.load(open(args.catalog, encoding="utf-8"))["operators"]})
    catset = set(catalog)
    rows = [json.loads(l) for l in args.data.read_text(encoding="utf-8").splitlines() if l.strip()]
    preds = {p["wid"]: p for p in (json.loads(l) for l in
              args.predictions.read_text(encoding="utf-8").splitlines() if l.strip())}

    canon = canon_factory(catalog) if args.canonicalize else None
    rule_counts = Counter()
    causes = Counter()

    # raw (baseline) accumulators
    tp = fp = fn = ltp = lfp = lfn = 0            # end-to-end: all rows
    ctp = cfp = cfn = cltp = clfp = clfn = 0      # conditional: usable rows only
    invalid_inst = pred_inst = 0
    parse_ok = truncated = empty_pred = repetition_rows = dag_valid = 0

    # canonicalized accumulators
    ktp = kfp = kfn = kctp = kcfp = kcfn = 0
    kinvalid = kinst = 0

    for r in rows:
        wid = r["wid"]
        p = preds.get(wid, {})
        raw = p.get("raw", "")
        gm = Counter(x["operator_id"] for x in r["processes"])
        gl = {(l["source_process_id"], l["target_process_id"]) for l in r["links"]}
        gold_ops = sum(gm.values())
        gold_links = len(gl)
        fn += gold_ops
        lfn += gold_links
        kfn += gold_ops          # canonicalized e2e shares the all-rows denominator

        # reliability taxonomy (extraction is parser-aware; regex works on
        # truncated JSON too)
        gen = p.get("n_gen_tokens", 0)
        if args.parser == "route2":
            op_seq = [t.split(":", 2)[2] for t in raw.split()
                      if t.startswith("P:") and t.count(":") >= 2]
        else:
            op_seq = OPID_RE.findall(raw)
        run = max_consecutive_run(op_seq)
        is_trunc = gen >= args.max_new_tokens
        if is_trunc:
            truncated += 1
        if run >= REPEAT_RUN_THRESHOLD:
            repetition_rows += 1

        parse = parse_route2 if args.parser == "route2" else parse_pred
        pr = parse(raw) if raw else {
            "ok": False,
            "reason": "empty_output" if args.parser == "route2" else "no_json"}
        # primary cause, mutually exclusive, spec ordering:
        # truncated > no_json/json_error/shape/empty_processes > empty_pred
        # > repetition_runaway > ok
        if not pr["ok"]:
            causes["truncated" if is_trunc else pr["reason"]] += 1
            continue
        parse_ok += 1
        pm = Counter(x["operator_id"] for x in pr["processes"])
        pl = set(pr["links"])
        if not dag_has_cycle(pl):
            dag_valid += 1
        if not pm:
            empty_pred += 1
            causes["truncated" if is_trunc else "empty_pred"] += 1
            continue
        if is_trunc:
            causes["truncated"] += 1
        else:
            causes["repetition_runaway" if run >= REPEAT_RUN_THRESHOLD else "ok"] += 1

        # raw metrics
        inter = sum((gm & pm).values())
        tp += inter
        fp += sum(pm.values()) - inter
        fn -= inter
        ctp += inter
        cfp += sum(pm.values()) - inter
        cfn += gold_ops - inter
        li = len(gl & pl)
        ltp += li
        lfp += len(pl) - li
        lfn -= li
        cltp += li
        clfp += len(pl) - li
        clfn += gold_links - li
        pred_inst += sum(pm.values())
        invalid_inst += sum(v for k, v in pm.items() if k not in catset)

        # canonicalized column (name repair only — no dedup, no guessing)
        if canon:
            kops = []
            for x in pr["processes"]:
                o, rule = canon(x["operator_id"])
                if rule:
                    rule_counts[rule] += 1
                kops.append(o)
            km = Counter(kops)
            kinter = sum((gm & km).values())
            ktp += kinter
            kfp += sum(km.values()) - kinter
            kfn -= kinter
            kctp += kinter
            kcfp += sum(km.values()) - kinter
            kcfn += gold_ops - kinter
            kinst += sum(km.values())
            kinvalid += sum(v for k, v in km.items() if k not in catset)

    n = len(rows)
    metrics = {
        "schema": "gis_recommend.v2a.score.v2",
        "predictions": str(args.predictions),
        "parser": args.parser,
        "n": n,
        "reliability": {
            "parse_ok_rate": round(parse_ok / n, 4),
            "hit_cap_rate": round(truncated / n, 4),
            "repetition_rate": round(repetition_rows / n, 4),
            "empty_rate": round(empty_pred / n, 4),
            "invalid_operator_rate": round(invalid_inst / max(pred_inst, 1), 4),
            "dag_valid_rate": round(dag_valid / max(parse_ok, 1), 4),
            "row_causes": dict(causes),
        },
        # PRIMARY: end-to-end
        "operator_e2e": prf(tp, fp, fn),
        "link_e2e": prf(ltp, lfp, lfn),
        # SECONDARY: conditional-on-parse (optimistic)
        "operator_conditional": dict(prf(ctp, cfp, cfn),
                                     note="optimistic; usable rows only"),
        "link_conditional": dict(prf(cltp, clfp, clfn),
                                 note="optimistic; usable rows only"),
        "pred_operator_instances": pred_inst,
        "gold_operator_instances": sum(
            sum(Counter(x["operator_id"] for x in r["processes"]).values()) for r in rows),
    }
    if canon:
        metrics["canonicalized"] = {
            "note": "deterministic catalog lookup only (R1 exact/R2 provider/"
                    "R3 separator/R4 unique-prefix); no similarity, no dedup",
            "rules_applied": dict(rule_counts),
            "operator_e2e": prf(ktp, kfp, kfn),
            "operator_conditional": dict(prf(kctp, kcfp, kcfn),
                                         note="optimistic; usable rows only"),
            "invalid_operator_rate": round(kinvalid / max(kinst, 1), 4),
        }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
