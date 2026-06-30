#!/usr/bin/env python3
"""
targeted_gap_mining.py — Generalized mining for ALL L3 coverage gaps.

Loads l3_coverage_gap_report.json → extracts all gap codes + their QGIS operators →
two-phase mining (_steps.csv then .py scripts) → LLM inference → training samples.

Key improvements over targeted_vector_mining.py:
  - ALL gap types (DATA_GAP + LOW_COVERAGE_NO_QGIS + LOW_COVERAGE + MAPPING_GAP)
  - Dual data source: _steps.csv (structured) AND .py (unstructured code)
  - Full 94-code L3 list for LLM (not just vector subset)
  - Task type auto-derived from L1 category
  - Configurable max scripts per phase

Usage (on server):
    DEEPSEEK_API_KEY=sk-... python3 scripts/targeted_gap_mining.py \
        --phase csv --max-scripts 3000 --batch-size 50

    DEEPSEEK_API_KEY=sk-... python3 scripts/targeted_gap_mining.py \
        --phase py --max-scripts 5000 --batch-size 50

    DEEPSEEK_API_KEY=sk-... python3 scripts/targeted_gap_mining.py \
        --phase both --max-scripts 3000 --py-max-scripts 5000
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# ── Progress tracking (module-level) ──────────────────
_progress_counter = 0

def _print_progress(accepted: int, rejected: int, errors: int, every: int = 20):
    """Print progress every N items, regardless of outcome."""
    global _progress_counter
    _progress_counter += 1
    if _progress_counter % every == 0:
        import datetime as _dt
        ts = _dt.datetime.now().strftime("%H:%M:%S")
        print(f"    [{ts}] Accepted={accepted} Rejected={rejected} Errors={errors}")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

# ── Paths ─────────────────────────────────────────────────────────
YLL_GEE_DIR = "/home/yll/GEE"
OUTPUT_DIR = ROOT / "outputs_v2" / "targeted_gap_mining"
DEFAULT_GAP_REPORT = ROOT / "outputs_v2" / "diagnostics" / "l3_coverage_gap_report.json"
ID_MAPPINGS = ROOT / "outputs_v2" / "id_mappings_v2.json"

# ── Quality Gate ──────────────────────────────────────────────────
SINGLE_CODE_MIN_CONF = 0.70
MULTI_CODE_MIN_CONF = 0.65
MAX_CODES = 8
MIN_CODES = 1
PY_MIN_CONF_BOOST = 0.05  # .py files get a slight confidence boost

RENDERING_KEYWORDS = [
    "render", "color", "colour", "symbology", "style", "legend",
    "label", "layout", "print", "map theme", "decoration",
]
SELF_REJECT_PHRASES = [
    "no geoprocessing", "no gis operation", "no spatial operation",
    "only parameter definitions", "cannot determine", "cannot infer",
    "pure rendering", "visualization only", "only layout",
    "no actual data processing", "just ui configuration",
]

# ── L1 → task_type mapping ────────────────────────────────────────
L1_TASK_TYPE_MAP = {
    "Data Management": "Data Management",
    "Vector Analysis": "Vector Analysis",
    "Raster Analysis": "Raster Analysis",
    "Surface & Hydrology": "Terrain & Surface Analysis",
    "Spatial Statistics & Geostatistics": "Spatial Statistics",
    "Visualization & Output": "Visualization & Output",
    "Machine Learning & Classification": "Machine Learning & Classification",
    "Image Enhancement & Filtering": "Image Enhancement",
    "Data Fusion & Integration": "Data Fusion",
}


# ═══════════════════════════════════════════════════════════════════
# Gap report loading
# ═══════════════════════════════════════════════════════════════════

def load_gap_report(path: Path) -> dict:
    """Load gap report and return structured data.

    Returns:
        {
            "targets": {l3_code: {"ops": [...], "l1": str, "l2": str, "name": str,
                                   "gap_type": str, "risk": float, "desc": str}},
            "all_codes": {l3_code: {"name": str, "l1": str, "l2": str, "desc": str}},
            "l1_codes": {l1_name: [l3_code, ...]},
            "stats": {gap_type: count, ...}
        }
    """
    with open(path, "r", encoding="utf-8") as f:
        report = json.load(f)

    targets = {}
    all_codes = {}
    l1_codes: Dict[str, List[str]] = {}
    stats = dict(report.get("summary", {}).get("gap_counts", {}))

    for r in report.get("results", []):
        code = r["l3_code"]
        name = r["l3_name"]
        l1 = r.get("l1_name", "")
        l2 = r.get("l2_name", "")
        desc = r.get("l3_description", "")
        gap_type = r.get("gap_type", "ADEQUATE")
        risk = r.get("risk_score", 0.0)
        is_vector = r.get("is_vector", False)

        # All codes registry
        all_codes[code] = {"name": name, "l1": l1, "l2": l2, "desc": desc,
                           "is_vector": is_vector}

        # L1 grouping
        if l1:
            l1_codes.setdefault(l1, []).append(code)

        # Gap targets (non-ADEQUATE codes)
        if gap_type != "ADEQUATE":
            ops = []
            for e in r.get("top_qgis_operators", []):
                op_name = e.get("qgis_name", "")
                if op_name:
                    ops.append(op_name)

            targets[code] = {
                "ops": ops,
                "l1": l1,
                "l2": l2,
                "name": name,
                "desc": desc,
                "gap_type": gap_type,
                "risk": risk,
                "is_vector": is_vector,
            }

    return {
        "targets": targets,
        "all_codes": all_codes,
        "l1_codes": l1_codes,
        "stats": stats,
    }


def build_search_terms(targets: dict) -> List[str]:
    """Build deduplicated search terms from all target codes."""
    terms = set()
    for code, info in targets.items():
        for op in info["ops"]:
            terms.add(op)
    return sorted(terms)


def build_l3_code_list(all_codes: dict) -> str:
    """Build full L3 code list string for LLM prompt, grouped by L1."""
    # Group by L1
    by_l1: Dict[str, List[dict]] = {}
    for code, info in all_codes.items():
        l1 = info["l1"] or "Other"
        by_l1.setdefault(l1, []).append({
            "code": code, "name": info["name"], "desc": info["desc"],
        })

    lines = []
    for l1_name in sorted(by_l1.keys()):
        lines.append(f"\n## {l1_name}")
        for entry in sorted(by_l1[l1_name], key=lambda x: x["code"]):
            desc_short = entry["desc"][:80] if entry["desc"] else ""
            lines.append(f"  {entry['code']}: {entry['name']} — {desc_short}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# Phase 1: _steps.csv mining
# ═══════════════════════════════════════════════════════════════════

def find_csv_scripts(terms: List[str], max_results: int = 3000) -> List[Tuple[str, str, str]]:
    """Grep *_steps.csv files under *QGIS* paths for any search term.
    Returns list of (dir, script_id, steps_path) tuples.
    """
    print(f"\n  [CSV] Searching {len(terms)} terms across QGIS steps files...")

    escaped = [re.escape(t) for t in terms if len(t) >= 3]  # skip very short terms
    if not escaped:
        print("  [WARN] No valid search terms (all too short)")
        return []

    pattern = "|".join(escaped)

    import subprocess
    cmd = [
        "find", YLL_GEE_DIR,
        "-path", "*QGIS*",
        "-name", "*_steps.csv",
        "-exec", "grep", "-lE", pattern, "{}", "+"
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=180,
            cwd=str(ROOT)
        )
        files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
        print(f"  [CSV] Found {len(files)} matching steps files")
    except subprocess.TimeoutExpired:
        print("  [CSV] find+grep timed out, trying Python walk...")
        return _find_csv_scripts_slow(terms, max_results)

    # Extract unique scripts
    script_dirs = set()
    for f in files:
        stem = Path(f).stem
        script_id = stem.replace("_steps", "")
        parent = str(Path(f).parent)
        script_dirs.add((parent, script_id, f))

    print(f"  [CSV] Unique scripts: {len(script_dirs)}")
    if max_results and len(script_dirs) > max_results:
        print(f"  [CSV] Limiting to {max_results} scripts")
        script_dirs = set(list(script_dirs)[:max_results])

    return sorted(script_dirs)


def _find_csv_scripts_slow(terms: List[str], max_results: int = 3000) -> List[Tuple[str, str, str]]:
    """Fallback: Python directory walk."""
    print("  [CSV] Slow scan mode...")
    script_dirs = set()
    count = 0
    terms_lower = [t.lower() for t in terms if len(t) >= 3]
    for root, dirs, files in os.walk(YLL_GEE_DIR):
        if "QGIS" not in root:
            continue
        for f in files:
            if not f.endswith("_steps.csv"):
                continue
            count += 1
            if count % 10000 == 0:
                print(f"    [CSV] Scanned {count} files, found {len(script_dirs)} matches...")

            fpath = os.path.join(root, f)
            try:
                with open(fpath, "r", encoding="utf-8-sig", errors="ignore") as fh:
                    content = fh.read(16384)
                content_lower = content.lower()
                for term in terms_lower:
                    if term in content_lower:
                        script_id = f.replace("_steps.csv", "")
                        script_dirs.add((root, script_id, fpath))
                        break
            except Exception:
                continue

            if max_results and len(script_dirs) >= max_results:
                break
        if max_results and len(script_dirs) >= max_results:
            break

    print(f"  [CSV] Scanned {count} files, found {len(script_dirs)} matching scripts")
    return sorted(script_dirs)


def parse_steps_csv(filepath: str) -> List[dict]:
    """Parse a steps.csv into a list of step dicts."""
    steps = []
    with open(filepath, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            steps.append(row)
    return steps


def build_api_trace(steps: List[dict]) -> str:
    """Convert steps to structured API trace text for LLM prompt."""
    lines = []
    for i, step in enumerate(steps):
        name = step.get("normalized_api_name", "") or step.get("name", "")
        role = step.get("semantic_role", "")
        desc = step.get("description", "")
        if role in ("EXPRESSION_ASSIGNMENT", "UI_TEXT_TRANSLATE", "synthetic_expression"):
            continue
        lines.append(f"  {i}: {name} | role={role} | {desc}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# Phase 2: .py script mining
# ═══════════════════════════════════════════════════════════════════

def find_py_scripts(terms: List[str], max_results: int = 5000) -> List[Tuple[str, str, str]]:
    """Grep .py files under *QGIS* paths for QGIS API calls + operator names.

    For .py files, we search for:
    1. Direct operator name mentions
    2. processing.run("qgis:...") / processing.run("native:...") patterns

    Returns list of (dir, script_id, py_path) tuples.
    """
    print(f"\n  [PY] Searching {len(terms)} terms across QGIS .py files...")

    # Build search terms: operator names + API patterns
    escaped_ops = [re.escape(t) for t in terms if len(t) >= 3]
    # Add QGIS API patterns
    api_patterns = [
        r"processing\.run\(",
        r"processing\.runAlgorithm\(",
        r"qgis:",
        r"native:",
        r"saga:",
        r"grass7:",
        r"gdal:",
        r"AlgorithmDialog",
        r"runandload\(",
    ]
    all_patterns = escaped_ops + api_patterns
    pattern = "|".join(all_patterns)

    import subprocess
    cmd = [
        "find", YLL_GEE_DIR,
        "-path", "*QGIS*",
        "-name", "*.py",
        "-exec", "grep", "-lE", pattern, "{}", "+"
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300,
            cwd=str(ROOT)
        )
        files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
        print(f"  [PY] Found {len(files)} matching .py files")
    except subprocess.TimeoutExpired:
        print("  [PY] find+grep timed out, using sampled approach...")
        return _find_py_scripts_sampled(terms, max_results)

    # Extract unique scripts
    script_dirs = set()
    for f in files:
        stem = Path(f).stem
        # .py files: stem is the script name
        script_id = stem
        parent = str(Path(f).parent)
        script_dirs.add((parent, script_id, f))

    print(f"  [PY] Unique .py scripts: {len(script_dirs)}")
    if max_results and len(script_dirs) > max_results:
        print(f"  [PY] Sampling down to {max_results} scripts")
        import random
        script_dirs = set(random.sample(list(script_dirs), max_results))

    return sorted(script_dirs)


def _find_py_scripts_sampled(terms: List[str], max_results: int = 5000) -> List[Tuple[str, str, str]]:
    """Sampled fallback: walk QGIS dirs and check first 200K .py files."""
    print("  [PY] Sampled scan mode...")
    script_dirs = set()
    count = 0
    terms_lower = [t.lower() for t in terms if len(t) >= 3]
    api_markers = ["processing.run(", "qgis:", "native:", "saga:", "grass7:", "gdal:"]

    for root, dirs, files in os.walk(YLL_GEE_DIR):
        if "QGIS" not in root:
            continue
        for f in files:
            if not f.endswith(".py"):
                continue
            count += 1
            if count % 20000 == 0:
                print(f"    [PY] Scanned {count} files, found {len(script_dirs)} matches...")

            fpath = os.path.join(root, f)
            try:
                with open(fpath, "r", encoding="utf-8-sig", errors="ignore") as fh:
                    content = fh.read(32768)
                content_lower = content.lower()

                # Check for API markers
                has_api = any(m in content_lower for m in api_markers)
                # Check for operator terms
                has_term = any(t in content_lower for t in terms_lower)

                if has_api or has_term:
                    script_id = f.replace(".py", "")
                    script_dirs.add((root, script_id, fpath))
            except Exception:
                continue

            if max_results and len(script_dirs) >= max_results:
                break
        if max_results and len(script_dirs) >= max_results:
            break

    print(f"  [PY] Scanned {count} files, found {len(script_dirs)} matching scripts")
    return sorted(script_dirs)


def extract_py_trace(filepath: str) -> str:
    """Extract QGIS-related lines from a .py script as an LLM-friendly trace.

    Focuses on:
    - processing.run() / runAlgorithm() calls
    - Import statements (qgis, processing)
    - Lines containing known QGIS operator prefixes
    """
    qgis_prefixes = ["qgis:", "native:", "saga:", "grass7:", "gdal:", "otb:"]
    relevant_lines = []
    in_multiline_call = False
    multiline_buffer = []

    with open(filepath, "r", encoding="utf-8-sig", errors="ignore") as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        lower = stripped.lower()

        # Always capture processing.run/runAlgorithm calls
        if any(kw in lower for kw in ["processing.run(", "processing.runalgorithm(",
                                        "runandload(", "iface.add", "qgsproject"]):
            relevant_lines.append(f"  L{i}: {stripped[:200]}")
            if "(" in stripped and ")" not in stripped:
                in_multiline_call = True
                multiline_buffer = []
            continue

        # Capture lines inside multiline processing calls
        if in_multiline_call:
            multiline_buffer.append(stripped[:200])
            if ")" in stripped:
                in_multiline_call = False
                relevant_lines.append(f"  ... ({len(multiline_buffer)} continuation lines)")
            continue

        # Capture lines with QGIS operator prefixes
        if any(p in lower for p in qgis_prefixes):
            relevant_lines.append(f"  L{i}: {stripped[:200]}")
            continue

        # Capture import lines
        if lower.startswith("import ") or lower.startswith("from "):
            if any(kw in lower for kw in ["qgis", "processing", "osgeo", "gdal", "ogr"]):
                relevant_lines.append(f"  L{i}: {stripped[:200]}")

    # Limit trace length
    if len(relevant_lines) > 200:
        # Keep imports + every Nth processing line
        imports = [l for l in relevant_lines if "import" in l.lower()]
        proc = [l for l in relevant_lines if "import" not in l.lower()]
        # Sample processing lines evenly
        step = max(1, len(proc) // 150)
        sampled = proc[::step]
        relevant_lines = imports + sampled

    return "\n".join(relevant_lines[:250])  # max 250 lines


def build_py_llm_prompt(py_trace: str, l3_code_list: str) -> str:
    """Build LLM prompt for .py script inference."""
    return f"""Given the following QGIS Python script (API calls extracted),
