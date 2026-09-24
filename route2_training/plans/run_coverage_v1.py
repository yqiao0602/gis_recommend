"""Server-side runner: convert the full B1 train file, aggregate coverage.

Produces the owner's ⑥-2-② coverage report - coverage_rate and plan
quality kept strictly separate.
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from route2_training.plans.chain_to_plan_v1_1 import convert, leakage  # noqa: E402

SRC = '/home/qy/system_redesign/outputs_v2/gee_b1_stage_data_v1/b1_gee_stage_train.jsonl'
OUT = Path(__file__).resolve().parent / 'coverage_report_v1_1.json'
SAMPLE_OUT = Path(__file__).resolve().parent / 'plan_samples_v1_1.jsonl'

st = Counter()
unknown_ops = Counter()
fail_lens = Counter()
flow_breaks = 0
leak_gee = leak_qgis = 0
ctor_att = ctor_st = mod_blocks = branch_marked = scalar_dem = unknown_host = 0
typed_io_complete = slot_role_complete = total_steps = 0
samples = []
sample_i = 0

with open(SRC, encoding='utf-8') as f:
    for line in f:
        st['total_chains'] += 1
        row = json.loads(line)
        chain = row.get('gee_canonical_chain') or ''
        plan, rec = convert(chain)
        if plan is None:
            st['plan_failed'] += 1
            for u in rec['unknown_ops']:
                unknown_ops[u] += 1
            fail_lens[min(rec['n_tokens'], 40)] += 1
            continue
        st['plan_success'] += 1
        st['total_tokens'] += rec['n_tokens']
        st['ctor_count'] += rec['ctor_count']
        st['reducer_count'] += rec['reducer_count']
        st['filter_count'] += rec['filter_count']
        st['op_count'] += rec['op_count']
        for u in rec['unknown_ops']:
            unknown_ops[u] += 1
        flow_breaks += rec['type_flow_breaks']
        ctor_att += rec['ctor_attached']; ctor_st += rec['ctor_standalone']
        mod_blocks += rec['modifier_blocks']; branch_marked += rec['branch_marked']
        scalar_dem += rec['scalar_demoted']
        unknown_host += 1 if rec.get('structural_fail') == 'UNKNOWN_HOST' else 0
        lk = leakage(plan)
        leak_gee += lk['gee_identity_leak']
        leak_qgis += lk['qgis_identity_leak']
        for s in plan['steps']:
            total_steps += 1
            io_ok = bool(s['output']['type']) and (not s['input'] or all(i['type'] for i in s['input']))
            typed_io_complete += io_ok
            slot_role_complete += bool(s.get('roles') or s['constraints'] or s['provision'])
        if sample_i < 400 and st['plan_success'] % 250 == 1:
            samples.append({'row_id': st['total_chains'],
                            'instruction': row.get('instruction', '')[:300],
                            'chain': chain, 'plan': plan,
                            'rendered': None})
            sample_i += 1

total = st['total_chains']
known_tokens = st['total_tokens'] and (st['op_count'] + st['ctor_count'] + st['filter_count'] + st['reducer_count'])
report = {
    'total_chains': total,
    'plan_success': st['plan_success'],
    'plan_failed': st['plan_failed'],
    'coverage_rate_chain': round(st['plan_success'] / total, 4),
    'total_known_tokens': known_tokens,
    'unknown_token_events': sum(unknown_ops.values()),
    'op_coverage_rate_token': None,
    'ctor_count': st['ctor_count'], 'reducer_count': st['reducer_count'],
    'filter_count': st['filter_count'], 'op_count': st['op_count'],
    'total_steps': total_steps,
    'typed_io_complete_rate': round(typed_io_complete / total_steps, 4) if total_steps else None,
    'slot_role_complete_rate': round(slot_role_complete / total_steps, 4) if total_steps else None,
    'type_flow_breaks': flow_breaks,
    'ctor_attached': ctor_att, 'ctor_standalone': ctor_st,
    'modifier_blocks': mod_blocks, 'branch_marked_steps': branch_marked,
    'scalar_demoted': scalar_dem, 'unknown_host_failures': unknown_host,
    'gee_identity_leak_chains': leak_gee,
    'qgis_identity_leak_chains': leak_qgis,
    'top_unknown_ops': unknown_ops.most_common(30),
    'failure_by_chain_len_bucket': {str(k): v for k, v in sorted(fail_lens.items())},
    'note': 'coverage_rate != plan quality (owner ruling); separate metrics',
}
report['op_coverage_rate_token'] = round(known_tokens / (known_tokens + sum(unknown_ops.values())), 4) if (known_tokens + sum(unknown_ops.values())) else None
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
SAMPLE_OUT.write_text('\n'.join(json.dumps(s, ensure_ascii=False) for s in samples), encoding='utf-8')
print(json.dumps({k: v for k, v in report.items() if k not in ('top_unknown_ops',)}, ensure_ascii=False, indent=1))
print('top unknown:', report['top_unknown_ops'][:10])
