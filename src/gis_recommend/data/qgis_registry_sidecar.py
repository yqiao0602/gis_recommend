"""Normalize QGIS Registry snapshots and compare them to catalog authority."""

# Schema validation intentionally exposes one ValueError contract for bad payloads.
# ruff: noqa: TRY004

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

REGISTRY_SCHEMA = "gis_recommend.qgis_registry_export.v1"
COMPARISON_SCHEMA = "gis_recommend.qgis_registry_comparison.v1"


def _objects(value: Any, *, field: str) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field} must be a sequence")
    result: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError(f"{field} contains a non-object")
        result.append(deepcopy(dict(item)))
    return result


def _required_text(row: Mapping[str, Any], field: str) -> str:
    value = str(row.get(field) or "").strip()
    if not value:
        raise ValueError(f"{field} is required")
    return value


def normalize_registry_snapshot(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Return one deterministic, source-preserving Registry snapshot."""
    if raw.get("schema") != REGISTRY_SCHEMA:
        raise ValueError(f"schema must be {REGISTRY_SCHEMA}")
    qgis_version = _required_text(raw, "qgis_version")
    image_digest = _required_text(raw, "image_digest")
    exporter_sha256 = _required_text(raw, "exporter_sha256")

    providers: list[dict[str, Any]] = []
    seen_providers: set[str] = set()
    seen_operators: set[str] = set()
    for provider in _objects(raw.get("providers", []), field="providers"):
        provider_id = _required_text(provider, "provider_id").lower()
        if provider_id in seen_providers:
            raise ValueError(f"duplicate provider_id {provider_id}")
        seen_providers.add(provider_id)
        algorithms: list[dict[str, Any]] = []
        for algorithm in _objects(provider.get("algorithms", []), field="algorithms"):
            operator_id = _required_text(algorithm, "operator_id").lower()
            if operator_id in seen_operators:
                raise ValueError(f"duplicate operator_id {operator_id}")
            if operator_id.split(":", 1)[0] != provider_id:
                raise ValueError(f"operator {operator_id} does not belong to {provider_id}")
            seen_operators.add(operator_id)
            parameters = sorted(
                _objects(algorithm.get("parameters", []), field="parameters"),
                key=lambda item: (_required_text(item, "name"), str(item.get("type") or "")),
            )
            outputs = sorted(
                _objects(algorithm.get("outputs", []), field="outputs"),
                key=lambda item: (_required_text(item, "name"), str(item.get("type") or "")),
            )
            algorithms.append(
                {
                    "operator_id": operator_id,
                    "display_name": _required_text(algorithm, "display_name"),
                    "parameters": parameters,
                    "outputs": outputs,
                }
            )
        providers.append(
            {
                "provider_id": provider_id,
                "name": _required_text(provider, "name"),
                "active": bool(provider.get("active")),
                "version": str(provider.get("version") or "unknown"),
                "algorithms": sorted(
                    algorithms, key=lambda item: item["operator_id"]
                ),
            }
        )

    return {
        "schema": REGISTRY_SCHEMA,
        "qgis_version": qgis_version,
        "image_digest": image_digest,
        "exporter_sha256": exporter_sha256,
        "providers": sorted(providers, key=lambda item: item["provider_id"]),
    }


def _coarse_type(type_name: str, *, output: bool) -> str:
    lowered = type_name.lower()
    if "raster" in lowered:
        return "raster"
    if any(token in lowered for token in ("source", "vector", "feature", "sink")):
        return "vector"
    if any(token in lowered for token in ("crs", "extent", "point", "geometry")):
        return "geographicData"
    if output and any(token in lowered for token in ("file", "folder")):
        return "geographicData"
    return "LiteralData"


def _registry_contract(algorithm: Mapping[str, Any]) -> tuple[set[str], set[str]]:
    inputs = {
        _coarse_type(str(parameter.get("type") or ""), output=False)
        for parameter in algorithm["parameters"]
    }
    outputs = {
        _coarse_type(str(output.get("type") or ""), output=True)
        for output in algorithm["outputs"]
    }
    return inputs, outputs


def compare_registry_to_catalog(
    snapshot: Mapping[str, Any], catalog: Mapping[str, Any]
) -> dict[str, Any]:
    """Create a report-only catalog delta without mutating either input."""
    normalized = normalize_registry_snapshot(snapshot)
    providers = {
        provider["provider_id"]: provider for provider in normalized["providers"]
    }
    algorithms = {
        algorithm["operator_id"]: algorithm
        for provider in normalized["providers"]
        for algorithm in provider["algorithms"]
    }

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in sorted(
        _objects(catalog.get("operators", []), field="operators"),
        key=lambda item: str(item.get("operator_id") or "").lower(),
    ):
        operator_id = _required_text(entry, "operator_id").lower()
        if operator_id in seen:
            raise ValueError(f"duplicate catalog operator_id {operator_id}")
        seen.add(operator_id)
        provider_id = str(entry.get("provider") or operator_id.split(":", 1)[0]).lower()
        provider = providers.get(provider_id)
        algorithm = algorithms.get(operator_id)
        expected_version = str(entry.get("expected_provider_version") or "")
        reasons: list[str] = []

        if provider is None or not provider["active"]:
            status = "provider_not_installed"
            reasons.append("provider_missing_or_inactive")
        elif expected_version and provider["version"] != expected_version:
            status = "provider_version_mismatch"
            reasons.append(
                f"expected={expected_version};actual={provider['version']}"
            )
        elif algorithm is None:
            status = "operator_not_found"
            reasons.append("operator_absent_from_registry")
        else:
            registry_inputs, registry_outputs = _registry_contract(algorithm)
            catalog_inputs = {str(value) for value in entry.get("input_types", [])}
            catalog_outputs = {str(value) for value in entry.get("output_types", [])}
            if registry_inputs != catalog_inputs or registry_outputs != catalog_outputs:
                status = "catalog_contract_mismatch"
                reasons.append(
                    "catalog_types_do_not_equal_registry_parameter_types"
                )
            else:
                status = "matched"

        rows.append(
            {
                "operator_id": operator_id,
                "provider_id": provider_id,
                "status": status,
                "reasons": reasons,
                "registry_provider_version": provider["version"] if provider else None,
            }
        )

    counts = Counter(row["status"] for row in rows)
    return {
        "schema": COMPARISON_SCHEMA,
        "qgis_version": normalized["qgis_version"],
        "catalog_operator_count": len(rows),
        "status_counts": dict(sorted(counts.items())),
        "operators": rows,
        "authority_mutated": False,
        "training_rows_emitted": 0,
    }
