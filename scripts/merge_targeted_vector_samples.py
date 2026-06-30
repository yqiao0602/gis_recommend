"""
merge_targeted_vector_samples.py

Merge targeted_vector_mining output into the existing oversampled training package.
Handles format alignment: L3 code strings → token IDs, field mapping, split update.

Usage (on server):
    python3 scripts/merge_targeted_vector_samples.py
"""

import json
import hashlib
import shutil
from pathlib import Path
from collections import Counter
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
PKG_DIR = ROOT / "outputs_v2" / "pipeline" / "step8_quality_gate_qgis_vector_oversampled"
GEN_FILE = ROOT / "outputs_v2" / "targeted_vector_mining" / "targeted_vector_samples.jsonl"
ID_MAPPINGS = ROOT / "outputs_v2" / "id_mappings_v2.json"

# Output: new package directory
OUT_DIR = ROOT / "outputs_v2" / "pipeline" / "step8_quality_gate_qgis_vector_v2"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load ID mappings
    print("[1/5] Loading ID mappings...")
    with open(ID_MAPPINGS, "r", encoding="utf-8") as f:
        idm = json.load(f)
    l3_to_id = idm.get("l3", {})
    id_to_l3 = {v: k for k, v in l3_to_id.items()}
    print(f"  L3 code -> token ID: {len(l3_to_id)} mappings")

    # 2. Load existing package
    print("[2/5] Loading existing package...")
    wf_path = PKG_DIR / "labeled_workflows_l3_v4_quality_gate_qgis_vector_oversampled.json"
    with open(wf_path, "r", encoding="utf-8") as f:
        wf = json.load(f)
    existing = wf["labeled_workflows"]
    print(f"  Existing samples: {len(existing)}")

    # Analyze existing format
    s0 = existing[0]
    print(f"  Existing keys: {list(s0.keys())}")
    # Check if l3_sequence uses token IDs (ints) or strings
    seq_sample = s0.get("l3_sequence", [])
    seq_types = set(type(x).__name__ for x in seq_sample[:10])
    print(f"  l3_sequence element types: {seq_types}")
    print(f"  l3_sequence sample: {seq_sample[:5]}")
    codes_sample = s0.get("l3_codes", [])
    print(f"  l3_codes sample: {codes_sample[:5]}")

    # 3. Load generated samples
    print("[3/5] Loading generated samples...")
    gen_samples = []
    with open(GEN_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                gen_samples.append(json.loads(line))
    print(f"  Generated samples: {len(gen_samples)}")

    # 4. Convert to existing format
    print("[4/5] Converting format...")
    converted = []
    skip_count = 0
    unknown_codes = set()

    for gs in gen_samples:
        l3_codes = gs.get("l3_codes", [])
        if not l3_codes:
            skip_count += 1
            continue

        # Convert L3 code strings to token IDs (if existing uses ints)
        token_ids = []
        for code in l3_codes:
            if code in l3_to_id:
                token_ids.append(l3_to_id[code])
            else:
                unknown_codes.add(code)

        if not token_ids:
            skip_count += 1
            continue

        confidence = float(gs.get("confidence", 0.7))
        num_steps = len(l3_codes)

        sample = {
            "l3_sequence": token_ids,
            "l3_codes": l3_codes,
            "operator_sequence": [],
            "confidences": [confidence] * num_steps,
            "ambiguity_flags": [False] * num_steps,
            "metadata": {
                "script_id": gs.get("script_id", ""),
                "source": "targeted_vector_mining",
                "original_num_operators": num_steps,
                "labeled_num_operators": num_steps,
                "num_ambiguous": 0,
                "avg_confidence": confidence,
                "skipped_by_category": {},
                "cleaning_metadata": None,
            },
            "task_metadata": {
                "task_type": gs.get("task_type", "Vector Analysis"),
                "task_name": "",
                "task_description": gs.get("task_description", ""),
            },
            "quality_gate": {
                "source": "targeted_vector_mining",
                "sequence_hash": hashlib.md5(
                    "".join(l3_codes).encode()
                ).hexdigest(),
                "task_type_original": gs.get("task_type", "Vector Analysis"),
                "task_type_normalized": gs.get("task_type", "Vector Analysis"),
            },
        }
        converted.append(sample)

    print(f"  Converted: {len(converted)}")
    print(f"  Skipped (empty/missing codes): {skip_count}")
    if unknown_codes:
        print(f"  [WARN] Unknown L3 codes: {unknown_codes}")

    # 5. Validate token IDs
    print("[5/5] Validating and merging...")
    all_existing_ids = set()
    for s in existing:
        for tid in s.get("l3_sequence", []):
            all_existing_ids.add(tid)

    our_ids = set()
    for s in converted:
        for tid in s.get("l3_sequence", []):
            our_ids.add(tid)

    missing_ids = our_ids - all_existing_ids
    if missing_ids:
        missing_codes = [id_to_l3.get(i, str(i)) for i in missing_ids]
        print(f"  [WARN] New token IDs not in existing vocab: {missing_codes}")
        print(f"  These codes might not be in the training vocabulary!")
    else:
        print(f"  [OK] All {len(our_ids)} token IDs present in training vocabulary")

    # 6. Merge and save
    all_samples = existing + converted
    new_indices = list(range(len(existing), len(all_samples)))

    # Load existing splits
    splits_path = PKG_DIR / "dataset_splits_v4_quality_gate_qgis_vector_oversampled.json"
    with open(splits_path, "r", encoding="utf-8") as f:
        splits = json.load(f)

    # Keep val/test unchanged, add new samples to train only
    old_train = len(splits["train_indices"])
    updated_splits = {
        "train_indices": splits["train_indices"] + new_indices,
        "val_indices": splits["val_indices"],
        "test_indices": splits["test_indices"],
    }

    # Save merged package
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    merged_wf = {
        "labeled_workflows": all_samples,
        "merge_info": {
            "original_samples": len(existing),
            "new_samples": len(converted),
            "new_source": "targeted_vector_mining",
            "merged_at": timestamp,
        },
        **{k: v for k, v in wf.items() if k != "labeled_workflows"},
    }

    wf_out = OUT_DIR / "labeled_workflows_l3_v4_quality_gate_qgis_vector_v2.json"
    with open(wf_out, "w", encoding="utf-8") as f:
        json.dump(merged_wf, f, ensure_ascii=False)
    print(f"  Saved: {wf_out} ({len(all_samples)} samples)")

    splits_out = OUT_DIR / "dataset_splits_v4_quality_gate_qgis_vector_v2.json"
    with open(splits_out, "w", encoding="utf-8") as f:
        json.dump(updated_splits, f, ensure_ascii=False)
    print(f"  Saved: {splits_out} "
          f"(train={len(updated_splits['train_indices'])}, "
          f"val={len(updated_splits['val_indices'])}, "
          f"test={len(updated_splits['test_indices'])})")

    # Copy supporting files (vocab, length stats)
    for fname in ["task_type_vocabulary_v4_quality_gate_qgis_vector_oversampled.json",
                   "task_type_length_stats.json"]:
        src = PKG_DIR / fname
        if src.exists():
            dst = OUT_DIR / fname.replace("_oversampled", "_v2")
            shutil.copy2(src, dst)
            print(f"  Copied: {dst.name}")

    # Summary
    print(f"\n{'='*60}")
    print(f"MERGE COMPLETE")
    print(f"{'='*60}")
    print(f"  Package: {OUT_DIR}")
    print(f"  Total samples: {len(all_samples)} (existing={len(existing)} + new={len(converted)})")
    print(f"  Train: {len(updated_splits['train_indices'])}")
    print(f"  Val: {len(updated_splits['val_indices'])}")
    print(f"  Test: {len(updated_splits['test_indices'])}")

    # New L3 code distribution
    new_cc = Counter()
    for s in converted:
        for c in s.get("l3_codes", []):
            new_cc[c] += 1
    print(f"\n  New vector codes in training set:")
    for code, count in sorted(new_cc.items()):
        if code.startswith("L3_02"):
            print(f"    {code}: {count} samples")


if __name__ == "__main__":
    main()
