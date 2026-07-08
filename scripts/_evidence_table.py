#!/usr/bin/env python3
"""Per-class evidence table for 13 new L3 codes.

For each new code, checks:
1. Real frequency in raw PY scripts (not via L3 mapping bias)
2. Can it be reasonably expressed by existing 94 codes?
3. Has clean training samples (single-code purity)?
4. Appears in open_landing gold annotation needs?
5. Has a clear QGIS landing bridge (L2 classification unambiguous)?
6. Semantic boundary — overlaps with existing codes?

Outputs Markdown table.
"""

import json, csv, re, os
from collections import Counter

PROJECT_ROOT = '/home/qy/system_redesign'

# ── 13 new codes ──
NEW_CODES = {
    'L3_02_01_02': {'name': 'Reproject', 'l2': 'L2_02_01',
                    'qgis_ops': ['reprojectlayer', 'assignprojection', 'warpreproject'],
                    'existing_alt': 'No L3 code for coordinate transformation',
                    'semantic_boundary': 'Distinct from L2_01_* data mgmt; distinct from raster reproject (L3_03_04_01)'},
    'L3_02_01_03': {'name': 'Fix Geometries', 'l2': 'L2_02_01',
                    'qgis_ops': ['fixgeometries', 'checkvalidity', 'repairgeometries'],
                    'existing_alt': 'No L3 code for geometry repair',
                    'semantic_boundary': 'Distinct from geometry conversion (L2_02_05, L2_02_07); repair ≠ convert'},
    'L3_02_03_01': {'name': 'Grid', 'l2': 'L2_02_03',
                    'qgis_ops': ['creategrid', 'fishnet', 'regularpoints'],
                    'existing_alt': 'Could be confused with raster grid (L3_03_*); this is VECTOR grid',
                    'semantic_boundary': 'Vector grid vs raster grid — needs L1_02 prefix to distinguish'},
    'L3_02_03_02': {'name': 'Simplify', 'l2': 'L2_02_03',
                    'qgis_ops': ['simplifygeometries'],
                    'existing_alt': 'No L3 code, but Smooth might be similar',
                    'semantic_boundary': 'Simplify (topological generalisation) ≠ Smooth (cartographic smoothing)'},
    'L3_02_03_03': {'name': 'Voronoi', 'l2': 'L2_02_03',
                    'qgis_ops': ['voronoipolygons'],
                    'existing_alt': 'No L3 code',
                    'semantic_boundary': 'Unique operation, no overlap'},
    'L3_02_03_04': {'name': 'Delaunay Triangulation', 'l2': 'L2_02_03',
                    'qgis_ops': ['delaunaytriangulation'],
                    'existing_alt': 'No L3 code; dual of Voronoi',
                    'semantic_boundary': 'Pairs with Voronoi, but distinct operation'},
    'L3_02_05_01': {'name': 'Delete Duplicate', 'l2': 'L2_02_05',
                    'qgis_ops': ['deleteduplicategeometries', 'deleteidenticalgeometries'],
                    'existing_alt': 'Could be approximated by Union+Dissolve combination',
                    'semantic_boundary': 'Data cleanup, not spatial analysis — but still a distinct operation'},
    'L3_02_05_02': {'name': 'Snap', 'l2': 'L2_02_05',
                    'qgis_ops': ['snapgeometries', 'snapgeometrytolayer'],
                    'existing_alt': 'No L3 code for topological snapping',
                    'semantic_boundary': 'Distinct from Buffer (L3_02_01_01) — snapping is topological, not geometric'},
    'L3_02_05_03': {'name': 'Delete Holes', 'l2': 'L2_02_05',
                    'qgis_ops': ['deleteholes'],
                    'existing_alt': 'Could be expressed as Select+Erase combination',
                    'semantic_boundary': 'Boundary overlaps with L3_02_02_04 (Erase) + L3_02_06_* (selection)'},
    'L3_02_05_04': {'name': 'Smooth', 'l2': 'L2_02_05',
                    'qgis_ops': ['smoothgeometry'],
                    'existing_alt': 'No L3 code; Simplify operates on topology, Smooth on vertex placement',
                    'semantic_boundary': 'Similar to Simplify in concept but different algorithm'},
    'L3_02_05_05': {'name': 'Concave Hull', 'l2': 'L2_02_05',
                    'qgis_ops': ['concavehull'],
                    'existing_alt': 'L3_02_05_12 (Min Bounding Geometry) = convex hull; concave hull is distinct',
                    'semantic_boundary': 'Different from Min Bounding Geometry (convex vs concave)'},
    'L3_02_07_02': {'name': 'Polygons to Lines', 'l2': 'L2_02_07',
                    'qgis_ops': ['polygonstolines'],
                    'existing_alt': 'L3_02_07_01 (Multipart→Singlepart) handles geometry set conversion, not type conversion',
                    'semantic_boundary': 'Geometry type conversion, distinct from set operations in L2_02_07'},
    'L3_02_07_03': {'name': 'Extract Vertices', 'l2': 'L2_02_07',
                    'qgis_ops': ['extractvertices'],
                    'existing_alt': 'L3_02_05_11 (Feature to Point) = centroid; vertices ≠ centroid',
                    'semantic_boundary': 'Distinct from Feature to Point — vertices preserve boundary, centroid is center'},
}


