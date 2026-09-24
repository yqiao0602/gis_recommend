"""⑥-5-4 Family constraint-sufficiency analysis (empirical, not asserted).

For each of the five hard families, decompose the candidate ambiguity
structure into three discrimination levels:
  L-typed : input/output type signature
  L-role  : + contract-abstracted slot roles (ROLE_MAP; expressible in
            the ④ Plan Contract)
  L-raw   : + raw parameter names (NOT contract-expressible)

Classification per family:
  LEGIT-AMB : candidates identical even at L-raw (genuinely multi-valid)
  SCHEMA_GAP: candidates separated only at L-raw (contract cannot express)
  otherwise : contract-expressible discriminators exist -> B2 audit item
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'scripts'))
from build_audit_a_v1 import ROLE_MAP  # noqa: E402

PROFILE = BASE / 'route2_training/profile/qgis_operator_capability_profile_v0_4.json'
FAMILIES = ['VECTOR_LOAD', 'EXPORT_OUTPUT', 'GEOMETRY_DEFINE', 'BAND_ARITHMETIC',
            'SPATIAL_JOIN']
KEYWORDS = {
    'VECTOR_LOAD': ('load', 'fromimages', 'sequence', 'pointslayer', 'randompoints',
                    'constant', 'generate'),
    'EXPORT_OUTPUT': ('export', 'save', 'package', 'todrive', 'printcomp', 'report'),
    'GEOMETRY_DEFINE': ('creategrid', 'extenttolayer', 'polygonfromlayer', 'point',
                        'rectangle', 'geometry', 'polygon', 'voronoi'),
    'BAND_ARITHMETIC': ('rastercalculator', 'calculator', 'multiply', 'divide', 'add',
                        'subtract', 'pow', 'float', 'byte', 'int', 'expression',
                        'normalizeddifference', 'rescale', 'where', 'cellstatistics'),
    'SPATIAL_JOIN': ('joinattributesbylocation', 'joinbynearest', 'joinbylocationsummary',
                     'joinattributestable', 'union', 'spatialjoin'),
}


import re as _re


def fam_of(oid, name):
    low = (oid + ' ' + name).lower()
    hits = []
    for f, keys in KEYWORDS.items():
        for kk in keys:
            if len(kk) <= 5:
                if _re.search(rf'{_re.escape(kk)}', low):
                    hits.append(f); break
            elif kk in low:
                hits.append(f); break
    return hits


def main() -> int:
    profile = {k: v for k, v in json.loads(
        PROFILE.read_text(encoding='utf-8')).items() if not k.startswith('_')}
    table = []
    for fam in FAMILIES:
        cands = {}
        for oid, op in profile.items():
            if not op.get('layer_b_params'):
                continue
            f = fam_of(oid, op.get('official_name', ''))
            if fam in f:  # fam among the op's family hits
                b = op.get('layer_b_params') or {}
                cands[oid] = {
                    'typed': (tuple(op.get('input_types_norm') or ()),
                              tuple(op.get('output_types_norm') or ())),
                    'role': tuple(sorted(ROLE_MAP.get(p['name'].lower(), '')
                                         for p in b.get('parameters', []))),
                    'raw': tuple(sorted(p['name'] for p in b.get('parameters', []))),
                }
        # grouping at each level
        g_typed = defaultdict(set)
        for oid, c in cands.items():
            g_typed[c['typed']].add(oid)
        g_role = defaultdict(set)
        for oid, c in cands.items():
            g_role[(c['typed'], c['role'])].add(oid)
        g_raw = defaultdict(set)
        for oid, c in cands.items():
            g_raw[(c['typed'], c['role'], c['raw'])].add(oid)

        typed_groups = len(g_typed)
        max_typed = max(len(v) for v in g_typed.values()) if g_typed else 0
        # residual ambiguity at role level (same typed+role, multiple ops)
        role_resid = {k: v for k, v in g_role.items() if len(v) > 1}
        role_resid_n = sum(len(v) for v in role_resid.values())
        raw_resid = {k: v for k, v in g_raw.items() if len(v) > 1}
        raw_resid_n = sum(len(v) for v in raw_resid.values())
        # LEGIT-AMB: raw-identical (same params) but multi-op
        legit_amb_n = raw_resid_n
        schema_gap_n = role_resid_n - raw_resid_n

        table.append({
            'family': fam, 'n_candidates': len(cands),
            'typed_io_groups': typed_groups, 'max_same_type_group': max_typed,
            'after_contract_roles_groups': len(g_role),
            'role_residual_ambiguous_ops': role_resid_n,
            'raw_only_separated_ops_SCHEMA_GAP': max(schema_gap_n, 0),
            'legit_ambiguous_ops': legit_amb_n,
            'role_residual_examples': [
                {'ops': sorted(v)[:4], 'roles': list(k[1])[:8]}
                for k, v in sorted(role_resid.items(), key=lambda kv: -len(kv[1]))[:3]
            ],
        })

    OUT = BASE / 'docs/reports/route2_p0_contract/plan_pipeline_v1/family_constraint_sufficiency_v1.json'
    OUT.write_text(json.dumps(table, ensure_ascii=False, indent=1), encoding='utf-8')
    for t in table:
        print(f"\n[{t['family']}] candidates={t['n_candidates']} "
              f"typed-groups={t['typed_io_groups']} max-same-type={t['max_same_type_group']}")
        print(f"  after contract roles: {t['after_contract_roles_groups']} groups | "
              f"role-residual ambiguous ops: {t['role_residual_ambiguous_ops']} | "
              f"SCHEMA_GAP-only separated: {t['raw_only_separated_ops_SCHEMA_GAP']} | "
              f"legit-AMB: {t['legit_ambiguous_ops']}")
        for ex in t['role_residual_examples']:
            print(f"    residual group: ops={ex['ops']} roles={ex['roles']}")
    print(f'\nwritten: {OUT}')
    return 0


if __name__ == '__main__':
    main()
