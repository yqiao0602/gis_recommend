#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Route 4: Raw .py source code + task description → LLM → L3 training samples.

Reads QGIS Python source files from yll's GitHub crawl, pairs them with
facts_summary task descriptions, and feeds both to deepseek-chat to infer
high-level L3 workflow steps.

Unlike Route 3 (API traces from steps.csv), this reads the FULL source code
including comments, variable names, and data paths — giving the LLM much
richer context for understanding the script's workflow.

Usage (on server):
    conda activate transformer
    export DEEPSEEK_API_KEY=...
    python scripts/server_batch_source_to_l3.py \
        --max-scripts 500 --batch-size 100 --sleep 0.3 \
        --out outputs_v2/source_l3_samples_500.jsonl \
        --checkpoint outputs_v2/source_l3_checkpoint_500.json
"""
from __future__ import annotations

import argparse, csv, json, os, re, sys, time
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
from gis_recommend.data.vector_training_builder import to_training_sample
from openai import OpenAI

# ── Paths ──
DEFAULT_VOCAB = ROOT / "outputs_v2" / "l3_vocab_v2.json"
DEFAULT_TASK_VOCAB = ROOT / "outputs_v2" / "pipeline" / "step8_quality_gate" / "task_type_vocabulary_v4_quality_gate.json"
FACTS_CSV = ROOT / "outputs_v2" / "qgis_facts_full.csv"
SOURCE_DIR = "/home/yll/GEE/爬取GithubQGIS/github_qgis_workflow/downloaded_scripts/"

L3_CODE_LIST = """L3_02_01_01:Buffer
L3_02_02_01:Intersect
L3_02_02_02:Union
L3_02_02_04:Erase
L3_02_02_05:Symmetrical Difference
L3_02_02_06:Clip
L3_02_02_07:Filter by Extent
L3_02_03_05:Collect Features/Dissolve
L3_02_04_01:Spatial Join
L3_02_05_06:Split Line at Point
L3_02_05_11:Feature to Point/Centroid
L3_02_05_12:Minimum Bounding Geometry
L3_02_06_01:Select by Attribute
L3_02_06_02:Extract by Attribute
L3_02_06_03:Extract by Location
L3_02_06_05:Filter by Geometry
L3_02_07_01:Multipart to Singlepart/Geometry Fix/Simplify
L3_01_02_01:Add Field
L3_01_02_02:Delete Field
L3_01_02_03:Reproject
L3_01_02_06:Field Calculate
L3_01_03_04:Merge
L3_07_04_01:Export Data
L3_07_04_05:Format Convert
L3_07_01_01:Spatial Index
L3_03_01_01:Clip Raster
L3_03_01_02:Raster Clip by Mask
L3_03_02_01:Zonal Statistics
L3_03_02_03:Surface Volume / Density Analysis
L3_03_02_05:Raster Statistics
L3_03_03_A:Raster Calculator
L3_03_03_L:Logical Comparison (Band Math)
L3_03_04_01:Reclassify
L3_03_04_02:Reclassify by Layer
L3_03_05_02:Raster Interpolation
L3_03_07_01:Raster Create / Mosaic
L3_04_01_01:Terrain Analysis (Slope/Aspect/Hillshade)
L3_04_01_02:Viewshed
L3_04_01_03:Surface Analysis
L3_05_03_03:Raster to Vector / Polygonize"""

SYSTEM_PROMPT = """You are a GIS workflow analyst. Given the Python source code of a QGIS script and its task description, infer the high-level L3 workflow steps.

Rules:
1. Only use L3 codes from the provided list — do NOT invent new codes
2. Output 2-8 codes in logical execution order
3. Always try to infer a workflow chain even with limited signal
4. "confidence" = how sure you are the inferred chain is correct. Be honest.
5. Do NOT modify L3 code strings — exact matches only"""

USER_PROMPT = """Task description: {task_desc}

