"""⑥-3 Plan Quality Tiering - full run with pre-registered rules (v1).

Converts the full B1 file, extracts per-plan features, assigns
tiers per TIERING_RULES_v1.md (frozen thresholds), and emits the tiered
pool + report. Also emits features for the 48 human-audited rows for
post-hoc agreement validation.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from route2_training.plans.chain_to_plan_v1_1 import convert, leakage  # noqa: E402

SRC = '/home/qy/system_redesign/outputs_v2/gee_b1_stage_data_v1/b1_gee_stage_train.jsonl'
AUDITED = '/home/qy/system_redesign/route2_training/plans/pilot_human_audit_48.jsonl'
OUT_POOL = Path(__file__).resolve().parent / 'plan_pool_tiered_v1.jsonl'
OUT_REPORT = Path(__file__).resolve().parent / 'tiering_report_v1.json'
OUT_AUDIT_FEATURES = Path(__file__).resolve().parent / 'audit48_tier_features.json'


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


def tier(f: dict) -> str:
    if f['prov_run_max'] >= 3 or f['flow_breaks'] >= 2:
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
    reject_reasons = {'prov_run': 0, 'flow_breaks': 0}
    pool_f = OUT_POOL.open('w', encoding='utf-8')
    row_id = 0
    audited_ids = set()
    aud_rows = [json.loads(l) for l in open(AUDITED, encoding='utf-8')]
    aud_chains = {' > '.join(t.strip() for t in r['chain'].split('>')): r['instruction'][:80] for r in aud_rows}

    with open(SRC, encoding='utf-8') as f:
        for line in f:
            row_id += 1
            row = json.loads(line)
            chain = row.get('gee_canonical_chain') or ''
            plan, rec = convert(chain)
            if plan is None:
                continue
            feats = features(plan, rec)
            t = tier(feats)
            dist[t] += 1
            if t == 'REJECT':
                if feats['prov_run_max'] >= 3:
                    reject_reasons['prov_run'] += 1
                else:
                    reject_reasons['flow_breaks'] += 1
            ck = ' > '.join(tt.strip() for tt in chain.split('>'))
            is_audited = ck in aud_chains
            if is_audited:
                audited_ids.add(row_id)
            pool_f.write(json.dumps({
                'row_id': row_id, 'tier': t, 'features': feats,
                'instruction': row.get('instruction', '')[:400],
                'plan': plan, 'rendered': None,
            }, ensure_ascii=False) + '\n')
    pool_f.close()

    # agreement check: batch presentation files x per-batch verdict lists
    # (owner-verified verdicts in presentation order; P1a basis after the
    # batch-3 fragment reclassification)
    BV = {
        '_p1_batch1.txt': ['偏差', '偏差', '偏差', '失败', '偏差', '偏差', '保真', '保真', '偏差'],
        '_p1_batch2.txt': ['偏差', '偏差', '保真', '偏差', '保真', '偏差', '偏差', '保真', '保真', '保真'],
        '_p1_batch3.txt': ['偏差', '保真', '失败', '偏差', '偏差', '偏差', '保真', '保真', '保真', '保真'],
        '_p1_batch4.txt': ['保真', '偏差', '保真', '偏差', '保真', '偏差', '保真', '保真', '偏差', '保真'],
        '_p1_batch5.txt': ['保真', '偏差', '偏差', '保真', '保真', '偏差', '保真', '保真'],
    }
    aud = [json.loads(l) for l in open(AUDITED, encoding='utf-8')]
    human_map = {'保真': 'A', '偏差': 'B', '失败': 'REJECT'}
    agree = {'agree_strict': 0, 'agree_lenient': 0, 'total': 0, 'matrix': {}}
    aud_by_chain = {}
    for r in aud:
        aud_by_chain[' > '.join(tt.strip() for tt in r['chain'].split('>'))] = r
    for bf, verd in BV.items():
        chains = [line[7:].strip() for line in
                  open(Path(__file__).resolve().parent / bf, encoding='utf-8')
                  if line.startswith('CHAIN: ')]
        if len(chains) != len(verd):
            print(f'WARN {bf}: {len(chains)} chains vs {len(verd)} verdicts')
        for ch, v in zip(chains, verd):
            match = aud_by_chain.get(ch)
            if match is None:
                continue
            feats = features(match['plan'], {'type_flow_breaks': match['flow_breaks']})
            tt2 = tier(feats)
            want = human_map[v]
            agree['total'] += 1
            key = f'{want}->{tt2}'
            agree['matrix'][key] = agree['matrix'].get(key, 0) + 1
            if tt2 == want:
                agree['agree_strict'] += 1
            if tt2 == want or {want, tt2} == {'A', 'B'}:
                agree['agree_lenient'] += 1
    agree['strict_rate'] = round(agree['agree_strict'] / max(agree['total'], 1), 3)
    agree['lenient_rate'] = round(agree['agree_lenient'] / max(agree['total'], 1), 3)

    report = {'tier_distribution': dist, 'reject_reasons': reject_reasons,
              'audit48_agreement': agree,
              'rules': 'TIERING_RULES_v1.md (pre-registered)'}
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    OUT_AUDIT_FEATURES.write_text(json.dumps(
        [features(r['plan'], {'type_flow_breaks': r['flow_breaks']}) for r in aud],
        ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    main()
