#!/usr/bin/env python3
"""Evaluate L3 vocabulary gap: check if missing ops exist in QGIS catalog + training data."""
import csv, json, re, os
from collections import Counter

os.chdir('/home/qy/system_redesign')

MISSING_OPS = {
    'Reproject': ['reproject', 'warp', 'transform crs', 'assign projection'],
    'Simplify': ['simplify', 'generalize', 'smooth geometry'],
    'Fix Geometries': ['fix geometr', 'repair geometr', 'validity', 'check validity'],
    'Grid': ['grid', 'create grid', 'fishnet', 'regular points'],
    'Voronoi': ['voronoi', 'thiessen'],
    'Delaunay': ['delaunay', 'triangulation', 'triangulate'],
    'Concave Hull': ['concave hull', 'alpha shape', 'k-nearest concave'],
    'Heatmap': ['heatmap', 'kernel density', 'point density', 'density'],
    'Network Analysis': ['shortest path', 'network', 'service area', 'distance matrix'],
    'Smooth': ['smooth'],
    'Delete Holes': ['delete holes', 'remove holes'],
    'Snap': ['snap geometr', 'snap points', 'snap to grid'],
    'Delete Duplicate': ['delete duplicate', 'remove duplicate', 'delete identical'],
    'Polygon→Polyline': ['polygons to lines', 'extract boundary', 'boundary'],
    'Single→Multipart': ['singleparts to multipart', 'promote to multipart', 'collect geometries'],
    'Extract Vertices': ['extract vertices'],
    'Export': ['save features', 'save selected', 'export', 'package layers'],
    'Table Join': ['join attributes by field', 'join by field value', 'join by table'],
    'Update Field': ['field calculator', 'add field', 'delete field', 'refactor fields'],
}

# ── 1. QGIS catalog check ──
print('=' * 70)
print('维度一：QGIS 算子库中是否有对应算子')
print('=' * 70)

catalog_ops = []
with open('/home/qy/system_redesign/爬取GithubQGIS/QGIS_Input.csv', 'r') as f:
    reader = csv.reader(f)
    next(reader)  # header
    for row in reader:
        if len(row) >= 3:
            catalog_ops.append({
                'provider': row[0],
                'name': row[2].lower(),
                'alg_id': (row[5] if len(row) > 5 else '').lower(),
            })

for concept, keywords in sorted(MISSING_OPS.items()):
    matches = []
    for op in catalog_ops:
        text = op['name'] + ' ' + op['alg_id']
        for kw in keywords:
            if kw in text:
                matches.append(op['provider'] + ':' + op['name'].title())
                break
    if matches:
        print('  [HAS_OP] %-25s: %2d ops  e.g. %s' % (concept, len(matches), matches[0][:60]))
    else:
        print('  [NO_OP]  %-25s: 0 ops in catalog' % concept)

# ── 2. PY script mining check ──
print()
print('=' * 70)
print('维度二：11,277 PY 脚本挖掘数据中的出现频率')
print('=' * 70)

vec_samples = []
with open('outputs_v2/targeted_vector_mining_v2/vector_py_samples_selected.jsonl', 'r') as f:
    for line in f:
        if line.strip():
            vec_samples.append(json.loads(line))

print('Total vector mining samples: %d' % len(vec_samples))

# These are the L3 codes used in the 11,277 samples
l3_in_samples = Counter()
for s in vec_samples:
    for c in s.get('l3_codes', []):
        l3_in_samples[c] += 1

# Also look at the original_ops field
original_ops_in_samples = Counter()
op_has_original = 0
for s in vec_samples:
    ops = s.get('original_ops', [])
    if ops:
        op_has_original += 1
    for op in ops:
        if ':' in op:
            original_ops_in_samples[op.split(':')[-1].lower()] += 1

print('Samples with original_ops: %d/%d' % (op_has_original, len(vec_samples)))

# Check each missing concept against original_ops
for concept, keywords in sorted(MISSING_OPS.items()):
    found = 0
    examples = []
    for op_name, cnt in original_ops_in_samples.most_common():
        for kw in keywords:
            if kw in op_name:
                found += cnt
                if len(examples) < 3:
                    examples.append(op_name)
                break
    if found > 0:
        print('  [IN_MINING] %-25s: %5d occurrences  e.g. %s' % (concept, found, ', '.join(examples[:2])))
    else:
        print('  [NOT_FOUND] %-25s: 0 in PY mining data' % concept)

# ── 3. Training data check ──
print()
print('=' * 70)
print('维度三：95,355 训练数据中的出现频率')
print('=' * 70)

data = json.load(open('outputs_v2/pipeline/step8_v2_vec11277_augmented/labeled_workflows_l3_v4_vec_augmented_11277.json'))
workflows = data['labeled_workflows']

# Load L3 code name mapping
idm = json.load(open('outputs_v2/id_mappings_v2.json'))
l3_id_to_code = {v: k for k, v in idm['l3'].items()}

# Count all L3 codes in training data
l3_in_train = Counter()
total_wf = len(workflows)
for wf in workflows:
    for tid in wf.get('l3_sequence', []):
        code = l3_id_to_code.get(tid, '')
        if code and code not in ('<START>', '<END>'):
            l3_in_train[code] += 1

# Show current 17 vector L3 codes in training
print('\nCurrent 17 vector L3 codes in training data:')
for code in sorted(l3_in_train):
    if code.startswith('L3_02'):
        print('  %s: %6d (%.1f%%)' % (code, l3_in_train[code], 100*l3_in_train[code]/sum(l3_in_train.values())))

# Check which open_landing tasks have NO operator in PY mining data
print()
print('=' * 70)
print('综合评估')
print('=' * 70)

# What percentage of open_landing vector tasks CAN the model express?
# From gold annotation: 20 scorable, 20 N/A
# Of the 20 N/A, which are actually "must have" vs "nice to have"?

print('''
分级建议:

【核心·必须加】
  Reproject        — QGIS有325个投影算子,PY挖掘有大量数据
  Simplify         — QGIS有算子,通用场景高频
  Fix Geometries   — QGIS有算子,数据预处理必备
  Grid             — QGIS有算子(gdal:creategrid等)
  Voronoi/Delaunay — QGIS有对应算子(saga/grass)
  Export           — QGIS有算子(native:savefeatures等)

【重要·建议加】
  Delete Duplicate — 数据清理常用
  Snap             — 拓扑修复
  Table Join       — 属性关联(非空间join)
  Update Field     — 字段操作基础

【低优先·暂缓】
  Heatmap          — 更偏栅格操作
  Network Analysis — 独立模块,复杂度高
  Smooth           — 使用率低
  Delete Holes     — 专项操作
  Concave Hull     — 专项操作
  Polygon→Polyline — 反向操作(少用)
  Single→Multipart — 反向操作(少用)
  Extract Vertices — 专项QC操作
''')
