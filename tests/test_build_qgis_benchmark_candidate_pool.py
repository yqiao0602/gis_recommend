from __future__ import annotations

import importlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _module():
    return importlib.import_module("scripts.build_qgis_benchmark_candidate_pool")


def test_real_discovery_pools_build_zero_overlap_source_supply() -> None:
    module = _module()
    result = module.build(
        root=ROOT,
        discovery_pools=module.DEFAULT_DISCOVERY_POOLS,
        mapping_path=ROOT / "benchmarks/qgis_planner_v1/authority/qgis_operator_l3_mapping.json",
        catalog_path=ROOT / "benchmarks/qgis_planner_v1/authority/qgis_catalog.json",
        capability_path=ROOT / "benchmarks/qgis_planner_v1/authority/capability_matrix.jsonl",
        exclusion_path=ROOT / "benchmarks/qgis_planner_v1/authority/source_exclusion_ledger.jsonl",
    )

    rows = result["rows"]
    summary = result["summary"]
    assert summary["discovery_record_count"] == 4_605
    assert summary["candidate_count"] == 146
    assert summary["distinct_normalized_dags"] == 50
    assert summary["provenance_counts"] == {
        "expert_authored": 0,
        "qgis_source_backed": 146,
    }
    assert summary["gate_status"] == "failed_insufficient_candidate_supply"
    assert "expert_authored_minimum_unmet" in summary["failure_reasons"]
    assert sum(
        row["gate3_family_status"] == "quota_8_supply_eligible"
        for row in summary["family_supply"]
    ) == 2
    assert sum(
        row["gate3_family_status"] == "quota_4_supply_eligible"
        for row in summary["family_supply"]
    ) == 4
    assert len({row["candidate_id"] for row in rows}) == len(rows)
    assert summary["distinct_source_authorities"] == len(
        {row["source_authority_key"] for row in rows}
    )
    assert all(row["gate1_status"] == "passed" for row in rows)
    assert all(row["gate2_overlap_fields"] == [] for row in rows)
    assert all(row["provenance_class"] == "qgis_source_backed" for row in rows)
    assert all(row["processes"] for row in rows)
    assert all(
        set(row).isdisjoint(
            {
                "task_text",
                "task_description",
                "source_path",
                "source_snippet",
                "parameter_facts",
            }
        )
        for row in rows
    )

    mapping = json.loads(
        (ROOT / "benchmarks/qgis_planner_v1/authority/qgis_operator_l3_mapping.json").read_text(
            encoding="utf-8"
        )
    )
    headline = {
        row["operator_id"]
        for row in mapping["entries"]
        if row["headline_eligible"]
    }
    assert all(
        process["operator_id"] in headline
        for row in rows
        for process in row["processes"]
    )


def test_graph_profile_rejects_disconnected_and_cyclic_links() -> None:
    module = _module()

    assert module.graph_profile(3, [(0, 1), (1, 2)]) == {
        "graph_size_stratum": "two_to_three",
        "topology": "linear",
    }
    assert module.graph_profile(3, [(0, 2), (1, 2)])["topology"] == "multi_input_merge"
    assert module.graph_profile(3, [(0, 1), (0, 2)])["topology"] == "branch_or_multi_output"
    assert module.graph_profile(3, [(0, 1)]) is None
    assert module.graph_profile(2, [(0, 1), (1, 0)]) is None


def test_family_supply_requires_quota_plus_reserve() -> None:
    module = _module()

    assert module.required_supply(8) == 11
    assert module.required_supply(4) == 7


def test_write_outputs_creates_only_gate3_authority_files(tmp_path: Path) -> None:
    module = _module()
    result = {
        "rows": [{"candidate_id": "candidate-1"}],
        "summary": {"schema": "summary-v1"},
    }

    paths = module.write_outputs(result, tmp_path)

    assert set(paths) == {"candidate_supply", "candidate_supply_summary"}
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "candidate_supply.jsonl",
        "candidate_supply_summary.json",
    ]


def test_optional_expert_input_counts_only_fully_admitted_rows(tmp_path: Path) -> None:
    module = _module()
    mapping_path = tmp_path / "mapping.json"
    catalog_path = tmp_path / "catalog.json"
    capability_path = tmp_path / "capability.jsonl"
    exclusion_path = tmp_path / "exclusion.jsonl"
    expert_path = tmp_path / "experts.jsonl"
    mapping_path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "operator_id": "native:buffer",
                        "strict_catalog_present": True,
                        "mapping_status": "stable101_direct",
                        "stable101_l3": "L3_02_01_01",
                        "headline_eligible": True,
                        "task_role": "analytical",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    catalog_path.write_text(
        json.dumps(
            {
                "operators": [
                    {
                        "operator_id": "native:buffer",
                        "input_types": ["vector"],
                        "output_types": ["vector"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    capability_path.write_text("", encoding="utf-8")
    exclusion_path.write_text("", encoding="utf-8")
    expert = {
        "proposal_id": "expert-001",
        "provenance_class": "expert_authored",
        "processes": [
            {
                "process_id": "p0",
                "operator_id": "native:buffer",
                "l3_code": "L3_02_01_01",
            }
        ],
        "links": [],
        "parameters_included": False,
        "quota_anchor_l3": "L3_02_01_01",
        "covered_l3": ["L3_02_01_01"],
        "modality": "vector",
        "topology": "linear",
        "graph_size_stratum": "one_step",
        "normalized_dag_key": "dag-1",
        "forbidden_near_dag_key": "near-1",
        "semantic_dag_key": "semantic-1",
        "graph_review_status": "independent_reviewed",
        "gate1_status": "passed",
        "gate2_status": "passed",
        "dedup_status": "canonical",
        "supply_admission": "gate3_candidate_admitted",
    }
    expert_path.write_text(json.dumps(expert) + "\n", encoding="utf-8")

    result = module.build(
        root=tmp_path,
        discovery_pools=(),
        mapping_path=mapping_path,
        catalog_path=catalog_path,
        capability_path=capability_path,
        exclusion_path=exclusion_path,
        expert_proposals_path=expert_path,
    )

    assert result["summary"]["candidate_count"] == 1
    assert result["summary"]["provenance_counts"] == {
        "expert_authored": 1,
        "qgis_source_backed": 0,
    }
    assert result["summary"]["distinct_source_authorities"] == 0
    assert result["rows"][0]["candidate_id"].startswith("qgis-expert-")
