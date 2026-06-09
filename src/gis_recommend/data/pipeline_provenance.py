# -*- coding: utf-8 -*-
"""Provenance helpers for binding pipeline outputs to mapping inputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PROVENANCE_SCHEMA = "gis_recommend.pipeline_provenance.v1"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def build_pipeline_provenance(id_mappings_path: Path, skip_list_path: Path | None = None) -> dict[str, Any]:
    """Return a stable provenance block for the mapping inputs used by Step6+."""
    id_mappings_path = Path(id_mappings_path)
    mapping_data = _load_json(id_mappings_path)
    metadata = mapping_data.get("metadata", {}) or {}
    l3_map = mapping_data.get("l3", {}) or {}
    mapping_metadata = mapping_data.get("mapping_metadata", {}) or {}
    gee_to_l3 = mapping_metadata.get("gee_to_l3", {}) or {}
    qgis_to_l3 = mapping_metadata.get("qgis_to_l3", {}) or {}

    provenance: dict[str, Any] = {
        "schema": PROVENANCE_SCHEMA,
        "id_mappings": {
            "path": str(id_mappings_path.resolve()),
            "sha256": file_sha256(id_mappings_path),
            "version": metadata.get("version"),
            "l3_vocab_size": len(l3_map),
            "metadata_l3_vocab_size": metadata.get("l3_vocab_size"),
            "gee_to_l3_count": sum(1 for meta in gee_to_l3.values() if meta.get("primary_l3")),
            "gee_to_l3_total": len(gee_to_l3),
            "qgis_to_l3_count": len(qgis_to_l3),
        },
        "gee_skip_list": {
            "path": None,
            "sha256": None,
            "version": None,
            "skip_operator_count": 0,
        },
    }

    if skip_list_path:
        skip_list_path = Path(skip_list_path)
        if skip_list_path.exists():
            skip_data = _load_json(skip_list_path)
            provenance["gee_skip_list"] = {
                "path": str(skip_list_path.resolve()),
                "sha256": file_sha256(skip_list_path),
                "version": skip_data.get("version") or (skip_data.get("metadata", {}) or {}).get("version"),
                "skip_operator_count": len(skip_data.get("skip_operators", []) or []),
            }

    return provenance


def provenance_warnings(
    provenance: dict[str, Any] | None,
    id_mappings_path: Path | None,
    skip_list_path: Path | None = None,
    require: bool = True,
) -> list[str]:
    """Compare a provenance block to current mapping inputs and return warning codes."""
    if not provenance:
        return ["missing_provenance"] if require else []
    warnings: list[str] = []
    if provenance.get("schema") != PROVENANCE_SCHEMA:
        warnings.append("provenance_schema_mismatch")

    if not id_mappings_path:
        return warnings

    current = build_pipeline_provenance(id_mappings_path, skip_list_path)
    comparisons = (
        ("id_mappings.sha256", ("id_mappings", "sha256")),
        ("id_mappings.version", ("id_mappings", "version")),
        ("id_mappings.l3_vocab_size", ("id_mappings", "l3_vocab_size")),
        ("id_mappings.gee_to_l3_count", ("id_mappings", "gee_to_l3_count")),
        ("id_mappings.gee_to_l3_total", ("id_mappings", "gee_to_l3_total")),
        ("gee_skip_list.sha256", ("gee_skip_list", "sha256")),
        ("gee_skip_list.skip_operator_count", ("gee_skip_list", "skip_operator_count")),
    )
    for warning_name, (section, key) in comparisons:
        expected = current.get(section, {}).get(key)
        actual = provenance.get(section, {}).get(key)
        if actual != expected:
            warnings.append(f"provenance_mismatch:{warning_name}")
    return warnings


def validate_pipeline_provenance(
    provenance: dict[str, Any] | None,
    id_mappings_path: Path | None,
    skip_list_path: Path | None = None,
    require: bool = True,
) -> list[str]:
    """Return provenance warning codes; never gate execution."""
    return provenance_warnings(provenance, id_mappings_path, skip_list_path, require=require)
