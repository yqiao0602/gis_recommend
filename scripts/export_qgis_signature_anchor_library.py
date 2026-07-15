#!/usr/bin/env python3
"""Export a deterministic library from fully adjudicated QGIS signatures."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.validate_qgis_core_signature_adjudications import validate_and_summarize


SCHEMA_VERSION = "qgis_signature_anchor_library_v1"
ANCHOR_SCHEMA_VERSION = "qgis_signature_anchor_v1"
EXCLUDED_TRANSFER_SOURCE_TYPES = {
    "FILESYSTEM",
    "PATH_OP",
    "PYTHON_BUILTIN",
    "PYTHON_COLLECTION",
    "TEXT_OP",
    "arcgis_tool",
    "gee_runtime_method",
    "platform_guard",
    "pyqt_ui",
    "python_builtin",
    "python_env",
    "qgis_plugin_helper",
    "qgis_processing_feedback",
    "qgis_processing_parameter",
    "qgis_processing_result_unpack",
    "qgis_processing_runtime",
    "synthetic_expression",
}


class AnchorExportError(ValueError):
    pass


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _json_compact(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _load_review(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    indexed = {}
    for row in rows:
        key = (row.get("record_id", ""), row.get("class_name", ""))
        if key in indexed:
            raise AnchorExportError(f"duplicate review key: {key}")
        indexed[key] = row
    return indexed


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    values = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AnchorExportError(f"invalid JSONL line {line_number}: {exc}") from exc
            if not isinstance(value, dict):
                raise AnchorExportError(f"JSONL line {line_number} must be an object")
            values.append(value)
    return values


def _load_signatures(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    indexed = {}
    for record in _load_jsonl(path):
        record_id = str(record.get("record_id") or "")
        for signature in record.get("class_signatures") or []:
            if not isinstance(signature, dict):
                continue
            key = (record_id, str(signature.get("class_name") or ""))
            if key in indexed:
                raise AnchorExportError(f"duplicate signature key: {key}")
            indexed[key] = {
                "source": record.get("source") or {},
                "signature": signature,
            }
    return indexed


def _candidate_for_operator(row: dict[str, str], operator_id: str) -> dict[str, Any]:
    for field in ("exact_candidates_json", "ranked_candidates_json"):
        try:
            candidates = json.loads(row.get(field) or "[]")
        except json.JSONDecodeError as exc:
            raise AnchorExportError(f"invalid candidate JSON for {operator_id}") from exc
        for candidate in candidates:
            if isinstance(candidate, dict) and candidate.get("operator_id") == operator_id:
                return candidate
    raise AnchorExportError(f"accepted operator missing from review candidates: {operator_id}")


def _clean_parameters(parameters: Any) -> list[dict[str, Any]]:
    cleaned = []
    for parameter in parameters or []:
        if not isinstance(parameter, dict):
            continue
        cleaned.append(
            {
                key: parameter.get(key)
                for key in ("direction", "identifier", "label", "parameter_type")
            }
        )
    return sorted(
        cleaned,
        key=lambda item: (
            str(item.get("direction") or ""),
            str(item.get("identifier") or ""),
            str(item.get("label") or ""),
        ),
    )


def _keep_transfer_call(call: dict[str, Any]) -> bool:
    operation = str(call.get("operation") or "").strip().lower()
    source_type = str(call.get("api_source_type") or "")
    if not operation or source_type in EXCLUDED_TRANSFER_SOURCE_TYPES:
        return False
    if operation in {"return", "super"}:
        return False
    return not operation.startswith(
        ("condition_", "func_", "raise_", "return_", "self.", "super.")
    )


def _transfer_operations(calls: Any) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for call in calls or []:
        if not isinstance(call, dict) or not _keep_transfer_call(call):
            continue
        operation = str(call.get("operation") or "").strip().lower()
        source_type = str(call.get("api_source_type") or "")
        key = (operation, source_type)
        value = grouped.setdefault(
            key,
            {
                "operation": operation,
                "api_source_type": source_type,
                "count": 0,
                "semantic_roles": set(),
            },
        )
        value["count"] += 1
        role = str(call.get("semantic_role") or "").strip()
        if role:
            value["semantic_roles"].add(role)
    result = []
    for value in grouped.values():
        result.append(
            {
                "operation": value["operation"],
                "api_source_type": value["api_source_type"],
                "count": value["count"],
                "semantic_roles": sorted(value["semantic_roles"]),
            }
        )
    return sorted(result, key=lambda item: (item["operation"], item["api_source_type"]))


def export_anchor_library(
    review_path: str | Path,
    decisions_path: str | Path,
    signature_records_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    review_path = Path(review_path)
    decisions_path = Path(decisions_path)
    signature_records_path = Path(signature_records_path)
    output_dir = Path(output_dir)

    adjudication = validate_and_summarize(review_path, decisions_path)
    if not adjudication["human_review_complete"]:
        raise AnchorExportError("review must be complete before anchor export")
    if adjudication["anchor_export_admission"] != "ready":
        raise AnchorExportError("anchor export admission is not ready")

    review = _load_review(review_path)
    signatures = _load_signatures(signature_records_path)
    decisions = _load_jsonl(decisions_path)
    accepted = [decision for decision in decisions if decision.get("decision") == "accept"]
    operator_ids = [str(decision.get("accepted_operator_id") or "") for decision in accepted]
    if len(operator_ids) != len(set(operator_ids)):
        duplicates = sorted(
            operator_id
            for operator_id in set(operator_ids)
            if operator_ids.count(operator_id) > 1
        )
        raise AnchorExportError(f"accepted operator IDs must be unique: {duplicates}")

    source_review_sha256 = _sha256(review_path)
    anchors = []
    for decision in sorted(
        accepted,
        key=lambda item: (
            str(item.get("accepted_operator_id") or ""),
            str(item.get("record_id") or ""),
            str(item.get("class_name") or ""),
        ),
    ):
        key = (str(decision.get("record_id") or ""), str(decision.get("class_name") or ""))
        if key not in review:
            raise AnchorExportError(f"accepted decision missing review row: {key}")
        if key not in signatures:
            raise AnchorExportError(f"accepted decision missing full signature: {key}")
        row = review[key]
        record = signatures[key]
        if row.get("trace_sha256") != decision.get("trace_sha256"):
            raise AnchorExportError(f"decision trace mismatch for {key}")
        source_trace = str((record.get("source") or {}).get("trace_sha256") or "")
        if source_trace and source_trace != row.get("trace_sha256"):
            raise AnchorExportError(f"signature trace mismatch for {key}")

        operator_id = str(decision["accepted_operator_id"])
        candidate = _candidate_for_operator(row, operator_id)
        signature = record["signature"]
        transfer_operations = _transfer_operations(signature.get("ordered_calls"))
        anchor_id = _stable_hash(
            {
                "source_review_sha256": source_review_sha256,
                "record_id": key[0],
                "class_name": key[1],
                "operator_id": operator_id,
                "trace_sha256": row.get("trace_sha256"),
            }
        )[:24]
        anchors.append(
            {
                "schema_version": ANCHOR_SCHEMA_VERSION,
                "anchor_id": anchor_id,
                "operator_id": operator_id,
                "official_name": candidate.get("official_name"),
                "provider_group": candidate.get("provider_group") or operator_id.split(":", 1)[0],
                "record_id": key[0],
                "class_name": key[1],
                "normalized_class_name": signature.get("normalized_class_name"),
                "class_bases": sorted(signature.get("class_bases") or []),
                "trace_sha256": row.get("trace_sha256"),
                "source_review_sha256": source_review_sha256,
                "provider_evidence": signature.get("provider_evidence") or {},
                "parameters": _clean_parameters(signature.get("parameters")),
                "ordered_call_count": len(signature.get("ordered_calls") or []),
                "transfer_operations": transfer_operations,
                "transfer_operation_set_sha256": _stable_hash(transfer_operations),
                "human_review": {
                    "batch_id": decision.get("batch_id"),
                    "reviewer": decision.get("reviewer"),
                    "reviewed_on": decision.get("reviewed_on"),
                    "review_basis": decision.get("review_basis"),
                },
                "taxonomy_admission": "not_granted",
                "training_admission": "not_granted",
            }
        )

    output_dir.mkdir(parents=True, exist_ok=False)
    anchors_path = output_dir / "accepted_signature_anchors.jsonl"
    anchors_path.write_text(
        "".join(_json_compact(anchor) + "\n" for anchor in anchors),
        encoding="utf-8",
    )
    operator_index = {
        anchor["operator_id"]: {
            "anchor_id": anchor["anchor_id"],
            "record_id": anchor["record_id"],
            "class_name": anchor["class_name"],
            "provider_group": anchor["provider_group"],
        }
        for anchor in anchors
    }
    index_path = output_dir / "operator_index.json"
    _write_json(index_path, operator_index)

    provider_counts: dict[str, int] = defaultdict(int)
    for anchor in anchors:
        provider_counts[str(anchor["provider_group"])] += 1
    summary = {
        "schema_version": SCHEMA_VERSION,
        "source_review_sha256": source_review_sha256,
        "source_decisions_sha256": _sha256(decisions_path),
        "source_signature_records_sha256": _sha256(signature_records_path),
        "review_rows": adjudication["review_rows_total"],
        "accepted_anchors": len(anchors),
        "unique_operator_ids": len(operator_index),
        "rejected_non_anchors": adjudication["decision_counts"].get("reject_non_anchor", 0),
        "provider_counts": dict(sorted(provider_counts.items())),
        "anchors_without_transfer_operations": sum(
            not anchor["transfer_operations"] for anchor in anchors
        ),
        "taxonomy_admission": "not_granted",
        "training_rows_emitted": 0,
    }
    summary_path = output_dir / "summary.json"
    _write_json(summary_path, summary)
    output_paths = [anchors_path, index_path, summary_path]
    ledger = {
        "schema_version": SCHEMA_VERSION,
        "inputs": {
            "review_sha256": source_review_sha256,
            "decisions_sha256": _sha256(decisions_path),
            "signature_records_sha256": _sha256(signature_records_path),
        },
        "outputs": {path.name: _sha256(path) for path in sorted(output_paths)},
    }
    _write_json(output_dir / "hash_ledger.json", ledger)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--signature-records", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = export_anchor_library(
        args.review,
        args.decisions,
        args.signature_records,
        args.output_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
