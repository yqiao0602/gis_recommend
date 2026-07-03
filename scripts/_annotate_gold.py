#!/usr/bin/env python3
"""Annotate 40 vector open_landing tasks with gold-standard L3 chains."""
import csv, json, sys
from collections import Counter

# ── L3 code reference ──
CODE_NAMES = {
    'L3_02_01_01': 'Buffer', 'L3_02_02_01': 'Intersect',
    'L3_02_02_02': 'Union', 'L3_02_02_04': 'Erase',
    'L3_02_02_05': 'Symmetrical Difference', 'L3_02_02_06': 'Clip',
    'L3_02_02_07': 'Update', 'L3_02_03_05': 'Collect Features',
    'L3_02_04_01': 'Spatial Join', 'L3_02_05_06': 'Split Line at Point',
    'L3_02_05_11': 'Feature to Point', 'L3_02_05_12': 'Min Bounding Geometry',
    'L3_02_06_01': 'Select by Attribute', 'L3_02_06_02': 'Extract by Attribute',
    'L3_02_06_03': 'Extract by Location', 'L3_02_06_05': 'Filter by Geometry',
    'L3_02_07_01': 'Multipart to Singlepart', 'L3_01_03_04': 'Merge',
    'L3_01_02_06': 'Calculate Field',
}

# ── Gold-standard L3 chains (carefully annotated per actual task) ──
# Key: "N/A" means the task requires L3 codes NOT in the 17 vector vocabulary.
GOLD = {
    # ── Well-covered tasks ──
    1:  ['L3_02_06_01', 'L3_02_01_01', 'L3_02_02_06'],   # Buffer roads 500m + clip to city boundary
    2:  ['L3_02_06_01', 'L3_02_03_05', 'L3_01_02_06'],   # Dissolve parcels by land use + calculate area per class
    3:  ['L3_01_03_04'],                                    # Merge three county shapefiles → single layer
    4:  ['L3_02_02_01'],                                    # Intersect flood zones + building footprints
    5:  ['L3_02_06_01', 'L3_02_02_04'],                    # Erase development sites from wetland (Select wetland, erase overlap)
    6:  ['L3_01_03_04', 'L3_02_03_05'],                    # Merge watersheds → dissolve into single polygon
    7:  ['L3_02_06_01', 'L3_02_02_06'],                    # Clip transmission lines to corridor
    8:  ['L3_02_04_01'],                                    # Spatial join census population → school districts
    9:  ['L3_02_06_02'],                                    # Select roads where surface_type='gravel'
    10: ['L3_02_01_01', 'L3_02_06_03'],                    # Buffer fault 200m → select buildings within

    # ── N/A: No matching L3 code in vocabulary ──
    11: [],   # Reproject WGS84→UTM — no L3 code for CRS transform in vector set
    12: [],   # Fix invalid geometries — no L3 code for geometry repair (exists in raster L3 but not vector)
    13: [],   # Simplify river network — no L3 code for Simplify
    14: [],   # Create regular grid — no L3 code for grid generation
    15: [],   # Voronoi polygons — no L3 code
    16: [],   # Heatmap density — no L3 code (this is more interpolation/heatmap)
    17: [],   # Nearest facility + travel distance — network analysis, no L3 code

    # ── Partial coverage ──
    18: ['L3_01_03_04', 'L3_02_03_05'],                    # Merge pipeline segments → dissolve
    19: ['L3_02_06_03'],                                    # Select wells within contaminated zone
    20: ['L3_02_04_01'],                                    # Join soil property table to farm polygons by field ID

    # ── N/A: No matching L3 code ──
    21: [],   # Polygon boundaries → polylines (Lines to Polygons reverse), no L3 code
    22: ['L3_02_05_11'],                                    # Extract centroid of building footprints
    23: ['L3_02_05_06'],                                    # Split road centerlines at intersection points
    24: [],   # Delete holes <10sqm from building footprints — no L3 code
    25: [],   # Smooth contour lines — no L3 code

    # ── Partial ──
    26: [],   # Concave hull around GPS points — no L3 code
    27: [],   # Thiessen polygons from rain gauge — no L3 code
    28: [],   # Delaunay triangulation on boreholes — no L3 code

    # ── Well-covered ──
    29: ['L3_02_04_01', 'L3_01_02_06'],                    # Spatial join (count incidents) by district
    30: ['L3_02_06_01'],                                    # Select by expression: pop>50000 AND area<100
    31: [],                                                  # Update admin boundary — attribute only, no spatial L3 needed
    32: [],                                                  # Export parcels to shapefile — export op, no L3 code
    33: ['L3_01_03_04'],                                    # Reproject(no code) + merge → at least Merge
    34: ['L3_02_01_01', 'L3_02_02_06', 'L3_02_03_05'],    # Buffer 30m + clip to watershed + dissolve by order
    35: [],                                                  # Snap road endpoints — no L3 code
    36: [],                                                  # Delete duplicate geometries — no L3 code
    37: [],                                                  # Join table by road ID — attribute join, no spatial L3
    38: [],                                                  # Singlepart→Multipart by region — reverse of Multipart→Singlepart
    39: [],                                                  # Extract vertices from polygons — no L3 code
    40: ['L3_02_01_01', 'L3_02_01_01', 'L3_02_01_01'],    # Multi-ring buffer 100m+200m+500m → Buffer x3
}


