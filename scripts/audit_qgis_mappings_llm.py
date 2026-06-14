# -*- coding: utf-8 -*-
"""
LLM-assisted audit of QGIS -> v2 L3 mappings.

For each QGIS operator in outputs_v2/id_mappings_v2.json, ask qwen-plus to
rank the top-3 v2 L3 targets by fit against the operator's description, with
a one-line rationale.  We record the LLM proposal alongside the current
auto-remapped mapping so a human reviewer can decide:

  outputs_v2/qgis_mapping_llm_proposals.json

Phases:
  A (this script)      — run LLM on all 469 ops, emit proposals
  B (manual review)    — you edit the 'user_decision' field in each entry
  C (integration)      — scripts/apply_qgis_audit.py rewrites id_mappings_v2

Resumable: if the output file already exists we skip any op we've already
scored.

Cost envelope: with DashScope prompt caching on the 94-entry L3 catalog,
~400 tokens input + ~200 tokens output per call.  469 calls ≈ 280k tokens
total — $0.02-0.05 depending on qwen-plus pricing.  Time: 25-40 min sequential.
"""
from __future__ import annotations
import csv
import json
import os
import sys
import time
from pathlib import Path

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
HIER_V2 = ROOT / "outputs_v2" / "classification_hierarchy_v2.csv"
ID_MAP = ROOT / "outputs_v2" / "id_mappings_v2.json"
QOPS_JSON = ROOT.parent / "operators-json" / "qgis_operators.json"
OUT = ROOT / "outputs_v2" / "qgis_mapping_llm_proposals.json"

API_KEY = (os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LLM_API_KEY") or os.environ.get("DASHSCOPE_API_KEY", ""))
BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1")
MODEL = os.environ.get("LLM_MODEL", "deepseek-v4-pro")


def build_catalog_text(hier_path: Path) -> str:
    rows = []
    for r in csv.DictReader(hier_path.open(encoding="utf-8")):
        rows.append(f"  {r['l3_code']}  |  {r['l3_name']}  |  [{r['l2_name']} / {r['l1_name']}]  |  {r.get('l3_description','')[:150]}")
    return "\n".join(rows)


SYSTEM_PROMPT_TEMPLATE = """You are a GIS operator taxonomist.  Your job: given a QGIS operator and its description, pick the 3 best-matching L3 primitive codes from the catalog below.  Prefer semantic fit over surface word overlap.  The 'description' fields in the catalog are authoritative.

L3 CATALOG (94 primitives in v2 taxonomy, code | name | [L2/L1] | short description):
{catalog}

Response format: a strict JSON object with a single key "top3" whose value is an array of 3 objects, each with fields {{l3_code, name, confidence, reason}}.  confidence is 0..1.  reason is at most 15 words.  Do NOT include markdown, prose, or any commentary outside the JSON."""

USER_PROMPT = """QGIS operator: {name}
Source toolbox: {source}
Description: {desc}

Existing mapping (auto-remap from v1, may be wrong): {current_l3} {current_name}

Return your top 3 L3 candidates now."""


def call_llm(client: OpenAI, system_prompt: str, qop_name: str, source: str,
             desc: str, current_l3: str, current_name: str) -> dict:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": USER_PROMPT.format(
                name=qop_name, source=source, desc=desc[:400],
                current_l3=current_l3, current_name=current_name,
            )},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
        max_tokens=350,
    )
    text = resp.choices[0].message.content
    return json.loads(text)


def main():
    print("Loading inputs ...")
    catalog = build_catalog_text(HIER_V2)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(catalog=catalog)

    # L3 code -> name
    l3_name = {}
    for r in csv.DictReader(HIER_V2.open(encoding="utf-8")):
        l3_name[r["l3_code"]] = r["l3_name"]

    # QGIS descriptions
    qops = json.load(QOPS_JSON.open(encoding="utf-8"))
    by_name = {op["name"]: op for op in qops}
    by_name_lower = {op["name"].lower(): op for op in qops}

    # Current v2 mapping
    with ID_MAP.open(encoding="utf-8") as f:
        qv2 = json.load(f)["mapping_metadata"]["qgis_to_l3"]

    # Resume from existing output if any
    proposals = {}
    if OUT.exists():
        with OUT.open(encoding="utf-8") as f:
            proposals = json.load(f).get("entries", {})
        print(f"  Resuming: {len(proposals)} entries already done")

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    to_do = [op for op in qv2 if op not in proposals]
    print(f"  Total QGIS ops: {len(qv2)}   remaining: {len(to_do)}")
    if not to_do:
        print("Nothing to do — rerun with OUT deleted if you want to refresh")
        return

    # Smoke-test first 3 ops so we fail fast on bad API
    t0 = time.time()
    errors = 0
    for i, qop_name in enumerate(to_do, 1):
        op_meta = by_name.get(qop_name) or by_name_lower.get(qop_name.lower())
        desc = (op_meta.get("description") if op_meta else "") or ""
        source = (op_meta.get("source") if op_meta else "") or "Unknown"

        current = qv2[qop_name]
        current_l3 = current.get("primary_l3", "")
        current_name = l3_name.get(current_l3, "?")

        try:
            llm_out = call_llm(client, system_prompt, qop_name, source, desc,
                               current_l3, current_name)
        except Exception as e:
            errors += 1
            print(f"  [{i}/{len(to_do)}] {qop_name}  ERROR: {e}")
            if errors >= 3 and i <= 5:
                print("Fail-fast: too many errors in first 5 calls, aborting.")
                return
            continue

        proposals[qop_name] = {
            "qgis_op": qop_name,
            "source": source,
            "description": desc[:300],
            "current_l3": current_l3,
            "current_l3_name": current_name,
            "llm_top3": llm_out.get("top3", []),
            "user_decision": "",  # fill in during phase B
        }

        # Checkpoint every 25
        if i % 25 == 0 or i == len(to_do):
            with OUT.open("w", encoding="utf-8") as f:
                json.dump({"model": MODEL, "count": len(proposals),
                           "entries": proposals}, f, ensure_ascii=False, indent=2)
            elapsed = time.time() - t0
            rate = i / elapsed if elapsed else 0
            eta = (len(to_do) - i) / rate if rate else 0
            print(f"  [{i}/{len(to_do)}] saved checkpoint "
                  f"({elapsed:.0f}s elapsed, ~{eta:.0f}s remaining)")

    print(f"\nDone.  Total proposals: {len(proposals)}  errors: {errors}")
    print(f"Output: {OUT}")


if __name__ == "__main__":
    main()
