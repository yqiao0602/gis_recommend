"""Rebuild the Operator Capability Profile: Layer A (v2 type normalization)
+ Layer B/C merge (QGIS registry + GRASS interfaces). Deterministic.

Type normalization v2: closed vocabulary - unknown free-text types from
the catalog (e.g. 'median', 'coefficient of variation') collapse to
structural classes ('table'/'report'/'literal') instead of passing
through verbatim.
"""

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
CATALOG = BASE.parents[1] / 'benchmarks/qgis_planner_v1/authority/qgis_catalog.json'

TYPE_NORM = {'polygon': 'vector', 'point': 'vector', 'line': 'vector', 'table': 'vector',
             'features': 'vector', 'vector': 'vector', 'raster': 'raster', 'grid': 'raster',
             'dem': 'raster'}
STAT_WORDS = {'median', 'majority', 'minority', 'min', 'max', 'sum', 'mean', 'count',
              'coefficient', 'variation', 'deviation', 'average', 'range', 'variance'}


def norm_type(t: str):
    t = t.strip().lower()
    if not t:
        return None
    if t == 'literaldata':
        return None
    if t in TYPE_NORM:
        return TYPE_NORM[t]
    if '/' in t:  # e.g. image/tiff
        return 'image'
    if t in ('html', 'htm', 'report'):
        return 'report'
    if t in ('csv', 'dbf', 'file'):
        return 'file'
    words = set(t.replace('_', ' ').split())
    if words & STAT_WORDS or ' ' in t:
        return 'table'
    closed = {'raster', 'vector', 'table', 'report', 'file', 'image', 'literal', 'string'}
    return t if t in closed else 'literal'


def norm_types(ts):
    out = set()
    for t in ts or []:
        v = norm_type(t)
        if v:
            out.add(v)
    return sorted(out)


def main() -> None:
    cat = json.loads(CATALOG.read_text(encoding='utf-8'))
    reg = {r['id']: r for r in json.loads(
        (BASE / 'qgis_registry_dump_v1.json').read_text(encoding='utf-8')) if 'error' not in r}
    grass = {r['id']: r for r in json.loads(
        (BASE / 'qgis_registry_dump_grass7_v1.json').read_text(encoding='utf-8'))}
    reg.update(grass)

    profile = {}
    for op in cat['operators']:
        oid = op['operator_id']
        rec = {
            'operator_id': oid,
            'official_name': op['official_name'],
            'provider': op['provider'],
            'input_types_raw': op.get('input_types', []),
            'output_types_raw': op.get('output_types', []),
            'input_types_norm': norm_types(op.get('input_types')),
            'output_types_norm': norm_types(op.get('output_types')),
            'layer_a': True,
            'layer_b_params': None,
            'layer_c_intent': None,
        }
        r = reg.get(oid)
        if r:
            rec['layer_b_params'] = {'parameters': r['parameters'], 'outputs': r['outputs'],
                                     'n_required': sum(1 for p in r['parameters'] if p.get('mandatory')),
                                     'n_optional': sum(1 for p in r['parameters'] if not p.get('mandatory'))}
            rec['layer_c_intent'] = {'text': (r.get('shortDescription') or '').strip() or None,
                                     'source': ('grass_interface' if oid.startswith('grass7:')
                                                else 'qgis_short_description'),
                                     'audited': False}
        profile[oid] = rec

    full = sum(1 for v in profile.values() if v.get('layer_b_params'))
    meta = {'layer_b_total': f'{full}/{len(profile)}',
            'layer_b_sources': ['qgis_registry_dump_v1.json (QGIS 3.28.13, 873 algs)',
                                'qgis_registry_dump_grass7_v1.json (grass83 interfaces, 256)'],
            'type_normalization': 'v2 closed vocabulary'}
    profile['_meta'] = meta
    out = BASE / 'qgis_operator_capability_profile_v0_4.json'
    out.write_text(json.dumps(profile, ensure_ascii=False, indent=1, sort_keys=True),
                   encoding='utf-8')
    print(f'profile v0.4: {len(profile)-1} operators, LayerB {full} -> {out}')


if __name__ == '__main__':
    main()
