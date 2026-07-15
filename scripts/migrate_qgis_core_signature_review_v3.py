#!/usr/bin/env python3
"""Migrate a QGIS signature review by adding audited bounded candidates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.validate_qgis_core_signature_adjudications import validate_and_summarize


MANIFEST_SCHEMA_VERSION = "qgis_core_signature_candidate_additions_v1"
TARGET_REVIEW_SCHEMA_VERSION = "qgis_core_signature_review_v3"
AUTHORIZED_REVIEW_FIELDS = (
    "exact_candidates_json",
    "ranked_candidates_json",
    "auto_proposed_operator_id",
    "resolution_status",
    "ambiguity_reason",
)


class ReviewMigrationError(ValueError):
    pass


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _load_review(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ReviewMigrationError("source review has no CSV header")
        rows = list(reader)
    keys = [(row.get("record_id", ""), row.get("class_name", "")) for row in rows]
    if len(keys) != len(set(keys)):
        raise ReviewMigrationError("source review contains duplicate record/class keys")
    return list(reader.fieldnames), rows


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    values = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ReviewMigrationError(
                    f"invalid source decision JSON at line {line_number}: {exc}"
                ) from exc
            if not isinstance(value, dict):
                raise ReviewMigrationError(
                    f"source decision line {line_number} must be an object"
                )
            values.append(value)
    return values


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReviewMigrationError(f"invalid candidate manifest: {exc}") from exc
    if not isinstance(value, dict):
        raise ReviewMigrationError("candidate manifest must be an object")
    if value.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ReviewMigrationError("invalid candidate manifest schema version")
    if value.get("target_review_schema_version") != TARGET_REVIEW_SCHEMA_VERSION:
        raise ReviewMigrationError("invalid target review schema version")
    if not isinstance(value.get("additions"), list) or not value["additions"]:
        raise ReviewMigrationError("candidate manifest additions must be non-empty")
    return value


def _candidate_ids(row: dict[str, str]) -> set[str]:
    result = set()
    for field in ("exact_candidates_json", "ranked_candidates_json"):
        try:
            candidates = json.loads(row.get(field) or "[]")
        except json.JSONDecodeError as exc:
            raise ReviewMigrationError(
                f"invalid {field} for {row.get('record_id')} / {row.get('class_name')}"
            ) from exc
        for candidate in candidates:
            if isinstance(candidate, dict) and candidate.get("operator_id"):
                result.add(str(candidate["operator_id"]))
    return result


def _validate_hex_sha256(value: Any, field: str) -> str:
    text = str(value or "")
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text.lower()):
        raise ReviewMigrationError(f"invalid {field}")
    return text.lower()


def _validate_addition(
    addition: dict[str, Any],
    review: dict[tuple[str, str], dict[str, str]],
) -> tuple[tuple[str, str], dict[str, Any]]:
    if not isinstance(addition, dict):
        raise ReviewMigrationError("candidate addition must be an object")
    key = (str(addition.get("record_id") or ""), str(addition.get("class_name") or ""))
    if key not in review:
        raise ReviewMigrationError(f"addition key not found in source review: {key}")
    row = review[key]
    if addition.get("trace_sha256") != row.get("trace_sha256"):
        raise ReviewMigrationError(f"trace hash mismatch for addition key: {key}")

    candidate = addition.get("candidate")
    if not isinstance(candidate, dict):
        raise ReviewMigrationError(f"candidate missing for addition key: {key}")
    required = ("operator_id", "official_name", "provider_group", "score", "match_signals")
    if any(candidate.get(field) in (None, "", []) for field in required):
        raise ReviewMigrationError(f"candidate fields incomplete for addition key: {key}")
    operator_id = str(candidate["operator_id"])
    if operator_id in _candidate_ids(row):
        raise ReviewMigrationError(f"candidate already present for addition key: {key}")

    provider_group = str(candidate["provider_group"])
    source_name = str(addition.get("source_name") or "")
    if operator_id != f"{provider_group}:{source_name}":
        raise ReviewMigrationError(f"candidate operator/source name mismatch for {key}")
    _validate_hex_sha256(addition.get("source_file_sha256"), "source_file_sha256")
    if not str(addition.get("source_path") or "").strip():
        raise ReviewMigrationError(f"missing source path for addition key: {key}")

    try:
        provider_evidence = json.loads(row.get("provider_evidence_json") or "{}")
    except json.JSONDecodeError as exc:
        raise ReviewMigrationError(f"invalid provider evidence for addition key: {key}") from exc
    providers = provider_evidence.get("providers") if isinstance(provider_evidence, dict) else []
    if provider_group not in (providers or []):
        raise ReviewMigrationError(f"candidate provider absent from evidence for {key}")
    return key, candidate


def _write_review(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _migrate_decisions(
    decisions: list[dict[str, Any]],
    source_review_sha256: str,
    target_review_sha256: str,
    migration_basis: str,
) -> list[dict[str, Any]]:
    migrated = []
    for decision in decisions:
        if decision.get("source_review_sha256") != source_review_sha256:
            raise ReviewMigrationError("source decision contains a stale review hash")
        value = dict(decision)
        history = list(value.get("authority_migration_history") or [])
        history.append(
            {
                "from_review_sha256": source_review_sha256,
                "to_review_sha256": target_review_sha256,
                "target_review_schema_version": TARGET_REVIEW_SCHEMA_VERSION,
                "migration_basis": migration_basis,
            }
        )
        value["authority_migration_history"] = history
        value["source_review_sha256"] = target_review_sha256
        migrated.append(value)
    return migrated


def migrate_review_authority(
    source_review_path: str | Path,
    source_decisions_path: str | Path,
    manifest_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    source_review_path = Path(source_review_path)
    source_decisions_path = Path(source_decisions_path)
    manifest_path = Path(manifest_path)
    output_dir = Path(output_dir)

    source_review_sha256 = _sha256(source_review_path)
    source_decisions_sha256 = _sha256(source_decisions_path)
    manifest = _load_manifest(manifest_path)
    if manifest.get("source_review_sha256") != source_review_sha256:
        raise ReviewMigrationError("source review hash mismatch")
    if manifest.get("source_decisions_sha256") != source_decisions_sha256:
        raise ReviewMigrationError("source decisions hash mismatch")
    migration_basis = str(manifest.get("migration_basis") or "").strip()
    if not migration_basis:
        raise ReviewMigrationError("candidate manifest lacks migration basis")

    validate_and_summarize(source_review_path, source_decisions_path)
    fieldnames, source_rows = _load_review(source_review_path)
    review = {
        (row.get("record_id", ""), row.get("class_name", "")): row
        for row in source_rows
    }
    additions: dict[tuple[str, str], tuple[dict[str, Any], dict[str, Any]]] = {}
    for addition in manifest["additions"]:
        key, candidate = _validate_addition(addition, review)
        if key in additions:
            raise ReviewMigrationError(f"duplicate addition key: {key}")
        additions[key] = (addition, candidate)

    migrated_rows = []
    changed_keys = []
    for source_row in source_rows:
        key = (source_row.get("record_id", ""), source_row.get("class_name", ""))
        row = dict(source_row)
        if key in additions:
            _, candidate = additions[key]
            exact_candidates = json.loads(row.get("exact_candidates_json") or "[]")
            ranked_candidates = json.loads(row.get("ranked_candidates_json") or "[]")
            exact_candidates.insert(0, candidate)
            ranked_candidates.insert(0, candidate)
            row["exact_candidates_json"] = _json_compact(exact_candidates)
            row["ranked_candidates_json"] = _json_compact(ranked_candidates)
            row["auto_proposed_operator_id"] = str(candidate["operator_id"])
            row["resolution_status"] = "auto_proposed_pending_review"
            row["ambiguity_reason"] = ""
            changed_keys.append({"record_id": key[0], "class_name": key[1]})
        migrated_rows.append(row)

    output_dir.mkdir(parents=True, exist_ok=False)
    review_path = output_dir / "signature_review.csv"
    _write_review(review_path, fieldnames, migrated_rows)
    target_review_sha256 = _sha256(review_path)

    decisions = _load_jsonl(source_decisions_path)
    migrated_decisions = _migrate_decisions(
        decisions,
        source_review_sha256,
        target_review_sha256,
        migration_basis,
    )
    decisions_path = output_dir / "adjudication_decisions.jsonl"
    decisions_path.write_text(
        "".join(_json_compact(value) + "\n" for value in migrated_decisions),
        encoding="utf-8",
    )
    adjudication_summary_path = output_dir / "adjudication_summary.json"
    adjudication_summary = validate_and_summarize(
        review_path,
        decisions_path,
        adjudication_summary_path,
    )

    manifest_copy_path = output_dir / "candidate_additions.json"
    _write_json(manifest_copy_path, manifest)
    report = {
        "schema_version": TARGET_REVIEW_SCHEMA_VERSION,
        "source_review_sha256": source_review_sha256,
        "source_decisions_sha256": source_decisions_sha256,
        "target_review_sha256": target_review_sha256,
        "authorized_review_fields": list(AUTHORIZED_REVIEW_FIELDS),
        "changed_review_rows": len(changed_keys),
        "changed_keys": changed_keys,
        "migrated_decisions": len(migrated_decisions),
        "remaining_review_rows": adjudication_summary["remaining_review_rows"],
        "accepted_anchor_candidates": adjudication_summary["accepted_anchor_candidates"],
        "training_rows_emitted": 0,
    }
    report_path = output_dir / "migration_report.json"
    _write_json(report_path, report)

    migration_md_path = output_dir / "migration_from_v2.md"
    lines = [
        "# QGIS Core Signature Review v3 Migration",
        "",
        f"Source review SHA256: `{source_review_sha256}`",
        f"Target review SHA256: `{target_review_sha256}`",
        "",
        "Only the following record/class keys receive new bounded candidates:",
        "",
    ]
    for key in changed_keys:
        addition, candidate = additions[(key["record_id"], key["class_name"])]
        lines.append(
            f"- `{key['record_id']} / {key['class_name']}` -> "
            f"`{candidate['operator_id']}` from source `name()={addition['source_name']}`."
        )
    lines.extend(
        [
            "",
            "All other review fields and all existing human decision semantics are preserved.",
            "No candidate is accepted by migration and no training row is emitted.",
        ]
    )
    migration_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    output_paths = [
        review_path,
        decisions_path,
        adjudication_summary_path,
        manifest_copy_path,
        report_path,
        migration_md_path,
    ]
    ledger = {
        "schema_version": TARGET_REVIEW_SCHEMA_VERSION,
        "inputs": {
            "source_review_sha256": source_review_sha256,
            "source_decisions_sha256": source_decisions_sha256,
            "candidate_manifest_sha256": _sha256(manifest_path),
        },
        "outputs": {path.name: _sha256(path) for path in sorted(output_paths)},
    }
    _write_json(output_dir / "hash_ledger.json", ledger)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-review", type=Path, required=True)
    parser.add_argument("--source-decisions", type=Path, required=True)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = migrate_review_authority(
        args.source_review,
        args.source_decisions,
        args.candidate_manifest,
        args.output_dir,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
