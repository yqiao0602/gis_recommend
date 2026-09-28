#!/usr/bin/env python3
"""Publish source-backed facts and task text for mapping-complete GEE workflows."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from gis_recommend.data.gee_workflow_task_facts import (
    build_workflow_fact_bundle,
    deduplicate_task_text_candidates,
    render_chain_faithful_task_text,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number} is not a JSON object")
            rows.append(row)
    return rows


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    ).encode("utf-8")


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("source_sha256") or ""), str(row.get("workflow_id") or "")


def _unique_index(rows: list[dict[str, Any]], label: str) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = _key(row)
        if not all(key):
            raise ValueError(f"{label} row has incomplete workflow identity: {key}")
        if key in index:
            raise ValueError(f"duplicate {label} workflow identity: {key}")
        index[key] = row
    return index


def _source_path(source_root: Path, row: dict[str, Any]) -> Path:
    value = Path(str(row["source_path"]))
    return value if value.is_absolute() else source_root / value


def _ast_path(ast_dir: Path, source_sha256: str) -> Path:
    candidates = (
        ast_dir / f"{source_sha256}.ast.json",
        ast_dir / f"{source_sha256}.json",
    )
    existing = [path for path in candidates if path.is_file()]
    if len(existing) != 1:
        raise ValueError(f"expected one AST for {source_sha256}; found {len(existing)}")
    return existing[0]


def _load_ast(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict) or value.get("type") != "Program":
        raise ValueError(f"{path} is not an ESTree Program")
    return value


def _risk_flags(bundle: dict[str, Any], candidate: dict[str, Any]) -> list[str]:
    flags = set(candidate.get("risk_flags") or [])
    if bundle.get("calibration_stratum") != "linear_export":
        flags.add(f"stratum:{bundle.get('calibration_stratum')}")
    if len(bundle.get("operator_sequence") or []) >= 20:
        flags.add("long_chain_20_plus")
    if len(bundle.get("dataset_facts") or []) > 1:
        flags.add("multiple_dataset_facts")
    if any(fact.get("text_use") == "omitted_private_asset" for fact in bundle.get("dataset_facts") or []):
        flags.add("private_asset_redacted")
    flags.update(str(value) for value in bundle.get("known_omissions") or [])
    if any(fact.get("resolution") == "external_identifier" for fact in bundle.get("spatial_input_facts") or []):
        flags.add("external_spatial_identifier")
    if any(fact.get("signature") == "legacy_positional" for fact in bundle.get("output_facts") or []):
        flags.add("legacy_positional_export")
    operator_sequence = bundle.get("operator_sequence") or []
    if len(set(operator_sequence)) < len(operator_sequence):
        flags.add("repeated_operator")
    return sorted(flags)


def _review_packet(candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_sources: set[str] = set()
    ordered = sorted(
        candidates,
        key=lambda row: (
            -len(row.get("risk_flags") or []),
            str(row.get("source_sha256")),
            str(row.get("workflow_id")),
        ),
    )
    for row in ordered:
        source_sha = str(row["source_sha256"])
        if source_sha in selected_sources:
            continue
        selected_sources.add(source_sha)
        selected.append(
            {
                "schema": "gis_recommend.gee_workflow_task_text_review.v1",
                "review_index": len(selected) + 1,
                **row,
                "human_dataset_fidelity": "",
                "human_temporal_fidelity": "",
                "human_spatial_fidelity": "",
                "human_transformation_fidelity": "",
                "human_output_fidelity": "",
                "human_task_text_fidelity": "",
                "human_decision": "",
                "human_notes": "",
            }
        )
        if len(selected) >= limit:
            break
    return selected


def _report(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    return (
        "# GEE Workflow Source-Backed Facts And Task Text\n\n"
        f"- Mapping-complete input: {counts['input_mapping_complete']}\n"
        f"- Source-backed fact bundles: {counts['fact_bundles']}\n"
        f"- Fact fail-closed: {counts['fail_closed']}\n"
        f"- Deduplicated task-text candidates: {counts['task_text_candidates']}\n"
        f"- Duplicate sidecar: {counts['duplicates']}\n"
        f"- Source-disjoint risk review rows: {counts['risk_review_rows']}\n"
        f"- Unique candidate sources: {counts['unique_candidate_sources']}\n"
        "- Frozen operator/L3 chains changed: 0\n"
        "- Training/validation/test/production admission: not granted\n"
        "- Training rows emitted: 0\n"
    )


def build_workflow_task_facts(
    *,
    typed_candidates_path: Path,
    fidelity_candidates_path: Path,
    ast_dir: Path,
    source_root: Path,
    output_dir: Path,
    review_limit: int = 50,
) -> dict[str, Any]:
    """Build a deterministic fact/text partition for frozen mapping-complete rows."""

    typed_rows = _load_jsonl(typed_candidates_path)
    fidelity_rows = _load_jsonl(fidelity_candidates_path)
    _unique_index(typed_rows, "typed")
    fidelity_by_key = _unique_index(fidelity_rows, "fidelity")
    fact_bundles: list[dict[str, Any]] = []
    text_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    verified_inputs: dict[str, str] = {}

    for typed in sorted(typed_rows, key=_key):
        workflow_key = _key(typed)
        fidelity = fidelity_by_key.get(workflow_key)
        if fidelity is None:
            failures.append(
                {
                    "schema": "gis_recommend.gee_workflow_fact_failure.v1",
                    "workflow_key": list(workflow_key),
                    "source_path": typed.get("source_path"),
                    "reason": "missing_fidelity_join",
                    "training_admission": "not_granted_fact_fail_closed",
                    "training_rows_emitted": 0,
                }
            )
            continue
        try:
            source = _source_path(source_root, typed)
            expected_sha = str(typed["source_sha256"])
            if not source.is_file():
                raise ValueError("source file missing")
            if _sha256(source) != expected_sha:
                raise ValueError("source hash mismatch")
            ast_path = _ast_path(ast_dir, expected_sha)
            bundle = build_workflow_fact_bundle(typed, fidelity, _load_ast(ast_path))
            candidate = render_chain_faithful_task_text(bundle)
            candidate["risk_flags"] = _risk_flags(bundle, candidate)
            fact_bundles.append(bundle)
            text_rows.append(candidate)
            # The ledger records logical identities so an A/B replay can use
            # different physical directories without changing its publication hash.
            verified_inputs[f"source/{typed['source_path']}"] = expected_sha
            verified_inputs[f"ast/{expected_sha}.json"] = _sha256(ast_path)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            failures.append(
                {
                    "schema": "gis_recommend.gee_workflow_fact_failure.v1",
                    "workflow_key": list(workflow_key),
                    "source_path": typed.get("source_path"),
                    "reason": str(exc),
                    "training_admission": "not_granted_fact_fail_closed",
                    "training_rows_emitted": 0,
                }
            )

    candidates, duplicates = deduplicate_task_text_candidates(text_rows)
    review_rows = _review_packet(candidates, max(0, review_limit))
    if len(fact_bundles) + len(failures) != len(typed_rows):
        raise ValueError("fact partition conservation failure")
    if len(candidates) + len(duplicates) != len(text_rows):
        raise ValueError("task-text partition conservation failure")

    risk_counts = Counter(flag for row in candidates for flag in row.get("risk_flags") or [])
    summary = {
        "schema": "gis_recommend.gee_workflow_task_facts_summary.v1",
        "counts": {
            "input_mapping_complete": len(typed_rows),
            "fidelity_authority_rows": len(fidelity_rows),
            "fact_bundles": len(fact_bundles),
            "fail_closed": len(failures),
            "task_text_candidates_before_dedup": len(text_rows),
            "task_text_candidates": len(candidates),
            "duplicates": len(duplicates),
            "risk_review_rows": len(review_rows),
            "unique_candidate_sources": len({row["source_sha256"] for row in candidates}),
            "training_rows_emitted": 0,
        },
        "risk_flags": dict(sorted(risk_counts.items())),
        "dedup_key": "normalized_task_name_description_plus_l3_sequence",
        "training_admission": "not_granted_risk_review_and_final_dedup_pending",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    payloads = {
        "workflow_fact_bundles.jsonl": _jsonl_bytes(fact_bundles),
        "task_text_candidates.jsonl": _jsonl_bytes(candidates),
        "fact_fail_closed.jsonl": _jsonl_bytes(failures),
        "task_text_duplicates.jsonl": _jsonl_bytes(duplicates),
        "risk_review_packet.jsonl": _jsonl_bytes(review_rows),
        "summary.json": _json_bytes(summary),
        "report.md": _report(summary).encode("utf-8"),
    }
    for name, payload in payloads.items():
        _atomic_write(output_dir / name, payload)
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            "typed_candidates": {
                "path": "mapping_complete_candidates.jsonl",
                "sha256": _sha256(typed_candidates_path),
            },
            "fidelity_candidates": {
                "path": "accepted_candidates.jsonl",
                "sha256": _sha256(fidelity_candidates_path),
            },
            "verified_source_and_ast_files": dict(sorted(verified_inputs.items())),
        },
        "artifacts": {
            name: {"sha256": hashlib.sha256(payload).hexdigest(), "size_bytes": len(payload)}
            for name, payload in sorted(payloads.items())
        },
    }
    _atomic_write(output_dir / "hash_ledger.json", _json_bytes(ledger))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--typed-candidates", type=Path, required=True)
    parser.add_argument("--fidelity-candidates", type=Path, required=True)
    parser.add_argument("--ast-dir", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--review-limit", type=int, default=50)
    args = parser.parse_args()
    build_workflow_task_facts(
        typed_candidates_path=args.typed_candidates,
        fidelity_candidates_path=args.fidelity_candidates,
        ast_dir=args.ast_dir,
        source_root=args.source_root,
        output_dir=args.output_dir,
        review_limit=args.review_limit,
    )


if __name__ == "__main__":
    main()
