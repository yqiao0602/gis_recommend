#!/usr/bin/env python3
"""Phase 14: Expand L3 vocabulary from 17 to 30 vector codes.
1. Define 13 new L3 codes with QGIS operator mappings
2. Mine PY scripts for these new codes
3. Build training samples with proper token IDs
"""

import json, os, re, sys, hashlib, time
from collections import Counter, defaultdict
from pathlib import Path

os.chdir('/home/qy/system_redesign')

GEE = '/home/yll/GEE'
OUTPUT_DIR = Path('outputs_v2/vocab_expansion_v1')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── 1. Define new L3 codes ─────────────────────────────────
# Extending from existing 94 codes (IDs 0-93)
NEW_CODES = {
    # P0: 第一类 必须补充
    'L3_02_01_02': {'name': 'Reproject', 'id': 94,
                    'qgis_patterns': ['reprojectlayer', 'warpreproject', 'assignprojection',
                                      'reproject', 'warp']},
    'L3_02_01_03': {'name': 'Fix Geometries', 'id': 95,
                    'qgis_patterns': ['fixgeometries', 'checkvalidity', 'repairgeometries',
                                      'checkvalid', 'repairgeometry']},
    'L3_02_03_01': {'name': 'Grid', 'id': 96,
                    'qgis_patterns': ['creategrid', 'fishnet', 'regularpoints', 'grid',
                                      'creategraticule']},
    'L3_02_03_02': {'name': 'Simplify', 'id': 97,
                    'qgis_patterns': ['simplifygeometries', 'v.generalize', 'simplify',
                                      'generalize']},
    'L3_02_03_03': {'name': 'Voronoi', 'id': 98,
                    'qgis_patterns': ['voronoipolygons', 'v.voronoi', 'voronoi', 'thiessen']},
    'L3_02_03_04': {'name': 'Delaunay Triangulation', 'id': 99,
                    'qgis_patterns': ['delaunaytriangulation', 'v.delaunay', 'delaunay',
                                      'triangulation', 'triangulate']},
    'L3_02_05_01': {'name': 'Delete Duplicate', 'id': 100,
                    'qgis_patterns': ['deleteduplicategeometries', 'deleteidenticalgeometries',
                                      'deleteidentical', 'deleteduplicate', 'removeduplicate']},
    'L3_02_05_02': {'name': 'Snap', 'id': 101,
                    'qgis_patterns': ['snapgeometries', 'snapgeometrytolayer', 'snap',
                                      'snappointstogrid']},
    'L3_02_05_03': {'name': 'Delete Holes', 'id': 102,
                    'qgis_patterns': ['deleteholes', 'removeholes', 'deletehole']},
    'L3_02_05_04': {'name': 'Smooth', 'id': 103,
                    'qgis_patterns': ['smoothgeometry', 'smooth', 'v.generalize.smooth']},
    'L3_02_05_05': {'name': 'Concave Hull', 'id': 104,
                    'qgis_patterns': ['concavehull', 'knearestconcavehull', 'concave',
                                      'alphashape']},

    # P0: 第二类 geometry conversion
    'L3_02_07_02': {'name': 'Polygons to Lines', 'id': 105,
                    'qgis_patterns': ['polygonstolines', 'extractboundary', 'boundary',
                                      'polygonstoline']},
    'L3_02_07_03': {'name': 'Extract Vertices', 'id': 106,
                    'qgis_patterns': ['extractvertices', 'extractvertex', 'vertices']},
}

print(f'New L3 codes: {len(NEW_CODES)} (total: 94 + {len(NEW_CODES)} = {94+len(NEW_CODES)})')
for code, info in sorted(NEW_CODES.items(), key=lambda x: x[1]['id']):
    print(f'  {info["id"]:3d}  {code}  {info["name"]}')

# ── 2. Build inverse mapping for ID mappings update ────────
# Load existing mappings
idm = json.load(open('outputs_v2/id_mappings_v2.json'))
existing_l3 = idm.get('l3', {})
print(f'\nExisting L3 codes: {len(existing_l3)}')

# Verify: new IDs don't conflict
existing_ids = set(existing_l3.values())
for code, info in NEW_CODES.items():
    if info['id'] in existing_ids:
        print(f'CONFLICT: {info["id"]} already used!')
        sys.exit(1)

# ── 3. Mine PY scripts for new L3 codes ────────────────────
print(f'\n[3] Mining PY scripts for new L3 codes...')

new_samples = []
code_hits = Counter()
seen_sequences = defaultdict(Counter)
max_per_code = 3000  # cap per code

# Build pattern matcher
code_patterns = {}
for code, info in NEW_CODES.items():
    code_patterns[code] = [re.compile(p) for p in info['qgis_patterns']]

