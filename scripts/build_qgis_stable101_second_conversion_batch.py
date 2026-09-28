#!/usr/bin/env python3
"""Select a deterministic second 50-row stable101 source-conversion batch."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
)
POOL_DIR = REPORT_ROOT / "stable101_candidate_pool_v1"
DEFAULT_CHAIN_POOL = POOL_DIR / "stable101_unique_chain_pool_v1.jsonl"
DEFAULT_FIRST_BATCH = POOL_DIR / "stable101_next_review_candidates_50_v1.jsonl"
DEFAULT_QGIS43_MANIFEST = (
    REPORT_ROOT
    / "stable101_source_review_50_v1/qgis43_manifest_v1/qgis43_train_v1.jsonl"
)
DEFAULT_OUTPUT_DIR = REPORT_ROOT / "stable101_second_batch_50_v1"
DEFAULT_CANDIDATES_JSONL = DEFAULT_OUTPUT_DIR / "second50_candidates_v1.jsonl"
DEFAULT_CANDIDATES_CSV = DEFAULT_OUTPUT_DIR / "second50_candidates_v1.csv"
DEFAULT_SUMMARY = DEFAULT_OUTPUT_DIR / "second50_summary_v1.json"
DEFAULT_REPORT = DEFAULT_OUTPUT_DIR / "second50_report_v1.md"
DEFAULT_HASH_LEDGER = DEFAULT_OUTPUT_DIR / "second50_hashes_v1.json"
DEFAULT_ARTIFACT_PATHS = (
    DEFAULT_CANDIDATES_JSONL,
    DEFAULT_CANDIDATES_CSV,
    DEFAULT_SUMMARY,
    DEFAULT_REPORT,
    DEFAULT_HASH_LEDGER,
)
BATCH_ID = "stable101_second_conversion_50_v1"
TRAINING_ADMISSION = "not_granted"
STRATUM_QUOTAS = {
    "multi_stable101_combo": 10,
    "single_polygonize": 8,
    "single_rasterize": 4,
    "single_fixgeometries": 8,
    "single_reprojectlayer": 20,
}
HUMAN_FIELDS = [
    "human_source_retrieval_ready",
    "human_workflow_boundary_decision",
    "human_operator_identity_order_decision",
    "human_dependency_decision",
    "human_task_text_usable",
    "human_description_generation_ready",
    "human_training_candidate_ready",
    "human_notes",
    "reviewer",
    "reviewed_at",
]


@dataclass(frozen=True)
class BatchResult:
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"expected JSON object at {path}:{line_number}")
            rows.append(value)
    return rows


def _sequence_key(values: Any) -> str:
    return " -> ".join(str(value).strip().lower() for value in values or [])


def _selection_stratum(row: dict[str, Any]) -> str:
    operators = [str(value) for value in row.get("proposal_ops_present") or []]
    if len(operators) > 1:
        return "multi_stable101_combo"
    if operators == ["gdal:polygonize"]:
        return "single_polygonize"
    if operators == ["gdal:rasterize"]:
        return "single_rasterize"
    if operators == ["native:fixgeometries"]:
        return "single_fixgeometries"
    if operators == ["native:reprojectlayer"]:
        return "single_reprojectlayer"
    raise ValueError(f"unexpected stable101 proposal combination: {operators}")


def _quality_tier(row: dict[str, Any]) -> str:
    usable = row.get("task_text_quality") == "usable_seed_text"
    bounded = 2 <= int(row.get("chain_length", 0)) <= 8
    if usable and bounded:
        return "usable_seed_len_2_8"
    if usable:
        return "usable_seed_other_length"
    if bounded:
        return "weak_seed_len_2_8"
    return "weak_seed_other_length"


def _quality_rank(row: dict[str, Any]) -> tuple[int, int, float, str]:
    tier_rank = {
        "usable_seed_len_2_8": 0,
        "usable_seed_other_length": 1,
        "weak_seed_len_2_8": 2,
        "weak_seed_other_length": 3,
    }[row["selection_quality_tier"]]
    l3_seen_rank = 1 if row["qgis43_l3_sequence_seen"] else 0
    return (
        tier_rank,
        l3_seen_rank,
        -float(row.get("review_priority_score", 0.0)),
        str(row["chain_key"]),
    )


def _select_stratum(
    candidates: list[dict[str, Any]],
    *,
    stratum: str,
    quota: int,
) -> list[dict[str, Any]]:
    rows = sorted(
        (row for row in candidates if row["selection_stratum"] == stratum),
        key=_quality_rank,
    )
    selected: list[dict[str, Any]] = []
    if stratum == "single_polygonize":
        selected.extend(row for row in rows if row.get("modality") == "pure_raster")
    selected_ids = {row["chain_key"] for row in selected}
    for row in rows:
        if len(selected) >= quota:
            break
        if row["chain_key"] not in selected_ids:
            selected.append(row)
            selected_ids.add(row["chain_key"])
    if len(selected) != quota:
        raise ValueError(f"insufficient candidates for {stratum}: {len(selected)}/{quota}")
    return selected


def build_second_conversion_batch(
    *,
    chain_pool_path: Path,
    first_batch_path: Path,
    qgis43_manifest_path: Path,
) -> BatchResult:
    chain_pool = _load_jsonl(chain_pool_path)
    first_batch = _load_jsonl(first_batch_path)
    qgis43 = _load_jsonl(qgis43_manifest_path)
    if len(chain_pool) != 179 or len(first_batch) != 50 or len(qgis43) != 43:
        raise ValueError(
            f"unexpected input sizes: pool={len(chain_pool)}, first={len(first_batch)}, qgis43={len(qgis43)}"
        )
    pool_keys = {str(row["chain_key"]) for row in chain_pool}
    first_keys = {str(row["chain_key"]) for row in first_batch}
    if len(pool_keys) != len(chain_pool) or len(first_keys) != len(first_batch):
        raise ValueError("chain pool and first batch must contain unique chain_key values")
    if not first_keys <= pool_keys:
        raise ValueError("first batch contains chains outside the stable101 pool")

    qgis43_operator_keys = {
        _sequence_key(row.get("operator_sequence")) for row in qgis43
    }
    qgis43_l3_keys = {_sequence_key(row.get("l3_code_sequence")) for row in qgis43}
    remaining = [row for row in chain_pool if row["chain_key"] not in first_keys]
    overlap = [row for row in remaining if row["chain_key"] in qgis43_operator_keys]
    eligible = [row for row in remaining if row["chain_key"] not in qgis43_operator_keys]

    enriched: list[dict[str, Any]] = []
    for source_row in eligible:
        row = dict(source_row)
        row["selection_stratum"] = _selection_stratum(row)
        row["selection_quality_tier"] = _quality_tier(row)
        row["qgis43_operator_sequence_seen"] = row["chain_key"] in qgis43_operator_keys
        row["qgis43_l3_sequence_seen"] = (
            _sequence_key(row.get("proposed_l3_sequence")) in qgis43_l3_keys
        )
        enriched.append(row)

    selected: list[dict[str, Any]] = []
    for stratum, quota in STRATUM_QUOTAS.items():
        selected.extend(
            _select_stratum(enriched, stratum=stratum, quota=quota)
        )
    selected = sorted(
        selected,
        key=lambda row: (
            list(STRATUM_QUOTAS).index(row["selection_stratum"]),
            _quality_rank(row),
        ),
    )
    if len(selected) != 50 or len({row["chain_key"] for row in selected}) != 50:
        raise ValueError("second batch must contain 50 unique chains")

    rows: list[dict[str, Any]] = []
    for review_index, source_row in enumerate(selected, start=1):
        row = dict(source_row)
        row["review_index"] = review_index
        row["batch_id"] = BATCH_ID
        row["selection_rationale"] = [
            "not_in_first_review_batch",
            "not_exactly_covered_by_qgis43",
            "quality_then_coverage_priority_within_stratum",
        ]
        if row.get("modality") == "pure_raster":
            row["selection_rationale"].append("retain_all_remaining_pure_raster")
        row["source_retrieval_status"] = "pending_provenance_replay"
        row["proposal_status"] = "proposal_only_pending_source_join"
        row["training_admission"] = TRAINING_ADMISSION
        row["validation_eligible"] = False
        row["test_eligible"] = False
        for field in HUMAN_FIELDS:
            row[field] = ""
        rows.append(row)

    summary = {
        "schema": "gis_recommend.qgis_stable101_second_conversion_batch_summary.v1",
        "counts": {
            "unique_chain_pool": len(chain_pool),
            "first_batch_chains": len(first_batch),
            "remaining_chains": len(remaining),
            "qgis43_overlap_excluded": len(overlap),
            "eligible_chains": len(eligible),
            "selected_rows": len(rows),
            "usable_seed_rows": sum(
                1 for row in rows if row["task_text_quality"] == "usable_seed_text"
            ),
            "bounded_len_2_8_rows": sum(
                1 for row in rows if 2 <= int(row["chain_length"]) <= 8
            ),
            "pure_raster_rows": sum(
                1 for row in rows if row["modality"] == "pure_raster"
            ),
            "qgis43_novel_l3_sequence_rows": sum(
                1 for row in rows if not row["qgis43_l3_sequence_seen"]
            ),
        },
        "selection_stratum_counts": dict(
            sorted(Counter(row["selection_stratum"] for row in rows).items())
        ),
        "selection_quality_tier_counts": dict(
            sorted(Counter(row["selection_quality_tier"] for row in rows).items())
        ),
        "modality_counts": dict(sorted(Counter(row["modality"] for row in rows).items())),
        "task_text_quality_counts": dict(
            sorted(Counter(row["task_text_quality"] for row in rows).items())
        ),
        "decision": {
            "batch_id": BATCH_ID,
            "proposal_status": "proposal_only_pending_source_join",
            "source_retrieval_status": "pending_provenance_replay",
            "training_admission": TRAINING_ADMISSION,
            "validation_eligible": False,
            "test_eligible": False,
            "llm_called": False,
            "next_gate": "replay provenance and build a source-backed review pack",
        },
    }
    return BatchResult(rows=rows, summary=summary)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _jsonl_text(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def _csv_text(rows: list[dict[str, Any]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: (
                    json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                    if isinstance(value, (list, dict))
                    else value
                )
                for key, value in row.items()
            }
        )
    return output.getvalue()


def _report_text(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    return f"""# stable101 second source-conversion batch

