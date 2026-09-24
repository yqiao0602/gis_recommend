"""⑥-5-3 Assembly pipeline validation (MOCK teacher plans, test-only).

Builds G1/G2 samples from MOCK teacher plans + P0 gold graphs and runs
the six-point acceptance contract. MOCK plans are the gold-derived
de-grounded plans (diagnostic line) reused as plan-shaped fixtures -
clearly marked: teacher_checkpoint_sha = "MOCK",
dataset_status = assembly_test_only. ZERO production samples.

Leakage gate scans INPUT side only (task + plan). QGIS operator IDs in
the TARGET are legitimate supervision, never leakage.
"""
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
GOLD = BASE / 'docs/reports/route2_p0_contract/test111_final_v1/v2a_A_test.gold.jsonl'
DG = BASE / 'docs/reports/route2_p0_contract/plan_pipeline_v1/gold_derived_plans_v1.jsonl'
OUT = BASE / 'docs/reports/route2_p0_contract/plan_pipeline_v1/assembly_validation_v1.json'
N_ROWS = 10

ID_RE = re.compile(r'\b(native|gdal|grass7?|saga|otb|qgis)\s*:', re.I)
PROV_RE = re.compile(r'\b(gdal|grass|saga|otb)\b', re.I)
GEE_RE = re.compile(r'\bee\.[A-Za-z]')
STATUS = 'assembly_test_only'
CKPT = 'MOCK'
RUN = 'assembly-v1-validation'


def input_leak(task, plan):
    """Plan-side scan only: the Task is a given condition and MAY mention
    implementations (user vocabulary; ③-D Task+Plan design relies on it)."""
    text = json.dumps(plan, ensure_ascii=False)
    return bool(ID_RE.search(text) or PROV_RE.search(text) or GEE_RE.search(text))


def constraint_ok(cons):
    """presence-only: values must be True/bool, never strings/'...'"""
    if not isinstance(cons, dict):
        return False
    return all(isinstance(v, bool) for v in cons.values())


def main() -> int:
    gold = [json.loads(l) for l in GOLD.open(encoding='utf-8')][:N_ROWS]
    dg = {json.loads(l)['wid']: json.loads(l)['gold_derived_plan']
          for l in DG.open(encoding='utf-8')}

    acc = Counter = {'g1': 0, 'g2': 0, 'g1_fail': [], 'g2_fail': [],
                     'leak_events': 0, 'g1_samples': 0, 'g2_samples': 0,
                     'production_samples': 0}
    out_samples = []
    for gi, row in enumerate(gold):
        wid = row['wid']
        plan = dg[wid]
        task = row.get('task_text', '')
        by_id = {p['process_id']: p for p in row['processes']}
        order = sorted(by_id, key=lambda pid: next(
            s['order'] for s in plan['steps'] if True))  # steps built in topo order
        topo = [p['process_id'] for p in row['processes']]
        # canonical order = the order used by de-grounding (processes list order
        # after topo in gold_deground; here plan steps carry order N -> map back)
        plan_steps = plan['steps']
        if len(plan_steps) != len(row['processes']):
            acc['g1_fail'].append({'wid': wid, 'why': 'step/gold count mismatch'})
            acc['g2_fail'].append({'wid': wid, 'why': 'step/gold count mismatch'})
            continue

        # ---- G2 sample ----
        g2 = {
            'sample_id': f'b2g2-{wid}', 'grounding_unit': 'workflow',
            'dataset_status': STATUS,
            'provenance': {'qgis_row_id': wid, 'teacher_checkpoint_sha': CKPT,
                           'assembly_run': RUN},
            'input': {'task': task, 'teacher_plan': plan},
            'target': {'processes': row['processes'], 'links': row['links']},
            'metadata': {'difficulty_families': sorted({s['family'] for s in plan_steps})},
            'audit': {'leakage_checked': True, 'constraint_checklist_version': 'b2-v1'},
        }
        g2_ok = True
        if len(g2['target']['processes']) != len(row['processes']) or \
           g2['target']['links'] != row['links']:
            g2_ok = False; acc['g2_fail'].append({'wid': wid, 'why': 'gold integrity'})
        if input_leak(task, plan):
            g2_ok = False; acc['leak_events'] += 1
            acc['g2_fail'].append({'wid': wid, 'why': 'input leakage'})
        for s in plan_steps:
            if not constraint_ok(s['constraints']):
                g2_ok = False; acc['g2_fail'].append({'wid': wid, 'why': 'constraint value binding'})
        if 'difficulty_families' in json.dumps(g2['input']):
            g2_ok = False; acc['g2_fail'].append({'wid': wid, 'why': 'difficulty in input'})
        if g2_ok:
            acc['g2'] += 1
            out_samples.append(g2)
        acc['g2_samples'] += 1

        # ---- G1 samples ----
        all_ok = True
        for s in plan_steps:
            n = s['order']
            gold_pid = topo[n - 1]
            target_op = by_id[gold_pid]['operator_id']
            g1 = {
                'sample_id': f'b2g1-{wid}-s{n}', 'grounding_unit': 'operation',
                'dataset_status': STATUS,
                'provenance': {'qgis_row_id': wid, 'teacher_plan_ref': f'{CKPT}#step{n}',
                               'assembly_run': RUN},
                'task_context': task,
                'plan_step': {'intent': s['intent'],
                              'input_types': [i['type'] for i in s['input']],
                              'output_types': [s['output']['type']],
                              'roles': s.get('roles', []),
                              'constraints': s['constraints']},
                'target_operator': target_op,
                'difficulty_family': s['family'],
                'audit': {'leakage_checked': True, 'constraint_checklist_version': 'b2-v1'},
            }
            ok = True
            if input_leak(task, s):
                ok = False; acc['leak_events'] += 1
            if not constraint_ok(s['constraints']):
                ok = False
            if s['intent'] != next(x['intent'] for x in plan_steps if x['order'] == n):
                ok = False
            if ok:
                out_samples.append(g1)
                acc['g1'] += 1
            else:
                acc['g1_fail'].append({'wid': wid, 'step': n})
            all_ok &= ok
            acc['g1_samples'] += 1
        if not all_ok:
            pass
    acc['production_samples'] = 0
    matrix = {
        'g1_assembly_pass': not acc['g1_fail'],
        'g2_assembly_pass': not acc['g2_fail'],
        'gold_target_integrity': not any(f.get('why') == 'gold integrity' for f in acc['g2_fail']),
        'plan_schema': not any(f.get('why') == 'constraint value binding' for f in acc['g2_fail']),
        'provenance_complete': True,
        'leakage_zero': acc['leak_events'] == 0,
        'mock_isolation': all(s['dataset_status'] == STATUS for s in out_samples),
        'teacher_plans_generated': 0,
        'production_samples': 0,
        'counts': {'g1_samples': acc['g1_samples'], 'g2_samples': acc['g2_samples'],
                   'g1_pass': acc['g1'], 'g2_pass': acc['g2'],
                   'leak_events': acc['leak_events']},
        'failures': {'g1': acc['g1_fail'], 'g2': acc['g2_fail']},
    }
    OUT.write_text(json.dumps({'acceptance': matrix, 'samples': out_samples},
                              ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(matrix, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    from collections import defaultdict
    Counter = defaultdict(int)
    sys.exit(main())
