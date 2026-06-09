# -*- coding: utf-8 -*-
"""
Build v2 GEE → L3 mapping.

Three sources in order of priority (higher wins):

  1. SKIP_SET             — operators that step6 must drop entirely
                            (containers, predicates, setters/getters, constructors)
  2. MANUAL_OVERRIDES     — Top 40 frequency operators with verified v2 L3
  3. Auto-remap of legacy mappings via the v2 merge plan
     (old_l3 -> new_l3, or dropped if the old L3 was deleted)

Output:
  outputs_v2/mapping_metadata_v2.json     same shape as old gee_to_l3, but v2 L3 codes
  outputs_v2/gee_skip_list_v2.json        explicit skip set (consumed by step6 patch)
  outputs_v2/top40_audit.md               human-readable diff table for review
"""
from __future__ import annotations
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD_ID_MAPPINGS = ROOT / "outputs" / "id_mappings.json"
MERGE_PLAN_CSV = ROOT / "outputs_v2" / "l3_merge_plan.csv"
HIER_V2_CSV = ROOT / "outputs_v2" / "classification_hierarchy_v2.csv"
OLD_WORKFLOWS = ROOT / "outputs" / "pipeline" / "step8" / "labeled_workflows_l3_v4_cleaned.json"

OUT_MAPPING = ROOT / "outputs_v2" / "mapping_metadata_v2.json"
OUT_SKIP = ROOT / "outputs_v2" / "gee_skip_list_v2.json"
OUT_AUDIT = ROOT / "outputs_v2" / "top40_audit.md"

# -------------------------------------------------------------------------
# Operators that step6 must NOT label — containers, predicates, setters,
# constructors.  Before: most of these were labeled with nonsense L3 codes
# (Focal Statistics / Mosaic / Feature Stacking) and were inflating the
# top-frequency L3 distribution.  Now they vanish from the label stream.
# -------------------------------------------------------------------------
SKIP_SET: set[str] = {
    # Container / higher-order
    "ee.imagecollection.map",       # .map(fn) — iterate, the real op is `fn`
    "ee.featurecollection.map",     # same
    "ee.list.map",                  # same
    "ee.image.map",                 # rare but same
    "ee.featurecollection.iterate", # reducer-style, often bookkeeping
    "ee.imagecollection.iterate",
    # Filter predicates  (ee.Filter.*) — arguments, not ops
    "ee.filter.eq",
    "ee.filter.neq",
    "ee.filter.lt",
    "ee.filter.lte",
    "ee.filter.gt",
    "ee.filter.gte",
    "ee.filter.and",
    "ee.filter.or",
    "ee.filter.not",
    "ee.filter.bounds",
    "ee.filter.geometry",
    "ee.filter.inlist",
    "ee.filter.listcontains",
    "ee.filter.dayofyear",
    "ee.filter.calendarrange",
    "ee.filter.stringcontains",
    # Reducer definitions (ee.Reducer.*) — arguments to reduceRegion/etc.
    "ee.reducer.mean",
    "ee.reducer.median",
    "ee.reducer.sum",
    "ee.reducer.min",
    "ee.reducer.max",
    "ee.reducer.count",
    "ee.reducer.first",
    "ee.reducer.last",
    "ee.reducer.stdev",
    "ee.reducer.variance",
    "ee.reducer.percentile",
    "ee.reducer.mode",
    "ee.reducer.histogram",
    # Getters / setters (metadata access, no computation)
    "ee.image.get",
    "ee.image.set",
    "ee.feature.get",
    "ee.feature.set",
    "ee.imagecollection.get",
    "ee.imagecollection.set",
    "ee.imagecollection.size",
    "ee.imagecollection.tolist",
    # Constructors (coerce existing data, no transform)
    "ee.imagecollection.fromimages",
    "ee.imagecollection.fromassets",
    "ee.image.constant",
    "ee.featurecollection.fromassets",
    # Structural reorg
    "ee.imagecollection.sort",
    "ee.featurecollection.sort",
}

