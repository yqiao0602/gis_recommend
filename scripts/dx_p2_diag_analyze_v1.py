#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2 diagnostic analysis (owner-approved). Read-only over A1 raw facts.

Event definitions frozen BEFORE analysis:
  EMPTY            raw.strip() == ""
  THINK_UNCLOSED   "<think>" present, "</think>" absent
  NO_TERMINAL      think closed (or absent) but no line starting with
                   SELECT <id> or "NO OPERATOR FOR THIS STEP"
  CONTRADICTORY    has both a SELECT line and a NO OPERATOR line
  TERMINAL         otherwise (a closed decision exists)
Prompt-length bins: quintiles of the pooled 316 prompt token counts
(pre-declared; no data-dependent threshold search).
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

SHORT = Path(r"E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification")
RAW = SHORT / ("system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/"
               "planning_capability_audit_v1/diag50_v1/dx_v1/dx50_v1/"
               "dx50_full_v1/p2_diag_v1/P2_DIAGNOSTIC_RAW_V1.json")
TOK = SHORT / "_p2_diag_work/token_counts.json"
A1 = SHORT / "a1_short"
OUT = RAW.parent

SEL_RE = re.compile(r"(?m)^\s*SELECT\s+\S+")
NOT_RE = re.compile(r"(?m)^\s*NO OPERATOR FOR THIS STEP")


def state(f):
    raw = f  # facts
    if raw["empty"]:
        return "EMPTY"
    if raw["has_think_open"] and not raw["has_think_close"]:
        return "THINK_UNCLOSED"
    # contradiction needs the raw text; approximated by flags:
    if raw.get("sel_in") or raw.get("sel_out"):
        if raw.get("no_operator"):
            return "CONTRADICTORY"
    if raw.get("no_operator") or raw.get("sel_in") or raw.get("sel_out"):
        return "TERMINAL"
    return "NO_TERMINAL"