Status: `proposal_only_pending_source_join`

- stable101 unique chains: {counts['unique_chain_pool']}
- first batch chains: {counts['first_batch_chains']}
- remaining chains: {counts['remaining_chains']}
- exact QGIS43 overlap excluded: {counts['qgis43_overlap_excluded']}
- selected: {counts['selected_rows']}
- usable seed rows: {counts['usable_seed_rows']}
- chain length 2-8: {counts['bounded_len_2_8_rows']}
- pure raster rows: {counts['pure_raster_rows']}
- QGIS43-novel L3 sequence rows: {counts['qgis43_novel_l3_sequence_rows']}

Strata: `{json.dumps(summary['selection_stratum_counts'], sort_keys=True)}`

This package is selection evidence only. Source retrieval, dependency recovery,
human review, training admission, validation/test admission, and model training
are not granted.
"""


def write_outputs(
    result: BatchResult,
    output_dir: Path,
    input_paths: dict[str, Path],
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    candidates_jsonl = output_dir / DEFAULT_CANDIDATES_JSONL.name
    candidates_csv = output_dir / DEFAULT_CANDIDATES_CSV.name
    summary = output_dir / DEFAULT_SUMMARY.name
    report = output_dir / DEFAULT_REPORT.name
    hash_ledger = output_dir / DEFAULT_HASH_LEDGER.name
    _atomic_write(candidates_jsonl, _jsonl_text(result.rows))
    _atomic_write(candidates_csv, _csv_text(result.rows))
    _atomic_write(summary, json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _atomic_write(report, _report_text(result.summary))
    artifacts = (candidates_jsonl, candidates_csv, summary, report)
    hashes = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            name: {"path": str(path), "sha256": _sha256(path)}
            for name, path in sorted(input_paths.items())
        },
        "artifacts": {
            path.name: {
                "path": str(path),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in artifacts
        },
    }
    _atomic_write(hash_ledger, json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {
        "candidates_jsonl": candidates_jsonl,
        "candidates_csv": candidates_csv,
        "summary": summary,
        "report": report,
        "hash_ledger": hash_ledger,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chain-pool", type=Path, default=DEFAULT_CHAIN_POOL)
    parser.add_argument("--first-batch", type=Path, default=DEFAULT_FIRST_BATCH)
    parser.add_argument("--qgis43-manifest", type=Path, default=DEFAULT_QGIS43_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    result = build_second_conversion_batch(
        chain_pool_path=args.chain_pool,
        first_batch_path=args.first_batch,
        qgis43_manifest_path=args.qgis43_manifest,
    )
    return write_outputs(
        result,
        args.output_dir,
        {
            "chain_pool": args.chain_pool,
            "first_batch": args.first_batch,
            "qgis43_manifest": args.qgis43_manifest,
        },
    )


if __name__ == "__main__":
    main()
