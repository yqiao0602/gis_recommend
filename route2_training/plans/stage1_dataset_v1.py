"""Stage-1 mixed training dataset builder (⑦ protocol, pre-registered).

Stream composition by CHARACTER budget (token proxy, measured post-hoc):
  core  60% : Task -> Workflow Plan        (rendered per PLAN_SCHEMA_v1)
  aux1  10% : completion (plan prefix -> final step intent)
  aux2  10% : reconstruction (swapped adjacent steps -> correct plan)
  aux4  20% : W4 corruption identify/repair (<=25% hard cap)
  chain LM 0%  (never)

Fail-closed: rows whose chain fails v1.1 conversion are excluded and
counted. Seed 20260924. Truncation: task protected (prompt head), plan
tail truncated per 7-5.
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from route2_training.plans.chain_to_plan_v1_1 import convert, render_plan  # noqa: E402

SRC = '/home/qy/system_redesign/outputs_v2/gee_b1_stage_data_v1/b1_gee_stage_train.jsonl'
OUT = Path(__file__).resolve().parent / 'stage1_train_v1.jsonl'
REPORT = Path(__file__).resolve().parent / 'stage1_dataset_report_v1.json'
SEED = 20260924
MAX_PLAN_CHARS = 3000  # ~ >1024 tokens; tail-truncated by collator anyway

rng = random.Random(SEED)

FAMILIES = ['TEMPORAL_FILTER', 'SPATIAL_FILTER', 'ATTRIBUTE_FILTER', 'BAND_SELECT',
            'BAND_ARITHMETIC', 'SPECTRAL_INDEX', 'THRESHOLD_LOGIC', 'MASKING',
            'AGGREGATION', 'REGIONAL_STATS', 'CLASSIFICATION', 'SPATIAL_CLIP',
            'VECTOR_GEOMETRY', 'NEIGHBORHOOD', 'TERRAIN_DERIVED', 'COMPOSITE',
            'SPATIAL_JOIN', 'RESAMPLE_REPROJECT', 'EXPORT_OUTPUT']


def corrupted_copy(steps):
    """W4 corruption: delete / swap / wrong-family insert. Returns (corrupted_steps, answer)."""
    kinds = ['delete', 'swap', 'insert']
    kind = rng.choice(kinds)
    i = rng.randrange(1, len(steps) - 1) if len(steps) > 3 else 1
    if kind == 'delete' and len(steps) >= 3:
        missing = steps[i]
        out = steps[:i] + steps[i + 1:]
        return out, f"the missing step is: {missing['intent']}"
    if kind == 'swap' and len(steps) >= 3:
        a, b = steps[i], steps[i + 1]
        out = steps[:i] + [b, a] + steps[i + 2:]
        return out, f"steps {a['order']} and {b['order']} are swapped"
    wrong = rng.choice([f for f in FAMILIES])
    return steps, f"an inserted step does not belong: {wrong.lower().replace('_', ' ')} operation"


def main() -> int:
    # 6-3 frozen pool: only Tier A/B rows enter Stage-1 supervision
    allowed_rows = set()
    tp = Path(__file__).resolve().parent / 'plan_pool_tiered_v2.jsonl'
    for line in tp.open(encoding='utf-8'):
        r = json.loads(line)
        if r['tier'] in ('A', 'B'):
            allowed_rows.add(r['row_id'])
    core, completion, recon, w4 = [], [], [], []
    st = {'rows': 0, 'converted': 0, 'coverage_failed': 0}
    with open(SRC, encoding='utf-8') as f:
        for line in f:
            st['rows'] += 1
            row_id = st['rows']  # 1-indexed line number, matches tier pool row_id
            row = json.loads(line)
            if row.get('split') != 'train':
                continue
            st['rows_train'] = st.get('rows_train', 0) + 1
            if row_id not in allowed_rows:
                st['outside_tier_pool'] = st.get('outside_tier_pool', 0) + 1
                continue
            plan, rec = convert(row.get('gee_canonical_chain') or '')
            if plan is None:
                st['coverage_failed'] += 1
                continue
            st['converted'] += 1
            task = row.get('instruction', '')
            if not task or len(plan['steps']) < 2:
                continue
            target = render_plan(plan)[:MAX_PLAN_CHARS]
            core.append({'cat': 'core', 'prompt': task + '\nWorkflow plan:',
                         'target': target})
            steps = plan['steps']
            # completion (10% bucket source)
            if len(steps) >= 3:
                k = rng.randrange(2, len(steps))
                prefix = render_plan({'steps': steps[:k]})[:MAX_PLAN_CHARS]
                completion.append({
                    'cat': 'completion',
                    'prompt': (task + '\nWorkflow plan (partial):\n' + prefix +
                               '\nWhat is the intent of the next operation step? '
                               'Answer with the operation description only.'),
                    'target': steps[k]['intent']})
            # reconstruction (10% bucket source)
            if len(steps) >= 3:
                i = rng.randrange(1, len(steps) - 1)
                sw = steps[:i] + [steps[i + 1], steps[i]] + steps[i + 2:]
                recon.append({
                    'cat': 'reconstruction',
                    'prompt': (task + '\nThe following workflow plan has two adjacent '
                               'steps in the wrong order. Rewrite the full plan in the '
                               'correct order.\n' + render_plan({'steps': sw})[:MAX_PLAN_CHARS]),
                    'target': render_plan(plan)[:MAX_PLAN_CHARS]})
            # W4 (20% bucket source)
            cor, ans = corrupted_copy(steps)
            w4.append({
                'cat': 'w4',
                'prompt': (task + '\nThe following workflow plan contains exactly one '
                           'structural problem (a removed step, a swapped pair, or an '
                           'inserted wrong operation). Identify the problem.\n' +
                           render_plan({'steps': cor})[:MAX_PLAN_CHARS]),
                'target': ans})
    rng.shuffle(core)
    rng.shuffle(completion)
    rng.shuffle(recon)
    rng.shuffle(w4)

    def chars(rows):
        return sum(len(r['prompt']) + len(r['target']) for r in rows)

    total_core = chars(core)
    budget_total = total_core / 0.60
    b_aux = budget_total * 0.10
    b_w4 = min(budget_total * 0.20, chars(w4))  # respect availability
    picked = list(core)
    for bucket, budget, rows in [('completion', b_aux, completion),
                                 ('reconstruction', b_aux, recon),
                                 ('w4', b_w4, w4)]:
        acc, c = [], 0
        for r in rows:
            cc = len(r['prompt']) + len(r['target'])
            if c + cc > budget:
                break
            acc.append(r)
            c += cc
        picked.extend(acc)
        st[f'{bucket}_picked'] = len(acc)
    rng.shuffle(picked)
    with OUT.open('w', encoding='utf-8') as f:
        for r in picked:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    cc = {c: sum(1 for r in picked if r['cat'] == c) for c in
          ('core', 'completion', 'reconstruction', 'w4')}
    ch = {c: sum(len(r['prompt']) + len(r['target']) for r in picked if r['cat'] == c)
          for c in cc}
    tot = sum(ch.values())
    report = {**st, 'samples': len(picked), 'count_by_cat': cc,
              'char_share': {c: round(v / tot, 3) for c, v in ch.items()},
              'total_chars': tot, 'est_tokens': round(tot / 3.7)}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=1))
    print(f'written: {OUT}')
    return 0


if __name__ == '__main__':
    main()
