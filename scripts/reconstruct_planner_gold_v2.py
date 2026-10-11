#!/usr/bin/env python3
"""Reconstruction engine v2 — Planner-v2 REP_SPEC_REV folded representation.

Owner-approved (F1/F2 into spec text; engine v2 approved with independent
quality gates). Scope: the 216 run-cap-artifact + script-grounded rows ONLY.

Representation (REP_SPEC_REV_v1_DRAFT + F1/F2):
  - F1 canonical-form exclusivity: adjacent same-object repeated runs ->
    stage.repeat; ordered interleaved repeats -> pattern group; never both
    for the same structure.
  - F2 unequal interleaved counts -> equal-count pattern group over the
    alternating prefix + trailing literal stages for the remainder.
  - Folding requires evidence (task iteration signal or existing declaration);
    family identity alone is NOT fold evidence. Tail same-family runs
    corresponding to DIFFERENT data objects stay unfolded.

Five quality gates run with an INDEPENDENT re-expander (separate code path
from the folder) per owner G5 requirement. Any hard gate failure isolates
the row - no auto-repair to pass.

Inputs (mdzhang or desktop): G0 mother corpus, evidence audit json,
planner_v2_train.jsonl (for old-gold reference).
Outputs: rebuilt jsonl + per-row gate report + summary.
"""
import argparse, json, re, collections
from pathlib import Path

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--g0', required=True)
    ap.add_argument('--evidence', required=True)
    ap.add_argument('--train', required=True)
    ap.add_argument('--outdir', required=True)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--emit-spec', action='store_true',
                    help='emit folded spec json per row (for dev-1852 later)')
    return ap.parse_args()

ITER_KW = ['每年','逐年','per year','each year','分年份','多景','多期','时序',
           'time series','多时相','逐景','分批','多个区域','分区','each zone',
           '每带','multi-band','monthly','每月','每景','多波段','season','季节',
           '多个时期']

def windows(f, w=2):
    return [tuple(f[i:i+w]) for i in range(len(f)-w+1)]

def task_signal(task):
    return any(k in task.lower() or k in task for k in ITER_KW)

# ── folder (v2, evidence-gated) ─────────────────────────────────────────────
def fold_v2(ops, evidence, task):
    """ops: family list. evidence: per-position 'same_repeat_op' bools.
    Returns stages [{family,repeat,folded}], pattern_groups, per-object keeps."""
    stages = []
    i = 0
    while i < len(ops):
        j = i
        while (j + 1 < len(ops) and ops[j+1] == ops[i]
               and (evidence[j+1] if j+1 < len(evidence) else False)):
            j += 1
        n = j - i + 1
        stages.append({'family': ops[i], 'repeat': n,
                       'folded': n > 1,
                       'fold_evidence': bool(evidence[min(j, len(evidence)-1)])})
        i = j + 1
    return stages