infer the high-level GIS workflow as a sequence of L3 codes.

Available L3 codes (grouped by category):
{l3_code_list}

QGIS Python script trace:
{py_trace}

Output format: Return a JSON object with:
- "l3_sequence": list of L3 codes in execution order (2-8 codes)
- "confidence": overall confidence (0.0-1.0)
- "reasoning": brief explanation of the workflow inference
- "reject": true if there are no clear GIS operations (set confidence to 0)

Only include codes that represent actual data-processing operations.
Do NOT include UI/rendering/export-only steps unless they are the primary operation.
If the script has no substantive GIS operations, reject it."""


# ═══════════════════════════════════════════════════════════════════
# LLM Pipeline (shared)
# ═══════════════════════════════════════════════════════════════════

def build_llm_prompt(api_trace: str, l3_code_list: str) -> str:
    """Build LLM prompt for CSV step inference (original format)."""
    return f"""Given the following C++ API calls actually executed by a QGIS script,
infer the high-level GIS workflow as a sequence of L3 codes.

Available L3 codes (grouped by category):
{l3_code_list}

API trace:
{api_trace}

Output format: Return a JSON object with:
- "l3_sequence": list of L3 codes in execution order (2-8 codes)
- "confidence": overall confidence (0.0-1.0)
- "reasoning": brief explanation of the workflow inference
- "reject": true if there are no clear GIS operations (set confidence to 0)