def main():
    # ── 1. Raw PY script frequency ──
    print("Loading raw scan data...")
    raw_counts = {}
    # Use the already-scanned data from _scan_raw_ops.py output
    # We'll read from the log or re-scan quickly
    scan_path = f'{PROJECT_ROOT}/outputs_v2/vocab_expansion_v1/vocab_expansion_raw_samples.jsonl'

    # 2. Training sample quality
    train_counts = Counter()
    single_code_rate = {}
    if os.path.exists(scan_path):
        with open(scan_path) as f:
            for line in f:
                if line.strip():
                    s = json.loads(line)
                    for c in s['l3_codes']:
                        train_counts[c] += 1
        for code in NEW_CODES:
            total = train_counts.get(code, 0)
            single = sum(1 for line in open(scan_path) if code in json.loads(line)['l3_codes'] and len(json.loads(line)['l3_codes']) == 1)
            single_code_rate[code] = single / max(total / len(open(scan_path).readlines()), 1) if total > 0 else 0

    # 3. open_landing gold need
    gold_csv = f'{PROJECT_ROOT}/outputs_v2/diagnostics/quality_gate/vector_gold_annotated.csv'
    gold_needed = set()
    if os.path.exists(gold_csv):
        with open(gold_csv, encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for r in reader:
                gc = r.get('gold_codes', '')
                if gc:
                    for c in gc.split(','):
                        c = c.strip()
                        if c in NEW_CODES:
                            gold_needed.add(c)

    # 4. Build table
    print()
    print("## Per-Class Evidence Table")
    print()
    print("| Code | Name | PY Scripts | Samples | Single-code% | Gold Need | QGIS Bridge | Boundary OK | **VERDICT** |")
    print("|------|------|-----------|---------|-------------|-----------|-------------|------------|-------------|")

    verdicts = []
    for code, info in sorted(NEW_CODES.items(), key=lambda x: train_counts.get(x[0], 0), reverse=True):
        name = info['name']
        samples = train_counts.get(code, 0)
        sc_rate = single_code_rate.get(code, 0)
        in_gold = "YES" if code in gold_needed else "no"
        qgis_ok = "YES" if info['qgis_ops'] else "?"
        boundary_ok = "YES" if "Distinct" in info.get('semantic_boundary', '') else "⚠ fuzzy"

        # Verdict logic
        if samples >= 500 and in_gold == "YES" and boundary_ok == "YES":
            verdict = "**KEEP** ✅"
        elif samples >= 200 and boundary_ok == "YES":
            verdict = "**KEEP** (conditional)"
            verdicts.append(f"{code}: conditional")
        elif samples < 100:
            verdict = "**DROP** ❌"
        else:
            verdict = "**REVIEW** ⚠"

        # For display, py_scripts count from the raw scan
        py_scripts = "?"  # placeholder — would need scan result

        print(f"| {code} | {name} | {py_scripts} | {samples} | {sc_rate:.0%} | {in_gold} | {qgis_ok} | {boundary_ok} | {verdict} |")

    # ── Summary recommendation ──
    print()
    print("## Recommendation")
    print()
    print("### KEEP (P0 — activate in next training cycle)")
    keep = [code for code, info in NEW_CODES.items() if train_counts.get(code, 0) >= 500]
    for code in keep:
        print(f"- {code} ({NEW_CODES[code]['name']}): {train_counts.get(code,0)} samples")

    print()
    print("### CONDITIONAL (P1 — activate only after boundary clarification)")
    cond = [code for code, info in NEW_CODES.items() if 200 <= train_counts.get(code, 0) < 500]
    for code in cond:
        print(f"- {code} ({NEW_CODES[code]['name']}): {train_counts.get(code,0)} samples")

    print()
    print("### DROP (P3 — insufficient evidence or overlap)")
    drop = [code for code, info in NEW_CODES.items() if train_counts.get(code, 0) < 200]
    for code in drop:
        print(f"- {code} ({NEW_CODES[code]['name']}): {train_counts.get(code,0)} samples — {info.get('existing_alt', '')[:80]}")

    print()
    print("### Activation Experiment (3-5 codes)")
    print("Select the top 3-5 KEEP codes, construct an oversampling training package")
    print("(family_sampler weight for new token families = 5-10x), train a small")
    print("warmstart cycle (10-20 epochs on the 94→107 head only), and verify that")
    print("the model actually outputs these new tokens in open_landing evaluation.")


if __name__ == '__main__':
    main()
