#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate L3 sequences from C++ API traces via LLM.

Reads per-script steps.csv files (yll's step-graph extraction), extracts the
meaningful C++ API call sequence (semantic_role + description), and feeds it to
deepseek-chat to infer high-level L3 workflow steps.

This is Route 3 (C++ API traces → LLM → L3), which combines:
  - Route 1's ground-truth constraint (actual API calls executed)
  - Route 2's LLM understanding (interprets low-level API → high-level L3)

Key finding from POC: API traces are MORE accurate than description-only for
inferring L3, because the LLM reasons from what was actually executed rather
than guessing from a task description.

Usage:
    python scripts/llm_generate_l3_from_api_traces.py \\
        --input-dir <dir_of_steps_csv> --out <samples.jsonl> [--max N] [--dry-run]
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

# ── L3 vocabulary for the prompt (40 codes — QGIS-relevant subset of 94) ──
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

# ── Prompts ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a GIS workflow analyst. Given the C++ API calls actually executed by a QGIS script, infer the high-level L3 workflow steps.

Rules:
1. Only use L3 codes from the provided list — do NOT invent new codes
2. Output 2-8 codes in logical execution order
3. Do not guess. If the trace does not show executable GIS operations, return empty l3_codes and confidence 0.0 rather than inventing a chain.
4. "confidence" = how sure you are the inferred chain is correct. Be honest on a 0.0-1.0 scale:
   - 0.8-1.0: clear spatial operations visible (buffer, clip, intersect, reproject, zonal stats, raster calc, coordinate transform, etc.)
   - 0.6-0.7: strong but indirect signal (field manipulation + feature iteration, CRS creation + export, etc.)
   - 0.4-0.5: weak signal — best-guess only, an expert might reasonably disagree
   - 0.0-0.3: the trace shows no GIS operations (only layer create, project save, UI, styles). Return empty l3_codes.
5. Do NOT modify L3 code strings — exact matches only"""

USER_PROMPT = """C++ API trace from a QGIS script:

{api_trace}

Available L3 codes (use ONLY these):
{l3_codes}

Output only a JSON object with keys: l3_codes, confidence, reasoning"""

# ── API name patterns that signal GIS-domain operations even when role/src are unknown ──
_API_GIS_PATTERNS = [
    r"\bQgs", r"\bqgs\b", r"\bprocessing\b", r"\braster\b", r"\bvector\b",
    r"\bcoordinate\b", r"\btransform\b", r"\bcrs\b", r"\bprojection\b",
    r"\bProvider\b", r"\bDataSource\b", r"\bRenderer\b",
    r"\balg\b", r"\bogr\b", r"\bgdal\b",
    r"\baddParameter\b", r"\bparameterAs\b", r"\bprocessAlgorithm\b",
    r"\binitAlgorithm\b", r"\baddMapLayer\b", r"\bmapLayer\b",
    r"\bsetPrefixPath\b", r"\binitQgis\b", r"\bexitQgis\b",
    r"\bSaveVectorOptions\b", r"\bVectorFileWriter\b", r"\bVectorLayer\b",
    r"\bRasterLayer\b", r"\bFeature\b", r"\bGeometry",
    # ArcPy patterns
    r"\bar\.setRasters\b", r"\bar\.setParameters\b", r"\bar\.RasterInfo\b",
    r"\bar\.run\b", r"\bar\.Item\b", r"\barcpy\.", r"\barcgis\.",
]

# src values that are inherently non-GIS (even if API name matches)
_NON_GIS_SOURCES = {"synthetic_expression", "pyqt_ui", "TEXT_OP", "PATH_OP", "IO"}

# Roles that are always GIS-relevant (QGIS/processing domain)
_GIS_ROLE_PREFIXES = ("QGIS_", "VECTOR_", "NativeAlgorithms", "SetPrefixPath")

# Roles that are never meaningful for GIS inference
_SKIP_ROLES = {
    "", "EXPRESSION_ASSIGNMENT", "RETURN_TERMINAL", "MAP_ASSIGNMENT",
    "UI_TEXT_TRANSLATE", "CONTROL_CONDITION", "LOOP_ITER_CONTROL",
    "RAISE_TERMINAL", "TERNARY_ASSIGNMENT", "PYTHON_BUILTIN",
    "COLLECTION_MUTATION", "COLLECTION_SIZE", "COLLECTION_CAST",
    "TYPE_CAST", "Print", "RANGE_GENERATION", "StringFormat",
    "SplitString", "PathJoin", "PathCreate", "DatetimeNow",
    "ITERATOR_ENUMERATE", "NUMERIC_MIN", "NUMERIC_MAX", "NUMERIC_ROUND",
    "DICT_ITEMS", "POINT_CREATE", "POINT_X_COORD", "POINT_Y_COORD",
}


def _is_gis_api(role: str, src: str, api: str, desc: str) -> bool:
    """Decide whether a step represents a GIS-domain operation worth including."""
    # Explicit skip
    if role in _SKIP_ROLES:
        return False
    # Always skip non-GIS sources
    if src in _NON_GIS_SOURCES:
        return False
    # Always include: QGIS processing algorithm calls
    if src == "qgis_processing_algorithm":
        return True
    # Include if role has a GIS prefix
    if role.startswith(_GIS_ROLE_PREFIXES):
        return True
    # Include if role is explicitly meaningful for GIS
    if role in ("QGIS_PARAMETER_DEFINITION", "QGIS_PARAMETER_RASTER_LAYER_DEFINE",
                "QGIS_PARAMETER_NUMBER_DEFINE", "QGIS_PARAMETER_ENUM_DEFINE",
                "QGIS_PARAMETER_CRS_DEFINE", "QGIS_PARAMETER_FEATURE_SINK_DEFINE",
                "QGIS_OUTPUT_DEFINITION", "QGIS_OUTPUT_PARAMETER_READ",
                "QGIS_LAYER_ADD", "QGIS_PROJECT_ADD_LAYER",
                "QGIS_FEATURE_SET_GEOMETRY", "QGIS_FEATURE_SINK_CREATE",
                "QGIS_FEATURE_ITERATION", "QGIS_FEATURE_ID",
                "QGIS_FIELD_DEFINE", "QGIS_FIELD_APPEND", "QGIS_FIELD_COLLECTION_CREATE",
                "QGIS_DATABASE_CONNECTION_CREATE",
                "QGIS_COLOR_NAME", "QGIS_SYMBOL_ACCESS", "QGIS_SYMBOL_COLOR_ACCESS",
                "QGIS_TEMP_LAYER_ADD", "QGIS_TEMP_LAYER_STORE_ACCESS",
                "QGIS_TEMP_OUTPUT_TO_LAYER",
                "QGIS_LOAD_ON_COMPLETION_REGISTER",
                "QGIS_PROVIDER_METADATA_ACCESS", "QGIS_PROVIDER_REGISTRY_INSTANCE",
                "QGIS_LAYER_VALIDATION",
                ):
        return True
    # role empty or general — match against API name patterns
    if not role:
        for pat in _API_GIS_PATTERNS:
            if re.search(pat, api):
                return True
    return False


def build_api_trace(steps_csv_path: str) -> str | None:
    """Extract meaningful API trace from a steps.csv file.

    Returns a compact text representation of the API call sequence,
    or None if the script has no meaningful GIS operations.
    """
    lines = []
    with open(steps_csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            role = (row.get("semantic_role") or "").strip()
            if role in _SKIP_ROLES:
                continue
            src = (row.get("api_source_type") or "").strip()
            api = (row.get("normalized_api_name") or "").strip()
            desc = (row.get("description") or "").strip()
            if not _is_gis_api(role, src, api, desc):
                continue
            label = role if role else (src if src != "unknown" else "")
            text = f"{api}"
            if desc and desc != api and not desc.startswith("Synthetic"):
                text += f" — {desc}"
            prefix = f"[{label}] " if label else ""
            lines.append(f"  {prefix}{text}")

    if not lines:
        return None

    # Deduplicate consecutive identical lines
    deduped = []
    for line in lines:
        if not deduped or line != deduped[-1]:
            deduped.append(line)

    return "\n".join(deduped)


def _clean_l3_code(code: str) -> str:
    """Strip ':Description' suffix that LLM sometimes appends to L3 codes."""
    # e.g. "L3_01_03_04:Merge" → "L3_01_03_04"
    # e.g. "L3_03_03_A:Raster Calculator" → "L3_03_03_A"
    m = re.match(r"^(L3_\d{2}_\d{2}_\d{2,3}[A-Z]?)", code)
    return m.group(1) if m else code


def _clean_llm_output(content: str) -> dict | None:
    """Robust JSON extraction from LLM output."""
    if not content:
        return None
    # Strip markdown code fences
    content = re.sub(r"^```\w*\n?|```$", "", content.strip(), flags=re.MULTILINE).strip()
    # Find JSON object
    m = re.search(r"\{.*\}", content, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        # Try fixing common issues
        text = m.group(0)
        text = re.sub(r",\s*}", "}", text)
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            return None
    # Normalize: strip ":Text" suffixes from L3 codes
    if obj and "l3_codes" in obj:
        obj["l3_codes"] = [_clean_l3_code(c) for c in obj["l3_codes"]]
    return obj


# ── Quality gates ──────────────────────────────────────────────────────

# Reasoning phrases that indicate the LLM knows there's no real geoprocessing
_REASONING_REJECT = [
    "no actual geoprocessing",
    "no spatial",
    "no geoprocessing",
    "cannot determine",
    "cannot infer",
    "unable to determine",
    "not enough information",
    "insufficient information",
    "purely ui",
    "only ui",
    "only rendering",
    "only symbology",
    "no meaningful",
]

# L3 code families
_SPATIAL_OPS = {"L3_02_01_01", "L3_02_02_01", "L3_02_02_02", "L3_02_02_04",
                "L3_02_02_05", "L3_02_02_06", "L3_02_04_01", "L3_02_03_05"}
_ATTR_OPS = {"L3_02_06_01", "L3_02_06_02", "L3_02_06_03"}
_TRANSFORM_OPS = {"L3_01_02_03", "L3_02_07_01", "L3_02_05_11", "L3_02_05_12"}
_RASTER_OPS = {"L3_03_01_01", "L3_03_02_01", "L3_03_04_01", "L3_03_03_A", "L3_04_01_01"}
_EXPORT_OPS = {"L3_07_04_01", "L3_01_03_04", "L3_01_02_06", "L3_01_02_02"}


def quality_gate(llm_obj: dict) -> tuple[bool, str]:
    """Return (pass, reason). Pass=False means drop this sample."""
    l3_codes = llm_obj.get("l3_codes", [])
    confidence = llm_obj.get("confidence", None)
    reasoning = (llm_obj.get("reasoning") or "").lower()

    # Gate 1: explicit self-rejection
    for phrase in _REASONING_REJECT:
        if phrase in reasoning:
            return False, f"self-reject: '{phrase}' in reasoning"

    # Gate 2: empty codes
    if not l3_codes:
        return False, "empty l3_codes"

    # Gate 3: confidence threshold
    if confidence is not None:
        try:
            conf = float(confidence)
        except (TypeError, ValueError):
            return False, "invalid confidence"
        # Single-code chains need moderate confidence
        if len(l3_codes) == 1:
            if conf < 0.70:
                return False, f"single-code confidence too low ({conf:.2f})"
        else:
            if conf < 0.65:
                return False, f"confidence too low ({conf:.2f})"
    else:
        return False, "missing confidence"

    # Gate 4: structural diversity check
    code_set = set(l3_codes)
    has_spatial = bool(code_set & _SPATIAL_OPS)
    has_attr = bool(code_set & _ATTR_OPS)
    has_transform = bool(code_set & _TRANSFORM_OPS)
    has_raster = bool(code_set & _RASTER_OPS)

    # Pure attribute-only chains (Select/Extract only) — most common hallucination
    if code_set <= _ATTR_OPS:
        if conf < 0.70:
            return False, f"pure-attr chain with low confidence ({conf})"
        if len(l3_codes) <= 2 and not (has_spatial or has_raster or has_transform):
            return False, "suspicious pure-attr chain, no spatial/transform/raster ops"

    # Single op that is just export/merge/field calc — too generic
    if code_set <= _EXPORT_OPS and len(l3_codes) <= 2:
        if conf < 0.65:
            return False, f"generic export/field chain, low confidence ({conf})"

    return True, "ok"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input-dir", required=True, help="Directory of per-script *_steps.csv files")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max", type=int, default=0, help="Max scripts to process (0=all)")
    ap.add_argument("--sleep", type=float, default=0.3, help="Sleep between LLM calls")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--facts", default=None, help="Optional facts_summary CSV for task_type/description join")
    args = ap.parse_args()

    # ── Load vocab ──
    vocab = json.loads(DEFAULT_VOCAB.read_text(encoding="utf-8"))
    code_to_id = vocab if isinstance(vocab, dict) else {}
    if "code_to_id" in vocab:
        code_to_id = vocab["code_to_id"]
    all_codes = set(code_to_id.keys())
    special = vocab.get("special_tokens", {"<START>": -3, "<END>": -4})
    tt2id = json.loads(DEFAULT_TASK_VOCAB.read_text(encoding="utf-8"))["task_type_to_id"]

    # ── Load optional facts ──
    facts_map = {}
    if args.facts and os.path.exists(args.facts):
        with open(args.facts, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                fn = (row.get("File Name") or "").strip()
                if fn:
                    facts_map[fn] = row

    # ── Discover steps.csv files ──
    csv_files = sorted(Path(args.input_dir).glob("*_steps.csv"))
    if args.max:
        csv_files = csv_files[:args.max]
    print(f"Found {len(csv_files)} steps.csv files")

    # ── Build API traces ──
    traces = []  # (script_name, api_trace_text, facts_row_or_None)
    skipped_empty = 0
    skipped_too_short = 0
    for fp in csv_files:
        trace = build_api_trace(str(fp))
        if not trace:
            skipped_empty += 1
            continue
        if len(trace.split("\n")) < 2:
            skipped_too_short += 1
            continue
        script_name = fp.name.replace("_steps.csv", "")
        facts_row = facts_map.get(script_name)
        traces.append((script_name, trace, facts_row))

    print(f"  {len(traces)} scripts with meaningful API traces")
    print(f"  {skipped_empty} skipped (no meaningful ops), {skipped_too_short} skipped (< 2 steps)")

    if args.dry_run:
        # Show sample traces
        for name, trace, facts in traces[:5]:
            print(f"\n{'='*60}")
            print(f"Script: {name}")
            if facts:
                print(f"Task type: {facts.get('Task Type', '')}")
                print(f"Description: {(facts.get('Task Description') or '')[:120]}")
            print(f"API trace ({len(trace.split(chr(10)))} steps):")
            print(trace[:800])
        return

    # ── LLM setup ──
    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LLM_API_KEY", "")
    client = OpenAI(base_url="https://api.deepseek.com/v1", api_key=api_key, timeout=90)

    st = Counter()
    st_q_reason = Counter()
    all_out = []

    for i, (name, trace, facts) in enumerate(traces):
        # Build prompt with optional description context
        desc_hint = ""
        if facts:
            task_desc = (facts.get("Task Description") or "").strip()
            task_type = (facts.get("Task Type") or "").strip()
            if task_desc:
                desc_hint = f"\nTask description (for context): {task_desc[:300]}\nTask type: {task_type}\n"

        prompt = USER_PROMPT.format(api_trace=desc_hint + trace[:2500], l3_codes=L3_CODE_LIST)
        st["attempt"] += 1

        try:
            r = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=600,
            )
            content = (r.choices[0].message.content or "").strip()
            # Fallback: deepseek-v4-pro puts answer in reasoning_content
            if not content:
                reasoning = getattr(r.choices[0].message, "reasoning_content", None) or ""
                if reasoning:
                    content = reasoning.strip()
            obj = _clean_llm_output(content)
            if obj is None:
                st["parse_fail"] += 1
                if st["parse_fail"] <= 5:
                    print(f"  [{i+1}] {name} PARSE FAIL: {repr(content[:200])}")
                continue
            l3_codes = obj.get("l3_codes", [])
            st["llm_ok"] += 1
        except Exception as e:
            st["llm_fail"] += 1
            print(f"  [{i+1}] LLM error: {e}")
            time.sleep(1)
            continue

        # Validate L3 codes
        if not l3_codes:
            st["empty_l3"] += 1
            continue
        if not all(c in all_codes for c in l3_codes):
            bad = [c for c in l3_codes if c not in all_codes]
            st["bad_l3"] += 1
            if st["bad_l3"] <= 3:
                print(f"  [{i+1}] {name}: BAD L3 codes: {bad}")
            continue

        # Quality gate
        q_pass, q_reason = quality_gate(obj)
        if not q_pass:
            st["quality_reject"] += 1
            st_q_reason[q_reason.split(":")[0]] += 1
            continue

        # Build training sample
        task_type = "Unknown"
        task_name = name
        task_desc = ""
        if facts:
            task_type = (facts.get("Task Type") or "Unknown").strip()
            task_name = (facts.get("Task Name") or name).strip()
            task_desc = (facts.get("Task Description") or "").strip()

        if task_type not in tt2id:
            task_type = "Other / Sparse"

        described = {
            "optional_l3_sequence": l3_codes,
            "task_description_en": task_desc or f"QGIS script: {name}",
            "qgis_ops": [],
            "operator_names": [],
            "source": "llm_api_trace_to_l3",
        }
        ts = to_training_sample(
            described, code_to_id=code_to_id, special_tokens=special,
            task_type=task_type, task_type_to_id=tt2id,
        )
        if ts is None:
            st["builder_drop"] += 1
            continue
        ts["task_metadata"]["task_name"] = task_name
        confidence_val = obj.get("confidence", None)
        try:
            confidence_val = float(confidence_val) if confidence_val is not None else None
        except (TypeError, ValueError):
            confidence_val = None
        ts["_script_name"] = name
        ts["_llm_reasoning"] = obj.get("reasoning", "")
        ts["_llm_confidence"] = confidence_val
        all_out.append(ts)
        st["kept"] += 1

        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(traces)}  kept={st['kept']}  llm_ok={st['llm_ok']}  "
                  f"bad_l3={st['bad_l3']}  parse_fail={st['parse_fail']}")
        time.sleep(args.sleep)

    # ── Write output ──
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for ts in all_out:
            f.write(json.dumps(ts, ensure_ascii=False) + "\n")

    # ── Stats ──
    print(f"\n{'='*60}")
    print(f"DONE: {st['attempt']} attempts → {st['kept']} kept ({100*st['kept']/max(st['attempt'],1):.0f}%)")
    print(f"  llm_ok={st['llm_ok']}  llm_fail={st['llm_fail']}")
    print(f"  parse_fail={st['parse_fail']}  empty_l3={st['empty_l3']}  bad_l3={st['bad_l3']}")
    print(f"  quality_reject={st['quality_reject']}  builder_drop={st['builder_drop']}")
    if st_q_reason:
        print(f"  reject reasons: {dict(st_q_reason)}")
    print(f"  → {args.out}")

    # L3 code distribution
    l3_dist = Counter()
    confidences = []
    for ts in all_out:
        conf = ts.get("_llm_confidence")
        if conf is not None:
            confidences.append(float(conf))
        for c in ts["l3_codes"]:
            if c not in ("<START>", "<END>"):
                l3_dist[c] += 1
    if confidences:
        print(f"\nConfidence: mean={sum(confidences)/len(confidences):.2f}  "
              f"min={min(confidences):.2f}  max={max(confidences):.2f}")
    print(f"\nL3 code distribution ({len(l3_dist)} unique):")
    for code, count in l3_dist.most_common(20):
        print(f"  {count:4d}  {code}")


if __name__ == "__main__":
    main()
