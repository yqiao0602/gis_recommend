# -*- coding: utf-8 -*-
"""
LLM-assisted audit of GEE auto-remapped entries that are NOT in SKIP and NOT
in MANUAL_OVERRIDES.  Top 41-200 covers 12% of training signal; at ~15%
observed error rate that's ~2% noise left in training.  This script proposes
corrections for human review, same shape as audit_qgis_mappings_llm.py.

Output: outputs_v2/gee_auto_mapping_llm_proposals.json
"""
from __future__ import annotations
import csv
import json
import os
import time
from collections import Counter
from pathlib import Path

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
HIER_V2 = ROOT / "outputs_v2" / "classification_hierarchy_v2.csv"
MAPPING_V2 = ROOT / "outputs_v2" / "mapping_metadata_v2.json"
SKIP_V2 = ROOT / "outputs_v2" / "gee_skip_list_v2.json"
GEE_OPS_JSON = ROOT.parent / "operators-json" / "gee_operators.json"
OLD_WF = ROOT / "outputs" / "pipeline" / "step8" / "labeled_workflows_l3_v4_cleaned.json"
OUT = ROOT / "outputs_v2" / "gee_auto_mapping_llm_proposals.json"

API_KEY = os.environ.get("DASHSCOPE_API_KEY", "sk-6d6a3478844243979fd29431ce31a841")
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen-plus"

TARGET_FREQ_LIMIT = 200  # only audit ops in top-N by training frequency

SYSTEM_PROMPT_TEMPLATE = """You are a GIS operator taxonomist.  Given a Google Earth Engine (GEE) operator call and its description, pick the 3 best-matching L3 primitive codes from the catalog.  Prefer semantic fit over surface word overlap.

IMPORTANT: GEE-specific pitfalls:
  - `.map()` / `.iterate()` are container/higher-order functions, not operations.
  - `ee.Filter.*` objects are predicates (arguments to filter()), not ops.
  - `ee.Reducer.*` objects are reducer definitions, not ops.
  - getters/setters like `.get()` / `.set()` / `.projection()` return metadata.
  If the operator is one of these, its best match is a SKIP token — set l3_code="SKIP".

L3 CATALOG (94 v2 primitives, code | name | [L2/L1] | description):
{catalog}

Response format: strict JSON, single key "top3" with 3 objects {{l3_code, name, confidence, reason}}.  Use l3_code="SKIP" for non-ops.  confidence is 0..1.  reason max 15 words.  No markdown, no prose outside JSON."""

USER_PROMPT = """GEE operator: {name}
Training frequency: {freq}
Description: {desc}
Existing mapping (auto-remap, may be wrong): {current_l3} {current_name}
"""


def load_l3_catalog() -> tuple[str, dict[str, str]]:
    rows, name_map = [], {}
    for r in csv.DictReader(HIER_V2.open(encoding="utf-8")):
        rows.append(f"  {r['l3_code']}  |  {r['l3_name']}  |  [{r['l2_name']} / {r['l1_name']}]  |  {r.get('l3_description','')[:150]}")
        name_map[r["l3_code"]] = r["l3_name"]
    return "\n".join(rows), name_map


def load_gee_desc() -> dict[str, str]:
    out = {}
    with GEE_OPS_JSON.open(encoding="utf-8") as f:
        data = json.load(f)
    for cat, ops in data.items():
        for op in ops:
            nm = (op.get("name") or "").lower().strip()
            if nm:
                out[nm] = op.get("description", "") or ""
    return out


def compute_op_freq() -> Counter:
    c = Counter()
    with OLD_WF.open(encoding="utf-8") as f:
        wfs = json.load(f)["labeled_workflows"]
    for wf in wfs:
        for op in wf.get("operator_sequence", []) or []:
            if isinstance(op, str):
                c[op] += 1
    return c


