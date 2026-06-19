#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bulk LLM L3 generation from yll's facts_summary descriptions.

For descriptions that have NO extracted QGIS chain (the 17k that use C++ APIs),
deepseek-chat generates L3 codes directly from the task description.
Output: labeled_workflows-schema training samples ready to merge.

Usage:
    python scripts/llm_generate_l3_from_facts.py --facts <facts.csv> --out <samples.jsonl> [--max N]
Requires: DEEPSEEK_API_KEY env var.
"""
from __future__ import annotations

import argparse, csv, json, os, re, sys, time
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]; SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
from gis_recommend.data.vector_training_builder import to_training_sample
from openai import OpenAI

DEFAULT_VOCAB = ROOT / "outputs_v2" / "l3_vocab_v2.json"
DEFAULT_TASK_VOCAB = ROOT / "outputs_v2" / "pipeline" / "step8_quality_gate" / "task_type_vocabulary_v4_quality_gate.json"

VECTOR_L3_CODES = """L3_02_01_01:Buffer
L3_02_02_01:Intersect
L3_02_02_02:Union
L3_02_02_04:Erase
L3_02_02_05:Symmetrical Difference
L3_02_02_06:Clip
L3_02_03_05:Collect Features/Dissolve
L3_02_04_01:Spatial Join
L3_02_05_06:Split Line at Point
L3_02_05_11:Feature to Point/Centroid
L3_02_05_12:Minimum Bounding Geometry
L3_02_06_01:Select by Attribute
L3_02_06_02:Extract by Attribute
L3_02_06_03:Extract by Location
L3_02_07_01:Multipart to Singlepart/Geometry Fix/Simplify
L3_01_02_02:Delete Field
L3_01_02_03:Reproject
L3_01_02_06:Field Calculate
L3_01_03_04:Merge
L3_07_04_01:Export Data
L3_03_01_01:Clip Raster
L3_03_02_01:Zonal Statistics
L3_03_04_01:Reclassify"""

PROMPT = """Pick L3 codes for this GIS task:
Description: {desc}
Task type: {task_type}

Available codes:
{codes}

Output ONLY: {{"l3_codes":["L3_XX_XX_XX",...],"confidence":0.9}}
2-8 codes, logical order. Return ONLY valid JSON."""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--facts", required=True, help="Path to facts_summary1000.csv")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max", type=int, default=0, help="Max samples to process (0=all)")
    ap.add_argument("--min-desc-len", type=int, default=80, help="Min description chars")
    ap.add_argument("--sleep", type=float, default=0.2, help="Sleep between calls")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    vocab = json.loads(args.vocab.read_text(encoding="utf-8")) if hasattr(args, 'vocab') else \
            json.loads(DEFAULT_VOCAB.read_text(encoding="utf-8"))
    all_codes = set((vocab if isinstance(vocab, dict) else {}).get("code_to_id", vocab).keys())
    code_to_id = vocab.get("code_to_id", vocab)
    special = vocab.get("special_tokens", {"<START>": -3, "<END>": -4})
    tt2id = json.loads(DEFAULT_TASK_VOCAB.read_text(encoding="utf-8"))["task_type_to_id"]

    # load descriptions
    samples = []
    with open(args.facts, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            desc = (row.get("Task Description") or "").strip()
            if len(desc) < args.min_desc_len: continue
            samples.append({
                "task_type": (row.get("Task Type") or "").strip(),
                "task_name": (row.get("Task Name") or "").strip(),
                "task_description": desc,
            })
    if args.max: samples = samples[:args.max]
    print(f"{len(samples)} descriptions loaded")

    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LLM_API_KEY", "")
    client = OpenAI(base_url="https://api.deepseek.com/v1", api_key=api_key, timeout=90)

    st = Counter(); all_out = []
    for i, s in enumerate(samples):
        prompt = PROMPT.format(desc=s["task_description"][:500], task_type=s["task_type"], codes=VECTOR_L3_CODES)
        st["attempt"] += 1
        if args.dry_run:
            print(f"[{i+1}] {s['task_name'][:50]}... DRY"); continue

        try:
            r = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}], temperature=0.2, max_tokens=600)
            content = (r.choices[0].message.content or "").strip()
            content = re.sub(r"^```\w*\n?|```$", "", content).strip()
            m = re.search(r"\{.*\}", content, re.DOTALL)
            if m: content = m.group(0)
            obj = json.loads(content)
            l3_codes = obj.get("l3_codes", [])
            st["llm_ok"] += 1
        except Exception as e:
            st["llm_fail"] += 1; time.sleep(1); continue

        if not l3_codes or not all(c in all_codes for c in l3_codes):
            st["bad_l3"] += 1; continue

        described = {"optional_l3_sequence": l3_codes, "task_description_en": s["task_description"],
                     "qgis_ops": [], "operator_names": [], "source": "llm_l3_from_facts"}
        tt = s["task_type"] if s["task_type"] in tt2id else "Other / Sparse"
        ts = to_training_sample(described, code_to_id=code_to_id, special_tokens=special, task_type=tt, task_type_to_id=tt2id)
        if ts is None: st["builder_drop"] += 1; continue
        ts["task_metadata"]["task_name"] = s["task_name"]
        all_out.append(ts); st["kept"] += 1

        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(samples)}  kept={st['kept']}  llm_ok={st['llm_ok']}")
        time.sleep(args.sleep)

    if not args.dry_run:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            for ts in all_out: f.write(json.dumps(ts, ensure_ascii=False) + "\n")

    print(f"\n DONE : {st['attempt']} attempts, kept={st['kept']} ({100*st['kept']/max(st['attempt'],1):.0f}%)")
    print(f" llm_ok={st['llm_ok']} llm_fail={st['llm_fail']} bad_l3={st['bad_l3']} builder_drop={st['builder_drop']}")
    print(f" -> {args.out}")


if __name__ == "__main__":
    main()
