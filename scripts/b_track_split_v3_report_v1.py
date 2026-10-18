#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Summarize Split V3 and the task-family ledger for the acceptance report.

Read-only. Output: B_TRACK_SPLIT_V3_SUMMARY_V1.json
"""
import gzip
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
B = (REPO / "docs/reports/route2_p0_contract/plan_pipeline_v1/"
     "planning_capability_audit_v1/diag50_v1/b_track_audit_v1")


def main():
    v2 = json.loads((B / "B_TRACK_SPLIT_MANIFEST_V2.json").read_text(encoding="utf-8"))
    v3 = json.loads((B / "B_TRACK_SPLIT_MANIFEST_V3.json").read_text(encoding="utf-8"))
    with gzip.open(B / "B_TRACK_TASK_FAMILY_MERGE_LEDGER_V1.json.gz",
                   "rt", encoding="utf-8") as fh:
        led = json.load(fh)
    ver = json.loads((B / "B_TRACK_SPLIT_V3_VERIFICATION_V1.json").read_text(encoding="utf-8"))
    fams = led["families"]
    sizes = Counter(f["n_components"] for f in fams)
    top = sorted(fams, key=lambda f: f["n_components"], reverse=True)[:10]
    flags = Counter(x for f in fams for x in f["audit_flags"])
    # known family membership
    def family_of(cid):
        for f in fams:
            if any(m["component_id"] == cid for m in f["members"]):
                return f
        return None
    known = {}
    for label, ids in (("oil", [48801, 50842, 74228]),
                       ("forest", [45165, 103943])):
        fs = [family_of(c) for c in ids]
        fids = sorted({f["family_id"] for f in fs if f})
        known[label] = {"components": ids, "families": fids,
                        "one_family": len(fids) == 1,
                        "sizes": [f["n_components"] for f in fs if f]}
    pending_cross = led.get("pending_edges_cross_split", [])
    high_conf_pending = [e for e in pending_cross
                         if e["evidence"]["title_j"] >= 0.60
                         or e["evidence"]["body_j"] >= 0.60]
    out = {
        "artifact": "B_TRACK_SPLIT_V3_SUMMARY_V1", "date": "2026-10-18",
        "verification_all_pass": ver.get("all_pass"),
        "counts": led["counts"],
        "split_v3": {
            "families": v3["split_families"],
            "components": v3["split_components"],
            "rows": v3["split_rows"],
        },
        "family_size": {
            "merged_families": len(fams),
            "size_histogram_top": sizes.most_common(10),
            "over_200": sum(1 for f in fams if f["n_components"] > 200),
            "over_50": sum(1 for f in fams if f["n_components"] > 50),
            "largest": [{"family_id": f["family_id"], "n_components": f["n_components"],
                         "n_rows": f["n_rows"], "split_v3": f["split_v3"],
                         "v2_splits": f["v2_splits"],
                         "audit_flags": f["audit_flags"]} for f in top],
        },
        "audit_flags": dict(flags),
        "cross_split": {
            "merge_edges_resolved": led["counts"]["cross_split_merge_edges"],
            "pending_cross_split": len(pending_cross),
            "pending_cross_split_high_confidence": len(high_conf_pending),
            "pending_cross_split_high_confidence_examples": high_conf_pending[:20],
            "deferred_by_size_cap": led["counts"].get(
                "family_assignment_deferred"),
            "deferred_high_confidence": led["counts"].get(
                "deferred_high_confidence"),
        },
        "known_families": known,
        "v2_to_v3": {
            "rows_changed": led["counts"]["rows_changed_v2_to_v3"],
            "components_changed": led["counts"]["components_changed_v2_to_v3"],
            "audited_rows": led["counts"]["audited_rows"],
            "audited_split_transitions": led["counts"]["audited_split_transitions"],
        },
        "skipped_buckets": led.get("skipped_buckets", {}),
    }
    (B / "B_TRACK_SPLIT_V3_SUMMARY_V1.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