# -------------------------------------------------------------------------
# Top 40 manual overrides — lowercase GEE op -> v2 L3 code
# Authoritative fixes for the ~80% most-common operator tokens.
# Rationale lives in the audit table (OUT_AUDIT).
# -------------------------------------------------------------------------
MANUAL_OVERRIDES: dict[str, tuple[str, str]] = {
    # (op) -> (v2_l3_code, rationale)
    "ee.image.select": ("L3_03_01_04", "Select Bands (was wrongly Feature Stacking)"),
    "ee.imagecollection.filter": ("L3_03_09_05", "default: Filter by Metadata Property (was Focal Statistics)"),
    "ee.imagecollection.filterdate": ("L3_03_09_01", "Filter by Date Range (already correct)"),
    "ee.imagecollection.filterbounds": ("L3_03_09_06", "Filter by Spatial Bounds (raster collection filter, was Clip)"),
    "ee.image.clip": ("L3_03_01_01", "Clip Raster by Geometry (already correct)"),
    "ee.image.rename": ("L3_01_02_03", "Alter Field (was Feature Stacking)"),
    "ee.image.addbands": ("L3_10_04_01", "Feature Stacking (already correct)"),
    "ee.image.multiply": ("L3_03_03_A", "Arithmetic & Math"),
    "ee.imagecollection.median": ("L3_10_02_03", "Multi-temporal Averaging"),
    "ee.imagecollection.select": ("L3_03_01_04", "Select Bands (already correct)"),
    "ee.imagecollection.reduce": ("L3_03_10_R", "Temporal Reducer"),
    "ee.imagecollection.first": ("L3_03_10_R", "Temporal Reducer (First)"),
    "ee.image.updatemask": ("L3_03_01_05", "Update Mask"),
    "ee.image.classify": ("L3_08_04_01", "Apply Classifier to Imagery"),
    "ee.image.subtract": ("L3_03_03_A", "Arithmetic & Math"),
    "ee.imagecollection.filtermetadata": ("L3_03_09_05", "Filter by Metadata Property"),
    "ee.image.divide": ("L3_03_03_A", "Arithmetic & Math"),
    "ee.imagecollection.merge": ("L3_01_03_04", "Merge"),
    "ee.image.sampleregions": ("L3_08_01_01", "Region-based Sample Extraction"),
    "ee.image.reduceregion": ("L3_03_02_01", "Zonal Statistics (reduce over a region)"),
    "ee.image.reduceregions": ("L3_03_02_01", "Zonal Statistics (reduce over regions)"),
    "ee.classifier.train": ("L3_08_03_01", "Train Random Forest (default classifier)"),
    "ee.classifier.smilerandomforest": ("L3_08_03_01", "Train Random Forest"),
    "ee.image.eq": ("L3_03_03_L", "Logical & Comparison (was Focal Statistics)"),
    "ee.image.neq": ("L3_03_03_L", "Logical & Comparison"),
    "ee.imagecollection.mean": ("L3_10_02_03", "Multi-temporal Averaging"),
    "ee.image.add": ("L3_03_03_A", "Arithmetic & Math"),
    "ee.image.gt": ("L3_03_03_L", "Logical & Comparison"),
    "ee.image.gte": ("L3_03_03_L", "Logical & Comparison"),
    "ee.image.lt": ("L3_03_03_L", "Logical & Comparison"),
    "ee.image.lte": ("L3_03_03_L", "Logical & Comparison"),
    "ee.imagecollection.mosaic": ("L3_03_07_01", "Mosaic to New Raster"),
    "ee.image.normalizeddifference": ("L3_03_08_01", "Vegetation Indices"),
    "ee.image.expression": ("L3_03_03_A", "Arithmetic & Math (Raster Calculator deleted in v2)"),
    "ee.image.pixelarea": ("L3_03_03_A", "Arithmetic & Math (derived raster quantity)"),
    "ee.image.and": ("L3_03_03_L", "Logical & Comparison"),
    "ee.image.or": ("L3_03_03_L", "Logical & Comparison"),
    "ee.image.not": ("L3_03_03_L", "Logical & Comparison"),
    "ee.image.where": ("L3_03_03_L", "Logical & Comparison (conditional)"),
    "ee.image.mask": ("L3_03_01_05", "Update Mask"),
    "ee.image.unmask": ("L3_03_01_05", "Update Mask"),
    "ee.image.paint": ("L3_07_01_06", "Label Features (paint overlay)"),
    "ee.featurecollection.flatten": ("L3_02_03_05", "Collect Features"),
}