Only include codes that represent actual data-processing operations.
Do NOT include UI/rendering/export-only steps.
If the script has no substantive GIS operations, reject it."""


def _parse_llm_json(content: str) -> Optional[dict]:
    """Robust JSON extraction from LLM response."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    for pattern in [r"```json\s*(.*?)\s*```", r"```\s*(.*?)\s*```", r"\{.*\}"]:
        m = re.search(pattern, content, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1) if "```" in pattern else m.group(0))
            except json.JSONDecodeError:
                continue

    # Brace matching
    depth = 0
    start = content.find("{")
    if start >= 0:
        for i in range(start, len(content)):
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(content[start:i+1])
                    except json.JSONDecodeError:
                        break
    return None


def infer_task_type(l3_codes: List[str], all_codes: dict) -> str:
    """Derive task_type from L1 category of the L3 codes."""
    l1_counts = Counter()
    for code in l3_codes:
        info = all_codes.get(code)
        if info:
            l1_name = info["l1"]
            if l1_name:
                l1_counts[l1_name] += 1

    if l1_counts:
        dominant_l1 = l1_counts.most_common(1)[0][0]
        return L1_TASK_TYPE_MAP.get(dominant_l1, "General GIS")

    return "General GIS"


def run_llm_pipeline(
    script_entries: List[Tuple[str, str, str]],
    l3_code_list: str,
    all_codes: dict,
    api_key: str,
    source: str = "csv",
    batch_size: int = 50,
) -> List[dict]:
    """Process scripts through LLM pipeline with quality gates.

    Args:
        script_entries: list of (dir, script_id, file_path) tuples
        l3_code_list: formatted L3 code list for prompt
        all_codes: full L3 code registry
        api_key: DeepSeek API key
        source: "csv" or "py"
        batch_size: scripts per batch

    Returns:
        List of training samples
    """
    global _progress_counter
    _progress_counter = 0

    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1", timeout=120.0)

    # Pre-parse allowed codes
    allowed_codes = set(all_codes.keys())

    results = []
    total = len(script_entries)
    accepted = 0
    rejected = 0
    errors = 0

    for batch_start in range(0, total, batch_size):
        batch = script_entries[batch_start:batch_start + batch_size]
        batch_num = batch_start // batch_size + 1
        print(f"\n  [{source.upper()}] Batch {batch_num}: "
              f"scripts {batch_start}-{min(batch_start+batch_size, total)}/{total}")

        for d, sid, fpath in batch:
            try:
                # 1. Extract trace based on source type
                if source == "csv":
                    steps = parse_steps_csv(fpath)
                    if len(steps) < 2:
                        rejected += 1
                        _print_progress(accepted, rejected, errors)
                        continue

                    api_trace = build_api_trace(steps)
                    prompt = build_llm_prompt(api_trace, l3_code_list)
                else:  # py
                    py_trace = extract_py_trace(fpath)
                    if len(py_trace) < 80:
                        rejected += 1
                        _print_progress(accepted, rejected, errors)
                        continue
                    prompt = build_py_llm_prompt(py_trace, l3_code_list)

                # 2. Check for rendering-only (CSV only)
                if source == "csv":
                    trace_lower = api_trace.lower()
                    rendering_score = sum(1 for kw in RENDERING_KEYWORDS if kw in trace_lower)
                    non_rendering = len(api_trace.split("\n"))
                    if non_rendering > 0 and rendering_score / max(non_rendering, 1) > 0.5:
                        rejected += 1
                        _print_progress(accepted, rejected, errors)
                        continue

                # 3. LLM call
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system",
                         "content": "You are a GIS workflow analyst. Output valid JSON only."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=2000,
                )

                content = response.choices[0].message.content or ""

                # 4. Parse JSON
                parsed = _parse_llm_json(content)
                if parsed is None:
                    errors += 1
                    _print_progress(accepted, rejected, errors)
                    continue

                # 5. Quality gates
                if parsed.get("reject"):
                    rejected += 1
                    _print_progress(accepted, rejected, errors)
                    continue

                l3_seq = parsed.get("l3_sequence", [])
                conf = float(parsed.get("confidence", 0))

                # .py scripts get slight confidence boost (richer context)
                if source == "py":
                    conf = min(1.0, conf + PY_MIN_CONF_BOOST)

                if len(l3_seq) < MIN_CODES or len(l3_seq) > MAX_CODES:
                    rejected += 1
                    _print_progress(accepted, rejected, errors)
                    continue

                if len(l3_seq) == 1 and conf < SINGLE_CODE_MIN_CONF:
                    rejected += 1
                    _print_progress(accepted, rejected, errors)
                    continue
                if len(l3_seq) > 1 and conf < MULTI_CODE_MIN_CONF:
                    rejected += 1
                    _print_progress(accepted, rejected, errors)
                    continue

                # 6. Self-rejection check
                reasoning = parsed.get("reasoning", "").lower()
                if any(phrase in reasoning for phrase in SELF_REJECT_PHRASES):
                    rejected += 1
                    _print_progress(accepted, rejected, errors)
                    continue

                # 7. Validate all codes are in allowed list
                if not all(c in allowed_codes for c in l3_seq):
                    rejected += 1
                    _print_progress(accepted, rejected, errors)
                    continue

                # 8. Derive task type
                task_type = infer_task_type(l3_seq, all_codes)

                # 9. Build training sample
                sample = {
                    "script_id": sid,
                    "script_dir": d,
                    "l3_codes": l3_seq,
                    "l3_sequence": l3_seq,
                    "confidence": conf,
                    "reasoning": parsed.get("reasoning", ""),
                    "task_description": parsed.get("reasoning", "")[:200],
                    "task_type": task_type,
                    "source": f"targeted_gap_mining_{source}",
                    "_training_quality": {
                        "tier": "generated",
                        "sample_weight": 1.0,
                        "confidence": conf,
                        "source": f"targeted_gap_mining_{source}",
                    },
                }
                results.append(sample)
                accepted += 1
                _print_progress(accepted, rejected, errors)

            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"    Error on {sid}: {e}")
                _print_progress(accepted, rejected, errors)
                continue

            # Rate limiting
            time.sleep(0.05)

    print(f"\n  [{source.upper()}] Final: Accepted={accepted} Rejected={rejected} Errors={errors}")
    return results


# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Targeted QGIS script miner for ALL L3 coverage gaps")
    parser.add_argument("--gap-report", type=str, default=str(DEFAULT_GAP_REPORT),
                        help="Path to l3_coverage_gap_report.json")
    parser.add_argument("--phase", type=str, default="csv",
                        choices=["csv", "py", "both"],
                        help="Mining phase: csv=_steps.csv, py=.py scripts, both=run both")
    parser.add_argument("--max-scripts", type=int, default=3000,
                        help="Max matching CSV scripts")
    parser.add_argument("--py-max-scripts", type=int, default=5000,
                        help="Max matching .py scripts")
    parser.add_argument("--batch-size", type=int, default=50,
                        help="Scripts per LLM batch")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only find matching scripts, don't call LLM")
    parser.add_argument("--output", type=str,
                        default=str(OUTPUT_DIR / "targeted_gap_samples.jsonl"),
                        help="Output JSONL path")
    parser.add_argument("--min-risk", type=float, default=0.0,
                        help="Minimum risk score for target codes (0-1)")
    parser.add_argument("--gap-types", type=str, default="DATA_GAP,LOW_COVERAGE,LOW_COVERAGE_NO_QGIS,MAPPING_GAP",
                        help="Comma-separated gap types to target")
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LLM_API_KEY")
    if not api_key and not args.dry_run:
        print("[ERROR] DEEPSEEK_API_KEY or LLM_API_KEY must be set")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    gap_types_filter = set(args.gap_types.split(","))

    # 1. Load gap report
    print("=" * 60)
    print("Targeted Gap Mining (Generalized)")
    print("=" * 60)

    gap_path = Path(args.gap_report)
    if not gap_path.exists():
        print(f"[ERROR] Gap report not found: {gap_path}")
        sys.exit(1)

    print(f"\n[1] Loading gap report: {gap_path}")
    report = load_gap_report(gap_path)
    targets = report["targets"]
    all_codes = report["all_codes"]
    stats = report["stats"]

    print(f"  Total gaps: {sum(stats.values())}")
    for gt, count in sorted(stats.items()):
        print(f"    {gt}: {count}")
    print(f"  Total L3 codes in vocab: {len(all_codes)}")

    # Filter by gap type and risk
    filtered_targets = {}
    for code, info in targets.items():
        if info["gap_type"] in gap_types_filter and info["risk"] >= args.min_risk:
            filtered_targets[code] = info

    print(f"\n  After filtering (types={gap_types_filter}, risk>={args.min_risk}):")
    print(f"  {len(filtered_targets)} target codes")
    for code, info in sorted(filtered_targets.items()):
        print(f"    {code} [{info['gap_type']}] {info['name']}: "
              f"{len(info['ops'])} ops, risk={info['risk']:.2f}")

    # 2. Build search terms and L3 code list
    search_terms = build_search_terms(filtered_targets)
    print(f"\n[2] Search terms: {len(search_terms)}")
    for t in sorted(search_terms)[:15]:
        print(f"    - {t}")
    if len(search_terms) > 15:
        print(f"    ... and {len(search_terms) - 15} more")

    l3_code_list = build_l3_code_list(all_codes)
    print(f"\n[3] L3 code list: {len(l3_code_list)} chars for LLM prompt")

    all_results = []

    # 3a. Phase: CSV
    if args.phase in ("csv", "both"):
        print(f"\n{'='*60}")
        print("PHASE A: _steps.csv Mining")
        print(f"{'='*60}")

        csv_matches = find_csv_scripts(search_terms, max_results=args.max_scripts)
        print(f"  Total CSV matches: {len(csv_matches)}")

        if csv_matches:
            match_file = OUTPUT_DIR / "matching_scripts_csv.json"
            with open(match_file, "w", encoding="utf-8") as f:
                json.dump([{"dir": d, "script_id": sid, "path": sp}
                           for d, sid, sp in csv_matches], f, indent=2)
            print(f"  Match list saved to {match_file}")

            if not args.dry_run:
                print(f"\n  [CSV] Processing {len(csv_matches)} scripts through LLM...")
                csv_results = run_llm_pipeline(
                    csv_matches, l3_code_list, all_codes, api_key,
                    source="csv", batch_size=args.batch_size
                )
                all_results.extend(csv_results)

    # 3b. Phase: PY
    if args.phase in ("py", "both"):
        print(f"\n{'='*60}")
        print("PHASE B: .py Script Mining")
        print(f"{'='*60}")

        py_max = args.py_max_scripts if args.phase in ("py", "both") else args.max_scripts
        py_matches = find_py_scripts(search_terms, max_results=py_max)
        print(f"  Total PY matches: {len(py_matches)}")

        if py_matches:
            match_file = OUTPUT_DIR / "matching_scripts_py.json"
            with open(match_file, "w", encoding="utf-8") as f:
                json.dump([{"dir": d, "script_id": sid, "path": sp}
                           for d, sid, sp in py_matches], f, indent=2)
            print(f"  Match list saved to {match_file}")

            if not args.dry_run:
                print(f"\n  [PY] Processing {len(py_matches)} scripts through LLM...")
                py_results = run_llm_pipeline(
                    py_matches, l3_code_list, all_codes, api_key,
                    source="py", batch_size=args.batch_size
                )
                all_results.extend(py_results)

    if args.dry_run:
        print(f"\n[DONE] Dry run complete. Found matching scripts.")
        print(f"  Run without --dry-run to process through LLM.")
        return

    # 4. Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for r in all_results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n{'='*60}")
    print(f"DONE: {len(all_results)} training samples → {output_path}")
    print(f"{'='*60}")

    # 5. Summary
    if all_results:
        code_counts = Counter()
        source_counts = Counter()
        task_type_counts = Counter()
        lengths = []
        for r in all_results:
            for c in r.get("l3_codes", []):
                code_counts[c] += 1
            source_counts[r.get("source", "unknown")] += 1
            task_type_counts[r.get("task_type", "unknown")] += 1
            lengths.append(len(r.get("l3_codes", [])))

        print(f"\n  By source:")
        for src, cnt in source_counts.most_common():
            print(f"    {src}: {cnt}")

        print(f"\n  By task type:")
        for tt, cnt in task_type_counts.most_common(10):
            print(f"    {tt}: {cnt}")

        print(f"\n  Chain length: avg={sum(lengths)/len(lengths):.1f}, "
              f"min={min(lengths)}, max={max(lengths)}")

        print(f"\n  L3 code distribution (top 30):")
        for code, count in code_counts.most_common(30):
            info = all_codes.get(code, {})
            name = info.get("name", "?")
            print(f"    {code} ({name}): {count}")

        # Coverage check
        covered_targets = set()
        for code in code_counts:
            if code in filtered_targets:
                covered_targets.add(code)
        uncovered = set(filtered_targets.keys()) - covered_targets
        print(f"\n  Target coverage: {len(covered_targets)}/{len(filtered_targets)} codes")
        if uncovered:
            print(f"  Still uncovered ({len(uncovered)}):")
            for code in sorted(uncovered):
                info = filtered_targets[code]
                print(f"    {code} [{info['gap_type']}] {info['name']}")


if __name__ == "__main__":
    main()
