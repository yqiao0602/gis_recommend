"""chain→Plan deterministic transformation (⑥-2-②).

Deterministic information reorganisation only - no LLM, no guessing.
Fail-closed: any token absent from gee_op_knowledge_v1 marks the row
coverage_failed; such rows never enter the qualified Plan set.

Modifier tokens (ee.Filter.*, ee.Reducer.*) attach as constraints to
the next emitted step (or the previous one at chain end); they never
emit steps. GEE identity vanishes at conversion: rendered plan text
uses intent/types/roles only, validated by leakage scans.
"""

import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))
from route2_training.plans.gee_op_knowledge_v1 import K  # noqa: E402

SPLIT_RE = re.compile(r'\s*(?:->|>)\s*')
GEE_ID_RE = re.compile(r'\bee\.[A-Za-z]')
QGIS_ID_RE = re.compile(r'\b(native|gdal|grass7?|saga|otb|qgis)\s*:', re.I)


def parse_chain(chain: str):
    return [t.strip() for t in SPLIT_RE.split(chain) if t.strip()]


def convert(chain: str) -> dict:
    """Convert one canonical chain -> plan dict + coverage record."""
    rec = {'unknown_ops': [], 'n_tokens': 0, 'n_steps': 0,
           'ctor_count': 0, 'reducer_count': 0, 'filter_count': 0,
           'op_count': 0, 'type_flow_breaks': 0}
    tokens = parse_chain(chain)
    rec['n_tokens'] = len(tokens)
    if not tokens:
        rec['unknown_ops'].append('<empty chain>')
        return None, rec

    steps = []
    pending = []          # constraints waiting for the next op step
    prev_out = None       # typed flow tracking
    prev_was_op = False
    for tok in tokens:
        entry = K.get(tok)
        if entry is None:
            rec['unknown_ops'].append(tok)
            continue
        kind = entry['kind']
        if kind == 'filter':
            rec['filter_count'] += 1
            pending.append({'role': 'filter predicate', 'value': entry['roles'][0]})
            continue
        if kind == 'reducer':
            rec['reducer_count'] += 1
            pending.append({'role': 'statistic', 'value': entry['roles'][0]})
            continue

        constraints = {}
        for c in pending:
            constraints[c['role']] = c['value']
        pending = []

        if kind == 'ctor':
            rec['ctor_count'] += 1
            step = {
                'order': len(steps) + 1,
                'intent': entry['intent'],
                'family': entry['family'],
                'input': [],
                'output': {'type': entry['out']},
                'depends_on': [len(steps)] if steps else [],
                'constraints': constraints,
                'provision': True,
            }
            prev_out = entry['out']
            prev_was_op = False
        else:
            rec['op_count'] += 1
            tin = entry['in']
            if prev_was_op and tin and prev_out and tin != prev_out:
                rec['type_flow_breaks'] += 1
            step = {
                'order': len(steps) + 1,
                'intent': entry['intent'],
                'family': entry['family'],
                'input': [{'role': 'primary input', 'type': tin}] if tin else [],
                'output': {'type': entry['out']},
                'depends_on': [len(steps)] if steps else [],
                'constraints': constraints,
                'roles': entry['roles'],
                'provision': False,
            }
            prev_out = entry['out']
            prev_was_op = True
        steps.append(step)
    rec['n_steps'] = len(steps)

    if rec['unknown_ops'] or not steps:
        return None, rec

    plan = {'steps': steps}
    # final constraint flush onto last step (chain-end modifiers)
    if pending and steps:
        steps[-1]['constraints'].update({c['role']: c['value'] for c in pending})
    return plan, rec


def render_plan(plan: dict) -> str:
    parts = []
    for s in plan['steps']:
        it = ', '.join(i['type'] for i in s['input']) or 'unspecified'
        cons = ''
        if s['constraints']:
            cons = ' Constraints: ' + '; '.join(f'{k} = {v}' for k, v in s['constraints'].items()) + '.'
        dep = 'The step depends on the output of the preceding step.' if s['depends_on'] else 'This is the provisioning first step.'
        parts.append(f"Step {s['order']}: perform an operation that will {s['intent']}. "
                     f"Input accepts: {it}. Produces: {s['output']['type']}.{cons} {dep}")
    return '\n'.join(parts)


def leakage(plan: dict) -> dict:
    text = json.dumps(plan, ensure_ascii=False)
    return {
        'gee_identity_leak': bool(GEE_ID_RE.search(text)),
        'qgis_identity_leak': bool(QGIS_ID_RE.search(text)),
    }


def main() -> int:
    """Self-test on a handful of representative chains."""
    tests = [
        'ee.ImageCollection > ee.ImageCollection.filterDate > ee.ImageCollection.filterBounds > ee.ImageCollection.median > ee.Image.clip',
        'ee.Image > ee.Image.select > ee.Image.normalizedDifference > ee.Image.rename',
        'ee.FeatureCollection > ee.FeatureCollection.filterBounds > ee.Image.reduceRegions > ee.Reducer.mean',
        'ee.ImageCollection > ee.ImageCollection.filter > ee.Filter.lt > ee.ImageCollection.select',
        'ee.Image > ee.Image.select > ee.Classifier.smileRandomForest > ee.Classifier.train > ee.Image.classify',
    ]
    for ch in tests:
        plan, rec = convert(ch)
        status = 'OK ' if plan else 'FAIL'
        print(f'[{status}] {ch[:60]}...')
        if plan:
            print('   steps:', len(plan['steps']),
                  '| flow-breaks:', rec['type_flow_breaks'],
                  '| leak:', leakage(plan))
        else:
            print('   unknown:', rec['unknown_ops'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
