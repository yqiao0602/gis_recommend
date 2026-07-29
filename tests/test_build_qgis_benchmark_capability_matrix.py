from __future__ import annotations

import importlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = (
    ROOT
    / "docs/reports/qgis_mapping_coverage_audit_2026-07-23/qgis_alg_id_crosswalk_v1.json"
)
STABLE98 = (
    ROOT
    / "docs/reports/qgis_mapping_coverage_audit_2026-07-23/stable98_extension_proposal_v1.json"
)
DELTA98 = (
    ROOT
    / "docs/reports/qgis_mapping_coverage_audit_2026-07-23/qgis_mapping_authority_stable98_delta_draft_v1.json"
)
STABLE101 = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_conservative_extension_proposal_v1.json"
)
DELTA101 = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/qgis_mapping_authority_stable101_conservative_delta_draft_v1.json"
)
REPLAY = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_all1442_source_replay_v1/complete_records.jsonl"
)
CATALOG = ROOT.parent / "operators-json/qgis_operators.json"


def _build(module, replay: Path = REPLAY):
    return module.build(
        hierarchy_path=ROOT / "outputs_v2/classification_hierarchy_v2.csv",
        stable98_path=STABLE98,
        stable101_path=STABLE101,
        crosswalk_path=CROSSWALK,
        stable98_delta_path=DELTA98,
        stable101_delta_path=DELTA101,
        catalog_path=CATALOG,
        replay_path=replay,
        design_spec_path=ROOT / ".omx/specs/deep-interview-qgis-evaluation-set.md",
    )


def test_real_authorities_build_exact_stable101_capability_matrix() -> None:
    module = importlib.import_module(
        "scripts.build_qgis_benchmark_capability_matrix"
    )
    artifacts = _build(module)

    taxonomy = artifacts["stable101_taxonomy"]
    assert taxonomy["taxonomy_id"] == "stable101-paper-v1"
    assert taxonomy["evaluation_taxonomy_admission"] == "granted"
    assert taxonomy["training_admission"] == "not_granted"
    assert taxonomy["production_merge"] == "not_granted"
    assert len(taxonomy["l3_families"]) == 101
    assert [row["token_id"] for row in taxonomy["l3_families"]] == list(
        range(101)
    )

    catalog = artifacts["qgis_catalog"]
    assert catalog["operator_count"] == 1291
    assert catalog["catalog_version"].startswith("sha256:")
    assert len({row["operator_id"] for row in catalog["operators"]}) == 1291

    mapping = artifacts["qgis_operator_l3_mapping"]
    assert mapping["operator_count"] == 262
    assert mapping["status_counts"] == {
        "pending": 112,
        "qgis_native_bridge": 19,
        "rejected": 5,
        "stable101_direct": 126,
    }
    assert mapping["replay_conflict_count"] == 0
    by_operator = {row["operator_id"]: row for row in mapping["entries"]}
    assert by_operator["native:createspatialindex"]["task_role"] == "support_only"
    assert by_operator["native:saveselectedfeatures"]["task_role"] == "output_only"
    assert by_operator["native:fixgeometries"]["mapping_status"] == "stable101_direct"
    assert by_operator["native:fixgeometries"]["stable101_l3"] == "L3_01_05_02"
    assert by_operator["gdal:translate"]["task_role"] == "output_only"
    assert by_operator["gdal:translate"]["headline_eligible"] is False

    matrix = artifacts["capability_matrix"]
    assert len(matrix) == 101
    assert {
        tier: sum(row["admission_tier"] == tier for row in matrix)
        for tier in ("headline_core", "capability_gap_diagnostic", "refusal")
    } == {
        "headline_core": 50,
        "capability_gap_diagnostic": 3,
        "refusal": 48,
    }
    assert sum(row["provisional_roster_candidate"] for row in matrix) == 20
    assert all(row["supply_status"] == "not_measured_gate3" for row in matrix)
    assert all(
        row["source_backed_supply"]
        == {
            "distinct_normalized_chains": None,
            "distinct_source_authorities": None,
            "graph_size_counts": None,
            "modality_counts": None,
            "status": "not_measured_gate3",
            "topology_counts": None,
        }
        for row in matrix
    )
    headline = [row for row in matrix if row["admission_tier"] == "headline_core"]
    refusal = [row for row in matrix if row["admission_tier"] == "refusal"]
    assert len(headline) >= 20
    assert refusal
    assert all(
        all(value["supported"] for value in row["route_output_support"].values())
        for row in headline
    )


def test_replay_mapping_conflict_fails_closed(tmp_path: Path) -> None:
    module = importlib.import_module(
        "scripts.build_qgis_benchmark_capability_matrix"
    )
    crosswalk = json.loads(CROSSWALK.read_text(encoding="utf-8"))
    expected = crosswalk["entries"]["native:buffer"]["l3_code"]
    assert expected != "L3_01_01_03"
    replay = tmp_path / "conflict.jsonl"
    replay.write_text(
        json.dumps(
            {
                "qgis_ops": ["native:buffer"],
                "proposed_l3_sequence": ["L3_01_01_03"],
                "mapping_authority": "stable101_composed_draft_v1",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    artifacts = _build(module, replay)
    by_operator = {
        row["operator_id"]: row
        for row in artifacts["qgis_operator_l3_mapping"]["entries"]
    }
    assert by_operator["native:buffer"]["replay_mapping_status"] == "conflict"
    assert by_operator["native:buffer"]["headline_eligible"] is False
    assert artifacts["qgis_operator_l3_mapping"]["replay_conflict_count"] == 1


def test_write_outputs_creates_only_gate1_authority_files(tmp_path: Path) -> None:
    module = importlib.import_module(
        "scripts.build_qgis_benchmark_capability_matrix"
    )
    artifacts = _build(module)
    paths = module.write_outputs(artifacts, tmp_path)

    assert set(paths) == {
        "capability_matrix",
        "qgis_catalog",
        "qgis_operator_l3_mapping",
        "stable101_taxonomy",
    }
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "capability_matrix.jsonl",
        "qgis_catalog.json",
        "qgis_operator_l3_mapping.json",
        "stable101_taxonomy.json",
    ]
    assert len((tmp_path / "capability_matrix.jsonl").read_text(encoding="utf-8").splitlines()) == 101
