"""Normalize report-only DataTrove deduplication evidence for QGIS sources."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from gis_recommend.data.qgis_source_authority import (
    normalized_source_body,
    source_authority,
)

SCHEMA = "gis_recommend.qgis_datatrove_sidecar.v1"


@dataclass(frozen=True)
class MinHashSidecarConfig:
    threshold: float = 0.8
    ngram_size: int = 5
    num_buckets: int = 8
    hashes_per_bucket: int = 10
    seed: int = 1
    tokenizer: str = "qgis_source_code_regex_v1"
    precision: int = 64
    hash_function: str = "sha1"

    def __post_init__(self) -> None:
        if not 0 < self.threshold <= 1:
            raise ValueError("threshold must be in (0, 1]")
        for field in ("ngram_size", "num_buckets", "hashes_per_bucket", "precision"):
            if getattr(self, field) <= 0:
                raise ValueError(f"{field} must be positive")
        if self.precision not in (32, 64):
            raise ValueError("precision must be 32 or 64")
        if self.hash_function not in ("sha1", "xxhash"):
            raise ValueError("hash_function must be sha1 or xxhash")
        if self.tokenizer != "qgis_source_code_regex_v1":
            raise ValueError("unsupported tokenizer")

    def to_report(self) -> dict[str, Any]:
        values = asdict(self)
        precision = values.pop("precision")
        hash_function = values.pop("hash_function")
        values["hash_config"] = {
            "precision": precision,
            "hash_function": hash_function,
        }
        values["lsh_inflection_threshold"] = (1 / self.num_buckets) ** (
            1 / self.hashes_per_bucket
        )
        return values


def _required_text(row: Mapping[str, Any], field: str) -> str:
    value = str(row.get(field) or "").strip()
    if not value:
        raise ValueError(f"{field} is required")
    return value


def build_datatrove_input(
    manifest_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    """Build stable DataTrove input rows from the authority normalization."""
    documents: list[dict[str, str]] = []
    seen: set[str] = set()
    for manifest_row in manifest_rows:
        record_id = _required_text(manifest_row, "record_id")
        if record_id in seen:
            raise ValueError(f"duplicate record_id {record_id}")
        seen.add(record_id)
        source_path = Path(_required_text(manifest_row, "source_path"))
        source_sha256 = _required_text(manifest_row, "source_sha256")
        body = normalized_source_body(source_path)
        authority = source_authority(source_path, source_sha256=source_sha256)
        documents.append(
            {
                "record_id": record_id,
                "source_path": str(source_path),
                "source_sha256": source_sha256,
                "normalized_source_body_sha256": authority[
                    "normalized_source_body_sha256"
                ],
                "text": body,
            }
        )
    return sorted(documents, key=lambda row: row["record_id"])


def _authority_clusters(documents: Sequence[Mapping[str, str]]) -> list[list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for row in documents:
        grouped[row["normalized_source_body_sha256"]].append(row["record_id"])
    return sorted(
        (sorted(record_ids) for record_ids in grouped.values() if len(record_ids) > 1),
        key=lambda cluster: tuple(cluster),
    )


def _normalize_clusters(
    clusters: Sequence[Sequence[str]], *, known_ids: set[str], field: str
) -> list[list[str]]:
    normalized: list[list[str]] = []
    assigned: set[str] = set()
    for cluster in clusters:
        members = sorted({str(record_id).strip() for record_id in cluster})
        if len(members) < 2:
            continue
        unknown = set(members) - known_ids
        if unknown:
            raise ValueError(f"{field} contains unknown record ids: {sorted(unknown)}")
        overlap = assigned.intersection(members)
        if overlap:
            raise ValueError(f"{field} assigns records to multiple clusters: {sorted(overlap)}")
        assigned.update(members)
        normalized.append(members)
    return sorted(normalized, key=lambda cluster: tuple(cluster))


def normalize_datatrove_report(
    documents: Sequence[Mapping[str, str]],
    *,
    datatrove_version: str,
    datatrove_exact_clusters: Sequence[Sequence[str]],
    datatrove_minhash_clusters: Sequence[Sequence[str]],
    config: MinHashSidecarConfig,
) -> dict[str, Any]:
    """Validate exact groups and normalize MinHash evidence without filtering rows."""
    version = datatrove_version.strip()
    if not version:
        raise ValueError("datatrove_version is required")
    stable_documents = sorted(
        (dict(row) for row in documents), key=lambda row: row["record_id"]
    )
    known_ids = {row["record_id"] for row in stable_documents}
    if len(known_ids) != len(stable_documents):
        raise ValueError("document record_id values must be unique")

    authority_clusters = _authority_clusters(stable_documents)
    exact_clusters = _normalize_clusters(
        datatrove_exact_clusters, known_ids=known_ids, field="exact clusters"
    )
    if exact_clusters != authority_clusters:
        raise ValueError(
            "exact clusters do not reconcile with normalized source body authority"
        )
    minhash_clusters = _normalize_clusters(
        datatrove_minhash_clusters, known_ids=known_ids, field="minhash clusters"
    )

    return {
        "schema": SCHEMA,
        "datatrove_version": version,
        "document_count": len(stable_documents),
        "documents": stable_documents,
        "config": config.to_report(),
        "exact_reconciliation": {
            "authority_clusters": authority_clusters,
            "datatrove_clusters": exact_clusters,
            "matched": True,
        },
        "minhash_clusters": minhash_clusters,
        "minhash_report_only": True,
        "minhash_removed_record_ids": [],
        "authority_mutated": False,
        "training_admission": "not_granted_external_analysis_pilot_only",
        "training_rows_emitted": 0,
    }


def write_normalized_report(path: Path, report: Mapping[str, Any]) -> None:
    """Write canonical JSON atomically after complete serialization succeeds."""
    payload = json.dumps(
        report, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".partial")
    partial.write_text(payload, encoding="utf-8", newline="\n")
    partial.replace(path)
