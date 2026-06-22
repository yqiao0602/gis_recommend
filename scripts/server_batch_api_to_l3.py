#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Server-side batch runner: C++ API traces → LLM → L3 training samples.

Reads steps.csv directly from yll's QGIS extraction pool (no SFTP needed),
processes them through deepseek-chat with quality gating, and outputs
labeled_workflows-compatible training samples.

Designed for checkpointed/resumable batch processing on the A10 server.

Usage (on server):
    conda activate transformer
    export DEEPSEEK_API_KEY=...
    python scripts/server_batch_api_to_l3.py \
        --max-scripts 2000 --batch-size 200 --checkpoint outputs_v2/api_l3_checkpoint.json
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

# ── Constants ─────────────────────────────────────────────────────────
YLL_QGIS_DIR = "/home/yll/GEE/数据抽取结果"
DEFAULT_VOCAB = ROOT / "outputs_v2" / "l3_vocab_v2.json"
DEFAULT_TASK_VOCAB = ROOT / "outputs_v2" / "pipeline" / "step8_quality_gate" / "task_type_vocabulary_v4_quality_gate.json"
FACTS_CSV = ROOT / "outputs_v2" / "qgis_facts_full.csv"

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

SYSTEM_PROMPT = """You are a GIS workflow analyst. Given the C++ API calls actually executed by a QGIS script, infer the high-level L3 workflow steps.

Rules:
1. Only use L3 codes from the provided list — do NOT invent new codes
2. Output 2-8 codes in logical execution order
3. Always try to infer a workflow chain even with limited signal — prefer reasonable guesses over empty output
4. "confidence" = how sure you are the inferred chain is correct. Be honest on a 0.0-1.0 scale:
   - 0.8-1.0: clear spatial operations visible (buffer, clip, intersect, reproject, zonal stats, raster calc, coordinate transform, etc.)
   - 0.6-0.7: strong but indirect signal (field manipulation + feature iteration, CRS creation + export, etc.)
   - 0.4-0.5: weak signal — best-guess only, an expert might reasonably disagree
   - 0.0-0.3: the trace shows no GIS operations (only layer create, project save, UI, styles). Still produce a guess but set confidence low.
5. Do NOT modify L3 code strings — exact matches only"""

USER_PROMPT = """C++ API trace from a QGIS script:

{api_trace}

Available L3 codes (use ONLY these):
{l3_codes}

Output only a JSON object with keys: l3_codes, confidence, reasoning"""

# ── API trace extraction (same logic as llm_generate_l3_from_api_traces.py) ──
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
    r"\bar\.setRasters\b", r"\bar\.setParameters\b", r"\bar\.RasterInfo\b",
    r"\bar\.run\b", r"\bar\.Item\b", r"\barcpy\.", r"\barcgis\.",
]

_NON_GIS_SOURCES = {"synthetic_expression", "pyqt_ui", "TEXT_OP", "PATH_OP", "IO"}

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

_GIS_ROLE_PREFIXES = ("QGIS_", "VECTOR_", "NativeAlgorithms", "SetPrefixPath")

_GIS_ROLES_EXPLICIT = {
    "QGIS_PARAMETER_DEFINITION", "QGIS_PARAMETER_RASTER_LAYER_DEFINE",
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
}


def _is_gis_api(role, src, api, desc):
    if role in _SKIP_ROLES:
        return False
    if src in _NON_GIS_SOURCES:
        return False
    if src == "qgis_processing_algorithm":
        return True
    if role.startswith(_GIS_ROLE_PREFIXES):
        return True
    if role in _GIS_ROLES_EXPLICIT:
        return True
    if not role:
        for pat in _API_GIS_PATTERNS:
            if re.search(pat, api):
                return True
    return False


def build_api_trace(steps_csv_path):
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
    deduped = []
    for line in lines:
        if not deduped or line != deduped[-1]:
            deduped.append(line)
    return "\n".join(deduped)


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
        text = m.group(0)
        text = re.sub(r",\s*}", "}", text)
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            return None
    if obj and "l3_codes" in obj:
        obj["l3_codes"] = [_clean_l3_code(c) for c in obj["l3_codes"]]
    return obj


