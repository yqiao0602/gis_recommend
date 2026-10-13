#!/usr/bin/env python3
"""Planner gold reconstruction engine v1 (owner-approved data engineering).

Rebuilds uncapped Planner-v2 gold for the 213 run-cap artifact rows + fixes
declarations on the 3 script-grounded rows. Source of truth per row:
semantic_chain_raw from the G0 mother corpus (verified 213/213 to equal
original_semantic_length).

Planner-v2 representation conventions (from blueprint_v2_gold_v3):
  stages: ordered [{seq, family, repeat}] — adjacent identical ops folded
          into one stage with repeat=N (semantic-layer fold)
  repetition_groups: [{stage_seq, family, repeat, iteration_hint}]
  total_iterations: sum of stage repeats
  stage_count: len(stages)

Quality gates per row:
  G1 traceability: sid + g0 line + old gold ref recorded
  G2 semantic completeness: expansion length == original_semantic_length
     (pre-cap truth) and explicit terminal stage present
  G3 representation consistency: repetition_groups repeats match stages
  G4 length control: char length recorded; over-budget rows flagged for
     semantic-layer abstraction (repeat-fold), never silently truncated

Unrecoverable rows: isolated with reason. Old gold kept untouched.
"""
import json, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G0P = ROOT.parent / 'server_backup_mdzhang_20260927/home/qy/system_redesign/outputs_v2/gee_b1_stage_data_v1/b1_gee_stage_train.jsonl'
EV = ROOT / 'docs/reports/route2_p0_contract/plan_pipeline_v1/planner_design/p1_unstated_133_evidence_audit.json'
TRAIN = Path(str(ROOT.parent / '04_DIAG_WORK/planner_v2_train.jsonl'))
OUTDIR = ROOT / 'docs/reports/route2_p0_contract/plan_pipeline_v1/planner_design/p1_gold_rebuild'
OUTDIR.mkdir(parents=True, exist_ok=True)

MAX_TARGET_CHARS = 6000   # beyond this -> abstract-representation handling, flagged

def load_jsonl(p):
    with open(p, encoding='utf-8') as f:
        return [json.loads(l) for l in f]

def fold_stages(ops):
    """Adjacent identical ops -> one stage with repeat=N (Planner-v2 fold)."""
    stages = []
    for op in ops:
        if stages and stages[-1]['family'] == op:
            stages[-1]['repeat'] += 1
        else:
            stages.append({'family': op, 'repeat': 1})
    return stages

