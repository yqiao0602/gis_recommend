#!/usr/bin/env python3
"""
LLM classifier: assign each open_landing task to one of 48 task_types.
Output: updated task JSONL with correct task_type field.
"""

import json, os, re, sys, time

TASK_TYPES = {
    0: "Unknown", 1: "Air quality", 2: "Atmospheric radiation",
    3: "Atmospheric temperature", 4: "Atmospheric water vapor", 5: "Atmospheric winds",
    6: "Atmospheric/ocean indicators", 7: "Biospheric indicators", 8: "Boundaries",
    9: "Carbon flux", 10: "Climate indicators", 11: "Clouds",
    12: "Cryospheric indicators", 13: "Environmental governance/management",
    14: "Environmental impacts", 15: "Erosion/sedimentation", 16: "Forest science",
    17: "Frozen ground", 18: "Geomorphic landforms/processes", 19: "Glaciers/ice sheets",
    20: "Ground water", 21: "Habitat conversion/fragmentation", 22: "Human settlements",
    23: "Infrastructure", 24: "Land ice/ocean classification",
    25: "Land surface/agriculture indicators", 26: "Land use/land cover",
    27: "Natural hazards", 28: "Other / Sparse", 29: "Population",
    30: "Precipitation", 31: "Regional climate levels", 32: "Salinity/density",
    33: "Sea ice", 34: "Sea surface temperature", 35: "Sea surface topography",
    36: "Snow/ice", 37: "Soils", 38: "Spectral/Engineering",
    39: "Surface radiative properties", 40: "Surface thermal properties",
    41: "Surface water", 42: "Terrestrial hydrosphere indicators",
    43: "Topography", 44: "Vegetation", 45: "Water quality",
    46: "Weather events", 47: "Vector Analysis",
}

TYPE_LIST = "\n".join(f"  {tid}: {tname}" for tid, tname in sorted(TASK_TYPES.items()))

PROMPT = f"""Classify this GIS task. Return ONLY the ID number. DO NOT return text, DO NOT wrap in markdown.

Task types:
{TYPE_LIST}

Task: {{task}}

Key rules:
- QGIS vector operations (buffer, clip, intersect, merge, dissolve, spatial join, centroid, extract, select, reproject, simplify, export, fix geometries, split, merge, delete, snap, aggregate, update, rasterize polygon, polygonize raster) → 47 (Vector Analysis)
- Raster operations (NDVI, DEM, slope, aspect, hillshade, reclassify, resample, mosaic, warp, clip raster, fill nodata, contour, zonal stats, raster calculator, threshold, classify, sample, change detection, cost distance) → match topic (43=Topography, 44=Vegetation, 30=Precipitation, etc.)
- If no clear match → 28 (Other / Sparse)

Return ONLY a single integer. Example: 47"""


def classify(client, task_text: str) -> dict:
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "system", "content": "Output ONLY an integer task type ID. Nothing else."},
                          {"role": "user", "content": PROMPT.format(task=task_text)}],
                temperature=0.1, max_tokens=20,
            )
            content = (resp.choices[0].message.content or "").strip()
            # Extract integer
            m = re.search(r'\d+', content)
            tid = int(m.group(0)) if m else 0
            tid = max(0, min(47, tid))
            tname = TASK_TYPES.get(tid, "Unknown")
            return {"task_type_id": tid, "task_type": tname}
        except Exception as e:
            if attempt == 2:
                print(f"    DEBUG: {e}")
            time.sleep(0.3)
    return {"task_type_id": 0, "task_type": "Unknown"}


def main():
    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LLM_API_KEY")
    if not api_key:
        sys.exit(1)
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1", timeout=120)

    # Load tasks
    task_file = "outputs_v2/diagnostics/open_landing_eval/open_landing_tasks.jsonl"
    tasks = []
    with open(task_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                tasks.append(json.loads(line))
    print(f"Loaded {len(tasks)} tasks from {task_file}")

    # Classify each task
    results = []
    type_counts = {}
    for i, t in enumerate(tasks):
        task_text = t.get("task_name", "") + " " + t.get("task_description", "")
        result = classify(client, task_text)
        tid = result.get("task_type_id", 0)
        tname = result.get("task_type", "Unknown")

        type_counts[tname] = type_counts.get(tname, 0) + 1
        print(f"  [{i+1:2d}/{len(tasks)}] {tname:35s}  {task_text[:60]}...")

        # Update task
        t["task_type"] = tname
        t["task_type_id"] = tid
        results.append(t)
        time.sleep(0.1)

    # Save
    out_file = task_file.replace(".jsonl", "_classified.jsonl")
    with open(out_file, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\nSaved {len(results)} tasks to {out_file}")
    print(f"\nTask type distribution:")
    for tname, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {cnt:3d}  {tname}")


if __name__ == "__main__":
    main()
