#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Join QGIS chains with task descriptions -> complete training samples.

Pairs:
  - extracted chains (qgis_chains_*.jsonl: {source_script, chain, ...})
  - task descriptions (facts_summary*.csv: File Name, Task Type, Task Name, Task Description)
by exact normalized script id (basename, strip .py, lower). Emits complete
samples {script, task_type, task_name, task_description, chain, modality} and
reports join coverage. stdlib only (csv handles multiline quoted descriptions).

Usage:
  python build_complete_qgis_samples.py --chains "outputs_v2/diagnostics/qgis_chains_*.jsonl" \
      --facts "/home/yll/GEE/描述性知识抽取qgis_chain_selected_script/facts_summary1000.csv" \
      --out outputs_v2/diagnostics/qgis_complete_samples.jsonl
"""
from __future__ import annotations

import argparse
import csv
import glob as globmod
import json
import os
import re
import sys
from collections import Counter

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
_PREFIX = re.compile(r"^processing\.run:")
_RASTER_NAME = ("raster", "rasterize", "warp", "dem", "slope", "aspect", "hillshade", "contour")


def norm_id(s):
    s = os.path.basename((s or "").strip())
    if s.endswith(".py"):
        s = s[:-3]
    return s.lower()


def clean_chain(ch):
    ch = [_PREFIX.sub("", x) for x in ch]
    out = []
    for x in ch:
        if not out or out[-1] != x:
            out.append(x)
    n = len(out)
    for p in range(1, n // 2 + 1):
        if n % p == 0 and all(out[i] == out[i % p] for i in range(n)):
            return out[:p]
    return out


def modality(ch):
    v = r = 0
    for o in ch:
        lo = o.lower()
        if o.startswith(("gdal:", "saga:")) or any(h in lo for h in _RASTER_NAME):
            r += 1
        elif o.startswith(("native:", "qgis:")):
            v += 1
    return "mixed" if v and r else ("raster" if r > v else ("vector" if v else "unknown"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chains", required=True, help="glob of qgis_chains_*.jsonl")
    ap.add_argument("--facts", required=True, help="glob of facts_summary*.csv")
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-len", type=int, default=2)
    args = ap.parse_args()

    # 1. chains by normalized id (prefer longer cleaned chain on dup)
    chains = {}
    for fp in globmod.glob(args.chains):
        for line in open(fp, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            cid = norm_id(r.get("source_script", ""))
            ch = clean_chain(r.get("chain", []))
            if len(ch) < args.min_len:
                continue
            if cid not in chains or len(ch) > len(chains[cid]):
                chains[cid] = ch
    print(f"chains: {len(chains)} unique script ids")

    # 2. descriptions by normalized id
    facts = {}
    for fp in globmod.glob(args.facts):
        with open(fp, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                fid = norm_id(row.get("File Name", ""))
                if not fid:
                    continue
                desc = (row.get("Task Description") or "").strip()
                if fid not in facts or len(desc) > len(facts[fid].get("task_description", "")):
                    facts[fid] = {
                        "task_type": (row.get("Task Type") or "").strip(),
                        "task_name": (row.get("Task Name") or "").strip(),
                        "task_description": desc,
                    }
    print(f"facts: {len(facts)} unique script ids")

    # 3. join
    joined = []
    modc = Counter()
    for cid, ch in chains.items():
        if cid in facts and facts[cid]["task_description"]:
            m = modality(ch)
            modc[m] += 1
            joined.append({"script": cid, **facts[cid], "chain": ch, "modality": m, "n": len(ch)})

    with open(args.out, "w", encoding="utf-8") as f:
        for s in joined:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    print(f"JOINED complete samples (chain+description): {len(joined)}")
    print(f"modality: {dict(modc)}  vector-relevant={modc['vector']+modc['mixed']}")
    print(f"out -> {args.out}")
    if joined:
        ex = joined[0]
        print(f"\nexample: [{ex['task_type']}] {ex['task_name']}")
        print(f"  desc: {ex['task_description'][:150]}")
        print(f"  chain: {' -> '.join(ex['chain'])}")


if __name__ == "__main__":
    main()