QGIS Python source code:
```python
{source_code}
```

Available L3 codes (use ONLY these):
{l3_codes}

Output JSON with: l3_codes, confidence, reasoning"""

# ── Quality gates (same as Route 3) ──
_REASONING_REJECT = [
    "no actual geoprocessing", "no actual spatial",
    "no geoprocessing", "no spatial",
    "cannot determine", "cannot infer", "unable to determine",
    "not enough information", "insufficient information",
    "purely ui", "only ui", "only rendering", "only symbology",
    "only parameter definitions", "only parameter definition",
    "no meaningful",
]

_SPATIAL_OPS = {"L3_02_01_01","L3_02_02_01","L3_02_02_02","L3_02_02_04","L3_02_02_05","L3_02_02_06","L3_02_04_01","L3_02_03_05"}
_ATTR_OPS = {"L3_02_06_01","L3_02_06_02","L3_02_06_03"}
_TRANSFORM_OPS = {"L3_01_02_03","L3_02_07_01","L3_02_05_11","L3_02_05_12"}
_RASTER_OPS = {"L3_03_01_01","L3_03_02_01","L3_03_04_01","L3_03_03_A","L3_03_03_L","L3_04_01_01"}
_EXPORT_OPS = {"L3_07_04_01","L3_01_03_04","L3_01_02_06","L3_01_02_02"}


def _clean_l3_code(code):
    m = re.match(r"^(L3_\d{2}_\d{2}_\d{2,3}[A-Z]?)", code)
    return m.group(1) if m else code


def _clean_llm_output(content):
    if not content:
        return None
    content = re.sub(r"^```\w*\n?|```$", "", content.strip(), flags=re.MULTILINE).strip()
    m = re.search(r"\{.*\}", content, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        text = re.sub(r",\s*}", "}", m.group(0))
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            return None
    if obj and "l3_codes" in obj:
        obj["l3_codes"] = [_clean_l3_code(c) for c in obj["l3_codes"]]
    return obj


def quality_gate(llm_obj):
    l3_codes = llm_obj.get("l3_codes", [])
    confidence = llm_obj.get("confidence", None)
    reasoning = (llm_obj.get("reasoning") or "").lower()

    for phrase in _REASONING_REJECT:
        if phrase in reasoning:
            return False, f"self-reject: '{phrase}'"

    if not l3_codes:
        return False, "empty l3_codes"

    try:
        conf = float(confidence) if confidence is not None else 0.5
    except (TypeError, ValueError):
        conf = 0.5

    if len(l3_codes) == 1:
        if conf < 0.60:
            return False, f"single-code low conf ({conf:.2f})"
    else:
        if conf < 0.50:
            return False, f"low conf ({conf:.2f})"

    code_set = set(l3_codes)
    has_spatial = bool(code_set & _SPATIAL_OPS)
    has_raster = bool(code_set & _RASTER_OPS)
    has_transform = bool(code_set & _TRANSFORM_OPS)

    if code_set <= _ATTR_OPS:
        if conf < 0.70:
            return False, f"pure-attr low conf ({conf})"
        if len(l3_codes) <= 2 and not (has_spatial or has_raster or has_transform):
            return False, "suspicious pure-attr"

    if code_set <= _EXPORT_OPS and len(l3_codes) <= 2:
        if conf < 0.65:
            return False, f"generic export/field low conf ({conf})"

    return True, "ok"


# ── Source file discovery ──
def discover_candidates():
    """Find scripts that have BOTH facts description AND .py source file."""
    # Load facts
    facts = {}
    if not FACTS_CSV.exists():
        print(f"FATAL: {FACTS_CSV} not found")
        return []

    with open(FACTS_CSV, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            fn = (row.get("File Name") or "").strip()
            desc = (row.get("Task Description") or "").strip()
            if fn and len(desc) >= 50:  # require meaningful description
                facts[fn.replace(".py", "")] = (row, len(desc))

    print(f"Facts with descriptions: {len(facts)}")

    # Check which have .py source files
    candidates = []
    import subprocess
    # Use find for speed
    result = subprocess.run(
        ["find", SOURCE_DIR, "-maxdepth", "1", "-name", "*.py"],
        capture_output=True, text=True, timeout=30,
        env={"LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8", "PATH": os.environ.get("PATH", "/usr/bin:/bin")},
    )
    source_files = set()
    for line in result.stdout.strip().split("\n"):
        if line:
            fname = os.path.basename(line).replace(".py", "")
            source_files.add(fname)

    for name, (row, desc_len) in facts.items():
        num = name.replace("script_", "")
        try:
            padded = f"script_{int(num):07d}"
        except ValueError:
            continue
        if padded in source_files:
            candidates.append((name, padded, row))

    print(f"With matching .py source: {len(candidates)}")
    return candidates


# ── Main ──
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-scripts", type=int, default=500)
    ap.add_argument("--batch-size", type=int, default=100)
    ap.add_argument("--checkpoint", default=str(ROOT / "outputs_v2" / "source_l3_checkpoint.json"))
    ap.add_argument("--out", default=str(ROOT / "outputs_v2" / "source_l3_samples.jsonl"))
    ap.add_argument("--sleep", type=float, default=0.3)
    args = ap.parse_args()

    # ── Load vocab ──
    vocab = json.loads(DEFAULT_VOCAB.read_text(encoding="utf-8"))
    code_to_id = vocab.get("code_to_id", vocab)
    all_codes = set(code_to_id.keys())
    special = vocab.get("special_tokens", {"<START>": -3, "<END>": -4})
    tt2id = json.loads(DEFAULT_TASK_VOCAB.read_text(encoding="utf-8"))["task_type_to_id"]

    # ── Discover candidates ──
    candidates = discover_candidates()
    if args.max_scripts > 0:
        import random
        random.seed(42)
        candidates = random.sample(candidates, min(args.max_scripts, len(candidates)))

    # ── Checkpoint ──
    checkpoint_path = Path(args.checkpoint)
    processed_set = set()
    if checkpoint_path.exists():
        ck = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        processed_set = set(ck.get("processed", []))
        print(f"Resuming: {len(processed_set)} already processed")

    pending = [(name, padded, row) for name, padded, row in candidates if name not in processed_set]
    print(f"Pending: {len(pending)}")

    if not pending:
        print("No pending scripts — all done or no candidates.")
        return

    # ── LLM setup ──
    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LLM_API_KEY", "")
    if not api_key:
        print("ERROR: DEEPSEEK_API_KEY not set"); sys.exit(1)
    client = OpenAI(base_url="https://api.deepseek.com/v1", api_key=api_key, timeout=90)

    st = Counter()
    st_q_reason = Counter()
    all_out = []
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    for i, (name, padded, fact_row) in enumerate(pending):
        if name in processed_set:
            continue

        # Read source code
        src_path = os.path.join(SOURCE_DIR, f"{padded}.py")
        try:
            with open(src_path, encoding="utf-8", errors="replace") as f:
                source_code = f.read(3000)  # first 3k chars
        except Exception:
            st["read_fail"] += 1
            processed_set.add(name)
            continue

        if len(source_code) < 100:
            st["too_short"] += 1
            processed_set.add(name)
            continue

        task_desc = fact_row.get("Task Description", "")[:400]
        task_type = fact_row.get("Task Type", "").strip()
        task_name = fact_row.get("Task Name", "").strip()

        prompt = USER_PROMPT.format(
            task_desc=task_desc,
            source_code=source_code,
            l3_codes=L3_CODE_LIST,
        )
        st["attempt"] += 1

        # LLM call
        try:
            r = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2, max_tokens=600,
            )
            content = (r.choices[0].message.content or "").strip()
            if not content:
                content = (getattr(r.choices[0].message, "reasoning_content", None) or "").strip()
            obj = _clean_llm_output(content)
            if obj is None:
                st["parse_fail"] += 1
                processed_set.add(name)
                continue
            st["llm_ok"] += 1
        except Exception as e:
            st["llm_fail"] += 1
            processed_set.add(name)
            time.sleep(1)
            continue

        l3_codes = obj.get("l3_codes", [])
        if not l3_codes:
            st["empty_l3"] += 1
            processed_set.add(name)
            continue
        if not all(c in all_codes for c in l3_codes):
            st["bad_l3"] += 1
            processed_set.add(name)
            continue

        # Quality gate
        q_pass, q_reason = quality_gate(obj)
        if not q_pass:
            st["quality_reject"] += 1
            st_q_reason[q_reason.split(":")[0]] += 1
            processed_set.add(name)
            continue

        # Build training sample
        if task_type not in tt2id:
            task_type = "Other / Sparse"

        described = {
            "optional_l3_sequence": l3_codes,
            "task_description_en": task_desc,
            "qgis_ops": [], "operator_names": [],
            "source": "llm_source_to_l3",
        }
        ts = to_training_sample(
            described, code_to_id=code_to_id, special_tokens=special,
            task_type=task_type, task_type_to_id=tt2id,
        )
        if ts is None:
            st["builder_drop"] += 1
            processed_set.add(name)
            continue

        try:
            conf = float(obj.get("confidence", None)) if obj.get("confidence") is not None else None
        except (TypeError, ValueError):
            conf = None
        ts["_script_name"] = name
        ts["_llm_reasoning"] = obj.get("reasoning", "")
        ts["_llm_confidence"] = conf
        ts["source"] = "llm_source_code_to_l3"  # override for route 4
        all_out.append(ts)
        st["kept"] += 1
        processed_set.add(name)

        # Periodic write
        if len(all_out) % 50 == 0 or (i + 1) % args.batch_size == 0:
            with open(out_path, "w", encoding="utf-8") as f:
                for s_ in all_out:
                    f.write(json.dumps(s_, ensure_ascii=False) + "\n")
            ck = {"processed": list(processed_set), "kept": len(all_out)}
            checkpoint_path.write_text(json.dumps(ck, ensure_ascii=False, indent=2))
            print(f"  [{i+1}/{len(pending)}] kept={st['kept']} llm_ok={st['llm_ok']} "
                  f"quality_reject={st['quality_reject']}")

        time.sleep(args.sleep)

    # ── Final write ──
    with open(out_path, "w", encoding="utf-8") as f:
        for s_ in all_out:
            f.write(json.dumps(s_, ensure_ascii=False) + "\n")
    ck = {"processed": list(processed_set), "kept": len(all_out)}
    checkpoint_path.write_text(json.dumps(ck, ensure_ascii=False, indent=2))

    # ── Stats ──
    print(f"\n{'='*60}")
    print(f"DONE: {st['attempt']} attempts → {st['kept']} kept ({100*st['kept']//max(st['attempt'],1)}%)")
    print(f"  llm_ok={st['llm_ok']} llm_fail={st['llm_fail']}")
    print(f"  parse_fail={st['parse_fail']} empty_l3={st['empty_l3']} bad_l3={st['bad_l3']}")
    print(f"  quality_reject={st['quality_reject']}")
    if st_q_reason:
        print(f"  reject reasons: {dict(st_q_reason)}")
    print(f"  → {out_path}")

    l3_dist = Counter()
    for ts in all_out:
        for c in ts["l3_codes"]:
            if c not in ("<START>", "<END>"):
                l3_dist[c] += 1
    print(f"L3 codes ({len(l3_dist)} unique):")
    for code, count in l3_dist.most_common(20):
        print(f"  {count:4d}  {code}")


if __name__ == "__main__":
    main()