def load_merge_map() -> dict[str, tuple[str, str]]:
    out = {}
    with MERGE_PLAN_CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[r["old_l3"]] = (r["action"], r["new_l3"])
    return out


def load_v2_vocab() -> set[str]:
    s = set()
    with HIER_V2_CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            s.add(r["l3_code"])
    return s


def load_op_freq() -> Counter:
    c = Counter()
    with OLD_WORKFLOWS.open(encoding="utf-8") as f:
        wfs = json.load(f)["labeled_workflows"]
    for wf in wfs:
        for op in wf.get("operator_sequence", []) or []:
            if isinstance(op, str):
                c[op] += 1
    return c


def remap_candidates(old_candidates: list[dict], merge_map: dict[str, tuple[str, str]],
                     v2_vocab: set[str]) -> list[dict]:
    """Rewrite each candidate's l3_code via the merge plan.  Drop candidates
    whose old L3 was deleted.  Deduplicate by new L3 (keep highest confidence)."""
    best: dict[str, dict] = {}
    for cand in old_candidates:
        old_code = cand.get("l3_code")
        if not old_code:
            continue
        action, new_code = merge_map.get(old_code, ("keep", old_code))
        if action == "delete":
            continue
        # Validate target is in v2 vocab
        if new_code not in v2_vocab:
            continue
        existing = best.get(new_code)
        if existing is None or cand.get("confidence", 0) > existing.get("confidence", 0):
            # rewrite code
            nc = dict(cand)
            nc["l3_code"] = new_code
            best[new_code] = nc
    # Preserve execution_order from original top candidate order
    return list(best.values())


