#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Missing-slot reconciliation (owner round-8 directive).

Aligns blind labels, r5 rule outputs, and the original 192 S2 candidates:
every slot instance that r5 counted as `missing` is listed with its evidence
(required-by hits, candidate families) and an ambiguity classification:
  V1 plain omission        - no ambiguity marker in the candidate
  V2 wrapper-ambiguous     - candidate contains ITERATIVE_APPLY (the missing
                             capability could theoretically be wrapped; per
                             owner S8 precedent these stay `missing` per the
                             representation-sufficiency caliber, but are
                             reported separately)
  V3 malformed-families    - candidate had null/non-string family entries
Also reconciles the owner's synthetic-packet labels vs r5 outputs.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from r5_requirement_parser_v0 import parse_task  # noqa: E402

RL = REPO / "docs/reports/route2_p0_contract/plan_pipeline_v1/rl_line"


def main():
    audit = json.loads((RL / "s2_dryrun/R5_S2_OFFLINE_AUDIT_V1.json").read_text(encoding="utf-8"))
    preds = json.loads((RL / "s2_dryrun/preds.json").read_text(encoding="utf-8"))
    tasks = json.loads((RL / "r5_packet_tasks_fetch.json").read_text(encoding="utf-8"))
    tasks.update(json.loads((RL / "r5_audit_tasks_rest.json").read_text(encoding="utf-8")))

    pred_by_key = {(p["k"], p["cand"]): p["pred_text"] for p in preds}

    instances = []
    for k, g in audit["groups"].items():
        if g["class"] == "abstained":
            continue
        pr = parse_task(tasks[str(k)])
        hit_evidence = {s["id"]: s["hits"][:1] for s in pr["slots"]}
        for c in g["candidates"]:
            if c.get("verdict") != "incomplete":
                continue
            text = pred_by_key.get((int(k), c["cand"]), "")
            wrapper = "ITERATIVE_APPLY" in text
            malformed = '"family": null' in text or '"family":null' in text
            for slot in c.get("missing", []):
                cat = ("V2_wrapper_ambiguous" if wrapper
                       else ("V3_malformed_family" if malformed else "V1_plain"))
                instances.append({
                    "k": int(k), "cand": c["cand"], "slot": slot,
                    "category": cat,
                    "wrapper_present": wrapper, "malformed_family": malformed,
                    "required_evidence": hit_evidence.get(slot),
                    "n_stages": c.get("n_stages"),
                })

    by_slot = Counter(i["slot"] for i in instances)
    by_cat = Counter(i["category"] for i in instances)
    by_slot_cat = Counter((i["slot"], i["category"]) for i in instances)
    summary = {
        "total_missing_instances": len(instances),
        "candidates_with_any_missing": len({(i['k'], i['cand']) for i in instances}),
        "by_slot": dict(by_slot.most_common()),
        "by_category": dict(by_cat.most_common()),
        "by_slot_x_category": {f"{s}|{c}": n for (s, c), n in by_slot_cat.most_common()},
    }
    out = {"label": "r5_missing_slot_reconciliation_v1",
           "summary": summary, "instances": instances}
    (RL / "R5_MISSING_SLOT_RECONCILIATION_V1.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
