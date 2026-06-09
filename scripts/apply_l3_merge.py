# -*- coding: utf-8 -*-
"""
Apply the v2 L3 merge plan to the training data.

Input:
  outputs/pipeline/step8/labeled_workflows_l3_v4_cleaned.json
  outputs_v2/l3_merge_plan.csv
  outputs_v2/classification_hierarchy_v2.csv

Output:
  outputs_v2/pipeline/step8/labeled_workflows_l3_v5.json
  outputs_v2/l3_vocab_v2.json      (code -> int id, int id -> code)

Behavior:
  For every workflow we walk (operator_i, l3_code_i, conf_i, ambig_i) in step,
  look up merge_plan[l3_code_i]:
    - 'delete' -> drop this step (ops/codes/conf/amb all dropped in lockstep)
    - 'merge'  -> rewrite code to new_l3
    - 'keep'   -> unchanged
  Then rebuild l3_sequence (int ids) using v2 vocab.
  Workflows whose final operator list is below MIN_SEQ_LEN (=3) are dropped.

Validation:
  - Token total after transform should equal old_total - deleted_freq
  - Active-L3 rate should be high (>=80%)
  - Special tokens (<START>/<END>) preserved at both ends
"""
from __future__ import annotations
import csv
import json
import sys
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parents[1]
OLD_WORKFLOWS = ROOT / "outputs" / "pipeline" / "step8" / "labeled_workflows_l3_v4_cleaned.json"
MERGE_PLAN_CSV = ROOT / "outputs_v2" / "l3_merge_plan.csv"
HIER_V2_CSV = ROOT / "outputs_v2" / "classification_hierarchy_v2.csv"

OUT_WORKFLOWS = ROOT / "outputs_v2" / "pipeline" / "step8" / "labeled_workflows_l3_v5.json"
OUT_VOCAB = ROOT / "outputs_v2" / "l3_vocab_v2.json"
OUT_WORKFLOWS.parent.mkdir(parents=True, exist_ok=True)

MIN_SEQ_LEN = 3  # drop workflows whose post-merge op list is shorter than this

# Special token IDs (keep same as current config/transformer_config.py)
SPECIAL_TOKENS = {"<PAD>": -1, "<UNK>": -2, "<START>": -3, "<END>": -4}


def load_merge_map() -> dict[str, tuple[str, str]]:
    """
    Returns dict: old_l3 -> (action, new_l3).
      action in {'keep','merge','delete'}
      new_l3 is '' for delete.
    """
    m: dict[str, tuple[str, str]] = {}
    with MERGE_PLAN_CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            m[r["old_l3"]] = (r["action"], r["new_l3"])
    return m


def load_v2_vocab() -> tuple[dict[str, int], list[str]]:
    """Build v2 L3 vocab: code -> id, id -> code. IDs start at 0 and are stable
    under sorted(v2 L3 codes)."""
    codes: list[str] = []
    with HIER_V2_CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            codes.append(r["l3_code"])
    codes.sort()  # deterministic
    code_to_id = {c: i for i, c in enumerate(codes)}
    return code_to_id, codes


def transform_workflow(
    wf: dict,
    merge_map: dict[str, tuple[str, str]],
    code_to_id: dict[str, int],
    stats: dict,
) -> dict | None:
    """Returns rewritten wf, or None if it should be dropped.

    Code-centric: we transform l3_codes (the training target) via the merge
    plan. operator_sequence is NOT realigned — it's kept for downstream L3→
    QGIS mapping diagnostics only and the upstream data already has cases
    where body != ops length (step4/5 cycle/auxiliary cleaning drops ops
    without dropping codes, or vice versa). Training only consumes
    l3_sequence, so only codes alignment matters.

    confidences/ambiguity are trimmed/padded to the new body length to keep
    downstream readers happy.
    """
    codes = wf.get("l3_codes", [])
    confs = wf.get("confidences", [])
    ambs = wf.get("ambiguity_flags", [])

    if not codes or codes[0] != "<START>" or codes[-1] != "<END>":
        stats["malformed_special_tokens"] += 1
        return None
    body = codes[1:-1]

    new_body_codes: list[str] = []
    new_confs: list[float] = []
    new_ambs: list[bool] = []

    for i, code in enumerate(body):
        action, new_code = merge_map.get(code, ("keep", code))
        if action == "delete":
            stats["step_deleted"] += 1
            continue
        stats["step_merged" if action == "merge" else "step_kept"] += 1
        new_body_codes.append(new_code)
        # Conf/amb align best-effort with body position
        new_confs.append(float(confs[i]) if i < len(confs) else 1.0)
        new_ambs.append(bool(ambs[i]) if i < len(ambs) else False)

    if len(new_body_codes) < MIN_SEQ_LEN:
        stats["workflow_dropped_too_short"] += 1
        return None

    new_codes = ["<START>"] + new_body_codes + ["<END>"]
    new_seq = [SPECIAL_TOKENS["<START>"]] \
        + [code_to_id[c] for c in new_body_codes] \
        + [SPECIAL_TOKENS["<END>"]]

    md = dict(wf.get("metadata", {}))
    md["post_v2_num_operators"] = len(new_body_codes)
    md["v2_merge_applied"] = True

    return {
        "l3_sequence": new_seq,
        "l3_codes": new_codes,
        "operator_sequence": wf.get("operator_sequence", []),
        "confidences": new_confs,
        "ambiguity_flags": new_ambs,
        "metadata": md,
        "task_metadata": wf.get("task_metadata", {}),
    }


