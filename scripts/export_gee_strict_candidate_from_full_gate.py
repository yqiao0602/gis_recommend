#!/usr/bin/env python3
"""Export the provisionally clean GEE full-gate rows as a candidate package.

The export is deliberately non-admitting: it creates a standalone train-only
candidate package without modifying the 11,397-row source package, opening
validation/test eligibility, or starting training.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1"
)
DEFAULT_TRAIN_JSON = PACKAGE_DIR / "train11397_v4_100.json"
DEFAULT_FULL_GATE_JSONL = (
    PACKAGE_DIR / "audit_full_policy_gate_v1" / "full_policy_gate_v1.jsonl"
)
DEFAULT_TASK_TYPE_VOCAB = PACKAGE_DIR / "task_type_vocab.json"
DEFAULT_OUTPUT_DIR = PACKAGE_DIR / "strict_candidate_v1"
OUTPUT_PREFIX = "gee_strict_candidate_v1"

CANDIDATE_DISPOSITION = "provisionally_keep_current_silver_row"
STRICT_ADMISSION = "not_granted_gee_strict_candidate_v1"
STRICT_SPLIT = "train_only_gee_strict_candidate_v1"
SUMMARY_ADMISSION = "not_granted_strict_candidate_export"
QUALITY_AUTHORITY = "gee_full_policy_gate_v1_provisionally_clean"


@dataclass(frozen=True)
class StrictCandidatePackageResult:
    rows: list[dict[str, Any]]
    sidecar_rows: list[dict[str, Any]]
    task_type_vocab: dict[str, Any]
    splits: dict[str, Any]
    summary: dict[str, Any]


def _filesystem_path(path: Path) -> str:
    text = str(path)
    if os.name != "nt" or text.startswith("\\\\?\\"):
        return text
    absolute = path if path.is_absolute() else Path.cwd() / path
    text = str(absolute)
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text.lstrip("\\")
    return "\\\\?\\" + text


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(_filesystem_path(Path(path)), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    with open(_filesystem_path(Path(path)), encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(_filesystem_path(Path(path)), encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number} must contain a JSON object")
            rows.append(row)
    return rows


def _unique_index(rows: list[dict[str, Any]], *, label: str) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row_number, row in enumerate(rows, start=1):
        sample_id = str(row.get("sample_id") or "").strip()
        if not sample_id:
            raise ValueError(f"{label} row {row_number} is missing sample_id")
        if sample_id in index:
            raise ValueError(f"duplicate sample_id in {label}: {sample_id}")
        index[sample_id] = row
    return index


def _strict_row(source_row: dict[str, Any], gate_row: dict[str, Any]) -> dict[str, Any]:
    row = deepcopy(source_row)
    row["training_admission"] = STRICT_ADMISSION
    row["split"] = STRICT_SPLIT
    row["validation_eligible"] = False
    row["test_eligible"] = False
    row["production_merge"] = "not_granted"
    row["review_required_before_promotion"] = True

    quality = deepcopy(row.get("_training_quality") or {})
    quality.update(
        {
            "tier": STRICT_ADMISSION,
            "authority": QUALITY_AUTHORITY,
            "validation_eligible": False,
            "test_eligible": False,
            "exclude_from_validation_test": True,
            "manual_review_role": "full_policy_gate_surface_candidate_only",
        }
    )
    row["_training_quality"] = quality
    row["strict_candidate_gate"] = {
        "schema": gate_row.get("schema"),
        "input_row_index": gate_row.get("input_row_index"),
        "risk_score": gate_row.get("risk_score"),
        "risk_level": gate_row.get("risk_level"),
        "risk_flags": list(gate_row.get("risk_flags") or []),
        "policy_hits": list(gate_row.get("policy_hits") or []),
        "strict_regeneration_disposition": gate_row.get(
            "strict_regeneration_disposition"
        ),
        "audit_notes": list(gate_row.get("audit_notes") or []),
        "full_gate_training_admission": gate_row.get("training_admission"),
    }
    return row


def _sidecar_row(
    source_row: dict[str, Any], gate_row: dict[str, Any], *, candidate_index: int
) -> dict[str, Any]:
    return {
        "schema": "gis_recommend.gee_strict_candidate_sidecar.v1",
        "candidate_index": candidate_index,
        "sample_id": source_row["sample_id"],
        "proposal_id": source_row.get("proposal_id"),
        "script_id": source_row.get("script_id"),
        "source_sha256": source_row.get("source_sha256"),
        "source_path": source_row.get("source_path"),
        "task_name": source_row.get("task_name"),
        "task_type": source_row.get("task_type"),
        "original_training_admission": source_row.get("training_admission"),
        "candidate_training_admission": STRICT_ADMISSION,
        "candidate_split": STRICT_SPLIT,
        "strict_regeneration_disposition": gate_row.get(
            "strict_regeneration_disposition"
        ),
        "risk_flags": list(gate_row.get("risk_flags") or []),
        "policy_hits": list(gate_row.get("policy_hits") or []),
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def build_strict_candidate_package(
    *,
    train_json: Path = DEFAULT_TRAIN_JSON,
    full_gate_jsonl: Path = DEFAULT_FULL_GATE_JSONL,
    task_type_vocab: Path = DEFAULT_TASK_TYPE_VOCAB,
) -> StrictCandidatePackageResult:
    train_payload = _load_json(train_json)
    train_rows = train_payload.get("labeled_workflows")
    if not isinstance(train_rows, list) or not train_rows:
        raise ValueError(f"{train_json} must contain non-empty labeled_workflows")
    if not all(isinstance(row, dict) for row in train_rows):
        raise ValueError("labeled_workflows must contain JSON objects")

    gate_rows = _load_jsonl(full_gate_jsonl)
    train_by_id = _unique_index(train_rows, label="source train package")
    gate_by_id = _unique_index(gate_rows, label="full policy gate")
    if set(train_by_id) != set(gate_by_id):
        missing_gate = sorted(set(train_by_id) - set(gate_by_id))[:5]
        missing_train = sorted(set(gate_by_id) - set(train_by_id))[:5]
        raise ValueError(
            "full policy gate and source train package sample IDs differ: "
            f"missing_gate={missing_gate}, missing_train={missing_train}"
        )

    selected_pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for source_row in train_rows:
        gate_row = gate_by_id[source_row["sample_id"]]
        if gate_row.get("strict_regeneration_disposition") != CANDIDATE_DISPOSITION:
            continue
        if gate_row.get("policy_hits") or gate_row.get("risk_flags"):
            raise ValueError(
                "provisionally clean gate row contains policy/risk flags: "
                f"{source_row['sample_id']}"
            )
        if source_row.get("source_sha256") != gate_row.get("source_sha256"):
            raise ValueError(f"source hash mismatch: {source_row['sample_id']}")
        selected_pairs.append((source_row, gate_row))

    rows = [_strict_row(source, gate) for source, gate in selected_pairs]
    sidecar_rows = [
        _sidecar_row(source, gate, candidate_index=index)
        for index, (source, gate) in enumerate(selected_pairs)
    ]
    source_hashes = [str(row.get("source_sha256") or "") for row in rows]
    if not all(source_hashes) or len(set(source_hashes)) != len(source_hashes):
        raise ValueError("strict candidate source_sha256 values must be present and unique")

    vocab_payload = _load_json(task_type_vocab)
    required_vocab_keys = {"task_type_to_id", "id_to_task_type", "num_types"}
    if not required_vocab_keys.issubset(vocab_payload):
        raise ValueError(f"{task_type_vocab} is not a task type vocabulary")

    splits = {
        "schema": "gis_recommend.gee_strict_candidate_splits.v1",
        "split": STRICT_SPLIT,
        "train_indices": list(range(len(rows))),
        "validation_indices": [],
        "test_indices": [],
        "validation_eligible": False,
        "test_eligible": False,
    }
    summary = {
        "schema": "gis_recommend.gee_strict_candidate_export_summary.v1",
        "source_package": {
            "train_json": str(train_json),
            "train_json_sha256": _sha256(train_json),
            "full_gate_jsonl": str(full_gate_jsonl),
            "full_gate_jsonl_sha256": _sha256(full_gate_jsonl),
            "task_type_vocab": str(task_type_vocab),
            "task_type_vocab_sha256": _sha256(task_type_vocab),
        },
        "counts": {
            "candidate_rows": len(rows),
            "source_train_rows": len(train_rows),
            "full_gate_rows": len(gate_rows),
            "rejected_by_full_gate_rows": len(gate_rows) - len(rows),
            "training_rows_emitted": 0,
        },
        "selection": {
            "required_disposition": CANDIDATE_DISPOSITION,
            "required_policy_hits": [],
            "required_risk_flags": [],
            "source_order_preserved": True,
            "joined_by": "sample_id",
        },
        "decision": {
            "training_admission": SUMMARY_ADMISSION,
            "mutated_train11397_package": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "training_run_started": False,
            "llm_used": False,
        },
    }
    return StrictCandidatePackageResult(
        rows=rows,
        sidecar_rows=sidecar_rows,
        task_type_vocab=vocab_payload,
        splits=splits,
        summary=summary,
    )


def _atomic_write(path: Path, text: str) -> None:
    os.makedirs(_filesystem_path(path.parent), exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="",
        dir=_filesystem_path(path.parent),
        delete=False,
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    os.replace(_filesystem_path(temporary), _filesystem_path(path))


def _json_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _jsonl_text(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def resolve_output_paths(
    output_dir: Path, *, output_prefix: str = OUTPUT_PREFIX, candidate_rows: int
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    return {
        "workflows": output_dir / f"{output_prefix}_train{candidate_rows}.json",
        "sidecar": output_dir / f"{output_prefix}_sidecar.jsonl",
        "task_type_vocab": output_dir / f"{output_prefix}_task_type_vocab.json",
        "splits": output_dir / f"{output_prefix}_splits.json",
        "summary": output_dir / f"{output_prefix}_summary.json",
        "report": output_dir / f"{output_prefix}_report.md",
        "hash_ledger": output_dir / f"{output_prefix}_hashes.json",
    }


def _render_report(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    return "\n".join(
        [
            "# GEE Strict Candidate Export v1",
            "",
            f"- Source rows: {counts['source_train_rows']:,}",
            f"- Strict candidate rows: {counts['candidate_rows']:,}",
            f"- Rejected/deferred by full gate: {counts['rejected_by_full_gate_rows']:,}",
            "- Training admission: not granted",
            "- Validation/test eligibility: false",
            "- Training run started: false",
            "",
            "Only full-gate rows marked `provisionally_keep_current_silver_row`",
            "with no policy hits or risk flags are included. This surface-screened",
            "package remains a reviewable candidate and does not modify `train11397_*`.",
            "",
        ]
    )


def write_outputs(
    result: StrictCandidatePackageResult,
    *,
    output_dir: Path,
    output_prefix: str = OUTPUT_PREFIX,
    train_json: Path = DEFAULT_TRAIN_JSON,
    full_gate_jsonl: Path = DEFAULT_FULL_GATE_JSONL,
    task_type_vocab: Path = DEFAULT_TASK_TYPE_VOCAB,
) -> dict[str, Path]:
    paths = resolve_output_paths(
        output_dir, output_prefix=output_prefix, candidate_rows=len(result.rows)
    )
    workflow_payload = {
        "schema": "gis_recommend.labeled_workflows_l3_v4.gee_strict_candidate.v1",
        "dataset_id": f"{output_prefix}_train{len(result.rows)}",
        "labeled_workflows": result.rows,
        "metadata": {
            "package_id": output_prefix,
            "training_admission": STRICT_ADMISSION,
            "split": STRICT_SPLIT,
            "source_package": str(train_json),
            "full_gate": str(full_gate_jsonl),
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
        },
    }
    _atomic_write(paths["workflows"], _json_text(workflow_payload))
    _atomic_write(paths["sidecar"], _jsonl_text(result.sidecar_rows))
    _atomic_write(paths["task_type_vocab"], _json_text(result.task_type_vocab))
    _atomic_write(paths["splits"], _json_text(result.splits))
    _atomic_write(paths["summary"], _json_text(result.summary))
    _atomic_write(paths["report"], _render_report(result.summary))

    ledger = {
        "schema": "gis_recommend.gee_strict_candidate_hash_ledger.v1",
        "source_inputs": {
            Path(train_json).name: {
                "path": str(train_json),
                "sha256": _sha256(train_json),
                "bytes": os.path.getsize(_filesystem_path(Path(train_json))),
            },
            Path(full_gate_jsonl).name: {
                "path": str(full_gate_jsonl),
                "sha256": _sha256(full_gate_jsonl),
                "bytes": os.path.getsize(_filesystem_path(Path(full_gate_jsonl))),
            },
            Path(task_type_vocab).name: {
                "path": str(task_type_vocab),
                "sha256": _sha256(task_type_vocab),
                "bytes": os.path.getsize(_filesystem_path(Path(task_type_vocab))),
            },
        },
        "artifacts": {
            path.name: {
                "path": str(path),
                "sha256": _sha256(path),
                "bytes": os.path.getsize(_filesystem_path(path)),
            }
            for key, path in paths.items()
            if key != "hash_ledger"
        },
    }
    _atomic_write(paths["hash_ledger"], _json_text(ledger))
    return paths


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-json", type=Path, default=DEFAULT_TRAIN_JSON)
    parser.add_argument("--full-gate-jsonl", type=Path, default=DEFAULT_FULL_GATE_JSONL)
    parser.add_argument("--task-type-vocab", type=Path, default=DEFAULT_TASK_TYPE_VOCAB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    args = parser.parse_args(argv)

    result = build_strict_candidate_package(
        train_json=args.train_json,
        full_gate_jsonl=args.full_gate_jsonl,
        task_type_vocab=args.task_type_vocab,
    )
    return write_outputs(
        result,
        output_dir=args.output_dir,
        output_prefix=args.output_prefix,
        train_json=args.train_json,
        full_gate_jsonl=args.full_gate_jsonl,
        task_type_vocab=args.task_type_vocab,
    )


if __name__ == "__main__":
    main()
