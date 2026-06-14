#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Consolidate + clean + dedup extracted QGIS chains; count by modality.

Reads all qgis_chains_*.jsonl produced by extract_qgis_chains_from_steps.py,
applies light cleaning (strip 'processing.run:' prefix, collapse consecutive
duplicates, collapse a whole-chain period repeat A.A.A -> A), dedups by chain,
and reports unique counts by coarse modality. Quantifies the deduped usable
QGIS chain reservoir. stdlib only.

Usage:
    python consolidate_qgis_chains.py --glob "outputs_v2/diagnostics/qgis_chains_*.jsonl" [--out merged.jsonl]
"""
from __future__ import annotations

import argparse
import glob as globmod
import json
import re
import statistics
from collections import Counter

_RASTER_NAME = ("raster", "rasterize", "warp", "dem", "slope", "aspect", "hillshade", "contour")
_PREFIX = re.compile(r"^processing\.run:")


def clean(ch):
    ch = [_PREFIX.sub("", x) for x in ch]
    out = []
    for x in ch:
        if not out or out[-1] != x:
            out.append(x)
    n = len(out)
    for p in range(1, n // 2 + 1):
        if n % p == 0 and all(out[i] == out[i % p] for i in range(n)):
            out = out[:p]
            break
    return out


def modality(ch):
    v = r = 0
    for o in ch:
        lo = o.lower()
        if o.startswith(("gdal:", "saga:")) or any(h in lo for h in _RASTER_NAME):
            r += 1
        elif o.startswith(("native:", "qgis:")):
            v += 1
    if v and r:
        return "mixed"
    if r > v:
        return "raster"
    return "vector" if v else "unknown"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", required=True)
    ap.add_argument("--min-len", type=int, default=2)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    seen = set()
    modc = Counter()
    kept = []
    raw = 0
    for fp in sorted(globmod.glob(args.glob)):
        for line in open(fp, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            raw += 1
            ch = clean(json.loads(line)["chain"])
            if len(ch) < args.min_len:
                continue
            key = tuple(ch)
            if key in seen:
                continue
            seen.add(key)
            m = modality(ch)
            modc[m] += 1
            kept.append({"chain": ch, "modality": m, "n": len(ch)})

    print(f"raw_chains_in={raw}  unique_cleaned_chains={len(kept)}")
    print(f"modality: {dict(modc)}")
    if kept:
        print(f"mean_len={statistics.mean(k['n'] for k in kept):.1f}")
        print(f"vector-relevant (vector+mixed) = {modc['vector'] + modc['mixed']}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            for k in kept:
                f.write(json.dumps(k, ensure_ascii=False) + "\n")
        print(f"out -> {args.out}")


if __name__ == "__main__":
    main()
