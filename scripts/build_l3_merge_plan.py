# -*- coding: utf-8 -*-
"""
Build the L3 merge & prune plan for the vocab-v2 redesign.

Input:
  classification_hierarchy.csv          (350 L3)
  outputs/pipeline/step8/labeled_workflows_l3_v4_cleaned.json (token freq)

Output (all under outputs_v2/):
  l3_merge_plan.csv             old_l3 -> new_l3 decision per row (350 rows)
  classification_hierarchy_v2.csv   new taxonomy (~120 L3)
  l3_merge_report.txt          human-readable summary

Rules (deterministic):
  R0  L1_06 (anonymous): DELETE ALL
  R1  Dead L1 shrinkage: in DEAD_L1_CODES, keep only active L3s; DELETE rest
  R2  Dead L2 shrinkage: in active L1, if L2 has 0 active AND L2 is in DEAD_L2_CODES,
      DELETE entire L2
  R3  Subfamily merges (SUBFAMILY_MERGES dict)
  R4  Everything else: KEEP (includes zero-freq neighbors in active L2 — may activate
      after mapping fix)
"""
from __future__ import annotations
import csv
import json
import sys
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parents[1]
HIERARCHY_CSV = ROOT / "classification_hierarchy.csv"
WORKFLOWS_JSON = ROOT / "outputs" / "pipeline" / "step8" / "labeled_workflows_l3_v4_cleaned.json"
OUT_DIR = ROOT / "outputs_v2"
OUT_DIR.mkdir(exist_ok=True)

PLAN_CSV = OUT_DIR / "l3_merge_plan.csv"
HIERARCHY_V2_CSV = OUT_DIR / "classification_hierarchy_v2.csv"
REPORT_TXT = OUT_DIR / "l3_merge_report.txt"

# --------------------------------------------------------------------------
# Rule config
# --------------------------------------------------------------------------
# R0/R1: L1s we treat as "dead branch" — only active L3s survive, rest deleted.
DEAD_L1_CODES = {
    "L1_06",  # anonymous / unnamed; 0 active across 26 L3
    "L1_04",  # Surface & Hydrology; 3 active / 36 — keep only active
    "L1_05",  # Spatial Statistics & Geostatistics; 1 active / 30 — keep only active
}

# R2: L2s to delete even though their parent L1 is active.
# All of these have 0 active L3.  Included because they represent capabilities
# GEE data doesn't reflect and keeping 100+ cold tokens would only add noise.
DEAD_L2_CODES = {
    # L1_01 Data Management (mostly admin/ops, not algorithmic)
    "L2_01_04", "L2_01_05", "L2_01_06", "L2_01_07", "L2_01_09",
    "L2_01_10", "L2_01_11", "L2_01_12",
    # L1_03 Raster — only one dead L2 worth dropping (Raster Overlay is niche)
    "L2_03_06",
    # L1_06 already handled via R0
    # L1_07 Visualization — Cartographic / Graphics / Web publishing not in scope
    "L2_07_02", "L2_07_03", "L2_07_05",
    # L1_08 Deep Learning Object Detection (single L3, 0 freq, niche)
    "L2_08_06",
    # L1_09 Image Enhancement — radiometric calib, freq filter, spectral sharp, superres
    "L2_09_01", "L2_09_03", "L2_09_07", "L2_09_09",
    # L1_10 Fusion — multi-res fusion & decision fusion dead
    "L2_10_01", "L2_10_05",
}

