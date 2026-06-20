#!/usr/bin/env python3
"""Quality analysis of 3k batch samples (40-code expansion)."""
import json, random
from collections import Counter

OLD_25 = {
    'L3_02_01_01','L3_02_02_01','L3_02_02_02','L3_02_02_04','L3_02_02_05','L3_02_02_06',
    'L3_02_03_05','L3_02_04_01','L3_02_05_06','L3_02_05_11','L3_02_05_12',
    'L3_02_06_01','L3_02_06_02','L3_02_06_03','L3_02_07_01',
    'L3_01_02_02','L3_01_02_03','L3_01_02_06','L3_01_03_04',
    'L3_07_04_01','L3_03_01_01','L3_03_02_01','L3_03_04_01','L3_04_01_01','L3_03_03_A'
}

samples = [json.loads(l) for l in open("outputs_v2/_server_batch/api_l3_samples_3k.jsonl", encoding="utf-8") if l.strip()]
print(f"Total: {len(samples)}")

# L3 code distribution
l3_dist = Counter()
for s in samples:
    for c in s["l3_codes"]:
        if c not in ("<START>", "<END>"):
            l3_dist[c] += 1

all_used = set(l3_dist.keys())
new_codes = all_used - OLD_25
old_only = all_used & OLD_25
print(f"L3 codes used: {len(all_used)} total")
print(f"  From old 25: {len(old_only)}")
print(f"  NEW (40-code expansion): {len(new_codes)}")
if new_codes:
    print(f"  New codes: {sorted(new_codes)}")
else:
    print("  ⚠️ NO NEW CODES USED — 40-code expansion had no effect")

# Confidence
confs = [s.get("_llm_confidence") for s in samples if s.get("_llm_confidence") is not None]
if confs:
    print(f"\nConfidence: mean={sum(confs)/len(confs):.2f}  min={min(confs):.2f}  max={max(confs):.2f}")

# Chain lens
lens = []
for s in samples:
    codes = [c for c in s["l3_codes"] if c not in ("<START>", "<END>")]
    lens.append(len(codes))
print(f"Chain len: mean={sum(lens)/len(lens):.1f}  min={min(lens)}  max={max(lens)}")

# L3 distribution
print(f"\nL3 code distribution ({len(l3_dist)} unique):")
for code, n in l3_dist.most_common(40):
    tag = " ★NEW" if code in new_codes else ""
    print(f"  {n:3d}  {code}{tag}")

# Spot-check 5 random
print(f"\n{'='*60}")
print("SPOT-CHECK (5 random):")
print(f"{'='*60}")
random.seed(7)
for s in random.sample(samples, min(5, len(samples))):
    codes = [c for c in s["l3_codes"] if c not in ("<START>", "<END>")]
    name = s.get("_script_name", "?")
    conf = s.get("_llm_confidence", "?")
    reasoning = s.get("_llm_reasoning", "")[:200]
    chain = " -> ".join(codes)
    print(f"\n{name} (conf={conf})")
    print(f"  Chain: {chain}")
    print(f"  LLM:   {reasoning}")
