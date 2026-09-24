"""Build the Grounding Discriminator Matrix + A0 separability audit (v1).

⑥-1 steps 1-4: semantic-group cleaning (G0/G1/G2), per-group discriminator
matrix, and profile-level (A0) separability. Pure data work on the oracle
mapping (148 test operators -> 21 semantic families) and the Operator
Capability Profile v0.3. No plans, no models, no training.

Group classes (owner ruling):
  G0: single concrete implementation        -> discrimination untestable
  G1: >=2 implementations, insufficient profile -> deferred, no verdict
  G2: >=2 implementations, separable on legit attributes -> Audit-A eligible

Legit discriminator attributes (interface-contract classes ONLY; provider
identity is deliberately excluded - it is a leakage dimension, not a
legitimate discriminator):
  input_types_norm, output_types_norm, parameter name set, required count,
  output slots.
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'scripts'))
from build_route2_semantic_oracle_v1 import MAP  # noqa: E402  (the 148-op mapping)

PROFILE = BASE / 'route2_training/profile/qgis_operator_capability_profile_v0_3.json'
OUT = BASE / 'docs/reports/route2_p0_contract/test111_final_v1/grounding_discriminator_matrix_v1.json'

# structured attributes comparable at A0 (profile level)
def attrs(op: dict) -> dict:
    b = op.get('layer_b_params') or {}
    return {
        'input_types': tuple(op.get('input_types_norm') or ()),
        'output_types': tuple(op.get('output_types_norm') or ()),
        'param_names': frozenset(p['name'] for p in b.get('parameters', [])) if b else None,
        'n_required': b.get('n_required') if b else None,
        'output_slots': tuple(o['name'] for o in b.get('outputs', [])) if b else None,
    }


def diffs(a: dict, b: dict) -> list:
    """Legitimate attributes on which two candidates differ."""
    d = []
    if a['input_types'] != b['input_types']:
        d.append('input_types')
    if a['output_types'] != b['output_types']:
        d.append('output_types')
    if a['param_names'] is not None and b['param_names'] is not None and a['param_names'] != b['param_names']:
        d.append('parameter_set')
    if a['n_required'] is not None and b['n_required'] is not None and a['n_required'] != b['n_required']:
        d.append('required_param_count')
    if a['output_slots'] is not None and b['output_slots'] is not None and a['output_slots'] != b['output_slots']:
        d.append('output_slots')
    return d


def main() -> None:
    profile = json.loads(PROFILE.read_text(encoding='utf-8'))
    groups = defaultdict(list)
    for oid, fam in MAP.items():
        groups[fam].append(oid)

    report_groups = {}
    cls = Counter()
    for fam in sorted(groups):
        members = sorted(groups[fam])
        infos = {}
        for m in members:
            op = profile.get(m)
            infos[m] = attrs(op) if op else None
        full = [m for m in members if infos[m] and infos[m]['param_names'] is not None]
        if len(members) < 2:
            c = 'G0'
        elif len(full) < 2:
            c = 'G1'
        else:
            c = None  # decided by pairwise separability below
        pair_records = []
        if c is None:
            separable_pairs = 0
            total_pairs = 0
            for i, a in enumerate(full):
                for b in full[i + 1:]:
                    total_pairs += 1
                    d = diffs(infos[a], infos[b])
                    if d:
                        separable_pairs += 1
                    pair_records.append({'a': a, 'b': b, 'differing_attributes': d})
            # eligible iff EVERY fully-profiled pair is separable (A0)
            c = 'G2' if total_pairs > 0 and separable_pairs == total_pairs else 'G1'
        else:
            pair_records = []
        cls[c] += 1
        # per-family discriminator attributes (union over separable pairs)
        fam_disc = sorted({d for pr in pair_records for d in pr['differing_attributes']})
        report_groups[fam] = {
            'semantic_family': fam,
            'candidates': members,
            'n_candidates': len(members),
            'n_full_profile': len(full),
            'class': c,
            'input_type': sorted({t for m in members if infos[m] for t in infos[m]['input_types']}),
            'output_type': sorted({t for m in members if infos[m] for t in infos[m]['output_types']}),
            'discriminators': fam_disc,
            'pairwise': pair_records,
            'audit_status': 'eligible' if c == 'G2' else ('deferred_insufficient_profile' if c == 'G1' else 'untestable_single_impl'),
        }

    summary = {
        'groups_total': len(report_groups),
        'class_counts': dict(cls),
        'eligible_G2': cls['G2'],
        'note': 'G1 (insufficient profile) is NOT an interface failure; deferred until profile coverage improves. G0 single-implementation families cannot test discrimination.',
    }
    out = {'summary': summary, 'groups': report_groups}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f'\nwritten: {OUT}')
    for fam, g in report_groups.items():
        print(f"  [{g['class']}] {fam}: {g['n_candidates']} candidates, "
              f"discriminators={g['discriminators'] or '-'}")


if __name__ == '__main__':
    main()