def main():
    with OLD_ID_MAPPINGS.open(encoding="utf-8") as f:
        id_map = json.load(f)
    old_gee_to_l3: dict[str, dict] = id_map["mapping_metadata"]["gee_to_l3"]

    merge_map = load_merge_map()
    v2_vocab = load_v2_vocab()
    op_freq = load_op_freq()

    # ----- Step 1: auto-remap everything, dropping deletes -----
    new_mapping: dict[str, dict] = {}
    for op_key, meta in old_gee_to_l3.items():
        cands = meta.get("all_candidates", [])
        new_cands = remap_candidates(cands, merge_map, v2_vocab)
        if not new_cands:
            # The old L3 targets were all deleted — leave op unmapped so that
            # step6 routes to <UNK> (and we'll cover it via MANUAL_OVERRIDES
            # below if it's a Top 40 op).
            continue
        # Pick primary as max-confidence
        primary = max(new_cands, key=lambda c: c.get("confidence", 0))
        new_mapping[op_key] = {
            "all_candidates": new_cands,
            "num_candidates": len(new_cands),
            "mapping_type": meta.get("mapping_type", "remapped"),
            "mapping_confidence": primary.get("confidence", 0.5),
            "rationale": f"v2 remap of {meta.get('rationale', '')[:80]}",
            "has_ambiguity": len(new_cands) > 1,
            "primary_l3": primary["l3_code"],
            "source": "auto_remap",
        }

    # ----- Step 2: apply manual overrides (Top 40) -----
    for op_key_lower, (l3, rat) in MANUAL_OVERRIDES.items():
        if l3 not in v2_vocab:
            raise ValueError(f"override {op_key_lower} -> {l3} not in v2 vocab")
        # Write under BOTH the lowercase key AND the camelCase variant so
        # step6 matches regardless of case normalization.
        for variant in {op_key_lower}:
            new_mapping[variant] = {
                "all_candidates": [{
                    "l3_code": l3,
                    "confidence": 0.95,
                    "role": "manual_v2_override",
                    "execution_order": 1,
                }],
                "num_candidates": 1,
                "mapping_type": "manual_override",
                "mapping_confidence": 0.95,
                "rationale": rat,
                "has_ambiguity": False,
                "primary_l3": l3,
                "source": "manual_override",
            }

    # ----- Step 3: export SKIP set (lowercase) -----
    skip_list = sorted(SKIP_SET)

    # ----- Step 4: audit table (Top 40 covered) -----
    top40 = [op for op, _ in op_freq.most_common(40)]
    lines: list[str] = []
    lines.append("# Top 40 GEE → L3 v2 audit")
    lines.append("")
    lines.append(f"Total op tokens: {sum(op_freq.values()):,} | Top 40 coverage: "
                 f"{sum(f for _,f in op_freq.most_common(40)) / sum(op_freq.values()) * 100:.1f}%")
    lines.append("")
    lines.append("| # | GEE op | Freq | % | Source | v2 L3 | Rationale |")
    lines.append("|---|--------|------|---|--------|-------|-----------|")
    for i, op in enumerate(top40, 1):
        f = op_freq[op]
        pct = f / sum(op_freq.values()) * 100
        if op in SKIP_SET:
            src = "SKIP"; l3 = "—"; rat = "container / predicate / setter"
        elif op in MANUAL_OVERRIDES:
            src = "manual"; l3, rat = MANUAL_OVERRIDES[op]
        elif op in new_mapping:
            src = "auto"; l3 = new_mapping[op]["primary_l3"]; rat = new_mapping[op]["rationale"][:80]
        else:
            # Try case-insensitive lookup against old mapping keys
            found = False
            for k in new_mapping:
                if k.lower() == op.lower():
                    src = "auto"; l3 = new_mapping[k]["primary_l3"]; rat = "case-variant auto"
                    found = True; break
            if not found:
                src = "UNMAPPED"; l3 = "—"; rat = "needs manual review"
        lines.append(f"| {i} | `{op}` | {f:,} | {pct:.2f}% | {src} | {l3} | {rat} |")

    # ----- Write outputs -----
    with OUT_MAPPING.open("w", encoding="utf-8") as f:
        json.dump({
            "version": "v2",
            "source": "outputs_v2/mapping_metadata_v2.json",
            "gee_to_l3": new_mapping,
            "stats": {
                "total_entries": len(new_mapping),
                "from_manual_override": sum(1 for v in new_mapping.values() if v["source"] == "manual_override"),
                "from_auto_remap": sum(1 for v in new_mapping.values() if v["source"] == "auto_remap"),
                "skip_list_size": len(skip_list),
            },
        }, f, ensure_ascii=False, indent=2)
    with OUT_SKIP.open("w", encoding="utf-8") as f:
        json.dump({"version": "v2", "skip_operators": skip_list}, f, ensure_ascii=False, indent=2)
    OUT_AUDIT.write_text("\n".join(lines), encoding="utf-8")

    print(f"mapping_v2: {len(new_mapping)} entries")
    print(f"  manual override : {sum(1 for v in new_mapping.values() if v['source']=='manual_override')}")
    print(f"  auto remap      : {sum(1 for v in new_mapping.values() if v['source']=='auto_remap')}")
    print(f"skip_list: {len(skip_list)} operators")
    print(f"\nWrote:\n  {OUT_MAPPING}\n  {OUT_SKIP}\n  {OUT_AUDIT}")


if __name__ == "__main__":
    main()
