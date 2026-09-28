#!/usr/bin/env python3
"""Export the grafted GEE raster-core candidate pool as a batch train-only package.

This is the scalable path for GEE data construction. Manual review is used only
as sampling audit and rule calibration; the exporter itself is deterministic:

* accept only authoritative source-identity grafted rows;
* require the existing 94-L3 mapping to cover every L3 code;
* keep all rows train-only, even if the earlier review split assigned an audit
  split of train/val/test;
* put failed rows and long chains into sidecars instead of guessing or
  truncating.

The artifact is a low-weight GEE raster/L3 silver package. It is not QGIS
operator-chain gold, not validation/test data, not a production merge, and it
does not start training.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


DEFAULT_GRAFTED_ROWS = (
    ROOT
    / "docs/reports/gee_raster_core_v1_source_identity_graft_2026-07-24"
    / "grafted_selected_rows.jsonl"
)
DEFAULT_SPLIT_ASSIGNMENTS = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "split_assignments.jsonl"
)
DEFAULT_ID_MAPPINGS = ROOT / "outputs_v2/id_mappings_v2.json"
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1"
)

PACKAGE_ID = "gee_raster_core_batch_training_package_v1"
TRAINING_ADMISSION = "granted_train_only_gee_raster_core_batch_silver_v1"
TRAIN_ONLY_SPLIT = "train_only_gee_raster_core_batch_v1"
TASK_TYPE_FALLBACK = "Unknown"
V4_DEFAULT_MAX_SEQ_LENGTH = 100
START_TOKEN = -3
END_TOKEN = -4
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

DEFERRED_CSV_FIELDS = (
    "input_row_index",
    "gate_status",
    "gate_reasons",
    "proposal_id",
    "script_id",
    "source_identity_status",
    "source_sha256",
    "source_path",
    "source_platform",
    "target_platform",
    "workflow_scope",
    "training_tier",
    "source_split",
    "task_type",
    "task_name",
    "task_description",
    "operator_count",
    "l3_count",
    "sample_weight",
    "validation_eligible",
    "test_eligible",
    "next_action",
)

LONG_CHAIN_CSV_FIELDS = (
    "sample_id",
    "proposal_id",
    "script_id",
    "content_length",
    "model_sequence_length",
    "required_max_seq_length",
    "fits_v4_max_seq_length_100",
    "source_sha256",
    "source_path",
    "task_type",
    "task_name",
    "task_description",
    "next_action",
)

AUDIT_CSV_FIELDS = (
    "audit_rank",
    "audit_status",
    "sample_id",
    "proposal_id",
    "script_id",
    "task_type",
    "task_name",
    "task_description",
    "operator_sequence",
    "l3_code_sequence",
    "model_sequence_length",
    "source_sha256",
    "source_path",
    "review_split_audit",
    "audit_questions",
)


@dataclass(frozen=True)
class BatchTrainingPackageResult:
    accepted_rows: list[dict[str, Any]]
    v4_100_rows: list[dict[str, Any]]
    long_chain_rows: list[dict[str, Any]]
    deferred_rows: list[dict[str, Any]]
    audit_sample_rows: list[dict[str, Any]]
    splits: dict[str, list[int]]
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


def _stable_hash(*parts: Any) -> str:
    payload = json.dumps(parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sequence_hash(values: list[str]) -> str:
    return _stable_hash(values)


def _as_str(value: Any) -> str:
    return str(value or "").strip()


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _is_false(value: Any) -> bool:
    return value is False


def _source_sha_counts(rows: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        if row.get("source_identity_status") != "authoritative_grafted":
            continue
        sha = _as_str(row.get("source_sha256"))
        if sha:
            counts[sha] += 1
    return counts


def _split_assignment_by_sha(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    rows = _load_jsonl(path)
    by_sha: dict[str, dict[str, Any]] = {}
    for row in rows:
        sha = _as_str(row.get("source_sha256"))
        if not sha:
            continue
        if sha in by_sha:
            raise ValueError(f"duplicate source_sha256 in split assignments: {sha}")
        by_sha[sha] = row
    return by_sha


def _gate_reasons(
    row: dict[str, Any],
    *,
    l3_to_id: dict[str, int],
    source_sha_counts: Counter[str],
    split_by_sha: dict[str, dict[str, Any]],
) -> list[str]:
    reasons: list[str] = []

    source_identity_status = _as_str(row.get("source_identity_status"))
    source_sha256 = _as_str(row.get("source_sha256"))
    source_path = _as_str(row.get("source_path"))
    l3_codes = _as_string_list(row.get("l3_codes"))
    operators = _as_string_list(row.get("operator_sequence"))

    if source_identity_status != "authoritative_grafted":
        reasons.append("source_identity_not_authoritative")
    if not _SHA256_RE.fullmatch(source_sha256):
        reasons.append("source_sha256_missing_or_invalid")
    elif source_sha_counts[source_sha256] != 1:
        reasons.append("duplicate_source_sha256")
    if not source_path:
        reasons.append("source_path_missing")

    expected_fields = {
        "source_platform": "GEE",
        "target_platform": "L3",
        "workflow_scope": "core_analysis",
        "training_tier": "silver_a",
        "source_split": "train",
    }
    for field, expected in expected_fields.items():
        if row.get(field) != expected:
            reasons.append(f"{field}_not_{expected}")
    if not _is_false(row.get("validation_eligible")):
        reasons.append("validation_eligible_not_false")
    if not _is_false(row.get("test_eligible")):
        reasons.append("test_eligible_not_false")

    sample_weight = row.get("sample_weight")
    if (
        isinstance(sample_weight, bool)
        or not isinstance(sample_weight, (int, float))
        or not 0 < float(sample_weight) <= 0.5
    ):
        reasons.append("sample_weight_out_of_range")

    if not _as_str(row.get("task_name")):
        reasons.append("task_name_missing")
    if not _as_str(row.get("task_description")):
        reasons.append("task_description_missing")
    if not l3_codes:
        reasons.append("l3_codes_empty")
    if not operators:
        reasons.append("operator_sequence_empty")
    if l3_codes and operators and len(l3_codes) != len(operators):
        reasons.append("operator_l3_length_mismatch")
    missing_l3_codes = sorted({code for code in l3_codes if code not in l3_to_id})
    if missing_l3_codes:
        reasons.append("l3_code_not_in_outputs_v2_mapping")

    if split_by_sha and _SHA256_RE.fullmatch(source_sha256) and source_sha256 not in split_by_sha:
        reasons.append("missing_review_split_assignment")

    return reasons


def _deferred_row(row: dict[str, Any], *, input_row_index: int, reasons: list[str]) -> dict[str, Any]:
    operators = _as_string_list(row.get("operator_sequence"))
    l3_codes = _as_string_list(row.get("l3_codes"))
    return {
        "schema": "gis_recommend.gee_raster_core_batch_gate_sidecar_row.v1",
        "input_row_index": input_row_index,
        "gate_status": "deferred",
        "gate_reasons": reasons,
        "proposal_id": row.get("proposal_id", ""),
        "script_id": row.get("script_id", ""),
        "source_identity_status": row.get("source_identity_status", ""),
        "source_sha256": row.get("source_sha256", ""),
        "source_path": row.get("source_path", ""),
        "source_platform": row.get("source_platform", ""),
        "target_platform": row.get("target_platform", ""),
        "workflow_scope": row.get("workflow_scope", ""),
        "training_tier": row.get("training_tier", ""),
        "source_split": row.get("source_split", ""),
        "task_type": row.get("task_type", ""),
        "task_name": row.get("task_name", ""),
        "task_description": row.get("task_description", ""),
        "operator_sequence": operators,
        "l3_codes": l3_codes,
        "operator_count": len(operators),
        "l3_count": len(l3_codes),
        "sample_weight": row.get("sample_weight", ""),
        "validation_eligible": row.get("validation_eligible", ""),
        "test_eligible": row.get("test_eligible", ""),
        "training_admission": "not_granted_batch_gate_deferred",
        "production_merge": "not_granted",
        "next_action": "repair the listed deterministic gate reason, then rerun this batch exporter",
    }


def _convert_row(
    row: dict[str, Any],
    *,
    input_row_index: int,
    l3_to_id: dict[str, int],
    split_by_sha: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    source_sha256 = _as_str(row["source_sha256"])
    l3_codes = _as_string_list(row.get("l3_codes"))
    operators = _as_string_list(row.get("operator_sequence"))
    token_ids = [int(l3_to_id[code]) for code in l3_codes]
    model_sequence = [START_TOKEN, *token_ids, END_TOKEN]
    task_type = _as_str(row.get("task_type")) or TASK_TYPE_FALLBACK
    review_split = _as_str((split_by_sha.get(source_sha256) or {}).get("split"))
    if not review_split:
        review_split = "not_available"
    sample_weight = float(row.get("sample_weight") or 0.5)
    sequence_fit = {
        "content_length": len(token_ids),
        "model_sequence_length": len(model_sequence),
        "v4_default_max_seq_length": V4_DEFAULT_MAX_SEQ_LENGTH,
        "fits_v4_max_seq_length_100": len(model_sequence) <= V4_DEFAULT_MAX_SEQ_LENGTH,
        "required_max_seq_length": len(model_sequence),
    }
    l3_sequence_hash = _sequence_hash(l3_codes)
    operator_sequence_hash = _sequence_hash(operators)
    return {
        "schema_version": "gee_raster_core_batch_training_sample_v1",
        "sample_id": f"gee_raster_core_batch_v1_{source_sha256[:16]}",
        "source": PACKAGE_ID,
        "input_row_index": input_row_index,
        "proposal_id": row.get("proposal_id", ""),
        "script_id": row.get("script_id", ""),
        "source_platform": "GEE",
        "target_platform": "L3",
        "workflow_scope": row.get("workflow_scope", "core_analysis"),
        "training_scope": "core_subworkflow",
        "task_name": _as_str(row.get("task_name")),
        "task_description": _as_str(row.get("task_description")),
        "task_type": task_type,
        "task_metadata": {
            "task_type": task_type,
            "task_name": _as_str(row.get("task_name")),
            "task_description": _as_str(row.get("task_description")),
            "source_platform": "GEE",
            "target_platform": "L3",
            "training_scope": "core_subworkflow",
            "workflow_scope": row.get("workflow_scope", "core_analysis"),
        },
        "operator_sequence": operators,
        "operator_sequence_hash": operator_sequence_hash,
        "l3_code_sequence": l3_codes,
        "l3_sequence_hash": l3_sequence_hash,
        "l3_token_ids": token_ids,
        "l3_sequence": model_sequence,
        "source_sha256": source_sha256,
        "source_path": _as_str(row.get("source_path")),
        "source_index": row.get("source_index"),
        "quality_gate_source_index": row.get("quality_gate_source_index"),
        "source_identity_status": row.get("source_identity_status", ""),
        "source_identity_authority": row.get("source_identity_authority", ""),
        "source_identity_graft": row.get("source_identity_graft", {}),
        "source_identity": row.get("source_identity", {}),
        "selection_reason": row.get("selection_reason", ""),
        "source_split": row.get("source_split", ""),
        "review_split_audit": review_split,
        "review_required_before_promotion": True,
        "training_tier": row.get("training_tier", ""),
        "training_admission": TRAINING_ADMISSION,
        "split": TRAIN_ONLY_SPLIT,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "sample_weight": sample_weight,
        "_training_quality": {
            "tier": TRAINING_ADMISSION,
            "source_tier": row.get("training_tier", ""),
            "sample_weight": sample_weight,
            "validation_eligible": False,
            "test_eligible": False,
            "authority": "deterministic_grafted_gee_raster_core_v1",
            "manual_review_role": "sampling_audit_only",
            "exclude_from_validation_test": True,
            "exclude_from_qgis_operator_chain_gold": True,
        },
        "sequence_fit": sequence_fit,
    }


def _splits(row_count: int) -> dict[str, list[int]]:
    return {
        "train_indices": list(range(row_count)),
        "val_indices": [],
        "test_indices": [],
    }


def _task_type_vocab(rows: list[dict[str, Any]]) -> dict[str, Any]:
    task_types = sorted({str(row.get("task_type") or TASK_TYPE_FALLBACK) for row in rows})
    ordered = [TASK_TYPE_FALLBACK] + [name for name in task_types if name != TASK_TYPE_FALLBACK]
    task_type_to_id = {name: index for index, name in enumerate(ordered)}
    return {
        "task_type_to_id": task_type_to_id,
        "id_to_task_type": {str(index): name for name, index in task_type_to_id.items()},
        "num_types": len(task_type_to_id),
    }


def _long_chain_sidecar_row(row: dict[str, Any]) -> dict[str, Any]:
    fit = row["sequence_fit"]
    return {
        "schema": "gis_recommend.gee_raster_core_batch_long_chain_sidecar_row.v1",
        "sample_id": row["sample_id"],
        "proposal_id": row["proposal_id"],
        "script_id": row["script_id"],
        "sequence_fit": fit,
        "content_length": fit["content_length"],
        "model_sequence_length": fit["model_sequence_length"],
        "required_max_seq_length": fit["required_max_seq_length"],
        "fits_v4_max_seq_length_100": fit["fits_v4_max_seq_length_100"],
        "source_sha256": row["source_sha256"],
        "source_path": row["source_path"],
        "task_type": row["task_type"],
        "task_name": row["task_name"],
        "task_description": row["task_description"],
        "training_admission": "granted_train_only_requires_long_sequence_loader",
        "validation_eligible": False,
        "test_eligible": False,
        "next_action": "train with max_seq_length >= required_max_seq_length or split with reviewed boundaries",
    }


def _build_audit_sample(
    rows: list[dict[str, Any]],
    *,
    sample_size: int,
    seed: str = PACKAGE_ID,
) -> list[dict[str, Any]]:
    if sample_size <= 0 or not rows:
        return []
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get("task_type") or TASK_TYPE_FALLBACK)].append(row)

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    ranked_groups = sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))
    for task_type, group_rows in ranked_groups:
        if len(selected) >= sample_size:
            break
        chosen = min(
            group_rows,
            key=lambda item: _stable_hash(seed, task_type, item["source_sha256"], item["l3_sequence_hash"]),
        )
        selected.append(chosen)
        selected_ids.add(chosen["sample_id"])

    if len(selected) < sample_size:
        remainder = sorted(
            [row for row in rows if row["sample_id"] not in selected_ids],
            key=lambda item: _stable_hash(seed, item["source_sha256"], item["task_type"], item["l3_sequence_hash"]),
        )
        for row in remainder[: sample_size - len(selected)]:
            selected.append(row)

    audit_rows: list[dict[str, Any]] = []
    for rank, row in enumerate(selected, start=1):
        audit_rows.append(
            {
                "schema": "gis_recommend.gee_raster_core_batch_audit_sample_row.v1",
                "audit_rank": rank,
                "audit_status": "pending_human_sampling_audit",
                "sample_id": row["sample_id"],
                "proposal_id": row["proposal_id"],
                "script_id": row["script_id"],
                "task_type": row["task_type"],
                "task_name": row["task_name"],
                "task_description": row["task_description"],
                "operator_sequence": row["operator_sequence"],
                "l3_code_sequence": row["l3_code_sequence"],
                "model_sequence_length": row["sequence_fit"]["model_sequence_length"],
                "source_sha256": row["source_sha256"],
                "source_path": row["source_path"],
                "review_split_audit": row["review_split_audit"],
                "audit_questions": [
                    "task text is faithful to the core raster workflow",
                    "operator/L3 sequence covers the core analysis without UI/export noise",
                    "row should remain train-only unless a separate validation/test gold gate is granted",
                ],
            }
        )
    return audit_rows


def build_batch_training_package(
    *,
    grafted_rows_path: Path,
    id_mappings_path: Path,
    split_assignments_path: Path | None = DEFAULT_SPLIT_ASSIGNMENTS,
    audit_sample_size: int = 50,
) -> BatchTrainingPackageResult:
    input_rows = _load_jsonl(grafted_rows_path)
    mappings = _load_json(id_mappings_path)
    l3_to_id = mappings.get("l3") or {}
    if len(l3_to_id) != 94:
        raise ValueError(f"expected 94-L3 id mapping, got {len(l3_to_id)}")

    split_by_sha = _split_assignment_by_sha(split_assignments_path)
    sha_counts = _source_sha_counts(input_rows)
    source_identity_status_counts = Counter(
        _as_str(row.get("source_identity_status")) or "missing"
        for row in input_rows
    )

    accepted_rows: list[dict[str, Any]] = []
    deferred_rows: list[dict[str, Any]] = []
    for input_row_index, row in enumerate(input_rows, start=1):
        reasons = _gate_reasons(
            row,
            l3_to_id=l3_to_id,
            source_sha_counts=sha_counts,
            split_by_sha=split_by_sha,
        )
        if reasons:
            deferred_rows.append(_deferred_row(row, input_row_index=input_row_index, reasons=reasons))
            continue
        accepted_rows.append(
            _convert_row(
                row,
                input_row_index=input_row_index,
                l3_to_id=l3_to_id,
                split_by_sha=split_by_sha,
            )
        )

    if len({row["sample_id"] for row in accepted_rows}) != len(accepted_rows):
        raise ValueError("sample_id values must be unique")
    if len({row["source_sha256"] for row in accepted_rows}) != len(accepted_rows):
        raise ValueError("source_sha256 values must be unique")

    v4_100_rows = [
        row for row in accepted_rows if row["sequence_fit"]["fits_v4_max_seq_length_100"]
    ]
    long_chain_rows = [
        _long_chain_sidecar_row(row)
        for row in accepted_rows
        if not row["sequence_fit"]["fits_v4_max_seq_length_100"]
    ]
    audit_sample_rows = _build_audit_sample(
        accepted_rows,
        sample_size=audit_sample_size,
    )
    task_type_vocab = _task_type_vocab(accepted_rows)

    sequence_lengths = [len(row["l3_sequence"]) for row in accepted_rows] or [0]
    token_ids = [token for row in accepted_rows for token in row["l3_token_ids"]]
    deferred_reason_counts = Counter(
        reason for row in deferred_rows for reason in row["gate_reasons"]
    )
    review_split_audit_counts = Counter(row["review_split_audit"] for row in accepted_rows)
    task_type_counts = Counter(row["task_type"] for row in accepted_rows)

    summary = {
        "schema": "gis_recommend.gee_raster_core_batch_training_package_summary.v1",
        "package_id": PACKAGE_ID,
        "inputs": {
            "grafted_rows": str(Path(grafted_rows_path)),
            "id_mappings": str(Path(id_mappings_path)),
            "split_assignments": str(Path(split_assignments_path)) if split_assignments_path else "",
        },
        "counts": {
            "input_rows": len(input_rows),
            "accepted_rows": len(accepted_rows),
            "v4_100_no_truncation_rows": len(v4_100_rows),
            "long_chain_sidecar_rows": len(long_chain_rows),
            "deferred_gate_sidecar_rows": len(deferred_rows),
            "audit_sample_rows": len(audit_sample_rows),
            "unique_source_sha256": len({row["source_sha256"] for row in accepted_rows}),
            "unique_l3_sequences": len({tuple(row["l3_code_sequence"]) for row in accepted_rows}),
            "unique_operator_sequences": len({tuple(row["operator_sequence"]) for row in accepted_rows}),
            "unique_l3_token_ids": len(set(token_ids)),
            "min_model_sequence_length": min(sequence_lengths),
            "max_model_sequence_length": max(sequence_lengths),
            "task_type_count": len(task_type_counts),
        },
        "source_identity_status_counts": dict(sorted(source_identity_status_counts.items())),
        "deferred_reason_counts": dict(sorted(deferred_reason_counts.items())),
        "review_split_audit_counts": dict(sorted(review_split_audit_counts.items())),
        "top_task_type_counts": task_type_counts.most_common(20),
        "decision": {
            "training_admission": TRAINING_ADMISSION,
            "split": TRAIN_ONLY_SPLIT,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge_granted": False,
            "training_run_started": False,
            "llm_used": False,
            "manual_review_is_sampling_audit_only": True,
            "dataset_level": "deterministic_silver_train_only",
            "default_v4_no_truncation_package": "v4_100",
            "long_chain_policy": "sidecar unless loader max_seq_length is raised or chain is reviewed/split",
        },
        "policy": {
            "source_platform": "GEE",
            "target_platform": "L3",
            "workflow_scope": "core_analysis",
            "training_scope": "core_subworkflow",
            "training_tier": "silver_a",
            "sample_weight_max": 0.5,
            "start_token": START_TOKEN,
            "end_token": END_TOKEN,
            "id_mapping_vocab_size": 94,
            "exclude_from_qgis_operator_chain_gold": True,
            "exclude_from_validation_test": True,
            "source_identity_required": True,
            "unmatched_rows_fail_closed": True,
        },
    }

    return BatchTrainingPackageResult(
        accepted_rows=accepted_rows,
        v4_100_rows=v4_100_rows,
        long_chain_rows=long_chain_rows,
        deferred_rows=deferred_rows,
        audit_sample_rows=audit_sample_rows,
        splits=_splits(len(accepted_rows)),
        task_type_vocab=task_type_vocab,
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


def _workflow_payload(
    rows: list[dict[str, Any]],
    *,
    dataset_id: str,
    result: BatchTrainingPackageResult,
) -> dict[str, Any]:
    return {
        "schema": "gis_recommend.labeled_workflows_l3_v4.gee_raster_core_batch.v1",
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
            "manual_review_is_sampling_audit_only": True,
            "task_type_vocab": result.task_type_vocab,
            "counts": result.summary["counts"],
        },
    }


def _render_report(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    decision = summary["decision"]
    lines = [
        "# GEE Raster Core Batch Training Package v1",
        "",
        "This is the scalable GEE raster/L3 train-only export. It converts the",
        "source-identity grafted candidate pool in batch and uses deterministic",
        "gates plus sidecars instead of row-by-row production review.",
        "",
        "## Result",
        "",
        f"- Input rows: {counts['input_rows']:,}",
        f"- Accepted train-only rows: {counts['accepted_rows']:,}",
        f"- V4-100 no-truncation rows: {counts['v4_100_no_truncation_rows']:,}",
        f"- Deferred gate sidecar rows: {counts['deferred_gate_sidecar_rows']:,}",
        f"- Long-chain sidecar rows: {counts['long_chain_sidecar_rows']:,}",
        f"- Audit sample rows: {counts['audit_sample_rows']:,}",
        f"- Unique source SHA256 values: {counts['unique_source_sha256']:,}",
        f"- Unique L3 sequences: {counts['unique_l3_sequences']:,}",
        f"- Unique operator sequences: {counts['unique_operator_sequences']:,}",
        f"- Model sequence length: {counts['min_model_sequence_length']}..{counts['max_model_sequence_length']}",
        f"- Training admission: `{decision['training_admission']}`",
        f"- Split: `{decision['split']}`",
        f"- Validation eligible: `{decision['validation_eligible']}`",
        f"- Test eligible: `{decision['test_eligible']}`",
        f"- Production merge granted: `{decision['production_merge_granted']}`",
        f"- Training run started: `{decision['training_run_started']}`",
        f"- Manual review role: sampling audit only = `{decision['manual_review_is_sampling_audit_only']}`",
        "",
        "## Gate failures",
        "",
    ]
    for reason, count in summary["deferred_reason_counts"].items():
        lines.append(f"- `{reason}`: {count:,}")
    lines.extend(
        [
            "",
            "## Review split handling",
            "",
            "The prior source/sequence-disjoint split is retained only as an audit",
            "field. This exporter does not emit validation/test rows because GEE",
            "validation/test promotion has not been granted.",
            "",
        ]
    )
    for split, count in summary["review_split_audit_counts"].items():
        lines.append(f"- original `{split}` audit rows: {count:,}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- This package is GEE raster/L3 silver supervision, not QGIS operator-chain gold.",
            "- It does not rewrite task descriptions or infer missing operators.",
            "- Unmatched source-identity rows fail closed into sidecar.",
            "- Human review is a stratified audit sample used to calibrate future rules.",
            "",
        ]
    )
    return "\n".join(lines)


def resolve_output_paths(
    *,
    output_dir: Path,
    accepted_count: int,
    v4_count: int,
    audit_sample_size: int,
) -> dict[str, Path]:
    """Resolve output artifact paths with Windows-safe short filenames."""

    output_dir = Path(output_dir)
    return {
        "full_workflows": output_dir / f"train{accepted_count}_full.json",
        "v4_100_workflows": output_dir / f"train{v4_count}_v4_100.json",
        "splits": output_dir / f"splits_train{accepted_count}.json",
        "task_type_vocab": output_dir / "task_type_vocab.json",
        "deferred_jsonl": output_dir / "deferred_sidecar.jsonl",
        "deferred_csv": output_dir / "deferred_sidecar.csv",
        "long_chain_jsonl": output_dir / "long_chain_sidecar.jsonl",
        "long_chain_csv": output_dir / "long_chain_sidecar.csv",
        "audit_sample_jsonl": output_dir / f"audit_sample_{audit_sample_size}.jsonl",
        "audit_sample_csv": output_dir / f"audit_sample_{audit_sample_size}.csv",
        "summary": output_dir / "summary.json",
        "report": output_dir / "report.md",
        "hash_ledger": output_dir / "hash_ledger.json",
    }


def write_outputs(result: BatchTrainingPackageResult, output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    accepted_count = len(result.accepted_rows)
    v4_count = len(result.v4_100_rows)
    paths = resolve_output_paths(
        output_dir=output_dir,
        accepted_count=accepted_count,
        v4_count=v4_count,
        audit_sample_size=len(result.audit_sample_rows),
    )

    _atomic_write(
        paths["full_workflows"],
        json.dumps(
            _workflow_payload(
                result.accepted_rows,
                dataset_id=f"gee_raster_core_batch_train{accepted_count}_full_v1",
                result=result,
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    _atomic_write(
        paths["v4_100_workflows"],
        json.dumps(
            _workflow_payload(
                result.v4_100_rows,
                dataset_id=f"gee_raster_core_batch_train{v4_count}_v4_100_v1",
                result=result,
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    _atomic_write(paths["splits"], json.dumps(result.splits, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _atomic_write(paths["task_type_vocab"], json.dumps(result.task_type_vocab, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _atomic_write(paths["deferred_jsonl"], _jsonl_text(result.deferred_rows))
    _atomic_write(paths["deferred_csv"], _csv_text(result.deferred_rows, fieldnames=DEFERRED_CSV_FIELDS))
    _atomic_write(paths["long_chain_jsonl"], _jsonl_text(result.long_chain_rows))
    _atomic_write(paths["long_chain_csv"], _csv_text(result.long_chain_rows, fieldnames=LONG_CHAIN_CSV_FIELDS))
    _atomic_write(paths["audit_sample_jsonl"], _jsonl_text(result.audit_sample_rows))
    _atomic_write(paths["audit_sample_csv"], _csv_text(result.audit_sample_rows, fieldnames=AUDIT_CSV_FIELDS))
    _atomic_write(paths["summary"], json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _atomic_write(paths["report"], _render_report(result.summary))

    source_inputs = {
        name: {
            "path": path,
            "sha256": _sha256(Path(path)),
        }
        for name, path in sorted(result.summary["inputs"].items())
        if path
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
    parser.add_argument("--grafted-rows", type=Path, default=DEFAULT_GRAFTED_ROWS)
    parser.add_argument("--split-assignments", type=Path, default=DEFAULT_SPLIT_ASSIGNMENTS)
    parser.add_argument("--id-mappings", type=Path, default=DEFAULT_ID_MAPPINGS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--audit-sample-size", type=int, default=50)
    args = parser.parse_args(argv)

    result = build_batch_training_package(
        grafted_rows_path=args.grafted_rows,
        id_mappings_path=args.id_mappings,
        split_assignments_path=args.split_assignments,
        audit_sample_size=args.audit_sample_size,
    )
    return write_outputs(result, args.output_dir)


if __name__ == "__main__":
    main()
