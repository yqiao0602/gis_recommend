"""chain→Plan v1.1 (⑥-2-② second iteration).

Structural fixes from the 16-sample sanity check, owner-approved:
  R1 ctor consumption attachment: a constructor whose output is consumed
     by the next operation becomes that operation's provisioned input
     slot, NOT a standalone step. Only genuine workflow-start provisions
     and unconsumed (branch) provisions remain standalone.
  R2 modifier-run guard: consecutive modifier runs attach as ONE
     constraint block to the next op (host confirmed) or, if the run is
     followed by a ctor/chain-end, to the LAST confirmed op host. If no
     op host exists at all -> UNKNOWN_HOST -> row fails closed.
  R3 branch marking: a mid-chain provision whose type differs from the
     current flow marks the consuming step branch=true. Linear order is
     kept; the plan must not pretend a recovered DAG.
  R4 scalar-utility demotion: scalar/text-producing utility ops become
     pending parameter constraints when consumed within the chain; they
     stay standalone only when nothing consumes them.

Hard discipline: UNKNOWN_HOST and unknown tokens fail closed. No fuzzy
host guessing.
"""

import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))
from route2_training.plans.gee_op_knowledge_v1_2 import K  # noqa: E402

SPLIT_RE = re.compile(r'\s*(?:->|>)\s*')
GEE_ID_RE = re.compile(r'\bee\.[A-Za-z]')
QGIS_ID_RE = re.compile(r'\b(native|gdal|grass7?|saga|otb|qgis)\s*:', re.I)
PARAM_TYPES = {'scalar', 'text', 'list', 'date', 'parameters'}
MODIFIER_RUN_MAX = 3


def parse_chain(chain: str):
    return [t.strip() for t in SPLIT_RE.split(chain) if t.strip()]


def type_matches(prev_out, tin) -> bool:
    """Flow type check: prev_out must be acceptable as input tin.
    tin may be a single type (str) or a tuple of acceptable types."""
    if tin is None or prev_out is None:
        return False
    if isinstance(tin, (tuple, list)):
        return prev_out in tin
    return prev_out == tin


def convert(chain: str) -> tuple:
    rec = {'unknown_ops': [], 'n_tokens': 0, 'n_steps': 0,
           'ctor_count': 0, 'reducer_count': 0, 'filter_count': 0,
           'op_count': 0, 'type_flow_breaks': 0,
           'ctor_attached': 0, 'ctor_standalone': 0,
           'modifier_blocks': 0, 'unknown_host_fail': 0,
           'branch_marked': 0, 'scalar_demoted': 0,
           'structural_fail': None}
    tokens = parse_chain(chain)
    rec['n_tokens'] = len(tokens)
    if not tokens:
        rec['structural_fail'] = 'empty_chain'
        return None, rec

    steps = []
    mods = []            # pending modifier constraints (deterministic host)
    pend_prov = None     # pending provision {type, intent} awaiting consumer
    flow_type = None     # current flow output type

    def flush_mods_to(host_step):
        if mods and host_step is not None:
            host_step['constraints'].update({f'modifier.{c["role"]}': c['value'] for c in mods})
            rec['modifier_blocks'] += 1
            mods.clear()

    def flush_pending_provision_standalone():
        nonlocal pend_prov
        if pend_prov is not None:
            steps.append({
                'order': len(steps) + 1, 'intent': pend_prov['intent'],
                'family': 'COLLECTION_MGMT', 'input': [],
                'output': {'type': pend_prov['type']},
                'depends_on': [len(steps)] if steps else [],
                'constraints': {}, 'provision': True,
                'branch': bool(steps)})
            if steps and len(steps) > 1:
                rec['branch_marked'] += 1
            rec['ctor_standalone'] += 1
            pend_prov = None

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        entry = K.get(tok)
        if entry is None:
            rec['unknown_ops'].append(tok)
            i += 1
            continue
        kind = entry['kind']

        if kind == 'filter':
            rec['filter_count'] += 1
            mods.append({'role': 'filter predicate', 'value': entry['roles'][0]})
            i += 1
            continue
        if kind == 'reducer':
            rec['reducer_count'] += 1
            mods.append({'role': 'statistic', 'value': entry['roles'][0]})
            i += 1
            continue

        if kind == 'ctor':
            rec['ctor_count'] += 1
            # R2 guard: long modifier run followed by ctor -> no valid future host
            if len(mods) >= MODIFIER_RUN_MAX:
                last_op = next((s for s in reversed(steps) if not s['provision']), None)
                if last_op is None:
                    rec['structural_fail'] = 'UNKNOWN_HOST'
                    return None, rec
                flush_mods_to(last_op)
            # R4-style: if a pending provision already waits, flush it standalone (parallel source)
            flush_pending_provision_standalone()
            if not steps:
                # genuine workflow start: standalone provision step
                steps.append({
                    'order': 1, 'intent': entry['intent'], 'family': entry['family'],
                    'input': [], 'output': {'type': entry['out']},
                    'depends_on': [], 'constraints': {}, 'provision': True})
                rec['ctor_standalone'] += 1
                flow_type = entry['out']
            else:
                pend_prov = {'type': entry['out'], 'intent': entry['intent']}
            i += 1
            continue

        # normal operation step
        rec['op_count'] += 1
        tin = entry['in']
        inputs = []
        branch = False
        if pend_prov is not None:
            if tin and (pend_prov['type'] == tin or (isinstance(tin, (tuple, list)) and pend_prov['type'] in tin)):
                inputs.append({'role': entry['roles'][0] if entry['roles'] else 'primary input',
                               'type': tin, 'provisioned': True})
                rec['ctor_attached'] += 1
            else:
                inputs.append({'role': 'provisioned input (branch source)',
                               'type': pend_prov['type'], 'provisioned': True})
                branch = True
                rec['branch_marked'] += 1
            pend_prov = None
        elif tin and flow_type and not type_matches(flow_type, tin):
            rec['type_flow_breaks'] += 1
            if steps and steps[-1].get('provision'):
                rec.setdefault('break_ctor_induced', 0)
                rec['break_ctor_induced'] += 1
            else:
                rec.setdefault('break_genuine_mismatch', 0)
                rec['break_genuine_mismatch'] += 1
        constraints = {c['role']: c['value'] for c in mods}
        if mods:
            rec['modifier_blocks'] += 1
        mods = []
        if tin is None and not branch and steps and all(s['provision'] for s in steps):
            # utility op consuming provisions implicitly
            pass
        step = {
            'order': len(steps) + 1, 'intent': entry['intent'],
            'family': entry['family'],
            'input': inputs or ([{'role': 'primary input', 'type': tin}] if tin else []),
            'output': {'type': entry['out']},
            'depends_on': [len(steps)] if steps else [],
            'constraints': constraints, 'roles': entry['roles'],
            'provision': False,
        }
        if branch:
            step['branch'] = True
        steps.append(step)
        flow_type = entry['out'] if entry['out'] in PARAM_TYPES or entry['out'] else entry['out']
        # R4: scalar/text utility outputs become pending parameter constraints
        if entry['out'] in PARAM_TYPES and entry['family'] in ('BAND_ARITHMETIC', 'COLLECTION_MGMT', 'TEMPORAL_FILTER'):
            pend_prov = {'type': entry['out'], 'intent': entry['intent']}
            rec['scalar_demoted'] += 1
        i += 1

    # end of chain
    if mods:
        last_op = next((s for s in reversed(steps) if not s['provision']), None)
        if last_op is None:
            rec['structural_fail'] = 'UNKNOWN_HOST'
            return None, rec
        flush_mods_to(last_op)
    flush_pending_provision_standalone()
    if rec['unknown_ops'] or not steps:
        if rec['unknown_ops']:
            rec['structural_fail'] = 'unknown_tokens'
        return None, rec
    rec['n_steps'] = len(steps)
    return {'steps': steps}, rec


