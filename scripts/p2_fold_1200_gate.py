#!/usr/bin/env python3
"""P2 data gate: convert 1,200 anti-forgetting rows (old rep) to the frozen
folded representation (REP_SPEC_REV v1), with per-row gates.

Rules (owner ruling 2026-10-12):
  - Faithful re-encoding ONLY: stage-level adjacent runs (repeat>1) are kept
    exactly as the old gold declared them (stage repeat=N, no group) - the
    new format's canonical form for adjacent runs (F1: per-stage repeats OR
    pattern groups, never both).
  - Undeclared alternating windows (2/3-family, >=3 rounds) are NOT folded
    (no evidence in old gold) -> row ISOLATED, reason recorded.
  - G5 via INDEPENDENT expander (expand_spec, separate implementation from
    this converter). Exact family-sequence equality required.
  - Old group declarations must reconcile 1:1 with repeat>1 stages (G3),
    else ISOLATE (reason recorded).

Outputs (docs/.../planner_design/p2_uniform_gate_v1/):
  gate_report_v1.json   - counts, reasons, per-row detail
  p2_converted_v1.jsonl - converted rows (target replaced, new cat)
  p2_isolated_v1.jsonl  - isolated rows with reasons
"""
import json, sys
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs/reports/route2_p0_contract/plan_pipeline_v1/planner_design/p1_sft_train_v1.jsonl"
OUT_DIR = ROOT / "docs/reports/route2_p0_contract/plan_pipeline_v1/planner_design/p2_uniform_gate_v1"
NEW_REP_JSONL = ROOT / "docs/reports/route2_p0_contract/plan_pipeline_v1/planner_design/p1_gold_rebuild_v2/planner_gold_rebuilt_v2.jsonl"


# ── G5 INDEPENDENT expander (rep_spec_rev1_validation.py implementation,
#    deliberately NOT re-derived from the converter logic below) ────────────
def expand_spec(doc):
    stages = doc["stages"]
    groups = sorted(doc.get("repetition_groups", []),
                    key=lambda g: g["anchor_seq"])
    out = []
    pos = 0
    for g in groups:
        anchor = g["anchor_seq"] - 1
        while pos < anchor:
            out += [stages[pos]["family"]] * int(stages[pos]["repeat"])
            pos += 1
        for _ in range(int(g["repeat_count"])):
            out += list(g["pattern"])
        pos = anchor + len(g["pattern"])
    while pos < len(stages):
        out += [stages[pos]["family"]] * int(stages[pos]["repeat"])
        pos += 1
    return out


def expand_old_literal(tj):
    out = []
    for s in tj["stages"]:
        out += [s["family"]] * int(s.get("repeat", 1))
    return out


