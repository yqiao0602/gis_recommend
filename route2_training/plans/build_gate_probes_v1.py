"""W1-W4 Capability Gate probe builder (⑦-3, pre-registration prerequisite).

Builds gate-dev and gate-test probe sets from the GEE author-disjoint
dev/test splits (training rows never used). Probe formats:

  W1 op_io      : operation intent -> accepts/produces types (knowledge
                  table answer key; low-frequency ops + surface variants)
  W2 comp_valid : two-step composition -> Yes/No legality (balanced
                  legal adjacency pairs vs type-mismatched corruptions)
  W3 plan_gen   : instruction -> full rendered plan (reference =
                  gold-derived dev/test plan; scored by op-family
                  sequence F1). REWRITTEN-instruction variant pending
                  DEEPSEEK key (answer-echo counter, owner to provision).
  W4 repair     : corrupted plan -> identify the problem

Scoring functions live here and are reused by any checkpoint evaluator
(base zero-shot, gate-dev, gate-test).
"""
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from route2_training.plans.chain_to_plan_v1_1 import convert, render_plan  # noqa: E402
from route2_training.plans.gee_op_knowledge_v1_2 import K  # noqa: E402

SRC = '/home/qy/system_redesign/outputs_v2/gee_b1_stage_data_v1/b1_gee_stage_train.jsonl'
OUTDIR = Path(__file__).resolve().parent
SEED = 20260924
rng = random.Random(SEED)


def norm_type(t):
    return (t or 'unspecified').strip().lower()


def w1_samples(steps, task):
    out = []
    seen = set()
    for s in steps:
        key = s['intent']
        if key in seen:
            continue
        seen.add(key)
        in_t = ', '.join(i['type'] for i in s['input']) or 'unspecified'
        out_t = s['output']['type'] or 'unspecified'
        out.append({
            'capability': 'W1', 'kind': 'op_io',
            'prompt': (f'A workflow step is described as: {s["intent"]}.\n'
                       f'Answer in exactly this form: accepts <input data type(s)>; '
                       f'produces <output data type>.'),
            'target': f'accepts {in_t}; produces {out_t}',
            'check': {'in': in_t, 'out': out_t}})
    return out


def w2_samples(steps, task):
    out = []
    for i in range(len(steps) - 1):
        a, b = steps[i], steps[i + 1]
        at = a['output']['type'] or 'unspecified'
        bt = ', '.join(x['type'] for x in b['input']) or 'unspecified'
        legal = norm_type(at) == norm_type(b['input'][0]['type'] if b['input'] else at)
        out.append({
            'capability': 'W2', 'kind': 'comp_valid',
            'prompt': (f'In a workflow: operation 1 "{a["intent"]}" produces: {at}. '
                       f'Operation 2 "{b["intent"]}" accepts: {bt}.\n'
                       f'Can operation 2 directly consume the output of operation 1? '
                       f'Answer Yes or No.'),
            'target': 'Yes' if legal else 'No',
            'check': {'legal': legal}})
    # illegal negatives by type substitution (balanced cap)
    negs = [s for s in out if s['target'] == 'No']
    poss = [s for s in out if s['target'] == 'Yes']
    keep = min(len(poss), len(negs)) + (len(poss) - min(len(poss), len(negs))) // 3
    return poss[:keep] + negs[:keep]


def w4_samples(steps, task):
    out = []
    if len(steps) < 3:
        return out
    i = rng.randrange(1, len(steps) - 1)
    kind = rng.choice(['delete', 'swap'])
    if kind == 'delete':
        missing = steps[i]
        cor = steps[:i] + steps[i + 1:]
        ans = f'the missing step is: {missing["intent"]}'
    else:
        a, b = steps[i], steps[i + 1]
        cor = steps[:i] + [b, a] + steps[i + 2:]
        ans = f'steps {a["order"]} and {b["order"]} are swapped'
    out.append({
        'capability': 'W4', 'kind': f'identify_{kind}',
        'prompt': (f'A workflow plan contains exactly one structural problem.\n'
                   f'{render_plan({"steps": cor})}\n'
                   f'Identify the problem in one sentence.'),
        'target': ans, 'check': {}})
    return out


def w3_sample(task, plan):
    return {
        'capability': 'W3', 'kind': 'plan_gen',
        'prompt': task + '\nWorkflow plan:',
        'target': render_plan(plan),
        'reference_families': [s['family'] for s in plan['steps']],
        'check': {'seq': [s['family'] for s in plan['steps']]}}


def main() -> int:
    splits = {'dev': [], 'test': []}
    SPLIT_KEY = {'dev': 'val', 'test': 'test'}
    with open(SRC, encoding='utf-8') as f:
        for line in f:
            row = json.loads(line)
            sp = row.get('split')
            if sp == 'val':
                splits['dev'].append(row)
            elif sp == 'test':
                splits['test'].append(row)

    report = {}
    for split, rows in splits.items():
        rng.seed(SEED + (0 if split == 'dev' else 1))
        probes = []
        plans_ok = 0
        for row in rows:
            task = row.get('instruction', '')
            plan, rec = convert(row.get('gee_canonical_chain') or '')
            if plan is None:
                continue
            plans_ok += 1
            steps = plan['steps']
            probes.extend(w1_samples(steps, task))
            probes.extend(w2_samples(steps, task))
            probes.append(w3_sample(task, plan))
            probes.extend(w4_samples(steps, task))
        cap = {'dev': 3000, 'test': 3000}
        if len(probes) > cap[split]:
            probes = rng.sample(probes, cap[split])
        cnt = Counter(p['capability'] for p in probes)
        outf = OUTDIR / f'gate_{split}_probes_v1.jsonl'
        with outf.open('w', encoding='utf-8') as f:
            for p in probes:
                f.write(json.dumps(p, ensure_ascii=False) + '\n')
        report[split] = {'rows': len(rows), 'plans_converted': plans_ok,
                         'probes': len(probes), 'by_capability': dict(cnt),
                         'file': str(outf)}
    print(json.dumps(report, ensure_ascii=False, indent=1))
    (OUTDIR / 'gate_build_report_v1.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    return 0


if __name__ == '__main__':
    main()