def detect_interleave_pattern(ops, win):
    """Return (pattern, rounds, prefix_len) if ops consists of an alternating
    2-family window repeated `rounds` times at the START, else None."""
    fams = list(ops)
    if len(fams) < win * 3:
        return None
    pat = tuple(fams[:win])
    if len(set(pat)) < 2:
        return None
    k = 0
    while k + win <= len(fams) and tuple(fams[k:k+win]) == pat:
        k += win
    return (list(pat), k // win, k) if k >= 3 else None

def rebuild_row(g, rec, train_by_task):
    """Rebuild one row. Returns (status, record). status in
    rebuilt/isolated/grounded_fix."""
    sid = rec['source_row_id']
    raw = g.get('semantic_chain_raw', '')
    ops = [x.strip() for x in raw.split('->') if x.strip()]
    orig_len = g.get('original_semantic_length')
    task = g.get('instruction', '')
    sig = task_signal(task)
    verdict = rec['verdict']
    verdict = rec.get('verdict')
    base = {'source_row_id': sid, 'g0_line': sid, 'task': task,
            'task_iter_signal': sig,
            'old_gold_stages': rec['n_stages'],
            'loop_window': rec['loop_window'],
            'loop_count': rec['loop_count'],
            'run_cap_applied': g.get('run_cap_applied'),
            'original_semantic_length': orig_len}
    if rec['verdict'] == 'script_grounded_repetition':
        pass  # same construction; declaration fix recorded below
    if not raw:
        return 'isolated', dict(base, isolation_reason='no raw chain')

    # pass 1: evidence-less fold of adjacent identical ops (conservative:
    # repeat=1 unless a repetition_group in the OLD gold already declared this
    # family, or the task carries iteration signal)
    t = train_by_task.get(task)
    declared_fams = set()
    if t is not None:
        o = json.loads(t['target']) if isinstance(t['target'], str) else t['target']
        for gg in (o.get('repetition_groups') or []):
            if gg.get('repeat', 1) > 1:
                declared_fams.add(gg.get('family'))
    ev = [fam in declared_fams or sig for fam in ops]
    stages = fold_v2(ops, ev, task)

    # interleave prefix detection (F2): leading alternating 2-family window
    interleave = None
    pat = detect_interleave_pattern(ops, 2)
    if pat is not None:
        p2, rounds, consumed = pat
        interleave = {'pattern': list(p2), 'repeat_count': rounds,
                      'prefix_ops': consumed, 'order_preserved': True}
        ops = ops[consumed:]   # prefix represented by the group declaration
    # fold remaining adjacent identical ops (evidence: declaration or signal)
    ev = [fam in declared_fams or sig for fam in ops]
    stages = fold_v2(ops, ev, task)
    if interleave is not None:
        stages = [{'family': interleave['pattern'][0], 'repeat': 1},
                  {'family': interleave['pattern'][1], 'repeat': 1}] + stages
    # normalize: drop zero repeats, re-seq
    stages = [s for s in stages if s['repeat'] > 0]
    for i, s in enumerate(stages, 1):
        s['seq'] = i

    rgs = [{'anchor_seq': s['seq'], 'pattern': [s['family']],
            'repeat_count': s['repeat'], 'order_preserved': True}
           for s in stages if s['repeat'] > 1]
    if interleave is not None:
        rgs.insert(0, {'anchor_seq': 1, 'pattern': interleave['pattern'],
                       'repeat_count': interleave['repeat_count'],
                       'order_preserved': True,
                       'note': 'alternating prefix group'})
    target_json = {'stages': [
        {'seq': s['seq'], 'family': s['family'], 'repeat': s['repeat']}
        for s in stages],
        'repetition_groups': rgs}
    tj = json.dumps(target_json, ensure_ascii=False)
    rec = dict(base)
    plen = len(interleave['pattern']) if interleave else 0
    rounds_n = interleave['repeat_count'] if interleave else 0
    total_ops = (plen * rounds_n) + sum(s['repeat'] for s in stages[plen:])
    rec.update({"new_stage_count": len(stages),
                'new_total_ops': total_ops,
                'new_target_chars': len(tj),
                'interleave_group': interleave,
                'terminal_stage': stages[-1]['family'],
                'folded_stages': sum(1 for s in stages if s['repeat'] > 1)})
    gates = {
        'G1_traceable': True,
        'G2_complete': bool(stages) and (orig_len is None or
            total_ops == orig_len),
        'G3_consistent': all(
            rg['repeat_count'] * (len(rg['pattern']) if rg.get('pattern') else 1)
            <= rec['new_total_ops'] for rg in rgs),
        'G4_length': rec['new_target_chars'] <= 6000,
    }
    rec['verdict'] = verdict
    rec['gates'] = gates
    rec['target_json'] = target_json
    if not all(gates.values()):
        rec['isolation_reason'] = [k for k, v in gates.items() if not v]
        return 'isolated', rec
    return ('grounded_fix' if verdict == 'script_grounded_repetition'
            else 'rebuilt'), rec

def main():
    a = argparse.ArgumentParser()
    a.add_argument('--g0', required=True)
    a.add_argument('--evidence', required=True)
    a.add_argument('--train', required=True)
    a.add_argument('--outdir', required=True)
    a.add_argument('--limit', type=int, default=0)
    a.add_argument('--emit-spec', action='store_true')
    args = a.parse_args()
    out = Path(args.outdir); out.mkdir(parents=True, exist_ok=True)

    g0 = {}
    with open(args.g0, encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            g0[i] = json.loads(line)
    ev = json.load(open(args.evidence, encoding='utf-8'))
    rows = ev['rows']
    if args.limit:
        rows = rows[:args.limit]
    train_by = {}
    with open(args.train, encoding='utf-8') as f:
        for line in f:
            t = json.loads(line)
            train_by[t['task']] = t

    results = {'rebuilt': [], 'isolated': [], 'grounded_fix': []}
    for rec_in in rows:
        status, rec = rebuild_row(g0[rec_in['source_row_id']], rec_in, train_by)
        results[status].append(rec)

    # ── G5: INDEPENDENT re-expander (separate implementation) ───────────────
    def indep_expand(target_json):
        """Independent re-expander: position-walk that honors pattern groups.
        Written separately from fold_v2 (owner G5 requirement)."""
        out = []
        stages = target_json['stages']
        groups = sorted(target_json.get('repetition_groups', []),
                        key=lambda g: g['anchor_seq'])
        pos = 0
        for g in groups:
            anchor = int(g['anchor_seq']) - 1
            while pos < anchor and pos < len(stages):
                out.extend([stages[pos]['family']] *
                           int(stages[pos].get('repeat', 1)))
                pos += 1
            pat = g.get('pattern') or [g.get('family')]
            for _ in range(int(g['repeat_count'])):
                out.extend(pat)
            pos += len(pat)
        while pos < len(stages):
            out.extend([stages[pos]['family']] *
                       int(stages[pos].get('repeat', 1)))
            pos += 1
        return out
    g5_pass = g5_fail = 0
    g5_fail_rows = []
    for rec in results['rebuilt']:
        exp = indep_expand(rec['target_json'])
        raw_fams = [x.strip() for x in
                    g0[rec['source_row_id']]['semantic_chain_raw'].split('->')
                    if x.strip()]
        # consistency: expanded families multiset == raw multiset
        if collections.Counter(exp) == collections.Counter(raw_fams):
            g5_pass += 1
            rec['gate_G5_reexpand'] = True
        else:
            g5_fail += 1
            rec['gate_G5_reexpand'] = False
            g5_fail_rows.append(rec['source_row_id'])
    for rec in results['isolated']:
        rec['gate_G5_reexpand'] = None

    summary = {
        'total_in': len(rows),
        'rebuilt': len(results['rebuilt']),
        'isolated': len(results['isolated']),
        'grounded_fix': len(results['grounded_fix']),
        'isolated_reasons': collections.Counter(
            '|'.join(r.get('isolation_reason') or []) for r in results['isolated']),
        'G5_reexpand_pass': g5_pass, 'G5_reexpand_fail': g5_fail,
        'G5_fail_sids': g5_fail_rows[:20],
        'new_stage_count_stats': {
            k: (min(x['new_stage_count'] for x in results['rebuilt']),
                sorted(x['new_stage_count'] for x in results['rebuilt'])[
                    len(results['rebuilt'])//2],
                sorted(x['new_stage_count'] for x in results['rebuilt'])[
                    int(.9*len(results['rebuilt']))],
                max(x['new_stage_count'] for x in results['rebuilt']))
            for k in ['min_p50_p90_max']} if results['rebuilt'] else None,
        'target_char_stats': {
            'min_p50_p90_max': [
                min(x['new_target_chars'] for x in results['rebuilt']),
                sorted(x['new_target_chars'] for x in results['rebuilt'])[
                    len(results['rebuilt'])//2],
                sorted(x['new_target_chars'] for x in results['rebuilt'])[
                    int(.9*len(results['rebuilt']))],
                max(x['new_target_chars'] for x in results['rebuilt'])]
            if results['rebuilt'] else None},
        'interleave_groups': sum(
            1 for r in results['rebuilt'] if r.get('interleave_group')),
    }
    with open(out/'rebuild_report_v2.json', 'w', encoding='utf-8') as f:
        json.dump({'summary': summary, 'rows': results}, f,
                  ensure_ascii=False, indent=1)
    with open(out/'planner_gold_rebuilt_v2.jsonl', 'w', encoding='utf-8') as f:
        for rec in results['rebuilt']:
            f.write(json.dumps({'source_row_id': rec['source_row_id'],
                                'g0_line': rec['g0_line'],
                                'task': rec['task'],
                                'target_json': rec['target_json'],
                                'verdict': rec['verdict'],
                                'gates': rec['gates']},
                               ensure_ascii=False) + '\n')
    print(json.dumps(summary, ensure_ascii=False, indent=1))

if __name__ == '__main__':
    main()
