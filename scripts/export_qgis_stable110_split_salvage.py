#!/usr/bin/env python3
"""Export source-replayed stable110 units salvaged from Snap-routed parents."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
for import_root in (ROOT, ROOT / "src", ROOT / "scripts"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from evaluate_qgis_stable118_structure_increment import (  # noqa: E402
    _fetch_ssh_source,
    materialize_sources,
)
from export_qgis_top20_existing_l3_training import (  # noqa: E402
    build_training_rows as build_existing_l3_rows,
)
from replay_qgis_stable106_direct_candidates import replay_candidates  # noqa: E402


DEFAULT_CANONICAL = (
    ROOT
    / "docs/reports/qgis_processing_snap_stable111_dedup_v1"
    / "canonical_proposals_v1.jsonl"
)
DEFAULT_EXISTING = (
    ROOT
    / "docs/reports/qgis_processing_train_delivery_177_v1"
    / "source_replay_v1/source_verified_train_v1.jsonl"
)
DEFAULT_EXTENSION = (
    ROOT
    / "docs/reports/qgis_processing_mapping_gap_stable106_v1"
    / "stable110_authority_v1/stable110_extension_v1.json"
)
DEFAULT_MAPPING = (
    ROOT
    / "docs/reports/qgis_processing_custom_scope_replay_v2_corrected_mapping"
    / "composed_stable110_mapping_v2_corrected.json"
)


def _prepared_candidate(row: dict[str, Any]) -> dict[str, Any]:
    candidate = dict(row)
    candidate.update(
        {
            "record_id": str(row["proposal_id"]),
            "source_root_id": str(row.get("parent_source_root_id") or ""),
            "mapping_authority": "stable110_authority_v1",
        }
    )
    return candidate


def build_stable110_salvage_training(
    canonical: list[dict[str, Any]],
    replay: list[dict[str, Any]],
    extension: dict[str, Any],
    mapping: dict[str, str],
    existing: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if extension.get("proposed_taxonomy") != "stable110":
        raise ValueError("split salvage requires the formal stable110 taxonomy")
    existing_regions = {str(row.get("source_region_key") or "") for row in existing}
    existing_graphs = {str(row.get("call_graph_key") or "") for row in existing}
    existing_pairs = {str(row.get("unified_training_pair_key") or "") for row in existing}
    candidates: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    for row in canonical:
        if row.get("dedup_decision") != "canonical_proposal_keep":
            raise ValueError("non-canonical row passed to stable110 salvage export")
        if row.get("taxonomy_route") != "stable110_existing":
            raise ValueError("Snap-containing proposal cannot enter stable110 salvage")
        operators = [str(value) for value in row.get("operator_ids") or []]
        l3_codes = [str(value) for value in row.get("mapped_l3_chain") or []]
        if not operators or len(operators) != len(l3_codes):
            raise ValueError("operator/L3 alignment failure")
        if [mapping.get(operator) for operator in operators] != l3_codes:
            raise ValueError(f"stable110 mapping mismatch: {row.get('proposal_id')}")
        if (
            row.get("source_region_key") in existing_regions
            or row.get("call_graph_key") in existing_graphs
            or row.get("training_pair_key") in existing_pairs
        ):
            raise ValueError(f"row overlaps formal authority: {row.get('proposal_id')}")
        candidate = _prepared_candidate(row)
        candidates.append(candidate)
        ledger.append({**candidate, "dedup_decision": "canonical_keep_candidate"})

    result = build_existing_l3_rows(
        ledger=ledger,
        candidates=candidates,
        replay=replay,
        extension=extension,
        authority=[],
        expected_mapping_authority="stable110_authority_v1",
    )
    rows = []
    for source in result.rows:
        row = dict(source)
        row.update(
            {
                "schema_version": "qgis_stable110_split_salvage_training_sample_v1",
                "sample_id": f"qgis_stable110_split_salvage_{source['record_id']}",
                "entrypoint": "source_replayed_stable110_split_salvage",
                "source": "qgis_stable110_split_salvage",
                "mapping_authority": "stable110_authority_v1",
                "training_admission": "granted_train_only_stable110_split_salvage",
                "split": "train_only_stable110_split_salvage",
            }
        )
        rows.append(row)
    summary = {
        "schema": "gis_recommend.qgis_stable110_split_salvage_export.summary.v1",
        "canonical_input_rows": len(canonical),
        "source_replayed_rows": len(replay),
        "exported_rows": len(rows),
        "unique_source_sha256": len({row["source_sha256"] for row in rows}),
        "unique_normalized_dags": len({row["normalized_dag_key"] for row in rows}),
        "taxonomy_profile": "stable110_authority_v1",
        "training_admission": "granted_train_only_stable110_split_salvage",
        "split": "train_only_stable110_split_salvage",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
        "training_run": False,
    }
    return rows, summary


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _jsonl(rows: Iterable[dict[str, Any]]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--existing-authority", type=Path, default=DEFAULT_EXISTING)
    parser.add_argument("--extension", type=Path, default=DEFAULT_EXTENSION)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--ssh-host", default="qy@10.191.2.38")
    parser.add_argument("--remote-prefix-alias", action="append", default=[])
    parser.add_argument("--expected-rows", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    aliases = []
    for value in args.remote_prefix_alias:
        old, separator, new = value.partition("=")
        if not separator or not old or not new:
            raise ValueError(f"invalid remote prefix alias: {value!r}")
        aliases.append((old, new))

    canonical = _read_jsonl(args.canonical)
    if len(canonical) != args.expected_rows:
        raise ValueError(f"canonical rows {len(canonical)} != expected {args.expected_rows}")
    prepared = [_prepared_candidate(row) for row in canonical]
    replay_ledger = [{**row, "dedup_decision": "canonical_keep_candidate"} for row in prepared]
    with tempfile.TemporaryDirectory(prefix="qgis_stable110_split_salvage_") as temp:
        materialized = materialize_sources(
            prepared,
            Path(temp),
            lambda path: _fetch_ssh_source(args.ssh_host, path),
            path_aliases=aliases,
        )
        replay, replay_summary = replay_candidates(
            materialized,
            replay_ledger,
            replay_profile="stable110_split_salvage",
        )
    originals = {str(row["record_id"]): str(row["source_path_original"]) for row in materialized}
    for row in replay:
        row["source_path"] = originals[str(row["record_id"])]
    rows, summary = build_stable110_salvage_training(
        canonical,
        replay,
        _read_json(args.extension),
        _read_json(args.mapping),
        _read_jsonl(args.existing_authority),
    )
    summary["source_replay"] = replay_summary
    summary["prior_formal_rows"] = len(_read_jsonl(args.existing_authority))
    summary["cumulative_processing_rows"] = summary["prior_formal_rows"] + len(rows)

    replay_path = args.output_dir / "source_replay_v1.jsonl"
    train_path = args.output_dir / "stable110_split_salvage_train_only_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    report_path = args.output_dir / "report_v1.md"
    _write(replay_path, _jsonl(replay))
    _write(train_path, _jsonl(rows))
    _write(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _write(
        report_path,
        "\n".join(
            [
                "# QGIS stable110 Split Salvage Delivery v1",
                "",
                f"- Exported train-only rows: {summary['exported_rows']}",
                f"- Verified source rows: {summary['source_replayed_rows']}",
                f"- Processing cumulative rows: {summary['cumulative_processing_rows']}",
                "- These rows contain no Snap operator and use only stable110 mappings.",
                "- Validation/test/production remain closed; no LLM and no training run.",
                "",
            ]
        ),
    )
    hash_path = args.output_dir / "hash_ledger_v1.json"
    _write(
        hash_path,
        json.dumps(
            {
                "schema": "gis_recommend.hash_ledger.v1",
                "inputs": {
                    str(path): _sha256(path)
                    for path in (args.canonical, args.existing_authority, args.extension, args.mapping)
                },
                "artifacts": {
                    path.name: _sha256(path)
                    for path in (replay_path, train_path, summary_path, report_path)
                },
                "remote_prefix_aliases": [{"from": old, "to": new} for old, new in aliases],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
