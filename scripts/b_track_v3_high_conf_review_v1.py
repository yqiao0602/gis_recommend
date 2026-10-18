#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Classify the V3 high-confidence review queue (read-only; no split change).

Inputs:
  - B_TRACK_SPLIT_MANIFEST_V3.json
  - B_TRACK_TASK_FAMILY_DECISIONS_V1.jsonl.gz
  - B_TRACK_TASK_FAMILY_MERGE_LEDGER_V1.json.gz

Outputs:
  - B_TRACK_V3_HIGH_CONF_REVIEW_V1.json   (5,778 deduped relations)
  - B_TRACK_V3_HIGH_CONF_REVIEW_V1.md     (human-readable triage)

Definitions (frozen for this review):
  pending high-confidence = decision pending, V3 cross-split,
      title_j >= 0.60 or body_j >= 0.60.
  deferred high-confidence = group edge (G1/D2) connecting different families,
      title_j >= 0.60 or asset_shared >= 1.
  The two sets are deduped by unordered component pair; overlap is reported.

Classes are a triage proposal, NOT an owner ruling:
  A_merge_candidate  direct same-task evidence (shared targets/source/chain)
  B_keep_candidate   evidence of different tasks (purpose/target/source conflict)
  C_conflict         both A and B indicators
  C_undetermined     insufficient or unclear evidence
