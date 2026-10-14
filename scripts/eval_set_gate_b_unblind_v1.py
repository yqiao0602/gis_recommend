#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Eval-set Gate B: freeze owner matrix, verify the 27 empty candidates,
unblind vs r5 v0.5.1 (B and Ø in SEPARATE buckets, never merged into O/C),
and run the pre-registered S0-S3 comparison.

Owner labels are compact strings per candidate in the packet's required-slot
order (e.g. "O-C-B"). Slots:
  O omission / C covered / B representation boundary / U requirement
  uncertain / N non-required / Ø EMPTY candidate (unjudgeable, excluded).
"""
import itertools
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from r5_requirement_parser_v0 import evaluate_pair  # noqa: E402
from r5_requirement_parser_v0 import parse_task  # noqa: E402

RL = REPO / "docs/reports/route2_p0_contract/plan_pipeline_v1/rl_line"
EP = RL / "eval_procurement"

# ---- owner matrix (round-14 blind labeling; slot order = packet order) ----
MATRIX = {
    "script_154762": (["TEMPORAL", "COMPOSITE", "TERRAIN"],
                      ["O-C-B", "C-O-B", "O-C-B", "O-C-B", "O-O-B",
                       "O-C-B", "C-C-B", "O-C-B"]),
    "script_160457": (["STATS"], ["C"] * 8),
    "script_177161": (["TEMPORAL", "MASK", "SPATIAL", "COMPOSITE", "CLASSIFY"],
                      ["O-O-O-O-C", "O-O-O-O-C", "O-O-O-C-C", "O-O-O-C-O",
                       "O-O-C-O-C", "O-O-O-O-O", "O-O-O-O-C", "O-O-O-C-C"]),
    "script_182431": (["TEMPORAL", "SPATIAL"],
                      ["O-C", "C-O", "C-O", "C-O", "C-C", "C-O", "C-O", "C-O"]),
    "script_187051": (["TEMPORAL", "SPATIAL", "COMPOSITE"],
                      ["C-C-C", "C-O-C", "C-C-O", "C-C-O", "C-O-C", "C-C-C",
                       "C-C-O", "C-O-O"]),
    "script_192304": (["TEMPORAL", "MASK", "COMPOSITE", "TERRAIN"],
                      ["C-O-C-B", "C-O-O-B", "O-O-C-B", "O-O-C-B", "C-O-C-B",
                       "O-O-C-B", "C-O-C-B", "C-O-C-B"]),
    "script_201566": (["TEMPORAL", "MASK", "CLASSIFY", "TERRAIN"],
                      ["EMPTY", "C-O-O-B", "C-O-O-B", "C-O-O-B", "C-O-O-B",
                       "C-O-O-B", "C-O-O-B", "C-O-O-B"]),
    "script_202426": (["MASK"],
                      ["O", "O", "O", "O", "O", "O", "EMPTY", "O"]),
    "script_211527": (["TEMPORAL"],
                      ["O", "O", "C", "O", "O", "O", "C", "C"]),
    "script_231195": (["TEMPORAL", "SPATIAL", "STATS"],
                      ["C-O-C", "O-O-O", "C-O-C", "C-O-C", "C-O-C", "O-O-C",
                       "C-C-O", "C-O-C"]),
    "script_241490": (["TEMPORAL", "SPATIAL"],
                      ["C-O", "C-C", "O-O", "C-C", "C-O", "O-O", "O-O", "C-O"]),
    "script_291385": (["INDEX", "COMPOSITE"],
                      ["O-C", "O-C", "O-C", "O-C", "O-C", "O-O", "O-O", "O-C"]),
    "script_31001": (["TEMPORAL", "STATS"],
                     ["C-C", "C-C", "C-C", "O-O", "O-C", "C-C", "O-C", "O-C"]),
    "script_32052": (["TEMPORAL"],
                     ["C", "C", "C", "C", "C", "EMPTY", "C", "C"]),
    "script_407954": (["TEMPORAL"], ["EMPTY"] * 8),
    "script_408172": (["MASK", "INDEX"],
                      ["O-O", "O-O", "O-O", "C-O", "O-O", "O-O", "O-O", "O-O"]),
    "script_411264": (["TEMPORAL", "MASK", "INDEX", "SPATIAL", "CLASSIFY"],
                      ["EMPTY"] * 8),
    "script_411270": (["TEMPORAL"], ["EMPTY"] * 8),
    "script_61437": (["TEMPORAL"],
                     ["C", "C", "O", "C", "O", "C", "C", "C"]),
    "script_74076": (["TEMPORAL", "MASK", "STATS"],
                     ["C-O-O", "O-O-C", "C-O-C", "O-O-O", "O-O-C", "C-O-O",
                      "O-C-O", "C-O-C"]),
    "script_150328": ([], None),
    "script_158835": ([], None),
    "script_19546": ([], None),
    "script_235273": ([], None),
}


def load_stages(text):
    try:
        b = json.loads(text)
    except Exception:
        return None
    if isinstance(b, dict) and isinstance(b.get("stages"), list):
        return b
    return None


def main():
    preds = json.loads((EP / "preds.json").read_text(encoding="utf-8"))
    tasks = {json.loads(l)["script"]: json.loads(l)
             for l in (EP / "eval_set_24_tasks.jsonl").read_text(encoding="utf-8").splitlines()}
    vocab_obj = json.loads((RL / "vocab23_server_verified.json").read_text(encoding="utf-8"))
    vocab = vocab_obj["families"] if isinstance(vocab_obj, dict) else vocab_obj

    by_group = defaultdict(list)
    for p in preds:
        by_group[p["k"]].append(p)

    # ---- step 2: empty-candidate verification ----
    empty_owner, empty_r5 = set(), set()
    slot_order_mismatch = []
    for k, (slots, _) in MATRIX.items():
        if not slots:
            continue
        pr = parse_task(tasks[k]["task"])
        parsed_required = [s["id"] for s in pr["slots"] if s["state"] == "required"]
        if parsed_required != slots:
            slot_order_mismatch.append({"k": k, "packet": slots,
                                        "fresh_parse": parsed_required})
        for cand, compact in enumerate(MATRIX[k][1]):
            if compact == "EMPTY":
                empty_owner.add((k, cand))
    for k, grp in by_group.items():
        for p in grp:
            b = load_stages(p["pred_text"])
            if b is None or not b.get("stages"):
                empty_r5.add((p["k"], p["cand"]))
    empty_match = empty_owner == empty_r5
    print(f"empty candidates: owner={len(empty_owner)} r5_unparseable_or_empty="
          f"{len(empty_r5)} exact_id_match={empty_match}")

    # ---- step 3: unblind contingency (B and O-EMPTY separate) ----
    buckets = Counter()
    per_slot_missing = defaultdict(lambda: Counter())
    rows = []
    scorable_cands = []
    for k, (slots, compacts) in MATRIX.items():
        if not slots or compacts is None:
            continue
        pr = parse_task(tasks[k]["task"])
        task = tasks[k]["task"]
        uncertain_slots = [s["id"] for s in pr["slots"]
                           if s["state"] == "requirement_uncertain"]
        for cand, compact in enumerate(compacts):
            if compact == "EMPTY":
                buckets["EMPTY_candidate_excluded"] += 1
                continue
            p = next(x for x in by_group[k] if x["cand"] == cand)
            b = load_stages(p["pred_text"])
            fams = {s.get("family") for s in b.get("stages", [])
                    if isinstance(s, dict)} if b else set()
            parts = compact.split("-")
            for slot_id, owner in zip(slots, parts):
                owner = {"O": "O", "C": "C", "B": "B", "U": "U",
                         "Ø": "EMPTY"}[owner]
                sc = evaluate_pair(task, {"stages": b.get("stages", [])})["score"]
                st = next((x for x in sc["per_slot"] if x["slot"] == slot_id), None)
                if st is None:
                    bucket = "r5_slot_not_required"
                else:
                    cov = st["coverage"]
                    if cov == "missing":
                        if owner == "O":
                            bucket = "TP"
                        elif owner == "C":
                            bucket = "FP_false_punish"
                        elif owner == "B":
                            bucket = "r5missing_vs_Boundary"
                            per_slot_missing[slot_id]["vs_Boundary"] += 1
                        elif owner == "U":
                            bucket = "r5missing_vs_uncertain"
                        elif owner == "N":
                            bucket = "false_requirement"
                        else:
                            bucket = f"missing_vs_{owner}"
                    elif cov in ("covered", "covered_coarse"):
                        if owner == "O":
                            bucket = "FN_false_pass"
                        elif owner == "C":
                            bucket = "TN"
                        elif owner == "B":
                            bucket = "covered_vs_Boundary"
                        elif owner == "U":
                            bucket = "covered_vs_uncertain"
                        else:
                            bucket = f"covered_vs_{owner}"
                    else:
                        bucket = f"unjudgable_{cov}"
                buckets[bucket] += 1
                rows.append({"k": k, "cand": cand, "slot": slot_id,
                             "owner": owner, "r5_coverage": cov,
                             "bucket": bucket})
            # candidate-level record for S0-S3 (scorable = has required slots,
            # non-empty)
            sc = evaluate_pair(task, {"stages": b.get("stages", [])})["score"]
            cov_req = [s for s in sc["per_slot"]]
            cov_owner = []
            for slot_id, owner in zip(slots, parts):
                if owner in ("O", "C"):
                    cov_owner.append(1 if owner == "C" else 0)
            owner_score = (sum(cov_owner) / len(cov_owner)) if cov_owner else None
            fams_all = {s.get("family") for s in b.get("stages", [])
                        if isinstance(s, dict)}
            fams_all = {f for f in fams_all if isinstance(f, str)}
            vocab_set = set(vocab)
            scorable_cands.append({
                "k": k, "cand": cand,
                "struct": None,  # filled by caller via formal reward
                "cov": sc["coverage_ratio"],
                "owner": owner_score,
                "owner_has_O": 0 in cov_owner,
                "empty": False})

    # ---- step 4: S0-S3 (needs formal reward; caller merges) ----
    out = {
        "empty_verification": {
            "owner_empty": len(empty_owner), "r5_side": len(empty_r5),
            "exact_id_match": empty_match,
            "owner_empty_list": sorted([f"{k}/c{c}" for k, c in empty_owner]),
        },
        "slot_order_mismatch": slot_order_mismatch,
        "buckets": dict(buckets),
        "per_slot_missing_vs_boundary": {s: dict(c) for s, c in per_slot_missing.items()},
        "rows": rows,
        "scorable_candidates": scorable_cands,
    }
    (RL / "eval_procurement/eval_set_gate_b_unblind_v1.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(dict(buckets), ensure_ascii=False, indent=2))
    print("slot order mismatches:", len(slot_order_mismatch))
    for m in slot_order_mismatch:
        print(" ", m)


if __name__ == "__main__":
    main()
