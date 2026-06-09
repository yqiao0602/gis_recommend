#!/usr/bin/env python3
"""Convert QGIS vector preference pairs to L3 DPO training format.

Reads qgis_vector_preference_pairs_clean.jsonl, converts QGIS alg_id
sequences to L3 token IDs using crosswalk + name-based mapping,
and outputs JSONL with pos_tokens / neg_tokens for training.

Only keeps pairs where BOTH chosen and rejected map fully and produce
different L3 sequences.

Usage:
    python scripts/build_qgis_dpo_training_data.py
    python scripts/build_qgis_dpo_training_data.py --pairs PATH --output PATH
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

CLEAN_PAIRS = ROOT / "outputs_v2" / "qgis_vector_preference_pairs_clean.jsonl"
OFFICIAL_OPS = ROOT.parent / "operators-json" / "qgis_operators.json"
CROSSWALK = ROOT / "outputs_v2" / "qgis_alg_id_crosswalk.json"
ID_MAPPINGS = ROOT / "outputs_v2" / "id_mappings_v2.json"
OUTPUT_PATH = ROOT / "outputs_v2" / "preference_data" / "qgis_vector_train.jsonl"


def load_official() -> dict[str, dict]:
    with open(OFFICIAL_OPS, "r", encoding="utf-8") as f:
        return {str(o.get("identifier", "")).lower().strip(): o for o in json.load(f)}


def load_crosswalk() -> dict[str, dict]:
    if not CROSSWALK.exists(): return {}
    with CROSSWALK.open("r", encoding="utf-8") as f:
        return json.load(f).get("entries", {})


def load_l3_mapping() -> tuple[dict[str, str], dict[str, str], dict[str, int]]:
    """Returns (name_to_l3_code, l3_code_to_name, l3_code_to_token_id)."""
    with ID_MAPPINGS.open("r", encoding="utf-8") as f:
        idm = json.load(f)
    q2l = idm.get("mapping_metadata", {}).get("qgis_to_l3", {})
    name_to_l3 = {}
    for k, v in q2l.items():
        if isinstance(v, dict) and v.get("primary_l3"):
            name_to_l3[k.lower().strip()] = v["primary_l3"]
    l3_map = idm.get("l3", {})
    l3_to_token = {k: int(v) for k, v in l3_map.items()}
    return name_to_l3, l3_map, l3_to_token


def alg_to_l3_token(
    alg_id: str, official: dict, xwalk: dict, name_to_l3: dict, l3_to_token: dict,
) -> int | None:
    """Convert a single QGIS alg_id to L3 token ID. Returns None if unmappable."""
    # 1) Crosswalk
    if alg_id.lower() in xwalk:
        e = xwalk[alg_id.lower()]
        if e.get("bridge_type") == "l3_bridge":
            code = e.get("l3_code", "")
            if code in l3_to_token:
                return l3_to_token[code]

    # 2) Official name → id_mappings
    op = official.get(alg_id.lower(), {})
    name = op.get("name", "").lower().strip() if op else ""
    if name and name in name_to_l3:
        code = name_to_l3[name]
        if code in l3_to_token:
            return l3_to_token[code]

    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", default=str(CLEAN_PAIRS))
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    args = parser.parse_args(argv)

    official = load_official()
    xwalk = load_crosswalk()
    name_to_l3, l3_to_code, l3_to_token = load_l3_mapping()

    # Also load L3 hierarchy for classification task_type
    l3_hierarchy = {}
    hierarchy_path = ROOT / "outputs_v2" / "classification_hierarchy_v2.csv"
    if hierarchy_path.exists():
        with hierarchy_path.open("r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                code = row.get("l3_code", "").strip()
                l2 = row.get("l2_code", "").strip()
                if code and l2:
                    l3_hierarchy[code] = l2

    pairs = []
    with Path(args.pairs).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            pairs.append(json.loads(line))

    print(f"Loaded {len(pairs)} clean pairs")

    train_data = []
    stats = Counter()

    for p in pairs:
        chosen_ops = p.get("chosen", [])
        rejected_ops = p.get("rejected", [])

        # Convert chosen
        pos_tokens = []
        for op in chosen_ops:
            tid = alg_to_l3_token(op, official, xwalk, name_to_l3, l3_to_token)
            if tid is None:
                pos_tokens = None
                break
            pos_tokens.append(tid)
        if pos_tokens is None:
            stats["chosen_unmappable"] += 1
            continue

        # Convert rejected
        neg_tokens = []
        for op in rejected_ops:
            tid = alg_to_l3_token(op, official, xwalk, name_to_l3, l3_to_token)
            if tid is None:
                neg_tokens = None
                break
            neg_tokens.append(tid)
        if neg_tokens is None:
            stats["rejected_unmappable"] += 1
            continue

        # Must be different
        if pos_tokens == neg_tokens:
            stats["identical"] += 1
            continue

        # Infer task_type from L3 tokens (use first token's L2 category)
        primary_l3_code = ""
        if pos_tokens:
            for code, tid in l3_to_token.items():
                if tid == pos_tokens[0]:
                    primary_l3_code = code
                    break
        l2 = l3_hierarchy.get(primary_l3_code, "Vector")

        # Determine task_type
        if l2.startswith("L2_02"):
            task_type = "Vector Analysis"
        elif l2.startswith("L2_03"):
            task_type = "Raster Analysis"
        else:
            task_type = "GIS Processing"

        record = {
            "pos_tokens": pos_tokens,
            "neg_tokens": neg_tokens,
            "task_name": p.get("task_description_en", ""),
            "task_description": p.get("task_description_zh", ""),
            "task_type": task_type,
            "reward_margin": 0.3,
            "source": "qgis_vector_v2",
        }
        train_data.append(record)
        stats["valid"] += 1

    print(f"\nResults:")
    print(f"  Valid training pairs:  {stats['valid']}/{len(pairs)}")
    print(f"  Rejected - chosen unmappable: {stats['chosen_unmappable']}")
    print(f"  Rejected - rejected unmappable: {stats['rejected_unmappable']}")
    print(f"  Rejected - identical: {stats['identical']}")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.output).open("w", encoding="utf-8") as f:
        for r in train_data:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nOutput: {args.output}")

    # Show sample
    if train_data:
        print(f"\nSample record:")
        r = train_data[0]
        print(f"  pos_tokens: {r['pos_tokens']}")
        print(f"  neg_tokens: {r['neg_tokens']}")
        print(f"  task_type: {r['task_type']}")
        print(f"  task_name: {r['task_name'][:100]}")


if __name__ == "__main__":
    main()