def render_plan(plan: dict) -> str:
    parts = []
    for s in plan['steps']:
        it = ', '.join((i['role'] + ' (' + i['type'] + ')') if i.get('provisioned')
                       else i['type'] for i in s['input']) or 'unspecified'
        cons = ''
        if s['constraints']:
            cons = ' Constraints: ' + '; '.join(f'{k} = {v}' for k, v in s['constraints'].items()) + '.'
        br = ' [branch in the source workflow]' if s.get('branch') else ''
        dep = ('The step depends on the output of the preceding step.' if s['depends_on']
               else 'This is the provisioning first step.')
        parts.append(f"Step {s['order']}: perform an operation that will {s['intent']}. "
                     f"Input accepts: {it}. Produces: {s['output']['type']}.{cons} {dep}{br}")
    return '\n'.join(parts)


def leakage(plan: dict) -> dict:
    text = json.dumps(plan, ensure_ascii=False)
    return {'gee_identity_leak': bool(GEE_ID_RE.search(text)),
            'qgis_identity_leak': bool(QGIS_ID_RE.search(text))}


def main() -> int:
    tests = [
        'ee.ImageCollection > ee.ImageCollection.filterDate > ee.ImageCollection.filterBounds > ee.ImageCollection.median > ee.Image.clip',
        'ee.ImageCollection > ee.ImageCollection.select > ee.Filter.date > ee.ImageCollection.filter > ee.FeatureCollection > ee.Classifier.smileRandomForest',
        'ee.Filter.lt > ee.Filter.gte > ee.Classifier.smileRandomForest',
        'ee.Image > ee.Image.select > ee.Classifier.smileRandomForest > ee.Classifier.train > ee.Image.classify',
        'ee.Number > ee.Number.multiply > ee.Image.pixelArea > ee.Image.multiply',
    ]
    for ch in tests:
        plan, rec = convert(ch)
        tag = 'OK  ' if plan else 'FAIL'
        print(f'[{tag}] {ch[:70]}')
        if plan is None:
            print('   fail:', rec['structural_fail'], rec['unknown_ops'][:3])
            continue
        for s in plan['steps']:
            cons = s['constraints'] or {}
            prov = [i for i in s['input'] if i.get('provisioned')]
            extra = ''
            if prov:
                extra += f" [consumes provisioned {prov[0]['type']}]"
            if s.get('branch'):
                extra += ' [BRANCH]'
            if cons:
                extra += f' constraints={cons}'
            print(f"   Step {s['order']}: {s['intent']} | {s['output']['type']}{extra}")
        print(f'   attached={rec["ctor_attached"]} standalone={rec["ctor_standalone"]} '
              f'demoted={rec["scalar_demoted"]} blocks={rec["modifier_blocks"]} '
              f'breaks={rec["type_flow_breaks"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
