#!/usr/bin/env python3
"""Build a cumulative, exclusion-only GEE source authority from JSONL manifests."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.build_gee_workflow_dag_calibration import (
    _EXPORT_RE,
    _GEE_RE,
    _SELECTION_FIELDS,
    _load_exact_join_paths,
    _stratum,
)


AUTHORITY_NAME = "source_exclusion_authority.jsonl"
SELECTION_NAME = "exclusion_selection.jsonl"
PROVENANCE_NAME = "exclusion_provenance.jsonl"
INCOMPATIBLE_NAME = "non_selector_compatible_sources.jsonl"
SUMMARY_NAME = "summary.json"
REPORT_NAME = "report.md"
HASH_LEDGER_NAME = "hash_ledger.json"
SOURCE_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
TRAINING_ADMISSION = "not_granted_exclusion_only"


@dataclass(frozen=True)
class SourceExclusionAuthorityResult:
    rows: list[dict[str, Any]]
    summary: dict[str, Any]
    input_manifests: list[dict[str, Any]]
    source_input_manifest_paths: dict[str, list[str]]


@dataclass(frozen=True)
class SelectorExclusionResult:
    selection_rows: list[dict[str, Any]]
    provenance_rows: list[dict[str, Any]]
    incompatible_rows: list[dict[str, Any]]
    authority_inputs: list[dict[str, Any]]


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_path(path: Path) -> str:
    return path.resolve().as_posix()


def _load_manifest(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"input manifest is not a file: {path}")
    content = path.read_bytes()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path} is not valid UTF-8") from exc
    if not text.strip():
        raise ValueError(f"input manifest must not be empty: {path}")

    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            raise ValueError(f"{path}:{line_number} must be a JSON object")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON at {path}:{line_number}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number} must be a JSON object")
        rows.append(row)

    metadata = {
        "path": _canonical_path(path),
        "sha256": hashlib.sha256(content).hexdigest(),
        "size_bytes": len(content),
    }
    return rows, metadata


def _source_identifiers(row: dict[str, Any], *, location: str) -> list[str]:
    identifiers: list[str] = []
    for field in ("source_path", "record_key"):
        value = row.get(field)
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{location} has invalid {field}")
        identifiers.append(value.strip())
    return identifiers


def build_source_exclusion_authority(
    input_manifest_paths: Iterable[Path],
) -> SourceExclusionAuthorityResult:
    paths = [Path(path) for path in input_manifest_paths]
    if not paths:
        raise ValueError("at least one input manifest is required")

    sources: dict[str, dict[str, set[str]]] = {}
    identifier_to_sha: dict[str, str] = {}
    input_manifests: list[dict[str, Any]] = []
    input_row_count = 0

    loaded = []
    for path in paths:
        rows, metadata = _load_manifest(path)
        loaded.append((metadata["path"], rows, metadata))

    for manifest_path, rows, metadata in sorted(loaded, key=lambda item: item[0]):
        input_manifests.append(metadata)
        for row_number, row in enumerate(rows, start=1):
            input_row_count += 1
            source_sha256 = row.get("source_sha256")
            if not isinstance(
                source_sha256, str
            ) or not SOURCE_SHA256_PATTERN.fullmatch(source_sha256):
                raise ValueError(
                    f"invalid source_sha256 at {manifest_path}:{row_number}"
                )
            identifiers = _source_identifiers(
                row, location=f"{manifest_path}:{row_number}"
            )
            for identifier in identifiers:
                prior_sha256 = identifier_to_sha.get(identifier)
                if prior_sha256 is not None and prior_sha256 != source_sha256:
                    raise ValueError(
                        f"source path or record key {identifier!r} maps to different "
                        "source SHA256 values"
                    )
                identifier_to_sha[identifier] = source_sha256

            source = sources.setdefault(
                source_sha256,
                {"source_paths": set(), "input_manifest_paths": set()},
            )
            source["source_paths"].update(identifiers)
            source["input_manifest_paths"].add(manifest_path)

    rows = [
        {
            "schema": "gis_recommend.gee_source_exclusion.v1",
            "source_sha256": source_sha256,
            "source_paths": sorted(values["source_paths"]),
            "input_manifest_paths": sorted(values["input_manifest_paths"]),
        }
        for source_sha256, values in sorted(sources.items())
    ]
    summary = {
        "schema": "gis_recommend.gee_source_exclusion_summary.v1",
        "input_manifest_count": len(paths),
        "input_row_count": input_row_count,
        "unique_source_count": len(rows),
        "duplicate_row_count": input_row_count - len(rows),
        "training_admission": TRAINING_ADMISSION,
        "training_rows_emitted": 0,
    }
    return SourceExclusionAuthorityResult(
        rows=rows,
        summary=summary,
        input_manifests=input_manifests,
        source_input_manifest_paths={
            source_sha256: sorted(values["input_manifest_paths"])
            for source_sha256, values in sorted(sources.items())
        },
    )


def _load_requested_canonical_rows(
    canonical_manifest: Path, requested_sha256: set[str]
) -> dict[str, dict[str, Any]]:
    matches: dict[str, list[dict[str, Any]]] = {
        source_sha256: [] for source_sha256 in requested_sha256
    }
    try:
        handle = Path(canonical_manifest).open("r", encoding="utf-8-sig")
    except OSError as exc:
        raise ValueError(
            f"cannot read canonical manifest: {canonical_manifest}"
        ) from exc
    with handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid JSON at canonical manifest line {line_number}"
                ) from exc
            if not isinstance(row, dict):
                raise ValueError(
                    f"canonical manifest line {line_number} must be a JSON object"
                )
            source_sha256 = row.get("source_sha256")
            if not isinstance(
                source_sha256, str
            ) or not SOURCE_SHA256_PATTERN.fullmatch(source_sha256):
                raise ValueError(
                    f"canonical manifest line {line_number} has invalid source_sha256"
                )
            if source_sha256 in matches:
                matches[source_sha256].append(row)

    resolved: dict[str, dict[str, Any]] = {}
    for source_sha256, rows in sorted(matches.items()):
        if len(rows) != 1:
            raise ValueError(
                f"requested source_sha256 {source_sha256} did not uniquely backjoin "
                f"to canonical authority: matches={len(rows)}"
            )
        resolved[source_sha256] = rows[0]
    return resolved


def _canonical_exact_paths(row: dict[str, Any], relative_path: str) -> set[str]:
    instances = row.get("instances")
    if not isinstance(instances, list):
        return {relative_path}
    return {
        item["source_path"]
        for item in instances
        if isinstance(item, dict)
        and isinstance(item.get("source_path"), str)
        and item["source_path"]
    }


def _artifact_input(path: Path, *, kind: str) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"{kind} is not a file: {path}")
    return {
        "kind": kind,
        "path": _canonical_path(path),
        "sha256": _file_sha256(path),
        "size_bytes": path.stat().st_size,
    }


def build_selector_exclusion(
    authority: SourceExclusionAuthorityResult,
    *,
    canonical_manifest: Path,
    join_ledger: Path,
    source_root: Path,
) -> SelectorExclusionResult:
    """Backjoin requested hashes and prove every selector exclusion field."""

    source_root = Path(source_root)
    if not source_root.is_dir():
        raise ValueError(f"source_root is not a directory: {source_root}")
    resolved_source_root = source_root.resolve()
    requested_sha256 = {row["source_sha256"] for row in authority.rows}
    canonical_rows = _load_requested_canonical_rows(
        canonical_manifest, requested_sha256
    )
    try:
        exact_join_paths = _load_exact_join_paths(Path(join_ledger))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load exact join ledger: {join_ledger}") from exc

    canonical_input = _artifact_input(canonical_manifest, kind="canonical_manifest")
    join_input = _artifact_input(join_ledger, kind="exact_join_ledger")
    selection_rows: list[dict[str, Any]] = []
    provenance_rows: list[dict[str, Any]] = []
    incompatible_rows: list[dict[str, Any]] = []

    for source_sha256 in sorted(requested_sha256):
        canonical_row = canonical_rows[source_sha256]
        relative_path = canonical_row.get("source_path")
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise ValueError(
                f"canonical authority for {source_sha256} lacks source_path"
            )
        relative_path = relative_path.strip()
        if not _canonical_exact_paths(canonical_row, relative_path).intersection(
            exact_join_paths
        ):
            raise ValueError(
                f"requested source_sha256 {source_sha256} lacks exact facts support"
            )

        source_path = (resolved_source_root / relative_path).resolve()
        if not source_path.is_relative_to(resolved_source_root):
            raise ValueError(
                f"canonical source path escapes source_root: {relative_path}"
            )
        if not source_path.is_file():
            raise ValueError(f"source path does not exist: {source_path}")
        source_bytes = source_path.read_bytes()
        size_bytes = len(source_bytes)
        actual_sha256 = hashlib.sha256(source_bytes).hexdigest()
        if actual_sha256 != source_sha256:
            raise ValueError(
                f"source_sha256 mismatch for {source_path}: expected "
                f"{source_sha256}, got {actual_sha256}"
            )
        source_text = source_bytes.decode("utf-8", errors="replace")
        provenance_rows.append(
            {
                "schema": "gis_recommend.gee_source_exclusion_provenance.v1",
                "source_sha256": source_sha256,
                "input_artifacts": [
                    {"kind": "source_request_manifest", "path": path}
                    for path in authority.source_input_manifest_paths[source_sha256]
                ],
                "authority_artifacts": [
                    {
                        "kind": "canonical_manifest",
                        "path": canonical_input["path"],
                    },
                    {"kind": "exact_join_ledger", "path": join_input["path"]},
                    {"kind": "source_file", "path": source_path.as_posix()},
                ],
            }
        )

        incompatible_reasons = []
        if not 200 <= size_bytes <= 100_000:
            incompatible_reasons.append("source_size_out_of_range")
        if not _GEE_RE.search(source_text):
            incompatible_reasons.append("missing_gee_signal")
        if not _EXPORT_RE.search(source_text):
            incompatible_reasons.append("missing_export_sink")
        if incompatible_reasons:
            incompatible_rows.append(
                {
                    "schema": "gis_recommend.gee_source_exclusion_incompatible.v1",
                    "source_path": relative_path,
                    "source_sha256": source_sha256,
                    "selector_compatible": False,
                    "reasons": incompatible_reasons,
                }
            )
            continue

        record_key = canonical_row.get("record_key", relative_path)
        if not isinstance(record_key, str) or not record_key.strip():
            raise ValueError(
                f"canonical authority for {source_sha256} has invalid record_key"
            )

        selection_row = {
            "record_key": record_key.strip(),
            "source_path": relative_path,
            "source_sha256": source_sha256,
            "size_bytes": size_bytes,
            "facts_supported": True,
            "calibration_stratum": _stratum(source_text),
        }
        if tuple(selection_row) != _SELECTION_FIELDS:
            raise AssertionError("selector exclusion field order drifted")
        selection_rows.append(selection_row)

    return SelectorExclusionResult(
        selection_rows=selection_rows,
        provenance_rows=provenance_rows,
        incompatible_rows=incompatible_rows,
        authority_inputs=[
            canonical_input,
            join_input,
            {"kind": "source_root", "path": resolved_source_root.as_posix()},
        ],
    )


def _canonical_jsonl(rows: Iterable[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for row in rows
    ).encode("utf-8")


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _report(summary: dict[str, Any]) -> bytes:
    return (
        "# GEE Source Exclusion Authority\n\n"
        f"- input manifests: `{summary['input_manifest_count']}`\n"
        f"- input rows: `{summary['input_row_count']}`\n"
        f"- unique sources: `{summary['unique_source_count']}`\n"
        f"- duplicate rows: `{summary['duplicate_row_count']}`\n"
        f"- selector-compatible sources: "
        f"`{summary['selector_compatible_source_count']}`\n"
        f"- non-selector-compatible sources: "
        f"`{summary['non_selector_compatible_source_count']}`\n"
        f"- non-selector-compatible reasons: "
        f"`{json.dumps(summary['non_selector_compatible_reasons'], sort_keys=True)}`\n"
        f"- training_admission: `{summary['training_admission']}`\n"
        f"- training rows emitted: `{summary['training_rows_emitted']}`\n"
    ).encode("utf-8")


def write_source_exclusion_authority(
    result: SourceExclusionAuthorityResult,
    selector_exclusion: SelectorExclusionResult,
    *,
    output_dir: Path,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")

    reason_counts = Counter(
        reason
        for row in selector_exclusion.incompatible_rows
        for reason in row["reasons"]
    )
    summary = {
        **result.summary,
        "selector_compatible_source_count": len(selector_exclusion.selection_rows),
        "non_selector_compatible_source_count": len(
            selector_exclusion.incompatible_rows
        ),
        "non_selector_compatible_reasons": dict(sorted(reason_counts.items())),
    }
    artifacts = {
        AUTHORITY_NAME: _canonical_jsonl(result.rows),
        SELECTION_NAME: _canonical_jsonl(selector_exclusion.selection_rows),
        PROVENANCE_NAME: _canonical_jsonl(selector_exclusion.provenance_rows),
        INCOMPATIBLE_NAME: _canonical_jsonl(selector_exclusion.incompatible_rows),
        SUMMARY_NAME: _canonical_json(summary),
        REPORT_NAME: _report(summary),
    }
    hash_ledger = {
        "schema": "gis_recommend.gee_source_exclusion_hash_ledger.v1",
        "input_manifests": result.input_manifests,
        "authority_inputs": selector_exclusion.authority_inputs,
        "artifacts": {
            name: {
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
            }
            for name, content in sorted(artifacts.items())
        },
        "training_admission": TRAINING_ADMISSION,
        "training_rows_emitted": 0,
    }
    artifacts[HASH_LEDGER_NAME] = _canonical_json(hash_ledger)

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent)
    )
    try:
        for name, content in artifacts.items():
            (staging / name).write_bytes(content)
        os.replace(staging, output_dir)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return hash_ledger


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-manifest", type=Path, action="append", required=True)
    parser.add_argument("--canonical-manifest", type=Path, required=True)
    parser.add_argument("--join-ledger", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    result = build_source_exclusion_authority(args.input_manifest)
    selector_exclusion = build_selector_exclusion(
        result,
        canonical_manifest=args.canonical_manifest,
        join_ledger=args.join_ledger,
        source_root=args.source_root,
    )
    hash_ledger = write_source_exclusion_authority(
        result, selector_exclusion, output_dir=args.output_dir
    )
    summary = json.loads((args.output_dir / SUMMARY_NAME).read_text(encoding="utf-8"))
    payload = {"summary": summary, "hash_ledger": hash_ledger}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