def call_llm(client: OpenAI, system_prompt: str, name: str, freq: int,
             desc: str, current_l3: str, current_name: str) -> dict:
    r = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": USER_PROMPT.format(
                name=name, freq=freq, desc=desc[:400],
                current_l3=current_l3, current_name=current_name,
            )},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
        max_tokens=350,
    )
    return json.loads(r.choices[0].message.content)


def main():
    catalog, name_map = load_l3_catalog()
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(catalog=catalog)

    freq = compute_op_freq()
    top_ops = [op for op, _ in freq.most_common(TARGET_FREQ_LIMIT)]

    with MAPPING_V2.open(encoding="utf-8") as f:
        gee_v2 = json.load(f)["gee_to_l3"]
    with SKIP_V2.open(encoding="utf-8") as f:
        skip_set = set(json.load(f)["skip_operators"])

    manual_set = {op.lower() for op, m in gee_v2.items()
                  if m.get("source") == "manual_override"}
    # Case-insensitive lookup — auto-remapped entries keep v1 camelCase keys,
    # but training tokens are always lowercase.
    gee_v2_ci = {k.lower(): k for k in gee_v2}
    gee_desc = load_gee_desc()

    # Ops to audit: top_ops minus SKIP minus MANUAL
    to_audit = []
    for op in top_ops:
        op_lower = op.lower()
        if op_lower in skip_set:
            continue
        if op_lower in manual_set:
            continue
        if op_lower in gee_v2_ci:
            to_audit.append((op, freq[op]))
        # else: unmapped, skip audit (step6 leaves as <UNK>)

    print(f"GEE Top-{TARGET_FREQ_LIMIT} auto-mapped ops to audit: {len(to_audit)}")
    total_f = sum(freq.values())
    covered_f = sum(f for _, f in to_audit)
    print(f"  Training signal covered: {covered_f:,} ({covered_f/total_f*100:.2f}%)")

    proposals = {}
    if OUT.exists():
        proposals = json.load(OUT.open(encoding="utf-8")).get("entries", {})
        print(f"  Resuming: {len(proposals)} done")

    to_do = [(op, f) for op, f in to_audit if op not in proposals]
    print(f"  Remaining: {len(to_do)}")

    if not to_do:
        print("Nothing to do.")
        return

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    t0 = time.time()
    errors = 0

    for i, (op, f) in enumerate(to_do, 1):
        canon = gee_v2_ci.get(op.lower())
        meta = gee_v2.get(canon) if canon else None
        if not meta:
            continue
        current_l3 = meta.get("primary_l3", "?")
        current_name = name_map.get(current_l3, "?")
        desc = gee_desc.get(op.lower(), "")

        try:
            llm_out = call_llm(client, system_prompt, op, f, desc,
                               current_l3, current_name)
        except Exception as e:
            errors += 1
            print(f"  [{i}/{len(to_do)}] {op} ERR: {e}")
            if errors >= 3 and i <= 5:
                print("Fail-fast: too many early errors."); return
            continue

        proposals[op] = {
            "gee_op": op,
            "frequency": f,
            "description": desc[:300],
            "current_l3": current_l3,
            "current_l3_name": current_name,
            "llm_top3": llm_out.get("top3", []),
            "user_decision": "",
        }

        if i % 25 == 0 or i == len(to_do):
            with OUT.open("w", encoding="utf-8") as fo:
                json.dump({"model": MODEL, "count": len(proposals),
                           "coverage_of_top_signal": f"{covered_f/total_f*100:.2f}%",
                           "entries": proposals}, fo, ensure_ascii=False, indent=2)
            el = time.time() - t0
            eta = (len(to_do) - i) * (el / i)
            print(f"  [{i}/{len(to_do)}] saved ({el:.0f}s, ~{eta:.0f}s to go)")

    print(f"\nDone.  proposals={len(proposals)}  errors={errors}")
    print(f"Output: {OUT}")


if __name__ == "__main__":
    main()