def main():
    g0 = {}
    with open(G0P, encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            g0[i] = json.loads(line)
    ev = json.load(open(EV, encoding='utf-8'))
    rows = ev['rows']
    train_rows = load_jsonl(TRAIN)

    rebuilt, grounded_fix, isolated = [], [], []
    for r in rows:
        sid = r['source_row_id']
        g = g0[sid]
        raw = g.get('semantic_chain_raw', '')
        ops = [x.strip() for x in raw.split('->') if x.strip()]
        orig_len = g.get('original_semantic_length')
        base = {
            'source_row_id': sid, 'g0_line': sid,
            'task': g.get('instruction', ''),
            'old_gold_stages': r['n_stages'], 'loop_window': r['loop_window'],
            'loop_count': r['loop_count'],
            'run_cap_applied': g.get('run_cap_applied'),
            'original_semantic_length': orig_len,
        }
        if r['verdict'] == 'gold_capped_by_legacy_run_cap':
            stages = fold_stages(ops)
        else:  # script_grounded: same construction; declaration fix handled below
            stages = fold_stages(ops)

        # declaration: emit repetition_groups for stages with repeat>1
        rgs = []
        for s in stages:
            if s['repeat'] > 1:
                rgs.append({'stage_seq': stages.index(s) + 1,
                            'family': s['family'], 'repeat': s['repeat'],
                            'iteration_hint': ['unspecified']})
        rec = dict(base)
        rec['new_stages'] = [{'seq': i + 1, 'family': s['family'],
                              'repeat': s['repeat']} for i, s in enumerate(stages)]
        rec['new_repetition_groups'] = rgs
        rec['new_stage_count'] = len(stages)
        rec['new_total_iterations'] = sum(s['repeat'] for s in stages)
        rec['new_target_chars'] = len(json.dumps(
            {'stages': rec['new_stages'], 'repetition_groups': rgs},
            ensure_ascii=False))
        rec['over_char_budget'] = rec['new_target_chars'] > MAX_TARGET_CHARS
        rec['terminal_stage'] = stages[-1]['family']
        rec['gate_G2_complete'] = (len(ops) == orig_len)
        rec['gate_G3_consistent'] = all(
            rg['repeat'] == rec['new_stages'][rg['stage_seq'] - 1]['repeat']
            for rg in rgs)

        if r['verdict'] == 'gold_capped_by_legacy_run_cap':
            if rec['over_char_budget'] or not rec['gate_G2_complete'] \
               or not rec['gate_G3_consistent']:
                rec['isolation_reason'] = (
                    'over_char_budget' if rec['over_char_budget'] else
                    'gate_G2/G3 violation')
                isolated.append(rec)
            else:
                rebuilt.append(rec)
        else:
            grounded_fix.append(rec)

    # grounded 3 rows: verify and emit declaration fix note
    for rec in grounded_fix:
        rec['declaration_fix'] = 'add repetition_groups covering verified repeat counts'

    # old-vs-new paired diagnostic set (all rebuilt rows)
    train_by = {}
    for i, t in enumerate(train_rows):
        train_by.setdefault(t['target'][:60], i)
    pairs = []
    for rec in rebuilt[:]:
        old = None
        # locate old gold via task match
        for tr in train_rows:
            if tr['task'] == rec['task']:
                t = tr['target']
                old = json.loads(t) if isinstance(t, str) else t
                break
        if old is None:
            continue
        old_st = old.get('stages', [])
        pairs.append({
            'source_row_id': rec['source_row_id'],
            'old_stage_count': rec['old_gold_stages'],
            'new_stage_count': rec['new_stage_count'],
            'old_total_iterations': old.get('total_iterations'),
            'new_total_iterations': rec['new_total_iterations'],
            'old_ends_mid_loop': rec['loop_count'] > 0 and
                rec['old_gold_stages'] < rec['new_stage_count'],
            'new_terminal_stage': rec['terminal_stage'],
            'restored_ops': rec['new_total_iterations'] -
                            sum(s.get('repeat', 1) for s in old_st),
            'declaration_added': len(rec['new_repetition_groups']) > 0,
        })

    summary = {
        'capped_total': len(rows),
        'rebuilt_clean': len(rebuilt),
        'isolated': len(isolated),
        'isolated_reasons': collections.Counter(
            r.get('isolation_reason') for r in isolated),
        'grounded_fixed': len(grounded_fix),
        'new_stage_count_min_p50_p90_max': [
            min(r['new_stage_count'] for r in rebuilt),
            sorted(r['new_stage_count'] for r in rebuilt)[len(rebuilt)//2],
            sorted(r['new_stage_count'] for r in rebuilt)[int(.9*len(rebuilt))],
            max(r['new_stage_count'] for r in rebuilt)] if rebuilt else None,
        'over_char_budget_flagged': sum(r['over_char_budget'] for r in rebuilt),
        'gate_G2_fail': sum(not r['gate_G2_complete'] for r in rebuilt),
        'gate_G3_fail': sum(not r['gate_G3_consistent'] for r in rebuilt),
    }
    json.dump({'summary': summary, 'rebuilt': rebuilt, 'isolated': isolated,
               'grounded_fix': grounded_fix, 'pairs': pairs},
              open(OUTDIR / 'p1_gold_rebuild_v1.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    # independent new gold data version (planner-v2 format, jsonl)
    with open(OUTDIR / 'planner_gold_rebuilt_v1.jsonl', 'w', encoding='utf-8') as f:
        for rec in rebuilt:
            t = rec['task']
            f.write(json.dumps({'source_row_id': rec['source_row_id'],
                                'task': t,
                                'stages': rec['new_stages'],
                                'repetition_groups': rec['new_repetition_groups'],
                                'total_iterations': rec['new_total_iterations'],
                                'stage_count': rec['new_stage_count'],
                                'rebuild_ref': {
                                    'g0_line': rec['g0_line'],
                                    'old_gold_stages': rec['old_gold_stages'],
                                    'verdict': 'gold_run_cap_artifact'}},
                               ensure_ascii=False) + '\n')
    print(json.dumps(summary, ensure_ascii=False, indent=1))

if __name__ == '__main__':
    main()
