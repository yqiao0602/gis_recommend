#!/usr/bin/env python3
"""Merge 2k + 3k batches, deduplicate by L3 chain, report final count."""
import json
from collections import Counter

def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]

def chain_key(s):
    return tuple(c for c in s["l3_codes"] if c not in ("<START>", "<END>"))

# Load both batches
b2k = load("outputs_v2/_server_batch/api_l3_2k_final.jsonl")
b3k = load("outputs_v2/_server_batch/api_l3_3k_final.jsonl")
print(f"2k batch: {len(b2k)}  |  3k batch: {len(b3k)}  |  raw sum: {len(b2k)+len(b3k)}")

# Merge with dedup: keep highest confidence version of each unique chain
seen = {}  # chain_key -> (sample, confidence)
skipped_dup = 0
all_samples = []

for s in b2k + b3k:
    key = chain_key(s)
    conf = s.get("_llm_confidence") or 0.5
    if key in seen:
        old_conf = seen[key][1]
        if conf > old_conf:
            seen[key] = (s, conf)  # replace with higher-conf version
        skipped_dup += 1
    else:
        seen[key] = (s, conf)

print(f"Merged unique: {len(seen)}  |  Duplicates skipped: {skipped_dup}")

# Stats on merged set
merged = [s for s, _ in seen.values()]
confs = [s.get("_llm_confidence") for s in merged if s.get("_llm_confidence")]
l3_dist = Counter()
for s in merged:
    for c in chain_key(s): l3_dist[c] += 1

print(f"Confidence: mean={sum(confs)/len(confs):.2f}  min={min(confs):.2f}  max={max(confs):.2f}")
print(f"L3 codes: {len(l3_dist)} unique")
print(f"\nL3 distribution:")
for code, n in l3_dist.most_common(30):
    print(f"  {n:4d}  {code}")

# Source breakdown
sources = Counter()
for s in merged:
    sources[s.get("source_original", s.get("source", "?"))] += 1
print(f"\nSources: {dict(sources)}")

# Save merged
out_path = "outputs_v2/_server_batch/api_l3_merged_2k3k.jsonl"
with open(out_path, "w", encoding="utf-8") as f:
    for s in merged:
        f.write(json.dumps(s, ensure_ascii=False) + "\n")
print(f"\nMerged file: {out_path}")
print(f"Final: 2k({len(b2k)}) + 3k({len(b3k)}) → dedup → {len(merged)} unique chains")
