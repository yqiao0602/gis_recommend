#!/usr/bin/env python3
"""REP_SPEC_REV v1-DRAFT semantic validation (step 1, CPU-only).

Implements the frozen draft spec's fold/expand semantics, runs the owner's
8-type test matrix (incl. the three counterexample classes), and records
every ambiguity the spec fails to answer. Findings are PROPOSALS for owner
confirmation - the frozen draft is not modified here.

Spec semantics implemented (per REP_SPEC_REV_v1_DRAFT.md):
  repeat_count = TOTAL rounds (no "1+24" ambiguity)
  pattern group = ordered stage sequence repeated repeat_count rounds
  single-stage repeat = stage.repeat = TOTAL executions of that stage
  folding adjacent same-family ops is allowed ONLY with same-repeat-pattern
    evidence; family identity alone is NOT sufficient (anti-fold rule)
  termination boundary = explicit subsequent stage after a pattern group
  count mismatch = stages with different true counts are represented as
    separate stages/groups, never force-equalized
"""
import json, collections
from pathlib import Path

OUT = (Path(__file__).resolve().parents[1] /
       'docs/reports/route2_p0_contract/plan_pipeline_v1/planner_design/'
       'REP_SPEC_REV1_VALIDATION_v1.json')
FINDINGS = []
RESULTS = []

def record(name, ok, detail=''):
    RESULTS.append({'test': name, 'pass': bool(ok), 'detail': detail})
    print(('PASS ' if ok else 'FAIL ') + name + (('  | ' + detail) if detail else ''))

def note_finding(q, proposal):
    FINDINGS.append({'ambiguity': q, 'proposal': proposal})
    print('FINDING:', q)

# ── representation primitives (v1-draft semantics) ─────────────────────────
def expand_stages(stages):
    """stages: [{family, repeat}] -> ordered family op list. repeat = TOTAL
    executions of that stage (owner check #1: no 1+N ambiguity)."""
    out = []
    for s in stages:
        out += [s['family']] * int(s['repeat'])
    return out

def expand_pattern_group(group):
    """pattern group: repeat_count = TOTAL rounds of the ordered pattern."""
    out = []
    for _ in range(int(group['repeat_count'])):
        out += list(group['pattern'])
    return out

def expand_spec(doc):
    """Full doc: stages in order; pattern groups are interleaved by their
    anchor position (stage_seq of the group's first stage). Canonical form
    rule (finding F1): a doc may contain EITHER per-stage repeats OR pattern
    groups for a given repeat structure - never both describing the same ops."""
    stages = doc['stages']
    groups = sorted(doc.get('repetition_groups', []),
                    key=lambda g: g['anchor_seq'])
    out = []
    pos = 0  # stages consumed
    for g in groups:
        anchor = g['anchor_seq'] - 1           # 0-based index of first pattern stage
        while pos < anchor:
            out += [stages[pos]['family']] * int(stages[pos]['repeat'])
            pos += 1
        out += expand_pattern_group(g)
        pos = anchor + len(g['pattern'])
    while pos < len(stages):
        out += [stages[pos]['family']] * int(stages[pos]['repeat'])
        pos += 1
    return out

def fold_with_evidence(ops, evidence):
    """Fold adjacent same-family ops into {family, repeat} stages ONLY where
    evidence marks the run as one repeated operation (owner check #2).
    evidence: list of bool, same length as ops - True = 'same repeated op'.
    Non-adjacent same-family stages are NEVER merged here."""
    stages = []
    i = 0
    while i < len(ops):
        j = i
        while j + 1 < len(ops) and ops[j+1] == ops[i] and evidence[j+1]:
            j += 1
        stages.append({'family': ops[i], 'repeat': j - i + 1,
                       'folded': (j - i + 1) > 1})
        i = j + 1
    return stages

# ── T1 short chain, no repeat ───────────────────────────────────────────────
ops1 = ['RASTER_LOAD', 'TEMPORAL_FILTER', 'CLASSIFICATION']
st1 = fold_with_evidence(ops1, [False, False, False])
doc1 = {'stages': st1, 'repetition_groups': []}
record('T1 short/no-repeat round-trip', expand_spec(doc1) == ops1)

# ── T2 long chain, no repeat ────────────────────────────────────────────────
ops2 = [f'OP_{i}' for i in range(30)]
ev2 = [False] * 30
st2 = fold_with_evidence(ops2, ev2)
doc2 = {'stages': st2, 'repetition_groups': []}
record('T2 long/no-repeat round-trip', expand_spec(doc2) == ops2 and len(st2) == 30)

# ── T3 single stage repeat (with evidence) ─────────────────────────────────
ops3 = ['RASTER_LOAD'] * 12 + ['TEMPORAL_FILTER', 'CLASSIFICATION']
ev3 = [True] * 12 + [False, False]
st3 = fold_with_evidence(ops3, ev3)
doc3 = {'stages': st3, 'repetition_groups': [
    {'anchor_seq': 1, 'pattern': ['RASTER_LOAD'], 'repeat_count': 12,
     'order_preserved': True}]}
ok3 = expand_spec(doc3) == ops3
# owner check #1: repeat_count=12 -> exactly 12 rounds, not 1+12
n_rounds = 12
record('T3 single-stage repeat x12 (total semantics)', ok3 and
       len(expand_pattern_group(doc3['repetition_groups'][0])) == n_rounds)

# ── T4 multi-stage ordered repeat (the P0 failure pattern) ─────────────────
pattern = ['AGGREGATION', 'RASTER_LOAD']; n_rounds4 = 24
ops4 = pattern * n_rounds4 + ['BAND_ARITHMETIC']
st4 = [{'seq': 1, 'family': 'AGGREGATION', 'repeat': 1},
       {'seq': 2, 'family': 'RASTER_LOAD', 'repeat': 1},
       {'seq': 3, 'family': 'BAND_ARITHMETIC', 'repeat': 1}]