# ── Quality gates ──────────────────────────────────────────────────────
_REASONING_REJECT = [
    "no actual geoprocessing", "no actual spatial",
    "no geoprocessing", "no spatial",
    "cannot determine", "cannot infer", "unable to determine",
    "not enough information", "insufficient information",
    "purely ui", "only ui", "only rendering", "only symbology",
    "only parameter definitions", "only parameter definition",
    "no meaningful",
]

_SPATIAL_OPS = {"L3_02_01_01", "L3_02_02_01", "L3_02_02_02", "L3_02_02_04",
                "L3_02_02_05", "L3_02_02_06", "L3_02_04_01", "L3_02_03_05"}
_ATTR_OPS = {"L3_02_06_01", "L3_02_06_02", "L3_02_06_03"}
_TRANSFORM_OPS = {"L3_01_02_03", "L3_02_07_01", "L3_02_05_11", "L3_02_05_12"}
_RASTER_OPS = {"L3_03_01_01", "L3_03_02_01", "L3_03_04_01", "L3_03_03_A", "L3_04_01_01"}
_EXPORT_OPS = {"L3_07_04_01", "L3_01_03_04", "L3_01_02_06", "L3_01_02_02"}


_RENDERING_ROLES = {
    "QGIS_SYMBOL_SET_COLOR", "QGIS_SYMBOL_SET_WIDTH",
    "QGIS_RENDERER_CATEGORY_CREATE", "QGIS_SYMBOL_ACCESS",
    "QGIS_SYMBOL_COLOR_ACCESS", "QGIS_COLOR_NAME",
    "QGIS_LAYER_RENDERER_ACCESS",
}
_RENDERING_API_KEYWORDS = [
    "colorRampShader", "pseudoColorRenderer", "Renderer", "renderer",
    "setColor", "setWidth", "setSymbol", "QgsCategorizedSymbolRenderer",
    "QgsGraduatedSymbolRenderer", "QgsSingleSymbolRenderer",
    "QgsHeatmapRenderer", "QgsRuleBasedRenderer",
]


def _is_rendering_only(trace_text: str) -> bool:
    """Return True if the trace shows only rendering/symbology operations.

    These scripts style layers but don't perform geoprocessing — their
    L3 chains are hallucinations."""
    lines = trace_text.split("\n")
    if len(lines) < 2:
        return False
    # Count rendering vs geoprocessing lines
    rendering = 0
    geoproc = 0
    for line in lines:
        is_rendering = False
        for role in _RENDERING_ROLES:
            if f"[{role}]" in line:
                rendering += 1
                is_rendering = True
                break
        for kw in _RENDERING_API_KEYWORDS:
            if kw in line:
                rendering += 1
                is_rendering = True
                break
        if not is_rendering:
            geoproc += 1
    # Reject if >50% of lines are rendering and geoproc <= 2
    if rendering > 0 and geoproc <= 2 and rendering >= geoproc:
        return True
    return False


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

    # Per-case confidence thresholds (NOT a blanket floor):
    # single-code chains need stronger evidence, multi-code lower is ok
    if len(l3_codes) == 1:
        if conf < 0.60:
            return False, f"single-code confidence ({conf:.2f})"
    else:
        if conf < 0.50:
            return False, f"confidence ({conf:.2f})"

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


