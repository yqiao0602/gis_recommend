"""Stage-1 dataset builder v2 (⑦ frozen protocol, implementation corrections).

Corrections vs the initial candidate builder:
- Uses the *actual Qwen tokenizer* and token counts, not character proxy.
- Enforces the frozen 6-3 Tier A/B pool at source row id.
- Stores task/context/target separately for the Task-protecting collator.
- W4 insert corruption really inserts a malformed typed step; delete/swap
  require full-plan repair. No fake 'identify a nonexistent corruption'.
- W4 hard cap <=25% actual tokens; target shares 60/10/10/20 are selected
  by tokenizer-token budget, then measured exactly and reported.
No chain-LM examples. No GPU/model loading; tokenizer only.
"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from route2_training.plans.chain_to_plan_v1_1 import convert, render_plan

SRC = '/home/qy/system_redesign/outputs_v2/gee_b1_stage_data_v1/b1_gee_stage_train.jsonl'
TIER = '/home/qy/system_redesign/route2_training/plans/plan_pool_tiered_v2.jsonl'
BASE_MODEL = '/home/qy/models/Qwen3.5/Qwen3.5-9B-Base'
OUT = Path(__file__).resolve().parent / 'stage1_train_v2_2.jsonl'
REPORT = Path(__file__).resolve().parent / 'stage1_dataset_report_v2_2.json'
SEED = 20260924
MAX_LEN = 1024
SEP = '\nWorkflow plan:'

FAMILIES = ['TEMPORAL_FILTER', 'SPATIAL_FILTER', 'ATTRIBUTE_FILTER', 'BAND_SELECT',
            'BAND_ARITHMETIC', 'SPECTRAL_INDEX', 'THRESHOLD_LOGIC', 'MASKING',
            'AGGREGATION', 'REGIONAL_STATS', 'CLASSIFICATION', 'SPATIAL_CLIP',
            'VECTOR_GEOMETRY', 'NEIGHBORHOOD', 'TERRAIN_DERIVED', 'COMPOSITE',
            'SPATIAL_JOIN', 'RESAMPLE_REPROJECT', 'EXPORT_OUTPUT']


def renumber(steps):
    out = []
    for i, s in enumerate(steps, 1):
        x = dict(s)
        x['order'] = i
        x['depends_on'] = [i - 1] if i > 1 else []
        out.append(x)
    return out


def corrupt_plan(plan, rng):
    """One real W4 mutation per source plan: delete / semantic swap / bad insert.

    Matches the owner-approved W4 meaning: delete an existing operation;
    swap adjacent semantically distinct operations (never identical steps);
    or insert an explicitly I/O-incompatible operation. Subtype mix is the
    natural seeded distribution inside the frozen overall W4 token budget.
    """
    steps = plan['steps']
    swap_pairs = []
    for j, (a, b) in enumerate(zip(steps, steps[1:])):
        sig_a = (a.get('family'), a.get('intent'), tuple(x.get('type') for x in a.get('input', [])),
                 (a.get('output') or {}).get('type'))
        sig_b = (b.get('family'), b.get('intent'), tuple(x.get('type') for x in b.get('input', [])),
                 (b.get('output') or {}).get('type'))
        if sig_a != sig_b:
            swap_pairs.append(j)
    choices = ['insert']
    if len(steps) >= 2: choices.append('delete')
    if swap_pairs: choices.append('swap')
    kind = rng.choice(choices)
    if kind == 'delete':
        i = rng.randrange(len(steps))
        damaged = renumber(steps[:i] + steps[i+1:])
    elif kind == 'swap':
        i = rng.choice(swap_pairs)
        damaged = renumber(steps[:i] + [steps[i+1], steps[i]] + steps[i+2:])
    else:
        i = rng.randrange(1, len(steps)+1)
        prev_t = (steps[i-1].get('output') or {}).get('type')
        vocab = ('raster','vector','geometry','scalar','text','list')
        bad_in = next(t for t in vocab if t != prev_t)
        bad_out = next(t for t in vocab if t != bad_in)
        bad = {'intent': f'perform an operation requiring {bad_in} with no compatible producer',
               'family':'OTHER_UNMAPPED','input':[{'role':'primary input','type':bad_in}],
               'output':{'type':bad_out},'depends_on':[],'constraints':{},'roles':[],
               'provision':False,'synthetic_corruption':True}
        damaged = renumber(steps[:i] + [bad] + steps[i:])
    assert damaged != steps
    return damaged, renumber(steps), kind



def make_example(cat, task, context, target, separator=None, corruption_kind=None, source_row_id=None):
    row = {'cat': cat, 'task': task, 'context': context, 'target': target}
    if separator is not None:
        row['separator'] = separator
    if corruption_kind is not None:
        row['corruption_kind'] = corruption_kind
    if source_row_id is not None:
        row['source_row_id'] = source_row_id
    return row


def token_len(tok, ex):
    """Match Stage1PlanCollator tokenization/truncation exactly (effective tokens)."""
    bos = 1 if tok.bos_token_id is not None else 0
    eos = 1 if tok.eos_token_id is not None else 0
    task = tok.encode(ex['task'], add_special_tokens=False)
    sep = tok.encode(ex.get('separator', SEP), add_special_tokens=False)
    context = tok.encode(ex.get('context', ''), add_special_tokens=False)
    target = tok.encode(' ' + ex['target'], add_special_tokens=False)
    fixed = bos + len(task) + len(sep)
    if fixed >= MAX_LEN:
        raise ValueError(f"task+separator exceeds max_len ({fixed}/{MAX_LEN})")
    room = MAX_LEN - fixed
    # Mirror Stage1PlanCollator: preserve complete Task; trim context tail,
    # then target tail; EOS token reserved before both truncations.
    if len(context) + len(target) + eos > room:
        keep_context = max(0, room - eos - min(len(target), max(0, room // 2)))
        context = context[:keep_context]
    target_room = max(0, room - len(context) - eos)
    target = target[:target_room]
    return fixed + len(context) + len(target) + eos


def token_truncation(tok, ex):
    bos = 1 if tok.bos_token_id is not None else 0
    eos = 1 if tok.eos_token_id is not None else 0
    task = tok.encode(ex['task'], add_special_tokens=False)
    sep = tok.encode(ex.get('separator', SEP), add_special_tokens=False)
    context = tok.encode(ex.get('context', ''), add_special_tokens=False)
    target = tok.encode(' ' + ex['target'], add_special_tokens=False)
    fixed = bos + len(task) + len(sep)
    if fixed >= MAX_LEN:
        raise ValueError(f"task+separator exceeds max_len ({fixed}/{MAX_LEN})")
    room = MAX_LEN - fixed
    ctx0, tar0 = len(context), len(target)
    if len(context) + len(target) + eos > room:
        keep_context = max(0, room - eos - min(len(target), max(0, room // 2)))
        context = context[:keep_context]
    target_room = max(0, room - len(context) - eos)
    target = target[:target_room]
    return {'context_truncated_tokens': ctx0-len(context),
            'target_truncated_tokens': tar0-len(target),
            'task_tokens': len(task), 'effective_tokens': fixed+len(context)+len(target)+eos}


def pick_to_budget(rows, budget, tok):
    picked, used = [], 0
    for r in rows:
        n = token_len(tok, r)
        if used + n > budget:
            continue
        picked.append((r, n))
        used += n
    return picked, used


def main():
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    rng = random.Random(SEED)
    allowed = {r['row_id'] for line in open(TIER, encoding='utf-8')
               if (r := json.loads(line))['tier'] in ('A', 'B')}
    buckets = {k: [] for k in ('core', 'completion', 'reconstruction', 'w4')}
    stats = Counter()
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
        full = render_plan(plan)
        buckets['core'].append(make_example('core', task, '', full, separator=SEP, source_row_id=row_id))
        steps = plan['steps']
        if len(steps) >= 3:
            k = rng.randrange(2, len(steps))
            prefix = render_plan({'steps': steps[:k]})
            buckets['completion'].append(make_example(
                'completion', task,
                prefix + '\nWhat is the intent of the next operation step? Answer with the operation description only.',
                steps[k]['intent'], separator='\nWorkflow plan (partial):\n',
                source_row_id=row_id))
            i = rng.randrange(1, len(steps) - 1)
            damaged = renumber(steps[:i] + [steps[i + 1], steps[i]] + steps[i + 2:])
            buckets['reconstruction'].append(make_example(
                'reconstruction', task, render_plan({'steps': damaged}), full,
                separator='\nThe following workflow plan has two adjacent steps in the wrong order. Rewrite the full plan in the correct order.\n',
                source_row_id=row_id))
        corrupted, repair, kind = corrupt_plan(plan, rng)
        buckets['w4'].append(make_example(
            'w4', task, render_plan({'steps': corrupted}), render_plan({'steps': repair}),
            separator=f'\nThe following workflow plan contains exactly one {kind} structural corruption. Repair it and output the complete corrected plan.\n',
            corruption_kind=kind, source_row_id=row_id))

    trunc_by_cat = {}
    for cat, examples in list(buckets.items()):
        kept = []
        for ex in examples:
            try:
                f = token_truncation(tok, ex)
                assert f['effective_tokens'] == token_len(tok, ex)
                stats[f'{cat}_context_truncated_tokens'] += f['context_truncated_tokens']
                stats[f'{cat}_target_truncated_tokens'] += f['target_truncated_tokens']
                kept.append(ex)
            except ValueError:
                # Complete Task + separator do not fit; protocol forbids Task truncation.
                stats[f'{cat}_task_too_long_excluded'] += 1
        buckets[cat] = kept
    for b in buckets.values():
        rng.shuffle(b)
    core = buckets['core']
    core_tokens = sum(token_len(tok, r) for r in core)
    total_budget = core_tokens / .60
    budgets = {'completion': total_budget*.10,
               'reconstruction': total_budget*.10,
               'w4': min(total_budget*.20, sum(token_len(tok, r) for r in buckets['w4']))}
    picked = list(core)
    picked_tokens = {'core': core_tokens}
    for cat in ('completion', 'reconstruction', 'w4'):
        sel, used = pick_to_budget(buckets[cat], budgets[cat], tok)
        picked.extend(r for r, _ in sel)
        picked_tokens[cat] = used
    rng.shuffle(picked)
    OUT.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in picked), encoding='utf-8')
    picked_trunc = Counter()
    picked_trunc_values = {k: {'context': [], 'target': []} for k in buckets}
    for ex in picked:
        ft = token_truncation(tok, ex)
        cat = ex['cat']
        for part in ('context', 'target'):
            ntr = ft[f'{part}_truncated_tokens']
            picked_trunc[f'{cat}_{part}_truncated_examples'] += int(ntr > 0)
            picked_trunc_values[cat][part].append(ntr)
    def qtile(vals, q):
        if not vals: return 0
        ss = sorted(vals)
        return ss[min(len(ss)-1, int(q*(len(ss)-1)))]
    trunc_summary = {
        cat: {part: {'truncated_examples': picked_trunc[f'{cat}_{part}_truncated_examples'],
                     'total_truncated_tokens': sum(vals),
                     'p50_truncated_tokens': qtile(vals, .50),
                     'p90_truncated_tokens': qtile(vals, .90),
                     'max_truncated_tokens': max(vals, default=0)}
              for part, vals in data.items()}
        for cat, data in picked_trunc_values.items()}
    total = sum(picked_tokens.values())
    report = {
        **stats, 'counts': dict(Counter(r['cat'] for r in picked)),
        'tokens_by_cat': picked_tokens,
        'actual_token_share': {k: round(v/total, 5) for k, v in picked_tokens.items()},
        'truncation_by_cat': trunc_summary,
        'total_tokens': total, 'estimated_steps_per_epoch': None,
        'max_len': MAX_LEN, 'tokenizer': BASE_MODEL,
        'truncation_contract': 'task protected; context tail then target tail only',
        'chain_lm_examples': 0,
        'w4_corruptions': dict(Counter(r.get('corruption_kind') for r in picked if r['cat']=='w4')),
        'task_truncation_count': 0,    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print('written:', OUT)


if __name__ == '__main__':
    main()
