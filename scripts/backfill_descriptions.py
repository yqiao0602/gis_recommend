#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backfill training samples with real task descriptions from yll's facts_summary.

Reads existing API-trace->L3 sample JSONL files, joins against the full QGIS
facts_summary (20,428 entries), and writes samples with real descriptions.

Usage:
    python scripts/backfill_descriptions.py --in <samples.jsonl> --out <fixed.jsonl>
    python scripts/backfill_descriptions.py --in-dir <dir_of_jsonls> --out-dir <dir>
"""
from __future__ import annotations

import argparse, csv, json, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FACTS_PATH = ROOT / "outputs_v2" / "_server_batch" / "qgis_facts_full.csv"


def load_facts(path: str | Path) -> dict:
    """Return {script_name: {task_type, task_name, task_description}}."""
    facts = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            fn = (row.get("File Name") or "").strip()
            if fn:
                name = fn.replace(".py", "")
                facts[name] = {
                    "task_type": (row.get("Task Type") or "").strip(),
                    "task_name": (row.get("Task Name") or "").strip(),
                    "task_description": (row.get("Task Description") or "").strip(),
                }
    return facts


def backfill_sample(sample: dict, facts: dict) -> dict:
    """Fill in task_metadata from facts if available."""
    name = sample.get("_script_name", "")
    if name not in facts:
        return sample

    fact = facts[name]
    md = sample.setdefault("task_metadata", {})

    # Only overwrite if currently a placeholder
    current_desc = md.get("task_description", "")
    is_placeholder = (not current_desc or current_desc.startswith("QGIS script:"))

    if is_placeholder:
        md["task_description"] = fact["task_description"] or current_desc
    if not md.get("task_type") or md["task_type"] == "Unknown":
        md["task_type"] = fact["task_type"] or "Unknown"
    if not md.get("task_name") or md["task_name"].startswith("QGIS script:"):
        md["task_name"] = fact["task_name"] or md.get("task_name", name)

    # Update top-level task_description_en used by the builder
    sample["_facts_task_type"] = fact["task_type"]
    return sample


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--in", dest="in_file", help="Single JSONL file")
    group.add_argument("--in-dir", dest="in_dir", help="Directory of JSONL files")
    ap.add_argument("--out", dest="out_file", help="Output file (single mode)")
    ap.add_argument("--out-dir", dest="out_dir", help="Output directory (dir mode)")
    ap.add_argument("--facts", default=str(FACTS_PATH), help="Path to facts_summary CSV")
    args = ap.parse_args()

    facts = load_facts(args.facts)
    print(f"Loaded {len(facts)} facts entries")

    files = []
    if args.in_file:
        files = [args.in_file]
        out_path = args.out_file or args.in_file + ".backfilled.jsonl"
    else:
        files = sorted(Path(args.in_dir).glob("*.jsonl"))
        out_dir = Path(args.out_dir or args.in_dir + "_backfilled")
        out_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    filled = 0
    for fp in files:
        fp = Path(fp)
        samples = []
        with open(fp, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    samples.append(json.loads(line))

        for s in samples:
            total += 1
            before_desc = s.get("task_metadata", {}).get("task_description", "")
            s = backfill_sample(s, facts)
            after_desc = s.get("task_metadata", {}).get("task_description", "")
            if before_desc.startswith("QGIS script:") and not after_desc.startswith("QGIS script:"):
                filled += 1

        # Write
        if args.in_file:
            out = out_path
        else:
            out = out_dir / fp.name

        with open(out, "w", encoding="utf-8") as f:
            for s in samples:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")

        print(f"  {fp.name}: {len(samples)} samples -> {out}")

    print(f"\nDone. {total} total, {filled} backfilled ({100*filled//max(total,1)}%)")
    print(f"  Still placeholder: {total - filled}")

    # Verify: show a few
    import random
    random.seed(1)
    check = random.sample(samples, min(5, len(samples)))
    print(f"\nSpot check:")
    for s in check:
        md = s.get("task_metadata", {})
        codes = [c for c in s.get("l3_codes", []) if c not in ("<START>", "<END>")]
        print(f"  {s.get('_script_name','?')}")
        print(f"    desc: {md.get('task_description','?')[:120]}")
        print(f"    chain: {' -> '.join(codes)}")


if __name__ == "__main__":
    main()