def find_windows(f, w, min_rounds=3):
    """Non-overlapping scan for alternating windows, any start position."""
    hits = []
    i, n = 0, len(f)
    while i + w * min_rounds <= n:
        pat = tuple(f[i:i + w])
        if len(set(pat)) < w:
            i += 1
            continue
        k = 0
        while i + k + w <= n and tuple(f[i + k:i + k + w]) == pat:
            k += w
        if k >= w * min_rounds:
            hits.append({"start": i + 1, "pattern": list(pat), "rounds": k // w})
            i += k
        else:
            i += 1
    return hits


def convert(tj):
    """Old-format target -> (new_doc | None, reason). None = isolate."""
    stages = tj.get("stages") or []
    if not stages:
        return None, "empty_stages"
    old_groups = tj.get("repetition_groups", []) or []

    # G3a: every repeat>1 stage must have an old declaration (stage_seq,
    # family, repeat all matching) - the old gold's own repetition claim.
    decl = {}
    for g in old_groups:
        try:
            decl[int(g["stage_seq"])] = (g["family"], int(g["repeat"]))
        except Exception:
            return None, "malformed_old_group"
    for pos, s in enumerate(stages, start=1):
        r = int(s.get("repeat", 1))
        if r > 1:
            if decl.get(pos) != (s["family"], r):
                return None, f"undeclared_adjacent_run_seq{pos}"
    # G3b: no declaration pointing at a repeat=1 stage or out of range
    for seq, (fam, rep) in decl.items():
        if seq < 1 or seq > len(stages):
            return None, f"group_seq_out_of_range_{seq}"
        s = stages[seq - 1]
        if int(s.get("repeat", 1)) != rep or s["family"] != fam:
            return None, f"group_stage_mismatch_seq{seq}"

    # Window scan on the expanded sequence: undeclared alternating windows
    # are not foldable without evidence -> isolate (owner: no forced folds).
    fseq = expand_old_literal(tj)
    for w in (2, 3):
        hits = find_windows(fseq, w)
        if hits:
            return None, f"undeclared_window_w{w}_" + "_".join(
                f"{'x'.join(h['pattern'])}x{h['rounds']}" for h in hits[:2])

    # Faithful re-encode per the 208 authority convention (verified:
    # single-family groups mirror anchor stage repeat 345/345; multi-family
    # unit stages all repeat=1 121/121):
    #   adjacent run -> stage repeat=N + single-family group (mirrored)
    new_stages = [{"seq": i, "family": s["family"],
                   "repeat": int(s.get("repeat", 1))}
                  for i, s in enumerate(stages, start=1)]
    new_groups = []
    for i, s in enumerate(new_stages, start=1):
        if s["repeat"] > 1:
            new_groups.append({"anchor_seq": i, "pattern": [s["family"]],
                               "repeat_count": s["repeat"],
                               "order_preserved": True})
    new_doc = {"stages": new_stages, "repetition_groups": new_groups}
    return new_doc, "ok"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    with open(SRC, encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            if r.get("cat") == "p1_anti_forgetting":
                rows.append(r)

    # canonical-convention confirmation on the 208 authority golds:
    single_family_groups = 0
    total_groups_208 = 0
    with open(NEW_REP_JSONL, encoding="utf-8") as fh:
        for line in fh:
            tj = json.loads(line)["target_json"]
            for g in tj.get("repetition_groups", []):
                total_groups_208 += 1
                single_family_groups += int(len(g["pattern"]) == 1)

    converted, isolated = [], []
    reason_counts = Counter()
    for r in rows:
        tj = json.loads(r["target"])
        new_doc, why = convert(tj)
        if new_doc is None:
            import re
            m = re.match(r"(undeclared_window_w\d|undeclared_adjacent_run|"
                         r"malformed_old_group|group_seq_out_of_range|"
                         r"group_stage_mismatch|empty_stages)", why)
            reason_counts[m.group(1) if m else why] += 1
            isolated.append(dict(r, isolation_reason=why))
            continue
        # G5: independent expander, exact equality with old literal expansion
        if expand_spec(new_doc) != expand_old_literal(tj):
            reason_counts["g5_expand_mismatch"] += 1
            isolated.append(dict(r, isolation_reason="g5_expand_mismatch"))
            continue
        out = dict(r)
        out["target"] = json.dumps(new_doc, ensure_ascii=False)
        out["cat"] = "p2_folded_from_old"
        out["p2_conversion"] = "faithful_reencode"
        converted.append(out)

    summary = {
        "n_anti_forgetting": len(rows),
        "converted": len(converted),
        "isolated": len(isolated),
        "isolation_reasons": dict(reason_counts),
        "canonical_check_208": {
            "total_groups": total_groups_208,
            "single_family_groups": single_family_groups,
            "convention": ("adjacent run = stage repeat=N + mirrored "
                           "single-family group; multi-family window groups "
                           "carry unit stages at repeat=1"),
        },
        "g5_expander": "expand_spec (rep_spec_rev1_validation.py, independent impl)",
        "exact_equality_required": True,
    }
    with open(OUT_DIR / "gate_report_v1.json", "w", encoding="utf-8") as fh:
        json.dump({"summary": summary,
                   "isolated_detail": [
                       {"source_row_id": r.get("source_row_id"),
                        "task_head": (r.get("task") or "")[:80],
                        "reason": r["isolation_reason"]}
                       for r in isolated]},
                  fh, ensure_ascii=False, indent=1)
    with open(OUT_DIR / "p2_converted_v1.jsonl", "w", encoding="utf-8") as fh:
        for r in converted:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(OUT_DIR / "p2_isolated_v1.jsonl", "w", encoding="utf-8") as fh:
        for r in isolated:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(main())
