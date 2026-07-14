#!/usr/bin/env python3
"""Build the reviewed 114-class QGIS taxonomy as non-default artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


PROFILE = "qgis_l3_v1_114_experimental"
INVALID_107_PROFILE = "v3_107_experimental"
PARENT_METADATA_OVERRIDES: dict[str, dict[str, str]] = {
    "L1_06": {
        "name": "3D and TIN Analysis",
        "reason": (
            "The legacy 350-class registry leaves l1_name blank for all L1_06 rows; "
            "the experimental taxonomy reactivates legacy Delaunay Triangulation."
        ),
        "scope": "qgis_l3_v1_114_experimental_only",
    }
}

ADDITIONS: tuple[dict[str, Any], ...] = (
    {"code": "L3_01_03_05", "name": "Attribute Table Join", "definition": "Joins fields from a non-spatial or spatial table to features using a shared key without applying a spatial predicate.", "source": "new", "aliases": ["native:joinattributestable", "qgis:joinattributestable"]},
    {"code": "L3_01_05_01", "name": "Check Geometry", "source": "legacy", "aliases": ["qgis:checkvalidity", "native:checkvalidity"]},
    {"code": "L3_01_05_02", "name": "Repair Geometry", "source": "legacy", "aliases": ["native:fixgeometries", "qgis:fixgeometries"]},
    {"code": "L3_01_05_04", "name": "Delete Identical", "source": "legacy", "aliases": ["native:deleteduplicategeometries", "qgis:deleteduplicategeometries"]},
    {"code": "L3_01_07_01", "name": "Add Spatial Index", "source": "legacy", "aliases": ["native:createspatialindex"]},
    {"code": "L3_01_09_06", "name": "Rasterize Vector", "definition": "Converts vector geometries and selected attributes into raster cells on a defined grid.", "source": "new", "aliases": ["gdal:rasterize", "gdal:rasterize_over"]},
    {"code": "L3_01_09_07", "name": "Polygonize Raster", "definition": "Converts contiguous raster regions into vector polygon features while preserving raster values as attributes.", "source": "new", "aliases": ["gdal:polygonize", "native:polygonize", "native:pixelstopolygons"]},
    {"code": "L3_01_10_01", "name": "Project/Reproject", "source": "legacy", "aliases": ["native:reprojectlayer", "qgis:reprojectlayer"]},
    {"code": "L3_01_10_02", "name": "Define Projection", "source": "legacy", "aliases": ["native:assignprojection", "gdal:assignprojection"]},
    {"code": "L3_02_03_06", "name": "Vector Grid Generation", "definition": "Creates a vector fishnet, rectangular, diamond, hexagonal, or regular-point grid over an extent.", "source": "new", "aliases": ["native:creategrid", "qgis:creategrid", "qgis:regularpoints"]},
    {"code": "L3_02_05_01", "name": "Simplify", "source": "legacy", "aliases": ["native:simplifygeometries", "qgis:simplifygeometries", "grass7:v.generalize"]},
    {"code": "L3_02_05_02", "name": "Smooth", "source": "legacy", "aliases": ["native:smoothgeometry", "qgis:smoothgeometry"]},
    {"code": "L3_02_05_13", "name": "Delete Holes", "definition": "Removes interior polygon rings below a threshold or removes all holes from polygon geometries.", "source": "new", "aliases": ["native:deleteholes", "qgis:deleteholes"]},
    {"code": "L3_02_05_14", "name": "Concave Hull", "definition": "Creates a concave enclosing polygon that follows the shape of input features more closely than a convex hull.", "source": "new", "aliases": ["native:concavehull", "qgis:concavehull", "qgis:knearestconcavehull"]},
    {"code": "L3_02_05_15", "name": "Extract Vertices", "definition": "Creates point features for all or selected vertices of input geometries, preserving source and vertex indices.", "source": "new", "aliases": ["native:extractvertices", "native:extractspecificvertices", "qgis:extractvertices", "qgis:extractspecificvertices"]},
    {"code": "L3_02_07_02", "name": "Feature to Polygon", "source": "legacy", "aliases": ["qgis:linestopolygons"]},
    {"code": "L3_02_07_03", "name": "Polygon to Line", "source": "legacy", "aliases": ["native:polygonstolines", "qgis:polygonstolines", "saga:convertpolygonstolines"]},
    {"code": "L3_02_07_07", "name": "Create Thiessen Polygons", "source": "legacy", "aliases": ["qgis:voronoipolygons", "native:voronoipolygons", "grass7:v.voronoi", "saga:thiessenpolygons"]},
    {"code": "L3_02_07_09", "name": "Snap", "source": "legacy", "aliases": ["native:snapgeometries", "qgis:snapgeometries", "native:snappointstogrid", "qgis:snappointstogrid"]},
    {"code": "L3_06_01_02", "name": "Delaunay Triangulation", "source": "legacy", "aliases": ["qgis:delaunaytriangulation", "grass7:v.delaunay"]},
)

INVALID_107_SEMANTICS: tuple[tuple[int, str, str, str], ...] = (
    (94, "L3_02_01_02", "Reproject", "L3_01_10_01"),
    (95, "L3_02_01_03", "Fix Geometries", "L3_01_05_02"),
    (96, "L3_02_03_01", "Grid", "L3_02_03_06"),
    (97, "L3_02_03_02", "Simplify", "L3_02_05_01"),
    (98, "L3_02_03_03", "Voronoi", "L3_02_07_07"),
    (99, "L3_02_03_04", "Delaunay Triangulation", "L3_06_01_02"),
    (100, "L3_02_05_01", "Delete Duplicate", "L3_01_05_04"),
    (101, "L3_02_05_02", "Snap", "L3_02_07_09"),
    (102, "L3_02_05_03", "Delete Holes", "L3_02_05_13"),
    (103, "L3_02_05_04", "Smooth", "L3_02_05_02"),
    (104, "L3_02_05_05", "Concave Hull", "L3_02_05_14"),
    (105, "L3_02_07_02", "Polygons to Lines", "L3_02_07_03"),
    (106, "L3_02_07_03", "Extract Vertices", "L3_02_05_15"),
)


def _load_legacy_hierarchy(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            code = (
                row.get("l3_code")
                or row.get("L3 ID")
                or row.get("l3_id")
                or row.get("L3_ID")
                or ""
            ).strip()
            if code:
                if code in rows:
                    raise ValueError(f"duplicate legacy hierarchy code: {code}")
                rows[code] = {
                    "name": (row.get("l3_name") or row.get("L3 Name") or "").strip(),
                    "definition": (
                        row.get("l3_description") or row.get("L3 Description") or ""
                    ).strip(),
                    "l2_code": (row.get("l2_code") or row.get("L2 ID") or "").strip(),
                    "l2_name": (row.get("l2_name") or row.get("L2 Name") or "").strip(),
                    "l1_code": (row.get("l1_code") or row.get("L1 ID") or "").strip(),
                    "l1_name": (row.get("l1_name") or row.get("L1 Name") or "").strip(),
                }
    return rows


def _parent_codes(l3_code: str) -> tuple[str, str]:
    parts = l3_code.split("_")
    if len(parts) < 4 or parts[0] != "L3":
        raise ValueError(f"invalid L3 code: {l3_code}")
    return "L2_" + "_".join(parts[1:-1]), f"L1_{parts[1]}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.write_bytes(serialized.encode("utf-8"))


def build_taxonomy(
    base_code_to_id: Mapping[str, int],
    legacy_hierarchy: Mapping[str, Mapping[str, str]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if len(base_code_to_id) != 94 or set(base_code_to_id.values()) != set(range(94)):
        raise ValueError("base taxonomy must contain exactly token IDs 0..93")
    legacy_hierarchy = legacy_hierarchy or {}
    code_to_id = dict(base_code_to_id)
    classes: list[dict[str, Any]] = []
    alias_to_code: dict[str, str] = {}
    family_by_l2: dict[str, Mapping[str, str]] = {}
    for legacy_row in legacy_hierarchy.values():
        l2_code = legacy_row.get("l2_code", "")
        if l2_code and l2_code not in family_by_l2:
            family_by_l2[l2_code] = legacy_row
    for token_id, addition in enumerate(ADDITIONS, start=94):
        code = addition["code"]
        if code in code_to_id:
            raise ValueError(f"addition already exists in base taxonomy: {code}")
        legacy = dict(legacy_hierarchy.get(code, {}))
        if addition["source"] == "legacy" and legacy_hierarchy and not legacy:
            raise ValueError(f"legacy definition missing for {code}")
        if addition["source"] == "new" and code in legacy_hierarchy:
            raise ValueError(f"new code collides with legacy registry: {code}")
        l2_code, l1_code = _parent_codes(code)
        family = family_by_l2.get(l2_code, {})
        parent_override = PARENT_METADATA_OVERRIDES.get(l1_code, {})
        aliases: list[str] = []
        for raw_alias in addition["aliases"]:
            alias = raw_alias.strip().lower()
            if not alias:
                raise ValueError(f"empty alias for {code}")
            previous = alias_to_code.get(alias)
            if previous and previous != code:
                raise ValueError(f"alias collision: {alias}: {previous} vs {code}")
            if alias in aliases:
                raise ValueError(f"duplicate alias for {code}: {alias}")
            aliases.append(alias)
            alias_to_code[alias] = code
        code_to_id[code] = token_id
        classes.append({
            **addition,
            "token_id": token_id,
            "aliases": aliases,
            "name": legacy.get("name") or addition["name"],
            "definition": legacy.get("definition") or addition.get("definition", ""),
            "l2_code": legacy.get("l2_code") or l2_code,
            "l2_name": legacy.get("l2_name") or family.get("l2_name"),
            "l1_code": legacy.get("l1_code") or family.get("l1_code") or l1_code,
            "l1_name": (
                legacy.get("l1_name")
                or family.get("l1_name")
                or parent_override.get("name")
            ),
        })

    taxonomy = {
        "schema": "gis_recommend.qgis_taxonomy.v1",
        "profile": PROFILE,
        "production_default": False,
        "content_vocab_size": 114,
        "base_profile": "v2_94_stable",
        "base_class_count": 94,
        "added_class_count": 20,
        "code_to_token_id": code_to_id,
        "alias_to_code": alias_to_code,
        "added_classes": classes,
        "parent_metadata_overrides": PARENT_METADATA_OVERRIDES,
        "reactivated_parent_families": [
            {
                "l1_code": "L1_06",
                "l2_code": "L2_06_01",
                "reason": "L3_06_01_02 is legacy but its L1/L2 families are absent from the stable-94 vocab.",
                "production_default_changed": False,
            }
        ],
        "decision": {
            "spatial_index": "keep",
            "concave_hull": "keep_independent",
            "rasterize_polygonize": "separate_directional_classes",
        },
    }
    old_to_new: dict[str, int] = {}
    semantic_migrations: dict[str, dict[str, Any]] = {}
    for old_token, old_code, old_name, new_code in INVALID_107_SEMANTICS:
        new_token = code_to_id[new_code]
        old_to_new[str(old_token)] = new_token
        semantic_migrations[old_code] = {
            "old_token_id": old_token,
            "old_profile_meaning": old_name,
            "new_code": new_code,
            "new_token_id": new_token,
            "migration_requires_source_profile": True,
        }
    migration = {
        "schema": "gis_recommend.qgis_taxonomy_migration.v1",
        "source_profile": INVALID_107_PROFILE,
        "source_profile_status": "invalid_code_reuse",
        "target_profile": PROFILE,
        "warning": "Never migrate by code string alone; the source profile reused legacy codes with different meanings.",
        "base_token_ids_unchanged": list(range(94)),
        "old_token_id_to_new_token_id": old_to_new,
        "semantic_migrations": semantic_migrations,
    }
    return taxonomy, migration


def validate_taxonomy(
    taxonomy: Mapping[str, Any],
    base_code_to_id: Mapping[str, int],
    legacy_hierarchy: Mapping[str, Mapping[str, str]] | None = None,
    migration: Mapping[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    code_to_id = taxonomy.get("code_to_token_id", {})
    if len(code_to_id) != 114:
        errors.append(f"class_count:{len(code_to_id)}")
    if set(code_to_id.values()) != set(range(114)):
        errors.append("token_ids_not_contiguous_0_113")
    for code, token_id in base_code_to_id.items():
        if code_to_id.get(code) != token_id:
            errors.append(f"base_id_changed:{code}:{token_id}->{code_to_id.get(code)}")
    rows = taxonomy.get("added_classes", [])
    if len(rows) != len(ADDITIONS):
        errors.append(f"added_class_count:{len(rows)}")
    row_ids = {row.get("token_id") for row in rows}
    if row_ids != set(range(94, 114)):
        errors.append("added_token_ids_not_contiguous_94_113")
    if taxonomy.get("added_class_count") != len(rows):
        errors.append("added_class_metadata_mismatch")
    if taxonomy.get("content_vocab_size") != len(code_to_id):
        errors.append("content_vocab_size_mismatch")
    aliases: dict[str, str] = {}
    for row in rows:
        code = row.get("code")
        token_id = row.get("token_id")
        if code_to_id.get(code) != token_id:
            errors.append(f"added_code_id_mismatch:{code}:{token_id}->{code_to_id.get(code)}")
        required_fields = ["name", "l2_code", "l1_code"]
        if legacy_hierarchy is not None:
            required_fields.extend(("definition", "l2_name", "l1_name"))
        for field in required_fields:
            if not row.get(field):
                errors.append(f"missing_added_field:{code}:{field}")
        if not str(row.get("l2_code", "")).startswith("L2_"):
            errors.append(f"invalid_l2_code:{code}:{row.get('l2_code')}")
        if not str(row.get("l1_code", "")).startswith("L1_"):
            errors.append(f"invalid_l1_code:{code}:{row.get('l1_code')}")
        if legacy_hierarchy is not None:
            if row.get("source") == "new" and code in legacy_hierarchy:
                errors.append(f"new_code_legacy_collision:{code}")
            if row.get("source") == "legacy" and code not in legacy_hierarchy:
                errors.append(f"legacy_code_missing:{code}")
        for alias in row.get("aliases", []):
            normalized = str(alias).strip().lower()
            previous = aliases.get(normalized)
            if previous and previous != code:
                errors.append(f"alias_collision:{normalized}:{previous}:{code}")
            aliases[normalized] = code
    if taxonomy.get("alias_to_code") != aliases:
        errors.append("alias_index_mismatch")
    if migration is not None:
        if migration.get("source_profile") != INVALID_107_PROFILE:
            errors.append(f"migration_source_profile:{migration.get('source_profile')}")
        if migration.get("source_profile_status") != "invalid_code_reuse":
            errors.append("migration_source_status_missing")
        old_to_new = migration.get("old_token_id_to_new_token_id", {})
        if set(old_to_new) != {str(index) for index in range(94, 107)}:
            errors.append("migration_source_tokens_not_94_106")
        semantic_rows = migration.get("semantic_migrations", {})
        for old_token, old_code, _old_name, new_code in INVALID_107_SEMANTICS:
            expected_token = code_to_id.get(new_code)
            actual_token = old_to_new.get(str(old_token))
            semantic = semantic_rows.get(old_code, {})
            if actual_token != expected_token:
                errors.append(
                    f"migration_target_mismatch:{old_token}:{actual_token}->{expected_token}"
                )
            if semantic.get("new_code") != new_code or semantic.get("new_token_id") != expected_token:
                errors.append(f"semantic_migration_mismatch:{old_code}")
            if semantic.get("migration_requires_source_profile") is not True:
                errors.append(f"migration_not_source_profile_guarded:{old_code}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-id-mappings", type=Path, required=True)
    parser.add_argument("--legacy-hierarchy", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    base_data = json.loads(args.base_id_mappings.read_text(encoding="utf-8"))
    base = base_data.get("l3", {})
    legacy = _load_legacy_hierarchy(args.legacy_hierarchy)
    taxonomy, migration = build_taxonomy(base, legacy)
    build_inputs = {
        "base_id_mappings_file": args.base_id_mappings.name,
        "base_id_mappings_sha256": _sha256(args.base_id_mappings),
        "legacy_hierarchy_file": args.legacy_hierarchy.name,
        "legacy_hierarchy_sha256": _sha256(args.legacy_hierarchy),
    }
    taxonomy["build_inputs"] = build_inputs
    migration["build_inputs"] = build_inputs
    errors = validate_taxonomy(taxonomy, base, legacy, migration)
    if errors:
        raise SystemExit("taxonomy validation failed: " + ", ".join(errors))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    taxonomy_path = args.output_dir / "qgis_l3_v1_114.json"
    migration_path = args.output_dir / "qgis_l3_v1_114_migration_from_invalid_107.json"
    _write_json(taxonomy_path, taxonomy)
    _write_json(migration_path, migration)
    with (args.output_dir / "qgis_l3_v1_114_added_classes.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["token_id", "code", "name", "definition", "source"])
        writer.writeheader()
        writer.writerows({key: row.get(key) for key in writer.fieldnames} for row in taxonomy["added_classes"])
    print(taxonomy_path)
    print(migration_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
