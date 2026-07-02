"""Task type classifier for L3 inference pipeline.

Provides LLM-based task type classification that maps natural-language GIS
queries to one of 48 pre-defined task types.  This is the canonical integration
point for intent recognition — every inference entry point that receives a raw
user query should route through this module before calling the L3 inferencer.

Environment: loads ``.env`` automatically on first import so that API keys
are available from the project root without manual exporting.
"""

from __future__ import annotations

import os
import re
import time

# Auto-load .env so DEEPSEEK_API_KEY / LLM_API_KEY are available.
try:
    from ..config.env import load_env as _load_env
    _load_env()
except Exception:
    pass

TASK_TYPES: dict[int, str] = {
    0: "Unknown",
    1: "Air quality",
    2: "Atmospheric radiation",
    3: "Atmospheric temperature",
    4: "Atmospheric water vapor",
    5: "Atmospheric winds",
    6: "Atmospheric/ocean indicators",
    7: "Biospheric indicators",
    8: "Boundaries",
    9: "Carbon flux",
    10: "Climate indicators",
    11: "Clouds",
    12: "Cryospheric indicators",
    13: "Environmental governance/management",
    14: "Environmental impacts",
    15: "Erosion/sedimentation",
    16: "Forest science",
    17: "Frozen ground",
    18: "Geomorphic landforms/processes",
    19: "Glaciers/ice sheets",
    20: "Ground water",
    21: "Habitat conversion/fragmentation",
    22: "Human settlements",
    23: "Infrastructure",
    24: "Land ice/ocean classification",
    25: "Land surface/agriculture indicators",
    26: "Land use/land cover",
    27: "Natural hazards",
    28: "Other / Sparse",
    29: "Population",
    30: "Precipitation",
    31: "Regional climate levels",
    32: "Salinity/density",
    33: "Sea ice",
    34: "Sea surface temperature",
    35: "Sea surface topography",
    36: "Snow/ice",
    37: "Soils",
    38: "Spectral/Engineering",
    39: "Surface radiative properties",
    40: "Surface thermal properties",
    41: "Surface water",
    42: "Terrestrial hydrosphere indicators",
    43: "Topography",
    44: "Vegetation",
    45: "Water quality",
    46: "Weather events",
    47: "Vector Analysis",
}

TYPE_LIST = "\n".join(f"  {tid}: {tname}" for tid, tname in sorted(TASK_TYPES.items()))

CLASSIFY_PROMPT = f"""Classify this GIS task. Return ONLY the ID number. DO NOT return text, DO NOT wrap in markdown.

Task types:
{TYPE_LIST}

Task: {{task}}

Key rules:
- QGIS vector operations (buffer, clip, intersect, merge, dissolve, spatial join, centroid, extract, select, reproject, simplify, export, fix geometries, split, merge, delete, snap, aggregate, update, rasterize polygon, polygonize raster) → 47 (Vector Analysis)
- Raster operations (NDVI, DEM, slope, aspect, hillshade, reclassify, resample, mosaic, warp, clip raster, fill nodata, contour, zonal stats, raster calculator, threshold, classify, sample, change detection, cost distance) → match topic (43=Topography, 44=Vegetation, 30=Precipitation, etc.)
- If no clear match → 28 (Other / Sparse)

Return ONLY a single integer. Example: 47"""


def _get_client():
    """Lazily create an OpenAI client pointed at deepseek-chat."""
    from openai import OpenAI  # noqa: F811

    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LLM_API_KEY")
    if not api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY or LLM_API_KEY environment variable is required "
            "for task type classification."
        )
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1", timeout=120)


_client = None  # singleton, created on first call


def classify_task_type(task_text: str, fallback: str = "Unknown") -> dict:
    """Classify a single natural-language GIS task.

    Args:
        task_text: The full task description (name + description).
        fallback: Returned task_type string when classification fails.

    Returns:
        dict with keys ``task_type_id`` (int) and ``task_type`` (str).
        ``task_type_id`` is suitable for the L3 model's task_type embedding.
    """
    global _client
    if _client is None:
        _client = _get_client()

    for attempt in range(3):
        try:
            resp = _client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "Output ONLY an integer task type ID. Nothing else."},
                    {"role": "user", "content": CLASSIFY_PROMPT.format(task=task_text)},
                ],
                temperature=0.1,
                max_tokens=20,
            )
            content = (resp.choices[0].message.content or "").strip()
            m = re.search(r"\d+", content)
            tid = int(m.group(0)) if m else 0
            tid = max(0, min(47, tid))
            tname = TASK_TYPES.get(tid, fallback)
            return {"task_type_id": tid, "task_type": tname}
        except Exception:
            if attempt < 2:
                time.sleep(0.3)
    return {"task_type_id": 0, "task_type": fallback}


def maybe_classify(
    task_name: str = "",
    task_description: str = "",
    task_type: str = "Unknown",
) -> str:
    """Return a resolved task_type string, classifying via LLM if unknown.

    This is the canonical entry point for inference callers: if the caller
    already knows the task type it is passed through unchanged; otherwise
    we ask the LLM to classify the combined task text.

    Args:
        task_name: Short task name / title.
        task_description: Longer natural-language description.
        task_type: If already known (e.g. from a UI selector) pass it here.

    Returns:
        A task type string matching one of the 48 entries in TASK_TYPES.
    """
    if task_type and task_type != "Unknown":
        return task_type

    # Build classification input — prefer description when available
    text = f"{task_name} {task_description}".strip()
    if not text:
        return "Unknown"

    result = classify_task_type(text, fallback="Unknown")
    return result.get("task_type", "Unknown")
