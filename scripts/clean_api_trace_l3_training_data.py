#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Clean API-trace derived L3 training samples.

This tool separates the raw API-trace L3 export into:
  - clean rows: high-confidence, non-placeholder, non-conflicting samples
  - weak rows: medium-confidence samples kept as weak supervision only
  - rejected rows: samples that should not be trained on

The goal is to stop placeholder prompts, low-confidence guesses, and same-prompt
multi-label conflicts from entering the main training corpus.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]

PLACEHOLDER_RE = re.compile(r"^\s*qgis script:\s*script_\d+\s*$", re.I)
SCRIPT_TOKEN_RE = re.compile(r"\bscript_\d+\b", re.I)

REJECT_REASONING_PHRASES = [
    "no actual geoprocessing",
    "no actual spatial",
    "no geoprocessing",
    "no spatial",
    "cannot determine",
    "cannot infer",
    "unable to determine",
    "not enough information",
    "insufficient information",
    "purely ui",
    "only ui",
    "only rendering",
    "only symbology",
    "only parameter definitions",
    "only parameter definition",
    "no meaningful",
]

TASK_CODE_MISMATCH_PATTERNS = [
    ("task description mentions", "actual code only"),
    ("task description mentions", "code only"),
    ("actual code only performs",),
    ("provided code is a test file",),
    ("does not directly implement", "inference is based solely"),
    ("inference is based solely on the task description",),
    ("source code appears to be from a different algorithm",),
    ("source code snippet is incomplete", "task description is clear"),
    ("provided code snippet is incomplete", "task description is clear"),
    ("provided code snippet is incomplete", "inference relies heavily on the task description"),
    ("provided code snippet is incomplete", "inference relies primarily on the task description"),
    ("provided source code is incomplete", "task description is clear"),
    ("provided source code is incomplete", "infer the single step"),
    ("task description mentions", "actual code does not contain"),
    ("task description mentions", "actual code performs"),
    ("task description mentions", "provided code is clearly"),
    ("task description mentions a different purpose",),
    ("workflow is inferred from the task description",),
    ("inference relies entirely on the task description",),
    ("based on the task description alone",),
    ("inferred from the task description alone",),
    ("task description appears to describe a different script",),
    ("task description may describe a different script",),
    ("task description describes a different script",),
    ("task description is misleading", "does not match"),
    ("task description", "does not match the actual script code"),
    ("provided source code is for a different script",),
    ("provided code is a different script",),
    ("appears to be from a different script",),
    ("different script or context",),
    ("different script", "workflow is inferred entirely from the task description"),
    ("provided code is for a different tool",),
    ("provided code is from a different tool",),
    ("provided code snippet is from a different tool",),
    ("provided code snippet is from a different script",),
    ("provided code snippet is from a different algorithm",),
    ("script code provided is for", "does not match the task"),
    ("provided script code is unrelated to the task description",),
    ("forcing reliance on the description alone",),
    ("workflow is inferred solely from the task description",),
    ("inference relies solely on the task description",),
    ("provided code snippet is incomplete", "different tool"),
    ("provided source code is from",),
    ("provided source code is incomplete", "different tool"),
    ("provided source code is incomplete", "different script"),
    ("provided source code is incomplete", "different algorithm"),
    ("provided code snippet is incomplete", "different algorithm"),
    ("provided code snippet is incomplete", "different script"),
    ("provided code snippet is incomplete", "does not match"),
    ("source code is from",),
    ("source code snippet is incomplete", "different tool"),
    ("source code snippet is incomplete", "different script"),
    ("source code snippet is incomplete", "different algorithm"),
    ("actual code does not match",),
    ("actual code focuses", "rather than the described"),
]

VECTOR_TEXT_HINTS = {
    "vector", "feature", "features", "shapefile", "parcel", "parcels",
    "road", "roads", "route", "network", "point", "points", "line",
    "lines", "linestring", "polygon", "polygons", "geometry", "geometries",
    "buffer", "intersect", "intersection", "union", "dissolve", "snap",
    "snapping", "nearest", "voronoi", "overlay",
}