# R3: Subfamily merges.  Map old_l3_code -> (new_l3_code, new_l3_name).
# The new code reuses one of the member codes as the canonical (first listed).
# Rationale:
#   - Temporal Reducer family:  Max/Min/Mean/Median/Sum/Percentile/Count are
#     semantically one op "reduce stack along time with stat X"; the stat is a
#     parameter, not a distinct operator.  First/Last is also a reducer but
#     "ordering-aware" — we merge into the same bucket for now (all zero-freq
#     today, so no signal loss).
#   - Raster math arithmetic/logical/comparison/math-funcs/bitwise: same
#     argument — "pixel-wise op with opcode X".  Split into two buckets
#     (arithmetic group vs logical group) to preserve the one distinction the
#     model actually uses.
# R4 refinement: zero-freq L3s are by default dropped unless their L2 is
# "semantic-rich" (≥ ACTIVE_THRESHOLD active L3), OR the L3 is in the
# post-fix activation whitelist (WILL_ACTIVATE) — operators we expect will
# gain freq after the D3 mapping audit.
ACTIVE_THRESHOLD = 4  # L2 with ≥4 active L3 keeps all its zero-freq siblings
WILL_ACTIVATE: set[str] = {
    # L1_01 Schema / Dataset — only fields that QGIS uses
    "L3_01_02_02",  # Delete Field
    "L3_01_02_03",  # Alter Field  (← ee.Image.rename maps here post-fix)
    "L3_01_02_06",  # Calculate Field
    # L1_02 Vector — filter-class ops that map from GEE filter*
    "L3_02_06_01",  # Select by Attribute  (← Filter.eq / filter post-fix)
    "L3_02_06_03",  # Extract by Location
    "L3_02_06_05",  # Filter by Geometry   (← filterbounds post-fix)
    # L1_03 Raster — remote-sensing ops currently inflated into Arithmetic
    "L3_03_08_01",  # Vegetation Indices   (← normalizedDifference NDVI post-fix)
    "L3_03_08_02",  # Water/Urban/Other Indices
    "L3_03_08_04",  # Atmospheric Correction
    "L3_03_08_05",  # Brightness Temperature
    "L3_03_08_08",  # Pan-sharpening
    "L3_03_08_10",  # Quality Band Parsing (QA bits)
    # L1_03 Raster Statistics — Zonal Stats routes reduceRegion
    "L3_03_02_01",  # Zonal Statistics  (← ee.Image.reduceRegion post-fix)
    # L1_03 Raster Extraction — extraction siblings
    "L3_03_01_02",  # Clip Raster by Extent
    "L3_03_01_05",  # Update Mask
    "L3_03_01_09",  # Add/Concatenate Bands
    # L1_07 Export
    "L3_07_04_01",  # Export To Shapefile
    "L3_07_04_06",  # Export Raster To Image
}

SUBFAMILY_MERGES: dict[str, tuple[str, str]] = {}

def _add_merge(members: list[str], new_code: str, new_name: str):
    for m in members:
        SUBFAMILY_MERGES[m] = (new_code, new_name)

# Temporal Reducer family  (L2_03_10, 9 L3 → 1)
_add_merge(
    [
        "L3_03_10_01",  # Temporal Median (0)
        "L3_03_10_02",  # Temporal Mean   (0)
        "L3_03_10_03",  # Temporal Maximum (2,115)
        "L3_03_10_04",  # Temporal Minimum (0)
        "L3_03_10_05",  # Temporal Sum    (0)
        "L3_03_10_08",  # Temporal Percentile (0)
        "L3_03_10_09",  # Temporal Count (0)
        "L3_03_10_10",  # Temporal First/Last (22,589)
        "L3_03_10_12",  # Reduce by Time Interval (0)
    ],
    "L3_03_10_R",
    "Temporal Reducer",
)

# Raster Math — Arithmetic Group (Arithmetic + MathFunctions + Bitwise)
_add_merge(
    [
        "L3_03_03_01",  # Arithmetic Operations (51,473)
        "L3_03_03_04",  # Mathematical Functions (3,428)
        "L3_03_03_06",  # Bitwise Operations (0)
    ],
    "L3_03_03_A",
    "Arithmetic & Math",
)
# Raster Math — Logical Group (Logical + Comparison)
_add_merge(
    [
        "L3_03_03_02",  # Logical Operations (58,393)
        "L3_03_03_03",  # Comparison Operations (0)
    ],
    "L3_03_03_L",
    "Logical & Comparison",
)

# Surface Parameters — keep active trio as-is (Slope/Aspect/Hillshade), drop rest
# already handled by DEAD_L1_CODES (L1_04)

# L1_08 Unsupervised Clustering — keep active, merge ISODATA/K-Means/Superpixel as one
_add_merge(
    [
        "L3_08_05_01",  # K-Means Pixel Clustering (4,137)
        "L3_08_05_02",  # ISODATA / Adaptive Clustering (167)
        "L3_08_05_03",  # Superpixel / SNIC Segmentation (2,007)
    ],
    "L3_08_05_C",
    "Pixel Clustering & Segmentation",
)

# --------------------------------------------------------------------------
# Load hierarchy + freq
# --------------------------------------------------------------------------
def load_hierarchy() -> dict[str, dict]:
    rows = {}
    with HIERARCHY_CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[r["l3_code"]] = r
    return rows