# ── Main ───────────────────────────────────────────────────────────────
def discover_qgis_steps_files():
    """Find all QGIS *_steps.csv using find command (proven reliable via SSH)."""
    import subprocess
    try:
        result = subprocess.run(
            "find /home/yll/GEE/ -path '*QGIS*' -name '*_steps.csv'",
            shell=True, capture_output=True, text=True, timeout=120,
            env={"LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8", "PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        )
        files = [f for f in result.stdout.strip().split("\n") if f.strip()]
        if files:
            return files
    except Exception as e:
        print(f"  find failed: {e}, trying glob...")
    # Fallback
    files = []
    for p in Path("/home/yll/GEE").rglob("*_steps.csv"):
        if "QGIS" in str(p):
            files.append(str(p))
    return files


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-scripts", type=int, default=-1)
    ap.add_argument("--batch-size", type=int, default=200)
    ap.add_argument("--checkpoint", default=ROOT / "outputs_v2" / "api_l3_checkpoint.json")
    ap.add_argument("--out", default=ROOT / "outputs_v2" / "api_l3_samples.jsonl")
    ap.add_argument("--sleep", type=float, default=0.3)
    ap.add_argument("--steps-dir", default=None,
                    help="Override: use this dir instead of scanning yll's QGIS pool")
    args = ap.parse_args()

    # ── Load vocab ──
    vocab = json.loads(DEFAULT_VOCAB.read_text(encoding="utf-8"))
    code_to_id = vocab.get("code_to_id", vocab)
    if isinstance(code_to_id, dict) and "code_to_id" not in code_to_id:
        code_to_id = vocab
        if "code_to_id" in vocab:
            code_to_id = vocab["code_to_id"]
    all_codes = set(code_to_id.keys())
    special = vocab.get("special_tokens", {"<START>": -3, "<END>": -4})
    tt2id = json.loads(DEFAULT_TASK_VOCAB.read_text(encoding="utf-8"))["task_type_to_id"]

    # ── Load facts ──
    facts_map = {}
    if FACTS_CSV.exists():
        with open(FACTS_CSV, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                fn = (row.get("File Name") or "").strip()
                if fn:
                    facts_map[fn] = row

    # ── Discover files ──
    if args.steps_dir:
        files = [str(p) for p in Path(args.steps_dir).glob("*_steps.csv")]
    else:
        files = discover_qgis_steps_files()
    print(f"Found {len(files)} QGIS steps.csv files")

    # ── Checkpoint / resume ──
    checkpoint_path = Path(args.checkpoint)
    processed = set()
    if checkpoint_path.exists():
        ck = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        processed = set(ck.get("processed", []))
        print(f"Resuming: {len(processed)} already processed")

    pending = [f for f in files if os.path.basename(f) not in processed]
    if args.max_scripts > 0:
        pending = pending[:args.max_scripts]
    print(f"Pending: {len(pending)}")

    # ── LLM setup ──
    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LLM_API_KEY", "")
    if not api_key:
        print("ERROR: DEEPSEEK_API_KEY not set"); sys.exit(1)
    client = OpenAI(base_url="https://api.deepseek.com/v1", api_key=api_key, timeout=90)

    st = Counter()
    st_q_reason = Counter()
    all_out = []  # accumulates training samples
    batch = []
    out_path = Path(args.out)

    for i, fp in enumerate(pending):
        fname = os.path.basename(fp)
        script_name = fname.replace("_steps.csv", "")

        # Skip already processed
        if fname in processed:
            continue

        # Build trace
        trace = build_api_trace(fp)
        if not trace:
            st["skip_no_trace"] += 1
            processed.add(fname)
            continue
        if len(trace.split("\n")) < 2:
            st["skip_too_short"] += 1
            processed.add(fname)
            continue

        # Build prompt
        facts = facts_map.get(script_name)
        desc_hint = ""
        if facts:
            task_desc = (facts.get("Task Description") or "").strip()
            task_type = (facts.get("Task Type") or "").strip()
            if task_desc:
                desc_hint = f"Task description: {task_desc[:300]}\nTask type: {task_type}\n\n"

        prompt = USER_PROMPT.format(
            api_trace=desc_hint + trace[:2500],
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
                processed.add(fname)
                time.sleep(args.sleep)
                continue
            st["llm_ok"] += 1
        except Exception as e:
            st["llm_fail"] += 1
            time.sleep(1)
            processed.add(fname)
            continue

        l3_codes = obj.get("l3_codes", [])
        if not l3_codes:
            st["empty_l3"] += 1
            processed.add(fname)
            continue
        if not all(c in all_codes for c in l3_codes):
            st["bad_l3"] += 1
            processed.add(fname)
            continue

        # Rendering/symbology check — reject scripts that only do styling
        if _is_rendering_only(trace):
            st["skip_rendering"] += 1
            processed.add(fname)
            continue

        # Quality gate
        q_pass, q_reason = quality_gate(obj)
        if not q_pass:
            st["quality_reject"] += 1
            q_cat = q_reason.split(":")[0]
            st_q_reason[q_cat] += 1
            processed.add(fname)
            continue

        # Build training sample
        task_type = "Unknown"
        task_name = script_name
        task_desc = ""
        if facts:
            task_type = (facts.get("Task Type") or "Unknown").strip()
            task_name = (facts.get("Task Name") or script_name).strip()
            task_desc = (facts.get("Task Description") or "").strip()
        if task_type not in tt2id:
            task_type = "Other / Sparse"

        described = {
            "optional_l3_sequence": l3_codes,
            "task_description_en": task_desc or f"QGIS script: {script_name}",
            "qgis_ops": [], "operator_names": [],
            "source": "llm_api_trace_to_l3",
        }
        ts = to_training_sample(
            described, code_to_id=code_to_id, special_tokens=special,
            task_type=task_type, task_type_to_id=tt2id,
        )
        if ts is None:
            st["builder_drop"] += 1
            processed.add(fname)
            continue

        try:
            conf = float(obj.get("confidence", None)) if obj.get("confidence") is not None else None
        except (TypeError, ValueError):
            conf = None
        ts["_script_name"] = script_name
        ts["_llm_reasoning"] = obj.get("reasoning", "")
        ts["_llm_confidence"] = conf
        all_out.append(ts)
        st["kept"] += 1
        processed.add(fname)

        # Periodic output
        if len(all_out) % 50 == 0 or (i + 1) % args.batch_size == 0:
            # Write cumulative output
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                for s_ in all_out:
                    f.write(json.dumps(s_, ensure_ascii=False) + "\n")
            # Write checkpoint
            ck = {"processed": list(processed), "kept": len(all_out),
                   "total_attempts": st["attempt"],
                   "script_last": os.path.basename(fp)}
            checkpoint_path.write_text(json.dumps(ck, ensure_ascii=False, indent=2))
            print(f"  [{i+1}/{len(pending)}] kept={st['kept']}  "
                  f"skip_no_trace={st['skip_no_trace']}  skip_too_short={st['skip_too_short']}  "
                  f"skip_rendering={st['skip_rendering']}  "
                  f"llm_ok={st['llm_ok']}  llm_fail={st['llm_fail']}  "
                  f"parse_fail={st['parse_fail']}  empty_l3={st['empty_l3']}  "
                  f"bad_l3={st['bad_l3']}  quality_reject={st['quality_reject']}")

        time.sleep(args.sleep)

    # ── Final write ──
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for s_ in all_out:
            f.write(json.dumps(s_, ensure_ascii=False) + "\n")

    ck = {"processed": list(processed), "kept": len(all_out),
          "total_attempts": st["attempt"]}
    checkpoint_path.write_text(json.dumps(ck, ensure_ascii=False, indent=2))

    # ── Stats ──
    print(f"\n{'='*60}")
    print(f"DONE: {st['attempt']} attempts → {st['kept']} kept "
          f"({100*st['kept']/max(st['attempt'],1):.0f}%)")
    print(f"  llm_ok={st['llm_ok']}  llm_fail={st['llm_fail']}")
    print(f"  parse_fail={st['parse_fail']}  empty_l3={st['empty_l3']}  bad_l3={st['bad_l3']}")
    print(f"  quality_reject={st['quality_reject']}  builder_drop={st['builder_drop']}")
    print(f"  skip_no_trace={st['skip_no_trace']}  skip_too_short={st['skip_too_short']}  skip_rendering={st['skip_rendering']}")
    if st_q_reason:
        print(f"  reject reasons: {dict(st_q_reason)}")
    print(f"  → {out_path}")

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
    print(f"L3 codes ({len(l3_dist)} unique):")
    for code, count in l3_dist.most_common(30):
        print(f"  {count:5d}  {code}")


if __name__ == "__main__":
    main()
