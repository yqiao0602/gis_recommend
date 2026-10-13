#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A1 result analysis: functional gate (768 re-run vs frozen p0b_768) +
runaway-generation characterization + idx=1024. Read-only."""
import gzip
import json
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

DW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                  "04_DIAG_WORK")
PULL = os.path.join(DW, "a1_pull")
PD = os.path.join(DW, "..", "system_redesign", "docs", "reports",
                  "route2_p0_contract", "plan_pipeline_v1", "planner_design")


def load_arm(name):
    with gzip.open(os.path.join(PULL, name), "rt", encoding="utf-8") as f:
        return {r["idx"]: r for r in json.load(f)["rows"]}


def main():
    b = load_arm("a1_arm768_raw.json.gz")
    e = load_arm("a1_arm2048_raw.json.gz")

    frozen = json.load(open(os.path.join(PD, "p0b_768", "predictions.json"),
                            encoding="utf-8"))["items"]

    out = {"schema": "a1_result_analysis_v1"}

    # ---- 1. functional gate: 768 re-run vs frozen p0b_768 ----
    term_agree = parse_agree = text_eq = 0
    n = len(b)
    term_dis_rows = []
    for i, r in b.items():
        fr = frozen[i]
        fterm = ("MAX_TOKENS" if fr.get("hit_max_new_tokens") else "EOS")
        if fterm == r["termination"]:
            term_agree += 1
        else:
            term_dis_rows.append(i)
        fparse = bool(fr.get("pred_text") and
                      json.loads(fr["pred_text"]).get("stages")
                      if _ok(fr.get("pred_text")) else False)
        if fparse == r["parse_ok"]:
            parse_agree += 1
        if (fr.get("pred_text") or "").strip() == (r["pred_text"] or "").strip():
            text_eq += 1
    out["functional_gate_768_vs_frozen"] = {
        "n": n,
        "termination_agreement": round(term_agree / n, 4),
        "parse_agreement": round(parse_agree / n, 4),
        "pred_text_exact_agreement": round(text_eq / n, 4),
        "termination_disagreement_rows": term_dis_rows[:20],
        "verdict": "FAIL" if text_eq / n < 0.95 else "PASS",
        "note": ("cross-host greedy: frozen = rented-box RTX3090; re-run = "
                 "mdzhang A10; 4-bit numerics diverge at margin"),
    }

    # ---- 2. runaway characterization (2048-arm truncated rows) ----
    tt = [r for r in e.values() if r["termination"] == "MAX_TOKENS"]
    out["runaway_2048"] = {
        "n": len(tt), "all_at_cap": all(r["generated_tokens"] == 2048
                                        for r in tt),
        "gold_len_of_truncated": sorted(r["gold_n_stages"]
                                        for r in tt)[:20],
        "note": None,
    }
    # text tail sample for degeneration check
    sample = sorted(tt, key=lambda r: -r["generated_tokens"])[0]
    tail = sample["pred_text"][-400:]
    out["runaway_sample"] = {"idx": sample["idx"], "tail400": tail}

    # repeat signature: longest repeated 20-char block heuristic
    def repeat_ratio(text):
        t = text[-1000:]
        if len(t) < 100:
            return 0.0
        from collections import Counter as C
        grams = [t[i:i + 20] for i in range(0, len(t) - 20, 10)]
        c = C(grams)
        top = c.most_common(1)[0][1] if c else 0
        return round(top / max(1, len(grams)), 3)
    rr = [repeat_ratio(r["pred_text"]) for r in tt]
    out["runaway_repeat_signature"] = {
        "mean_top20gram_ratio_tail1k": round(sum(rr) / len(rr), 3),
        "rows_with_ratio_gt_0.5": sum(1 for x in rr if x > 0.5),
    }

    # ---- 3. rescue / gate metrics ----
    resc = [i for i in b if b[i]["termination"] == "MAX_TOKENS"
            and e[i]["termination"] != "MAX_TOKENS"]
    out["rescue"] = {"count": len(resc), "rows": resc[:10]}
    out["truncation_counts"] = {
        "baseline_768_rerun": sum(1 for r in b.values()
                                  if r["termination"] == "MAX_TOKENS"),
        "experiment_2048": len(tt),
        "frozen_p0b768_on_these_131": sum(
            1 for i in b if frozen[i].get("hit_max_new_tokens")),
    }
    json.dump(out, open(os.path.join(PULL, "A1_RESULT_ANALYSIS_V1.json"),
                        "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(json.dumps(out, indent=2, ensure_ascii=False)[:3000])


def _ok(text):
    try:
        json.loads(text or "")
        return True
    except Exception:
        return False


if __name__ == "__main__":
    main()