def main():
    print("Loading merge plan + vocab + workflows ...")
    merge_map = load_merge_map()
    code_to_id, codes = load_v2_vocab()
    print(f"  merge_map entries: {len(merge_map)}  v2 vocab size: {len(codes)}")

    with OLD_WORKFLOWS.open(encoding="utf-8") as f:
        old_data = json.load(f)
    old_wfs = old_data["labeled_workflows"]
    print(f"  old workflows: {len(old_wfs):,}")

    # Old freq sanity
    old_freq = Counter()
    for wf in old_wfs:
        for c in wf.get("l3_codes", []):
            if isinstance(c, str) and c.startswith("L3_"):
                old_freq[c] += 1
    old_total = sum(old_freq.values())
    print(f"  old L3 tokens: {old_total:,}")

    stats = defaultdict(int)
    new_wfs = []
    for wf in old_wfs:
        nw = transform_workflow(wf, merge_map, code_to_id, stats)
        if nw is not None:
            new_wfs.append(nw)

    # New freq
    new_freq = Counter()
    for wf in new_wfs:
        for c in wf["l3_codes"]:
            if c.startswith("L3_"):
                new_freq[c] += 1
    new_total = sum(new_freq.values())

    # Compose stats for statistics section
    out_data = {
        "num_workflows": len(new_wfs),
        "labeled_workflows": new_wfs,
        "statistics": {
            "source": str(OLD_WORKFLOWS),
            "merge_plan": str(MERGE_PLAN_CSV),
            "v2_vocab_size": len(codes),
            "old_workflows": len(old_wfs),
            "new_workflows": len(new_wfs),
            "workflow_drop_rate": round(1 - len(new_wfs) / len(old_wfs), 4),
            "old_token_count": old_total,
            "new_token_count": new_total,
            "tokens_deleted": old_total - new_total,
            "step_stats": dict(stats),
            "top20_new_freq": new_freq.most_common(20),
            "active_v2_l3": len(new_freq),
            "active_rate": round(len(new_freq) / len(codes), 4),
        },
    }

    print("\nWriting output ...")
    with OUT_WORKFLOWS.open("w", encoding="utf-8") as f:
        json.dump(out_data, f, ensure_ascii=False)
    with OUT_VOCAB.open("w", encoding="utf-8") as f:
        json.dump({
            "special_tokens": SPECIAL_TOKENS,
            "code_to_id": code_to_id,
            "id_to_code": codes,
            "vocab_size": len(codes),
            "total_vocab_size": len(codes) + len(SPECIAL_TOKENS),
        }, f, ensure_ascii=False, indent=2)

    # Report
    print("\n=== D2 Apply Merge — Summary ===")
    print(f"  old workflows: {len(old_wfs):,}  -> new: {len(new_wfs):,}  "
          f"(drop {len(old_wfs)-len(new_wfs):,} = "
          f"{(1-len(new_wfs)/len(old_wfs))*100:.2f}%)")
    print(f"  old tokens   : {old_total:,}  -> new: {new_total:,}  "
          f"(drop {old_total-new_total:,} = "
          f"{(1-new_total/old_total)*100:.2f}%)")
    print(f"  v2 vocab     : {len(codes)}  active: {len(new_freq)}  "
          f"({len(new_freq)/len(codes)*100:.1f}%)")
    print("\n  Step-level stats:")
    for k, v in sorted(stats.items()):
        print(f"    {k}: {v:,}")
    print("\n  Top-20 v2 L3 freq:")
    for c, f in new_freq.most_common(20):
        print(f"    {c:<16} {f:>8,}  ({f/new_total*100:5.2f}%)")

    print(f"\nWrote:\n  {OUT_WORKFLOWS}\n  {OUT_VOCAB}")


if __name__ == "__main__":
    main()
