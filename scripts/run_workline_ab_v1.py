#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Owner C-ruling execution: parallel Work Line A (eval audit) + Work Line B
(BAND_SELECT capability diagnosis). Training deferred until both gates met."""

import json, sys, hashlib, os
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, '..')
PD = os.path.join(REPO, 'docs', 'reports', 'route2_p0_contract',
                  'plan_pipeline_v1', 'planner_design')
DEV = os.path.join(REPO, '..', '04_DIAG_WORK', 'planner_v2_dev.jsonl')


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(65536), b''):
            h.update(c)
    return h.hexdigest()


def bp_hash(tgt):
    return hashlib.sha256(json.dumps(tgt, sort_keys=True,
                                     ensure_ascii=False).encode('utf-8')).hexdigest()


def expand(stages):
    out = []
    for s in stages:
        out += [s['family']] * int(s.get('repeat', 1))
    return out


def metrics(pred_seq, gold_seq):
    pc, gc = Counter(pred_seq), Counter(gold_seq)
    tp = sum(min(pc[f], gc[f]) for f in pc)
    np_, ng = len(pred_seq), len(gold_seq)
    bag = 2 * tp / (np_ + ng) if np_ + ng else 0
    over = sum(max(0, pc[f] - gc[f]) for f in pc)
    under = sum(max(0, gc[f] - pc[f]) for f in gc)
    prec = tp / np_ if np_ else 0
    rec = tp / ng if ng else 0
    return {'bag': round(bag, 4), 'prec': round(prec, 4), 'rec': round(rec, 4),
            'over': over, 'under': under}


def main():
    dev = [json.loads(l) for l in open(DEV, encoding='utf-8') if l.strip()]
    pred = json.load(open(os.path.join(PD, 'p0b_768', 'predictions.json'),
                          encoding='utf-8'))
    items = pred['items']

    # parse all predictions
    parsed = {}
    for i, it in enumerate(items):
        try:
            obj = json.loads(it.get('pred_text') or '')
            if isinstance(obj, dict) and 'stages' in obj:
                parsed[i] = expand(obj['stages'])
            else:
                parsed[i] = None
        except Exception:
            parsed[i] = None

    # ===== WORK LINE A: blueprint duplicate audit =====
    print('=' * 60)
    print('WORK LINE A: Evaluation credibility audit')
    print('=' * 60)

    bp_groups = defaultdict(list)
    for i, d in enumerate(dev):
        t = d['target']
        if isinstance(t, str):
            try:
                t = json.loads(t)
            except Exception:
                continue
        bp_groups[bp_hash(t)].append({
            'idx': i, 'task': (d['task'] or '').splitlines()[0][:120],
            'task_full': d['task'] or '',
            'families': sorted(set(s['family'] for s in t.get('stages', []))),
            'stages_n': len(t.get('stages', [])),
            'rg_n': len(t.get('repetition_groups', [])),
        })

    multi = {h: r for h, r in bp_groups.items() if len(r) > 1}
    singleton_n = sum(1 for r in bp_groups.values() if len(r) == 1)

    # classify each multi group structurally
    group_class = {}
    for h, rs in sorted(multi.items(), key=lambda kv: -len(kv[1])):
        tasks = set(r['task'] for r in rs)
        fam_sets = set(tuple(r['families']) for r in rs)
        # same task + same blueprint = true duplicate
        if len(tasks) == 1:
            cls = 'true_duplicate'
        # different tasks + minimal families = likely binding error
        elif len(rs[0]['families']) <= 4:
            cls = 'binding_error_suspect'
        # different tasks + rich families = possibly legitimate shared subflow
        else:
            cls = 'possible_valid_shared'
        group_class[h] = {'rows': rs, 'classification': cls,
                          'size': len(rs), 'unique_tasks': len(tasks)}

    cls_dist = Counter(g['classification'] for g in group_class.values())
    affected_rows = sum(g['size'] for g in group_class.values())

    # high-priority groups for owner review (binding_error_suspect, largest first)
    priority = sorted(
        [(h, g) for h, g in group_class.items()
         if g['classification'] == 'binding_error_suspect'],
        key=lambda kv: -kv[1]['size'])

    wa_result = {
        'total_dev': len(dev),
        'singleton_blueprints': singleton_n,
        'multi_blueprints': len(multi),
        'affected_rows': affected_rows,
        'affected_pct': round(affected_rows / len(dev) * 100, 1),
        'classification': dict(cls_dist),
        'high_priority_binding_error_groups': [
            {'hash': h[:12], 'size': g['size'],
             'unique_tasks': g['unique_tasks'],
             'families': g['rows'][0]['families'],
             'sample_tasks': [r['task'][:60] for r in g['rows'][:3]]}
            for h, g in priority[:8]],
    }
    print(json.dumps(wa_result, indent=2, ensure_ascii=False))

    # ===== WORK LINE B: BAND_SELECT capability diagnosis =====
    print('\n' + '=' * 60)
    print('WORK LINE B: BAND_SELECT capability diagnosis')
    print('=' * 60)

    TARGET = 'BAND_SELECT'
    # per-row analysis
    rows_data = []
    for i, d in enumerate(dev):
        t = d['target']
        if isinstance(t, str):
            try:
                t = json.loads(t)
            except Exception:
                continue
        gold_stages = t.get('stages', [])
        gold_fams = set(s['family'] for s in gold_stages)
        gold_seq = expand(gold_stages)
        pred_seq = parsed.get(i)

        has_target = TARGET in gold_fams
        if pred_seq is not None:
            pred_fams = set(pred_seq)
            has_pred = TARGET in pred_fams
            under_n = sum(max(0, gold_seq.count(f) - pred_seq.count(f))
                          for f in gold_fams)
            over_n = sum(max(0, pred_seq.count(f) - gold_seq.count(f))
                         for f in pred_seq)
        else:
            pred_fams = set()
            has_pred = False
            under_n = len(gold_seq)
            over_n = 0

        glen = len(gold_seq)
        rows_data.append({
            'idx': i, 'parsed': pred_seq is not None,
            'has_target': has_target, 'has_pred': has_pred,
            'glen': glen, 'under_n': under_n, 'over_n': over_n,
            'task_head': (d['task'] or '').splitlines()[0][:60],
            'task_text': d['task'] or '',
        })

    # Q1: BAND_SELECT miss rate
    with_target = [r for r in rows_data if r['has_target']]
    without_target = [r for r in rows_data if not r['has_target']]
    missed = [r for r in with_target if not r['has_pred']]
    hit = [r for r in with_target if r['has_pred']]
    miss_rate = len(missed) / max(1, len(with_target))

    # Q2: co-occurrence — when BAND_SELECT is missed, what else is missing?
    cooccur = Counter()
    for r in missed:
        t = dev[r['idx']]['target']
        if isinstance(t, str):
            try:
                t = json.loads(t)
            except Exception:
                continue
        gf = set(s['family'] for s in t.get('stages', []))
        pp = parsed.get(r['idx'])
        if pp is None:
            continue
        pf = set(pp)
        for f in gf - pf:
            if f != TARGET:
                cooccur[f] += 1

    # Q3: controlled analysis — after parse_ok only
    parsed_only = [r for r in rows_data if r['parsed']]
    pt_with = [r for r in parsed_only if r['has_target']]
    pt_missed = [r for r in pt_with if not r['has_pred']]
    miss_rate_parsed = len(pt_missed) / max(1, len(pt_with))

    # Q4: length-stratified miss rate
    len_buckets = {'short(<=10)': [], 'mid(11-25)': [], 'long(>25)': []}
    for r in pt_with:
        b = ('short(<=10)' if r['glen'] <= 10 else
             'mid(11-25)' if r['glen'] <= 25 else 'long(>25)')
        len_buckets[b].append(r)
    len_miss = {}
    for b, rs in sorted(len_buckets.items()):
        m = [r for r in rs if not r['has_pred']]
        len_miss[b] = f"{len(m)}/{len(rs)} = {round(len(m)/max(1,len(rs)),3)}"

    # Q5: does BAND_SELECT miss co-occur with other semantic misses?
    # For rows with BAND_SELECT in gold and NOT in pred, check what else is missing
    bs_miss_rows = [r for r in rows_data
                    if r['has_target'] and not r['has_pred'] and r['parsed']]
    co_miss = Counter()
    for r in bs_miss_rows:
        i = r['idx']
        t = dev[i]['target']
        if isinstance(t, str):
            t = json.loads(t)
        gf = set(s['family'] for s in t.get('stages', []))
        pp = parsed.get(i)
        if pp is None:
            continue
        pf = set(pp)
        for f in gf - pf:
            if f != TARGET:
                co_miss[f] += 1

    wb_result = {
        'gold_has_TARGET_rows': len(with_target),
        'gold_lacks_TARGET_rows': len(without_target),
        'miss_rate_all': round(miss_rate, 4),
        'miss_rate_parsed_only': round(miss_rate_parsed, 4),
        'hit_count': len(hit),
        'miss_count': len(missed),
        'length_stratified_miss': len_miss,
        'cooccurring_missed_families': dict(co_miss.most_common(10)),
        'interpretation': '',
    }

    # statistical significance: Fisher's exact test approximation
    a = len(hit)  # gold has TARGET, pred has TARGET
    b = len(missed)  # gold has TARGET, pred missing
    c = sum(1 for r in rows_data if not r['has_target'] and r['has_pred'])
    dd = sum(1 for r in rows_data if not r['has_target'] and not r['has_pred'])
    wb_result['contingency_table'] = {'a_TP': a, 'b_FN': b,
                                      'c_FP': c, 'd_TN': dd}

    # Interpretation
    if miss_rate > 0.4:
        wb_result['interpretation'] = (
            f'BAND_SELECT miss rate {miss_rate:.1%} is substantial. '
            f'Top co-occurring misses: {dict(co_miss.most_common(3))}. '
            f'This suggests a stable family-selection deficiency, not random noise.')
    else:
        wb_result['interpretation'] = (
            f'BAND_SELECT miss rate {miss_rate:.1%} is moderate.')

    print(json.dumps(wb_result, indent=2, ensure_ascii=False))

    # ===== Save combined results =====
    combined = {
        'schema': 'workline_AB_results_v1',
        'work_line_A_eval_audit': wa_result,
        'work_line_B_band_select': wb_result,
        'training_gate_status': {
            'eval_gate': 'pending — dev audit incomplete',
            'training_gate': 'pending — BAND_SELECT diagnosis in progress',
        },
    }
    out = os.path.join(PD, 'WORKLINE_AB_RESULTS_V1.json')
    json.dump(combined, open(out, 'w', encoding='utf-8'), indent=2,
              ensure_ascii=False)
    print('\nsaved:', out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