RASTER_TEXT_HINTS = {
    "raster", "rasters", "geotiff", "tif", "dem", "band", "bands", "pixel",
    "pixels", "cell", "cells", "slope", "hillshade", "ndvi", "reclassify",
    "reclassified", "zonal", "grid", "mosaic", "vrt", "density",
}

VECTOR_L3_PREFIXES = ("L3_02_",)
RASTER_L3_PREFIXES = ("L3_03_", "L3_04_")

MIN_CLEAN_CONFIDENCE = 0.70
MIN_WEAK_CONFIDENCE = 0.55


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


def _load_records(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("[") or text.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            records = data.get("labeled_workflows", data.get("rows", []))
            if isinstance(records, list):
                return records
            raise ValueError(f"Unsupported JSON container in {path}")
        if isinstance(data, list):
            return data
        if data is not None:
            raise ValueError(f"Unsupported JSON payload in {path}")

    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _strip_markers(l3_codes: list[str] | None) -> list[str]:
    if not l3_codes:
        return []
    return [
        str(code)
        for code in l3_codes
        if str(code) not in {"<START>", "<END>", "<PAD>", "<UNK>"}
    ]


def _task_metadata(row: dict) -> dict:
    meta = row.get("task_metadata", {}) or {}
    return {
        "task_type": meta.get("task_type", "") or "",
        "task_name": meta.get("task_name", "") or "",
        "task_description": meta.get("task_description", "") or "",
    }


def _prompt_signature(row: dict) -> str:
    meta = _task_metadata(row)
    return json.dumps(
        {
            "task_type": _normalize_text(meta["task_type"]),
            "task_name": _normalize_text(meta["task_name"]),
            "task_description": _normalize_text(meta["task_description"]),
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _content_signature(row: dict) -> tuple[str, ...]:
    return tuple(_strip_markers(row.get("l3_codes") or []))


def _parse_confidence(row: dict) -> float | None:
    raw = row.get("_llm_confidence", row.get("confidence"))
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _reasoning_text(row: dict) -> str:
    return _normalize_text(row.get("_llm_reasoning") or row.get("reasoning"))


def _is_placeholder_prompt(row: dict) -> bool:
    meta = _task_metadata(row)
    task_name = _normalize_text(meta["task_name"])
    task_desc = _normalize_text(meta["task_description"])
    combined = f"{task_name} {task_desc}".strip()
    if not combined:
        return True
    if PLACEHOLDER_RE.fullmatch(task_name) or PLACEHOLDER_RE.fullmatch(task_desc):
        return True
    if SCRIPT_TOKEN_RE.search(combined) and len(combined.split()) <= 4:
        return True
    return False


def _has_reject_reason(row: dict) -> tuple[bool, str | None]:
    reasoning = _reasoning_text(row)
    for phrase in REJECT_REASONING_PHRASES:
        if phrase in reasoning:
            return True, phrase
    return False, None


def _has_task_code_mismatch(row: dict) -> bool:
    reasoning = _reasoning_text(row)
    for pattern in TASK_CODE_MISMATCH_PATTERNS:
        if all(phrase in reasoning for phrase in pattern):
            return True
    return False


def _task_l3_modality_mismatch(row: dict) -> bool:
    meta = _task_metadata(row)
    text = _normalize_text(f"{meta['task_name']} {meta['task_description']}")
    words = set(re.findall(r"[a-z0-9_]+", text))
    vector_hits = words & VECTOR_TEXT_HINTS
    raster_hits = words & RASTER_TEXT_HINTS
    content = _content_signature(row)
    if not content:
        return False
    vector_codes = [code for code in content if code.startswith(VECTOR_L3_PREFIXES)]
    raster_codes = [code for code in content if code.startswith(RASTER_L3_PREFIXES)]

    if len(vector_hits) >= 2 and raster_codes and not vector_codes:
        return True
    if len(raster_hits) >= 2 and vector_codes and not raster_codes:
        return True
    return False


def _sample_weight(tier: str, confidence: float | None) -> float:
    if tier == "clean":
        if confidence is None:
            return 0.65
        return round(min(0.85, 0.55 + max(confidence - MIN_CLEAN_CONFIDENCE, 0.0)), 3)
    if tier == "weak":
        if confidence is None:
            return 0.25
        return round(min(0.40, 0.15 + max(confidence - MIN_WEAK_CONFIDENCE, 0.0)), 3)
    return 0.0


def _annotate_row(row: dict, *, tier: str, reason: str, confidence: float | None) -> dict:
    annotated = deepcopy(row)
    annotated["reject_reason"] = reason if tier == "rejected" else ""
    annotated["_training_quality"] = {
        "tier": tier,
        "sample_weight": _sample_weight(tier, confidence),
        "confidence": confidence,
        "reason": reason,
        "prompt_is_placeholder": _is_placeholder_prompt(row),
    }
    return annotated


def clean_api_trace_training_data(rows: list[dict]) -> dict:
    """Return clean / weak / rejected splits with audit metadata."""
    prompt_groups: dict[str, list[int]] = defaultdict(list)
    content_groups: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    for index, row in enumerate(rows):
        prompt = _prompt_signature(row)
        prompt_groups[prompt].append(index)
        content_groups[prompt].add(_content_signature(row))

    conflict_indices: set[int] = set()
    conflict_prompt_count = 0
    for prompt, indices in prompt_groups.items():
        if len(content_groups[prompt]) > 1:
            conflict_indices.update(indices)
            conflict_prompt_count += 1

    clean: list[dict] = []
    weak: list[dict] = []
    rejected: list[dict] = []
    conflicts: list[dict] = []
    reason_counts: Counter[str] = Counter()
    confidence_values: list[float] = []
    tier_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()

    for index, row in enumerate(rows):
        source_counts[(row.get("source_original") or row.get("source") or "unknown").strip()] += 1
        confidence = _parse_confidence(row)
        if confidence is not None:
            confidence_values.append(confidence)

        placeholder = _is_placeholder_prompt(row)
        has_reason_reject, reject_phrase = _has_reject_reason(row)
        has_mismatch = _has_task_code_mismatch(row)
        has_modality_mismatch = _task_l3_modality_mismatch(row)
        content = _content_signature(row)
        empty_codes = not content
        conflict = index in conflict_indices

        if placeholder:
            tier = "rejected"
            reason = "placeholder_prompt"
        elif empty_codes:
            tier = "rejected"
            reason = "empty_l3_codes"
        elif has_reason_reject:
            tier = "rejected"
            reason = f"reasoning:{reject_phrase}"
        elif has_mismatch:
            tier = "rejected"
            reason = "task_code_mismatch"
        elif has_modality_mismatch:
            tier = "rejected"
            reason = "task_l3_modality_mismatch"
        elif conflict:
            tier = "rejected"
            reason = "same_prompt_multi_label_conflict"
        elif confidence is None:
            tier = "rejected"
            reason = "missing_confidence"
        elif confidence >= MIN_CLEAN_CONFIDENCE:
            tier = "clean"
            reason = "high_confidence"
        elif confidence >= MIN_WEAK_CONFIDENCE:
            tier = "weak"
            reason = "medium_confidence"
        else:
            tier = "rejected"
            reason = "low_confidence"

        annotated = _annotate_row(row, tier=tier, reason=reason, confidence=confidence)
        tier_counts[tier] += 1
        reason_counts[reason] += 1

        if tier == "clean":
            clean.append(annotated)
        elif tier == "weak":
            weak.append(annotated)
        else:
            rejected.append(annotated)
            if conflict:
                conflicts.append(annotated)

    summary = {
        "total_rows": len(rows),
        "clean_count": len(clean),
        "weak_count": len(weak),
        "rejected_count": len(rejected),
        "conflict_count": len(conflicts),
        "conflict_prompt_count": conflict_prompt_count,
        "source_counts": dict(source_counts),
        "tier_counts": dict(tier_counts),
        "reason_counts": dict(reason_counts),
        "confidence_mean": round(statistics.mean(confidence_values), 4) if confidence_values else None,
        "confidence_median": round(statistics.median(confidence_values), 4) if confidence_values else None,
        "confidence_min": round(min(confidence_values), 4) if confidence_values else None,
        "confidence_max": round(max(confidence_values), 4) if confidence_values else None,
        "clean_rate": round(len(clean) / max(len(rows), 1), 4),
        "weak_rate": round(len(weak) / max(len(rows), 1), 4),
        "rejected_rate": round(len(rejected) / max(len(rows), 1), 4),
    }

    return {
        "summary": summary,
        "clean": clean,
        "weak": weak,
        "rejected": rejected,
        "conflicts": conflicts,
    }


def _render_report(report: dict, input_path: Path) -> str:
    summary = report["summary"]
    lines = [
        "# API Trace L3 Cleaning Report",
        "",
        f"Input: `{input_path}`",
        "",
        "## Summary",
        "",
        f"- Total rows: {summary['total_rows']}",
        f"- Clean: {summary['clean_count']}",
        f"- Weak: {summary['weak_count']}",
        f"- Rejected: {summary['rejected_count']}",
        f"- Conflicts: {summary['conflict_count']}",
        f"- Conflict prompts: {summary['conflict_prompt_count']}",
        f"- Confidence mean: {summary['confidence_mean']}",
        f"- Confidence median: {summary['confidence_median']}",
        f"- Confidence min/max: {summary['confidence_min']} / {summary['confidence_max']}",
        "",
        "## Tier Counts",
        "",
    ]
    for key, value in sorted(summary["tier_counts"].items()):
        lines.append(f"- {key}: {value}")

    reject_reasons = Counter(
        row.get("reject_reason") or row.get("_training_quality", {}).get("reason", "")
        for row in report["rejected"]
    )
    lines.extend(["", "## Reject Reasons", ""])
    for reason, count in reject_reasons.most_common(20):
        lines.append(f"- {reason}: {count}")

    lines.extend(["", "## Decision Reasons", ""])
    for reason, count in Counter(summary["reason_counts"]).most_common(20):
        lines.append(f"- {reason}: {count}")
    return "\n".join(lines) + "\n"


def clean_api_trace_file(input_path: Path, out_dir: Path) -> dict:
    rows = _load_records(input_path)
    report = clean_api_trace_training_data(rows)

    out_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out_dir / "API_trace_to_L3_TRAINING_CLEAN.jsonl", report["clean"])
    _write_jsonl(out_dir / "API_trace_to_L3_TRAINING_WEAK.jsonl", report["weak"])
    _write_jsonl(out_dir / "API_trace_to_L3_TRAINING_REJECTED.jsonl", report["rejected"])
    _write_jsonl(out_dir / "API_trace_to_L3_TRAINING_CONFLICTS.jsonl", report["conflicts"])
    (out_dir / "api_trace_l3_cleaning_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "api_trace_l3_cleaning_report.md").write_text(
        _render_report(report, input_path),
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default=str(ROOT / "outputs_v2" / "API_trace_to_L3_TRAINING_FINAL.jsonl"),
        help="Raw API-trace training file.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "outputs_v2" / "diagnostics" / "api_trace_l3_cleaning"),
        help="Directory for cleaned outputs and report files.",
    )
    args = parser.parse_args()

    report = clean_api_trace_file(Path(args.input), Path(args.out_dir))
    summary = report["summary"]
    print(f"Wrote cleaned outputs to {args.out_dir}")
    print(
        "Summary: "
        f"clean={summary['clean_count']} weak={summary['weak_count']} "
        f"rejected={summary['rejected_count']} conflicts={summary['conflict_count']}"
    )


if __name__ == "__main__":
    main()
