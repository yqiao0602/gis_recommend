#!/usr/bin/env python3
"""Direct scan of raw PY scripts for operations NOT covered by existing L3 codes.
Bypasses the L3 mapping to avoid selection bias."""

import os, re, sys
from collections import Counter

GEE = '/home/yll/GEE'

OPS_TO_FIND = {
    'Reproject': ['reproject', 'warpreproject', 'assignprojection'],
    'Simplify': ['simplifygeometr', 'v.generalize'],
    'Fix Geometries': ['fixgeometr', 'checkvalidity', 'repairgeometr'],
    'Grid': ['creategrid', 'fishnet', 'regularpoints'],
    'Voronoi': ['voronoipolygons', 'v.voronoi'],
    'Delaunay': ['delaunaytriangulation', 'v.delaunay'],
    'Export': ['savefeatures', 'saveselected', 'exporttospreadsheet', 'packagelayers'],
    'Delete Duplicate': ['deleteduplicategeometr', 'deleteidentical'],
    'Snap': ['snapgeometr', 'snappointstogrid'],
    'Table Join': ['joinattributesbyfield', 'joinbyfield'],
    'Add/Update Field': ['addfieldtoattributestable', 'fieldcalculator', 'refactorfields'],
    'Delete Holes': ['deleteholes'],
    'Smooth': ['smoothgeometry', 'smooth'],
    'Concave Hull': ['concavehull'],
    'Extract Vertices': ['extractvertices'],
    'Polygon to Polyline': ['polygonstolines', 'extractboundary'],
    'Single to Multipart': ['singlepartstomultipart', 'promotetomultipart'],
    'Network Analysis': ['shortestpath', 'servicearea', 'distancematrix'],
    'Heatmap': ['heatmapkerneldensity'],
}

op_counts = Counter()
script_counts = Counter()
total_scanned = 0
total_qgis = 0
has_run_count = 0

for root, dirs, files in os.walk(GEE):
    if 'QGIS' not in root:
        continue
    for f in files:
        if not f.endswith('.py'):
            continue
        total_qgis += 1
        fp = os.path.join(root, f)
        try:
            with open(fp, 'r', encoding='utf-8-sig', errors='ignore') as fh:
                content = fh.read(32768)
        except Exception:
            continue

        total_scanned += 1
        has_run = 'processing.run' in content
        if not has_run:
            continue
        has_run_count += 1

        content_lower = content.lower()

        # Extract all alg_ids from this script
        alg_ids = set()
        for pattern in [
            r"processing\.(?:runalg|run)\s*\(\s*'([^']+)'",
            r'processing\.(?:runalg|run)\s*\(\s*"([^"]+)"',
        ]:
            for m in re.findall(pattern, content):
                alg_ids.add(m.lower())

        for op_name, patterns in OPS_TO_FIND.items():
            found = 0
            for pat in patterns:
                matching = [a for a in alg_ids if re.search(pat, a)]
                found += len(matching)
            if found:
                op_counts[op_name] += found
                script_counts[op_name] += 1

        if total_scanned % 50000 == 0:
            print('  scanned %d/%d (has_run=%d)...' % (total_scanned, total_qgis, has_run_count))

print()
print('Scanned: %d QGIS py scripts, %d with processing.run()' % (total_scanned, has_run_count))
print()
print('%-25s %8s %8s  %s' % ('Operation', 'Scripts', 'Calls', 'Recommendation'))
print('-' * 70)

for op_name in sorted(OPS_TO_FIND.keys()):
    sc = script_counts.get(op_name, 0)
    oc = op_counts.get(op_name, 0)

    if sc > 500:
        rec = 'P0: MUST ADD'
    elif sc > 100:
        rec = 'P1: should add'
    elif sc > 20:
        rec = 'P2: optional'
    else:
        rec = 'P3: skip'

    bar = '#' * min(50, max(1, sc // 20))
    print('%-25s %8d %8d  %-15s %s' % (op_name, sc, oc, rec, bar))
