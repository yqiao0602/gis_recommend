#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Full-corpus task-group split V2 (deterministic, read-only over the frozen pool).

Rules (frozen):
  - task-group unit = connected component over
      (a) near-duplicate instructions (rare-token Jaccard >= 0.75, >=3 shared
          rare tokens, rare df <= 60 — identical to the Q2 pair finder),
      (b) rows sharing the same script id.
  - components are atomic; split assigned at component level with seed 20261018,
    80/10/10.
  - no admission decision is made here: split membership != training
    eligibility. Admission stays governed by the frozen relation/admission
    baseline and the Q2 admission buckets.

Outputs (b_track_audit_v1/):
  B_TRACK_SPLIT_MANIFEST_V2.json
  B_TRACK_FULL_CORPUS_INVENTORY_V1.json
"""
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
POOL = REPO.parent / "04_DIAG_WORK/b1_gee_stage_train.jsonl"
B = (REPO / "docs/reports/route2_p0_contract/plan_pipeline_v1/"
     "planning_capability_audit_v1/diag50_v1/b_track_audit_v1")
ADM = B / "Q2_ADMISSION_V1.json"
SEED = 20261018
TOK = re.compile(r"[a-z0-9]+")


def norm(s):
    return re.sub(r"\s+", " ", s.strip().lower())


def toks(s):
    return set(TOK.findall(s))


def main():
    rows = []
    with POOL.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            r = json.loads(line)
            rows.append({"idx": i, "instr": norm(r.get("instruction", "")),
                         "script": r.get("script", ""), "split": r.get("split", "")})
    ids, groups = {}, defaultdict(list)
    for r in rows:
        ni = r["instr"]
        if ni not in ids:
            ids[ni] = len(ids)
        groups[ni].append(r["idx"])
    NID = len(ids)
    tok_sets = {ni: toks(ni) for ni in groups}
    id2tok = {ids[ni]: ts for ni, ts in tok_sets.items()}
    df = Counter()
    for ts in tok_sets.values():
        df.update(ts)
    rare = {t for t, c in df.items() if c <= 60}
    inv = defaultdict(list)
    for ni, ts in tok_sets.items():
        nid = ids[ni]
        for t in ts & rare:
            inv[t].append(nid)
    parent = list(range(NID))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    pairs = 0
    seen = set()
    for t, docs in inv.items():
        docs.sort()
        for ai in range(len(docs)):
            a = docs[ai]
            for bi in range(ai + 1, len(docs)):
                b = docs[bi]
                packed = a * NID + b
                if packed in seen:
                    continue
                seen.add(packed)
                sa, sb = id2tok[a], id2tok[b]
                inter = sa & sb
                if len(inter) < 3:
                    continue
                if len(inter) / len(sa | sb) >= 0.75:
                    pairs += 1
                    union(a, b)
    script_first = {}
    for r in rows:
        s = r["script"]
        nid = ids[r["instr"]]
        if s:
            if s in script_first:
                union(script_first[s], nid)
            else:
                script_first[s] = nid
    comp_rows = defaultdict(list)
    for r in rows:
        comp_rows[find(ids[r["instr"]])].append(r["idx"])
    comps = list(comp_rows.items())
    rng = random.Random(SEED)
    rng.shuffle(comps)
    n = len(comps)
    ntr = round(n * 0.8)
    nv = round(n * 0.1)
    assign = {}
    for i, (c, idxs) in enumerate(comps):
        assign[c] = "train" if i < ntr else ("val" if i < ntr + nv else "test")
    row_split = ["?"] * len(rows)
    row_comp = [0] * len(rows)
    for c, idxs in comps:
        for i in idxs:
            row_split[i] = {"train": "t", "val": "v", "test": "s"}[assign[c]]
            row_comp[i] = c
    # audited overlay
    adm = json.loads(ADM.read_text(encoding="utf-8"))
    rank = {"A_high_confidence": 0, "C1_conditional_literal": 1,
            "M_multiref_candidate": 2, "C2_conditional_underdesc": 3,
            "Q1_misdescribed": 4, "Q2_insufficient": 5}
    scripts = {}
    for r in adm["records"]:
        for s in (r["script_a"], r["script_b"]):
            b = r["admission_bucket"]
            if s not in scripts or rank[b] > rank[scripts[s]]:
                scripts[s] = b
    audited_rows = [i for i, r in enumerate(rows) if r["script"] in scripts]
    aud_split = Counter(row_split[i] for i in audited_rows)
    elig = {s for s, b in scripts.items()
            if b in ("A_high_confidence", "C1_conditional_literal", "M_multiref_candidate")}
    elig_rows = [i for i, r in enumerate(rows) if r["script"] in elig]
    elig_split = Counter(row_split[i] for i in elig_rows)
    inv_out = {
        "artifact": "B_TRACK_FULL_CORPUS_INVENTORY_V1", "date": "2026-10-18",
        "pool_rows": len(rows), "unique_instructions": NID,
        "near_dup_pairs": pairs, "components": len(comp_rows),
        "component_size_top": Counter(len(v) for v in comp_rows.values()).most_common(10),
        "audited_unique_scripts": len(scripts), "audited_rows": len(audited_rows),
        "audited_by_split_v2": dict(aud_split),
        "eligible_scripts_A_C1_M": len(elig),
        "eligible_rows_by_split_v2": dict(elig_split),
        "bucket_counts": dict(Counter(scripts.values())),
        "seed": SEED,
    }
    man = {
        "artifact": "B_TRACK_SPLIT_MANIFEST_V2", "version": "V2", "date": "2026-10-18",
        "seed": SEED, "pool_rows": len(rows), "components": len(comp_rows),
        "split_components": dict(Counter(assign.values())),
        "split_rows": dict(Counter(row_split)),
        "audited_overlay": {"rows": dict(aud_split), "eligible_A_C1_M": dict(elig_split)},
        "rule": "component-level 80/10/10; component = near-dup instruction cluster + shared script id; "
                "split membership != training admission",
        "row_split": "".join(row_split),
        "row_component": row_comp,
        "note": "row_split is a per-line string (t/v/s) aligned to the frozen pool; "
                "row_component is the component root id per line. Regenerate with "
                "scripts/b_track_full_corpus_split_v1.py.",
    }
    (B / "B_TRACK_FULL_CORPUS_INVENTORY_V1.json").write_text(
        json.dumps(inv_out, ensure_ascii=False, indent=1), encoding="utf-8")
    (B / "B_TRACK_SPLIT_MANIFEST_V2.json").write_text(
        json.dumps(man, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(inv_out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
