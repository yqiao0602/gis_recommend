#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D1 analysis (FROZEN before execution, 2026-10-18).

Preregistered outputs:
  - paired empty-output-rate difference (B - A) with a TASK-level cluster
    bootstrap 95% CI (26 tasks, 10k resamples, seed 20261018);
  - per-item termination distribution (v2 instrument) and four-way paired
    transitions;
  - decision-class distribution (POS/OOC/ABST/NODEC) and self-contradictory
    count;
  - manipulation check: every record's prompt_sha16 must equal the frozen
    prompt hash, and B prompts must be within 1650 +/- 10 tokens;
  - same-round A arm vs A1 historical: empty-state and decision-class
    agreement (generation stability reference).

Boundary (frozen): results describe the effect of inserting the frozen neutral
long text at the specified position for these 47 previously-successful short
prompts. They are NOT a general token-length causal claim and must not be
extrapolated to the other 111 affected steps.
"""
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from dx_s23 import parse_s2_v2  # noqa: E402

SHORT = REPO.parent
D1 = (REPO / ("docs/reports/route2_p0_contract/plan_pipeline_v1/"
              "planning_capability_audit_v1/diag50_v1/dx_v1/dx50_v1/"
              "dx50_full_v1/d1_v1"))
A1_RUNS = SHORT / "_a1_work/runs_local"
CTRL_TREE = SHORT / "dx50_short/runs"


def sha16(s):
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def decision_class(raw, parsed):
    if not raw.strip():
        return "EMPTY"
    if re.search(r"(?m)^\s*SELECT\s+\S+", raw.split("</think>")[-1] if "</think>" in raw else raw) \
            and re.search(r"(?m)^\s*NO OPERATOR FOR THIS STEP", raw):
        return "CONTRADICTORY"
    if parsed.get("no_operator_for_step"):
        return "ABST"
    if parsed.get("selected_in_candidates"):
        return "POS"
    if parsed.get("selected_outside_candidates"):
        return "OOC"
    return "NODEC"


def load_run(root, key, arm):
    tid, snum = key.split("#S")
    d = root / tid / "S2" / f"S{snum}" / arm
    raw = (d / "raw_output.txt").read_text(encoding="utf-8")
    g = json.loads((d / "gen.json").read_text(encoding="utf-8"))
    return raw, g


def top_oids(key):
    tid, snum = key.split("#S")
    retr = json.loads((CTRL_TREE / tid / "S1" / "retrieval.json")
                      .read_text(encoding="utf-8"))
    top = next(x for x in retr["steps"] if x["step"] == int(snum))
    return [c["operator_id"] for c in top["top10"]]


def main(results_root):
    prompts = json.loads((D1 / "D1_PROMPTS_V1.json").read_text(encoding="utf-8"))
    sample = json.loads((D1 / "D1_SAMPLE_V1.json").read_text(encoding="utf-8"))
    task_of = {s["step_key"]: s["task"] for s in sample["steps"]}
    frozen = {(p["step_key"], p["arm"]): p for p in prompts}

    rows, manip = [], []
    for key in sorted(task_of):
        oids = top_oids(key)
        rec = {"step_key": key, "task": task_of[key]}
        for arm in ("A", "B"):
            raw, g = load_run(Path(results_root), key, arm)
            fp = frozen[(key, arm)]
            m = {"step_key": key, "arm": arm,
                 "prompt_sha_ok": g.get("prompt_sha16") == sha16(fp["prompt"]),
                 "tokens": fp["tokens"],
                 "in_range": (abs(fp["tokens"] - 1650) <= 10) if arm == "B" else True}
            manip.append(m)
            parsed = parse_s2_v2(raw, oids)
            rec[arm] = {"raw": raw, "gen": g,
                        "state": "empty" if not raw.strip() else "non_empty",
                        "term": g.get("term"), "decision": decision_class(raw, parsed),
                        "sel": parsed.get("selected_in_candidates") or []}
        rows.append(rec)

    def rate(arm):
        e = sum(1 for r in rows if r[arm]["state"] == "empty")
        return e, len(rows) - e

    eA, nA = rate("A")
    eB, nB = rate("B")
    diff = (eB / len(rows)) - (eA / len(rows))
    by_task = defaultdict(list)
    for r in rows:
        by_task[r["task"]].append(r)
    tasks = sorted(by_task)
    rng = random.Random(20261018)
    boots = []
    for _ in range(10000):
        ea = eb = tot = 0
        for _ in range(len(tasks)):
            t = tasks[rng.randrange(len(tasks))]
            for r in by_task[t]:
                tot += 1
                ea += r["A"]["state"] == "empty"
                eb += r["B"]["state"] == "empty"
        boots.append((eb - ea) / tot)
    boots.sort()
    ci = (boots[250], boots[9750])

    trans = Counter((r["A"]["state"], r["B"]["state"]) for r in rows)
    termA = Counter(r["A"]["term"] for r in rows)
    termB = Counter(r["B"]["term"] for r in rows)
    decA = Counter(r["A"]["decision"] for r in rows)
    decB = Counter(r["B"]["decision"] for r in rows)

    # same-round A vs A1 historical
    cons = Counter()
    for r in rows:
        tid, snum = r["step_key"].split("#S")
        h = A1_RUNS / tid / "S2" / f"S{snum}"
        hraw = (h / "raw_output.txt").read_text(encoding="utf-8")
        cons["same_empty_state"] += (("empty" if not hraw.strip() else "non_empty")
                                     == r["A"]["state"])
        hpar = parse_s2_v2(hraw, top_oids(r["step_key"]))
        cons["same_decision"] += (decision_class(hraw, hpar) == r["A"]["decision"])
        cons["exact_raw"] += (hraw == r["A"]["raw"])

    out = {"n_pairs": len(rows), "n_tasks": len(tasks),
           "empty": {"A": eA, "B": eB, "rate_A": eA / len(rows),
                     "rate_B": eB / len(rows), "diff": diff, "ci95": ci},
           "transitions": {f"{a}->{b}": n for (a, b), n in trans.items()},
           "termination": {"A": dict(termA), "B": dict(termB)},
           "decisions": {"A": dict(decA), "B": dict(decB)},
           "self_contradictory": {
               "A": sum(1 for r in rows if r["A"]["decision"] == "CONTRADICTORY"),
               "B": sum(1 for r in rows if r["B"]["decision"] == "CONTRADICTORY")},
           "manipulation": {"all_prompt_sha_ok": all(m["prompt_sha_ok"] for m in manip),
                            "all_B_in_range": all(m["in_range"] for m in manip),
                            "failures": [m for m in manip
                                         if not (m["prompt_sha_ok"] and m["in_range"])]},
           "same_round_A_vs_A1": dict(cons),
           "per_pair": [{"step": r["step_key"], "task": r["task"],
                         "A_state": r["A"]["state"], "B_state": r["B"]["state"],
                         "A_term": r["A"]["term"], "B_term": r["B"]["term"],
                         "A_dec": r["A"]["decision"], "B_dec": r["B"]["decision"]}
                        for r in rows]}
    (D1 / "D1_RESULTS_V1.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
    print(json.dumps({k: out[k] for k in
                      ("empty", "transitions", "termination", "manipulation")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
