#!/usr/bin/env python3
"""Build one cross-pool, deduplicated QGIS train-only pilot manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ALLOWED_SOURCE_ADMISSIONS = {
    "granted_train_only_qgis43_pilot",
    "granted_train_only_direct_deterministic_pilot",
    "granted_train_only_split_census_pilot",
    "granted_train_only_qgis_unified_pilot",
    "granted_train_only_stable106_increment",
    "granted_train_only_existing_l3_increment",
    "granted_train_only_mapping_correction",
    "granted_train_only_qgis_api_v1",
    "granted_train_only_qgis_processing_review_v1",
    "granted_train_only_description_recovery",
    "granted_train_only_after_semantic_revocation",
    "granted_train_only_custom_scope",
    "granted_train_only_stable110_split_salvage",
}
UNIFIED_ADMISSION = "granted_train_only_qgis_unified_pilot"
UNIFIED_SPLIT = "train_only_qgis_unified_pilot"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalize_text(value: Any) -> str:
    return "".join(str(value or "").lower().split())


def _json_key(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _training_pair_key(row: dict[str, Any]) -> str:
    return _json_key(
        {
            "task_name": _normalize_text(row.get("task_name")),
            "task_description": _normalize_text(row.get("task_description")),
            "operator_sequence": row.get("operator_sequence") or [],
            "l3_code_sequence": row.get("l3_code_sequence") or [],
        }
    )


def _mapped_source_value(
    value: Any, source_prefix_maps: list[tuple[str, str]]
) -> str:
    normalized = str(value or "").replace("\\", "/")
    for source, target in source_prefix_maps:
        source_prefix = source.replace("\\", "/").rstrip("/")
        target_prefix = target.replace("\\", "/").rstrip("/")
        if normalized == source_prefix or normalized.startswith(source_prefix + "/"):
            normalized = target_prefix + normalized[len(source_prefix) :]
            break
    return normalized


def _mapped_source_path(
    value: Any, source_prefix_maps: list[tuple[str, str]]
) -> Path:
    return Path(_mapped_source_value(value, source_prefix_maps))


def _validate_row(
    row: dict[str, Any],
    *,
    verify_source: bool,
    source_prefix_maps: list[tuple[str, str]],
    code_to_id: dict[str, int] | None,
    operator_to_l3: dict[str, str] | None,
) -> Path:
    sample_id = str(row.get("sample_id") or "")
    if not sample_id:
        raise ValueError("missing sample_id")
    if row.get("training_admission") not in ALLOWED_SOURCE_ADMISSIONS:
        raise ValueError(f"unapproved source admission for {sample_id}")
    if not str(row.get("split") or "").startswith("train_only_"):
        raise ValueError(f"row is not train-only: {sample_id}")
    if row.get("validation_eligible") or row.get("test_eligible"):
        raise ValueError(f"row is not train-only: {sample_id}")
    if row.get("production_merge") not in (None, "not_granted"):
        raise ValueError(f"production merge was unexpectedly granted: {sample_id}")
    operators = list(row.get("operator_sequence") or [])
    l3_codes = list(row.get("l3_code_sequence") or [])
    token_ids = list(row.get("l3_token_ids") or [])
    if not operators or len(operators) != len(l3_codes) or len(operators) != len(token_ids):
        raise ValueError(f"operator/L3 alignment failure: {sample_id}")
    if list(row.get("l3_sequence") or []) != [-3, *token_ids, -4]:
        raise ValueError(f"L3 token sequence mismatch: {sample_id}")
    task_name = str(row.get("task_name") or "").strip()
    task_description = str(row.get("task_description") or "").strip()
    task_metadata = row.get("task_metadata")
    if not task_name or not task_description:
        raise ValueError(f"missing task text: {sample_id}")
    if not isinstance(task_metadata, dict) or (
        task_metadata.get("task_name") != row.get("task_name")
        or task_metadata.get("task_description") != row.get("task_description")
    ):
        raise ValueError(f"task metadata mismatch: {sample_id}")
    for alias in ("qgis_operator_chain", "chain"):
        if alias in row and list(row.get(alias) or []) != operators:
            raise ValueError(f"operator chain alias mismatch: {sample_id}")
    if code_to_id is not None:
        expected_tokens = [code_to_id.get(code) for code in l3_codes]
        if None in expected_tokens or expected_tokens != token_ids:
            raise ValueError(f"L3 code/token authority mismatch: {sample_id}")
    if operator_to_l3 is not None:
        expected_codes = [operator_to_l3.get(operator) for operator in operators]
        if None in expected_codes or expected_codes != l3_codes:
            raise ValueError(f"operator/L3 authority mismatch: {sample_id}")
    for field in ("source_sha256", "source_region_key", "call_graph_key"):
        if not str(row.get(field) or ""):
            raise ValueError(f"missing {field}: {sample_id}")
    if verify_source:
        source_path = _mapped_source_path(row.get("source_path"), source_prefix_maps)
        if not source_path.is_file() or _sha256(source_path) != row["source_sha256"]:
            raise ValueError(f"source identity mismatch: {sample_id}")
    return _mapped_source_path(row.get("source_path"), source_prefix_maps)


def build_unified_manifest(
    pools: list[tuple[str, list[dict[str, Any]]]],
    *,
    verify_source: bool = False,
    source_prefix_maps: list[tuple[str, str]] | None = None,
    code_to_id: dict[str, int] | None = None,
    operator_to_l3: dict[str, str] | None = None,
    target_taxonomy_profile: str | None = None,
    target_schema_version: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    source_prefix_maps = list(source_prefix_maps or [])
    sample_ids: set[str] = set()
    canonical_regions: dict[str, dict[str, Any]] = {}
    canonical_graphs: dict[str, dict[str, Any]] = {}
    canonical_pairs: dict[str, dict[str, Any]] = {}
    ledger: list[dict[str, Any]] = []
    manifest: list[dict[str, Any]] = []
    input_counts: Counter[str] = Counter()
    kept_counts: Counter[str] = Counter()
    suppressed_counts: Counter[str] = Counter()

    for pool_name, rows in pools:
        if not pool_name:
            raise ValueError("pool name must not be empty")
        for raw_source in rows:
            source = dict(raw_source)
            source_path = _validate_row(
                source,
                verify_source=verify_source,
                source_prefix_maps=source_prefix_maps,
                code_to_id=code_to_id,
                operator_to_l3=operator_to_l3,
            )
            if verify_source:
                source["source_verification"] = "verified_sha256"
                source.setdefault("source_authority_basis", "source_sha256")
                source.setdefault(
                    "source_authority_key", f"source_sha256:{source['source_sha256']}"
                )
                source.setdefault(
                    "source_identity_replay",
                    "gis_recommend.qgis_training_source_identity_replay.v1",
                )
            source["source_path"] = _mapped_source_value(
                source.get("source_path"), source_prefix_maps
            )
            sample_id = str(source["sample_id"])
            if sample_id in sample_ids:
                raise ValueError(f"cross-pool sample_id collision: {sample_id}")
            sample_ids.add(sample_id)
            input_counts[pool_name] += 1
            region = str(source["source_region_key"])
            graph = str(source["call_graph_key"])
            pair = _training_pair_key(source)
            canonical = canonical_regions.get(region)
            if canonical is not None:
                decision = "duplicate_source_region_suppressed"
                reason = "same source SHA and Processing call spans"
            elif (canonical := canonical_graphs.get(graph)) is not None:
                decision = "duplicate_call_graph_suppressed"
                reason = "same source-backed ordered calls and dependency edges"
            elif (canonical := canonical_pairs.get(pair)) is not None:
                decision = "exact_training_pair_suppressed"
                reason = "same normalized task text, operator chain, and L3 chain"
            else:
                decision = "canonical_keep"
                reason = "unique source evidence and training pair"
                canonical = source
                canonical_regions[region] = source
                canonical_graphs[graph] = source
                canonical_pairs[pair] = source
                unified = dict(source)
                unified.update(
                    {
                        "manifest_schema": "gis_recommend.qgis_unified_train_manifest.v1",
                        "manifest_source_pool": pool_name,
                        "source_training_admission": source["training_admission"],
                        "source_split": source["split"],
                        "training_admission": UNIFIED_ADMISSION,
                        "split": UNIFIED_SPLIT,
                        "validation_eligible": False,
                        "test_eligible": False,
                        "production_merge": "not_granted",
                        "unified_training_pair_key": pair,
                    }
                )
                if target_taxonomy_profile:
                    unified["taxonomy_profile"] = target_taxonomy_profile
                if target_schema_version:
                    unified["source_schema_version"] = unified.get("schema_version")
                    unified["schema_version"] = target_schema_version
                manifest.append(unified)
                kept_counts[pool_name] += 1
            if decision != "canonical_keep":
                suppressed_counts[pool_name] += 1
            ledger.append(
                {
                    "schema": "gis_recommend.qgis_unified_dedup_ledger.v1",
                    "sample_id": sample_id,
                    "record_id": source.get("record_id"),
                    "source_pool": pool_name,
                    "source_sha256": source["source_sha256"],
                    "source_region_key": region,
                    "call_graph_key": graph,
                    "normalized_dag_key": source.get("normalized_dag_key"),
                    "training_pair_key": pair,
                    "dedup_decision": decision,
                    "dedup_reason": reason,
                    "canonical_sample_id": canonical["sample_id"],
                    "canonical_source_pool": (
                        pool_name
                        if decision == "canonical_keep"
                        else next(
                            item["source_pool"]
                            for item in ledger
                            if item["sample_id"] == canonical["sample_id"]
                        )
                    ),
                    "training_row_emitted": decision == "canonical_keep",
                }
            )

    decisions = Counter(row["dedup_decision"] for row in ledger)
    summary = {
        "schema": "gis_recommend.qgis_unified_train_manifest.summary.v1",
        "input_rows": len(ledger),
        "manifest_rows": len(manifest),
        "pool_input_counts": dict(input_counts),
        "pool_kept_counts": dict(kept_counts),
        "pool_suppressed_counts": dict(suppressed_counts),
        "suppressed_duplicate_source_regions": decisions[
            "duplicate_source_region_suppressed"
        ],
        "suppressed_duplicate_call_graphs": decisions[
            "duplicate_call_graph_suppressed"
        ],
        "suppressed_exact_training_pairs": decisions[
            "exact_training_pair_suppressed"
        ],
        "unique_source_sha256": len({row["source_sha256"] for row in manifest}),
        "unique_source_regions": len({row["source_region_key"] for row in manifest}),
        "unique_call_graphs": len({row["call_graph_key"] for row in manifest}),
        "unique_normalized_dags": len(
            {row.get("normalized_dag_key") for row in manifest}
        ),
        "unique_operator_sequences": len(
            {tuple(row["operator_sequence"]) for row in manifest}
        ),
        "unique_l3_sequences": len(
            {tuple(row["l3_code_sequence"]) for row in manifest}
        ),
        "row_admission": UNIFIED_ADMISSION,
        "split": UNIFIED_SPLIT,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "training_run": False,
        "taxonomy_profile": target_taxonomy_profile,
        "schema_version": target_schema_version,
    }
    return ledger, manifest, summary


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


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


def write_outputs(
    ledger: list[dict[str, Any]],
    manifest: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    pool_paths: list[tuple[str, Path]],
    authority_paths: list[tuple[str, Path]] | None = None,
    source_prefix_maps: list[tuple[str, str]] | None = None,
    output_dir: Path,
) -> None:
    authority_paths = list(authority_paths or [])
    source_prefix_maps = list(source_prefix_maps or [])
    ledger_path = output_dir / "qgis_unified_dedup_ledger_v1.jsonl"
    manifest_path = output_dir / "qgis_unified_train_v1.jsonl"
    summary_path = output_dir / "summary_v1.json"
    report_path = output_dir / "report_v1.md"
    hash_path = output_dir / "hash_ledger_v1.json"
    _atomic_write(ledger_path, _jsonl(ledger))
    _atomic_write(manifest_path, _jsonl(manifest))
    _atomic_write(
        summary_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    report = [
        "# QGIS Unified Train-only Manifest v1",
        "",
        f"- Input rows: {summary['input_rows']}",
        f"- Canonical rows: {summary['manifest_rows']}",
        f"- Exact training pairs suppressed: {summary['suppressed_exact_training_pairs']}",
        "- Validation/test eligible: false",
        "- Production merge: not granted",
        "- Training run: false",
        "",
        "## Pools",
        "",
        "| Pool | Input | Kept | Suppressed |",
        "|---|---:|---:|---:|",
        *[
            f"| {name} | {summary['pool_input_counts'].get(name, 0)} | "
            f"{summary['pool_kept_counts'].get(name, 0)} | "
            f"{summary['pool_suppressed_counts'].get(name, 0)} |"
            for name, _ in pool_paths
        ],
        "",
    ]
    _atomic_write(report_path, "\n".join(report))
    _atomic_write(
        hash_path,
        json.dumps(
            {
                "schema": "gis_recommend.hash_ledger.v1",
                "source_inputs": {
                    name: {"path": str(path), "sha256": _sha256(path)}
                    for name, path in pool_paths
                },
                "authority_inputs": {
                    name: {"path": str(path), "sha256": _sha256(path)}
                    for name, path in authority_paths
                },
                "source_prefix_maps": [
                    {"source": source, "target": target}
                    for source, target in source_prefix_maps
                ],
                "artifacts": {
                    path.name: {
                        "path": str(path),
                        "sha256": _sha256(path),
                        "bytes": path.stat().st_size,
                    }
                    for path in (ledger_path, manifest_path, summary_path, report_path)
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )


def _pool_argument(value: str) -> tuple[str, Path]:
    name, separator, path = value.partition("=")
    if not separator or not name or not path:
        raise argparse.ArgumentTypeError("pool must use NAME=PATH")
    return name, Path(path)


def _prefix_map_argument(value: str) -> tuple[str, str]:
    source, separator, target = value.partition("=")
    if not separator or not source or not target:
        raise argparse.ArgumentTypeError("source prefix map must use SOURCE=TARGET")
    return source, target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", action="append", type=_pool_argument, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--verify-source", action="store_true")
    parser.add_argument(
        "--source-prefix-map", action="append", type=_prefix_map_argument, default=[]
    )
    parser.add_argument("--taxonomy-authority", type=Path)
    parser.add_argument("--operator-mapping", type=Path)
    parser.add_argument("--target-taxonomy-profile")
    parser.add_argument("--target-schema-version")
    args = parser.parse_args(argv)
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    pool_paths: list[tuple[str, Path]] = args.pool
    if len({name for name, _ in pool_paths}) != len(pool_paths):
        raise ValueError("pool names must be unique")
    pools = [(name, _load_jsonl(path)) for name, path in pool_paths]
    code_to_id = None
    if args.taxonomy_authority:
        authority = json.loads(args.taxonomy_authority.read_text(encoding="utf-8"))
        code_to_id = {
            **authority.get("existing_code_to_id", {}),
            **authority.get("proposed_code_to_id_additions", {}),
        }
    operator_to_l3 = None
    if args.operator_mapping:
        operator_to_l3 = json.loads(args.operator_mapping.read_text(encoding="utf-8"))
    ledger, manifest, summary = build_unified_manifest(
        pools,
        verify_source=args.verify_source,
        source_prefix_maps=args.source_prefix_map,
        code_to_id=code_to_id,
        operator_to_l3=operator_to_l3,
        target_taxonomy_profile=args.target_taxonomy_profile,
        target_schema_version=args.target_schema_version,
    )
    write_outputs(
        ledger,
        manifest,
        summary,
        pool_paths=pool_paths,
        authority_paths=[
            (name, path)
            for name, path in (
                ("taxonomy", args.taxonomy_authority),
                ("operator_mapping", args.operator_mapping),
            )
            if path is not None
        ],
        source_prefix_maps=args.source_prefix_map,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
