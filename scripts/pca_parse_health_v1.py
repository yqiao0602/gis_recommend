#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PCA scoring Step 2 — per-row parse + format-health classification (183 rows).

Frozen-protocol rules:
  - all 183 raw outputs retained; parse failure NEVER drops a row from the
    denominator — it sets scoreable=False with a reason;
  - hit_cap (generation budget flag) and termination_status (end
    classification) are DISTINCT dimensions; cross-tab emitted;
  - END_OF_PLAN position audit: trailing (<=80 trailing chars of boilerplate),
    mid-text, or absent (owner round-16 priority on A_base);
  - repetition: line-level duplicate ratio (fine-grained semantic-loop
    analysis happens at scoring; this is the mechanical layer);
  - scoreable = format_valid AND content_assessable (heuristic layer; judge
    makes final per-row assessability calls under the frozen rubric).
"""
import json, hashlib, glob, re
from collections import Counter

FILES = sorted(glob.glob("../pca_data_ref/pca_outputs_batch1/outputs/*/*/run_001.json"))
OUT = "docs/reports/route2_p0_contract/plan_pipeline_v1/planning_capability_audit_v1/pca_parse_health_v1.json"

def classify(text, gen_tokens, hit_cap, recorded_term):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    n_lines = len(lines)
    # END OF PLAN position audit
    idx = text.rfind("END OF PLAN")
    if idx < 0:
        eop_pos = "absent"
    else:
        tail = text[idx + len("END OF PLAN"):].strip()
        eop_pos = "trailing" if len(tail) <= 80 else "midtext"
    # step-node heuristic: numbered/bulleted lines or >=3 short lines with step verbs
    step_lines = sum(1 for l in lines if re.match(r"^(\d+[\).\:]|[-*•]|step\s*\d)", l, re.I))
    stepish = sum(1 for l in lines if re.match(r"^(load|read|reproject|clip|mask|filter|compute|calculate|classify|derive|extract|aggregate|merge|export|convert|apply|combine|identify|flag|rank|select|buffer|repair|check|summar)", l, re.I))
    format_valid = (step_lines >= 1 or stepish >= 2 or n_lines >= 3)
    # repetition: exact duplicate line ratio
    if n_lines:
        dup_ratio = 1 - len(set(lines)) / n_lines
    else:
        dup_ratio = 1.0
    # content assessability (mechanical layer): not near-empty, not pure repetition
    words = len(text.split())
    content_assessable = (words >= 25) and (dup_ratio < 0.8) and n_lines >= 2
    scoreable = format_valid and content_assessable
    return {
        "n_lines": n_lines, "n_words": words, "dup_ratio": round(dup_ratio, 3),
        "end_marker": eop_pos, "format_valid": format_valid,
        "content_assessable": content_assessable, "scoreable": scoreable,
        "scoreable_reason": None if scoreable else (
            "no step structure" if not format_valid else
            ("near-empty" if words < 25 else "high repetition")),
    }

def main():
    rows = []
    for f in FILES:
        r = json.load(open(f, encoding="utf-8"))
        cls = classify(r["raw_output"], r["gen_tokens"], r["hit_cap"], r["termination_status"])
        rows.append({"task_id": r["task_id"], "arm": r["arm"],
                     "group": "Bprime" if r["arm"] == "Bprime_diag" else None,
                     "gen_tokens": r["gen_tokens"], "hit_cap": r["hit_cap"],
                     "recorded_termination": r["termination_status"],
                     "main_scoring": r["main_scoring"], **cls})
    # cross-tab: hit_cap x recorded_termination (definitions are DISTINCT)
    cross = Counter((r["hit_cap"], r["recorded_termination"]) for r in rows)
    by_arm = {}
    for arm in ("A_base", "B_stage1", "C_stage1_tool", "Bprime_diag"):
        rs = [r for r in rows if r["arm"] == arm]
        n = len(rs)
        by_arm[arm] = {
            "n": n,
            "normal_termination_rate": round(sum(1 for r in rs if r["end_marker"] == "trailing") / n, 3),
            "parse_structure_rate": round(sum(1 for r in rs if r["format_valid"]) / n, 3),
            "scoreable_rate": round(sum(1 for r in rs if r["scoreable"]) / n, 3),
            "eop_trailing": sum(1 for r in rs if r["end_marker"] == "trailing"),
            "eop_midtext": sum(1 for r in rs if r["end_marker"] == "midtext"),
            "eop_absent": sum(1 for r in rs if r["end_marker"] == "absent"),
            "high_repetition": sum(1 for r in rs if r["dup_ratio"] >= 0.5),
            "denominator": n,
        }
    payload = {"_meta": {
        "stage": "PCA scoring Step-2 parse + format health v1",
        "n_rows": len(rows),
        "hit_cap_x_termination_cross": {f"hit_cap={h}|{t}": n for (h, t), n in sorted(cross.items())},
        "rules": "parse failure never drops rows; scoreable heuristic pre-judge; "
                 "hit_cap (budget flag) and termination_status (classification) distinct",
        "by_arm_summary": by_arm},
        "rows": rows}
    blob = json.dumps(payload, ensure_ascii=False, indent=1)
    open(OUT, "w", encoding="utf-8", newline="").write(blob)
    print("hit_cap x termination cross:", dict(sorted(cross.items())))
    for arm, s in by_arm.items():
        print(f"{arm}: n={s['n']} normalTerm={s['normal_termination_rate']} "
              f"parseStruct={s['parse_structure_rate']} scoreable={s['scoreable_rate']} "
              f"eop[T/M/A]={s['eop_trailing']}/{s['eop_midtext']}/{s['eop_absent']} hiRep={s['high_repetition']}")
    print("file_sha256:", hashlib.sha256(blob.encode()).hexdigest()[:16])

if __name__ == "__main__":
    main()
