"""
targeted_vector_mining.py

Server-side targeted script miner for DATA_GAP L3 codes.
Searches 52k QGIS steps.csv files for specific operator names,
then feeds matching scripts through LLM→L3 pipeline.

Strategy:
  1. Load the gap report to get target L3 codes + their QGIS operators
  2. Grep all *_steps.csv for those operator names (fast, server-side)
  3. For matching scripts, extract API traces + feed to LLM
  4. Apply quality gates + output training samples

Usage (on server):
    conda activate transformer
    export DEEPSEEK_API_KEY=...
    python scripts/targeted_vector_mining.py \
        --gap-report outputs_v2/diagnostics/l3_coverage_gap_report.json \
        --max-scripts 500 --batch-size 50
"""

from __future__ import annotations

import argparse, csv, json, os, re, sys, time
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Set, Tuple, Optional

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

# ── Constants ──────────────────────────────────────────────────
YLL_GEE_DIR = "/home/yll/GEE"
OUTPUT_DIR = ROOT / "outputs_v2" / "targeted_vector_mining"
DEFAULT_GAP_REPORT = ROOT / "outputs_v2" / "diagnostics" / "l3_coverage_gap_report.json"

# Vector DATA_GAP L3 codes → QGIS operator names to search for
# Generated from gap report; can be overridden via --gap-report
VECTOR_TARGET_OPERATORS: Dict[str, List[str]] = {
    "L3_02_02_01": ["Intersection", "Intersect", "qgis:intersection", "Line intersections", "Polygon Self-Intersection"],
    "L3_02_02_04": ["Difference", "qgis:difference", "native:difference"],
    "L3_02_02_05": ["Symmetrical difference", "Symmetrical Difference", "qgis:symmetricaldifference"],
    "L3_02_02_06": ["Clip", "qgis:clip", "native:clip", "Extract/clip by extent", "Polygon Clipping", "Clip vector by mask layer", "Clip vector by extent"],
    "L3_02_02_07": ["Overlap analysis", "Update", "qgis:update"],
    "L3_02_05_06": ["Split Lines at Points", "Split Lines with Lines", "v.split", "Line Crossings", "qgis:splitlinesatpoints", "qgis:splitwithlines"],
    "L3_02_05_11": ["Centroids", "Polygon Centroids", "qgis:centroids", "native:centroids", "Feature to Point"],
    "L3_02_05_12": ["Bounding boxes", "Minimum bounding geometry", "qgis:boundingboxes", "qgis:minimumboundinggeometry", "native:minimumboundinggeometry"],
    "L3_02_06_01": ["Select by Attributes", "Select by attribute", "Select by expression", "qgis:selectbyattribute", "qgis:selectbyexpression"],
    "L3_02_06_02": ["Extract Shapefile encoding", "Extract Z values", "Extract M values", "Random extract within subsets", "qgis:extractbyattribute", "List unique values"],
    "L3_02_06_05": ["Filter by geometry type", "Filter vertices by M value", "qgis:filterbygeometry", "native:filterbygeometry"],
    "L3_02_07_01": ["Multipart to singleparts", "qgis:multiparttosingleparts", "native:multiparttosingleparts", "Geometry Fix", "Fix geometries", "qgis:fixgeometries"],
}

# Search priority: first pass = direct operator names, second pass = partial matches
PRIMARY_SEARCH_TERMS: List[str] = []
SECONDARY_SEARCH_TERMS: List[str] = []

for _ops in VECTOR_TARGET_OPERATORS.values():
    for _op in _ops:
        if any(kw in _op.lower() for kw in ["qgis:", "native:", "saga:", "grass:"]):
            PRIMARY_SEARCH_TERMS.append(_op)
        else:
            SECONDARY_SEARCH_TERMS.append(_op)

PRIMARY_SEARCH_TERMS = list(set(PRIMARY_SEARCH_TERMS))
SECONDARY_SEARCH_TERMS = list(set(SECONDARY_SEARCH_TERMS))

# ── Quality Gate Constants ─────────────────────────────────────
SINGLE_CODE_MIN_CONF = 0.70
MULTI_CODE_MIN_CONF = 0.65
MAX_CODES = 8
MIN_CODES = 1

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


