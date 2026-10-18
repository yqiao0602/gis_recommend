#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S1 component-level stratified sampling list (deterministic, read-only).

Frozen inputs:
  - pool: 04_DIAG_WORK/b1_gee_stage_train.jsonl (SHA 09c37104...)
  - split: B_TRACK_SPLIT_MANIFEST_V2.json (component atomic; row_split/row_component)
  - quotas: B_TRACK_S1_AUDIT_QUOTAS_V1.json (Phase-1)
Rules:
  - sampling unit = task-group component; all rows of a selected component are
    audited together; no component is split to fill a quota.
  - strata = support tier x length band; task-type cap 20% per split applied at
    selection; capacity gaps are recorded, never silently backfilled from other
    strata.
  - risk flags are computed per selected component from its representative
    script (UI calls, duplicate lines, indirect asset references, empty RLE,
    known Q1/Q2 from the audited overlay).

Outputs:
  B_TRACK_S1_SAMPLING_LIST_V1.json
"""
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
POOL = REPO.parent / "04_DIAG_WORK/b1_gee_stage_train.jsonl"
B = (REPO / "docs/reports/route2_p0_contract/plan_pipeline_v1/"
     "planning_capability_audit_v1/diag50_v1/b_track_audit_v1")
SEED = 20261018
Q = B / "B_TRACK_S1_AUDIT_QUOTAS_V1.json"
MAN = B / "B_TRACK_SPLIT_MANIFEST_V2.json"
ADM = B / "Q2_ADMISSION_V1.json"
TREE = [REPO / ".tmp_gee_batch13_sources/Data", REPO / ".tmp_gee_batch8_ast_bridge/sources"]


def main():
    man = json.loads(MAN.read_text(encoding="utf-8"))
    quotas = json.loads(Q.read_text(encoding="utf-8"))["quotas_by_split_stratum"]
    adm = json.loads(ADM.read_text(encoding="utf-8"))
    q_bucket = {}
    for r in adm["records"]:
        for s in (r["script_a"], r["script_b"]):
            q_bucket.setdefault(s, set()).add(r["admission_bucket"])
    rows = []
    with POOL.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            r = json.loads(line)
            rle = r.get("semantic_chain_rle", "")
            rows.append({"idx": i, "instr": r.get("instruction", ""),
                         "rle": rle, "script": r.get("script", ""),
                         "task_type": r.get("task_type", ""),
                         "steps": len([x for x in re.split(r"\s*->\s*", rle) if x])})
    rs = man["row_split"]
    rc = man["row_component"]
    assert len(rs) == len(rows)
    # template support
    sup = Counter(r["rle"] for r in rows)
    comp = defaultdict(lambda: {"rows": [], "tmpl": Counter(), "tt": Counter(),
                                "steps": [], "split": set()})
    for i, r in enumerate(rows):
        c = rc[i]
        d = comp[c]
        d["rows"].append(i)
        d["tmpl"][r["rle"]] += 1
        d["tt"][r["task_type"]] += 1
        d["steps"].append(r["steps"])
        d["split"].add(rs[i])
    index = {}
    for tree in TREE:
        if tree.exists():
            for d in sorted(tree.iterdir()):
                if d.is_dir():
                    for f in d.glob("script_*.txt"):
                        index.setdefault(f.name[:-4], f)

    def tier(c):
        t = comp[c]["tmpl"].most_common(1)[0][0]
        s = sup[t]
        return "high" if s > 100 else ("mid" if s > 10 else ("low" if s > 1 else "singleton"))

    def band(c):
        st = sorted(comp[c]["steps"])
        m = st[len(st) // 2]
        return "short" if m <= 5 else ("medium" if m <= 20 else "long")

    def split(c):
        return next(iter(comp[c]["split"]))

    def mode_tt(c):
        return comp[c]["tt"].most_common(1)[0][0]

    def risk_flags(c):
        rep = rows[comp[c]["rows"][0]]
        flags = []
        if not rep["rle"]:
            flags.append("empty_rle")
        p = index.get(rep["script"])
        if p:
            src = p.read_text(encoding="utf-8", errors="replace")
            if re.search(r"\bui\.|Map\.(addLayer|setCenter|centerObject|add|setOptions)", src):
                flags.append("ui_scaffold")
            lines = [re.sub(r"\s+", "", l.split("//")[0]) for l in src.splitlines()]
            lines = [l for l in lines if len(l) >= 8]
            if any(v > 1 for v in Counter(lines).values()):
                flags.append("duplicate_lines")
            if re.search(r"ee\.(?:ImageCollection|Image|FeatureCollection)\(\s*(?:[A-Za-z_$]|['\"][^'\"]*['\"]\s*\+)", src):
                flags.append("indirect_asset")
        if q_bucket.get(rep["script"], set()) & {"Q1_misdescribed"}:
            flags.append("known_Q1")
        if q_bucket.get(rep["script"], set()) & {"Q2_insufficient"}:
            flags.append("known_Q2")
        return flags

    meta = {}
    for c in comp:
        meta[c] = {"split": split(c), "tier": tier(c), "band": band(c),
                   "task_type": mode_tt(c), "n_rows": len(comp[c]["rows"]),
                   "flags": risk_flags(c)}
    rng = random.Random(SEED)
    selected, gaps = [], []
    for sp in ("t", "v", "s"):
        q = quotas[sp]
        cap = Counter()
        for c, m in meta.items():
            if m["split"] == sp:
                cap[f'{m["tier"]}|{m["band"]}'] += 1
        tt_count = Counter()
        split_total = sum(q.values())
        tt_cap = max(1, round(split_total * 0.20))
        for key in sorted(q):
            want = q[key]
            tier_, band_ = key.split("|")
            pool_c = [c for c, m in meta.items()
                      if m["split"] == sp and m["tier"] == tier_ and m["band"] == band_]
            rng.shuffle(pool_c)
            taken = 0
            for c in pool_c:
                if taken >= want:
                    break
                tt = meta[c]["task_type"]
                if tt_count[tt] >= tt_cap:
                    continue
                selected.append({"component_id": c, **meta[c], "quota": want,
                                 "order": len(selected) + 1})
                tt_count[tt] += 1
                taken += 1
            if taken < want:
                gaps.append({"split": sp, "stratum": key, "quota": want,
                             "capacity": len(pool_c), "selected": taken,
                             "gap": want - taken})
    # hashes
    pool_sha = hashlib.sha256(POOL.read_bytes()).hexdigest()
    list_sha = hashlib.sha256(json.dumps(selected, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    out = {"artifact": "B_TRACK_S1_SAMPLING_LIST_V1", "date": "2026-10-18",
           "seed": SEED, "pool_sha256": pool_sha, "split_manifest": str(MAN.name),
           "quotas": str(Q.name), "n_selected": len(selected),
           "list_sha256": list_sha,
           "rule": "component-level stratified sampling; no component split; capacity gaps recorded",
           "gaps": gaps, "components": selected}
    (B / "B_TRACK_S1_SAMPLING_LIST_V1.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("selected", len(selected), "gaps", len(gaps), "list_sha", list_sha[:16])
    print("by split", Counter(x["split"] for x in selected))
    print("by tier", Counter(x["tier"] for x in selected))
    print("by band", Counter(x["band"] for x in selected))
    print("flagged", Counter(f for x in selected for f in x["flags"]))


if __name__ == "__main__":
    main()
