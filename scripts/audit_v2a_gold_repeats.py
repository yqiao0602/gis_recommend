#!/usr/bin/env python3
"""V2a Gold consecutive-repeat audit (owner ruling 2026-09-17, option b).

Pure CPU, read-only: classifies consecutive same-operator runs in the frozen
A-profile gold by their DAG role, to decide whether "repetition" is legal
workflow structure or a serialization artifact BEFORE any P2 decision.

The gold contract carries no parameters, so the R1/R2 "different params"
question is proxied by DAG structure:
  fanout   distinct parents and/or children per member  -> separate instances
           (e.g. 16 buffers each feeding one merge)     [legal]
  chain    links between run members themselves         -> op feeding its own
           output (a->a->a)                             [suspicious]
  dup      identical or absent edge neighborhoods       -> serialization
           duplicates                                   [suspicious]
  mixed    anything else                                [inspect]
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "docs/reports/v2a_manifest"
OUT = REPO / "docs/reports/v2a_results/gold_repeat_audit.json"


def runs_of(ops):
    out, i = [], 0
    while i < len(ops):
        j = i
        while j + 1 < len(ops) and ops[j + 1] == ops[i]:
            j += 1
        if j > i:
            out.append((i, j, ops[i]))          # start, end(incl), operator
        i = j + 1
    return out


def classify_run(row, start, end):
    """Structural role of one consecutive run. Returns (kind, detail)."""
    pids = [p["process_id"] for p in row["processes"][start:end + 1]]
    pid_set = set(pids)
    parents, children = defaultdict(set), defaultdict(set)
    internal = 0                                # links between run members
    for l in row["links"]:
        a, b = l["source_process_id"], l["target_process_id"]
        if a in pid_set and b in pid_set and pids.index(a) + 1 == pids.index(b):
            internal += 1
        if b in pid_set:
            parents[b].add(a)
        if a in pid_set:
            children[a].add(b)
    nbhd = [frozenset(parents[p]) for p in pids] + \
           [frozenset(children[p]) for p in pids]
    n_distinct_nbhd = len({(frozenset(parents[p]), frozenset(children[p])) for p in pids})
    n_isolated = sum(1 for p in pids if not parents[p] and not children[p])
    # children convergence: all members feed one shared downstream node
    child_sets = [children[p] for p in pids]
    converge = len(child_sets) > 0 and all(len(cs) == 1 for cs in child_sets) \
        and len(set().union(*child_sets)) == 1
    if internal > 0:
        return "chain", {"internal_links": internal, "n": len(pids)}
    if n_distinct_nbhd == 1 and n_isolated == len(pids):
        return "dup_isolated", {"n": len(pids)}
    if n_distinct_nbhd == 1:
        return "dup_same_nbhd", {"n": len(pids)}
    if converge:
        return "fanout_converge", {"n": len(pids), "converge_to": True}
    return "fanout_distinct", {"n": len(pids), "distinct_nbhd": n_distinct_nbhd,
                               "isolated": n_isolated}


def audit_file(path):
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    per_run = []                                # one record per run>=2
    rows_with_runs = 0
    for r in rows:
        ops = [p["operator_id"] for p in r["processes"]]
        rr = runs_of(ops)
        if rr:
            rows_with_runs += 1
        for s, e, op in rr:
            kind, detail = classify_run(r, s, e)
            per_run.append({"wid": r["wid"], "operator": op, "len": e - s + 1,
                            "kind": kind, "detail": detail,
                            "run_index": f"{s}-{e}"})
    return {"file": path.name, "n_rows": len(rows),
            "rows_with_runs": rows_with_runs, "runs": per_run}


def main():
    files = ["v2a_A_train.jsonl", "v2a_A_dev.jsonl", "v2a_A_test.jsonl"]
    result = {"schema": "gis_recommend.v2a.gold_repeat_audit.v1",
              "note": "read-only; run length >= 2 consecutive same operator"}
    for f in files:
        result[f.split("_")[2].split(".")[0]] = audit_file(DATA / f)

    for split in ("train", "dev", "test"):
        runs = result[split]["runs"]
        rl = Counter(r["len"] for r in runs)
        kd = Counter(r["kind"] for r in runs)
        op = Counter(r["operator"] for r in runs)
        print(f"=== {split}: {result[split]['rows_with_runs']}/{result[split]['n_rows']} rows have runs, "
              f"{len(runs)} runs total ===")
        print("  run-length histogram:", dict(sorted(rl.items())))
        print("  structural kinds:", dict(kd.most_common()))
        print("  top operators:", dict(op.most_common(6)))
        # the two owner tables
        bands = [(2, 2), (3, 3), (4, 5), (6, 8), (9, 16)]
        legal = {"fanout_converge", "fanout_distinct"}
        print("  | run length | runs | legal(fanout) | suspicious(chain/dup) |")
        for lo, hi in bands:
            sel = [r for r in runs if lo <= r["len"] <= hi]
            lg = sum(1 for r in sel if r["kind"] in legal)
            print(f"  | {lo}-{hi} | {len(sel)} | {lg} | {len(sel)-lg} |")
        print("  max-run case:", max(runs, key=lambda r: r["len"]))

    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nfull records -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
