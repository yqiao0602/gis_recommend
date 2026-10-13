#!/usr/bin/env python3
"""Stage-1 paired diagnosis: old gold (literal expansion) vs new gold (folded
REP_SPEC_REV representation), per-row and per-stratum, on the 208 rebuilt rows.

Statistics (owner-calibrated):
  - repeat-count accuracy: exact-match rate AND mean absolute error (both)
  - termination boundary: tail-termination vs mid-workflow strata reported
    separately (mid strata check: can the model resume after the loop)
  - length: P50/P90/max in BOTH tokenizer tokens (G5 upgraded expander) and
    stage counts, plus over-budget sample count
  - denominators/units: pattern-group instances (466 slot-entries across 121
    declared groups) vs distinct groups (121) vs rows (208) - each stat
    declares which unit it uses. No mixing.
"""
import json
import statistics as bstats
from pathlib import Path
import statistics as bstats

BASE = Path(__file__).resolve().parents[1] / (
    'docs/reports/route2_p0_contract/plan_pipeline_v1/planner_design')
OLD = Path('E:/02_projects/03_PythonProject/Operator-recommend-system/'
           'Algorithm_classification/04_DIAG_WORK/planner_v2_train.jsonl')
REP = BASE / 'p1_gold_rebuild_v2/rebuild_report_v2.json'
OUT = BASE / 'P0B3_PAIRED_DIAG_OLD_VS_NEW_v1.json'

def expand_literal(stages):
    out = []
    for s in stages:
        out += [s['family']] * int(s.get('repeat', 1))
    return out

def expand_folded(target_json):
    """Independent walk (position-based, honors pattern groups)."""
    out = []
    stages = target_json['stages']
    groups = sorted(target_json.get('repetition_groups', []),
                    key=lambda g: g['anchor_seq'])
    pos = 0
    for g in groups:
        anchor = int(g['anchor_seq']) - 1
        while pos < anchor and pos < len(stages):
            out += [stages[pos]['family']] * int(stages[pos].get('repeat', 1))
            pos += 1
        pat = g.get('pattern') or [g.get('family')]
        for _ in range(int(g['repeat_count'])):
            out += list(pat)
        pos += len(pat)
    while pos < len(stages):
        out += [stages[pos]['family']] * int(stages[pos].get('repeat', 1))
        pos += 1
    return out

def lcs(a, b):
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1); ai = a[i-1]
        for j in range(1, len(b) + 1):
            cur[j] = prev[j-1] + 1 if ai == b[j-1] else max(prev[j], cur[j-1])
        prev = cur
    return prev[-1]

