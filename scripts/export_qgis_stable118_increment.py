#!/usr/bin/env python3
"""Export a minimum stable-N Processing increment as train-only JSONL."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable, NamedTuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.build_qgis_direct_description_candidates import build_candidates
from scripts.export_qgis_top20_existing_l3_training import build_training_rows
from scripts.replay_qgis_stable106_direct_candidates import replay_candidates
from scripts.run_qgis_processing_blocker_batch import (
    _parse_prefix_aliases,
    annotate_dedup,
    enrich_source_authority,
    resolve_source_rows,
)


class IncrementResult(NamedTuple):
    candidates: list[dict[str, Any]]
    dedup_ledger: list[dict[str, Any]]
    source_replay: list[dict[str, Any]]
    training_rows: list[dict[str, Any]]
    summary: dict[str, Any]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _authority_operators(authority_rows: list[dict[str, Any]]) -> set[str]:
    operators = {
        str(row.get("operator_id") or "")
        for row in authority_rows
        if row.get("mapping_admission") == "granted"
    }
    if "" in operators or not operators:
        raise ValueError("stable118 authority has blank or no granted operator")
    if len(operators) != len(authority_rows):
        raise ValueError("stable118 authority contains duplicate or ungranted operators")
    return operators


def _select_direct_rows(
    replay_rows: list[dict[str, Any]],
    authority_operators: set[str],
    mapping_authority: str,
) -> list[dict[str, Any]]:
    selected = [
        row
        for row in replay_rows
        if row.get("action") == "auto_accept_candidate"
        and row.get("mapping_complete") is True
        and row.get("mapping_authority") == mapping_authority
        and authority_operators.intersection(row.get("operator_ids") or [])
    ]
    record_ids = [str(row.get("record_id") or "") for row in selected]
    if "" in record_ids or len(record_ids) != len(set(record_ids)):
        raise ValueError("selected stable118 direct rows have blank or duplicate record_id")
    return sorted(selected, key=lambda row: str(row["record_id"]))


def _as_export_ledger(
    rows: list[dict[str, Any]], profile_name: str
) -> list[dict[str, Any]]:
    ledger: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        canonical = row.get("dedup_status") == "canonical_candidate"
        row.update(
            {
                "schema": f"gis_recommend.qgis_{profile_name}_increment_dedup.v1",
                "dedup_decision": (
                    "canonical_keep_candidate"
                    if canonical
                    else str(row.get("dedup_status") or "duplicate_unknown")
                ),
                "source_region_key": row["dedup_source_region_key"],
                "call_graph_key": row["dedup_call_graph_key"],
                "normalized_dag_key": row["dedup_normalized_dag_key"],
                "training_pair_key": row["dedup_training_pair_key"],
                "training_admission": (
                    "not_granted_pending_source_replay"
                    if canonical
                    else "not_granted_duplicate"
                ),
                "training_row_emitted": False,
            }
        )
        ledger.append(row)
    return ledger


def build_increment_package(
    *,
    replay_rows: list[dict[str, Any]],
    authority_rows: list[dict[str, Any]],
    extension: dict[str, Any],
    existing_train_rows: list[dict[str, Any]],
    source_prefix_aliases: list[tuple[str, str]] | None = None,
    profile_name: str = "stable118",
) -> IncrementResult:
    mapping_authority = f"{profile_name}_authority_v1"
    authority_operators = _authority_operators(authority_rows)
    selected = _select_direct_rows(
        replay_rows, authority_operators, mapping_authority
    )
    candidates, description_summary = build_candidates(selected)
    passed = [
        row for row in candidates if row.get("description_fidelity_passed") is True
    ]
    resolved, source_failures = resolve_source_rows(
        passed, list(source_prefix_aliases or [])
    )
    if source_failures:
        failed_ids = [str(row.get("record_id") or "") for row in source_failures]
        raise ValueError(f"stable118 source path resolution failed: {failed_ids}")
    enriched = enrich_source_authority(resolved)
    dedup_ledger = _as_export_ledger(
        annotate_dedup(enriched, existing_train_rows), profile_name
    )
    source_replay, replay_summary = replay_candidates(
        enriched,
        dedup_ledger,
        replay_profile=profile_name,
    )
    export = build_training_rows(
        ledger=dedup_ledger,
        candidates=enriched,
        replay=source_replay,
        extension=extension,
        authority=[
            {
                **row,
                "candidate_l3_code": row.get("candidate_l3_code")
                or row.get("l3_code"),
            }
            for row in authority_rows
        ],
    )
    training_rows = []
    for source in export.rows:
        row = dict(source)
        row.update(
            {
                "schema_version": f"qgis_{profile_name}_increment_v1",
                "mapping_authority": mapping_authority,
                "taxonomy_profile": mapping_authority,
                "source_replay_authority": f"{profile_name}_source_replay_v1",
            }
        )
        training_rows.append(row)
    summary = {
        "schema": f"gis_recommend.qgis_{profile_name}_increment_summary.v1",
        "input_replay_rows": len(replay_rows),
        "selected_direct_rows": len(selected),
        "description_fidelity_passed_rows": len(passed),
        "description_fidelity_deferred_rows": len(candidates) - len(passed),
        "canonical_rows": sum(
            row.get("dedup_decision") == "canonical_keep_candidate"
            for row in dedup_ledger
        ),
        "duplicate_rows": sum(
            row.get("dedup_decision") != "canonical_keep_candidate"
            for row in dedup_ledger
        ),
        "source_replayed_rows": len(source_replay),
        "exported_training_rows": len(training_rows),
        "content_token_count": int(extension.get("proposed_class_count") or 0),
        "description_policy": description_summary.get("description_policy"),
        "source_verification_mode_counts": replay_summary.get(
            "verification_mode_counts"
        ),
        "llm_called": False,
        "training_run": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return IncrementResult(
        candidates=candidates,
        dedup_ledger=dedup_ledger,
        source_replay=source_replay,
        training_rows=training_rows,
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


def _jsonl(rows: Iterable[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for row in rows
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--authority", type=Path, required=True)
    parser.add_argument("--extension", type=Path, required=True)
    parser.add_argument("--existing-pool", type=Path, action="append", default=[])
    parser.add_argument("--source-prefix-alias", action="append", default=[])
    parser.add_argument("--profile-name", default="stable118")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    result = build_increment_package(
        replay_rows=_read_jsonl(args.replay),
        authority_rows=_read_jsonl(args.authority),
        extension=_read_json(args.extension),
        existing_train_rows=[
            row for path in args.existing_pool for row in _read_jsonl(path)
        ],
        source_prefix_aliases=_parse_prefix_aliases(args.source_prefix_alias),
        profile_name=args.profile_name,
    )
    artifacts = {
        "candidates_v1.jsonl": _jsonl(result.candidates),
        "dedup_ledger_v1.jsonl": _jsonl(result.dedup_ledger),
        "source_replay_v1.jsonl": _jsonl(result.source_replay),
        "train_only_v1.jsonl": _jsonl(result.training_rows),
        "summary_v1.json": json.dumps(
            result.summary, ensure_ascii=False, indent=2, sort_keys=True
        )
        + "\n",
    }
    artifact_paths: list[Path] = []
    for name, content in artifacts.items():
        path = args.output_dir / name
        _atomic_write(path, content)
        artifact_paths.append(path)
    hash_path = args.output_dir / "hash_ledger_v1.json"
    inputs = [args.replay, args.authority, args.extension, *args.existing_pool]
    _atomic_write(
        hash_path,
        json.dumps(
            {
                "schema": "gis_recommend.hash_ledger.v1",
                "inputs": {str(path): _sha256(path) for path in inputs},
                "artifacts": {path.name: _sha256(path) for path in artifact_paths},
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    print(json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
