#!/usr/bin/env python3
"""Gate 3: GEE-contamination scan over route-2 arm predictions (CPU, read-only).

Scans the raw generation text of each prediction for GEE API / syntax residue
that would indicate negative transfer (domain interference) after GEE DAPT.
Pure reporting — no thresholds, no verdict; interpretation belongs to the
Gate 2 report per the roadmap.

Usage:
  python gate3_ee_contamination_scan.py --predictions a.jsonl [--predictions b.jsonl ...] --out scan.json

Each --predictions file is scanned as one arm (arm name = file stem).
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

# GEE residue families: JS API objects/calls, client constructs, and
# Earth-Engine-specific method names that have no QGIS counterpart.
PATTERNS = {
    "ee_object": re.compile(r"\bee\.[A-Za-z]"),
    "ee_client_map": re.compile(r"\bMap\.(addLayer|centerObject|setCenter)\b"),
    "ee_ui": re.compile(r"\bui\.(Chart|root|panel)\b"),
    "ee_collection_type": re.compile(r"\b(ImageCollection|FeatureCollection)\b"),
    "ee_filter_method": re.compile(r"\b(filterDate|filterBounds|calendarRange)\b"),
    "ee_export": re.compile(r"\bExport\.(image|table)\b", re.IGNORECASE),
    "ee_reduce": re.compile(r"\bee\.Reducer\b|\breduceRegion\b"),
}


def scan_text(text):
    hits = {}
    for name, rx in PATTERNS.items():
        m = rx.findall(text or "")
        if m:
            hits[name] = len(m)
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--predictions", action="append", required=True,
                    help="predictions jsonl (repeatable; stem = arm name)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    arms = {}
    for path in args.predictions:
        p = Path(path)
        rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()
                if l.strip()]
        n_rows = len(rows)
        fam_rows = Counter()
        fam_hits = Counter()
        examples = {}
        for r in rows:
            hits = scan_text(r.get("raw", ""))
            for fam, n in hits.items():
                fam_rows[fam] += 1
                fam_hits[fam] += n
                if fam not in examples:
                    examples[fam] = {"wid": r.get("wid"),
                                     "snippet": (r.get("raw", "")[:160])}
        arms[p.stem] = {
            "n_rows": n_rows,
            "clean_rows": n_rows - len({r.get("wid") for r in rows
                                        if scan_text(r.get("raw", ""))}),
            "contaminated_rows": sum(1 for r in rows
                                     if scan_text(r.get("raw", ""))),
            "families": {fam: {"rows": fam_rows[fam], "hits": fam_hits[fam],
                               "row_rate": round(fam_rows[fam] / max(n_rows, 1), 4),
                               "example": examples.get(fam)}
                         for fam in sorted(fam_rows)},
        }
    out = {"schema": "gis_recommend.transfer.gate3.scan", "arms": arms}
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False),
                              encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
