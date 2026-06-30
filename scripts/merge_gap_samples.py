"""
merge_gap_samples.py — Merge targeted_gap_mining outputs into training package.

Merges CSV + PY generated samples with existing labeled_workflows package.
Handles L3 code strings → token IDs, deduplication, split update.

Usage (on server):
    python3 scripts/merge_gap_samples.py \
        --csv samples_csv.jsonl --py samples_py.jsonl \
        --package step8_quality_gate_qgis_vector_v2
"""
import json
import hashlib
import shutil
import argparse
from pathlib import Path
from collections import Counter
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PKG = ROOT / "outputs_v2/pipeline/step8_quality_gate_qgis_vector_v2"
ID_MAPPINGS = ROOT / "outputs_v2" / "id_mappings_v2.json"


def load_map():
    with open(ID_MAPPINGS, "r", encoding="utf-8") as f:
        idm = json.load(f)
    l3_to_id = idm.get("l3", {})
    id_to_l3 = {v: k for k, v in l3_to_id.items()}
    return l3_to_id, id_to_l3


def load_existing(pkg_dir: Path):
    """Load existing labeled workflows from package."""
    candidates = list(pkg_dir.glob("labeled_workflows_*.json"))
    if not candidates:
        raise FileNotFoundError(f"No labeled_workflows found in {pkg_dir}")

    wf_path = candidates[0]
    print(f"  Loading: {wf_path.name}")
    with open(wf_path, "r", encoding="utf-8") as f:
        wf = json.load(f)
    return wf, wf_path.stem


def load_splits(pkg_dir: Path):
    """Load dataset splits."""
    candidates = list(pkg_dir.glob("dataset_splits_*.json"))
    if not candidates:
        return None
    with open(candidates[0], "r", encoding="utf-8") as f:
        return json.load(f)


def load_generated(filepath: Path) -> list:
    """Load generated samples from JSONL file."""
    if not filepath or not filepath.exists():
        print(f"  [SKIP] Not found: {filepath}")
        return []

    samples = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    print(f"  Loaded {len(samples)} from {filepath.name}")
    return samples


def convert_sample(gs: dict, l3_to_id: dict) -> dict | None:
    """Convert generated sample to training format."""
    l3_codes = gs.get("l3_codes", [])
    if not l3_codes:
        return None

    # Convert L3 codes to token IDs
    token_ids = []
    for code in l3_codes:
        tid = l3_to_id.get(code)
        if tid is not None:
            token_ids.append(tid)

    if not token_ids:
        return None

    confidence = float(gs.get("confidence", 0.7))
    num_steps = len(l3_codes)
    source = gs.get("source", "targeted_gap_mining")
    task_type = gs.get("task_type", "General GIS")

    return {
        "l3_sequence": token_ids,
        "l3_codes": l3_codes,
        "operator_sequence": [],
        "confidences": [confidence] * num_steps,
        "ambiguity_flags": [False] * num_steps,
        "metadata": {
            "script_id": gs.get("script_id", ""),
            "source": source,
            "original_num_operators": num_steps,
            "labeled_num_operators": num_steps,
            "num_ambiguous": 0,
            "avg_confidence": confidence,
            "skipped_by_category": {},
            "cleaning_metadata": None,
        },
        "task_metadata": {
            "task_type": task_type,
            "task_name": gs.get("task_description", "")[:100] if gs.get("task_description") else "",
            "task_description": gs.get("task_description", ""),
        },
        "quality_gate": {
            "source": source,
            "sequence_hash": hashlib.md5("".join(l3_codes).encode()).hexdigest(),
            "task_type_original": task_type,
            "task_type_normalized": task_type,
        },
    }


def deduplicate(new_samples: list, existing: list) -> list:
    """Remove duplicates based on l3_codes matching existing sequences."""
    existing_seqs = set()
    for s in existing:
        seq = tuple(s.get("l3_codes", []))
        existing_seqs.add(seq)

    deduped = []
    duplicates = 0
    for s in new_samples:
        seq = tuple(s.get("l3_codes", []))
        if seq not in existing_seqs:
            deduped.append(s)
            existing_seqs.add(seq)
        else:
            duplicates += 1

    return deduped, duplicates


