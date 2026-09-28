#!/usr/bin/env python3
"""Export canonical custom-implementation Processing scopes as train-only JSONL."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gis_recommend.data.qgis_source_authority import source_authority
from export_qgis_mapping_correction_training import _code_to_id


SPECIAL_TOKENS = {"<START>": -3, "<END>": -4}


class TrainingPackage:
    def __init__(
        self,
        source_replay_rows: list[dict[str, Any]],
        training_rows: list[dict[str, Any]],
        summary: dict[str, Any],
    ) -> None:
        self.source_replay_rows = source_replay_rows
        self.training_rows = training_rows
        self.summary = summary


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _literal_processing_calls(tree: ast.AST) -> list[tuple[int, int, str]]:
    calls: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (
            isinstance(func, ast.Attribute)
            and func.attr == "run"
            and isinstance(func.value, ast.Name)
            and func.value.id == "processing"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            continue
        calls.append(
            (
                int(node.lineno),
                int(getattr(node, "end_lineno", node.lineno)),
                str(node.args[0].value).strip().lower(),
            )
        )
    return sorted(calls)


def _same_operator_contract(literal: str, expected: str) -> bool:
    if literal == expected:
        return True
    literal_provider, separator, literal_slug = literal.partition(":")
    expected_provider, expected_separator, expected_slug = expected.partition(":")
    return bool(
        separator
        and expected_separator
        and literal_slug == expected_slug
        and literal_provider == "qgis"
        and expected_provider == "native"
    )


def _verify_source(candidate: dict[str, Any]) -> dict[str, Any]:
    record_id = str(candidate.get("record_id") or "")
    path = Path(str(candidate.get("source_path") or ""))
    expected_sha = str(candidate.get("source_sha256") or "")
    if not path.is_file() or _sha256(path) != expected_sha:
        raise ValueError(f"source SHA mismatch: {record_id}")
    source_text = path.read_text(encoding="utf-8-sig", errors="strict")
    tree = ast.parse(source_text)
    literal_calls = _literal_processing_calls(tree)
    call_sites = list(candidate.get("call_sites") or [])
    operators = [str(value).lower() for value in candidate.get("operator_ids") or []]
    if not call_sites or len(call_sites) != len(operators):
        raise ValueError(f"operator/call-site length mismatch: {record_id}")

    source_lines = source_text.splitlines()
    snippets: list[str] = []
    for site, expected_operator in zip(call_sites, operators, strict=True):
        start = int(site.get("line_start") or 0)
        end = int(site.get("line_end") or start)
        if start < 1 or end < start or end > len(source_lines):
            raise ValueError(f"invalid call span for {record_id}: {start}-{end}")
        matched = [
            literal
            for call_start, call_end, literal in literal_calls
            if call_start >= start and call_end <= end
        ]
        if len(matched) != 1 or not _same_operator_contract(
            matched[0], expected_operator
        ):
            raise ValueError(
                f"literal Processing operator mismatch for {record_id}: "
                f"{matched!r} != {expected_operator!r}"
            )
        snippets.append(
            "\n".join(
                f"{line_number} | {source_lines[line_number - 1]}"
                for line_number in range(start, end + 1)
            )
        )

    authority = source_authority(path, source_sha256=expected_sha)
    return {
        "schema": "gis_recommend.qgis_custom_scope_source_replay.v1",
        "record_id": record_id,
        "source_path": str(path),
        "source_sha256": expected_sha,
        "source_verification": "verified_sha256",
        "ast_verification": "verified_python_ast",
        "call_span_verification": "verified_processing_calls",
        "literal_operator_verification": "verified",
        "operator_ids": operators,
        "mapped_l3_chain": list(candidate.get("mapped_l3_chain") or []),
        "call_sites": call_sites,
        "source_snippet": "\n...\n".join(snippets),
        **authority,
        "training_admission": "not_granted_pending_custom_scope_export",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def _source_span(call_sites: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "line_start": min(int(site["line_start"]) for site in call_sites),
        "line_end": max(int(site["line_end"]) for site in call_sites),
        "call_sites": call_sites,
    }


def build_training_package(
    scope_rows: list[dict[str, Any]],
    *,
    extension: dict[str, Any],
    mapping_authority: str,
) -> TrainingPackage:
    if not mapping_authority.strip():
        raise ValueError("mapping authority is required")
    code_to_id = _code_to_id(extension)
    canonical = [
        row for row in scope_rows if row.get("dedup_status") == "canonical_candidate"
    ]
    if not canonical:
        raise ValueError("no canonical custom-scope candidates")

    replay_rows: list[dict[str, Any]] = []
    training_rows: list[dict[str, Any]] = []
    quality_deferred_record_ids: list[str] = []
    seen_record_ids: set[str] = set()
    for candidate in canonical:
        record_id = str(candidate.get("record_id") or "")
        if not record_id or record_id in seen_record_ids:
            raise ValueError(f"blank or duplicate record_id: {record_id!r}")
        seen_record_ids.add(record_id)
        if (
            candidate.get("description_fidelity_passed") is not True
            or candidate.get("mapping_complete") is not True
            or candidate.get("parameter_evidence_status") != "verified_source_ast"
        ):
            quality_deferred_record_ids.append(record_id)
            continue
        operators = [str(value) for value in candidate.get("operator_ids") or []]
        l3_codes = [str(value) for value in candidate.get("mapped_l3_chain") or []]
        if not operators or len(operators) != len(l3_codes):
            raise ValueError(f"operator/L3 length mismatch: {record_id}")
        try:
            token_ids = [code_to_id[code] for code in l3_codes]
        except KeyError as exc:
            raise ValueError(f"unmapped stable110 code for {record_id}: {exc}") from exc
        task_name = str(candidate.get("task_name") or "").strip()
        task_description = str(candidate.get("task_description") or "").strip()
        if not task_name or not task_description:
            raise ValueError(f"missing deterministic task text: {record_id}")

        replay = _verify_source(candidate)
        replay_rows.append(replay)
        scope = str(candidate.get("workflow_unit_scope") or "")
        task_type = (
            "QGIS可验证局部工作流"
            if scope == "local_subworkflow"
            else "QGIS可验证Processing工作流"
        )
        training_rows.append(
            {
                "schema_version": "qgis_custom_scope_training_sample_v1",
                "sample_id": f"qgis_custom_scope_{record_id}",
                "record_id": record_id,
                "source_root_id": candidate.get("source_root_id", ""),
                "source_path": replay["source_path"],
                "source_sha256": replay["source_sha256"],
                "source_authority_key": replay["source_authority_key"],
                "source_authority_basis": replay["source_authority_basis"],
                "source_verification": replay["source_verification"],
                "ast_verification": replay["ast_verification"],
                "call_span_verification": replay["call_span_verification"],
                "literal_operator_verification": replay[
                    "literal_operator_verification"
                ],
                "source_span": _source_span(replay["call_sites"]),
                "evidence_snippet": replay["source_snippet"],
                "entrypoint": "source_replayed_custom_implementation_scope",
                "operator_sequence": operators,
                "qgis_operator_chain": operators,
                "chain": operators,
                "l3_code_sequence": l3_codes,
                "l3_token_ids": token_ids,
                "l3_sequence": [
                    SPECIAL_TOKENS["<START>"],
                    *token_ids,
                    SPECIAL_TOKENS["<END>"],
                ],
                "l3_codes": ["<START>", *l3_codes, "<END>"],
                "n": len(operators),
                "task_name": task_name,
                "task_description": task_description,
                "task_type": task_type,
                "task_metadata": {
                    "task_type": task_type,
                    "task_name": task_name,
                    "task_description": task_description,
                },
                "workflow_scope": scope,
                "dependency_edges": candidate.get("dependency_edges") or [],
                "parameter_facts": candidate.get("parameter_facts") or [],
                "known_omissions": candidate.get("known_omissions") or [],
                "source_region_key": candidate["dedup_source_region_key"],
                "call_graph_key": candidate["dedup_call_graph_key"],
                "normalized_dag_key": candidate["dedup_normalized_dag_key"],
                "unified_training_pair_key": candidate[
                    "dedup_training_pair_key"
                ],
                "cluster_id": candidate["dedup_normalized_dag_key"],
                "source": "qgis_custom_implementation_scope_replayed_v1",
                "_training_quality": {
                    "tier": "source_replayed_deterministic_gold",
                    "sample_weight": 1.0,
                },
                "taxonomy_profile": "stable110_authority_v1",
                "mapping_authority": mapping_authority,
                "training_admission": "granted_train_only_custom_scope",
                "split": "train_only_custom_scope",
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )

    summary = {
        "schema": "gis_recommend.qgis_custom_scope_export_summary.v1",
        "counts": {
            "scope_rows": len(scope_rows),
            "canonical_rows": len(canonical),
            "duplicate_rows": len(scope_rows) - len(canonical),
            "quality_deferred_rows": len(quality_deferred_record_ids),
            "source_replayed_rows": len(replay_rows),
            "exported_rows": len(training_rows),
            "unique_sources": len(
                {row["source_sha256"] for row in training_rows}
            ),
            "unique_dags": len(
                {row["normalized_dag_key"] for row in training_rows}
            ),
        },
        "taxonomy": {
            "profile": "stable110_authority_v1",
            "content_token_count": int(extension["proposed_class_count"]),
            "mapping_authority": mapping_authority,
        },
        "decision": {
            "row_admission": "granted_train_only_custom_scope",
            "production_merge": "not_granted",
            "validation_eligible": False,
            "test_eligible": False,
            "llm_called": False,
            "training_run": False,
            "quality_deferred_record_ids": quality_deferred_record_ids,
        },
    }
    return TrainingPackage(replay_rows, training_rows, summary)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
    )


def write_package(
    package: TrainingPackage,
    *,
    output_dir: Path,
    inputs: dict[str, Path],
) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {output_dir}")
    replay_path = output_dir / "source_replay_v1.jsonl"
    train_path = output_dir / "train_only_v1.jsonl"
    summary_path = output_dir / "summary_v1.json"
    hash_path = output_dir / "hash_ledger_v1.json"
    _write_jsonl(replay_path, package.source_replay_rows)
    _write_jsonl(train_path, package.training_rows)
    _write_json(summary_path, package.summary)
    _write_json(
        hash_path,
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                name: {"path": str(path), "sha256": _sha256(path)}
                for name, path in sorted(inputs.items())
            },
            "artifacts": {
                path.name: {
                    "path": str(path),
                    "sha256": _sha256(path),
                    "bytes": path.stat().st_size,
                }
                for path in (replay_path, train_path, summary_path)
            },
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope-ledger", type=Path, required=True)
    parser.add_argument("--extension", type=Path, required=True)
    parser.add_argument("--mapping-authority", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    package = build_training_package(
        _read_jsonl(args.scope_ledger),
        extension=_read_json(args.extension),
        mapping_authority=args.mapping_authority,
    )
    write_package(
        package,
        output_dir=args.output_dir,
        inputs={"scope_ledger": args.scope_ledger, "extension": args.extension},
    )
    print(json.dumps(package.summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