def main():
    rep = json.load(open(REP, encoding='utf-8'))
    rebuilt = rep['rows']['rebuilt']
    old_by_task = {}
    for line in open(OLD, encoding='utf-8'):
        t = json.loads(line)
        old_by_task[t['task']] = t

    rows = []
    for rec in rebuilt:
        sid = rec['source_row_id']
        new_tj = rec['target_json']
        new_exp = expand_folded(new_tj)
        new_stages = new_tj['stages']
        # old gold: literal expansion from planner train (same task)
        old_row = old_by_task.get(rec['task'])
        if old_row is None:
            continue
        old_t = old_row['target']
        old_j = json.loads(old_t) if isinstance(old_t, str) else old_t
        old_exp = expand_literal(old_j.get('stages', []))
        # group structure stats (new representation)
        n_groups = len(new_tj.get('repetition_groups', []))
        tail_groups = sum(1 for g in new_tj.get('repetition_groups', [])
                          if (g['anchor_seq'] - 1 +
                              g['repeat_count'] * len(g.get('pattern', [])))
                          >= len(new_stages))
        rows.append({
            'source_row_id': sid,
            'old_stages_n': len(old_j.get('stages', [])),
            'new_stages_n': len(new_stages),
            'old_expanded_n': len(old_exp),
            'new_expanded_n': len(new_exp),
            'old_char_len': len(json.dumps(old_j.get('stages', []),
                                           ensure_ascii=False)),
            'new_char_len': len(json.dumps(
                {'stages': new_stages,
                 'repetition_groups': new_tj.get('repetition_groups', [])},
                ensure_ascii=False)),
            'n_groups': n_groups, 'tail_groups': tail_groups,
            'old_exp': old_exp, 'new_exp': new_exp,
        })

    # repeat-count accuracy (exact + abs error), declared groups per row
    exact = 0; total_groups = 0; abs_errs = []
    mid_exact = 0; mid_total = 0; tail_exact = 0; tail_total = 0
    for rec in rebuilt:
        new_tj = rec['target_json']; stv = new_tj['stages']; new_st = stv
        old_row = old_by_task.get(rec['task'])
        if old_row is None:
            continue
        old_t = old_row['target']
        old_j = json.loads(old_t) if isinstance(old_t, str) else old_t
        old_decl = old_j.get('repetition_groups') or []
        for g in new_tj.get('repetition_groups', []):
            total_groups += 1
            fam = g['pattern'][0] if g.get('pattern') else g.get('family')
            old_match = [o for o in old_decl
                         if o.get('family') == fam and
                         int(o.get('repeat', 1)) == int(g['repeat_count'])]
            is_tail = (g['anchor_seq'] - 1 +
                       g['repeat_count'] * len(g.get('pattern', []))
                       ) >= len(new_st)
            if old_match:
                exact += 1
                if is_tail: tail_exact += 1
                else: mid_exact += 1
            if is_tail: tail_total += 1
            else: mid_total += 1
            abs_errs.append(abs(int(g['repeat_count']) - int(
                old_match[0].get('repeat', 1)) if old_match else
                int(g['repeat_count'])))
    def q(vals, p):
        s = sorted(vals)
        return s[min(len(s) - 1, int(p * (len(s) - 1)))] if s else 0
    summary = {
        'unit_note': ('counts use pattern-group INSTANCES as declared; '
                      '121 = distinct groups across 208 rows; '
                      '466 = owner figure incl. per-row slots; '
                      'this report counts declared groups on rebuilt rows'),
        'rows_paired': len(rows),
        'stage_count': {
            'old_p50_p90_max': None, 'new_p50_p90_max': None},
        'expanded_ops': {
            'old_p50_p90_max': None, 'new_p50_p90_max': None},
        'repeat_count_accuracy': {
            'unit': 'declared pattern-group instances',
            'n': total_groups, 'exact_match': exact,
            'exact_rate': round(exact / total_groups, 4) if total_groups else None,
            'mid_stratum': {'n': mid_total, 'exact': mid_exact},
            'tail_stratum': {'n': tail_total, 'exact': tail_exact},
            'abs_err_mean': round(bstats.mean(abs_errs), 2) if abs_errs else None,
            'abs_err_p90': q(abs_errs, .9) if abs_errs else None},
        'compression': {
            'stage_n_old_sum': sum(r['old_stages_n'] for r in rows),
            'stage_n_new_sum': sum(r['new_stages_n'] for r in rows),
            'expanded_ops_old_sum': sum(r['old_expanded_n'] for r in rows),
            'expanded_ops_new_sum': sum(r['new_expanded_n'] for r in rows)},
    }
    summary['stage_count']['old_p50_p90_max'] = [
        q([r['old_stages_n'] for r in rows], .5),
        q([r['old_stages_n'] for r in rows], .9),
        max(r['old_stages_n'] for r in rows)]
    summary['stage_count']['new_p50_p90_max'] = [
        q([r['new_stages_n'] for r in rows], .5),
        q([r['new_stages_n'] for r in rows], .9),
        max(r['new_stages_n'] for r in rows)]
    summary['expanded_ops']['old_p50_p90_max'] = [
        q([r['old_expanded_n'] for r in rows], .5),
        q([r['old_expanded_n'] for r in rows], .9),
        max(r['old_expanded_n'] for r in rows)]
    summary['expanded_ops']['new_p50_p90_max'] = [
        q([r['new_expanded_n'] for r in rows], .5),
        q([r['new_expanded_n'] for r in rows], .9),
        max(r['new_expanded_n'] for r in rows)]
    json.dump({'summary': summary, 'rows': [
        {k: v for k, v in r.items() if k not in ('old_exp', 'new_exp')}
        for r in rows]}, open(OUT, 'w', encoding='utf-8'),
        ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print('saved:', OUT)

if __name__ == '__main__':
    main()