def load_freq() -> Counter:
    with WORKFLOWS_JSON.open(encoding="utf-8") as f:
        data = json.load(f)
    wfs = data["labeled_workflows"] if isinstance(data, dict) else data
    c = Counter()
    for wf in wfs:
        for tok in wf.get("l3_codes", []) or []:
            if isinstance(tok, str) and tok.startswith("L3_"):
                c[tok] += 1
    return c

# --------------------------------------------------------------------------
# Decide per-L3 action
# --------------------------------------------------------------------------
def decide(l3_code: str, info: dict, freq: int, l2_active_count: dict[str, int]) -> tuple[str, str, str, str]:
    """
    Returns (action, new_code, new_name, reason).
      action ∈ {'keep', 'merge', 'delete'}
      new_code/new_name are empty for 'delete'
    """
    l1 = info["l1_code"]
    l2 = info["l2_code"]

    # R0/R1: dead L1 branch — keep only if active
    if l1 in DEAD_L1_CODES:
        if freq > 0:
            return "keep", l3_code, info["l3_name"], f"active in dead L1 {l1}"
        return "delete", "", "", f"dead L1 {l1}, freq=0"

    # R2: dead L2
    if l2 in DEAD_L2_CODES:
        return "delete", "", "", f"dead L2 {l2}"

    # R3: subfamily merge
    if l3_code in SUBFAMILY_MERGES:
        nc, nn = SUBFAMILY_MERGES[l3_code]
        return "merge", nc, nn, f"subfamily merge to {nc}"

    # R4: zero-freq gating
    if freq == 0:
        if l2_active_count.get(l2, 0) >= ACTIVE_THRESHOLD:
            return "keep", l3_code, info["l3_name"], f"zero-freq in rich L2 ({l2_active_count[l2]} active)"
        if l3_code in WILL_ACTIVATE:
            return "keep", l3_code, info["l3_name"], "post-fix activation whitelist"
        return "delete", "", "", f"zero-freq in sparse L2 ({l2_active_count.get(l2, 0)} active)"

    # Active L3 — default keep
    return "keep", l3_code, info["l3_name"], "active, default keep"

