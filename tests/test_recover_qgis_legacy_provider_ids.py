from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "recover_qgis_legacy_provider_ids.py"
)
SPEC = importlib.util.spec_from_file_location(
    "recover_qgis_legacy_provider_ids", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_canonicalize_operator_id_accepts_only_catalog_backed_provider_aliases() -> None:
    catalog = {"native:buffer", "native:clip", "gdal:buffer"}

    assert MODULE.canonicalize_operator_id("qgis:buffer", catalog) == (
        "native:buffer",
        "qgis_to_native_same_slug",
    )
    assert MODULE.canonicalize_operator_id("native:clip", catalog) == (
        "native:clip",
        "catalog_exact",
    )
    assert MODULE.canonicalize_operator_id("thirdparty:buffer", catalog) == (
        None,
        "unresolved",
    )
    assert MODULE.canonicalize_operator_id("qgis:missing", catalog) == (
        None,
        "unresolved",
    )


def test_canonicalize_operator_id_recovers_provider_version_aliases() -> None:
    catalog = {
        "gdal:convertformat",
        "grass7:r.watershed",
        "saga:upslopearea",
    }

    assert MODULE.canonicalize_operator_id("gdalogr:convertformat", catalog) == (
        "gdal:convertformat",
        "gdalogr_to_gdal_same_slug",
    )
    assert MODULE.canonicalize_operator_id("grass:r.watershed", catalog) == (
        "grass7:r.watershed",
        "grass_to_grass7_same_slug",
    )
    assert MODULE.canonicalize_operator_id("sagang:upslopearea", catalog) == (
        "saga:upslopearea",
        "sagang_to_saga_same_slug",
    )
    assert MODULE.canonicalize_operator_id("grass:r.missing", catalog) == (
        None,
        "unresolved",
    )


def test_canonicalize_operator_id_recovers_reviewed_legacy_slug_aliases() -> None:
    catalog = {
        "native:buffer",
        "qgis:rastercalculator",
        "qgis:voronoipolygons",
    }

    assert MODULE.canonicalize_operator_id("native:rastercalc", catalog) == (
        "qgis:rastercalculator",
        "reviewed_legacy_slug_alias",
    )
    assert MODULE.canonicalize_operator_id("native:modelerrastercalc", catalog) == (
        "qgis:rastercalculator",
        "reviewed_legacy_slug_alias",
    )
    assert MODULE.canonicalize_operator_id("native:voronoipolygons", catalog) == (
        "qgis:voronoipolygons",
        "reviewed_legacy_slug_alias",
    )
    assert MODULE.canonicalize_operator_id("qgis:fixeddistancebuffer", catalog) == (
        "native:buffer",
        "reviewed_legacy_slug_alias",
    )
    assert MODULE.canonicalize_operator_id("native:alignsingleraster", catalog) == (
        None,
        "unresolved",
    )


def test_canonicalize_operator_id_recovers_reviewed_provider_equivalents() -> None:
    catalog = {
        "gdal:convertformat",
        "gdal:cliprasterbymasklayer",
        "gdal:cliprasterbyextent",
        "gdal:clipvectorbyextent",
        "gdal:polygonize",
        "native:centroids",
        "native:creategrid",
        "native:deleteduplicategeometries",
        "native:fieldcalculator",
        "native:mergevectorlayers",
        "native:multiparttosingleparts",
        "native:polygonstolines",
        "native:retainfields",
        "native:setlayerstyle",
        "native:union",
        "native:zonalhistogram",
        "qgis:basicstatisticsforfields",
        "qgis:checkvalidity",
        "qgis:delaunaytriangulation",
        "qgis:joinbylocationsummary",
        "qgis:minimumboundinggeometry",
        "qgis:rastercalculator",
    }
    expected = {
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

    for source, target in expected.items():
        assert MODULE.canonicalize_operator_id(source, catalog) == (
            target,
            "reviewed_provider_equivalent",
        )


def test_recover_row_normalizes_chain_and_runs_structure_gate(tmp_path: Path) -> None:
    source_path = tmp_path / "workflow.py"
    source_path.write_text(
        '''
def execute(layer):
    buffered = processing.run("qgis:buffer", {"INPUT": layer})["OUTPUT"]
    return processing.run("qgis:fixgeometries", {"INPUT": buffered})
''',
        encoding="utf-8",
    )
    row = {
        "content_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "source_path": str(source_path),
        "source_root_id": "fixture",
        "relative_path": source_path.name,
        "primary_layer": "explicit_processing_catalog_miss",
        "screening_literal_operator_ids": [
            "qgis:buffer",
            "qgis:fixgeometries",
        ],
        "catalog_miss_ids": ["qgis:buffer", "qgis:fixgeometries"],
    }

    recovered = MODULE.recover_row(
        row, {"native:buffer", "native:fixgeometries"}
    )

    assert recovered["normalization_status"] == "fully_normalized"
    assert recovered["canonical_operator_ids"] == [
        "native:buffer",
        "native:fixgeometries",
    ]
    assert recovered["dependency_edges"] == [[0, 1]]
    assert recovered["structure_action"] == "auto_accept_candidate"
    assert recovered["action"] == "auto_accept_candidate"
    assert recovered["operator_ids"] == recovered["canonical_operator_ids"]
    assert recovered["source_sha256"] == row["content_sha256"]
    assert [site["operator_id"] for site in recovered["call_sites"]] == [
        "native:buffer",
        "native:fixgeometries",
    ]
    assert recovered["training_row_emitted"] is False


def test_recover_row_records_non_exact_provider_migration(tmp_path: Path) -> None:
    source_path = tmp_path / "workflow.py"
    source_path.write_text(
        'return processing.run("gdalogr:convertformat", {"INPUT": layer})\n',
        encoding="utf-8",
    )
    row = {
        "content_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "source_path": str(source_path),
        "source_root_id": "fixture",
        "relative_path": source_path.name,
        "primary_layer": "explicit_processing_catalog_miss",
        "screening_literal_operator_ids": ["gdalogr:convertformat"],
        "catalog_miss_ids": ["gdalogr:convertformat"],
    }

    recovered = MODULE.recover_row(row, {"gdal:convertformat"})

    assert recovered["normalization_status"] == "fully_normalized"
    assert recovered["provider_migrations"] == [
        {
            "source": "gdalogr:convertformat",
            "target": "gdal:convertformat",
            "rule": "gdalogr_to_gdal_same_slug",
        }
    ]


def test_build_recovery_keeps_mixed_provider_record_deferred(tmp_path: Path) -> None:
    source_path = tmp_path / "workflow.py"
    source_path.write_text(
        'processing.run("qgis:buffer", {})\n'
        'processing.run("plugin:custom", {})\n',
        encoding="utf-8",
    )
    row = {
        "content_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "source_path": str(source_path),
        "source_root_id": "fixture",
        "relative_path": source_path.name,
        "primary_layer": "explicit_processing_catalog_miss",
        "screening_literal_operator_ids": ["qgis:buffer", "plugin:custom"],
        "catalog_miss_ids": ["qgis:buffer", "plugin:custom"],
    }
    ledger_path = tmp_path / "census.jsonl"
    ledger_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    rows, summary = MODULE.build_recovery(ledger_path, {"native:buffer"})

    assert rows[0]["normalization_status"] == "partially_normalized"
    assert rows[0]["unresolved_operator_ids"] == ["plugin:custom"]
    assert rows[0]["structure_action"] == "defer_operator_resolution"
    assert summary["fully_normalized_records"] == 0
    assert summary["partially_normalized_records"] == 1
