#!/usr/bin/env python3
"""Repair training packages whose l3_sequence rows lack START/END sentinels.

The TaskConditionedL3DatasetV4 expects raw special tokens in l3_sequence:
  -3 = START, -4 = END
and maps them to internal ids at load time. Generated samples merged as bare L3 ids
therefore teach the model never to emit END. This script rewrites a package into a
new package directory with every sequence normalized to [-3] + content + [-4].
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path

START_RAW = -3
END_RAW = -4
PAD_RAW = -1
UNK_RAW = -2
SPECIAL_RAW = {START_RAW, END_RAW, PAD_RAW, UNK_RAW}


def find_one(directory: Path, pattern: str) -> Path:
    matches = sorted(directory.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No {pattern} in {directory}")
    if len(matches) > 1:
        print(f"  [WARN] Multiple {pattern} files; using {matches[0].name}")
    return matches[0]


def source_of(sample: dict) -> str:
    meta = sample.get("metadata") or {}
    quality = sample.get("_training_quality") or {}
    return meta.get("source") or quality.get("source") or sample.get("source") or "unknown"


def normalize_sequence(seq: list) -> tuple[list, dict]:
    before = list(seq)
    # Keep only content L3 token ids and unknown non-special tokens. Drop all raw sentinels,
    # then re-wrap exactly once to avoid duplicate START/END.
    content = [tok for tok in before if tok not in (START_RAW, END_RAW)]
    fixed = [START_RAW] + content + [END_RAW]
    return fixed, {
        "had_start": bool(before) and before[0] == START_RAW,
        "had_end": bool(before) and before[-1] == END_RAW,
        "changed": fixed != before,
        "before_len": len(before),
        "after_len": len(fixed),
    }


def audit(samples: list[dict]) -> dict:
    counts = Counter()
    by_source = Counter()
    no_start_source = Counter()
    no_end_source = Counter()
    lengths = []
    for sample in samples:
        seq = sample.get("l3_sequence") or []
        src = source_of(sample)
        by_source[src] += 1
        if seq and seq[0] == START_RAW:
            counts["has_start"] += 1
        else:
            counts["no_start"] += 1
            no_start_source[src] += 1
        if seq and seq[-1] == END_RAW:
            counts["has_end"] += 1
        else:
            counts["no_end"] += 1
            no_end_source[src] += 1
        lengths.append(len(seq))
    return {
        "total": len(samples),
        "has_start": counts["has_start"],
        "has_end": counts["has_end"],
        "no_start": counts["no_start"],
        "no_end": counts["no_end"],
        "len_min": min(lengths) if lengths else 0,
        "len_max": max(lengths) if lengths else 0,
        "len_avg": sum(lengths) / max(len(lengths), 1),
        "source_top": by_source.most_common(20),
        "no_start_by_source": no_start_source.most_common(20),
        "no_end_by_source": no_end_source.most_common(20),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fix START/END sentinels in a training package")
    parser.add_argument("--package", required=True, help="Input package directory")
    parser.add_argument("--output", required=True, help="Output package directory")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    in_dir = Path(args.package)
    out_dir = Path(args.output)
    wf_path = find_one(in_dir, "labeled_workflows*.json")
    split_files = sorted(in_dir.glob("dataset_splits*.json"))

    print(f"[1] Loading {wf_path}")
    with open(wf_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    samples = payload.get("labeled_workflows")
    if not isinstance(samples, list):
        raise ValueError("labeled_workflows is missing or not a list")

    print("[2] Before audit")
    before = audit(samples)
    print(json.dumps(before, ensure_ascii=False, indent=2))

    changed = 0
    changes_by_source = Counter()
    for sample in samples:
        seq = sample.get("l3_sequence") or []
        fixed, info = normalize_sequence(seq)
        if info["changed"]:
            changed += 1
            changes_by_source[source_of(sample)] += 1
            sample["l3_sequence"] = fixed
            sample.setdefault("metadata", {})["start_end_repaired"] = True
            sample["metadata"]["start_end_repair_before_len"] = info["before_len"]
            sample["metadata"]["start_end_repair_after_len"] = info["after_len"]

    payload.setdefault("repair_info", {})["start_end_fix"] = {
        "start_raw": START_RAW,
        "end_raw": END_RAW,
        "changed_rows": changed,
        "changed_by_source": dict(changes_by_source),
        "input_package": str(in_dir),
    }

    print("[3] After audit")
    after = audit(samples)
    print(json.dumps(after, ensure_ascii=False, indent=2))
    print(f"[4] Changed rows: {changed}")
    for src, n in changes_by_source.most_common(20):
        print(f"  {src}: {n}")

    if after["no_start"] or after["no_end"]:
        raise RuntimeError("Repair failed: some rows still lack START/END")

    if args.dry_run:
        print("[DONE] Dry run only; no files written")
        return

    print(f"[5] Writing output package: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    out_wf = out_dir / wf_path.name.replace(".json", "_start_end_fixed.json")
    with open(out_wf, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    print(f"  wrote {out_wf.name}")

    for split in split_files:
        shutil.copy2(split, out_dir / split.name)
        print(f"  copied {split.name}")

    for path in in_dir.iterdir():
        if path.name == wf_path.name or path.name.startswith("dataset_splits"):
            continue
        if path.is_file():
            shutil.copy2(path, out_dir / path.name)
            print(f"  copied {path.name}")

    print("[DONE] Package repaired")


if __name__ == "__main__":
    main()
