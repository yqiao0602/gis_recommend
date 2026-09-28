from __future__ import annotations

import json
import runpy
from copy import deepcopy
from pathlib import Path

from gis_recommend.data.qgis_registry_sidecar import (
    compare_registry_to_catalog,
    normalize_registry_snapshot,
)

FIXTURE = Path("tests/fixtures/qgis_external_pilot/registry_records.json")
CATALOG = Path("benchmarks/qgis_planner_v1/authority/qgis_catalog.json")
EXPORTER = Path("scripts/qgis_external_pilot/export_qgis_registry.py")


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_registry_normalization_has_stable_nested_order() -> None:
    snapshot = _fixture()["snapshot"]
    shuffled = deepcopy(snapshot)
    shuffled["providers"].reverse()
    shuffled["providers"][1]["algorithms"].reverse()
    shuffled["providers"][1]["algorithms"][0]["parameters"].reverse()

    assert normalize_registry_snapshot(snapshot) == normalize_registry_snapshot(shuffled)
    normalized = normalize_registry_snapshot(snapshot)
    assert normalized["providers"][1]["algorithms"][0]["operator_id"] == "native:buffer"
    assert [item["name"] for item in normalized["providers"][1]["algorithms"][0]["parameters"]] == ["DISTANCE", "INPUT"]


def test_registry_comparison_emits_all_fail_closed_statuses() -> None:
    fixture = _fixture()

    report = compare_registry_to_catalog(fixture["snapshot"], fixture["catalog"])

    statuses = {row["operator_id"]: row["status"] for row in report["operators"]}
    assert statuses == {
        "grass7:v.clean": "provider_version_mismatch",
        "native:buffer": "matched",
        "native:centroids": "catalog_contract_mismatch",
        "native:missing": "operator_not_found",
        "saga:foo": "provider_not_installed",
    }
    assert report["authority_mutated"] is False
    assert report["training_rows_emitted"] == 0


def test_registry_comparison_never_mutates_catalog_authority() -> None:
    before = CATALOG.read_bytes()
    fixture = _fixture()

    compare_registry_to_catalog(fixture["snapshot"], fixture["catalog"])

    assert CATALOG.read_bytes() == before


def test_qgis_exporter_uses_lazy_runtime_imports() -> None:
    namespace = runpy.run_path(str(EXPORTER), run_name="qgis_registry_import_test")

    assert callable(namespace["export_registry"])