def find_matching_scripts(terms: List[str], max_results: int = 2000) -> List[str]:
    """Grep all QGIS *_steps.csv for lines containing any search term.
    Returns list of unique script directory paths.
    """
    print(f"\n  Searching {len(terms)} terms across QGIS steps files...")

    # Build grep pattern (OR of all terms)
    # Escape special regex chars in terms
    escaped = [re.escape(t) for t in terms]
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
            cmd, capture_output=True, text=True, timeout=120,
            cwd=str(ROOT)
        )
        files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
        print(f"  Found {len(files)} matching steps files")

        # Extract unique script directories
        script_dirs = set()
        for f in files:
            # file is like .../Workflowoutput.../script_12345_steps.csv
            # Extract the script ID
            stem = Path(f).stem  # script_12345_steps
            script_id = stem.replace("_steps", "")  # script_12345
            parent = str(Path(f).parent)
            script_dirs.add((parent, script_id, f))

        print(f"  Unique scripts: {len(script_dirs)}")
        if max_results and len(script_dirs) > max_results:
            print(f"  Limiting to {max_results} scripts")
            script_dirs = set(list(script_dirs)[:max_results])

        return sorted(script_dirs)
    except subprocess.TimeoutExpired:
        print("  [WARN] find+grep timed out, trying alternative...")
        return _find_matching_scripts_slow(terms, max_results)


def _find_matching_scripts_slow(terms: List[str], max_results: int = 2000) -> List[str]:
    """Fallback: use Python to walk directories."""
    print("  Slow scan mode...")
    script_dirs = set()
    count = 0
    for root, dirs, files in os.walk(YLL_GEE_DIR):
        if "QGIS" not in root:
            continue
        for f in files:
            if not f.endswith("_steps.csv"):
                continue
            count += 1
            if count % 5000 == 0:
                print(f"    Scanned {count} files, found {len(script_dirs)} matches...")

            fpath = os.path.join(root, f)
            try:
                with open(fpath, "r", encoding="utf-8-sig", errors="ignore") as fh:
                    content = fh.read(8192)  # read first 8KB
                for term in terms:
                    if term.lower() in content.lower():
                        script_id = f.replace("_steps.csv", "")
                        script_dirs.add((root, script_id, fpath))
                        break
            except Exception:
                continue

            if max_results and len(script_dirs) >= max_results:
                break
        if max_results and len(script_dirs) >= max_results:
            break

    print(f"  Scanned {count} files, found {len(script_dirs)} matching scripts")
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
    """Convert steps to a structured API trace text for LLM prompt."""
    lines = []
    for i, step in enumerate(steps):
        name = step.get("normalized_api_name", "") or step.get("name", "")
        role = step.get("semantic_role", "")
        desc = step.get("description", "")
        # Skip synthetic/internal steps
        if role in ("EXPRESSION_ASSIGNMENT", "UI_TEXT_TRANSLATE", "synthetic_expression"):
            continue
        lines.append(f"  {i}: {name} | role={role} | {desc}")
    return "\n".join(lines)


