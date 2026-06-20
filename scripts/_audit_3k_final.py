#!/usr/bin/env python3
"""Full quality audit of 3k batch final results."""
import json, random
from collections import Counter

OLD_25 = {'L3_02_01_01','L3_02_02_01','L3_02_02_02','L3_02_02_04','L3_02_02_05','L3_02_02_06','L3_02_03_05','L3_02_04_01','L3_02_05_06','L3_02_05_11','L3_02_05_12','L3_02_06_01','L3_02_06_02','L3_02_06_03','L3_02_07_01','L3_01_02_02','L3_01_02_03','L3_01_02_06','L3_01_03_04','L3_07_04_01','L3_03_01_01','L3_03_02_01','L3_03_04_01','L3_04_01_01','L3_03_03_A'}

samples = [json.loads(l) for l in open("outputs_v2/_server_batch/api_l3_3k_final.jsonl", encoding="utf-8") if l.strip()]
print(f"=== 3k FINAL REPORT ===\n")
print(f"Total kept: {len(samples)}")

# ── 1. L3 code distribution ──
l3_dist = Counter()
for s in samples:
    for c in s["l3_codes"]:
        if c not in ("<START>", "<END>"): l3_dist[c] += 1

all_used = set(l3_dist.keys())
new_codes = all_used - OLD_25
print(f"\n--- L3 Coverage ---")
print(f"Unique codes: {len(all_used)} ({len(new_codes)} new from 40)")
print(f"New codes used: {sorted(new_codes) if new_codes else 'NONE'}")

confs = [s.get("_llm_confidence") for s in samples if s.get("_llm_confidence") is not None]
lens = [len([c for c in s["l3_codes"] if c not in ("<START>","<END>")]) for s in samples]
print(f"\n--- Aggregate Stats ---")
print(f"Confidence: mean={sum(confs)/len(confs):.2f}  min={min(confs):.2f}  max={max(confs):.2f}")
print(f"Chain len: mean={sum(lens)/len(lens):.1f}  min={min(lens)}  max={max(lens)}")

# ── 2. Confidence tail ──
print(f"\n--- Confidence Tail (0.50-0.55) ---")
tail = [s for s in samples if s.get("_llm_confidence") is not None and 0.50 <= s["_llm_confidence"] <= 0.55]
print(f"Count: {len(tail)}/{len(samples)} ({100*len(tail)/len(samples):.0f}%)")
for i, s in enumerate(tail[:10]):
    codes = [c for c in s["l3_codes"] if c not in ("<START>","<END>")]
    print(f"  [{i+1}] {s['_script_name']} conf={s['_llm_confidence']} chain={' -> '.join(codes)}")
    print(f"       LLM: {(s.get('_llm_reasoning','') or '')[:120]}")

# ── 3. L3 distribution ──
print(f"\n--- L3 Code Distribution ({len(l3_dist)} codes) ---")
for code, n in l3_dist.most_common(50):
    tag = " ★NEW" if code in new_codes else ""
    bar = "█" * min(n, 50)
    print(f"  {n:4d}  {code}{tag}")

# ── 4. Spot-check 15 ──
print(f"\n{'='*60}")
print("SPOT-CHECK 15 (5 random + 5 low conf + 5 high conf)")
print(f"{'='*60}")
random.seed(42)
rand5 = random.sample(samples, min(5, len(samples)))
low5 = sorted(samples, key=lambda s: s.get("_llm_confidence", 0.5))[:5]
high5 = sorted(samples, key=lambda s: s.get("_llm_confidence", 0.5), reverse=True)[:5]

for label, group in [("RANDOM", rand5), ("LOW-CONF", low5), ("HIGH-CONF", high5)]:
    print(f"\n--- {label} ---")
    for s in group:
        codes = [c for c in s["l3_codes"] if c not in ("<START>","<END>")]
        conf = s.get("_llm_confidence", "?")
        reasoning = s.get("_llm_reasoning", "") or ""
        print(f"  [{conf}] {s['_script_name']}: {' -> '.join(codes)}")
        print(f"        {reasoning[:150]}")

# ── 5. Dedup check (internal) ──
chains = Counter()
for s in samples:
    key = tuple(c for c in s["l3_codes"] if c not in ("<START>","<END>"))
    chains[key] += 1
dup_chains = {k: v for k, v in chains.items() if v > 1}
print(f"\n--- Internal Dedup ---")
print(f"Unique chains: {len(chains)}/{len(samples)} ({100*len(chains)/len(samples):.0f}%)")
if dup_chains:
    print(f"Duplicate chains: {len(dup_chains)}")
    for chain, count in sorted(dup_chains.items(), key=lambda x: -x[1])[:10]:
        print(f"  {count}x  {' -> '.join(chain)}")
