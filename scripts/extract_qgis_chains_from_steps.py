#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract QGIS alg-id operator chains from yll's step-graph extraction.

Reads a merged_nodes_process.csv (yll's workflow extraction output, READ-ONLY)
and reconstructs, per source script, the ordered sequence of QGIS processing
algorithm calls (api_source_type == 'qgis_processing_algorithm', alg-id in
normalized_api_name), ordered by statement_index.

Output: a chains.jsonl ({source_script, chain:[alg-id...], n}) written into the
caller-specified --out (under /home/qy/system_redesign, NEVER into yll's data),
plus a stats summary (script count, length distribution, vector/raster split,
unique chains) — to quantify the usable QGIS chain reservoir.

stdlib only (no pandas). Streams the CSV.

Usage:
    python extract_qgis_chains_from_steps.py --input <merged_nodes_process.csv> --out <chains.jsonl>
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))  # args field holds large JSON

# Coarse modality by alg-id namespace/name (quantification only; precise modality
# later via the QGIS io_types registry).
_RASTER_HINTS = ("gdal:", "saga:")
_RASTER_NAME = ("raster", "rasterize", "warp", "dem", "slope", "aspect", "hillshade", "contour")


def _modality(chain):
    v = r = 0
    for op in chain:
        o = op.lower()
        if o.startswith(_RASTER_HINTS) or any(h in o for h in _RASTER_NAME):
            r += 1
        elif o.startswith("native:") or o.startswith("qgis:"):
            v += 1
    if v and r:
        return "mixed"
    if r > v:
        return "raster"
    return "vector" if v else "unknown"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-len", type=int, default=2, help="keep chains with >= this many ops")
    args = ap.parse_args()

    per_script = defaultdict(list)  # script -> [(stmt_idx, id, alg_id)]
    rows = 0
    with open(args.input, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows += 1
            if (row.get("api_source_type") or "").strip() != "qgis_processing_algorithm":
                continue
            alg = (row.get("normalized_api_name") or "").strip()
            if not alg or ":" not in alg:
                continue
            script = (row.get("source_script") or "").strip()
            try:
                stmt = int(row.get("statement_index") or 0)
            except ValueError:
                stmt = 0
            per_script[script].append((stmt, row.get("id", ""), alg))

    chains = []
    for script, steps in per_script.items():
        steps.sort(key=lambda t: (t[0], t[1]))
        chain = [alg for _, _, alg in steps]
        if len(chain) >= args.min_len:
            chains.append({"source_script": script, "chain": chain, "n": len(chain),
                           "modality": _modality(chain)})

    with open(args.out, "w", encoding="utf-8") as f:
        for ch in chains:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")

    # ── stats ──
    n = len(chains)
    mod = Counter(ch["modality"] for ch in chains)
    lens = [ch["n"] for ch in chains]
    uniq = len({tuple(ch["chain"]) for ch in chains})
    print(f"rows_scanned={rows}  scripts_with_qgis_algs={len(per_script)}  chains(len>={args.min_len})={n}")
    print(f"unique_chains={uniq}  mean_len={sum(lens)/n:.1f}" if n else "no chains")
    print(f"modality: vector={mod['vector']} raster={mod['raster']} mixed={mod['mixed']} unknown={mod['unknown']}")
    print(f"out -> {args.out}")


if __name__ == "__main__":
    main()
