#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1 (owner directive 2026-10-12): order-preserving alignment repair for the
788 alignment_mismatch C6 stages.

Root cause (diagnosed on sid 30470): the upstream semantic chain is a
FILTERED SUBSEQUENCE of the canonical chain — calls the upstream extractor
classes as AUX/presentation (ee.String, ee.Image.paint, ...) are dropped.
Local classify() (gee_route2_semantic_workflow_v1) reproduces the mapping
well enough to align: greedy/DP order-preserving match of sem tokens against
[classify(c) for c in canonical].

Per row outputs:
  alignment ratio (matched sem / total sem), unmatched sem tokens (upstream/
  local class disagreement candidates), skipped canonical tokens with local
  class, chain hashes (stable evidence keys).

C6 is then re-run for ALL repeat>1 stages using aligned canonical spans.
Previously classified stages serve as REGRESSION: class must not change
unless itemized with alignment evidence.

Read-only; no gold is modified.
"""

import hashlib
import json
import os
import sys
import importlib.util
import itertools
from collections import Counter, defaultdict
from difflib import SequenceMatcher

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
DW = os.path.join(REPO, "..", "04_DIAG_WORK")
DEV = os.path.join(DW, "planner_v2_dev.jsonl")
GOLD3 = os.path.join(DW, "blueprint_v2_gold_v3.jsonl")
SRC = os.path.join(DW, "b1_gee_stage_train.jsonl")
PD = os.path.join(REPO, "docs", "reports", "route2_p0_contract",
                  "plan_pipeline_v1", "planner_design")
OUT = os.path.join(PD, "ALIGNMENT_C6_V2_DEV.json")
OLD_C6 = os.path.join(PD, "CANONICAL_AGREEMENT_C6_DEV_V1.json")


def load_classify():
    spec = importlib.util.spec_from_file_location(
        "gsw", os.path.join(REPO, "scripts", "gee_route2_semantic_workflow_v1.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gsw"] = mod
    spec.loader.exec_module(mod)
    return mod.classify


def main():
    classify = load_classify()
    old = json.load(open(OLD_C6, encoding="utf-8"))
    old_class = {}   # (dev_idx, seq) -> old C6 class
    for r in old["row_detail"]:
        for f in r["flags"]:
            if f["check"].startswith("C6_"):
                old_class[(r["dev_idx"], f["seq"])] = f["check"][3:]

    dev = []
    with open(DEV, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                t = r.get("target")
                if isinstance(t, str):
                    t = json.loads(t)
                dev.append({"task": r.get("task") or "", "tgt": t})

    task2sid = {}
    with open(GOLD3, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            task2sid.setdefault(r.get("task"), r.get("source_row_id"))

    need = set()
    for r in dev:
        t = r["tgt"]
        if isinstance(t, dict) and any(int(s.get("repeat", 1)) > 1
                                       for s in t.get("stages", [])):
            sid = task2sid.get(r["task"])
            if sid:
                need.add(sid)

    chains = {}
    with open(SRC, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if i in need:
                r = json.loads(line)
                sem = [x.strip() for x in
                       (r.get("semantic_chain_raw") or "").split("->")
                       if x.strip()]
                can = [x.strip() for x in
                       (r.get("gee_canonical_chain") or "").split("->")
                       if x.strip()]
                chains[i] = (sem, can)
            if len(chains) == len(need):
                break

    new_class_total = Counter()
    regression = Counter()
    changed_examples = []
    row_stats = []
    mismatch_rows_fixed = 0

    for idx, r in enumerate(dev):
        t = r["tgt"]
        if not isinstance(t, dict) or "stages" not in t:
            continue
        stages = t["stages"]
        rep_stages = [s for s in stages if int(s.get("repeat", 1)) > 1]
        if not rep_stages:
            continue
        sid = task2sid.get(r["task"])
        sem, can = chains.get(sid, (None, None))
        rec = {"dev_idx": idx, "sid": sid}
        if sem is None:
            rec["status"] = "no_chain_join"
            row_stats.append(rec)
            continue
        can_cls = [classify(c) for c in can]
        h_sem = hashlib.sha256(
            "->".join(sem).encode("utf-8")).hexdigest()[:12]
        sm = SequenceMatcher(None, can_cls, sem, autojunk=False)
        blocks = sm.get_matching_blocks()  # (can_i, sem_i, size)
        sem2can = {}
        for bi in range(len(blocks) - 1):
            ci, si, size = blocks[bi]
            for k in range(size):
                sem2can[si + k] = ci + k
        matched = len(sem2can)
        unmatched_sem = [i for i in range(len(sem)) if i not in sem2can]
        rec.update({
            "sem_len": len(sem), "can_len": len(can),
            "sem_chain_hash": h_sem,
            "matched": matched,
            "align_ratio": round(matched / max(1, len(sem)), 4),
            "unmatched_sem": [{"pos": i, "family": sem[i],
                               "nearby_can": can[sem2can[i - 1] + 1]
                               if (i - 1) in sem2can and
                               sem2can[i - 1] + 1 < len(can) else None}
                              for i in unmatched_sem[:5]],
            "skipped_can_n": len(can) - matched,
            "skipped_can": [{"can_idx": ci, "token": can[ci][:50],
                             "local_class": can_cls[ci]}
                            for ci in range(len(can)) if ci not in
                            set(sem2can.values())][:5],
        })
        had_mismatch = any(
            old_class.get((idx, s["seq"])) == "alignment_mismatch"
            for s in rep_stages)
        if had_mismatch and matched == len(sem):
            mismatch_rows_fixed += 1

        # re-run C6 with aligned spans
        for s in rep_stages:
            fam, rep = s["family"], int(s["repeat", 1]) if False else int(s.get("repeat", 1))
            # find matching sem run (same family+count, else same family)
            runs = []
            p = 0
            for fam_, g in itertools.groupby(sem):
                c_ = len(list(g))
                runs.append((fam_, c_, p))
                p += c_
            m = next((x for x in runs if x[0] == fam and x[1] == rep),
                     next((x for x in runs if x[0] == fam), None))
            key = (idx, s["seq"])
            if m is None:
                cls = "run_not_found"
            else:
                span = range(m[2], m[2] + m[1])
                can_pos = [sem2can[i] for i in span if i in sem2can]
                if len(can_pos) < m[1]:
                    cls = "alignment_partial"
                else:
                    seg = [can[p_] for p_ in can_pos]
                    u = set(seg)
                    if len(u) == 1:
                        cls = "all_identical"
                    elif len(u) == len(seg):
                        cls = "all_distinct"
                    else:
                        cls = "mixed"
            new_class_total[cls] += 1
            ocls = old_class.get(key)
            if ocls is None:
                regression["new_stage_not_in_old"] += 1
            elif ocls == cls:
                regression["unchanged"] += 1
            else:
                regression[f"changed:{ocls}->{cls}"] += 1
                if len(changed_examples) < 30:
                    changed_examples.append({
                        "dev_idx": idx, "seq": s["seq"], "family": fam,
                        "repeat": rep, "old": ocls, "new": cls,
                        "align_ratio": rec["align_ratio"]})
        row_stats.append(rec)

    out = {
        "schema": "alignment_c6_v2_dev",
        "method": ("order-preserving SequenceMatcher alignment of semantic "
                   "chain vs [classify(c) for c in canonical chain]; "
                   "skipped canonical = upstream AUX/presentation drops; "
                   "unmatched sem = upstream/local class disagreement "
                   "candidates; C6 re-run on aligned spans."),
        "root_cause_diagnosis": ("semantic chain = filtered subsequence of "
                                 "canonical chain (AUX/presentation calls "
                                 "dropped upstream, e.g. ee.String, "
                                 "ee.Image.paint -> AUX_VALUE locally)"),
        "rows": len(row_stats),
        "full_align_rows": sum(1 for x in row_stats
                               if x.get("matched") == x.get("sem_len")),
        "mismatch_rows_fully_recovered": mismatch_rows_fixed,
        "new_class_totals": dict(new_class_total),
        "regression_vs_c6_v1": dict(regression),
        "changed_examples": changed_examples,
        "row_stats": row_stats,
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=2,
              ensure_ascii=False)
    print(json.dumps({k: out[k] for k in
                      ("rows", "full_align_rows",
                       "mismatch_rows_fully_recovered",
                       "new_class_totals", "regression_vs_c6_v1")},
                     indent=2))
    print("saved:", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
