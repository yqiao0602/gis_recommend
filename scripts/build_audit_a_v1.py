"""Audit-A v1: plan-level separability (A1) + leakage audit + report.

Owner ⑥-1 ruling, steps 5-7. Plan instances are Contract-Consistent
Prototype Plans (CCPP): built ONLY from the ④ information contract
(typed I/O + semantic slot roles), deterministic, no QGIS identity, no
model output, no gold-derived plans, no chain->plan pipeline.

Candidate matching at three degradation levels gives Discriminator
Completeness / essentiality per group:
  full   : input_types + output_types + slot roles
  -slots : input_types + output_types
  -io    : slot roles only

Categories per owner: G0 / G1 / G2-UG (uniquely groundable) / G2-AMB
(multiple legal implementations) / G2-INS (insufficient info; = 0 by
construction in closed groups, becomes measurable at 6-4 open-set).
Leakage scans L1-L3 run on rendered plan text; L4 (reverse recovery)
is vacuous for prototype plans (built from profiles by construction)
and is binding only for 6-2 real plans - reported as deferred.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'scripts'))
from build_route2_semantic_oracle_v1 import MAP  # noqa: E402

PROFILE = BASE / 'route2_training/profile/qgis_operator_capability_profile_v0_4.json'
OUT = BASE / 'docs/reports/route2_p0_contract/test111_final_v1/audit_a_v1.json'

# deterministic param-name -> neutral role map (generic names only;
# unmapped names are EXCLUDED from plans and tracked as coverage loss)
ROLE_MAP = {
    'input': 'primary input', 'input_raster': 'primary input',
    'input_layer': 'primary input', 'layers': 'input layers',
    'start_points': 'start points', 'input_points': 'start points',
    'output': 'output', 'output_html_file': 'report output',
    'overlay': 'overlay geometry', 'mask': 'mask geometry',
    'extent': 'extent constraint',
    'field': 'attribute field', 'field_name': 'attribute field',
    'column': 'attribute field', 'fields': 'attribute fields',
    'band': 'band selector', 'raster_band': 'band selector',
    'target_crs': 'coordinate reference', 'crs': 'coordinate reference',
    'data_type': 'output data type', 'type': 'output data type',
    'method': 'computation method', 'resampling': 'computation method',
    'expression': 'filter expression', 'predicate': 'spatial predicate',
    'nodata': 'nodata handling', 'ignore_nodata': 'nodata handling',
    'distance': 'distance value', 'radius': 'distance value',
    'threshold': 'threshold value', 'tolerance': 'tolerance value',
    'grid_size': 'grid size', 'iterations': 'iteration count',
    'interval': 'interval value', 'z_factor': 'vertical scale factor',
}

FAMILY_PHRASE = {
    'AGGREGATION': 'aggregate features or cell values into summary results',
    'ATTRIBUTE_FILTER': 'select features by attribute condition',
    'BAND_ARITHMETIC': 'compute per-cell arithmetic across raster bands',
    'BAND_SELECT': 'select or reorder raster bands',
    'COLLECTION_MGMT': 'manage layer, field, or dataset organisation',
    'COMPOSITE': 'combine multiple inputs into one composite product',
    'EXPORT_OUTPUT': 'export or save workflow output',
    'GEOMETRY_DEFINE': 'define a geometry or grid construct',
    'NEIGHBORHOOD': 'compute neighbourhood-based raster values',
    'REGIONAL_STATS': 'compute statistics over zones or sampled regions',
    'RESAMPLE_REPROJECT': 'resample or reproject a raster layer',
    'SPATIAL_CLIP': 'restrict data spatially using a geometry or extent',
    'SPATIAL_FILTER': 'select features by spatial relationship',
    'SPATIAL_JOIN': 'join attributes or nearest features across layers',
    'THRESHOLD_LOGIC': 'reclassify values by threshold or membership rule',
    'VECTOR_GEOMETRY': 'transform vector geometries in place',
    'VECTOR_LOAD': 'generate or load a vector source',
    'VECTOR_TO_RASTER': 'convert vector features into raster cells',
}

L1_RE = re.compile(r'\b(native|gdal|grass7?|saga|otb|qgis)\s*:', re.I)
L2_RE = re.compile(r'\b(gdal|grass|saga|otb)\b', re.I)


def roles_of(op: dict) -> tuple:
    b = op.get('layer_b_params') or {}
    roles = []
    for p in b.get('parameters', []):
        role = ROLE_MAP.get(p['name'].lower())
        if role:
            roles.append(role)
    return tuple(sorted(roles))


def sig(op: dict, level: str) -> tuple:
    it = tuple(op.get('input_types_norm') or ())
    ot = tuple(op.get('output_types_norm') or ())
    b = op.get('layer_b_params') or {}
    n_out = len(b.get('outputs', [])) if b else None
    r = roles_of(op)
    if level == 'full':
        return (it, ot, n_out, r)
    if level == '-slots':
        return (it, ot)
    return (r,)  # '-io'


def render_plan(fam: str, op: dict, level: str) -> str:
    phrase = FAMILY_PHRASE.get(fam, fam.lower().replace('_', ' '))
    it = ', '.join(op.get('input_types_norm') or [])
    ot = ', '.join(op.get('output_types_norm') or [])
    r = ', '.join(roles_of(op))
    b = op.get('layer_b_params') or {}
    n_out = len(b.get('outputs', [])) if b else 0
    parts = [f'Perform an operation that will {phrase}.']
    if level != '-io':
        parts.append(f'Input accepts: {it or "unspecified"}. Produces {n_out} output(s) of type: {ot or "unspecified"}.')
    if level != '-slots':
        parts.append(f'Configuration involves: {r or "no additional named configuration"}.')
    parts.append('The step depends on the output of the preceding step.')
    return ' '.join(parts)


def leakage_scan(text: str, rare_names: set) -> dict:
    return {
        'L1_operator_id': bool(L1_RE.search(text)),
        'L2_provider_identity': bool(L2_RE.search(text)),
        'L3_rare_param_name': sorted({n for n in rare_names
                                      if re.search(rf'\b{re.escape(n)}\b', text, re.I)}),
    }


def main() -> None:
    profile = json.loads((BASE / 'route2_training/profile/qgis_operator_capability_profile_v0_4.json')
                         .read_text(encoding='utf-8'))

    # rare param names across the WHOLE catalog (<=2 operators) for L3
    freq = Counter()
    for op in profile.values():
        b = op.get('layer_b_params') or {}
        for p in b.get('parameters', []):
            freq[p['name'].lower()] += 1
    # contract vocabulary allowlist: roles + types + family phrases + boilerplate
    allow = set(ROLE_MAP.values())
    allow |= {'raster', 'vector', 'file', 'literal', 'image', 'tiff', 'table'}
    for v in FAMILY_PHRASE.values():
        allow |= set(re.findall(r'[a-z]+', v))
    allow |= {'perform', 'operation', 'accepts', 'produces', 'unspecified', 'configuration',
              'involves', 'named', 'step', 'depends', 'output', 'preceding', 'additional'}
    rare_names = {n for n, c in freq.items() if c <= 2 and len(n) >= 5 and n.isalpha()
                  and n not in allow}

    groups = defaultdict(list)
    for oid, fam in MAP.items():
        groups[fam].append(oid)

    matrix = json.loads((BASE / 'docs/reports/route2_p0_contract/test111_final_v1/'
                         'grounding_discriminator_matrix_v1.json').read_text(encoding='utf-8'))
    eligible = {f: g for f, g in matrix['groups'].items() if g['class'] == 'G2'}

    instances, level_stats = [], {lv: Counter() for lv in ('full', '-slots', '-io')}
    leak_flags = []
    for fam in sorted(eligible):
        members = sorted(eligible[fam]['candidates'])
        full = [m for m in members if profile.get(m, {}).get('layer_b_params')]
        if len(full) < 2:
            continue
        for target in full:
            t_op = profile[target]
            for level in ('full', '-slots', '-io'):
                s_t = sig(t_op, level)
                matches = [m for m in full if sig(profile[m], level) == s_t]
                level_stats[level]['unique' if len(matches) == 1 else
                                   ('ambiguous' if len(matches) > 1 else 'insufficient')] += 1
                if level != 'full':
                    continue
                cat = 'UG' if len(matches) == 1 else 'AMB'
                text = render_plan(fam, t_op, level)
                leak = leakage_scan(text, rare_names)
                if any([leak['L1_operator_id'], leak['L2_provider_identity'], leak['L3_rare_param_name']]):
                    leak_flags.append({'target': target, 'family': fam, **leak})
                instances.append({
                    'semantic_family': fam, 'target': target,
                    'plan': text, 'level': level,
                    'candidates': full,
                    'supporting_candidates': matches,
                    'unique': len(matches) == 1,
                    'ambiguity_type': cat,
                    'uniquely_groundable': len(matches) == 1,
                    'leakage': leak,
                })

    full_inst = [i for i in instances if i['level'] == 'full']
    n_full = len(full_inst)
    ug = sum(1 for i in full_inst if i['unique'])
    report = {
        'groups_total': matrix['summary']['groups_total'],
        'G0_untestable': matrix['summary']['class_counts'].get('G0', 0),
        'G1_deferred_insufficient_profile': matrix['summary']['class_counts'].get('G1', 0),
        'G2_eligible': matrix['summary']['class_counts'].get('G2', 0),
        'instances_total': n_full,
        'uniquely_groundable_rate_G2': round(ug / n_full, 4) if n_full else None,
        'ambiguous_valid_rate_G2': round((n_full - ug) / n_full, 4) if n_full else None,
        'insufficient_information_rate_G2': 0.0,
        'note_INS': 'zero by construction in closed candidate groups; open-set INS becomes measurable at 6-4',
        'leakage_rate': round(len(leak_flags) / n_full, 4) if n_full else None,
        'leakage_flags': leak_flags,
        'degradation_unique_counts': {lv: dict(level_stats[lv]) for lv in level_stats},
        'per_family': {},
    }
    byfam = defaultdict(lambda: {'UG': 0, 'AMB': 0})
    for i in full_inst:
        byfam[i['semantic_family']]['UG' if i['unique'] else 'AMB'] += 1
    for fam, d in sorted(byfam.items()):
        tot = d['UG'] + d['AMB']
        report['per_family'][fam] = {**d, 'UG_rate': round(d['UG'] / tot, 3)}

    OUT.write_text(json.dumps({'report': report, 'instances': instances},
                              ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=1)[:2600])
    print(f'\nwritten: {OUT}')


if __name__ == '__main__':
    from collections import defaultdict
    main()
