#!/usr/bin/env python3
"""Build immutable, source-backed manifests for the two QGIS batch pools.

The screening layer has one extra low-level row that is not in the strong-signal
authority.  This command therefore derives the API pool from the strong-signal
path ledger, not from the broad layer table.  It only emits audit manifests;
training, validation, test, and production admission remain closed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


PROCESSING_LAYERS = {
    "dynamic_or_blank_processing_id",
    "explicit_processing_catalog_miss",
    "processing_algorithm_implementation_or_custom",
}


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _strong_paths(path: Path) -> set[str]:
    # The ledger is NUL-delimited because source paths contain newlines in rare
    # repositories.  Decode replacement bytes only for an explicit audit flag.
    raw = path.read_bytes()
    return {item.decode("utf-8", errors="replace") for item in raw.split(b"\0") if item}


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _base(row: dict[str, Any], *, pool: str, source_path: str, source_sha: str) -> dict[str, Any]:
    return {
        "schema": "gis_recommend.qgis_source_authority_manifest.v1",
        "pool": pool,
        # Existing QGIS replay artifacts use the first 24 hex characters as
        # the stable record identity; keep that identity for carry-forward joins.
        "record_id": source_sha[:24],
        "source_path": source_path,
        "source_sha256": source_sha,
        "content_sha256": source_sha,
        "source_root_id": row.get("source_root_id", ""),
        "relative_path": row.get("relative_path", ""),
        "primary_layer": row.get("primary_layer", ""),
        "screening_tier": row.get("screening_tier", ""),
        "parse_status": row.get("parse_status", ""),
        "provenance_authority": "nine_sources_canonical_v2_strong_signal",
        "source_replay_status": "pending_full_replay",
        "training_admission": "not_granted",
        "training_row_emitted": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }


def build(
    *,
    resolution_path: Path,
    corpus_path: Path,
    layered_path: Path,
    strong_paths_path: Path,
    strong_summary_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    resolution = _jsonl(resolution_path)
    corpus = _jsonl(corpus_path)
    layered = _jsonl(layered_path)
    strong_paths = _strong_paths(strong_paths_path)
    strong_summary = json.loads(strong_summary_path.read_text(encoding="utf-8"))

    by_hash: dict[str, dict[str, Any]] = {}
    by_source_path: dict[str, dict[str, Any]] = {}
    for row in corpus:
        sha = str(row.get("content_sha256") or "")
        source_path = str(row.get("source_path") or "")
        if len(sha) != 64 or not source_path:
            raise ValueError("corpus manifest contains an incomplete source identity")
        by_hash.setdefault(sha, row)
        by_source_path[source_path] = row

    layer_by_hash = {str(row.get("content_sha256")): row for row in layered}
    processing = []
    for row in resolution:
        sha = str(row.get("content_sha256") or "")
        layer = str(row.get("primary_layer") or "")
        source_path = str(row.get("source_path") or "")
        if layer not in PROCESSING_LAYERS or len(sha) != 64 or not source_path:
            raise ValueError("resolution authority row is not a complete Processing source row")
        corpus_row = by_hash.get(sha)
        if corpus_row is None or str(corpus_row.get("source_path")) != source_path:
            raise ValueError(f"resolution/corpus source identity mismatch: {sha}")
        processing.append({
            **_base(row, pool="processing", source_path=source_path, source_sha=sha),
            "resolution_record_id": row.get("record_id", ""),
            "operator_evidence": row.get("screening_literal_operator_ids", []),
        })

    if len(processing) != 8466 or len({row["source_sha256"] for row in processing}) != 8466:
        raise ValueError("Processing authority must contain 8,466 unique source rows")

    # Strong paths identify the exact 80,998 strong-signal hashes.  Filtering
    # the broad layer by this set gives the contractual 39,386 API rows.
    strong_hashes = {
        str(by_source_path[path].get("content_sha256"))
        for path in strong_paths
        if path in by_source_path
    }
    api = []
    for sha, row in layer_by_hash.items():
        if row.get("primary_layer") != "low_level_pyqgis_api_candidate" or sha not in strong_hashes:
            continue
        corpus_row = by_hash.get(sha)
        if corpus_row is None:
            raise ValueError(f"layer/corpus source identity mismatch: {sha}")
        source_row = {
            **row,
            "source_root_id": corpus_row.get("source_root_id", ""),
            "relative_path": corpus_row.get("relative_path", ""),
            "screening_tier": corpus_row.get("screening_tier", row.get("screening_tier", "")),
            "parse_status": corpus_row.get("parse_status", row.get("parse_status", "")),
        }
        api.append({
            **_base(source_row, pool="api", source_path=str(corpus_row["source_path"]), source_sha=sha),
            "api_evidence": row.get("reason_codes", []),
        })
    api.sort(key=lambda row: row["source_sha256"])
    if len(api) != 39386 or len({row["source_sha256"] for row in api}) != 39386:
        raise ValueError(f"API strong-signal authority must contain 39,386 rows, got {len(api)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    processing_path = output_dir / "processing_source_manifest_v1.jsonl"
    api_path = output_dir / "api_source_manifest_v1.jsonl"
    _write_jsonl(processing_path, processing)
    _write_jsonl(api_path, api)
    summary = {
        "schema": "gis_recommend.qgis_full_authority_manifest_summary.v1",
        "processing_rows": len(processing),
        "processing_unique_source_sha256": len({row["source_sha256"] for row in processing}),
        "api_rows": len(api),
        "api_unique_source_sha256": len({row["source_sha256"] for row in api}),
        "api_broad_layer_rows": sum(row.get("primary_layer") == "low_level_pyqgis_api_candidate" for row in layered),
        "strong_signal_expected_api_rows": int(strong_summary["primary_layer_counts"]["low_level_pyqgis_api_candidate"]),
        "strong_signal_path_count": int(strong_summary["strong_signal_path_count"]),
        "source_disjoint_ready": False,
        "task_boundary_ready": False,
        "l3_mapping_ready": False,
        "description_fidelity_ready": False,
        "dedup_ready": False,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_manifest_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
        "layer_counts": dict(sorted(Counter(row["primary_layer"] for row in processing).items())),
    }
    summary_path = output_dir / "summary_v1.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    hash_path = output_dir / "hash_ledger_v1.json"
    hash_path.write_text(json.dumps({
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {name: {"path": str(path), "sha256": _sha256(path)} for name, path in {
            "resolution": resolution_path, "corpus": corpus_path, "layered": layered_path,
            "strong_paths": strong_paths_path, "strong_summary": strong_summary_path,
        }.items()},
        "artifacts": {path.name: _sha256(path) for path in (processing_path, api_path, summary_path)},
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resolution", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--layered", type=Path, required=True)
    parser.add_argument("--strong-paths", type=Path, required=True)
    parser.add_argument("--strong-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(
        resolution_path=args.resolution,
        corpus_path=args.corpus,
        layered_path=args.layered,
        strong_paths_path=args.strong_paths,
        strong_summary_path=args.strong_summary,
        output_dir=args.output_dir,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
