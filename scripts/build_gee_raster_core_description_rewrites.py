#!/usr/bin/env python3
"""Build deterministic P2 chain-faithful descriptions for GEE raster-core rows.

This pass only rewrites the eight P0 `rewrite_description_then_train` rows. It
does not call an LLM, does not repair extractor gaps, does not export token ids,
and does not grant validation/test or dataset-level training admission.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.data.gee_raster_core_schema import (  # noqa: E402
    SCHEMA as TRAIN_ROW_SCHEMA,
    validate_core_train_row,
)
from scripts.audit_gee_training_admission import _atomic_write_text  # noqa: E402


DEFAULT_REPORT_DIR = ROOT / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
DEFAULT_SALVAGE_CSV = DEFAULT_REPORT_DIR / "gee_salvage_50_v1.csv"
DEFAULT_SOURCE_SNIPPETS = DEFAULT_REPORT_DIR / "source_evidence_snippets.jsonl"

REWRITE_BUCKET = "rewrite_description_then_train"
OUTPUT_PREFIX = "gee_p2_rewrite_8_v1"


@dataclass(frozen=True)
class RewriteSpec:
    task_name: str
    task_description: str
    known_omissions: tuple[str, ...]


REWRITE_SPECS: dict[str, RewriteSpec] = {
    "gee_raster_core_review_002": RewriteSpec(
        task_name="Summarize mosaicked water-vapor imagery by polygons",
        task_description=(
            "Select the water-vapor band from a Sentinel-2 image collection, "
            "mosaic the selected imagery, compute zonal mean water-vapor values "
            "for polygons, and apply the retained limit operation."
        ),
        known_omissions=(
            "polygon area multiplication",
            "water-vapor volume estimate",
            "top-5 ranking",
            "map display",
        ),
    ),
    "gee_raster_core_review_003": RewriteSpec(
        task_name="Summarize vegetated area from an NDVI mask",
        task_description=(
            "Filter Sentinel-2 imagery by region, date, and metadata, mosaic and "
            "clip the imagery, compute and rename NDVI, apply a vegetation "
            "threshold mask, multiply the masked pixels by pixel area, and reduce "
            "the result over the region to summarize vegetated area."
        ),
        known_omissions=(
            "map display layers",
            "NDVI visualization palette",
            "printed non-vegetated and total area summaries",
        ),
    ),
    "gee_raster_core_review_015": RewriteSpec(
        task_name="Calculate annual precipitation zonal means",
        task_description=(
            "Select precipitation imagery, filter the image collection to the "
            "target year, reduce the collection into an annual precipitation "
            "image, and compute polygon zonal mean precipitation with "
            "reduceRegions."
        ),
        known_omissions=(
            "watershed area calculation",
            "appending area properties",
            "raster or feature export",
        ),
    ),
    "gee_raster_core_review_016": RewriteSpec(
        task_name="Build an alert-proximity cumulative-cost mask",
        task_description=(
            "Compute cumulative cost from alert locations over a raster cost "
            "surface, threshold the cost image to retain locations within the "
            "distance limit, and filter the related image collection used by the "
            "retained core chain."
        ),
        known_omissions=(
            "peat-forest overlay",
            "alert-point display",
            "visual buffer assessment",
            "map display layers",
        ),
    ),
    "gee_raster_core_review_019": RewriteSpec(
        task_name="Detect irrigated areas with NDVI-temperature masking",
        task_description=(
            "Filter Landsat imagery by date and cloud criteria, build median "
            "composites, compute NDVI and temperature-derived images, combine "
            "threshold conditions, apply the resulting irrigation mask, multiply "
            "by pixel area, and reduce the masked area over the region."
        ),
        known_omissions=(
            "histogram outputs",
            "chart analysis",
            "map display layers",
        ),
    ),
    "gee_raster_core_review_025": RewriteSpec(
        task_name="Classify land cover and summarize class area",
        task_description=(
            "Add derived bands to imagery, filter image collections, select "
            "predictor bands, sample training regions, configure and train a "
            "Random Forest classifier, classify the image, add pixel-area "
            "information, reduce the classified image over the region, and "
            "flatten the resulting feature collection."
        ),
        known_omissions=(
            "accuracy evaluation",
            "confusion matrix",
            "class accuracy metrics",
        ),
    ),
    "gee_raster_core_review_032": RewriteSpec(
        task_name="Filter a calibrated GPM precipitation collection",
        task_description=(
            "Select calibrated precipitation from the GPM IMERG image collection, "
            "filter the collection by date, and filter it by the study geometry."
        ),
        known_omissions=(
            "clipping",
            "downstream temporal analysis",
            "downstream spatial analysis",
        ),
    ),
    "gee_raster_core_review_048": RewriteSpec(
        task_name="Prepare TerraClimate mean and banded climate imagery",
        task_description=(
            "Select TerraClimate variables, compute their long-term mean image, "
            "select precipitation imagery, convert the precipitation collection "
            "to bands, select image bands, and rename the retained climate bands."
        ),
        known_omissions=(
            "annual composites for 2001-2019",
            "WorldClim comparison",
            "print and band-inspection output",
        ),
    ),
}

REWRITE_SPECS_V2: dict[str, RewriteSpec] = {
    **REWRITE_SPECS,
    "gee_raster_core_review_016": RewriteSpec(
        task_name="Build an alert-proximity cumulative-cost mask",
        task_description=(
            "Compute cumulative cost from alert locations over a constant raster "
            "cost surface, threshold the cost image to retain locations within "
            "the distance limit, and apply the retained country-code collection "
            "filter for the study-region boundary features."
        ),
        known_omissions=(
            "peat-forest overlay",
            "alert-point display",
            "visual buffer assessment",
            "map display layers",
        ),
    ),
    "gee_raster_core_review_019": RewriteSpec(
        task_name="Detect irrigated areas with NDVI-temperature masking",
        task_description=(
            "Filter Landsat imagery by date and WRS path/row metadata, build "
            "median composites, compute NDVI and temperature-derived images, "
            "combine threshold conditions, apply the resulting irrigation mask, "
            "multiply by pixel area, and reduce the masked area over the region."
        ),
        known_omissions=(
            "histogram outputs",
            "chart analysis",
            "map display layers",
        ),
    ),
}

REWRITE_SPECS_BY_VERSION = {
    "v1": REWRITE_SPECS,
    "v2": REWRITE_SPECS_V2,
}

FORBIDDEN_TEXT_MARKERS = (
    "export",
    "map.addlayer",
    "visualization",
    "visual layers",
    "chart",
    "histogram",
    "printed",
    "print ",
    "worldclim",
    "top 5",
    "accuracy evaluation",
    "confusion matrix",
)


@dataclass(slots=True)
class RewriteResult:
    report: dict[str, Any]
    rows: list[dict[str, Any]]
    train_rows: list[dict[str, Any]]


def _load_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"{path} contains no rows")
    return rows


def _load_snippets(path: Path) -> dict[str, str]:
    snippets: dict[str, str] = {}
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            review_id = str(record.get("review_id") or "")
            evidence_lines = record.get("evidence_lines") or []
            if not review_id:
                raise ValueError(f"missing review_id in snippets line {line_number}")
            snippet = "\n".join(
                f"{item.get('line')}: {item.get('text')}"
                for item in evidence_lines[:12]
                if isinstance(item, dict)
            ).strip()
            snippets[review_id] = snippet
    return snippets


def _json_list(value: str, *, field: str, review_id: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid {field} JSON for {review_id}: {exc}") from exc
    if not isinstance(parsed, list) or any(not isinstance(item, str) for item in parsed):
        raise ValueError(f"{field} must be a JSON string list for {review_id}")
    return parsed


def _check_no_forbidden_text(row: dict[str, Any]) -> list[str]:
    text = f"{row['task_name']} {row['task_description']}".lower()
    return [marker for marker in FORBIDDEN_TEXT_MARKERS if marker in text]


def _train_row_from_salvage(
    salvage_row: dict[str, str],
    *,
    spec: RewriteSpec,
    evidence_snippet: str,
) -> dict[str, Any]:
    review_id = salvage_row["review_id"]
    train_row = {
        "schema": TRAIN_ROW_SCHEMA,
        "review_id": review_id,
        "script_id": salvage_row["script_id"],
        "source_platform": "GEE",
        "target_platform": "L3",
        "training_scope": "core_subworkflow",
        "task_name": spec.task_name,
        "task_description": spec.task_description,
        "l3_sequence": _json_list(
            salvage_row["l3_codes_json"],
            field="l3_codes_json",
            review_id=review_id,
        ),
        "operator_sequence": _json_list(
            salvage_row["operator_sequence_json"],
            field="operator_sequence_json",
            review_id=review_id,
        ),
        "source_sha256": salvage_row["source_sha256"],
        "source_path": salvage_row["source_path"],
        "evidence_snippet": evidence_snippet,
        "admission_tier": "gee_core_p2_rewrite",
        "sample_weight": float(salvage_row.get("sample_weight") or 0.5),
        "validation_eligible": False,
        "test_eligible": False,
        "description_policy": "rewritten_chain_faithful",
        "known_omissions": list(spec.known_omissions),
        "review_split": salvage_row.get("split") or "train_only",
    }
    validate_core_train_row(train_row)
    forbidden = _check_no_forbidden_text(train_row)
    if forbidden:
        raise ValueError(f"forbidden rewritten text markers for {review_id}: {forbidden}")
    return train_row


def build_description_rewrites(
    *,
    salvage_csv_path: Path,
    source_snippets_path: Path,
    rewrite_version: str = "v1",
) -> RewriteResult:
    if rewrite_version not in REWRITE_SPECS_BY_VERSION:
        raise ValueError(f"rewrite_version must be one of {sorted(REWRITE_SPECS_BY_VERSION)}")
    rewrite_specs = REWRITE_SPECS_BY_VERSION[rewrite_version]
    salvage_rows = _load_csv(salvage_csv_path)
    snippets = _load_snippets(source_snippets_path)
    rewrite_rows = [row for row in salvage_rows if row.get("salvage_bucket") == REWRITE_BUCKET]
    rewrite_ids = {row["review_id"] for row in rewrite_rows}
    missing_specs = rewrite_ids.difference(rewrite_specs)
    extra_specs = set(rewrite_specs).difference(rewrite_ids)
    if missing_specs or extra_specs:
        raise ValueError(
            f"rewrite specs do not match rewrite bucket: missing={sorted(missing_specs)}, "
            f"extra={sorted(extra_specs)}"
        )

    rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    omissions_counter: Counter[str] = Counter()
    for salvage_row in sorted(rewrite_rows, key=lambda item: item["review_id"]):
        review_id = salvage_row["review_id"]
        evidence_snippet = snippets.get(review_id, "")
        if not evidence_snippet:
            raise ValueError(f"missing evidence snippet for {review_id}")
        spec = rewrite_specs[review_id]
        train_row = _train_row_from_salvage(
            salvage_row,
            spec=spec,
            evidence_snippet=evidence_snippet,
        )
        omissions_counter.update(train_row["known_omissions"])
        rows.append(
            {
                **train_row,
                "original_task_name": salvage_row.get("task_name", ""),
                "original_task_description": salvage_row.get("task_description", ""),
                "salvage_reason": salvage_row.get("salvage_reason", ""),
                "p2_human_review_status": "pending",
            }
        )
        train_rows.append(train_row)

    report = {
        "schema": "gis_recommend.gee_raster_core_description_rewrite.v1",
        "inputs": {
            "salvage_csv": str(Path(salvage_csv_path)),
            "source_snippets": str(Path(source_snippets_path)),
        },
        "rewrite_version": rewrite_version,
        "counts": {
            "rewrite_rows": len(rows),
            "p1_valid_rows": len(train_rows),
            "known_omission_types": len(omissions_counter),
        },
        "rewrite_ids": [row["review_id"] for row in rows],
        "known_omissions": omissions_counter.most_common(),
        "decision": {
            "training_admission": "not_granted_pending_human_text_fidelity_review",
            "validation_eligible": False,
            "test_eligible": False,
            "next_gate": "human text-fidelity review or P3 extractor repair",
        },
        "policy": {
            "llm_used": False,
            "description_policy": "rewritten_chain_faithful",
            "preserve_operator_order": True,
            "allow_operator_add_delete_reorder": False,
            "known_omissions_are_sidecar_only": True,
        },
    }
    return RewriteResult(report=report, rows=rows, train_rows=train_rows)


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
    if not rows:
        raise ValueError("cannot write empty rewrite CSV")
    fieldnames = [
        "review_id",
        "script_id",
        "review_split",
        "task_name",
        "task_description",
        "original_task_name",
        "original_task_description",
        "l3_sequence",
        "operator_sequence",
        "known_omissions",
        "salvage_reason",
        "source_sha256",
        "source_path",
        "admission_tier",
        "sample_weight",
        "validation_eligible",
        "test_eligible",
        "description_policy",
        "p2_human_review_status",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field, "")) for field in fieldnames})


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _render_markdown(report: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# GEE Raster Core P2 Description Rewrites",
        "",
        "Deterministic chain-faithful rewrites for the eight P0 rows marked",
        "`rewrite_description_then_train`. This pass does not call an LLM and does",
        "not grant validation/test or dataset-level training admission.",
        "",
        "## Summary",
        "",
        f"- Rewrite rows: {report['counts']['rewrite_rows']}",
        f"- P1-valid train-only candidate rows: {report['counts']['p1_valid_rows']}",
        f"- Training admission: `{report['decision']['training_admission']}`",
        f"- Validation eligible: `{report['decision']['validation_eligible']}`",
        f"- Test eligible: `{report['decision']['test_eligible']}`",
        "",
        "## Rewritten rows",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"### {row['review_id']}",
                "",
                f"- Task name: {row['task_name']}",
                f"- Task description: {row['task_description']}",
                f"- Known omissions: {', '.join(row['known_omissions'])}",
                "",
            ]
        )
    return "\n".join(lines)


def write_outputs(
    result: RewriteResult,
    output_dir: Path,
    *,
    output_prefix: str = OUTPUT_PREFIX,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"{output_prefix}.csv"
    jsonl_path = output_dir / f"{output_prefix}.jsonl"
    train_rows_path = output_dir / f"{output_prefix}_train_rows.jsonl"
    summary_path = output_dir / f"{output_prefix}_summary.json"
    report_path = output_dir / f"{output_prefix}_report.md"
    hash_ledger_path = output_dir / f"{output_prefix}_hash_ledger.json"

    _write_csv(csv_path, result.rows)
    _atomic_write_text(jsonl_path, _jsonl_text(result.rows))
    _atomic_write_text(train_rows_path, _jsonl_text(result.train_rows))
    _atomic_write_text(summary_path, json.dumps(result.report, ensure_ascii=False, indent=2, sort_keys=True))
    _atomic_write_text(report_path, _render_markdown(result.report, result.rows))

    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            "salvage_csv": {
                "path": result.report["inputs"]["salvage_csv"],
                "sha256": _sha256(Path(result.report["inputs"]["salvage_csv"])),
            },
            "source_snippets": {
                "path": result.report["inputs"]["source_snippets"],
                "sha256": _sha256(Path(result.report["inputs"]["source_snippets"])),
            },
        },
        "artifacts": {
            csv_path.name: {"path": str(csv_path), "sha256": _sha256(csv_path), "bytes": csv_path.stat().st_size},
            jsonl_path.name: {"path": str(jsonl_path), "sha256": _sha256(jsonl_path), "bytes": jsonl_path.stat().st_size},
            train_rows_path.name: {"path": str(train_rows_path), "sha256": _sha256(train_rows_path), "bytes": train_rows_path.stat().st_size},
            summary_path.name: {"path": str(summary_path), "sha256": _sha256(summary_path), "bytes": summary_path.stat().st_size},
            report_path.name: {"path": str(report_path), "sha256": _sha256(report_path), "bytes": report_path.stat().st_size},
        },
    }
    _atomic_write_text(hash_ledger_path, json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True))
    return {
        "csv": csv_path,
        "jsonl": jsonl_path,
        "train_rows_jsonl": train_rows_path,
        "summary": summary_path,
        "report": report_path,
        "hash_ledger": hash_ledger_path,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salvage-csv", type=Path, default=DEFAULT_SALVAGE_CSV)
    parser.add_argument("--source-snippets", type=Path, default=DEFAULT_SOURCE_SNIPPETS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--rewrite-version", choices=sorted(REWRITE_SPECS_BY_VERSION), default="v1")
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    args = parser.parse_args(argv)

    result = build_description_rewrites(
        salvage_csv_path=args.salvage_csv,
        source_snippets_path=args.source_snippets,
        rewrite_version=args.rewrite_version,
    )
    return write_outputs(result, args.output_dir, output_prefix=args.output_prefix)


if __name__ == "__main__":
    main()
