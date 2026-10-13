#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A″ bounded failure attribution (owner 2026-10-12, three questions).

Existing artifacts ONLY — no training, no gold changes, no new GPU runs.

Q1 training trajectory: from ledger + run log (grad norms were NOT
   recorded — instrumentation gap, reported honestly).
Q2 regression concentration: the 45 newly-runaway rows (c-set) vs
   coverage-degraded rows — overlap + stratum/gold-length distribution.
Q3 mechanism: for each newly-runaway row, is the post text (a) complete
   JSON + trailing content (EOS shifted later), (c) unbounded prefix
   (no complete object), or (x) other; plus parse/length flips.
"""
import gzip
import json
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
DW = os.path.join(HERE, "..", "..", "04_DIAG_WORK")
PULL = os.path.join(DW, "a1_pull")


def load(path):
    op = gzip.open if path.endswith(".gz") else open
    with op(path, "rt", encoding="utf-8") as f:
        return {r["idx"]: r for r in json.load(f)["rows"]}


def stages_of(r):
    if not r["parse_ok"]:
        return None
    try:
        return json.loads(r["pred_text"])["stages"]
    except Exception:
        return None


def expand(st):
    out = []
    for s in st or []:
        out += [s["family"]] * int(s.get("repeat", 1))
    return out


def bag_excl(pred_st, gold_st):
    p, g = expand(pred_st), expand(gold_st)
    if not p:
        return 0.0
    pc, gc = Counter(p), Counter(g)
    tp = sum(min(pc[k], gc[k]) for k in pc)
    return 2 * tp / (len(p) + len(g)) if (len(p) + len(g)) else 0.0


def first_complete_json(text):
    """Extract the first balanced top-level JSON object, if any."""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                frag = text[start:i + 1]
                try:
                    json.loads(frag)
                    return frag
                except Exception:
                    return None
    return None


def main():
    pre = load(os.path.join(PULL, "a1_arm768_raw.json.gz"))
    post = load(os.path.join(PULL, "adprime_post768_raw.json"))
    s131 = json.load(open(os.path.join(
        HERE, "..", "docs", "reports", "route2_p0_contract",
        "plan_pipeline_v1", "planner_design", "A1_SAMPLE_131.json"),
        encoding="utf-8"))
    strata = {x["idx"]: x["stratum"] for x in s131["samples"]}
    dev = [json.loads(l) for l in open(
        os.path.join(DW, "planner_v2_dev_fix1_loopinv.jsonl"),
        encoding="utf-8") if l.strip()]

    out = {"schema": "adprime_failure_attribution_v1"}

    # ---- Q1: training trajectory ----
    led = json.load(open(os.path.join(PULL, "run_ledger.json"),
                         encoding="utf-8"))
    log_tail = ["step 5/150 loss=1.2815 lr=9.97e-06 rows=160 tgt_trunc=0 (593s)"]
    out["Q1_training_trajectory"] = {
        "steps": led["steps"], "examples": led["stats"]["examples"],
        "tokens": led["stats"]["tokens"],
        "final_loss_window": led.get("final_loss_window"),
        "loss_points": ("step5=1.2815 (only logged point; log_every=5) + "
                        "final window"),
        "grad_norms": "NOT RECORDED (trainer does not log; instrumentation "
                      "gap for any future run)",
        "lr_schedule": "cosine 1e-5 -> 0 over 9 steps (deterministic)",
        "verdict": "insufficient trajectory data to detect abnormal "
                   "single-step updates; EOS-token-specific loss was not "
                   "logged either",
    }

    # ---- Q2 + Q3 ----
    c_rows = [i for i in pre
              if pre[i]["termination"] != "MAX_TOKENS"
              and post[i]["termination"] == "MAX_TOKENS"]
    gold = {i: (json.loads(r["target"]) if isinstance(r["target"], str)
                else r["target"]) for i, r in enumerate(dev)}
    deg = []
    for i in pre:
        bp = bag_excl(stages_of(pre[i]), gold[i]["stages"])
        bp_o = bag_excl(stages_of(post[i]), gold[i]["stages"])
        if bp_o < bp - 0.01:
            deg.append(i)
    c_set, deg_set = set(c_rows), set(deg)
    out["Q2_concentration"] = {
        "n_newly_runaway": len(c_rows),
        "n_coverage_degraded": len(deg),
        "overlap": len(c_set & deg_set),
        "jaccard": round(len(c_set & deg_set)
                         / max(1, len(c_set | deg_set)), 3),
        "c_strata": dict(Counter(strata[i] for i in c_rows)),
        "c_gold_len_buckets": dict(Counter(
            ("1-5" if len(gold[i]["stages"]) <= 5 else
             ("6-15" if len(gold[i]["stages"]) <= 15 else "16+"))
            for i in c_rows)),
        "deg_strata": dict(Counter(strata[i] for i in deg)),
    }

    mech = Counter()
    detail = []
    for i in c_rows:
        t = post[i]["pred_text"]
        complete = first_complete_json(t) is not None
        if complete:
            m = "B_complete_json_then_ran_on(EOS_shifted_later)"
        else:
            m = "C_no_complete_object(unbounded_prefix)"
        mech[m] += 1
        detail.append({"idx": i, "stratum": strata[i],
                       "pre_term": pre[i]["termination"],
                       "pre_tokens": pre[i]["generated_tokens"],
                       "post_tokens": post[i]["generated_tokens"],
                       "pre_n_stages": pre[i]["pred_n_stages"],
                       "mechanism": m})
    out["Q3_mechanism"] = {
        "distribution": dict(mech),
        "post_all_at_768_cap": all(post[i]["generated_tokens"] == 768
                                   for i in c_rows),
        "pre_termination_of_c_rows": dict(Counter(
            pre[i]["termination"] for i in c_rows)),
        "detail_head": detail[:12],
    }
    json.dump(out, open(os.path.join(PULL,
                                     "ADPRIME_FAILURE_ATTRIBUTION_V1.json"),
                         "w", encoding="utf-8"), indent=2,
              ensure_ascii=False)
    print(json.dumps(out, indent=2, ensure_ascii=False)[:2600])
    return 0


if __name__ == "__main__":
    sys.exit(main())