scanned = 0
has_run = 0
for root, dirs, files in os.walk(GEE):
    if 'QGIS' not in root:
        continue
    for f in files:
        if not f.endswith('.py'):
            continue
        scanned += 1
        fp = os.path.join(root, f)
        try:
            with open(fp, 'r', encoding='utf-8-sig', errors='ignore') as fh:
                content = fh.read(32768)
        except:
            continue
        if 'processing.run' not in content:
            continue
        has_run += 1

        # Extract all alg_ids
        alg_ids = set()
        for pat in [r"processing\.(?:runalg|run)\s*\(\s*'([^']+)'",
                     r'processing\.(?:runalg|run)\s*\(\s*"([^"]+)"']:
            for m in re.findall(pat, content):
                alg_ids.add(m.lower())

        if not alg_ids:
            continue

        # Map each alg_id to new L3 codes
        matched_codes = []
        for aid in alg_ids:
            for code, patterns in code_patterns.items():
                for pat in patterns:
                    if pat.search(aid):
                        matched_codes.append(code)
                        break

        if not matched_codes:
            continue

        l3_codes = list(dict.fromkeys(matched_codes))  # dedup preserve order
        if len(l3_codes) > 12:
            continue

        # Check if we still need samples for these codes
        if not any(code_hits.get(c, 0) < max_per_code for c in l3_codes):
            continue

        # Per-code dedup: allow up to 5 samples per unique sequence per code
        seq_key = tuple(l3_codes)
        for c in l3_codes:
            seq_count = seen_sequences[c].get(seq_key, 0)
            if seq_count < 5:
                seen_sequences[c][seq_key] = seq_count + 1
                code_hits[c] += 1

        sample = {
            'l3_codes': l3_codes,
            'source_file': os.path.basename(fp).replace('.py', ''),
            'source': 'vocab_expansion_mining',
            'original_ops': list(alg_ids)[:12],
        }
        new_samples.append(sample)

        if scanned % 50000 == 0:
            hits_str = ', '.join(f'{NEW_CODES[c]["name"]}:{code_hits.get(c,0)}'
                               for c in sorted(NEW_CODES) if code_hits.get(c,0) < 100)
            status = f'  scanned {scanned} (has_run={has_run}), samples={len(new_samples)}'
            if hits_str:
                status += f' | need_more: {hits_str}'
            print(status)

        if all(code_hits.get(c, 0) >= max_per_code for c in NEW_CODES):
            print(f'  All codes saturated at {max_per_code}! Breaking early.')
            break

print(f'\nScanned: {scanned}, has_run: {has_run}')
print(f'New samples mined: {len(new_samples)}')
print(f'\nPer-code counts:')
for code in sorted(NEW_CODES, key=lambda x: NEW_CODES[x]['id']):
    cnt = code_hits.get(code, 0)
    bar = '#' * (cnt // 50)
    print(f'  {code} {NEW_CODES[code]["name"]:25s}: {cnt:5d} {bar}')

# ── 4. Save raw samples ────────────────────────────────────
raw_out = OUTPUT_DIR / 'vocab_expansion_raw_samples.jsonl'
with open(raw_out, 'w', encoding='utf-8') as f:
    for s in new_samples:
        f.write(json.dumps(s, ensure_ascii=False) + '\n')
print(f'\nRaw samples: {raw_out}')

# ── 5. Save updated ID mappings ────────────────────────────
new_idm = {
    'l3': dict(existing_l3),
    'l2': dict(idm.get('l2', {})),
    'l1': dict(idm.get('l1', {})),
    'qgis_op': dict(idm.get('qgis_op', {})),
    'gee_op': dict(idm.get('gee_op', {})),
    'mapping_metadata': idm.get('mapping_metadata', {}),
    'metadata': dict(idm.get('metadata', {})),
}
for code, info in NEW_CODES.items():
    new_idm['l3'][code] = info['id']

idm_out = OUTPUT_DIR / 'id_mappings_v3_expanded.json'
with open(idm_out, 'w', encoding='utf-8') as f:
    json.dump(new_idm, f, ensure_ascii=False, indent=2)
print(f'Updated ID mappings: {idm_out}')

# ── 6. Summary ──────────────────────────────────────────────
print(f'\n{"="*60}')
print(f'Vocabulary Expansion Summary')
print(f'{"="*60}')
print(f'Existing L3 codes: {len(existing_l3)}')
print(f'New L3 codes:      {len(NEW_CODES)}')
print(f'Total:             {len(existing_l3) + len(NEW_CODES)}')
print(f'Training samples:  {len(new_samples)}')
print(f'Output:            {OUTPUT_DIR}/')
