#!/usr/bin/env python3
"""
Prototype v2: C++ API trace → QGIS operator chain.

Stage 1: Extract GIS-relevant keywords from C++ class/method names
Stage 2: Match against 1,291 QGIS operator catalog → top-50
Stage 3: LLM selects correct operator sequence from candidates

The key insight: C++ API calls don't contain QGIS alg IDs, but the
class names and method calls carry strong semantic signals that LLM
can map to QGIS Processing operators.
"""

import csv, json, os, re, sys, time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ── C++ class → GIS concept mapping ──────────────────────────────

# Maps C++ API patterns to GIS operation keywords for better catalog matching
CPP_TO_GIS = {
    # Vector operations
    "qgsgeometry": ["buffer", "clip", "intersect", "difference", "union",
                    "dissolve", "transform", "simplify", "centroid", "area", "length"],
    "qgsvectorlayer": ["vector", "feature", "layer", "select", "extract", "field"],
    "qgsfeature": ["feature", "attribute", "geometry", "select"],
    "qgsfield": ["field", "calculate", "attribute", "type", "schema"],
    "qgsvectorfilewriter": ["export", "save", "write", "shapefile"],

    # Raster operations
    "qgsrasterlayer": ["raster", "band", "pixel", "grid", "resolution"],
    "qgsrasterdataprovider": ["raster", "data", "block", "read"],
    "gdalutils": ["gdal", "raster", "warp", "translate", "reproject"],
    "qgsrastercalculator": ["raster", "calculator", "algebra", "formula"],

    # Processing
    "qgsprocessingalgorithm": ["processing", "algorithm", "parameter"],
    "qgsprocessingparameter": ["parameter", "input", "output", "configuration"],
    "qgsprocessingfeedback": ["feedback", "progress", "cancel"],

    # Analysis
    "qgsslopefilter": ["slope", "terrain", "elevation", "gradient"],
    "qgsaspectfilter": ["aspect", "direction", "terrain", "orientation"],
    "qgshillshadefilter": ["hillshade", "relief", "terrain", "light"],
    "qgsruggednessfilter": ["terrain", "ruggedness", "roughness"],
    "qgsrelieffilter": ["relief", "terrain", "height"],

    # Distance/Spatial
    "qgsdistancearea": ["distance", "area", "measure", "calculation"],
    "qgscoordinatereferencesystem": ["crs", "projection", "coordinate", "reproject"],
    "qgscoordinatetransform": ["transform", "reproject", "coordinate", "crs"],

    # IO
    "qgsvectorlayer.source": ["vector", "source", "layer"],
    "qgsmaplayer.dataprovider": ["data", "provider", "load", "read"],
    "gdalconnectiondetails": ["gdal", "connection", "database", "uri"],

    # Common operations
    "buffer": ["buffer", "distance"],
    "clip": ["clip", "crop", "extract"],
    "intersect": ["intersect", "overlay", "cross"],
    "merge": ["merge", "combine", "union"],
    "dissolve": ["dissolve", "aggregate", "group"],
    "select": ["select", "query", "filter", "extract"],
    "extract": ["extract", "filter", "subset"],
    "reproject": ["reproject", "transform", "warp"],
    "calculate": ["calculate", "compute", "field", "expression"],
    "distance": ["distance", "proximity", "near"],
    "slope": ["slope", "terrain", "gradient", "elevation"],
    "raster": ["raster", "grid", "pixel", "band"],
    "vector": ["vector", "feature", "polygon", "line", "point"],
    "layer": ["layer", "data", "source"],
    "field": ["field", "attribute", "column"],
    "geometry": ["geometry", "shape", "spatial"],
}


def extract_gis_keywords(api_trace: str) -> list[str]:
    """Extract GIS-relevant keywords from C++ API trace."""
    trace_lower = api_trace.lower()
    keywords = set()
    for pattern, words in CPP_TO_GIS.items():
        if pattern in trace_lower:
            for w in words:
                keywords.add(w)
    return list(keywords)


# ── QGIS Catalog ──────────────────────────────────────────────────

def load_catalog(path: str) -> list[dict]:
    """Parse QGIS_Input.csv into structured operator list."""
    with open(path, "r", encoding="utf-8-sig") as f:
        content = f.read()
    ops = []
    for line in content.strip().split("\n")[1:]:
        if not line.strip():
            continue
        alg_match = re.search(r'(?:qgis|native|gdal|grass7|saga|otb):\w+', line)
        if not alg_match:
            continue
        alg_id = alg_match.group(0)
        parts = line.split(",")
        name = parts[2].strip('"') if len(parts) > 2 else ""
        desc = parts[4].strip('"') if len(parts) > 4 else ""
        desc = desc[:300]
        # Determine I/O types
        has_vector = "vector" in line.lower()
        has_raster = "raster" in line.lower()

        ops.append({
            "name": name,
            "alg_id": alg_id,
            "desc": desc,
            "search_text": f"{name} {alg_id} {desc}"[:500].lower(),
            "is_vector": has_vector,
            "is_raster": has_raster,
        })

    # Dedup by alg_id
    seen = set()
    deduped = []
    for op in ops:
        if op["alg_id"] not in seen:
            seen.add(op["alg_id"])
            deduped.append(op)
    return deduped


def keyword_match(keywords: list[str], catalog: list[dict], top_k: int = 50) -> list[dict]:
    """Match extracted keywords against catalog."""
    scored = []
    for op in catalog:
        score = 0
        for kw in keywords:
            if kw in op["search_text"]:
                score += 1
            # Name exact match bonus
            if kw == op["name"].lower():
                score += 5
        if score > 0:
            scored.append({**op, "match_score": score})
    scored.sort(key=lambda x: -x["match_score"])
    return scored[:top_k]


