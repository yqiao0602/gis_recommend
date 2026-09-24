"""Read-only deterministic provenance audit for Stage-1 dataset v1.

Replays the frozen builder against the Tier A/B row-id pool, then compares
expected and actual serialized samples as multisets. Never writes/modifies
the training dataset.
"""
import collections
import hashlib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from route2_training.plans.chain_to_plan_v1_1 import convert, render_plan
from route2_training.plans.stage1_dataset_v1 import corrupted_copy, SEED, MAX_PLAN_CHARS

SRC = '/home/qy/system_redesign/outputs_v2/gee_b1_stage_data_v1/b1_gee_stage_train.jsonl'
TIER = '/home/qy/system_redesign/route2_training/plans/plan_pool_tiered_v2.jsonl'
ACTUAL = '/home/qy/system_redesign/route2_training/plans/stage1_train_v1.jsonl'


def digest(row):
    raw = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def main():
    allowed = {r['row_id'] for line in open(TIER, encoding='utf-8')
               if (r := json.loads(line))['tier'] in ('A', 'B')}
    rng = random.Random(SEED)
    core, completion, recon, w4 = [], [], [], []
    stats = collections.Counter()
    for row_id, line in enumerate(open(SRC, encoding='utf-8'), 1):
        row = json.loads(line)
        if row.get('split') != 'train' or row_id not in allowed:
            continue
        stats['tier_ab_train_rows'] += 1
        plan, rec = convert(row.get('gee_canonical_chain') or '')
        if plan is None:
            stats['tier_ab_convert_fail'] += 1
            continue
        task = row.get('instruction', '')
        if not task or len(plan['steps']) < 2:
            stats['ineligible_task_or_steps'] += 1
            continue
        target = render_plan(plan)[:MAX_PLAN_CHARS]
        core.append({'cat': 'core', 'prompt': task + '\nWorkflow plan:', 'target': target})
        steps = plan['steps']
        if len(steps) >= 3:
            k = rng.randrange(2, len(steps))
            prefix = render_plan({'steps': steps[:k]})[:MAX_PLAN_CHARS]
            completion.append({'cat': 'completion', 'prompt': (task + '\nWorkflow plan (partial):\n' + prefix + '\nWhat is the intent of the next operation step? Answer with the operation description only.'), 'target': steps[k]['intent']})
            i = rng.randrange(1, len(steps) - 1)
            swapped = steps[:i] + [steps[i + 1], steps[i]] + steps[i + 2:]
            recon.append({'cat': 'reconstruction', 'prompt': (task + '\nThe following workflow plan has two adjacent steps in the wrong order. Rewrite the full plan in the correct order.\n' + render_plan({'steps': swapped})[:MAX_PLAN_CHARS]), 'target': render_plan(plan)[:MAX_PLAN_CHARS]})
        corrupted, answer = corrupted_copy(steps)
        w4.append({'cat': 'w4', 'prompt': (task + '\nThe following workflow plan contains exactly one structural problem (a removed step, a swapped pair, or an inserted wrong operation). Identify the problem.\n' + render_plan({'steps': corrupted})[:MAX_PLAN_CHARS]), 'target': answer})
    rng.shuffle(core); rng.shuffle(completion); rng.shuffle(recon); rng.shuffle(w4)
    nchars = lambda xs: sum(len(r['prompt']) + len(r['target']) for r in xs)
    total_budget = nchars(core) / .60
    picked = list(core)
    for xs, budget in ((completion, total_budget*.10), (recon, total_budget*.10), (w4, min(total_budget*.20, nchars(w4)))):
        acc, used = [], 0
        for r in xs:
            size = len(r['prompt']) + len(r['target'])
            if used + size > budget: break
            acc.append(r); used += size
        picked.extend(acc)
    rng.shuffle(picked)
    expected = collections.Counter(digest(r) for r in picked)
    actual_rows = [json.loads(l) for l in open(ACTUAL, encoding='utf-8')]
    actual = collections.Counter(digest(r) for r in actual_rows)
    missing, extra = expected - actual, actual - expected
    cats = collections.Counter(r['cat'] for r in actual_rows)
    chars = collections.Counter({c: sum(len(r['prompt']) + len(r['target']) for r in actual_rows if r['cat'] == c) for c in cats})
    total_chars = sum(chars.values())
    report = {
        'tier_ab_pool_rows': len(allowed), **stats,
        'expected_samples': sum(expected.values()), 'actual_samples': sum(actual.values()),
        'exact_multiset_match': not missing and not extra,
        'missing_records': sum(missing.values()), 'extra_records': sum(extra.values()),
        'cat_counts': dict(cats),
        'char_shares': {c: round(n/total_chars, 4) for c, n in chars.items()},
    }
    out = Path(__file__).resolve().parent / 'stage1_dataset_provenance_audit_v1.json'
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print('written:', out)


if __name__ == '__main__':
    main()
