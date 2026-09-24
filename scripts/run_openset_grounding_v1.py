"""⑥-4 Open-set Grounding Sufficiency (pure analysis, frozen assets only).

Three levels per owner ruling, all deterministic (Profile v0.4 + the
Audit-A CCPP instances; no model, no training, no converter/table
changes):

  L1 same-family open   : candidates = all catalog ops labeled with the
                          target's semantic family (family labels: oracle
                          MAP for the 148 + deterministic keyword rules
                          for the rest; UNFAMILY excluded here)
  L2 full-catalog open  : candidates = full catalog after the hard
                          compatibility filter (typed I/O equality),
                          family-blind
  L3 cross-family noise : L1 candidates + same-signature ops from other
                          families

Matching signature = (input_types, output_types, slot roles) - the ④
contract attributes; provider/algorithm ID never used. Outputs: UG/AMB/
INS per level, Candidate Reduction funnel, Ambiguity Set Size
(median/P90/max), family difficulty ranking.
"""
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'scripts'))
sys.path.insert(0, str(BASE))
from build_route2_semantic_oracle_v1 import MAP  # noqa: E402
from build_audit_a_v1 import ROLE_MAP  # noqa: E402  (contract role abstraction)

PROFILE = BASE / 'route2_training/profile/qgis_operator_capability_profile_v0_4.json'
AUDIT_A = BASE / 'docs/reports/route2_p0_contract/test111_final_v1/audit_a_v1.json'
REGIME = 'contract'  # 'raw' = param-name ceiling; 'contract' = abstracted roles (what plans render)
OUT = BASE / ('docs/reports/route2_p0_contract/plan_pipeline_v1/openset_grounding_v1_' + REGIME + '.json')

FAMILY_KEYWORDS = [
    ('SPATIAL_CLIP', ('clip', 'difference', 'intersect')),
    ('VECTOR_GEOMETRY', ('buffer', 'centroid', 'convexhull', 'simplify', 'smooth',
                         'dissolve', 'multipart', 'singleparts', 'vertices', 'explodelines',
                         'mergelines', 'extendlines', 'densify', 'snap', 'translategeometry',
                         'fixgeometries', 'deleteholes', 'polygonstolines', 'linestopolygons',
                         'triangulation', 'generalize', 'orientedminimumbbox', 'eliminate')),
    ('BAND_ARITHMETIC', ('rastercalculator', 'calculator', 'normalize', 'bandarith',
                         'rasterlocalop', 'cellstatistics')),
    ('REGIONAL_STATS', ('zonal', 'statistics', 'sampling', 'contour', 'profile')),
    ('RESAMPLE_REPROJECT', ('warpreproject', 'reproject', 'rescale', 'assignprojection',
                            'defineprojection', 'resample')),
    ('AGGREGATION', ('aggregate', 'groupby', 'countpointsinpolygon', 'meancoordinates')),
    ('TEMPORAL_FILTER', ('filterdate', 'temporal')),
    ('SPATIAL_FILTER', ('extractbylocation', 'selectbylocation', 'extractbyextent',
                        'extractbyexpression', 'extractbyattribute', 'selectbyattribute')),
    ('SPATIAL_JOIN', ('joinattributesbylocation', 'joinbynearest', 'joinbylocationsummary',
                      'joinattributestable', 'union', 'spatialjoin')),
    ('BAND_SELECT', ('rearrange_bands', 'selectbands', 'rgb', 'spectral')),
    ('RASTER_TO_VECTOR', ('polygonize', 'rastertovector', 'contour', 'pixelstopoints',
                          'pixelstopolygons', 'grass7:r.to.vect', 'todownload')),
    ('VECTOR_TO_RASTER', ('rasterize', 'vectortoraster')),
    ('TERRAIN_DERIVED', ('slope', 'aspect', 'ruggedness', 'hillshade', 'terrain',
                         'wetness', 'wind', 'horizon', 'solarradiation', 'precipitation')),
    ('COMPOSITE', ('merge', 'mosaic', 'pansharp', 'buildvirtualraster', 'harmonize')),
    ('EXPORT_OUTPUT', ('export', 'savedeatures', 'package', 'todrive', 'printcomp',
                       'report', 'layout')),
    ('MASKING', ('mask', 'updatemask', 'fillnodata', 'sieve')),
    ('NEIGHBORHOOD', ('focal', 'neighborhood', 'idwinterpolation', 'tininterpolation',
                      'fillnodata', 'grid')),
    ('CLASSIFICATION', ('classifier', 'clusterer', 'classify', 'train', 'kmeans',
                        'randomforest', 'cart')),
    ('COLLECTION_MGMT', ('rename', 'refactor', 'reorder', 'style', 'layer', 'package',
                         'metadata', 'quality', 'excel', 'dataset', 'splitvectorlayer',
                         'creategrid', 'extenttolayer', 'randompoints')),
]