def build_llm_prompt(api_trace: str, l3_code_list: str) -> str:
    """Build the LLM prompt for L3 inference from API traces."""
    return f"""Given the following C++ API calls actually executed by a QGIS script,
infer the high-level GIS workflow as a sequence of L3 codes.

Available L3 codes:
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


def run_llm_batch(
    script_entries: List[Tuple[str, str, str]],
    l3_code_list: str,
    api_key: str,
    batch_size: int = 50,
) -> List[dict]:
    """Process scripts through LLM pipeline with quality gates.

    Args:
        script_entries: list of (dir, script_id, steps_path) tuples
        l3_code_list: formatted L3 code list for prompt
        api_key: DeepSeek API key
        batch_size: number of scripts per batch

    Returns:
        List of training samples (labeled_workflows compatible)
    """
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")

    results = []
    total = len(script_entries)
    accepted = 0
    rejected = 0
    errors = 0

    for batch_start in range(0, total, batch_size):
        batch = script_entries[batch_start:batch_start + batch_size]
        print(f"\n  Batch {batch_start//batch_size + 1}: "
              f"scripts {batch_start}-{min(batch_start+batch_size, total)}/{total}")

        for d, sid, spath in batch:
            try:
                # 1. Parse steps
                steps = parse_steps_csv(spath)
                if len(steps) < 2:
                    rejected += 1
                    continue

                # 2. Build API trace
                api_trace = build_api_trace(steps)
                if len(api_trace) < 50:  # too short to have meaningful operations
                    rejected += 1
                    continue

                # 3. Check for rendering-only
                trace_lower = api_trace.lower()
                rendering_score = sum(1 for kw in RENDERING_KEYWORDS if kw in trace_lower)
                non_rendering = len(api_trace.split("\n"))
                if non_rendering > 0 and rendering_score / max(non_rendering, 1) > 0.5:
                    rejected += 1
                    continue

                # 4. LLM call
                prompt = build_llm_prompt(api_trace, l3_code_list)
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": "You are a GIS workflow analyst. Output valid JSON only."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=2000,
                )

                content = response.choices[0].message.content or ""

                # 5. Parse JSON response
                parsed = _parse_llm_json(content)
                if parsed is None:
                    errors += 1
                    continue

                # 6. Quality gate
                if parsed.get("reject"):
                    rejected += 1
                    continue

                l3_seq = parsed.get("l3_sequence", [])
                conf = float(parsed.get("confidence", 0))

                if len(l3_seq) < MIN_CODES or len(l3_seq) > MAX_CODES:
                    rejected += 1
                    continue

                if len(l3_seq) == 1 and conf < SINGLE_CODE_MIN_CONF:
                    rejected += 1
                    continue
                if len(l3_seq) > 1 and conf < MULTI_CODE_MIN_CONF:
                    rejected += 1
                    continue

                # 7. Self-rejection check
                reasoning = parsed.get("reasoning", "").lower()
                if any(phrase in reasoning for phrase in SELF_REJECT_PHRASES):
                    rejected += 1
                    continue

                # 8. Validate all codes are in the allowed list
                allowed_codes = set()
                for line in l3_code_list.strip().split("\n"):
                    code = line.split(":")[0].strip()
                    if code.startswith("L3_"):
                        allowed_codes.add(code)

                if not all(c in allowed_codes for c in l3_seq):
                    rejected += 1
                    continue

                # 9. Build training sample
                sample = {
                    "script_id": sid,
                    "script_dir": d,
                    "l3_codes": l3_seq,
                    "l3_sequence": l3_seq,
                    "confidence": conf,
                    "reasoning": parsed.get("reasoning", ""),
                    "task_description": "",  # will be backfilled if possible
                    "task_type": "Vector Analysis",
                    "source": "targeted_vector_mining",
                    "_training_quality": {
                        "tier": "generated",
                        "sample_weight": 1.0,
                        "confidence": conf,
                        "source": "targeted_vector_mining",
                    },
                }
                results.append(sample)
                accepted += 1

            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"    Error on {sid}: {e}")
                continue

            # Progress
            if (accepted + rejected + errors) % 20 == 0:
                print(f"    Accepted={accepted} Rejected={rejected} Errors={errors}")

            # Rate limiting
            time.sleep(0.1)

    print(f"\n  Final: Accepted={accepted} Rejected={rejected} Errors={errors}")
    return results


def _parse_llm_json(content: str) -> Optional[dict]:
    """Robust JSON extraction from LLM response."""
    # Try direct parse
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON block
    for pattern in [r"```json\s*(.*?)\s*```", r"```\s*(.*?)\s*```", r"\{.*\}"]:
        m = re.search(pattern, content, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1) if "```" in pattern else m.group(0))
            except json.JSONDecodeError:
                continue

    # Try brace matching
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


def load_gap_report(path: Path) -> Dict[str, List[str]]:
    """Extract target operators from gap report JSON.
    Merges with built-in VECTOR_TARGET_OPERATORS to ensure full coverage.
    """
    targets = dict(VECTOR_TARGET_OPERATORS)  # start with built-in defaults

    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            report = json.load(f)

        for r in report.get("results", []):
            if r.get("is_vector") and r.get("gap_type") == "DATA_GAP":
                code = r["l3_code"]
                # Extract operators from top_qgis_operators (both mapped and discovered)
                ops = [e["qgis_name"] for e in r.get("top_qgis_operators", [])[:5] if e.get("qgis_name")]
                if ops and code not in targets:
                    targets[code] = ops
                elif ops:
                    # Merge with built-in, deduplicate
                    existing = set(targets.get(code, []))
                    for op in ops:
                        if op not in existing:
                            targets.setdefault(code, []).append(op)

    return targets


def main():
    parser = argparse.ArgumentParser(description="Targeted QGIS script miner for DATA_GAP L3 codes")
    parser.add_argument("--gap-report", type=str, default=str(DEFAULT_GAP_REPORT),
                        help="Path to l3_coverage_gap_report.json")
    parser.add_argument("--max-scripts", type=int, default=500,
                        help="Max matching scripts to process")
    parser.add_argument("--batch-size", type=int, default=50,
                        help="Scripts per LLM batch")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only find matching scripts, don't call LLM")
    parser.add_argument("--output", type=str, default=str(OUTPUT_DIR / "targeted_vector_samples.jsonl"),
                        help="Output JSONL path")
    parser.add_argument("--primary-only", action="store_true",
                        help="Only search primary terms (qgis:/native: prefixes)")
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LLM_API_KEY")
    if not api_key and not args.dry_run:
        print("[ERROR] DEEPSEEK_API_KEY or LLM_API_KEY must be set")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load targets
    print("=" * 60)
    print("Targeted Vector Mining")
    print("=" * 60)

    gap_path = Path(args.gap_report)
    if gap_path.exists():
        print(f"\n[1] Loading gap report: {gap_path}")
        targets = load_gap_report(gap_path)
        print(f"  Loaded {len(targets)} vector DATA_GAP codes")
        for code, ops in targets.items():
            print(f"    {code}: {ops[:3]}")
    else:
        print(f"\n[1] Gap report not found, using built-in targets")
        targets = VECTOR_TARGET_OPERATORS

    # 2. Build search terms
    search_terms = []
    for ops in targets.values():
        search_terms.extend(ops)
    search_terms = list(set(search_terms))

    if args.primary_only:
        search_terms = [t for t in search_terms
                        if any(kw in t.lower() for kw in ["qgis:", "native:", "saga:", "grass:"])]

    print(f"\n[2] Search terms: {len(search_terms)}")
    for t in sorted(search_terms)[:10]:
        print(f"    - {t}")
    if len(search_terms) > 10:
        print(f"    ... and {len(search_terms) - 10} more")

    # 3. Find matching scripts
    print(f"\n[3] Finding matching scripts...")
    matches = find_matching_scripts(search_terms, max_results=args.max_scripts)
    print(f"  Total matches: {len(matches)}")

    if not matches:
        print("[DONE] No matching scripts found.")
        return

    # Save match list
    match_file = OUTPUT_DIR / "matching_scripts.json"
    with open(match_file, "w", encoding="utf-8") as f:
        json.dump([{"dir": d, "script_id": sid, "steps_path": sp}
                    for d, sid, sp in matches], f, indent=2)
    print(f"  Match list saved to {match_file}")

    if args.dry_run:
        print("\n[DONE] Dry run complete. Run without --dry-run to process scripts.")
        return

    # 4. Build L3 code list for LLM prompt
    # Include all vector codes + common supporting codes
    l3_code_lines = []
    for code, ops in VECTOR_TARGET_OPERATORS.items():
        code_name = code  # will use code as name
        l3_code_lines.append(f"{code}:{code_name}")

    # Add supporting codes
    supporting = [
        "L3_01_02_03:Alter Field/Reproject",
        "L3_01_03_04:Merge",
        "L3_01_02_01:Add Field",
        "L3_01_02_06:Calculate Field",
        "L3_02_01_01:Buffer",
        "L3_02_02_02:Union",
        "L3_02_03_05:Collect Features/Dissolve",
        "L3_02_04_01:Spatial Join",
        "L3_02_06_03:Extract by Location",
        "L3_07_04_01:Export Data",
    ]
    for s in supporting:
        if s not in l3_code_lines:
            l3_code_lines.append(s)

    l3_code_list = "\n".join(l3_code_lines)

    # 5. Run LLM pipeline
    print(f"\n[4] Processing {len(matches)} scripts through LLM...")
    results = run_llm_batch(
        matches, l3_code_list, api_key, batch_size=args.batch_size
    )

    # 6. Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n[DONE] {len(results)} training samples saved to {output_path}")

    # 7. Summary stats
    if results:
        code_counts = Counter()
        for r in results:
            for c in r.get("l3_codes", []):
                code_counts[c] += 1
        print(f"\n  L3 code distribution in output:")
        for code, count in code_counts.most_common(20):
            print(f"    {code}: {count}")


if __name__ == "__main__":
    main()