# ── LLM ───────────────────────────────────────────────────────────

def build_llm_prompt(api_trace: str, candidates: list[dict], task_hint: str = "") -> str:
    cand_text = "\n".join(
        f"  {op['name']:30s} ({op['alg_id']}) — {op['desc'][:100]}"
        for op in candidates[:40]
    )
    return f"""You are analyzing a QGIS C++ API trace to identify which QGIS Processing operators were used.

{f'Context: {task_hint}' if task_hint else ''}

C++ API trace (actual method calls from script execution):
{api_trace[:4000]}

Candidate QGIS Processing operators:
{cand_text}

Select the operators that correspond to the actual GIS data processing
steps in the trace. Ignore UI, rendering, parameter setup, and I/O utilities.
Focus only on spatial/raster data transformations.

Output a JSON object:
{{"identifier_sequence": ["alg_id1", "alg_id2", ...],
  "reasoning": "brief explanation",
  "confidence": 0.0-1.0}}"""


def parse_json(content: str) -> dict | None:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    for p in [r"```json\s*(.*?)\s*```", r"```\s*(.*?)\s*```", r"\{.*\}"]:
        m = re.search(p, content, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1) if "```" in p else m.group(0))
            except json.JSONDecodeError:
                continue
    return None


def llm_select(client, api_trace: str, candidates: list[dict], task_hint: str = "") -> dict:
    prompt = build_llm_prompt(api_trace, candidates, task_hint)
    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": "You are a QGIS C++ API analyst. Output valid JSON only."},
                      {"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=1000,
        )
        return parse_json(resp.choices[0].message.content or "") or {}
    except Exception as e:
        return {"identifier_sequence": [], "reasoning": f"ERROR: {e}"}


# ── C++ API trace parser ──────────────────────────────────────────

def parse_steps_csv(filepath: str) -> list[dict]:
    steps = []
    with open(filepath, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            steps.append(row)
    return steps


def build_api_trace(steps: list[dict], max_steps: int = 60) -> str:
    lines = []
    for i, step in enumerate(steps[:max_steps]):
        name = step.get("normalized_api_name", "") or step.get("name", "")
        desc = step.get("description", "")
        role = step.get("semantic_role", "")
        if role in ("EXPRESSION_ASSIGNMENT", "UI_TEXT_TRANSLATE", "synthetic_expression"):
            continue
        lines.append(f"  {i}: {name} | {desc}"[:150])
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────

def main():
    cat_path = str(ROOT / "爬取GithubQGIS" / "QGIS_Input.csv")
    print(f"[1] Loading QGIS catalog...")
    catalog = load_catalog(cat_path)
    print(f"  {len(catalog)} operators loaded")
    print(f"  Sample: {catalog[50]['alg_id']} - {catalog[50]['name']}")

    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LLM_API_KEY")
    if not api_key:
        sys.exit(1)
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1", timeout=120)

    # Find large _steps.csv files with diverse API calls
    GEE = Path("/home/yll/GEE")
    files = []
    for root, dirs, files_ in os.walk(GEE):
        if "QGIS" not in root:
            continue
        for f in files_:
            if f.endswith("_steps.csv"):
                fp = os.path.join(root, f)
                sz = os.path.getsize(fp)
                if sz > 50000:  # >= 50KB
                    files.append((sz, fp))
        if len(files) >= 10:
            break
    files.sort(key=lambda x: -x[0])

    # Pick 2 diverse scripts (one param-heavy, one with more operations)
    samples = [files[0][1], files[-1][1]] if len(files) >= 2 else [f[1] for f in files]

    for i, fpath in enumerate(samples[:2]):
        print(f"\n{'='*70}")
        print(f"Sample {i+1}: {Path(fpath).name}")
        print(f"{'='*70}")

        # Parse trace
        steps = parse_steps_csv(fpath)
        print(f"  Steps: {len(steps)}")

        # Extract GIS keywords from C++ API names
        trace = build_api_trace(steps)
        api_names = Counter(
            (s.get("normalized_api_name", "") or s.get("name", ""))
            for s in steps
        )
        print(f"  Top C++ APIs:")
        for name, cnt in api_names.most_common(10):
            print(f"    {cnt:3d}x {name[:80]}")

        # Stage 1: keyword extraction
        keywords = extract_gis_keywords(trace)
        print(f"\n  [Stage 1] GIS keywords ({len(keywords)}): {sorted(keywords)[:20]}")

        # Stage 2: catalog matching
        candidates = keyword_match(keywords, catalog)
        print(f"\n  [Stage 2] Catalog matches ({len(candidates)}):")
        for c in candidates[:10]:
            print(f"    {c['alg_id']:35s} score={c['match_score']:2d}  {c['name']}")

        # Stage 3: LLM selection
        print(f"\n  [Stage 3] LLM selection...")
        script_id = Path(fpath).stem.replace("_steps", "")
        result = llm_select(client, trace, candidates, task_hint=script_id)

        seq = result.get("identifier_sequence", [])
        conf = result.get("confidence", 0)
        reasoning = result.get("reasoning", "")[:200]
        print(f"  Selected ({len(seq)} ops, conf={conf:.2f}):")
        for alg in seq:
            print(f"    {alg}")
        print(f"  Reasoning: {reasoning}")

        time.sleep(0.5)


if __name__ == "__main__":
    main()
