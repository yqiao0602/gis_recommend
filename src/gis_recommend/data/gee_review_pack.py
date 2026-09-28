"""Deterministic, source-disjoint review packs for GEE extraction evidence."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Iterable


STRATA = (
    "dynamic_unresolved",
    "nested_callback",
    "helper",
    "arrow_callback",
    "function_callback",
    "branch_loop",
    "io_presentation",
    "direct_chain",
)
DEFAULT_QUOTAS = {
    "dynamic_unresolved": 15,
    "nested_callback": 15,
    "helper": 20,
    "arrow_callback": 20,
    "function_callback": 20,
    "branch_loop": 15,
    "io_presentation": 15,
    "direct_chain": 30,
}
HUMAN_REVIEW_FIELDS = (
    "human_core_precision",
    "human_core_recall",
    "human_order_correct",
    "human_callback_helper_complete",
    "human_io_correct",
    "human_presentation_correct",
    "human_workflow_complete",
    "human_notes",
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_manifest_path(value: str, manifest_dir: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else manifest_dir / path


def load_manifest_records(manifest_path: Path, *, excerpt_chars: int = 12_000) -> list[dict[str, Any]]:
    """Load review candidates and bind every record to verified source bytes."""

    manifest_path = Path(manifest_path)
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid manifest JSON at line {line_number}: {exc}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"manifest line {line_number} must contain an object")
        source_path = _resolve_manifest_path(str(record.get("source_path", "")), manifest_path.parent)
        expected_hash = record.get("source_sha256")
        if not source_path.is_file():
            raise ValueError(f"source_path does not exist at line {line_number}: {source_path}")
        actual_hash = _sha256_file(source_path)
        if actual_hash != expected_hash:
            raise ValueError(
                f"source_sha256 mismatch at line {line_number}: expected {expected_hash}, got {actual_hash}"
            )

        evidence = record.get("evidence")
        if evidence is None:
            evidence_value = record.get("evidence_path")
            if not evidence_value:
                raise ValueError(f"missing evidence/evidence_path at line {line_number}")
            evidence_path = _resolve_manifest_path(str(evidence_value), manifest_path.parent)
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        if not isinstance(evidence, dict):
            raise ValueError(f"evidence must be an object at line {line_number}")
        if evidence.get("source_sha256") != expected_hash:
            raise ValueError(f"evidence source_sha256 mismatch at line {line_number}")

        source_text = source_path.read_text(encoding="utf-8", errors="replace")
        records.append({
            **record,
            "source_path": str(source_path),
            "evidence": evidence,
            "source_excerpt": source_text[:excerpt_chars],
        })
    return records


def _validate_candidate(record: dict[str, Any]) -> None:
    record_id = record.get("record_id")
    if not isinstance(record_id, str) or not record_id:
        raise ValueError("record_id must be a non-empty string")
    source_hash = record.get("source_sha256")
    if not isinstance(source_hash, str) or not _SHA256_RE.fullmatch(source_hash):
        raise ValueError(f"invalid source_sha256 for {record_id}")
    evidence = record.get("evidence")
    if not isinstance(evidence, dict):
        raise ValueError(f"missing evidence for {record_id}")
    if evidence.get("schema") != "gis_recommend.gee_source_evidence.v1":
        raise ValueError(f"unsupported evidence schema for {record_id}")
    if evidence.get("source_sha256") != source_hash:
        raise ValueError(f"evidence source_sha256 mismatch for {record_id}")


def _stratum(record: dict[str, Any]) -> str:
    evidence = record["evidence"]
    flags = set(evidence.get("quality_flags", []))
    calls = evidence.get("ordered_calls", [])
    if any(":callback:callback" in str(call.get("scope", "")) for call in calls):
        return "nested_callback"
    if any(call.get("context") == "helper_inline" for call in calls):
        return "helper"
    if "arrow_callback" in flags:
        return "arrow_callback"
    if "function_callback" in flags:
        return "function_callback"
    if flags.intersection({"branch_order_unresolved", "loop_order_unresolved"}):
        return "branch_loop"
    if evidence.get("io_contract") or evidence.get("presentation_actions"):
        return "io_presentation"
    if evidence.get("unresolved_calls") or "dynamic_callee" in flags or "recursive_helper" in flags:
        return "dynamic_unresolved"
    return "direct_chain"


def build_review_selection(
    records: Iterable[dict[str, Any]],
    *,
    quotas: dict[str, int] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    quotas = dict(DEFAULT_QUOTAS if quotas is None else quotas)
    unknown_strata = set(quotas).difference(STRATA)
    if unknown_strata:
        raise ValueError(f"unknown review strata: {sorted(unknown_strata)}")
    if any(not isinstance(value, int) or value < 0 for value in quotas.values()):
        raise ValueError("review quotas must be non-negative integers")

    materialized = list(records)
    seen_ids: set[str] = set()
    groups: dict[str, list[dict[str, Any]]] = {}
    for record in materialized:
        _validate_candidate(record)
        record_id = record["record_id"]
        if record_id in seen_ids:
            raise ValueError(f"duplicate record_id: {record_id}")
        seen_ids.add(record_id)
        groups.setdefault(record["source_sha256"], []).append(record)

    canonical: list[dict[str, Any]] = []
    for source_hash, members in sorted(groups.items()):
        ordered = sorted(members, key=lambda item: (str(item["source_path"]), item["record_id"]))
        representative = dict(ordered[0])
        representative["source_sha256"] = source_hash
        representative["observed_source_paths"] = sorted({str(item["source_path"]) for item in members})
        representative["duplicate_instance_count"] = len(members)
        representative["review_stratum"] = _stratum(representative)
        canonical.append(representative)

    by_stratum = {name: [] for name in STRATA}
    for record in canonical:
        by_stratum[record["review_stratum"]].append(record)
    for values in by_stratum.values():
        values.sort(key=lambda item: (item["source_sha256"], item["record_id"]))

    selected: list[dict[str, Any]] = []
    strata_summary: dict[str, dict[str, int]] = {}
    required_count = 0
    for name in STRATA:
        quota = quotas.get(name, 0)
        available = len(by_stratum[name])
        required = [
            record for record in by_stratum[name]
            if record.get("pilot_feature") == "required_regression"
        ]
        ordinary = [record for record in by_stratum[name] if record not in required]
        chosen = [*required, *ordinary[:quota]]
        for record in chosen:
            row = dict(record)
            row["required_regression"] = record.get("pilot_feature") == "required_regression"
            required_count += int(row["required_regression"])
            for field in HUMAN_REVIEW_FIELDS:
                row[field] = ""
            selected.append(row)
        strata_summary[name] = {
            "quota": quota,
            "available": available,
            "selected": len(chosen),
            "shortfall": max(0, quota - len(chosen)),
        }

    summary = {
        "schema": "gis_recommend.gee_review_pack_summary.v1",
        "input_record_count": len(materialized),
        "unique_source_count": len(canonical),
        "duplicate_instance_count": len(materialized) - len(canonical),
        "selected_count": len(selected),
        "required_regression_count": required_count,
        "strata": strata_summary,
        "training_admission": "not_granted",
        "human_correctness_scored": False,
    }
    return selected, summary


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _jsonl_bytes(values: Iterable[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for value in values
    ).encode("utf-8")


def _csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    base_fields = (
        "record_id",
        "review_stratum",
        "source_path",
        "source_sha256",
        "observed_source_paths",
        "duplicate_instance_count",
        "pilot_feature",
        "source_features",
        "required_regression",
        "legacy_operations",
        "evidence",
        "source_excerpt",
    )
    fields = [*base_fields, *HUMAN_REVIEW_FIELDS]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        encoded = dict(row)
        for field in ("observed_source_paths", "source_features", "legacy_operations", "evidence"):
            encoded[field] = json.dumps(encoded.get(field), ensure_ascii=False, sort_keys=True)
        writer.writerow(encoded)
    return output.getvalue().encode("utf-8")


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _validate_output_dir(output_dir: Path, forbidden_roots: Iterable[Path]) -> Path:
    resolved = Path(output_dir).resolve()
    for root in forbidden_roots:
        forbidden = Path(root).resolve()
        if resolved == forbidden or forbidden in resolved.parents:
            raise ValueError(f"forbidden output root: {forbidden}")
    return resolved


def write_review_artifacts(
    records: Iterable[dict[str, Any]],
    output_dir: Path,
    *,
    quotas: dict[str, int] | None = None,
    forbidden_roots: Iterable[Path] = (),
) -> dict[str, Any]:
    output_dir = _validate_output_dir(output_dir, forbidden_roots)
    selected, summary = build_review_selection(records, quotas=quotas)
    payloads = {
        "review.csv": _csv_bytes(selected),
        "selection.jsonl": _jsonl_bytes(selected),
        "summary.json": _json_bytes(summary),
    }
    for name, payload in payloads.items():
        _atomic_write(output_dir / name, payload)
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "artifacts": {
            name: {"sha256": _sha256_bytes(payload), "size_bytes": len(payload)}
            for name, payload in sorted(payloads.items())
        },
    }
    _atomic_write(output_dir / "hash_ledger.json", _json_bytes(ledger))
    return summary
