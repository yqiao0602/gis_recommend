#!/usr/bin/env python3
"""Extract versioned GEE call evidence from source-bound ESTree AST files."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable

from gis_recommend.data.gee_source_extractor import EXTRACTOR_VERSION, extract_gee_source_evidence


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _jsonl_bytes(values: Iterable[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for value in values
    ).encode("utf-8")


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


def _validated_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    materialized = list(records)
    seen_ids: set[str] = set()
    validated: list[dict[str, Any]] = []
    for record in materialized:
        record_id = record.get("record_id")
        if not isinstance(record_id, str) or not record_id:
            raise ValueError("record_id must be a non-empty string")
        if record_id in seen_ids:
            raise ValueError(f"duplicate record_id: {record_id}")
        seen_ids.add(record_id)
        source_path = Path(str(record.get("source_path", "")))
        ast_path = Path(str(record.get("ast_path", "")))
        if not source_path.is_file():
            raise ValueError(f"source_path does not exist for {record_id}: {source_path}")
        if not ast_path.is_file():
            raise ValueError(f"ast_path does not exist for {record_id}: {ast_path}")
        actual_hash = _sha256(source_path)
        if actual_hash != record.get("source_sha256"):
            raise ValueError(
                f"source_sha256 mismatch for {record_id}: expected {record.get('source_sha256')}, got {actual_hash}"
            )
        validated.append({**record, "source_path": str(source_path), "ast_path": str(ast_path)})
    return validated


def _validate_output_dir(output_dir: Path, forbidden_roots: Iterable[Path]) -> Path:
    resolved = Path(output_dir).resolve()
    for root in forbidden_roots:
        forbidden = Path(root).resolve()
        if resolved == forbidden or forbidden in resolved.parents:
            raise ValueError(f"forbidden output root: {forbidden}")
    return resolved


def build_evidence_manifest(
    records: Iterable[dict[str, Any]],
    output_dir: Path,
    *,
    forbidden_roots: Iterable[Path] = (),
) -> dict[str, Any]:
    validated = _validated_records(records)
    output_dir = _validate_output_dir(output_dir, forbidden_roots)
    evidence_payloads: dict[str, bytes] = {}
    manifest_records: list[dict[str, Any]] = []

    for record in sorted(validated, key=lambda item: item["record_id"]):
        ast = json.loads(Path(record["ast_path"]).read_text(encoding="utf-8"))
        evidence = extract_gee_source_evidence(
            ast,
            source_path=record["source_path"],
            source_sha256=record["source_sha256"],
        ).to_dict()
        record_suffix = hashlib.sha256(record["record_id"].encode("utf-8")).hexdigest()[:8]
        filename = f"{record['source_sha256'][:16]}_{record_suffix}.json"
        relative_path = f"evidence/{filename}"
        evidence_payloads[relative_path] = _json_bytes(evidence)
        manifest_record = {
            "record_id": record["record_id"],
            "source_path": record["source_path"],
            "source_sha256": record["source_sha256"],
            "ast_path": record["ast_path"],
            "evidence_path": relative_path,
            "legacy_operations": record.get("legacy_operations", []),
        }
        for key in ("pilot_feature", "source_features"):
            if key in record:
                manifest_record[key] = record[key]
        manifest_records.append(manifest_record)

    summary = {
        "schema": "gis_recommend.gee_evidence_manifest_summary.v1",
        "record_count": len(manifest_records),
        "unique_source_count": len({record["source_sha256"] for record in manifest_records}),
        "extractor_version": EXTRACTOR_VERSION,
        "training_admission": "not_granted",
    }
    payloads = {
        **evidence_payloads,
        "manifest.jsonl": _jsonl_bytes(manifest_records),
        "summary.json": _json_bytes(summary),
    }
    for relative_path, payload in payloads.items():
        _atomic_write(output_dir / relative_path, payload)
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "artifacts": {
            name: {"sha256": hashlib.sha256(payload).hexdigest(), "size_bytes": len(payload)}
            for name, payload in sorted(payloads.items())
        },
    }
    _atomic_write(output_dir / "hash_ledger.json", _json_bytes(ledger))
    return summary


def _load_input_manifest(path: Path) -> list[dict[str, Any]]:
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"manifest line {line_number} must contain an object")
        for key in ("source_path", "ast_path"):
            candidate = Path(str(value.get(key, "")))
            if not candidate.is_absolute():
                value[key] = str(path.parent / candidate)
        records.append(value)
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--forbidden-root", type=Path, action="append", default=[])
    args = parser.parse_args(argv)
    summary = build_evidence_manifest(
        _load_input_manifest(args.manifest),
        args.output_dir,
        forbidden_roots=args.forbidden_root,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