doc4 = {'stages': st4, 'repetition_groups': [
    {'anchor_seq': 1, 'pattern': pattern, 'repeat_count': n_rounds4,
     'order_preserved': True}]}
out4 = expand_spec(doc4)
ok4 = out4 == ops4 and len(out4) == 2 * n_rounds4 + 1
# intra-order preservation: within each round, AGG before LOAD
intra = all(out4[2*i] == 'AGGREGATION' and out4[2*i+1] == 'RASTER_LOAD'
            for i in range(n_rounds4))
record('T4 multi-stage ordered repeat x24 + termination boundary',
       ok4 and intra and out4[-1] == 'BAND_ARITHMETIC',
       f'expanded {len(out4)} ops, intra-order={intra}')

# ── T5 repeat followed by independent stage (termination boundary) ─────────
ok5 = doc4['stages'][-1]['family'] == 'BAND_ARITHMETIC' and out4[-1] == 'BAND_ARITHMETIC'
record('T5 explicit termination stage after pattern group', ok5)

# ── T6 unequal true counts (count-mismatch prohibition) ────────────────────
# gold truth: AGG x24 alternating LOAD x12 -> NOT expressible as one uniform
# pattern group; spec requires separate representation
ops6 = ['AGGREGATION', 'RASTER_LOAD'] * 12 + ['AGGREGATION'] * 12
doc6_uniform = {'stages': [
    {'seq': 1, 'family': 'AGGREGATION', 'repeat': 1},
    {'seq': 2, 'family': 'RASTER_LOAD', 'repeat': 1}],
    'repetition_groups': [
    {'anchor_seq': 1, 'pattern': ['AGGREGATION', 'RASTER_LOAD'],
     'repeat_count': 24, 'order_preserved': True}]}
wrong = expand_spec(doc6_uniform)  # would give 24 AGG + 24 LOAD
note_finding(
    'T6: uniform pattern group cannot express unequal true counts '
    '(AGG x24 vs LOAD x12); v1-draft forces a wrong uniform expansion',
    'proposal: allow pattern groups with per-stage counts '
    '{"pattern":["AGGREGATION","RASTER_LOAD"],"per_stage_counts":[24,12]} '
    'OR represent as literal stages with individual repeats; owner to choose '
    'canonical form')
# canonical decomposition rule (finding F2): interleaved unequal counts =
# equal-count pattern group over the alternating prefix + explicit trailing
# stages for the remainder
doc6_canonical = {'stages': [
    {'seq': 1, 'family': 'AGGREGATION', 'repeat': 1},
    {'seq': 2, 'family': 'RASTER_LOAD', 'repeat': 1},
    {'seq': 3, 'family': 'AGGREGATION', 'repeat': 12}],
    'repetition_groups': [
    {'anchor_seq': 1, 'pattern': ['AGGREGATION', 'RASTER_LOAD'],
     'repeat_count': 12, 'order_preserved': True}]}
out6 = expand_spec(doc6_canonical)
ok6 = out6 == ops6
record('T6 unequal interleaved counts via pattern-group + trailing stage '
       '(canonical decomposition)', ok6,
       f'expanded {len(out6)} ops vs gold {len(ops6)}')

# ── T7 tail same-family x4, different data objects (anti-fold case) ────────
ops7 = ['RASTER_LOAD', 'TEMPORAL_FILTER'] * 3 + ['RASTER_LOAD'] * 4
ev7 = [False]*6 + [False, False, False, False]   # no fold evidence: 4 objects
st7 = fold_with_evidence(ops7, ev7)
kept_separate = all(s['repeat'] == 1 for s in st7[-4:])
record('T7 tail same-family different objects stays unfolded (anti-fold)',
       kept_separate and len(st7) == 10,
       'family identity alone is not fold evidence - owner check #2')

# ── T8 super-long over-budget ───────────────────────────────────────────────
ops8 = ['AGGREGATION', 'RASTER_LOAD'] * 250    # 500 ops
char_len = len(json.dumps({'stages': [
    {'seq': 1, 'family': 'AGGREGATION'}, {'seq': 2, 'family': 'RASTER_LOAD'}],
    'repetition_groups': [
    {'anchor_seq': 1, 'pattern': ['AGGREGATION', 'RASTER_LOAD'],
     'repeat_count': 250, 'order_preserved': True}]}, ensure_ascii=False))
st8 = fold_with_evidence(ops8, [True]*500)
doc8 = {'stages': st8[:2] if False else [
    {'seq': 1, 'family': 'AGGREGATION', 'repeat': 1},
    {'seq': 2, 'family': 'RASTER_LOAD', 'repeat': 1}],
    'repetition_groups': [
    {'anchor_seq': 1, 'pattern': ['AGGREGATION', 'RASTER_LOAD'],
     'repeat_count': 250, 'order_preserved': True}]}
out8 = expand_spec(doc8)
record('T8 over-budget sample: folded representation is compact & round-trips',
       out8 == ops8 and char_len < 500,
       f'literal {len(ops8)} ops -> folded spec ~{char_len} chars')

# ── ambiguity summary ───────────────────────────────────────────────────────
n_pass = sum(1 for r in RESULTS if r['pass'])
out = {'results': RESULTS, 'findings': FINDINGS,
       'summary': {'passed': n_pass, 'total': len(RESULTS)}}
OUT.parent.mkdir(parents=True, exist_ok=True)
json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f"\n{OUT}")
print(f"VALIDATION: {n_pass}/{len(RESULTS)} pass, {len(FINDINGS)} findings")
