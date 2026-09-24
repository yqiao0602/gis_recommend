"""⑥-2-③ stratified pilot: full-auto P2/P3/P4 + 48-row human-audit sample.

P2 typed-I/O fidelity   : plans with zero unexplained type-flow breaks
P3 slot-role fidelity   : plans where every step carries roles/constraints
P4 de-identification    : leakage scan zero (GEE + QGIS identity)
P1 semantic fidelity    : HUMAN audit on the 48 selected rows (next step)

Selection is seeded and quota-driven: high-risk structures (branch,
modifier block, scalar demotion, flow break, long chains) are
deliberately over-represented per owner ruling, plus length x I/O
strata for coverage.
"""
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from route2_training.plans.chain_to_plan_v1_1 import convert, render_plan, leakage  # noqa: E402

SRC = '/home/qy/system_redesign/outputs_v2/gee_b1_stage_data_v1/b1_gee_stage_train.jsonl'
OUT_P = Path(__file__).resolve().parent
SEED = 20260924


def ntok(chain):
    return len([t for t in re.split(r'\s*(?:->|>)\s*', chain) if t])


def io_class(plan):
    types = set()
    for s in plan['steps']:
        types |= set(s['output']['type'] for s in [s])
        for i in s['input']:
            types.add(i['type'])
        types.add(s['output']['type'])
    has_r = 'raster' in types or 'raster_collection' in types
    has_v = 'vector' in types or 'feature' in types or 'geometry' in types
    has_s = bool(types & {'scalar', 'text', 'list', 'date', 'parameters'})
    if has_r and has_v:
        return 'mixed'
    if has_s and len(types) <= 3:
        return 'scalar-assisted'
    if has_r:
        return 'raster'
    if has_v:
        return 'vector'
    return 'collection'


def main() -> int:
    rng = random.Random(SEED)
    pool = []
    st = {'total': 0, 'ok': 0, 'p2_break_free': 0, 'p3_slot_complete': 0,
          'p4_leak_free': 0}
    with open(SRC, encoding='utf-8') as f:
        for line in f:
            st['total'] += 1
            row = json.loads(line)
            plan, rec = convert(row.get('gee_canonical_chain') or '')
            if plan is None:
                continue
            st['ok'] += 1
            lk = leakage(plan)
            p2 = rec['type_flow_breaks'] == 0
            p3 = all(s.get('roles') or s.get('constraints') or s.get('provision')
                     for s in plan['steps'])
            p4 = not (lk['gee_identity_leak'] or lk['qgis_identity_leak'])
            st['p2_break_free'] += p2
            st['p3_slot_complete'] += p3
            st['p4_leak_free'] += p4
            n = rec['n_tokens']
            pool.append({
                'row_id': st['total'], 'chain': row.get('gee_canonical_chain', ''),
                'instruction': row.get('instruction', '')[:400],
                'plan': plan, 'rendered': render_plan(plan),
                'ntok': n, 'len_class': 'short' if n <= 5 else ('medium' if n <= 12 else 'long'),
                'flow_breaks': rec['type_flow_breaks'],
                'branch': rec['branch_marked'] > 0,
                'mod_block': rec['modifier_blocks'] > 0,
                'scalar_dem': rec['scalar_demoted'] > 0,
                'ctor_att': rec['ctor_attached'] > 0,
                'io_class': io_class(plan), 'p2': p2, 'p3': p3, 'p4': p4,
            })

    N = st['ok']
    auto = {
        'plans_total': N,
        'P2_typed_io_fidelity': round(st['p2_break_free'] / N, 4),
        'P3_slot_role_fidelity': round(st['p3_slot_complete'] / N, 4),
        'P4_deidentification': round(st['p4_leak_free'] / N, 4),
    }
    # --- stratified selection of 48 ---
    def risk_class(p):
        if p['flow_breaks'] > 0:
            return 'flowbreak'
        if p['branch']:
            return 'branch'
        if p['mod_block']:
            return 'modblock'
        if p['scalar_dem']:
            return 'scalar'
        return None

    selected, used = [], set()

    def take(pred, k, tag):
        cand = [p for p in pool if p['row_id'] not in used and pred(p)]
        rng.shuffle(cand)
        for p in cand[:k]:
            used.add(p['row_id'])
            selected.append((tag, p))

    # high-risk quotas (over-represented by design)
    take(lambda p: p['flow_breaks'] > 0, 6, 'RISK-flowbreak')
    take(lambda p: p['branch'] and p['ntok'] > 12, 5, 'RISK-branch-long')
    take(lambda p: p['mod_block'] and p['ntok'] > 10, 4, 'RISK-modblock')
    take(lambda p: p['scalar_dem'] and p['ntok'] > 8, 3, 'RISK-scalardemote')
    # length x io strata
    for lc in ('short', 'medium', 'long'):
        for io in ('raster', 'vector', 'mixed', 'collection', 'scalar-assisted'):
            take(lambda p, lc=lc, io=io: p['len_class'] == lc and p['io_class'] == io,
                 1, f'{lc}-{io}')
    # fill remainder seeded
    take(lambda p: True, 48 - len(selected), 'FILL')

    with (OUT_P / 'pilot_human_audit_48.jsonl').open('w', encoding='utf-8') as f:
        for tag, p in selected:
            f.write(json.dumps({'audit_tag': tag, **p}, ensure_ascii=False) + '\n')

    tag_dist = Counter = {}
    for tag, _ in selected:
        Counter[tag] = Counter.get(tag, 0) + 1
    result = {'auto': auto, 'selected': len(selected), 'tag_distribution': Counter}
    (OUT_P / 'pilot_auto_metrics_v1.json').write_text(
        json.dumps({'auto': auto, 'tag_distribution': Counter}, ensure_ascii=False, indent=1),
        encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
