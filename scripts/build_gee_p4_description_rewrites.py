#!/usr/bin/env python3
"""Build deterministic P4 chain-faithful task-text rewrites for GEE rows.

This pass handles only the P4 rows already adjudicated as `needs_edit`.
It rewrites task name/description to match the source-extracted core operator
chain. It deliberately does not emit training rows because the P4 chain still
requires a separate deterministic operator-to-L3 canonicalization gate.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_gee_training_admission import _atomic_write_text  # noqa: E402


DEFAULT_REPORT_DIR = ROOT / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
DEFAULT_P4_ADJUDICATION = DEFAULT_REPORT_DIR / "gee_p4_review_adjudication_28_v1.jsonl"
OUTPUT_PREFIX = "gee_p4_rewrite_10_v1"
NEEDS_EDIT_DECISION = "needs_edit"
TRAINING_ADMISSION = "not_granted_pending_l3_mapping_and_export_gate"
NEW_L3_SEQUENCE_STATUS = "pending_operator_l3_canonicalization"


@dataclass(frozen=True)
class P4RewriteSpec:
    task_name: str
    task_description: str
    known_omissions: tuple[str, ...]


REWRITE_SPECS: dict[str, P4RewriteSpec] = {
    "gee_raster_core_review_004": P4RewriteSpec(
        task_name="Prepare Sentinel-2 water-index masks and quality mosaic",
        task_description=(
            "Filter site features and Sentinel-2 imagery by region and date, "
            "clip the images, decode QA cloud bits to update masks, compute "
            "water-index and wetness bands, add them to each image, and build "
            "a quality mosaic using the retained index band."
        ),
        known_omissions=(
            "final thresholded water-extent product",
            "map display layers",
            "print output",
        ),
    ),
    "gee_raster_core_review_005": P4RewriteSpec(
        task_name="Construct land-cover training samples from joined imagery",
        task_description=(
            "Convert labeled training features to centroids, merge training "
            "feature collections, join them with nearby Landsat surface-reflectance "
            "images, apply cloud masking and calibrated band selection, sample "
            "image values at the training locations, flatten the sampled collection, "
            "and inspect the first sample row."
        ),
        known_omissions=(
            "full classifier training and prediction",
            "map styling and display layers",
            "final land-cover map use",
        ),
    ),
    "gee_raster_core_review_006": P4RewriteSpec(
        task_name="Prepare Sentinel-2 spectral and texture features",
        task_description=(
            "Filter Sentinel-2 Level-1 imagery by date, cloud metadata, and "
            "bounds, decode QA bits to mask clouds, select the first retained "
            "image, clip it to the region, and derive B8 texture features using "
            "a GLCM texture operation."
        ),
        known_omissions=(
            "training and testing samples",
            "final tea-area classification",
            "map display and band diagnostics",
        ),
    ),
    "gee_raster_core_review_021": P4RewriteSpec(
        task_name="Filter Sentinel-1 SAR imagery for minimum backscatter",
        task_description=(
            "Filter Sentinel-1 GRD images by required VV/VH polarizations, "
            "instrument mode, region, and date; compute the minimum image from "
            "the retained collection; select backscatter polarizations; and clip "
            "the result to the study polygon."
        ),
        known_omissions=(
            "terrain-correction internals",
            "map centering and display",
            "downstream interpretation",
        ),
    ),
    "gee_raster_core_review_027": P4RewriteSpec(
        task_name="Min-max normalize a Sentinel-2 median composite",
        task_description=(
            "Filter Sentinel-2 imagery by date, region, and metadata, build a "
            "median composite, clip it to the study geometry, compute per-band "
            "min-max statistics, unit-scale each selected band, stack the "
            "normalized bands, and rename the output bands."
        ),
        known_omissions=(
            "cloud-mask update-mask semantics from the source helper",
            "display layers",
        ),
    ),
    "gee_raster_core_review_029": P4RewriteSpec(
        task_name="Build Sentinel-1 composites and train a Random Forest from samples",
        task_description=(
            "Create date-window Sentinel-1 composites, filter out empty composites, "
            "select a representative clipped image, sample training regions from "
            "the retained image, initialize a Random Forest classifier, and train "
            "it on the sampled features."
        ),
        known_omissions=(
            "adaptive-threshold reduceRegion logic",
            "post-training classify output",
            "final open-water or submerged-vegetation map",
        ),
    ),
    "gee_raster_core_review_033": P4RewriteSpec(
        task_name="Construct Landsat vegetation-index yearly composites",
        task_description=(
            "Filter Landsat imagery by region and yearly windows, apply QA cloud "
            "masking, clip images, compute NDVI, EVI, and SAVI vegetation-index "
            "bands, add the derived bands, and build yearly mean index composites."
        ),
        known_omissions=(
            "GIF or video thumbnail generation",
            "map display layers",
            "long-form output presentation",
        ),
    ),
    "gee_raster_core_review_034": P4RewriteSpec(
        task_name="Preprocess MODIS phenology bands and masks",
        task_description=(
            "Filter MCD12Q2 phenology imagery by date, select phenology and "
            "cycle-count bands, apply NumCycles and phenology masks, adjust "
            "day-of-year values relative to a baseline date, and convert retained "
            "phenology-mask outputs to integer bands."
        ),
        known_omissions=(
            "full LAI capping and processing",
            "phenology interpretation steps",
            "print diagnostics",
        ),
    ),
    "gee_raster_core_review_044": P4RewriteSpec(
        task_name="Summarize algae-mask counts by region and elevation context",
        task_description=(
            "Prepare glacier and algae masks, filter MODIS imagery and regional "
            "features, build mask images for retained algae/elevation strata, "
            "compute regional pixel-count summaries with reduceRegions, and carry "
            "the bounded grid and region attributes used by the statistical extraction."
        ),
        known_omissions=(
            "full timing-of-maximum algae analysis",
            "pixel-level temporal statistics",
            "unverified elevation-stratified outputs",
        ),
    ),
    "gee_raster_core_review_047": P4RewriteSpec(
        task_name="Decode MODIS QA bits and build a combined mask",
        task_description=(
            "Select MODIS QA bands, repeatedly extract bit ranges with bitwise "
            "operations and shifts, derive cloud, shadow, and land/water logical "
            "conditions, combine the QA conditions, and update the image mask "
            "with the retained combined mask."
        ),
        known_omissions=(
            "overlay and display layers for individual QA components",
        ),
    ),
}


CSV_FIELDS = (
    "review_id",
    "script_id",
    "review_split",
    "task_name",
    "task_description",
    "original_task_name",
    "original_task_description",
    "operator_sequence",
    "old_l3_sequence",
    "new_l3_sequence_status",
    "known_omissions",
    "quality_flags",
    "source_sha256",
    "source_path",
    "evidence_snippet",
    "description_policy",
    "training_admission",
    "validation_eligible",
    "test_eligible",
    "adjudication_basis",
    "adjudication_notes",
)


@dataclass(slots=True)
class P4RewriteResult:
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path} line {line_number} must be a JSON object")
            rows.append(row)
    if not rows:
        raise ValueError(f"{path} contains no rows")
    return rows


def _check_specs_match(needs_edit_rows: list[dict[str, Any]]) -> None:
    needs_edit_ids = {str(row.get("review_id") or "") for row in needs_edit_rows}
    missing_specs = needs_edit_ids.difference(REWRITE_SPECS)
    extra_specs = set(REWRITE_SPECS).difference(needs_edit_ids)
    if missing_specs or extra_specs:
        raise ValueError(
            "P4 rewrite specs do not match needs_edit rows: "
            f"missing={sorted(missing_specs)}, extra={sorted(extra_specs)}"
        )


def _rewrite_row(row: dict[str, Any]) -> dict[str, Any]:
    review_id = str(row["review_id"])
    spec = REWRITE_SPECS[review_id]
    operator_sequence = list(row.get("new_core_operator_sequence") or [])
    old_l3_sequence = list(row.get("old_l3_sequence") or [])
    if not operator_sequence:
        raise ValueError(f"missing new_core_operator_sequence for {review_id}")
    if not old_l3_sequence:
        raise ValueError(f"missing old_l3_sequence lineage for {review_id}")
    return {
        "schema": "gis_recommend.gee_p4_description_rewrite.v1",
        "review_id": review_id,
        "script_id": row.get("script_id", ""),
        "review_split": row.get("review_split", ""),
        "task_name": spec.task_name,
        "task_description": spec.task_description,
        "original_task_name": row.get("task_name", ""),
        "original_task_description": row.get("task_description", ""),
        "operator_sequence": operator_sequence,
        "old_l3_sequence": old_l3_sequence,
        "new_l3_sequence_status": NEW_L3_SEQUENCE_STATUS,
        "known_omissions": list(spec.known_omissions),
        "quality_flags": list(row.get("quality_flags") or []),
        "source_sha256": row.get("source_sha256", ""),
        "source_path": row.get("source_path", ""),
        "evidence_snippet": row.get("evidence_snippet", ""),
        "description_policy": "rewritten_chain_faithful",
        "training_admission": TRAINING_ADMISSION,
        "validation_eligible": False,
        "test_eligible": False,
        "adjudication_basis": row.get("adjudication_basis", ""),
        "adjudication_notes": row.get("human_review_notes", ""),
    }


def build_p4_description_rewrites(*, p4_adjudication_jsonl_path: Path) -> P4RewriteResult:
    adjudicated_rows = _load_jsonl(p4_adjudication_jsonl_path)
    needs_edit_rows = [
        row
        for row in adjudicated_rows
        if row.get("human_should_enter_train_only") == NEEDS_EDIT_DECISION
    ]
    if not needs_edit_rows:
        raise ValueError("P4 adjudication contains no needs_edit rows")
    _check_specs_match(needs_edit_rows)
    rows = [_rewrite_row(row) for row in sorted(needs_edit_rows, key=lambda item: item["review_id"])]
    summary = {
        "schema": "gis_recommend.gee_p4_description_rewrite_summary.v1",
        "inputs": {
            "p4_adjudication": str(Path(p4_adjudication_jsonl_path)),
        },
        "counts": {
            "adjudicated_rows": len(adjudicated_rows),
            "rewrite_rows": len(rows),
            "training_rows_emitted": 0,
            "validation_rows_emitted": 0,
            "test_rows_emitted": 0,
        },
        "rewrite_ids": [row["review_id"] for row in rows],
        "decision": {
            "training_admission": TRAINING_ADMISSION,
            "validation_eligible": False,
            "test_eligible": False,
            "next_gate": "canonicalize P4 operators to L3, then run schema/export gate for accepted plus rewritten rows",
        },
        "policy": {
            "llm_used": False,
            "description_policy": "rewritten_chain_faithful",
            "preserve_operator_order": True,
            "allow_operator_add_delete_reorder": False,
            "old_l3_sequence_is_lineage_only": True,
            "known_omissions_are_sidecar_only": True,
        },
    }
    return P4RewriteResult(rows=rows, summary=summary)


def _jsonl_text(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field, "")) for field in CSV_FIELDS})


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _render_report(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# GEE P4 Description Rewrites",
        "",
        "Deterministic chain-faithful task-text rewrites for the P4 rows adjudicated as `needs_edit`.",
        "This pass does not emit training rows because the new P4 operator chains still require a separate L3 canonicalization gate.",
        "",
        "## Summary",
        "",
        f"- Rewrite rows: {summary['counts']['rewrite_rows']}",
        f"- Training rows emitted: {summary['counts']['training_rows_emitted']}",
        f"- Training admission: `{summary['decision']['training_admission']}`",
        f"- Validation eligible: `{summary['decision']['validation_eligible']}`",
        f"- Test eligible: `{summary['decision']['test_eligible']}`",
        "",
        "## Rows",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"### {row['review_id']}",
                "",
                f"- Task name: {row['task_name']}",
                f"- Task description: {row['task_description']}",
                f"- Operator calls retained: {len(row['operator_sequence'])}",
                f"- New L3 status: `{row['new_l3_sequence_status']}`",
                f"- Known omissions: {', '.join(row['known_omissions'])}",
                "",
            ]
        )
    return "\n".join(lines)


def write_outputs(
    result: P4RewriteResult,
    output_dir: Path,
    *,
    output_prefix: str = OUTPUT_PREFIX,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"{output_prefix}.csv"
    jsonl_path = output_dir / f"{output_prefix}.jsonl"
    summary_path = output_dir / f"{output_prefix}_summary.json"
    report_path = output_dir / f"{output_prefix}_report.md"
    hash_ledger_path = output_dir / f"{output_prefix}_hash_ledger.json"

    _write_csv(csv_path, result.rows)
    _atomic_write_text(jsonl_path, _jsonl_text(result.rows))
    _atomic_write_text(summary_path, json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True))
    _atomic_write_text(report_path, _render_report(result.summary, result.rows))

    source_input = Path(result.summary["inputs"]["p4_adjudication"])
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            "p4_adjudication": {
                "path": str(source_input),
                "sha256": _sha256(source_input),
            }
        },
        "artifacts": {
            csv_path.name: {"path": str(csv_path), "sha256": _sha256(csv_path), "bytes": csv_path.stat().st_size},
            jsonl_path.name: {"path": str(jsonl_path), "sha256": _sha256(jsonl_path), "bytes": jsonl_path.stat().st_size},
            summary_path.name: {"path": str(summary_path), "sha256": _sha256(summary_path), "bytes": summary_path.stat().st_size},
            report_path.name: {"path": str(report_path), "sha256": _sha256(report_path), "bytes": report_path.stat().st_size},
        },
    }
    _atomic_write_text(hash_ledger_path, json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True))
    return {
        "csv": csv_path,
        "jsonl": jsonl_path,
        "summary": summary_path,
        "report": report_path,
        "hash_ledger": hash_ledger_path,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--p4-adjudication", type=Path, default=DEFAULT_P4_ADJUDICATION)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    args = parser.parse_args(argv)
    result = build_p4_description_rewrites(p4_adjudication_jsonl_path=args.p4_adjudication)
    return write_outputs(result, args.output_dir, output_prefix=args.output_prefix)


if __name__ == "__main__":
    main()
