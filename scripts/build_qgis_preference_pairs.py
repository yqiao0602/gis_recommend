#!/usr/bin/env python3
"""Build QGIS vector preference pairs from described vector candidates.

For each described chain (chosen), constructs a rejected chain by:
  1. Modality mismatch: pair a vector chain with a raster template
  2. Missing key steps: drop one critical operator
  3. Generic template: replace task-specific ops with generic ones

Also loads existing DPO model beam outputs as negative candidates when available.

Output: qgis_vector_preference_pairs.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

DESCRIBED_INPUT = ROOT / "outputs_v2" / "qgis_vector_chain_described.jsonl"
OUTPUT = ROOT / "outputs_v2" / "qgis_vector_preference_pairs.jsonl"

# Raster template chains (for modality mismatch negatives)
RASTER_TEMPLATES = [
    ["gdal:warpreproject", "gdal:cliprasterbymasklayer", "native:zonalstatisticsfb"],
    ["native:buffer", "gdal:cliprasterbymasklayer", "qgis:rastercalculator"],
    ["gdal:buildvirtualraster", "gdal:warpreproject", "gdal:cliprasterbymasklayer",
     "gdal:cliprasterbyextent", "gdal:translate"],
    ["native:fillnodata", "gdal:cliprasterbymasklayer", "native:zonalstatisticsfb"],
]

# Generic "safe" vector templates (too generic, not task-specific)
GENERIC_TEMPLATES = [
    ["native:reprojectlayer", "native:savefeatures"],
    ["native:reprojectlayer", "native:extractbyexpression", "native:mergevectorlayers"],
    ["native:reprojectlayer", "native:fieldcalculator", "native:savefeatures"],
    ["native:buffer", "native:fixgeometries", "native:savefeatures"],
]


def missing_key_negative(ops: list[str], official: dict[str, dict]) -> list[str] | None:
    """Remove one middle operator to create a 'missing step' negative."""
    if len(ops) < 3:
        return None
    idx = random.randint(1, len(ops) - 2)  # keep first and last
    return ops[:idx] + ops[idx + 1:]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(DESCRIBED_INPUT))
    parser.add_argument("--output", default=str(OUTPUT))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    random.seed(args.seed)
    candidates = []
    with Path(args.input).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            candidates.append(json.loads(line))

    print(f"Loaded {len(candidates)} described vector candidates")

    pairs = []
    stats = Counter()

    for c in candidates:
        chosen_ops = c["qgis_ops"]
        modality = c.get("modality", "pure_vector")
        n = len(chosen_ops)

        # Choose negative strategy based on modality
        neg_type = ""
        rejected_ops = []

        # Strategy 1: Modality mismatch (vector -> raster template)
        if modality == "pure_vector" and random.random() < 0.4:
            rejected_ops = random.choice(RASTER_TEMPLATES)
            neg_type = "modality_mismatch"

        # Strategy 2: Missing key step
        elif n >= 3 and random.random() < 0.5:
            result = missing_key_negative(chosen_ops, {})
            if result:
                rejected_ops = result
                neg_type = "missing_step"

        # Strategy 3: Generic template
        else:
            rejected_ops = random.choice(GENERIC_TEMPLATES)
            neg_type = "generic_template"

        pair = {
            "task_description_zh": c.get("task_description_zh", ""),
            "task_description_en": c.get("task_description_en", ""),
            "modality": modality,
            "chosen": chosen_ops,
            "chosen_l3": c.get("optional_l3_sequence"),
            "chosen_names": c.get("operator_names", []),
            "rejected": rejected_ops,
            "rejection_type": neg_type,
            "intent_tags": c.get("intent_tags", []),
            "confidence": c.get("confidence", 0.5),
            "source": "qgis_vector_v2_described",
        }
        pairs.append(pair)
        stats[neg_type] += 1
        stats["total"] += 1

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.output).open("w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    print(f"\nPreference pairs: {len(pairs)} -> {args.output}")
    print(f"  modality_mismatch: {stats['modality_mismatch']}")
    print(f"  missing_step:      {stats['missing_step']}")
    print(f"  generic_template:  {stats['generic_template']}")


if __name__ == "__main__":
    main()
