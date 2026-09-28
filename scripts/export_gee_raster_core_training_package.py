#!/usr/bin/env python3
"""Export reviewed GEE raster-core rows as model-ready train-only packages.

The reviewed 35-row manifest stores L3 codes. This exporter converts those
codes into the integer `l3_sequence` format expected by the existing V4 dataset
path, while preserving source evidence and train-only restrictions.

Two packages are emitted:

* full-35: all reviewed rows, including long chains.
* v4-100: only rows whose START + content + END length fits the current V4
  default max sequence length of 100, so the loader will not truncate labels.

No validation/test split, production merge, LLM call, or training run is
authorized by this exporter.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.data.gee_raster_core_schema import validate_core_train_row  # noqa: E402


DEFAULT_REPORT_DIR = ROOT / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
DEFAULT_REVIEWED_MANIFEST = DEFAULT_REPORT_DIR / "gee_raster_core_reviewed_train_only_35_v1.jsonl"
DEFAULT_ID_MAPPINGS = ROOT / "outputs_v2/id_mappings_v2.json"
DEFAULT_OUTPUT_DIR = DEFAULT_REPORT_DIR / "gee_raster_core_training_package_v1"

PACKAGE_ID = "gee_raster_core_training_package_v1"
TRAINING_ADMISSION = "granted_train_only_gee_raster_core_v1"
TRAIN_ONLY_SPLIT = "train_only_gee_raster_core_v1"
TASK_TYPE = "GEE Raster Core"
V4_DEFAULT_MAX_SEQ_LENGTH = 100
START_TOKEN = -3
END_TOKEN = -4

FULL_WORKFLOWS_NAME = "labeled_workflows_l3_v4_gee_raster_core_train35_full_v1.json"
V4_100_WORKFLOWS_NAME = "labeled_workflows_l3_v4_gee_raster_core_train33_v4_100_v1.json"
FULL_SPLITS_NAME = "dataset_splits_gee_raster_core_train35_full_v1.json"
V4_100_SPLITS_NAME = "dataset_splits_gee_raster_core_train33_v4_100_v1.json"
TASK_VOCAB_NAME = "task_type_vocabulary_gee_raster_core_train_v1.json"
LONG_CHAIN_JSONL_NAME = "gee_raster_core_train35_long_chain_sidecar_v1.jsonl"
LONG_CHAIN_CSV_NAME = "gee_raster_core_train35_long_chain_sidecar_v1.csv"
SUMMARY_NAME = "gee_raster_core_training_package_v1_summary.json"
REPORT_NAME = "gee_raster_core_training_package_v1_report.md"
HASH_LEDGER_NAME = "gee_raster_core_training_package_v1_hash_ledger.json"

LONG_CHAIN_FIELDS = (
    "sample_id",
    "review_id",
    "script_id",
    "content_length",
    "model_sequence_length",
    "required_max_seq_length",
    "fits_v4_max_seq_length_100",
    "source_sha256",
    "source_path",
    "task_name",
    "task_description",
)


@dataclass(frozen=True)
class TrainingPackageResult:
    full_rows: list[dict[str, Any]]
    v4_100_rows: list[dict[str, Any]]
    long_chain_rows: list[dict[str, Any]]
    full_splits: dict[str, list[int]]
    v4_100_splits: dict[str, list[int]]
    task_type_vocab: dict[str, Any]
    summary: dict[str, Any]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number} must contain a JSON object")
            rows.append(row)
    if not rows:
        raise ValueError(f"{path} contains no rows")
    return rows


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _review_number(review_id: str) -> str:
    suffix = str(review_id).rsplit("_", 1)[-1]
    return suffix if suffix.isdigit() else hashlib.sha1(review_id.encode()).hexdigest()[:8]


def _task_type_vocab() -> dict[str, Any]:
    return {
        "task_type_to_id": {"Unknown": 0, TASK_TYPE: 1},
        "id_to_task_type": {"0": "Unknown", "1": TASK_TYPE},
        "num_types": 2,
    }


def _splits(row_count: int) -> dict[str, list[int]]:
    return {
        "train_indices": list(range(row_count)),
        "val_indices": [],
        "test_indices": [],
    }


def _validate_reviewed_manifest_row(row: dict[str, Any]) -> None:
    validate_core_train_row(row)
    if row.get("manifest_id") != "gee_raster_core_reviewed_train_only_35_v1":
        raise ValueError(f"unexpected manifest_id for {row.get('review_id')}")
    if row.get("manifest_split") != "train_only":
        raise ValueError(f"unexpected manifest split for {row.get('review_id')}")
    if row.get("validation_eligible") is not False or row.get("test_eligible") is not False:
        raise ValueError(f"validation/test eligible row in reviewed manifest: {row.get('review_id')}")
    if float(row.get("sample_weight") or 0) > 0.5:
        raise ValueError(f"GEE reviewed row exceeds sample_weight 0.5: {row.get('review_id')}")


def _convert_row(row: dict[str, Any], *, l3_to_id: dict[str, int]) -> dict[str, Any]:
    _validate_reviewed_manifest_row(row)
    review_id = str(row["review_id"])
    l3_codes = list(row["l3_sequence"])
    operators = list(row["operator_sequence"])
    if len(l3_codes) != len(operators):
        raise ValueError(f"operator/L3 length mismatch: {review_id}")
    missing = [code for code in l3_codes if code not in l3_to_id]
    if missing:
        raise ValueError(f"unmapped L3 code(s) for {review_id}: {sorted(set(missing))}")
    token_ids = [int(l3_to_id[code]) for code in l3_codes]
    model_sequence = [START_TOKEN, *token_ids, END_TOKEN]
    sequence_fit = {
        "content_length": len(token_ids),
        "model_sequence_length": len(model_sequence),
        "v4_default_max_seq_length": V4_DEFAULT_MAX_SEQ_LENGTH,
        "fits_v4_max_seq_length_100": len(model_sequence) <= V4_DEFAULT_MAX_SEQ_LENGTH,
        "required_max_seq_length": len(model_sequence),
    }
    sample_id = f"gee_raster_core_v1_{_review_number(review_id)}"
    return {
        "schema_version": "gee_raster_core_training_sample_v1",
        "sample_id": sample_id,
        "source": PACKAGE_ID,
        "source_manifest_id": row["manifest_id"],
        "source_manifest_training_admission": row.get("manifest_training_admission", ""),
        "source_package": row.get("source_package", ""),
        "source_package_row_index": row.get("source_package_row_index"),
        "review_id": review_id,
        "script_id": row.get("script_id", ""),
        "source_platform": "GEE",
        "target_platform": "L3",
        "training_scope": "core_subworkflow",
        "task_name": row.get("task_name", ""),
        "task_description": row.get("task_description", ""),
        "task_metadata": {
            "task_type": TASK_TYPE,
            "task_name": row.get("task_name", ""),
            "task_description": row.get("task_description", ""),
            "source_platform": "GEE",
            "target_platform": "L3",
            "training_scope": "core_subworkflow",
        },
        "operator_sequence": operators,
        "l3_code_sequence": l3_codes,
        "l3_token_ids": token_ids,
        "l3_sequence": model_sequence,
        "source_sha256": row.get("source_sha256", ""),
        "source_path": row.get("source_path", ""),
        "evidence_snippet": row.get("evidence_snippet", ""),
        "known_omissions": list(row.get("known_omissions") or []),
        "admission_tier": row.get("admission_tier", ""),
        "training_admission": TRAINING_ADMISSION,
        "split": TRAIN_ONLY_SPLIT,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "sample_weight": float(row.get("sample_weight") or 0.5),
        "_training_quality": {
            "tier": TRAINING_ADMISSION,
            "source_tier": row.get("admission_tier", ""),
            "sample_weight": float(row.get("sample_weight") or 0.5),
            "validation_eligible": False,
            "test_eligible": False,
            "description_policy": row.get("description_policy", ""),
            "authority": "reviewed_gee_raster_core_manifest_v1",
        },
        "sequence_fit": sequence_fit,
    }


def _long_chain_sidecar_row(row: dict[str, Any]) -> dict[str, Any]:
    fit = row["sequence_fit"]
    return {
        "sample_id": row["sample_id"],
        "review_id": row["review_id"],
        "script_id": row["script_id"],
        "sequence_fit": fit,
        "content_length": fit["content_length"],
        "model_sequence_length": fit["model_sequence_length"],
        "required_max_seq_length": fit["required_max_seq_length"],
        "fits_v4_max_seq_length_100": fit["fits_v4_max_seq_length_100"],
        "source_sha256": row["source_sha256"],
        "source_path": row["source_path"],
        "task_name": row["task_name"],
        "task_description": row["task_description"],
        "training_admission": "granted_train_only_requires_long_sequence_loader",
        "validation_eligible": False,
        "test_eligible": False,
        "next_action": "train with max_seq_length >= required_max_seq_length or split with reviewed boundaries",
    }


def build_training_package(
    *,
    reviewed_manifest_jsonl_path: Path,
    id_mappings_path: Path,
) -> TrainingPackageResult:
    manifest_rows = _load_jsonl(reviewed_manifest_jsonl_path)
    mappings = _load_json(id_mappings_path)
    l3_to_id = mappings.get("l3") or {}
    if len(l3_to_id) != 94:
        raise ValueError(f"expected 94-L3 id mapping, got {len(l3_to_id)}")

    full_rows = [
        _convert_row(row, l3_to_id=l3_to_id)
        for row in sorted(manifest_rows, key=lambda item: int(item["manifest_row_index"]))
    ]
    if len(full_rows) != 35:
        raise ValueError(f"expected 35 reviewed GEE rows, got {len(full_rows)}")
    if len({row["sample_id"] for row in full_rows}) != len(full_rows):
        raise ValueError("sample_id values must be unique")
    if len({row["source_sha256"] for row in full_rows}) != len(full_rows):
        raise ValueError("source_sha256 values must be unique")

    v4_100_rows = [
        row for row in full_rows if row["sequence_fit"]["fits_v4_max_seq_length_100"]
    ]
    long_chain_rows = [
        _long_chain_sidecar_row(row)
        for row in full_rows
        if not row["sequence_fit"]["fits_v4_max_seq_length_100"]
    ]

    sequence_lengths = [len(row["l3_sequence"]) for row in full_rows]
    token_ids = [token for row in full_rows for token in row["l3_token_ids"]]
    source_package_counts = Counter(row["source_package"] for row in full_rows)
    source_tier_counts = Counter(row["admission_tier"] for row in full_rows)
    summary = {
        "schema": "gis_recommend.gee_raster_core_training_package_summary.v1",
        "package_id": PACKAGE_ID,
        "inputs": {
            "reviewed_manifest": str(Path(reviewed_manifest_jsonl_path)),
            "id_mappings": str(Path(id_mappings_path)),
        },
        "counts": {
            "full_rows": len(full_rows),
            "v4_100_no_truncation_rows": len(v4_100_rows),
            "long_chain_sidecar_rows": len(long_chain_rows),
            "unique_review_ids": len({row["review_id"] for row in full_rows}),
            "unique_source_sha256": len({row["source_sha256"] for row in full_rows}),
            "unique_operator_sequences": len({tuple(row["operator_sequence"]) for row in full_rows}),
            "unique_l3_sequences": len({tuple(row["l3_code_sequence"]) for row in full_rows}),
            "unique_l3_token_ids": len(set(token_ids)),
            "min_model_sequence_length": min(sequence_lengths),
            "max_model_sequence_length": max(sequence_lengths),
            "source_package_counts": dict(sorted(source_package_counts.items())),
            "source_tier_counts": dict(sorted(source_tier_counts.items())),
        },
        "long_chain_review_ids": [row["review_id"] for row in long_chain_rows],
        "decision": {
            "training_admission": TRAINING_ADMISSION,
            "full_package_split": TRAIN_ONLY_SPLIT,
            "v4_100_package_split": TRAIN_ONLY_SPLIT,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge_granted": False,
            "training_run_started": False,
            "llm_used": False,
            "default_v4_no_truncation_package": "v4_100",
            "long_chain_policy": "sidecar unless loader max_seq_length is raised or chain is reviewed/split",
        },
        "policy": {
            "source_platform": "GEE",
            "target_platform": "L3",
            "training_scope": "core_subworkflow",
            "sample_weight": 0.5,
            "start_token": START_TOKEN,
            "end_token": END_TOKEN,
            "id_mapping_vocab_size": 94,
        },
    }
    return TrainingPackageResult(
        full_rows=full_rows,
        v4_100_rows=v4_100_rows,
        long_chain_rows=long_chain_rows,
        full_splits=_splits(len(full_rows)),
        v4_100_splits=_splits(len(v4_100_rows)),
        task_type_vocab=_task_type_vocab(),
        summary=summary,
    )


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _workflow_payload(rows: list[dict[str, Any]], *, dataset_id: str, summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "gis_recommend.labeled_workflows_l3_v4.gee_raster_core.v1",
        "dataset_id": dataset_id,
        "labeled_workflows": rows,
        "metadata": {
            "package_id": PACKAGE_ID,
            "training_admission": TRAINING_ADMISSION,
            "split": TRAIN_ONLY_SPLIT,
            "source_platform": "GEE",
            "target_platform": "L3",
            "training_scope": "core_subworkflow",
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "counts": summary["counts"],
        },
    }


def _jsonl_text(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _csv_text(rows: list[dict[str, Any]], *, fieldnames: tuple[str, ...]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _csv_value(row.get(field, "")) for field in fieldnames})
    return output.getvalue()


def _render_report(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    decision = summary["decision"]
    lines = [
        "# GEE Raster Core Training Package v1",
        "",
        "This package converts the reviewed 35-row GEE raster-core manifest into",
        "the integer L3-token format expected by the existing V4 data path.",
        "",
        "## Result",
        "",
        f"- Full train-only rows: {counts['full_rows']}",
        f"- V4-100 no-truncation rows: {counts['v4_100_no_truncation_rows']}",
        f"- Long-chain sidecar rows: {counts['long_chain_sidecar_rows']}",
        f"- Unique source SHA256 values: {counts['unique_source_sha256']}",
        f"- Unique operator sequences: {counts['unique_operator_sequences']}",
        f"- Unique L3 sequences: {counts['unique_l3_sequences']}",
        f"- Model sequence length: {counts['min_model_sequence_length']}..{counts['max_model_sequence_length']}",
        f"- Training admission: `{decision['training_admission']}`",
        f"- Validation eligible: `{decision['validation_eligible']}`",
        f"- Test eligible: `{decision['test_eligible']}`",
        f"- Production merge granted: `{decision['production_merge_granted']}`",
        "",
        "## Long-chain policy",
        "",
        "Rows longer than the current V4 default max sequence length of 100 are",
        "not included in the V4-100 package, because silent truncation would damage",
        "the gold chain. They remain available in the full package and sidecar.",
        "",
    ]
    for review_id in summary["long_chain_review_ids"]:
        lines.append(f"- `{review_id}`")
    lines.append("")
    return "\n".join(lines)


def write_outputs(result: TrainingPackageResult, output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "full_workflows": output_dir / FULL_WORKFLOWS_NAME,
        "v4_100_workflows": output_dir / V4_100_WORKFLOWS_NAME,
        "full_splits": output_dir / FULL_SPLITS_NAME,
        "v4_100_splits": output_dir / V4_100_SPLITS_NAME,
        "task_type_vocab": output_dir / TASK_VOCAB_NAME,
        "long_chain_jsonl": output_dir / LONG_CHAIN_JSONL_NAME,
        "long_chain_csv": output_dir / LONG_CHAIN_CSV_NAME,
        "summary": output_dir / SUMMARY_NAME,
        "report": output_dir / REPORT_NAME,
        "hash_ledger": output_dir / HASH_LEDGER_NAME,
    }
    _atomic_write(
        paths["full_workflows"],
        json.dumps(
            _workflow_payload(result.full_rows, dataset_id="gee_raster_core_train35_full_v1", summary=result.summary),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    _atomic_write(
        paths["v4_100_workflows"],
        json.dumps(
            _workflow_payload(result.v4_100_rows, dataset_id="gee_raster_core_train33_v4_100_v1", summary=result.summary),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    _atomic_write(paths["full_splits"], json.dumps(result.full_splits, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _atomic_write(paths["v4_100_splits"], json.dumps(result.v4_100_splits, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _atomic_write(paths["task_type_vocab"], json.dumps(result.task_type_vocab, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _atomic_write(paths["long_chain_jsonl"], _jsonl_text(result.long_chain_rows))
    _atomic_write(paths["long_chain_csv"], _csv_text(result.long_chain_rows, fieldnames=LONG_CHAIN_FIELDS))
    _atomic_write(paths["summary"], json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _atomic_write(paths["report"], _render_report(result.summary))

    source_inputs = {
        name: {
            "path": path,
            "sha256": _sha256(Path(path)),
        }
        for name, path in sorted(result.summary["inputs"].items())
    }
    artifacts = {
        path.name: {
            "path": str(path),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
        }
        for key, path in paths.items()
        if key != "hash_ledger"
    }
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": source_inputs,
        "artifacts": artifacts,
    }
    _atomic_write(paths["hash_ledger"], json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return paths


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewed-manifest", type=Path, default=DEFAULT_REVIEWED_MANIFEST)
    parser.add_argument("--id-mappings", type=Path, default=DEFAULT_ID_MAPPINGS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    result = build_training_package(
        reviewed_manifest_jsonl_path=args.reviewed_manifest,
        id_mappings_path=args.id_mappings,
    )
    return write_outputs(result, args.output_dir)


if __name__ == "__main__":
    main()
