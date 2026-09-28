#!/usr/bin/env python3
"""Build a fixed source-disjoint calibration for complete GEE output DAGs."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Iterable

from gis_recommend.data.gee_source_extractor import extract_gee_source_evidence
from gis_recommend.data.gee_workflow_dag_gate import build_output_workflow_dags


DEFAULT_QUOTAS = {
    "linear_export": 30,
    "helper_export": 10,
    "control_flow_export": 10,
}
_SELECTION_FIELDS = (
    "record_key",
    "source_path",
    "source_sha256",
    "size_bytes",
    "facts_supported",
    "calibration_stratum",
)
_SELECTION_FIELD_SET = frozenset(_SELECTION_FIELDS)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_EXPORT_RE = re.compile(r"\bExport\.(?:image|table|video|map)\.[A-Za-z_$][\w$]*\s*\(")
_GEE_RE = re.compile(r"\bee\.[A-Za-z_$][\w$]*")
_HELPER_RE = re.compile(
    r"(?:^|[;{}\n])\s*(?:function\s+[A-Za-z_$][\w$]*\s*\(|(?:var|let|const)\s+[A-Za-z_$][\w$]*\s*=\s*(?:function\b|[^;\n]*=>))"
)
_CONTROL_FLOW_RE = re.compile(r"\b(?:if|for|switch|try|while)\s*(?:\(|\{)")


def _stratum(source_text: str) -> str:
    if _CONTROL_FLOW_RE.search(source_text):
        return "control_flow_export"
    if _HELPER_RE.search(source_text):
        return "helper_export"
    return "linear_export"


def select_calibration_candidates(
    records: Iterable[dict[str, Any]],
    *,
    quotas: dict[str, int] | None = None,
    exclude_source_sha256: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """Select deterministic high-evidence exports without retaining source text."""

    quotas = dict(DEFAULT_QUOTAS if quotas is None else quotas)
    if set(quotas) != set(DEFAULT_QUOTAS):
        raise ValueError(f"quotas must contain exactly {sorted(DEFAULT_QUOTAS)}")
    if any(not isinstance(value, int) or value < 0 for value in quotas.values()):
        raise ValueError("quota values must be non-negative integers")
    excluded = set(exclude_source_sha256)
    if any(
        not isinstance(source_hash, str) or not _SHA256_RE.fullmatch(source_hash)
        for source_hash in excluded
    ):
        raise ValueError(
            "excluded source SHA256 values must be lowercase SHA256 strings"
        )

    materialized: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    for record in records:
        source_hash = record.get("source_sha256")
        if not isinstance(source_hash, str) or not _SHA256_RE.fullmatch(source_hash):
            raise ValueError("source_sha256 must be a lowercase 64-character SHA256")
        if source_hash in seen_hashes:
            raise ValueError(f"duplicate source_sha256: {source_hash}")
        seen_hashes.add(source_hash)
        materialized.append(record)

    buckets: dict[str, list[dict[str, Any]]] = {name: [] for name in DEFAULT_QUOTAS}
    for record in sorted(materialized, key=lambda item: item["source_sha256"]):
        if record["source_sha256"] in excluded:
            continue
        source_text = record.get("source_text")
        if not record.get("facts_supported") or not isinstance(source_text, str):
            continue
        size_bytes = record.get("size_bytes")
        if not isinstance(size_bytes, int) or not 200 <= size_bytes <= 100_000:
            continue
        if not _EXPORT_RE.search(source_text) or not _GEE_RE.search(source_text):
            continue
        stratum = _stratum(source_text)
        row = {key: value for key, value in record.items() if key != "source_text"}
        row["calibration_stratum"] = stratum
        buckets[stratum].append(row)

    selected: list[dict[str, Any]] = []
    for stratum in DEFAULT_QUOTAS:
        selected.extend(buckets[stratum][: quotas[stratum]])
    return selected


def _validate_selected_quotas(
    selected: Iterable[dict[str, Any]], quotas: dict[str, int]
) -> None:
    """Require an exact, source-disjoint selection before AST parsing begins."""

    if set(quotas) != set(DEFAULT_QUOTAS):
        raise ValueError(f"quotas must contain exactly {sorted(DEFAULT_QUOTAS)}")
    if any(not isinstance(value, int) or value < 0 for value in quotas.values()):
        raise ValueError("quota values must be non-negative integers")
    rows = list(selected)
    source_hashes = [row.get("source_sha256") for row in rows]
    if any(
        not isinstance(source_hash, str) or not _SHA256_RE.fullmatch(source_hash)
        for source_hash in source_hashes
    ) or len(source_hashes) != len(set(source_hashes)):
        raise ValueError(
            "selected source SHA256 values must be unique lowercase SHA256 strings"
        )
    actual = Counter(row.get("calibration_stratum") for row in rows)
    expected = Counter(quotas)
    if actual != expected:
        raise ValueError(
            f"exact selection quotas required before parsing: expected {dict(expected)}, "
            f"got {dict(actual)}"
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_verified_source(
    source_path: Path,
    destination: Path,
    *,
    expected_size: int,
    expected_hash: str,
) -> None:
    digest = hashlib.sha256()
    actual_size = 0
    with source_path.open("rb") as source, destination.open("wb") as target:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            target.write(chunk)
            digest.update(chunk)
            actual_size += len(chunk)
        target.flush()
        os.fsync(target.fileno())
    actual_hash = digest.hexdigest()
    if actual_size != expected_size or actual_hash != expected_hash:
        raise ValueError(
            f"source identity changed during replay for {source_path}: "
            f"expected size/hash {expected_size}/{expected_hash}, "
            f"got {actual_size}/{actual_hash}"
        )


def _stable_parser_diagnostics(
    diagnostics: str,
    *,
    parser_source_path: Path,
    stable_source_path: str,
    ast_temp_path: Path,
    stable_ast_path: str,
) -> str:
    replacements = (
        (str(parser_source_path), stable_source_path),
        (parser_source_path.as_posix(), stable_source_path),
        (str(ast_temp_path), stable_ast_path),
        (ast_temp_path.as_posix(), stable_ast_path),
    )
    for temporary_path, stable_path in replacements:
        diagnostics = diagnostics.replace(temporary_path, stable_path)
    return diagnostics[-2000:]


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _jsonl_bytes(values: Iterable[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for value in values
    ).encode("utf-8")


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _load_exact_join_paths(path: Path) -> set[str]:
    exact: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(
                    f"join ledger line {line_number} must contain an object"
                )
            if row.get("join_status") == "authoritative_exact_batch_join":
                source_path = row.get("source_path")
                if isinstance(source_path, str) and source_path:
                    exact.add(source_path)
    return exact


def _select_authority_candidates(
    canonical_manifest: Path,
    source_root: Path,
    exact_join_paths: set[str],
    *,
    quotas: dict[str, int],
    exclude_source_sha256: Iterable[str] = (),
) -> list[dict[str, Any]]:
    if set(quotas) != set(DEFAULT_QUOTAS):
        raise ValueError(f"quotas must contain exactly {sorted(DEFAULT_QUOTAS)}")
    if any(not isinstance(value, int) or value < 0 for value in quotas.values()):
        raise ValueError("quota values must be non-negative integers")
    excluded = set(exclude_source_sha256)
    if any(
        not isinstance(source_hash, str) or not _SHA256_RE.fullmatch(source_hash)
        for source_hash in excluded
    ):
        raise ValueError(
            "excluded source SHA256 values must be lowercase SHA256 strings"
        )

    buckets: dict[str, list[dict[str, Any]]] = {name: [] for name in DEFAULT_QUOTAS}
    resolved_source_root = source_root.resolve()
    previous_hash = ""

    def quotas_filled() -> bool:
        return all(len(buckets[name]) >= quotas[name] for name in DEFAULT_QUOTAS)

    if quotas_filled():
        return []
    with canonical_manifest.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(
                    f"canonical manifest line {line_number} must contain an object"
                )
            relative_path = row.get("source_path")
            if not isinstance(relative_path, str) or not relative_path:
                raise ValueError(
                    f"canonical manifest line {line_number} lacks source_path"
                )
            instances = row.get("instances")
            instance_paths = (
                {
                    item.get("source_path")
                    for item in instances
                    if isinstance(item, dict)
                    and isinstance(item.get("source_path"), str)
                }
                if isinstance(instances, list)
                else {relative_path}
            )
            facts_supported = bool(instance_paths.intersection(exact_join_paths))
            if not facts_supported:
                continue
            expected_hash = row.get("source_sha256")
            if not isinstance(expected_hash, str) or not _SHA256_RE.fullmatch(
                expected_hash
            ):
                raise ValueError(
                    f"canonical manifest line {line_number} has invalid source_sha256"
                )
            if expected_hash < previous_hash:
                raise ValueError("canonical manifest must be sorted by source_sha256")
            previous_hash = expected_hash
            if expected_hash in excluded:
                continue
            source_path = (source_root / relative_path).resolve()
            if not source_path.is_relative_to(resolved_source_root):
                raise ValueError(
                    f"canonical source path escapes source_root: {relative_path}"
                )
            if not source_path.is_file():
                raise ValueError(f"source path does not exist: {source_path}")
            source_bytes = source_path.read_bytes()
            size_bytes = len(source_bytes)
            if not 200 <= size_bytes <= 100_000:
                continue
            actual_hash = hashlib.sha256(source_bytes).hexdigest()
            if actual_hash != expected_hash:
                raise ValueError(
                    f"source_sha256 mismatch for {source_path}: expected {expected_hash}, got {actual_hash}"
                )
            source_text = source_bytes.decode("utf-8", errors="replace")
            if not _EXPORT_RE.search(source_text) or not _GEE_RE.search(source_text):
                continue
            stratum = _stratum(source_text)
            if len(buckets[stratum]) >= quotas[stratum]:
                continue
            buckets[stratum].append(
                {
                    "record_key": row.get("record_key", relative_path),
                    "source_path": relative_path,
                    "source_sha256": actual_hash,
                    "size_bytes": size_bytes,
                    "facts_supported": True,
                    "calibration_stratum": stratum,
                }
            )
            if quotas_filled():
                break

    selected = [record for stratum in DEFAULT_QUOTAS for record in buckets[stratum]]
    _validate_selected_quotas(selected, quotas)
    return selected


def _load_fixed_selection_records(
    selection_manifest: Path,
    source_root: Path,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    resolved_source_root = source_root.resolve()
    with selection_manifest.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(
                    f"selection manifest line {line_number} must contain an object"
                )

            missing_fields = [field for field in _SELECTION_FIELDS if field not in row]
            unknown_fields = sorted(set(row) - _SELECTION_FIELD_SET)
            if missing_fields or unknown_fields:
                details: list[str] = []
                if missing_fields:
                    details.append(f"missing fields {missing_fields}")
                if unknown_fields:
                    details.append(f"unknown fields {unknown_fields}")
                raise ValueError(
                    f"selection manifest line {line_number} schema mismatch: {'; '.join(details)}"
                )

            record_key = row["record_key"]
            if not isinstance(record_key, str) or not record_key.strip():
                raise ValueError(
                    f"selection manifest line {line_number} record_key must be a non-empty string"
                )

            source_hash = row.get("source_sha256")
            if not isinstance(source_hash, str) or not _SHA256_RE.fullmatch(
                source_hash
            ):
                raise ValueError(
                    f"selection manifest line {line_number} source_sha256 must be a "
                    "lowercase 64-character SHA256"
                )
            if source_hash in seen_hashes:
                raise ValueError(f"duplicate source_sha256: {source_hash}")
            seen_hashes.add(source_hash)

            relative_path = row.get("source_path")
            if not isinstance(relative_path, str) or not relative_path.strip():
                raise ValueError(
                    f"selection manifest line {line_number} lacks source_path"
                )
            source_path = (resolved_source_root / relative_path).resolve()
            if not source_path.is_relative_to(resolved_source_root):
                raise ValueError(
                    f"selection manifest line {line_number} source_path must be confined under source_root"
                )

            if row.get("facts_supported") is not True:
                raise ValueError(
                    f"selection manifest line {line_number} facts_supported must be true"
                )
            stratum = row.get("calibration_stratum")
            if not isinstance(stratum, str) or stratum not in DEFAULT_QUOTAS:
                raise ValueError(
                    f"selection manifest line {line_number} calibration_stratum must be one of "
                    f"{sorted(DEFAULT_QUOTAS)}"
                )
            expected_size = row.get("size_bytes")
            if type(expected_size) is not int:
                raise ValueError(
                    f"selection manifest line {line_number} size_bytes must be an integer"
                )
            if not 200 <= expected_size <= 100_000:
                raise ValueError(
                    f"selection manifest line {line_number} size_bytes must be between 200 and 100000"
                )
            if not source_path.is_file():
                raise ValueError(f"source path does not exist: {source_path}")

            actual_size = source_path.stat().st_size
            if actual_size != expected_size:
                raise ValueError(
                    f"size_bytes mismatch for {source_path}: expected {expected_size}, got {actual_size}"
                )
            actual_hash = _sha256(source_path)
            if actual_hash != source_hash:
                raise ValueError(
                    f"source_sha256 mismatch for {source_path}: expected {source_hash}, got {actual_hash}"
                )

            record = {field: row[field] for field in _SELECTION_FIELDS}
            record["_resolved_source_path"] = source_path
            records.append(record)
    return records


def _validate_input_mode(
    canonical_manifest: Path | None,
    join_ledger: Path | None,
    selection_manifest: Path | None,
) -> None:
    if selection_manifest is not None:
        return
    if canonical_manifest is None or join_ledger is None:
        raise ValueError(
            "canonical_manifest and join_ledger are both required when selection_manifest is absent"
        )


def _ast_replay_ledger(
    ast_replay_dir: Path, selected: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    digest = hashlib.sha256()
    file_count = 0
    for record in sorted(selected, key=lambda row: row["source_sha256"]):
        name = f"{record['source_sha256']}.json"
        path = ast_replay_dir / name
        digest.update(name.encode("utf-8") + b"\0")
        if path.is_file():
            digest.update(bytes.fromhex(_sha256(path)))
            file_count += 1
        else:
            digest.update(b"missing")
        digest.update(b"\n")
    return {
        # The content-addressed aggregate is the authority.  A physical replay
        # directory differs between A/B runs and must not make the ledger differ.
        "path": "ast/",
        "file_count": file_count,
        "aggregate_sha256": digest.hexdigest(),
    }


def build_calibration(
    *,
    canonical_manifest: Path | None,
    join_ledger: Path | None,
    source_root: Path,
    parser_path: Path,
    output_dir: Path,
    selection_manifest: Path | None = None,
    exclude_selection_manifest: Path | None = None,
    ast_replay_dir: Path | None = None,
    node_executable: str = "node",
    quotas: dict[str, int] | None = None,
) -> dict[str, Any]:
    _validate_input_mode(canonical_manifest, join_ledger, selection_manifest)
    if selection_manifest is not None and exclude_selection_manifest is not None:
        raise ValueError(
            "exclude_selection_manifest is only valid in full authority mode"
        )
    if ast_replay_dir is not None and selection_manifest is None:
        raise ValueError("ast_replay_dir requires a fixed selection_manifest")
    if ast_replay_dir is not None and not ast_replay_dir.is_dir():
        raise ValueError(f"ast_replay_dir does not exist: {ast_replay_dir}")
    excluded_source_sha256: set[str] = set()
    if selection_manifest is not None:
        records = _load_fixed_selection_records(selection_manifest, source_root)
        selected = [
            {field: row[field] for field in _SELECTION_FIELDS} for row in records
        ]
        parse_source_paths = [row["_resolved_source_path"] for row in records]
    else:
        assert canonical_manifest is not None and join_ledger is not None
        effective_quotas = dict(DEFAULT_QUOTAS if quotas is None else quotas)
        if exclude_selection_manifest is not None:
            excluded_source_sha256 = {
                row["source_sha256"]
                for row in _load_fixed_selection_records(
                    exclude_selection_manifest,
                    source_root,
                )
            }
        exact_join_paths = _load_exact_join_paths(join_ledger)
        selected = _select_authority_candidates(
            canonical_manifest,
            source_root,
            exact_join_paths,
            quotas=effective_quotas,
            exclude_source_sha256=excluded_source_sha256,
        )
        parse_source_paths = [source_root / row["source_path"] for row in selected]

    ast_dir = output_dir / "ast"
    ast_dir.mkdir(parents=True, exist_ok=True)
    workflow_rows: list[dict[str, Any]] = []
    parse_failures: list[dict[str, Any]] = []
    for record, source_path in zip(selected, parse_source_paths, strict=True):
        ast_path = ast_dir / f"{record['source_sha256']}.json"
        source_temp_path: Path | None = None
        try:
            parser_source_path = source_path
            if selection_manifest is not None and ast_replay_dir is None:
                with tempfile.NamedTemporaryFile(
                    prefix="gee-calibration-source-",
                    suffix=source_path.suffix or ".txt",
                    delete=False,
                ) as handle:
                    source_temp_path = Path(handle.name)
                _copy_verified_source(
                    source_path,
                    source_temp_path,
                    expected_size=record["size_bytes"],
                    expected_hash=record["source_sha256"],
                )
                parser_source_path = source_temp_path

            evidence: dict[str, Any] | None = None
            dag_result = None
            parser_stderr = ""
            if ast_replay_dir is not None:
                replay_path = ast_replay_dir / f"{record['source_sha256']}.json"
                try:
                    ast_bytes = replay_path.read_bytes()
                    ast = json.loads(ast_bytes.decode("utf-8"))
                    if (
                        not isinstance(ast, dict)
                        or ast.get("type") != "Program"
                        or not isinstance(ast.get("body"), list)
                    ):
                        raise ValueError(
                            "invalid AST root: expected an object with type 'Program' and list body"
                        )
                    evidence = extract_gee_source_evidence(
                        ast,
                        source_path=str(source_path),
                        source_sha256=record["source_sha256"],
                    ).to_dict()
                    dag_result = build_output_workflow_dags(
                        ast,
                        evidence["ordered_calls"],
                    )
                    _atomic_write(ast_path, ast_bytes)
                except Exception as exc:
                    evidence = None
                    dag_result = None
                    error_detail = (
                        "replay AST file is missing"
                        if isinstance(exc, FileNotFoundError)
                        else str(exc)
                    )
                    diagnostics = (
                        f"AST replay failure for ast/{replay_path.name}: "
                        f"{type(exc).__name__}: {error_detail}"
                    )
                    parser_stderr = _stable_parser_diagnostics(
                        diagnostics,
                        parser_source_path=replay_path,
                        stable_source_path=f"ast/{replay_path.name}",
                        ast_temp_path=replay_path,
                        stable_ast_path=f"ast/{replay_path.name}",
                    )
            else:
                with tempfile.TemporaryDirectory(
                    dir=ast_dir, prefix=f".{record['source_sha256']}-"
                ) as ast_temp_dir:
                    ast_temp_path = Path(ast_temp_dir) / "ast.json"
                    stable_ast_path = str(Path("ast") / ast_path.name)
                    process = subprocess.run(
                        [
                            node_executable,
                            str(parser_path),
                            str(parser_source_path),
                            str(ast_temp_path),
                        ],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    diagnostics = process.stderr
                    if process.returncode == 0 and ast_temp_path.is_file():
                        try:
                            ast = json.loads(ast_temp_path.read_text(encoding="utf-8"))
                        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                            diagnostics += f"\ninvalid AST JSON: {exc}"
                        else:
                            if (
                                not isinstance(ast, dict)
                                or ast.get("type") != "Program"
                                or not isinstance(ast.get("body"), list)
                            ):
                                diagnostics += "\ninvalid AST root: expected an object with type 'Program' and list body"
                            else:
                                try:
                                    evidence = extract_gee_source_evidence(
                                        ast,
                                        source_path=str(source_path),
                                        source_sha256=record["source_sha256"],
                                    ).to_dict()
                                    dag_result = build_output_workflow_dags(
                                        ast,
                                        evidence["ordered_calls"],
                                    )
                                    os.replace(ast_temp_path, ast_path)
                                except Exception as exc:
                                    evidence = None
                                    dag_result = None
                                    diagnostics += f"\nAST processing failure: {type(exc).__name__}: {exc}"
                    parser_stderr = _stable_parser_diagnostics(
                        diagnostics,
                        parser_source_path=parser_source_path,
                        stable_source_path=record["source_path"],
                        ast_temp_path=ast_temp_path,
                        stable_ast_path=stable_ast_path,
                    )

            if evidence is None or dag_result is None:
                parse_failures.append(
                    {
                        **record,
                        "parse_status": "fail_closed",
                        "fail_closed_reason": "ast_parse_failure",
                        "parser_stderr": parser_stderr,
                    }
                )
                continue
        finally:
            if source_temp_path is not None and source_temp_path.exists():
                source_temp_path.unlink()
        workflow_rows.append(
            {
                **record,
                "source_status": dag_result.source_status,
                "source_fail_closed_reasons": list(
                    dag_result.source_fail_closed_reasons
                ),
                "slicer_quality_flags": list(dag_result.slicer_quality_flags),
                "extractor_version": evidence["extractor_version"],
                "workflows": [asdict(item) for item in dag_result.workflows],
                "training_admission": "not_granted_dag_calibration_only",
                "training_rows_emitted": 0,
            }
        )

    workflow_statuses = Counter(row["source_status"] for row in workflow_rows)
    workflow_reasons = Counter(
        reason
        for row in workflow_rows
        for workflow in row["workflows"]
        for reason in workflow["fail_closed_reasons"]
    )
    summary = {
        "schema": "gis_recommend.gee_workflow_dag_calibration_summary.v1",
        "selected_source_count": len(selected),
        "excluded_calibration_source_count": len(excluded_source_sha256),
        "unique_source_count": len({row["source_sha256"] for row in selected}),
        "strata": dict(
            sorted(Counter(row["calibration_stratum"] for row in selected).items())
        ),
        "ast_success_count": len(workflow_rows),
        "ast_failure_count": len(parse_failures),
        "source_statuses": dict(sorted(workflow_statuses.items())),
        "workflow_fail_closed_reasons": dict(sorted(workflow_reasons.items())),
        "training_admission": "not_granted_dag_calibration_only",
        "training_rows_emitted": 0,
    }
    report = (
        "# GEE Complete Output-DAG Calibration\n\n"
        f"- Selected sources: {summary['selected_source_count']}\n"
        f"- Unique source SHA256: {summary['unique_source_count']}\n"
        f"- Strata: {json.dumps(summary['strata'], sort_keys=True)}\n"
        f"- AST success/failure: {summary['ast_success_count']}/{summary['ast_failure_count']}\n"
        f"- Source statuses: {json.dumps(summary['source_statuses'], sort_keys=True)}\n"
        f"- Fail-closed reasons: {json.dumps(summary['workflow_fail_closed_reasons'], sort_keys=True)}\n"
        "- Admission: calibration only; zero training rows emitted.\n"
    )
    payloads = {
        "selection.jsonl": _jsonl_bytes(selected),
        "workflow_dags.jsonl": _jsonl_bytes(workflow_rows),
        "parse_failures.jsonl": _jsonl_bytes(parse_failures),
        "summary.json": _json_bytes(summary),
        "report.md": report.encode("utf-8"),
    }
    if selection_manifest is not None:
        ledger_inputs = {
            "selection_manifest": {
                "path": "selection.jsonl",
                "sha256": _sha256(selection_manifest),
            },
            "parser": {"path": str(parser_path), "sha256": _sha256(parser_path)},
        }
        if ast_replay_dir is not None:
            ledger_inputs["ast_replay"] = _ast_replay_ledger(
                ast_replay_dir, selected
            )
    else:
        assert canonical_manifest is not None and join_ledger is not None
        ledger_inputs = {
            "canonical_manifest": {
                "path": str(canonical_manifest),
                "sha256": _sha256(canonical_manifest),
            },
            "join_ledger": {"path": str(join_ledger), "sha256": _sha256(join_ledger)},
            "parser": {"path": str(parser_path), "sha256": _sha256(parser_path)},
        }
        if exclude_selection_manifest is not None:
            ledger_inputs["exclude_selection_manifest"] = {
                "path": str(exclude_selection_manifest),
                "sha256": _sha256(exclude_selection_manifest),
            }
    for name, payload in payloads.items():
        _atomic_write(output_dir / name, payload)
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": ledger_inputs,
        "artifacts": {
            name: {
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
            }
            for name, payload in sorted(payloads.items())
        },
    }
    _atomic_write(output_dir / "hash_ledger.json", _json_bytes(ledger))
    return summary


def _parse_quota(value: str) -> tuple[str, int]:
    try:
        name, count = value.split("=", 1)
        return name, int(count)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("quota must use STRATUM=COUNT") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical-manifest", type=Path)
    parser.add_argument("--join-ledger", type=Path)
    parser.add_argument("--selection-manifest", type=Path)
    parser.add_argument("--exclude-selection-manifest", type=Path)
    parser.add_argument("--ast-replay-dir", type=Path)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--parser", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--node", default="node")
    parser.add_argument("--quota", type=_parse_quota, action="append", default=[])
    args = parser.parse_args(argv)
    try:
        _validate_input_mode(
            args.canonical_manifest, args.join_ledger, args.selection_manifest
        )
        if (
            args.selection_manifest is not None
            and args.exclude_selection_manifest is not None
        ):
            raise ValueError(
                "exclude_selection_manifest is only valid in full authority mode"
            )
    except ValueError as exc:
        parser.error(str(exc))
    quotas = dict(DEFAULT_QUOTAS)
    quotas.update(dict(args.quota))
    summary = build_calibration(
        canonical_manifest=args.canonical_manifest,
        join_ledger=args.join_ledger,
        selection_manifest=args.selection_manifest,
        exclude_selection_manifest=args.exclude_selection_manifest,
        ast_replay_dir=args.ast_replay_dir,
        source_root=args.source_root,
        parser_path=args.parser,
        output_dir=args.output_dir,
        node_executable=args.node,
        quotas=quotas,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
