from __future__ import annotations

import hashlib

import pytest

from scripts.build_qgis_processing_mapping_gap_queue import (
    build_admission_census,
    build_admission_clusters,
    build_queue,
)


def test_ranks_single_gap_unlocks_and_keeps_admission_closed() -> None:
    rows = [
        {
            "record_id": "a",
            "normalization_status": "fully_normalized",
            "mapping_complete": False,
            "unmapped_operator_ids": ["native:creategrid"],
            "operator_ids": ["native:creategrid"],
            "source_root_id": "fixture",
            "source_path": "missing.py",
            "source_sha256": "sha-a",
        },
        {
            "record_id": "b",
            "normalization_status": "fully_normalized",
            "mapping_complete": False,
            "unmapped_operator_ids": ["native:creategrid"],
            "operator_ids": ["native:buffer", "native:creategrid"],
            "source_root_id": "fixture-2",
            "source_path": "missing.py",
            "source_sha256": "sha-b",
        },
        {
            "record_id": "c",
            "normalization_status": "fully_normalized",
            "mapping_complete": False,
            "unmapped_operator_ids": ["native:other", "native:blocked"],
            "operator_ids": ["native:other", "native:blocked"],
            "source_root_id": "fixture",
            "source_path": "missing.py",
            "source_sha256": "sha-c",
        },
    ]

    queue, summary = build_queue(
        rows,
        {"entries": {"native:creategrid": {"status": "rejected", "bridge_type": "rejected"}}},
        top_n=2,
        samples_per_operator=1,
        verify_sources=False,
    )

    assert queue[0]["operator_id"] == "native:creategrid"
    assert queue[0]["single_gap_records"] == 2
    assert queue[0]["experimental_114_candidate_l3"] == "L3_02_03_06"
    assert queue[0]["training_row_emitted"] is False
    assert summary["training_rows_emitted"] == 0


def test_excludes_already_adjudicated_operators() -> None:
    rows = [
        {
            "record_id": operator,
            "normalization_status": "fully_normalized",
            "mapping_complete": False,
            "unmapped_operator_ids": [operator],
            "operator_ids": [operator],
            "source_root_id": "fixture",
            "source_path": "missing.py",
            "source_sha256": operator,
        }
        for operator in ("native:already-reviewed", "native:next")
    ]

    queue, _ = build_queue(
        rows,
        {"entries": {}},
        excluded_operator_ids={"native:already-reviewed"},
        verify_sources=False,
    )

    assert [row["operator_id"] for row in queue] == ["native:next"]


def test_limits_queue_to_explicit_operator_allowlist() -> None:
    rows = [
        {
            "record_id": operator,
            "normalization_status": "fully_normalized",
            "mapping_complete": False,
            "unmapped_operator_ids": [operator],
            "operator_ids": [operator],
            "source_root_id": "fixture",
            "source_path": "missing.py",
            "source_sha256": operator,
        }
        for operator in ("native:target", "native:other")
    ]

    queue, summary = build_queue(
        rows,
        {"entries": {}},
        allowed_operator_ids={"native:target"},
        verify_sources=False,
    )

    assert [row["operator_id"] for row in queue] == ["native:target"]
    assert summary["allowed_operator_count"] == 1


def test_skips_stale_source_copy_when_verified_copy_is_available(tmp_path) -> None:
    verified = tmp_path / "verified.py"
    verified.write_text("print('ok')\n", encoding="utf-8")
    verified_sha = hashlib.sha256(verified.read_bytes()).hexdigest()
    rows = [
        {
            "record_id": "stale",
            "normalization_status": "fully_normalized",
            "mapping_complete": False,
            "unmapped_operator_ids": ["native:target"],
            "operator_ids": ["native:target"],
            "source_root_id": "root-a",
            "source_path": str(tmp_path / "missing.py"),
            "source_sha256": "0" * 64,
        },
        {
            "record_id": "verified",
            "normalization_status": "fully_normalized",
            "mapping_complete": False,
            "unmapped_operator_ids": ["native:target"],
            "operator_ids": ["native:target"],
            "source_root_id": "root-b",
            "source_path": str(verified),
            "source_sha256": verified_sha,
        },
    ]

    queue, _ = build_queue(
        rows,
        {"entries": {}},
        samples_per_operator=1,
    )

    assert [sample["record_id"] for sample in queue[0]["samples"]] == ["verified"]


