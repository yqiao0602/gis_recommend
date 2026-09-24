"""Failure redistribution audit after Round 1 (owner ruling).

Re-converts the full file, but aggregates ONLY failures:
  - failure reason buckets
  - unknown-op frequency, affected chain count, affected token count
Emits the raw distribution; candidate qualification screening happens
next (deterministic intent + typed I/O + slot roles + renderable).
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from route2_training.plans.chain_to_plan_v1_1 import convert  # noqa: E402

SRC = '/home/qy/system_redesign/outputs_v2/gee_b1_stage_data_v1/b1_gee_stage_train.jsonl'
OUT = Path(__file__).resolve().parent / 'failure_redistribution_round1.json'

reason = Counter()
op_freq = Counter()          # unknown op -> token events
op_chains = Counter()        # unknown op -> chains affected
op_tokens_lost = Counter()   # unknown op -> total tokens in affected chains
unknown_per_chain = Counter()
total = 0

with open(SRC, encoding='utf-8') as f:
    for line in f:
        total += 1
        row = json.loads(line)
        plan, rec = convert(row.get('gee_canonical_chain') or '')
        if plan is not None:
            continue
        if rec.get('structural_fail') == 'UNKNOWN_HOST':
            reason['UNKNOWN_HOST'] += 1
            continue
        if rec.get('structural_fail') == 'empty_chain':
            reason['empty_chain'] += 1
            continue
        if rec['unknown_ops']:
            reason['unknown_tokens'] += 1
            n = len(rec['unknown_ops'])
            unknown_per_chain[min(n, 10)] += 1
            for u in set(rec['unknown_ops']):
                op_chains[u] += 1
            for u in rec['unknown_ops']:
                op_freq[u] += 1
                op_tokens_lost[u] += rec['n_tokens']
        else:
            reason['other'] += 1

dist = [r for r in []]  # placeholder no-op
top = []
for op, c in op_freq.most_common(50):
    top.append({'op': op, 'token_events': c, 'affected_chains': op_chains[op],
                'tokens_in_affected_chains': op_tokens_lost[op]})
out = {'total': total, 'failure_reasons': dict(reason),
       'unknown_ops_distinct': len(op_freq),
       'unknown_per_chain_capped10': dict(unknown_per_chain),
       'top50': top}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
print(json.dumps({k: v for k, v in out.items() if k != 'top50'}, ensure_ascii=False, indent=1))
print('\ntop 40 unknown ops (events | chains):')
for t in top[:40]:
    print(f"  {t['op']:45s} {t['token_events']:6d} | {t['affected_chains']:6d}")