"""
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
B = (REPO / "docs/reports/route2_p0_contract/plan_pipeline_v1/"
     "planning_capability_audit_v1/diag50_v1/b_track_audit_v1")


def load_v3():
    v3 = json.loads((B / "B_TRACK_SPLIT_MANIFEST_V3.json").read_text(encoding="utf-8"))
    fids = v3["family_ids"]
    cf, cs = {}, {}
    for c, fi, s in zip(v3["row_component"], v3["row_family"], v3["row_split"]):
        cf.setdefault(c, fids[fi])
        cs.setdefault(c, s)
    return cf, cs, v3


GENERIC_REVIEW_TOKENS = set("""
sery serie series time temporal multi data value values pixel pixels region
regions area areas map maps image images imagery band bands class classes type
types count number fraction feature features landsat sentinel modis s1 s2
satellite collection scale resolution level site new different various multiple
based using use workflow task result results change changes year years date
dates product products method methods study
vv vh sar glcm featur texture reflectance backscatter
after before event events
""".split())


def eff_targets(ev):
    return [t for t in ev["target_shared"]
            if t not in GENERIC_REVIEW_TOKENS and not t.isdigit()]


def pattern(ev):
    t, b = ev["title_j"], ev["body_j"]
    o, df, a = len(eff_targets(ev)), len(ev["dataset_shared"]), len(ev["asset_shared"])
    if not ev["purpose_compatible"]:
        return "purpose_conflict"
    if a >= 3 and t < 0.60:
        return "same_assets_diff_title"
    if o >= 2 and t < 0.60:
        return "same_targets_diff_title"
    if ev["chain_same"] and o == 0:
        return "same_chain_diff_target"
    if t >= 0.60 and a == 0 and df == 0:
        return "same_title_diff_source"
    if b >= 0.60 and t < 0.40 and o < 2 and a == 0:
        return "body_only"
    if not ev["task_type_same"]:
        return "task_type_diff"
    return "mixed_or_weak"


def classify(ev):
    t, b = ev["title_j"], ev["body_j"]
    o = len(eff_targets(ev))
    df, a = len(ev["dataset_shared"]), len(ev["asset_shared"])
    p, tt, cs = ev["purpose_compatible"], ev["task_type_same"], ev["chain_same"]
    merge = (
        (o >= 2 and p and (a >= 1 or df >= 1 or cs))
        or (a >= 3 and (t >= 0.40 or b >= 0.60) and p)
        or (a >= 5 and b >= 0.60 and p)
        or (cs and t >= 0.60 and p and o >= 1)
        or (b >= 0.70 and (t >= 0.40 or o >= 1) and p)
        or (t >= 0.60 and o >= 2 and p and tt)
    )
    keep = (
        ((not p) and o == 0 and a == 0 and df == 0)
        or (o == 0 and a == 0 and df == 0 and t < 0.40 and b < 0.60)
        or ((not tt) and o == 0 and a == 0 and t < 0.50)
        or (cs and o == 0 and not p)
        or (cs and o == 0 and a == 0 and not tt)
    )
    if merge and keep:
        return "C_conflict", "A and B indicators both present"
    if merge:
        return "A_merge_candidate", "shared target/source/chain evidence"
    if keep:
        return "B_keep_candidate", "purpose/target/source conflict or no overlap"
    return "C_undetermined", "insufficient or mixed evidence"


def main():
    cf, cs, v3 = load_v3()
    ledger = None
    with gzip.open(B / "B_TRACK_TASK_FAMILY_MERGE_LEDGER_V1.json.gz",
                   "rt", encoding="utf-8") as fh:
        ledger = json.load(fh)
    pend, defer = {}, {}
    v2_pending_hi = 0
    with gzip.open(B / "B_TRACK_TASK_FAMILY_DECISIONS_V1.jsonl.gz",
                   "rt", encoding="utf-8") as fh:
        for line in fh:
            e = json.loads(line)
            a, b = e["a"], e["b"]
            key = (a, b) if a < b else (b, a)
            ev = e["evidence"]
            v2_cross = e["split_a"] != e["split_b"]
            v3_cross = cs.get(a) != cs.get(b)
            hi_pending = ev["title_j"] >= 0.60 or ev["body_j"] >= 0.60
            if e["decision"] == "pending":
                if v2_cross and hi_pending:
                    v2_pending_hi += 1
                if v3_cross and hi_pending:
                    pend[key] = e
            if e.get("group_id"):
                same_family = cf.get(a) == cf.get(b)
                hi_defer = ev["title_j"] >= 0.60 or len(ev["asset_shared"]) >= 1
                if (not same_family) and hi_defer:
                    defer[key] = e
    rows = []
    for kind, mapping in (("pending", pend), ("deferred", defer)):
        for key, e in mapping.items():
            ev = e["evidence"]
            a, b = e["a"], e["b"]
            cls_, reason = classify(ev)
            rows.append({
                "review_id": "",
                "pair": list(key), "kind": kind, "rule": e["rule"],
                "signals": e["signals"],
                "class": cls_, "class_reason": reason,
                "pattern": pattern(ev),
                "strength": round(ev["title_j"] + 0.5 * ev["body_j"]
                                  + 0.3 * len(eff_targets(ev))
                                  + 0.5 * len(ev["asset_shared"])
                                  + (0.3 if ev["chain_same"] else 0), 4),
                "effective_targets": eff_targets(ev),
                "v2_cross": e["split_a"] != e["split_b"],
                "v3_cross": cs.get(a) != cs.get(b),
                "v2_splits": [e["split_a"], e["split_b"]],
                "v3_splits": [cs.get(a), cs.get(b)],
                "family_a": cf.get(a), "family_b": cf.get(b),
                "family_same": cf.get(a) == cf.get(b),
                "evidence": ev,
            })
    rows.sort(key=lambda r: (r["class"], r["pattern"], r["kind"], r["rule"],
                             r["pair"][0], r["pair"][1]))
    for i, r in enumerate(rows, 1):
        r["review_id"] = f"R{i:05d}"
    # ledger cross-checks
    checks = {
        "ledger_pending_cross_split_v2": len(ledger.get("pending_edges_cross_split", [])),
        "reconstructed_pending_high_conf_v2": v2_pending_hi,
        "pending_high_conf_cross_v3": len(pend),
        "ledger_family_assignment_deferred": ledger["counts"].get("family_assignment_deferred"),
        "reconstructed_deferred_high_conf": len(defer),
        "ledger_deferred_high_confidence": ledger["counts"].get("deferred_high_confidence"),
        "overlap_pairs": len(set(pend) & set(defer)),
        "union_pairs": len(set(pend) | set(defer)),
    }
    out = {
        "artifact": "B_TRACK_V3_HIGH_CONF_REVIEW_V1", "date": "2026-10-18",
        "definitions": {
            "pending_high_conf": "decision pending, V3 cross-split, title_j>=0.60 or body_j>=0.60",
            "deferred_high_conf": "G1/D2 edge across different families, title_j>=0.60 or asset_shared>=1",
            "dedup": "unordered component pair; overlap reported",
            "classification": "triage proposal only; owner adjudicates",
        },
        "checks": checks,
        "counts": {
            "total_unique": len(rows),
            "by_kind": dict(Counter(r["kind"] for r in rows)),
            "by_class": dict(Counter(r["class"] for r in rows)),
            "by_class_kind": {f"{k[0]}|{k[1]}": n for k, n in
                              Counter((r["class"], r["kind"]) for r in rows).items()},
            "by_pattern": dict(Counter(r["pattern"] for r in rows)),
            "by_pattern_class": {f"{k[0]}|{k[1]}": n for k, n in
                                 Counter((r["pattern"], r["class"]) for r in rows).items()},
            "deferred_cross_v3": sum(1 for r in rows
                                     if r["kind"] == "deferred" and r["v3_cross"]),
            "deferred_same_v3": sum(1 for r in rows
                                    if r["kind"] == "deferred" and not r["v3_cross"]),
            "affected_components": len({x for r in rows for x in r["pair"]}),
            "affected_families": len({f for r in rows for f in (r["family_a"], r["family_b"])
                                      if f}),
        },
        "relations": rows,
    }
    (B / "B_TRACK_V3_HIGH_CONF_REVIEW_V1.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("checks", "counts")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