def test_admission_census_filters_side_effects_and_collapses_source_bodies(
    tmp_path,
) -> None:
    body = 'processing.run("native:pointstopath", {})\n'
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    first.write_text(
        "# Source repo: owner/repo\n# Source path: workflow.py\n\n" + body,
        encoding="utf-8",
    )
    second.write_text(body, encoding="utf-8")

    def row(record_id, operator_id, source_path, *, structure="auto_accept_candidate"):
        return {
            "record_id": record_id,
            "normalization_status": "fully_normalized",
            "mapping_complete": False,
            "structure_action": structure,
            "operator_ids": [operator_id],
            "unmapped_operator_ids": [operator_id],
            "source_path": str(source_path),
            "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
            "source_root_id": "fixture",
            "feature_signature_hash": f"signature-{operator_id}",
        }

    rows = [
        row(
            "database",
            "native:postgisexecutesql",
            first,
        ),
        row("support", "native:createspatialindex", first),
        row("semantic-a", "native:pointstopath", first),
        row("semantic-b", "native:pointstopath", second),
        row("wrong-structure", "native:pointstopath", first, structure="split_subworkflow"),
        {**row("mapped", "native:pointstopath", first), "mapping_complete": True},
    ]

    ledger, summary = build_admission_census(
        rows,
        semantic_adjudications={
            "native:pointstopath": {
                "decision": "defer_no_exact_stable110_mapping",
                "reason": "stable110_has_no_points_to_path_contract",
            }
        },
    )

    assert [item["record_id"] for item in ledger] == [
        "database",
        "semantic-a",
        "semantic-b",
        "support",
    ]
    assert summary["fully_normalized_mapping_incomplete_rows"] == 5
    assert summary["structure_eligible_rows"] == 4
    assert summary["database_side_effect_rows"] == 1
    assert summary["support_export_rows"] == 1
    assert summary["semantic_review_rows"] == 2
    assert summary["semantic_unique_normalized_source_bodies"] == 1
    assert summary["existing_stable110_candidate_rows"] == 0
    assert summary["training_rows_emitted"] == 0

    clusters = build_admission_clusters(ledger)
    assert clusters["operator_clusters"]["native:pointstopath"] == 2
    assert list(clusters["normalized_source_body_clusters"].values()) == [2]
    assert list(clusters["source_authority_clusters"].values()) == [2]


def test_admission_census_rejects_unadjudicated_semantic_operator(tmp_path) -> None:
    source = tmp_path / "source.py"
    source.write_text('processing.run("native:unknown", {})\n', encoding="utf-8")
    rows = [
        {
            "record_id": "unknown",
            "normalization_status": "fully_normalized",
            "mapping_complete": False,
            "structure_action": "auto_accept_candidate",
            "operator_ids": ["native:unknown"],
            "unmapped_operator_ids": ["native:unknown"],
            "source_path": str(source),
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        }
    ]

    with pytest.raises(ValueError, match="missing semantic adjudications"):
        build_admission_census(rows, semantic_adjudications={})


def test_admission_census_recomputes_gaps_from_effective_mapping(tmp_path) -> None:
    source = tmp_path / "source.py"
    source.write_text('processing.run("native:revoked", {})\n', encoding="utf-8")
    common = {
        "normalization_status": "fully_normalized",
        "structure_action": "auto_accept_candidate",
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }
    rows = [
        {
            **common,
            "record_id": "revoked",
            "mapping_complete": True,
            "canonical_operator_ids": ["native:revoked"],
            "unmapped_operator_ids": [],
        },
        {
            **common,
            "record_id": "newly-mapped",
            "mapping_complete": False,
            "canonical_operator_ids": ["native:known"],
            "unmapped_operator_ids": ["native:known"],
        },
    ]

    ledger, summary = build_admission_census(
        rows,
        effective_mapping={"native:known": "L3_KNOWN"},
        semantic_adjudications={
            "native:revoked": {
                "decision": "defer_no_exact_stable110_mapping",
                "reason": "mapping_revoked",
            }
        },
    )

    assert [row["record_id"] for row in ledger] == ["revoked"]
    assert ledger[0]["unmapped_operator_ids"] == ["native:revoked"]
    assert summary["fully_normalized_mapping_incomplete_rows"] == 1


def test_admission_census_resolves_stale_path_by_exact_source_sha(tmp_path) -> None:
    source = tmp_path / "resolved.py"
    source.write_text('processing.run("native:pointstopath", {})\n', encoding="utf-8")
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    rows = [
        {
            "record_id": "stale",
            "normalization_status": "fully_normalized",
            "mapping_complete": False,
            "structure_action": "auto_accept_candidate",
            "canonical_operator_ids": ["native:pointstopath"],
            "operator_ids": ["native:pointstopath"],
            "unmapped_operator_ids": ["native:pointstopath"],
            "source_path": str(tmp_path / "missing.py"),
            "source_sha256": source_sha,
        }
    ]

    ledger, summary = build_admission_census(
        rows,
        source_authority_rows=[
            {"source_sha256": source_sha, "source_path": str(source)}
        ],
        semantic_adjudications={
            "native:pointstopath": {
                "decision": "defer_no_exact_stable110_mapping",
                "reason": "stable110_has_no_points_to_path_contract",
            }
        },
    )

    assert ledger[0]["source_path"] == str(source)
    assert ledger[0]["source_path_resolution"] == "source_manifest_sha_match"
    assert ledger[0]["source_sha256_verified"] is True
    assert summary["source_manifest_resolved_rows"] == 1
    assert summary["source_unverified_rows"] == 0