def main():
    d = json.loads(RAW.read_text(encoding="utf-8"))
    tok = json.loads(TOK.read_text(encoding="utf-8"))
    items = d["items"]
    for it in items:
        for arm in ("control", "experiment"):
            it[arm]["prompt_tokens"] = tok[it["step_key"] + "|" + arm]

    vals = sorted([t[arm]["prompt_tokens"] for t in items
                   for arm in ("control", "experiment")])
    qs = [vals[int(len(vals) * q)] for q in (0.2, 0.4, 0.6, 0.8)]
    assert qs == sorted(qs), qs
    def bin_of(n):
        for i, q in enumerate(qs):
            if n <= q:
                return f"B{i+1}(<= {q})"
        return f"B5(> {qs[-1]})"

    # ---- per-arm event counts over 158 ----
    per_arm = {}
    for arm in ("control", "experiment"):
        st = Counter(state(it[arm]) for it in items)
        st_norm = Counter()
        for it in items:
            s = state(it[arm])
            # normalize for reporting buckets
            if s in ("EMPTY",):
                st_norm["empty"] += 1
            elif s in ("THINK_UNCLOSED", "NO_TERMINAL"):
                st_norm["truncated/unclosed"] += 1
            elif s == "CONTRADICTORY":
                st_norm["contradictory"] += 1
            else:
                st_norm["terminal"] += 1
        per_arm[arm] = {"raw_states": dict(st), "buckets": dict(st_norm)}

    # ---- reconciliation with the 52-pair review subset ----
    ledger = json.loads((A1 / "A1_FULL_EVIDENCE_PACKET_V1/LEDGER_V1.json")
                        .read_text(encoding="utf-8"))
    pair_keys = {e["step_key"] for e in ledger["entries"]}
    sub = [it for it in items if it["step_key"] in pair_keys]
    recon = {"n_pairs": len(sub)}
    for arm in ("control", "experiment"):
        c = Counter()
        for it in sub:
            s = state(it[arm])
            c["empty" if s == "EMPTY" else
              ("contradictory" if s == "CONTRADICTORY" else
               ("terminal" if s == "TERMINAL" else "truncated/unclosed"))] += 1
        recon[arm] = dict(c)

    # ---- prompt-length bins ----
    by_bin = defaultdict(lambda: {"n": Counter(), "empty": Counter(),
                                  "trunc": Counter()})
    for it in items:
        for arm in ("control", "experiment"):
            b = bin_of(it[arm]["prompt_tokens"])
            s = state(it[arm])
            by_bin[(arm, b)]["n"][arm] += 1
            if s == "EMPTY":
                by_bin[(arm, b)]["empty"][arm] += 1
            if s in ("THINK_UNCLOSED", "NO_TERMINAL"):
                by_bin[(arm, b)]["trunc"][arm] += 1

    # ---- step position / last step ----
    pos = defaultdict(lambda: Counter())
    for it in items:
        bucket = "last" if it["is_last"] else ("early<=1/3" if it["pos_ratio"] <= 0.34 else "mid")
        for arm in ("control", "experiment"):
            s = state(it[arm])
            pos[(arm, bucket)]["n"] += 1
            if s == "EMPTY":
                pos[(arm, bucket)]["empty"] += 1
            if s in ("THINK_UNCLOSED", "NO_TERMINAL"):
                pos[(arm, bucket)]["trunc"] += 1

    # ---- task concentration ----
    per_task = defaultdict(lambda: Counter())
    for it in items:
        for arm in ("control", "experiment"):
            s = state(it[arm])
            f = per_task[(arm, it["task"])]
            f["n"] += 1
            if s == "EMPTY":
                f["empty"] += 1
            if s in ("THINK_UNCLOSED", "NO_TERMINAL"):
                f["trunc"] += 1
    top_tasks = {}
    for arm in ("control", "experiment"):
        rows = [(t, c["empty"] + c["trunc"], c["n"])
                for (a, t), c in per_task.items() if a == arm and c["n"] >= 2]
        rows.sort(key=lambda x: -x[1])
        tot_fail = sum(r[1] for r in rows)
        top_tasks[arm] = {"total_failures": tot_fail,
                          "top5": rows[:5],
                          "top5_share": round(sum(r[1] for r in rows[:5]) / max(1, tot_fail), 3)}

    # ---- paired failure states (52 subset) ----
    def bucket(s):
        return "empty" if s == "EMPTY" else ("contradictory" if s == "CONTRADICTORY"
                                             else ("terminal" if s == "TERMINAL" else "trunc"))
    paired = Counter()
    for it in sub:
        paired[(bucket(state(it["control"])), bucket(state(it["experiment"])))] += 1

    # ---- empty-output term distribution ----
    empty_term = {arm: Counter(it[arm]["term"] for it in items
                               if state(it[arm]) == "EMPTY")
                  for arm in ("control", "experiment")}

    # ---- card share ----
    def share_stats(cond):
        v = [it[arm]["card_chars"] / max(1, it[arm]["prompt_chars"])
             for it in items for arm in ("control", "experiment") if cond(it, arm)]
        return round(sum(v) / len(v), 4) if v else None
    card_share = {
        "failed": share_stats(lambda it, a: state(it[a]) in
                              ("EMPTY", "THINK_UNCLOSED", "NO_TERMINAL")),
        "terminal": share_stats(lambda it, a: state(it[a]) == "TERMINAL")}

    summary = {
        "population": {"n_items": len(items), "arms": 2,
                       "prompt_tokens": {"min": vals[0], "median": vals[len(vals)//2],
                                         "max": vals[-1]},
                       "bins": qs},
        "per_arm_158": per_arm,
        "reconciliation_52pairs": recon,
        "by_prompt_bin": {f"{a}|{b}": v["n"][a] and {
            "n": v["n"][a], "empty": v["empty"][a], "trunc": v["trunc"][a],
            "empty_rate": round(v["empty"][a] / v["n"][a], 3),
            "trunc_rate": round(v["trunc"][a] / v["n"][a], 3)}
            for (a, b), v in sorted(by_bin.items())},
        "by_position": {f"{a}|{b}": {"n": v["n"], "empty": v["empty"],
                                     "trunc": v["trunc"],
                                     "empty_rate": round(v["empty"] / max(1, v["n"]), 3),
                                     "trunc_rate": round(v["trunc"] / max(1, v["n"]), 3)}
                        for (a, b), v in sorted(pos.items())},
        "task_concentration": top_tasks,
        "paired_states_52": {f"{a}->{b}": n for (a, b), n in sorted(paired.items())},
        "empty_term_distribution": {a: dict(c) for a, c in empty_term.items()},
        "card_share": card_share,
    }
    (OUT / "P2_DIAGNOSTIC_SUMMARY_V1.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in
                      ("per_arm_158", "reconciliation_52pairs",
                       "empty_term_distribution", "card_share")},
                     ensure_ascii=False, indent=1))
    print("bins:", qs)
    for k, v in summary["by_prompt_bin"].items():
        if v:
            print(k, v)
    for k, v in summary["by_position"].items():
        print(k, v)


if __name__ == "__main__":
    main()
