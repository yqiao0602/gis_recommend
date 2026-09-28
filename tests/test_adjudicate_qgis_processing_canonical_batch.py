from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "adjudicate_qgis_processing_canonical_batch.py"
)


def _load_module():
    assert SCRIPT.exists(), "canonical batch adjudicator is not implemented"
    spec = importlib.util.spec_from_file_location(
        "adjudicate_qgis_processing_canonical_batch", SCRIPT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(candidate_id: str, status: str = "canonical_candidate") -> dict:
    return {
        "candidate_id": candidate_id,
        "record_id": f"record-{candidate_id}",
        "source_sha256": "a" * 64,
        "source_authority_key": f"source:{candidate_id}",
        "unit_id": f"unit-{candidate_id}",
        "dedup_status": status,
    }


def test_builds_explicit_per_row_decisions_without_granting_new_signatures() -> None:
    module = _load_module()
    rows = [_row("accepted"), _row("deferred"), _row("duplicate", "duplicate_training_pair")]

    review, adjudication = module.build_canonical_batch_adjudication(
        candidate_rows=rows,
        approved_candidate_ids={"accepted"},
        inherited_rule_authority={
            "status": "granted_source_disjoint_zero_failure",
            "signature_fields": ["candidate_lane"],
            "approved_signatures": ["existing-signature"],
        },
        package_hashes={"package_hash_ledger_sha256": "ledger"},
    )

    assert [row["candidate_id"] for row in review] == ["accepted", "deferred"]
    assert all(row["review_split"] == "canonical_batch" for row in review)
    assert [row["candidate_id"] for row in adjudication["decisions"]] == ["accepted"]
    assert adjudication["rule_authority"]["approved_signatures"] == ["existing-signature"]
    assert adjudication["new_rule_signatures_granted"] == []


def test_rejects_approval_of_noncanonical_candidate() -> None:
    module = _load_module()

    with pytest.raises(ValueError, match="not canonical"):
        module.build_canonical_batch_adjudication(
            candidate_rows=[_row("duplicate", "duplicate_training_pair")],
            approved_candidate_ids={"duplicate"},
            inherited_rule_authority={},
            package_hashes={},
        )