def family_of(oid: str, name: str) -> str:
    if oid in MAP:
        return MAP[oid]
    low = (oid + ' ' + name).lower()
    for fam, keys in FAMILY_KEYWORDS:
        if any(kk in low for kk in keys):
            return fam
    return 'UNFAMILY'


REGIME = 'contract'  # 'raw' = implementation param names (ceiling); 'contract' = abstracted roles


REGIME = 'contract'  # 'raw' = implementation param names (ceiling); 'contract' = abstracted roles


def sig(op: dict) -> tuple:
    b = op.get('layer_b_params') or {}
    if REGIME == 'contract':
        roles = tuple(sorted(rr for rr in (ROLE_MAP.get(p['name'].lower()) for p in b.get('parameters', [])) if rr))
    else:
        roles = tuple(sorted(p['name'] for p in b.get('parameters', [])))
    return (tuple(op.get('input_types_norm') or ()),
            tuple(op.get('output_types_norm') or ()),
            roles)


def main() -> int:
    profile = {k: v for k, v in json.loads(
        PROFILE.read_text(encoding='utf-8')).items() if not k.startswith('_')}
    audit = json.loads(AUDIT_A.read_text(encoding='utf-8'))
    instances = [i for i in audit['instances'] if i['level'] == 'full']

    fam_label = {}
    for oid, op in profile.items():
        fam_label[oid] = family_of(oid, op.get('official_name', ''))

    results = []
    funnel_all = defaultdict(list)
    amb_sizes = defaultdict(list)
    for inst in instances:
        fam = inst['semantic_family']
        target = inst['target']
        t_op = profile[target]
        t_sig = sig(t_op)
        matrix = json.loads((BASE / 'docs/reports/route2_p0_contract/test111_final_v1/'
                             'grounding_discriminator_matrix_v1.json').read_text(encoding='utf-8'))
        group_members = set(matrix['groups'][fam]['candidates'])

        # candidate pools
        full_b = {oid for oid, op in profile.items() if op.get('layer_b_params')}
        l0 = group_members & full_b
        l1 = {oid for oid in full_b if fam_label.get(oid) == fam}
        l2 = {oid for oid in full_b
              if sig(profile[oid])[0] == t_sig[0] and sig(profile[oid])[1] == t_sig[1]}
        l3 = l1 | {oid for oid in full_b if sig(profile[oid]) == t_sig and fam_label.get(oid) != fam}

        row = {'semantic_family': fam, 'target': target}
        for lv, cand in (('L0_closed', l0), ('L1_family', l1), ('L2_catalog', l2),
                         ('L3_cross', l3)):
            matches = sorted(oid for oid in cand if sig(profile[oid]) == t_sig)
            n = len(matches)
            row[lv] = {'n_candidates': len(cand), 'n_supporting': n,
                       'ug': n == 1, 'amb': n > 1, 'ins': n == 0}
            funnel_all[lv].append([len(cand), n])
            if n > 1:
                amb_sizes[lv].append(n)
        results.append(row)

    agg = {}
    for lv in ('L0_closed', 'L1_family', 'L2_catalog', 'L3_cross'):
        n_inst = len(results)
        ug = sum(1 for r in results if r[lv]['ug'])
        amb = sum(1 for r in results if r[lv]['amb'])
        ins = sum(1 for r in results if r[lv]['ins'])
        pairs = funnel_all[lv]
        amb_n = amb_sizes[lv]
        agg[lv] = {
            'UG_rate': round(ug / n_inst, 3), 'AMB_rate': round(amb / n_inst, 3),
            'INS_rate': round(ins / n_inst, 3),
            'reduction_median_start': round(statistics.median(p[0] for p in pairs), 1),
            'reduction_median_end': round(statistics.median(p[1] for p in pairs), 1),
            'amb_set_median': round(statistics.median(amb_n), 1) if amb_n else None,
            'amb_set_p90': round(sorted(amb_n)[int(0.9 * len(amb_n))], 1) if amb_n else None,
            'amb_set_max': max(amb_n) if amb_n else None,
        }

    fam_diff = defaultdict(lambda: {'UG': 0, 'n': 0})
    for r in results:
        fam_diff[r['semantic_family']]['n'] += 1
        fam_diff[r['semantic_family']]['UG'] += r['L2_catalog']['ug']
    fam_rank = sorted(({'family': f, 'UG_rate_L2': round(d['UG'] / d['n'], 3), 'n': d['n']}
                       for f, d in fam_diff.items()), key=lambda x: x['UG_rate_L2'])

    out = {'levels': agg, 'per_family_L2_UG': fam_rank, 'instances': results}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({'levels': agg}, ensure_ascii=False, indent=1))
    print('\nL2 family difficulty (lowest UG first):')
    for r in fam_rank[:8]:
        print(f"  {r['family']:20s} UG={r['UG_rate_L2']} (n={r['n']})")
    print(f'\nwritten: {OUT}')
    return 0


if __name__ == '__main__':
    main()