# --------------------------------------------------------------------------
# Emit
# --------------------------------------------------------------------------
def main():
    hier = load_hierarchy()
    freq = load_freq()

    # Precompute: for each L2, how many active (freq>0) L3 it has.
    l2_active_count: dict[str, int] = Counter()
    for code, info in hier.items():
        if freq.get(code, 0) > 0:
            l2_active_count[info["l2_code"]] += 1

    plan_rows = []
    for code, info in hier.items():
        f = freq.get(code, 0)
        action, new_code, new_name, reason = decide(code, info, f, l2_active_count)
        plan_rows.append({
            "old_l3": code,
            "old_name": info["l3_name"],
            "l2_code": info["l2_code"],
            "l2_name": info["l2_name"],
            "l1_code": info["l1_code"],
            "l1_name": info["l1_name"],
            "old_freq": f,
            "action": action,
            "new_l3": new_code,
            "new_name": new_name,
            "reason": reason,
        })

    # Write merge_plan.csv
    with PLAN_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["old_l3", "old_name", "l2_code", "l2_name",
                        "l1_code", "l1_name", "old_freq",
                        "action", "new_l3", "new_name", "reason"],
        )
        w.writeheader()
        w.writerows(plan_rows)

    # Build v2 hierarchy (one row per distinct new_l3)
    survivors: dict[str, dict] = {}
    merged_freq: Counter = Counter()
    for row in plan_rows:
        if row["action"] == "delete":
            continue
        new_code = row["new_l3"]
        merged_freq[new_code] += row["old_freq"]
        if new_code not in survivors:
            # keep L2/L1 of the first member we see
            survivors[new_code] = {
                "l3_code": new_code,
                "l3_name": row["new_name"],
                "l3_description": "",  # filled below if keep; merged rows get joined
                "l2_code": row["l2_code"],
                "l2_name": row["l2_name"],
                "l1_code": row["l1_code"],
                "l1_name": row["l1_name"],
                "_members": [row["old_l3"]],
            }
        else:
            survivors[new_code]["_members"].append(row["old_l3"])

    # Fill descriptions (keep original for 'keep'; concat for 'merge')
    desc_map = {}
    for code, info in hier.items():
        desc_map[code] = info.get("l3_description", "")
    for new_code, srow in survivors.items():
        if len(srow["_members"]) == 1:
            srow["l3_description"] = desc_map.get(srow["_members"][0], "")
        else:
            # merged: join descriptions with ' | '
            srow["l3_description"] = " | ".join(
                f"[{m}] {desc_map.get(m, '')}" for m in srow["_members"]
            )

    # Write hierarchy_v2.csv
    with HIERARCHY_V2_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "l3_code", "l3_name", "l3_description",
            "l2_code", "l2_name", "l1_code", "l1_name",
            "old_members", "freq_v2",
        ])
        for new_code, srow in sorted(survivors.items()):
            w.writerow([
                srow["l3_code"],
                srow["l3_name"],
                srow["l3_description"],
                srow["l2_code"],
                srow["l2_name"],
                srow["l1_code"],
                srow["l1_name"],
                "|".join(srow["_members"]),
                merged_freq[new_code],
            ])

    # Summary report
    n_keep = sum(1 for r in plan_rows if r["action"] == "keep")
    n_merge = sum(1 for r in plan_rows if r["action"] == "merge")
    n_delete = sum(1 for r in plan_rows if r["action"] == "delete")
    kept_freq = sum(r["old_freq"] for r in plan_rows if r["action"] != "delete")
    lost_freq = sum(r["old_freq"] for r in plan_rows if r["action"] == "delete")

    lines = []
    lines.append("=== L3 Merge Plan — Summary ===")
    lines.append(f"Input L3 : {len(plan_rows)}")
    lines.append(f"  keep   : {n_keep}")
    lines.append(f"  merge  : {n_merge}  (→ {sum(1 for r in plan_rows if r['action']=='merge' and r['old_l3']==r['new_l3']) + len({r['new_l3'] for r in plan_rows if r['action']=='merge'})} distinct targets)")
    lines.append(f"  delete : {n_delete}")
    lines.append(f"Output L3 vocab (v2): {len(survivors)}")
    lines.append(f"Token budget: kept={kept_freq:,}  deleted={lost_freq:,}  ({lost_freq/(kept_freq+lost_freq)*100:.2f}% dropped)")

    lines.append("\n=== Top 20 v2 L3 by freq (post-merge) ===")
    for new_code, f in merged_freq.most_common(20):
        name = survivors[new_code]["l3_name"]
        mem = survivors[new_code]["_members"]
        mem_str = f" <- {'|'.join(mem)}" if len(mem) > 1 else ""
        lines.append(f"  {new_code:<16} {name[:40]:<40} {f:>8,}{mem_str}")

    lines.append("\n=== Active rate by L1 (v2) ===")
    # v2 active rate: every v2 L3 has freq>0 iff any of its members had freq>0
    by_l1 = defaultdict(lambda: [0, 0, 0])  # [active, total, freq]
    for new_code, srow in survivors.items():
        f = merged_freq[new_code]
        by_l1[(srow["l1_code"], srow["l1_name"])][0] += 1 if f > 0 else 0
        by_l1[(srow["l1_code"], srow["l1_name"])][1] += 1
        by_l1[(srow["l1_code"], srow["l1_name"])][2] += f
    for (l1c, l1n), (act, tot, fr) in sorted(by_l1.items()):
        lines.append(f"  {l1c} {l1n[:30]:<30}  active {act:>2}/{tot:<2}  freq {fr:>9,}")

    lines.append("\n=== Deletes by L1 ===")
    del_by_l1 = Counter()
    for r in plan_rows:
        if r["action"] == "delete":
            del_by_l1[(r["l1_code"], r["l1_name"])] += 1
    for (l1c, l1n), n in sorted(del_by_l1.items(), key=lambda x: -x[1]):
        lines.append(f"  {l1c} {l1n[:30]:<30}  deleted {n}")

    lines.append("\n=== Merges summary ===")
    merge_groups = defaultdict(list)
    for r in plan_rows:
        if r["action"] == "merge":
            merge_groups[(r["new_l3"], r["new_name"])].append(
                (r["old_l3"], r["old_name"], r["old_freq"])
            )
    for (nc, nn), members in merge_groups.items():
        tot = sum(f for _, _, f in members)
        lines.append(f"\n  [{nc}] {nn}  total freq {tot:,}")
        for oc, on, of in sorted(members, key=lambda x: -x[2]):
            lines.append(f"    <- {oc} {on[:40]:<40} {of:>7,}")

    report = "\n".join(lines)
    REPORT_TXT.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nWrote:\n  {PLAN_CSV}\n  {HIERARCHY_V2_CSV}\n  {REPORT_TXT}")

if __name__ == "__main__":
    main()
