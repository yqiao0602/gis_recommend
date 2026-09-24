"""⑥-3 Tiering v2: F-STRUCT determination replaced by unconsumed-run test.

Owner-approved scope: ONLY the tiering-layer F-STRUCT determination
changes. Converter v1.1, knowledge table v1.2, schema, R1-R4 frozen.

F-STRUCT-01 v2 (three-class mechanization of the human criterion):
  A provision run (consecutive standalone provision steps) is an
  F-STRUCT reject iff ALL of:
    1. run length >= 3
    2. NOT at plan start (initial/auxiliary inputs are legitimate)
    3. no downstream step consumes the run's type (unconsumed)
    4. run type == the plan's primary flow type AND the run dominates
       the plan (>= 50% of steps) - i.e. the run REPLACED the core
       workflow rather than辅助 a surviving one.
  Auxiliary-type runs (scalar/params next to a surviving core) and
  consumed runs are NOT auto-rejected (classes 1-2 of the owner's
  three-way distinction).

Everything else (Tier A/B/C rules, thresholds) identical to v1.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from route2_training.plans.chain_to_plan_v1_1 import convert  # noqa: E402

SRC = '/home/qy/system_redesign/outputs_v2/gee_b1_stage_data_v1/b1_gee_stage_train.jsonl'
AUDITED = '/home/qy/system_redesign/route2_training/plans/pilot_human_audit_48.jsonl'
OUT_POOL = Path(__file__).resolve().parent / 'plan_pool_tiered_v2.jsonl'
OUT_REPORT = Path(__file__).resolve().parent / 'tiering_report_v2.json'


def features(plan, rec):
    steps = plan['steps']
    n = len(steps)
    run = mx = 0
    for s in steps:
        if s.get('provision'):
            run += 1
            mx = max(mx, run)
        else:
            run = 0
    inc = sum(1 for s in steps if not (s.get('roles') or s.get('constraints') or s.get('provision')))
    util = sum(1 for s in steps if s.get('provision') or s['output']['type'] in
               ('scalar', 'text', 'list', 'date', 'parameters'))
    br = sum(1 for s in steps if s.get('branch'))
    return {'prov_run_max': mx, 'flow_breaks': rec['type_flow_breaks'],
            'slot_incomplete_steps': inc, 'utility_ratio': round(util / n, 3) if n else 1.0,
            'branch_ratio': round(br / n, 3) if n else 1.0, 'n_steps': n}


def unconsumed_dominant_run(plan) -> bool:
    """F-STRUCT v2 test: see module docstring."""
    steps = plan['steps']
    n = len(steps)
    primary = Counter(s['output']['type'] for s in steps if not s.get('provision'))
    primary_type = primary.most_common(1)[0][0] if primary else None
    i = 0
    while i < n:
        if steps[i].get('provision'):
            j = i
            while j < n and steps[j].get('provision'):
                j += 1
            run_len = j - i
            if run_len >= 3 and i > 0:  # not at plan start
                run_type = steps[i]['output']['type']
                downstream_ref = any(
                    any(inp.get('type') == run_type for inp in s['input'])
                    for s in steps[j:])
                if not downstream_ref and run_type == primary_type and run_len >= 0.5 * n:
                    return True
            i = j
        else:
            i += 1
    return False


def tier_v2(f: dict, plan: dict) -> str:
    if f['prov_run_max'] >= 3 and unconsumed_dominant_run(plan):
        return 'REJECT'
    if f['flow_breaks'] >= 2:
        return 'REJECT'
    if (f['flow_breaks'] == 0 and f['slot_incomplete_steps'] == 0
            and f['prov_run_max'] <= 1 and f['utility_ratio'] <= 0.5
            and f['branch_ratio'] <= 0.5 and f['n_steps'] >= 3):
        return 'A'
    if (f['flow_breaks'] <= 1 and f['slot_incomplete_steps'] <= 1
            and f['utility_ratio'] <= 0.7 and f['branch_ratio'] <= 0.7):
        return 'B'
    return 'C'


def main() -> int:
    dist = {'REJECT': 0, 'A': 0, 'B': 0, 'C': 0}
    pool_f = OUT_POOL.open('w', encoding='utf-8')
    row_id = 0
    with open(SRC, encoding='utf-8') as f:
        for line in f:
            row_id += 1
            row = json.loads(line)
            plan, rec = convert(row.get('gee_canonical_chain') or '')
            if plan is None:
                continue
            feats = features(plan, rec)
            t = tier_v2(feats, plan)
            dist[t] += 1
            pool_f.write(json.dumps({
                'row_id': row_id, 'tier': t, 'features': feats,
                'instruction': row.get('instruction', '')[:400],
                'plan': plan, 'rendered': None,
            }, ensure_ascii=False) + '\n')
    pool_f.close()

    # gates vs v1 on the audited 47
    aud = [json.loads(l) for l in open(AUDITED, encoding='utf-8')]
    BV = {
        '_p1_batch1.txt': ['偏差', '偏差', '偏差', '失败', '偏差', '偏差', '保真', '保真', '偏差'],
        '_p1_batch2.txt': ['偏差', '偏差', '保真', '偏差', '保真', '偏差', '偏差', '保真', '保真', '保真'],
        '_p1_batch3.txt': ['偏差', '保真', '失败', '偏差', '偏差', '偏差', '保真', '保真', '保真', '保真'],
        '_p1_batch4.txt': ['保真', '偏差', '保真', '偏差', '保真', '偏差', '保真', '保真', '偏差', '保真'],
        '_p1_batch5.txt': ['保真', '偏差', '偏差', '保真', '保真', '偏差', '保真', '保真'],
    }
    human_map = {'保真': 'A', '偏差': 'B', '失败': 'REJECT'}
    aud_by_chain = {}
    for r in aud:
        aud_by_chain[' > '.join(tt.strip() for tt in r['chain'].split('>'))] = r
    agree = {'strict': 0, 'lenient': 0, 'total': 0, 'matrix': {}}
    fstruct_contained = 0
    fstruct_total = 0
    faithful_rejected = 0
    for bf, verd in BV.items():
        chains = [line[7:].strip() for line in
                  open(Path(__file__).resolve().parent / bf, encoding='utf-8')
                  if line.startswith('CHAIN: ')]
        for ch, v in zip(chains, verd):
            match = aud_by_chain.get(ch)
            if match is None:
                continue
            feats = features(match['plan'], {'type_flow_breaks': match['flow_breaks']})
            tt2 = tier_v2(feats, match['plan'])
            want = human_map[v]
            agree['total'] += 1
            key = f'{want}->{tt2}'
            agree['matrix'][key] = agree['matrix'].get(key, 0) + 1
            if tt2 == want:
                agree['strict'] += 1
            if tt2 == want or {want, tt2} == {'A', 'B'}:
                agree['lenient'] += 1
            if want == '失败':
                fstruct_total += 1
                if tt2 == 'REJECT':
                    fstruct_contained += 1
            if want == '保真' and tt2 == 'REJECT':
                faithful_rejected += 1
    agree['strict_rate'] = round(agree['strict'] / max(agree['total'], 1), 3)
    agree['lenient_rate'] = round(agree['lenient'] / max(agree['total'], 1), 3)
    gates = {
        'gate1_fstruct_containment': f'{fstruct_contained}/{fstruct_total}',
        'gate1_pass': fstruct_contained == fstruct_total,
        'gate2_agreement_improved': (agree['strict_rate'], agree['lenient_rate']),
        'gate3_faithful_rejected_count': faithful_rejected,
    }
    report = {'tier_distribution': dist, 'gates_vs_v1': gates,
              'audit48_agreement': agree,
              'rules': 'tiering v2 - unconsumed-dominant F-STRUCT test'}
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({'tier_distribution': dist, 'gates': gates,
                      'agreement': {'strict_rate': agree['strict_rate'],
                                    'lenient_rate': agree['lenient_rate'],
                                    'matrix': agree['matrix']}}, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    main()