def main():
    parser = argparse.ArgumentParser(description="Merge gap mining samples into training package")
    parser.add_argument("--csv", type=str, default="",
                        help="Path to CSV-generated samples JSONL")
    parser.add_argument("--py", type=str, default="",
                        help="Path to PY-generated samples JSONL")
    parser.add_argument("--package", type=str, default=str(DEFAULT_PKG),
                        help="Path to training package directory")
    parser.add_argument("--output", type=str, default="",
                        help="Output package directory (default: package + '_gap_v1')")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate without writing output")
    args = parser.parse_args()

    pkg_dir = Path(args.package)
    if not pkg_dir.exists():
        print(f"[ERROR] Package not found: {pkg_dir}")
        return

    out_dir = Path(args.output) if args.output else pkg_dir.parent / (pkg_dir.name + "_gap_v1")

    # 1. Load ID mappings
    print("[1] Loading ID mappings...")
    l3_to_id, id_to_l3 = load_map()
    print(f"  {len(l3_to_id)} L3 code -> token ID mappings")

    # 2. Load existing package
    print("[2] Loading existing package...")
    wf, wf_stem = load_existing(pkg_dir)
    existing = wf["labeled_workflows"]
    print(f"  Existing samples: {len(existing)}")

    splits = load_splits(pkg_dir)
    if splits:
        print(f"  Existing splits: train={len(splits.get('train_indices',[]))}, "
              f"val={len(splits.get('val_indices',[]))}, "
              f"test={len(splits.get('test_indices',[]))}")

    # 3. Load generated samples
    print("[3] Loading generated samples...")
    csv_file = Path(args.csv) if args.csv else None
    py_file = Path(args.py) if args.py else None

    gen_samples = []
    if csv_file and csv_file.exists():
        gen_samples.extend(load_generated(csv_file))
    if py_file and py_file.exists():
        gen_samples.extend(load_generated(py_file))

    if not gen_samples:
        print("[ERROR] No generated samples to merge!")
        return

    print(f"  Total generated: {len(gen_samples)}")

    # 4. Convert format
    print("[4] Converting format...")
    converted = []
    unknown_codes = set()
    skip_empty = 0

    for gs in gen_samples:
        converted_sample = convert_sample(gs, l3_to_id)
        if converted_sample is None:
            skip_empty += 1
            continue
        # Check unknown codes
        for c in gs.get("l3_codes", []):
            if c not in l3_to_id:
                unknown_codes.add(c)
        converted.append(converted_sample)

    print(f"  Converted: {len(converted)}")
    print(f"  Skipped (empty/missing): {skip_empty}")
    if unknown_codes:
        print(f"  [WARN] Unknown L3 codes: {unknown_codes}")

    # 5. Deduplicate
    print("[5] Deduplicating...")
    deduped, dupes = deduplicate(converted, existing)
    print(f"  After dedup: {len(deduped)} (removed {dupes} duplicates)")

    # 6. Validate token IDs
    print("[6] Validating token IDs...")
    existing_ids = set()
    for s in existing:
        for tid in s.get("l3_sequence", []):
            existing_ids.add(tid)

    new_ids = set()
    for s in deduped:
        for tid in s.get("l3_sequence", []):
            new_ids.add(tid)

    missing = new_ids - existing_ids
    if missing:
        missing_codes = [id_to_l3.get(i, str(i)) for i in missing]
        print(f"  [INFO] New token IDs: {missing_codes}")
    else:
        print(f"  [OK] All {len(new_ids)} token IDs in vocab")

    # 7. Merge and save
    if args.dry_run:
        print("\n[DONE] Dry run — would merge {len(deduped)} new samples.")
        print(f"  Total would be: {len(existing) + len(deduped)}")
        return

    print("[7] Saving merged package...")
    out_dir.mkdir(parents=True, exist_ok=True)

    all_samples = existing + deduped
    new_indices = list(range(len(existing), len(all_samples)))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    # Update splits (new samples go to train only)
    if splits:
        updated_splits = {
            "train_indices": splits["train_indices"] + new_indices,
            "val_indices": splits["val_indices"],
            "test_indices": splits["test_indices"],
        }
        splits_out = out_dir / f"dataset_splits_{wf_stem.replace('labeled_workflows_', '')}_gap_v1.json"
        # Simplify: use original naming
        split_name = None
        for fname in pkg_dir.glob("dataset_splits_*.json"):
            split_name = fname.name
            break
        if split_name:
            splits_out = out_dir / split_name
        with open(splits_out, "w", encoding="utf-8") as f:
            json.dump(updated_splits, f, ensure_ascii=False)
        print(f"  Saved: {splits_out.name}")
        print(f"    train={len(updated_splits['train_indices'])}, "
              f"val={len(updated_splits['val_indices'])}, "
              f"test={len(updated_splits['test_indices'])}")

    # Merge info
    merged_wf = {
        "labeled_workflows": all_samples,
        "merge_info": {
            "original_samples": len(existing),
            "new_csv_samples": len([s for s in deduped if "csv" in s.get("metadata", {}).get("source", "")]),
            "new_py_samples": len([s for s in deduped if "py" in s.get("metadata", {}).get("source", "")]),
            "duplicates_removed": dupes,
            "merged_at": timestamp,
        },
        **{k: v for k, v in wf.items() if k != "labeled_workflows"},
    }

    wf_out = out_dir / f"labeled_workflows_l3_v4_quality_gate_qgis_gap_v1.json"
    with open(wf_out, "w", encoding="utf-8") as f:
        json.dump(merged_wf, f, ensure_ascii=False)
    print(f"  Saved: {wf_out.name} ({len(all_samples)} samples)")

    # Copy supporting files
    for fname in pkg_dir.glob("*.*"):
        if fname.name.startswith("labeled_workflows") or fname.name.startswith("dataset_splits"):
            continue
        dst = out_dir / fname.name
        if not dst.exists():
            shutil.copy2(fname, dst)

    # 8. Summary
    print(f"\n{'='*60}")
    print(f"MERGE COMPLETE")
    print(f"{'='*60}")
    print(f"  Package: {out_dir}")
    print(f"  Total: {len(all_samples)} (existing={len(existing)} + new={len(deduped)} - dupes={dupes})")

    # Code distribution of new samples
    new_cc = Counter()
    for s in deduped:
        for c in s.get("l3_codes", []):
            new_cc[c] += 1

    print(f"\n  New L3 code coverage ({len(new_cc)} codes):")
    for code, count in sorted(new_cc.items()):
        print(f"    {code}: {count}")


if __name__ == "__main__":
    main()