def set_f1(pred, gold):
    p, g = set(pred), set(gold)
    if not p and not g: return 1.0
    if not p or not g: return 0.0
    tp = len(p & g)
    prec = tp / len(p)
    rec = tp / len(g)
    return 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0


def grade_model(pred_codes, gold_codes):
    if not gold_codes:
        return 'N/A'  # no gold standard available (L3 vocabulary gap)
    pred_set = set(pred_codes)
    gold_set = set(gold_codes)
    if pred_set == gold_set: return 'A'
    overlap = pred_set & gold_set
    extra = pred_set - gold_set
    if len(overlap) >= len(gold_set) * 0.6 and len(extra) <= 2: return 'B'
    if len(overlap) >= 1: return 'C'
    return 'D'


def main():
    rows = []
    with open('/tmp/vector_gold_input.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    updated = []
    for r in rows:
        idx = int(r['idx'])
        gold_codes = GOLD.get(idx, [])
        gold_names = ' -> '.join([f'{c}({CODE_NAMES.get(c, c)})' for c in gold_codes])
        model_codes = [c.strip() for c in r['model_l3_codes'].split(',') if c.strip()]
        grade = grade_model(model_codes, gold_codes)
        gold_set = set(gold_codes)
        model_set = set(model_codes)
        notes_parts = []
        missing = gold_set - model_set
        extra = model_set - gold_set
        if missing: notes_parts.append('missing: ' + ', '.join(CODE_NAMES.get(c,c) for c in missing))
        if extra: notes_parts.append('extra: ' + ', '.join(CODE_NAMES.get(c,c) for c in extra))
        notes = '; '.join(notes_parts)

        updated.append({
            'idx': idx, 'task': r['task'],
            'model_l3_names': r['model_l3_names'],
            'model_l3_codes': r['model_l3_codes'],
            'qgis_chain': r['qgis_chain'],
            'gold_codes': ', '.join(gold_codes),
            'gold_names': gold_names,
            'grade': grade, 'notes': notes,
        })

    out_path = '/home/qy/system_redesign/outputs_v2/diagnostics/quality_gate/vector_gold_annotated.csv'
    with open(out_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['idx', 'task', 'model_l3_names', 'model_l3_codes', 'qgis_chain',
                         'gold_codes', 'gold_names', 'grade', 'notes'])
        for r in updated:
            writer.writerow([r[k] for k in ['idx','task','model_l3_names','model_l3_codes',
                             'qgis_chain','gold_codes','gold_names','grade','notes']])

    grades = Counter()
    f1s = []
    na_count = 0
    for r in updated:
        mc = [c.strip() for c in r['model_l3_codes'].split(',') if c.strip()]
        gc = [c.strip() for c in r['gold_codes'].split(',') if c.strip()]
        if not gc:
            na_count += 1
            r['grade'] = 'N/A'
        else:
            r['grade'] = grade_model(mc, gc)
            f1s.append(set_f1(mc, gc))
        grades[r['grade']] += 1

    n = len(updated)
    scored_n = n - na_count
    print('=== Gold Annotation Complete ===')
    print(f'Total: {n} vector tasks')
    print(f'Scorable (have gold L3): {scored_n}')
    print(f'N/A (L3 vocabulary gap): {na_count}')
    print(f'\nGrade distribution (scorable tasks only):')
    for g in ['A', 'B', 'C', 'D']:
        cnt = grades.get(g, 0)
        print(f'  {g}: {cnt:2d} ({100*cnt/max(scored_n,1):.0f}%)')
    print(f'\nOverall SetF1 (scorable tasks): {sum(f1s)/max(len(f1s),1):.3f}')
    print(f'Saved: {out_path}')

    # Print A and D cases for review
    print('\n=== Grade A (perfect match) ===')
    for r in updated:
        if r['grade'] == 'A':
            print(f'  [{r["idx"]:2d}] {r["task"][:70]}')
    print('\n=== Grade D (wrong) ===')
    for r in updated:
        if r['grade'] == 'D':
            print(f'  [{r["idx"]:2d}] {r["task"][:70]}')
            print(f'        Gold: {r["gold_names"]}')
            print(f'        Model: {r["model_l3_names"]}')

    print('\n=== Grade C (partial) ===')
    for r in updated:
        if r['grade'] == 'C':
            print(f'  [{r["idx"]:2d}] {r["task"][:60]}')
            print(f'        {r["notes"]}')


if __name__ == '__main__':
    main()
