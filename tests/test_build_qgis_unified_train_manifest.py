from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "build_qgis_unified_train_manifest.py"
)
SPEC = importlib.util.spec_from_file_location(
    "build_qgis_unified_train_manifest", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _row(
    sample_id: str,
    *,
    source_region: str,
    call_graph: str,
    task: str,
    operator: str = "native:buffer",
) -> dict:
    return {
        "schema_version": "qgis_stable101_training_sample_v1",
        "sample_id": sample_id,
        "record_id": "shared-record-id",
        "source_sha256": f"sha-{sample_id}",
        "source_path": f"/source/{sample_id}.py",
        "source_region_key": source_region,
        "call_graph_key": call_graph,
        "normalized_dag_key": "same-dag",
        "task_name": task,
        "task_description": task,
        "task_metadata": {
            "task_name": task,
            "task_description": task,
            "task_type": "QGIS workflow",
        },
        "operator_sequence": [operator],
        "qgis_operator_chain": [operator],
        "chain": [operator],
        "l3_code_sequence": ["L3_A"],
        "l3_token_ids": [1],
        "l3_sequence": [-3, 1, -4],
        "training_admission": "granted_train_only_direct_deterministic_pilot",
        "split": "train_only_direct_deterministic_pilot",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def test_unified_manifest_suppresses_only_duplicate_evidence_or_training_pair() -> None:
    first = _row("first", source_region="region-1", call_graph="graph-1", task="缓冲")
    same_pair = _row(
        "same-pair", source_region="region-2", call_graph="graph-2", task="缓冲"
    )
    same_dag_different_task = _row(
        "different-task",
        source_region="region-3",
        call_graph="graph-3",
        task="按指定距离创建缓冲区",
    )
    same_region = _row(
        "same-region",
        source_region="region-1",
        call_graph="graph-4",
        task="另一种写法",
    )

    ledger, manifest, summary = MODULE.build_unified_manifest(
        [("primary", [first]), ("secondary", [same_pair, same_dag_different_task, same_region])]
    )

    assert [row["sample_id"] for row in manifest] == ["first", "different-task"]
    assert summary["input_rows"] == 4
    assert summary["manifest_rows"] == 2
    assert summary["suppressed_exact_training_pairs"] == 1
    assert summary["suppressed_duplicate_source_regions"] == 1
    assert all(row["training_admission"] == "granted_train_only_qgis_unified_pilot" for row in manifest)
    assert all(row["split"] == "train_only_qgis_unified_pilot" for row in manifest)
    assert all(
        row["schema_version"] == "qgis_stable101_training_sample_v1"
        for row in manifest
    )
    assert all(
        row["manifest_schema"] == "gis_recommend.qgis_unified_train_manifest.v1"
        for row in manifest
    )
    decisions = {row["sample_id"]: row["dedup_decision"] for row in ledger}
    assert decisions == {
        "first": "canonical_keep",
        "same-pair": "exact_training_pair_suppressed",
        "different-task": "canonical_keep",
        "same-region": "duplicate_source_region_suppressed",
    }


def test_unified_manifest_rejects_non_train_or_validation_eligible_rows() -> None:
    row = _row("unsafe", source_region="region", call_graph="graph", task="缓冲")
    row["validation_eligible"] = True

    try:
        MODULE.build_unified_manifest([("unsafe-pool", [row])])
    except ValueError as exc:
        assert "train-only" in str(exc)
    else:
        raise AssertionError("expected fail-closed permission validation")


def test_unified_manifest_replays_legacy_source_prefix_before_sha_check(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sample.py"
    source.write_text('processing.run("native:buffer", {})\n', encoding="utf-8")
    row = _row("mapped", source_region="region", call_graph="graph", task="缓冲")
    row["source_path"] = r"X:\legacy\sample.py"
    row["source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()

    _, manifest, _ = MODULE.build_unified_manifest(
        [("legacy", [row])],
        verify_source=True,
        source_prefix_maps=[("X:/legacy", str(tmp_path).replace("\\", "/"))],
    )

    assert Path(manifest[0]["source_path"]) == source
    assert manifest[0]["source_verification"] == "verified_sha256"
    assert manifest[0]["source_authority_basis"] == "source_sha256"
    assert (
        manifest[0]["source_authority_key"]
        == f"source_sha256:{row['source_sha256']}"
    )
    assert (
        manifest[0]["source_identity_replay"]
        == "gis_recommend.qgis_training_source_identity_replay.v1"
    )


def test_unified_manifest_preserves_posix_authority_path() -> None:
    row = _row("posix", source_region="region", call_graph="graph", task="buffer")
    row["source_path"] = "/home/yll/data/sample.py"

    _, manifest, _ = MODULE.build_unified_manifest([("primary", [row])])

    assert manifest[0]["source_path"] == "/home/yll/data/sample.py"


def test_unified_manifest_accepts_already_granted_increment_authorities() -> None:
    admissions = [
        "granted_train_only_qgis_unified_pilot",
        "granted_train_only_stable106_increment",
        "granted_train_only_existing_l3_increment",
        "granted_train_only_mapping_correction",
        "granted_train_only_qgis_api_v1",
        "granted_train_only_qgis_processing_review_v1",
        "granted_train_only_description_recovery",
        "granted_train_only_after_semantic_revocation",
        "granted_train_only_custom_scope",
        "granted_train_only_stable110_split_salvage",
    ]
    pools = []
    for index, admission in enumerate(admissions):
        row = _row(
            f"increment-{index}",
            source_region=f"region-{index}",
            call_graph=f"graph-{index}",
            task=f"task-{index}",
        )
        row["training_admission"] = admission
        pools.append((f"pool-{index}", [row]))

    _, manifest, summary = MODULE.build_unified_manifest(pools)

    assert len(manifest) == len(admissions)
    assert summary["manifest_rows"] == len(admissions)


def test_unified_manifest_rejects_task_metadata_drift() -> None:
    row = _row("task-drift", source_region="region", call_graph="graph", task="buffer")
    row["task_metadata"]["task_description"] = "different description"

    with pytest.raises(ValueError, match="task metadata mismatch"):
        MODULE.build_unified_manifest([("primary", [row])])


def test_unified_manifest_validates_stable_mapping_and_relabels_profile() -> None:
    row = _row("mapped", source_region="region", call_graph="graph", task="buffer")

    _, manifest, summary = MODULE.build_unified_manifest(
        [("primary", [row])],
        code_to_id={"L3_A": 1},
        operator_to_l3={"native:buffer": "L3_A"},
        target_taxonomy_profile="stable110_authority_v1",
        target_schema_version="qgis_unified_training_sample_v1",
    )

    assert manifest[0]["taxonomy_profile"] == "stable110_authority_v1"
    assert manifest[0]["schema_version"] == "qgis_unified_training_sample_v1"
    assert manifest[0]["source_schema_version"] == "qgis_stable101_training_sample_v1"
    assert summary["taxonomy_profile"] == "stable110_authority_v1"
    assert summary["schema_version"] == "qgis_unified_training_sample_v1"

    with pytest.raises(ValueError, match="operator/L3 authority mismatch"):
        MODULE.build_unified_manifest(
            [("primary", [row])],
            code_to_id={"L3_A": 1},
            operator_to_l3={"native:buffer": "L3_WRONG"},
            target_taxonomy_profile="stable110_authority_v1",
        )


def test_hash_ledger_binds_mapping_authorities_and_source_prefix_maps(
    tmp_path: Path,
) -> None:
    row = _row("bound", source_region="region", call_graph="graph", task="buffer")
    ledger, manifest, summary = MODULE.build_unified_manifest([("primary", [row])])
    pool = tmp_path / "pool.jsonl"
    taxonomy = tmp_path / "taxonomy.json"
    mapping = tmp_path / "mapping.json"
    pool.write_text("{}\n", encoding="utf-8")
    taxonomy.write_text("{}\n", encoding="utf-8")
    mapping.write_text("{}\n", encoding="utf-8")

    MODULE.write_outputs(
        ledger,
        manifest,
        summary,
        pool_paths=[("primary", pool)],
        authority_paths=[("taxonomy", taxonomy), ("operator_mapping", mapping)],
        source_prefix_maps=[("/old", "/new")],
        output_dir=tmp_path / "output",
    )

    hashes = json.loads((tmp_path / "output/hash_ledger_v1.json").read_text(encoding="utf-8"))
    assert set(hashes["authority_inputs"]) == {"taxonomy", "operator_mapping"}
    assert hashes["source_prefix_maps"] == [{"source": "/old", "target": "/new"}]
