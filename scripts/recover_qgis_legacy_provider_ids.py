#!/usr/bin/env python3
"""Recover legacy ``qgis:*`` IDs only when the same ``native:*`` slug exists."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gis_recommend.data.qgis_conversion_features import extract_conversion_features
from gis_recommend.data.qgis_conversion_rules import route_candidate


SCHEMA = "gis_recommend.qgis_legacy_provider_recovery.v1"

PROVIDER_VERSION_ALIASES = {
    "gdalogr": ("gdal", "gdalogr_to_gdal_same_slug"),
    "grass": ("grass7", "grass_to_grass7_same_slug"),
    "sagang": ("saga", "sagang_to_saga_same_slug"),
}

REVIEWED_LEGACY_SLUG_ALIASES = {
    "native:modelerrastercalc": "qgis:rastercalculator",
    "native:rastercalc": "qgis:rastercalculator",
    "native:voronoipolygons": "qgis:voronoipolygons",
    "qgis:fixeddistancebuffer": "native:buffer",
}

REVIEWED_PROVIDER_EQUIVALENTS = {
    "aerodromeutilities:polygontosinglepart": "native:multiparttosingleparts",
    "gdal:mergevectorlayers": "native:mergevectorlayers",
    "gdalogr:clipvectorsbyextent": "gdal:clipvectorbyextent",
    "geodyntools:retainfields": "native:retainfields",
    "gmlas:convertformat_gmlas": "gdal:convertformat",
    "ladm_col:fieldcalculatorforinputlayer": "native:fieldcalculator",
    "ladm_col:polygonstolines": "native:polygonstolines",
    "native: zonalhistogram": "native:zonalhistogram",
    "native:basicstatisticsforfields": "qgis:basicstatisticsforfields",
    "native:checkvalidity": "qgis:checkvalidity",
    "native:cliprasterbyextent": "gdal:cliprasterbyextent",
    "native:delaunaytriangulation": "qgis:delaunaytriangulation",
    "native:joinattributesbylocationsummary": "qgis:joinbylocationsummary",
    "native:joinbylocationsummary": "qgis:joinbylocationsummary",
    "native:minimumboundinggeometry": "qgis:minimumboundinggeometry",
    "native:removeduplicategeometries": "native:deleteduplicategeometries",
    "qgis.fieldcalculator": "native:fieldcalculator",
    "qgis:cliprasterbymasklayer": "gdal:cliprasterbymasklayer",
    "qgis:polygoncentroids": "native:centroids",
    "qgis:applylayerstyle": "native:setlayerstyle",
    "qgis:vectorgrid": "native:creategrid",
    "saga:polygonunion": "native:union",
    "sagang:polygonunion": "native:union",
    "sagang:vectorizingrasterclasses": "gdal:polygonize",
    "script:copernicusrastercalculator": "qgis:rastercalculator",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def load_catalog_ids(path: Path) -> set[str]:
    operator_ids: set[str] = set()
    with path.open(encoding="utf-8-sig", errors="replace", newline="") as handle:
        for row in csv.reader(handle):
            if len(row) > 5 and ":" in row[5]:
                operator_ids.add(row[5].strip().lower())
    if not operator_ids:
        raise ValueError(f"no provider-qualified operator IDs found in {path}")
    return operator_ids


def canonicalize_operator_id(
    operator_id: str, catalog_ids: set[str]
) -> tuple[str | None, str]:
    normalized = operator_id.strip().lower()
    if normalized in catalog_ids:
        return normalized, "catalog_exact"
    reviewed = REVIEWED_LEGACY_SLUG_ALIASES.get(normalized)
    if reviewed in catalog_ids:
        return reviewed, "reviewed_legacy_slug_alias"
    equivalent = REVIEWED_PROVIDER_EQUIVALENTS.get(normalized)
    if equivalent in catalog_ids:
        return equivalent, "reviewed_provider_equivalent"
    if normalized.startswith("qgis:"):
        candidate = "native:" + normalized.split(":", 1)[1]
        if candidate in catalog_ids:
            return candidate, "qgis_to_native_same_slug"
    provider, separator, slug = normalized.partition(":")
    alias = PROVIDER_VERSION_ALIASES.get(provider)
    if separator and alias:
        target_provider, rule = alias
        candidate = f"{target_provider}:{slug}"
        if candidate in catalog_ids:
            return candidate, rule
    return None, "unresolved"


def _literal_call_sites(source_text: str) -> list[dict[str, Any]]:
    tree = ast.parse(source_text)
    sites: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        is_run = (
            isinstance(node.func, ast.Name) and node.func.id == "run"
        ) or (
            isinstance(node.func, ast.Attribute) and node.func.attr == "run"
        )
        operator = node.args[0]
        if (
            not is_run
            or not isinstance(operator, ast.Constant)
            or not isinstance(operator.value, str)
            or not operator.value.strip()
        ):
            continue
        sites.append(
            {
                "operator_id": operator.value.strip(),
                "line_start": node.lineno,
                "line_end": node.end_lineno or node.lineno,
            }
        )
    return sorted(sites, key=lambda site: (site["line_start"], site["line_end"]))


def recover_row(row: dict[str, Any], catalog_ids: set[str]) -> dict[str, Any]:
    source_path = Path(str(row.get("source_path") or ""))
    base = {
        "schema": SCHEMA,
        "record_id": str(row.get("content_sha256") or "")[:24],
        "content_sha256": str(row.get("content_sha256") or ""),
        "source_sha256": str(row.get("content_sha256") or ""),
        "source_root_id": row.get("source_root_id"),
        "relative_path": row.get("relative_path"),
        "source_path": str(source_path),
        "original_operator_ids": row.get("screening_literal_operator_ids") or [],
        "catalog_miss_ids": row.get("catalog_miss_ids") or [],
        "training_admission": "not_granted_recovery_rule_only",
        "training_row_emitted": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    original_ids = [str(value).strip().lower() for value in base["original_operator_ids"]]
    resolutions = [canonicalize_operator_id(value, catalog_ids) for value in original_ids]
    canonical_ids = [value for value, _ in resolutions if value]
    unresolved = [
        original
        for original, (canonical, _) in zip(original_ids, resolutions)
        if canonical is None
    ]
    migrated = [
        {"source": original, "target": canonical, "rule": rule}
        for original, (canonical, rule) in zip(original_ids, resolutions)
        if canonical is not None and rule != "catalog_exact"
    ]
    if not unresolved:
        normalization_status = "fully_normalized"
    elif canonical_ids:
        normalization_status = "partially_normalized"
    else:
        normalization_status = "unresolved"
    base.update(
        {
            "normalization_status": normalization_status,
            "canonical_operator_ids": canonical_ids,
            "unresolved_operator_ids": list(dict.fromkeys(unresolved)),
            "provider_migrations": migrated,
        }
    )
    if unresolved:
        base.update(
            {
                "structure_action": "defer_operator_resolution",
                "structure_rule_id": "defer-unresolved-provider-id-v1",
                "action": "defer_operator_resolution",
                "rule_id": "defer-unresolved-provider-id-v1",
                "operator_ids": canonical_ids,
                "ordered_operator_ids": canonical_ids,
                "call_sites": [],
                "dependency_edges": [],
                "structure_evidence": {},
            }
        )
        return base
    if not source_path.is_file() or _sha256(source_path) != base["content_sha256"]:
        base.update(
            {
                "structure_action": "exclude_source_authority_failure",
                "structure_rule_id": "reject-source-authority-v1",
                "action": "exclude_source_authority_failure",
                "rule_id": "reject-source-authority-v1",
                "operator_ids": canonical_ids,
                "ordered_operator_ids": canonical_ids,
                "call_sites": [],
                "dependency_edges": [],
                "structure_evidence": {},
            }
        )
        return base

    source_text = source_path.read_text(encoding="utf-8-sig", errors="replace")
    literal_sites = _literal_call_sites(source_text)
    extracted = extract_conversion_features(
        source_text, call_sites=literal_sites
    )
    features = dict(extracted.data)
    extracted_ids = [str(value).strip().lower() for value in features["operator_ids"]]
    if extracted_ids != original_ids:
        base.update(
            {
                "structure_action": "exclude_candidate_alignment_failure",
                "structure_rule_id": "reject-candidate-alignment-v1",
                "action": "exclude_candidate_alignment_failure",
                "rule_id": "reject-candidate-alignment-v1",
                "operator_ids": canonical_ids,
                "ordered_operator_ids": canonical_ids,
                "call_sites": literal_sites,
                "dependency_edges": features.get("dependency_edges") or [],
                "structure_evidence": {
                    "screening_operator_ids": original_ids,
                    "extracted_operator_ids": extracted_ids,
                },
            }
        )
        return base
    features["operator_ids"] = canonical_ids
    route_input = {
        "mapped_l3_chain": ["L3_PENDING"] * len(canonical_ids),
        "call_graph_status": (
            "disconnected_candidate_scopes"
            if features.get("workflow_unit_scope") == "cross_scope_candidate"
            else "single_scope"
        ),
        "api_pattern_calls": [],
    }
    decision = route_candidate(route_input, features)
    canonical_sites = [
        {**site, "operator_id": canonical}
        for site, canonical in zip(literal_sites, canonical_ids)
    ]
    base.update(
        {
            "structure_action": decision.action,
            "structure_rule_id": decision.rule_id,
            "action": decision.action,
            "rule_id": decision.rule_id,
            "operator_ids": canonical_ids,
            "ordered_operator_ids": canonical_ids,
            "call_sites": canonical_sites,
            "dependency_edges": features.get("dependency_edges") or [],
            "dependency_edge_evidence": features.get("dependency_edge_evidence") or [],
            "workflow_unit_scope": features.get("workflow_unit_scope"),
            "structure_evidence": decision.evidence,
            "feature_signature_hash": extracted.signature_hash,
        }
    )
    return base


def build_recovery(
    census_path: Path, catalog_ids: set[str]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    inputs = [
        row
        for row in _load_jsonl(census_path)
        if row.get("primary_layer") == "explicit_processing_catalog_miss"
    ]
    rows = [recover_row(row, catalog_ids) for row in inputs]
    statuses = Counter(row["normalization_status"] for row in rows)
    actions = Counter(row["structure_action"] for row in rows)
    fully = [row for row in rows if row["normalization_status"] == "fully_normalized"]
    summary = {
        "schema": f"{SCHEMA}.summary",
        "input_catalog_miss_records": len(inputs),
        "fully_normalized_records": statuses["fully_normalized"],
        "partially_normalized_records": statuses["partially_normalized"],
        "unresolved_records": statuses["unresolved"],
        "fully_normalized_multistep_records": sum(
            len(row["canonical_operator_ids"]) >= 2 for row in fully
        ),
        "provider_migration_pairs": dict(
            sorted(
                Counter(
                    f"{item['source']} -> {item['target']}"
                    for row in rows
                    for item in row["provider_migrations"]
                ).items(),
                key=lambda item: (-item[1], item[0]),
            )
        ),
        "structure_action_counts": dict(sorted(actions.items())),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_recovery_rule_only",
        "next_gate": "apply stable101 L3 mapping and source-disjoint fidelity audit",
    }
    return rows, summary


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def write_outputs(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    census_path: Path,
    catalog_path: Path,
    output_dir: Path,
) -> None:
    ledger_path = output_dir / "legacy_provider_recovery_v1.jsonl"
    summary_path = output_dir / "summary_v1.json"
    report_path = output_dir / "report_v1.md"
    hash_path = output_dir / "hash_ledger_v1.json"
    _atomic_write(
        ledger_path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
    )
    _atomic_write(
        summary_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    report = [
        "# QGIS Legacy Provider Recovery v1",
        "",
        f"- Catalog-miss records: {summary['input_catalog_miss_records']}",
        f"- Fully normalized: {summary['fully_normalized_records']}",
        f"- Fully normalized multistep: {summary['fully_normalized_multistep_records']}",
        "- Training rows emitted: 0",
        "",
        "## Structure Routing",
        "",
        "| Action | Records |",
        "|---|---:|",
        *[
            f"| {action} | {count} |"
            for action, count in summary["structure_action_counts"].items()
        ],
        "",
    ]
    _atomic_write(report_path, "\n".join(report))
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            census_path.name: _sha256(census_path),
            catalog_path.name: _sha256(catalog_path),
        },
        "artifacts": {
            path.name: _sha256(path)
            for path in (ledger_path, summary_path, report_path)
        },
    }
    _atomic_write(
        hash_path,
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--census", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows, summary = build_recovery(args.census, load_catalog_ids(args.catalog))
    write_outputs(
        rows,
        summary,
        census_path=args.census,
        catalog_path=args.catalog,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
