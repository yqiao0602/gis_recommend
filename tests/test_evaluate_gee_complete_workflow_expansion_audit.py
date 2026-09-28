from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


HUMAN_FIELDS = (
    "human_dataset_fidelity",
    "human_temporal_fidelity",
    "human_spatial_fidelity",
    "human_transformation_fidelity",
    "human_output_fidelity",
    "human_task_text_fidelity",
    "human_critical_failure",
    "human_decision",
    "human_notes",
)


def _jsonl_bytes(rows: list[dict]) -> bytes:
    return b"".join(
        (
            json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            + "\n"
        ).encode("utf-8")
        for row in rows
    )


def _authority_hash(row: dict) -> str:
    payload = {
        key: value
        for key, value in row.items()
        if key not in HUMAN_FIELDS and key != "audit_row_authority_sha256"
    }
    return hashlib.sha256(
        (
            json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            + "\n"
        ).encode("utf-8")
    ).hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> bytes:
    content = _jsonl_bytes(rows)
    path.write_bytes(content)
    return content


def _audit_authorities(
    tmp_path: Path, *, row_count: int = 30
) -> tuple[dict[str, Path], list[dict]]:
    rows: list[dict] = []
    manifest: list[dict] = []
    for index in range(row_count):
        source_sha = f"{index + 1:064x}"
        workflow_id = "output-workflow-1"
        row = {
            "schema": "gis_recommend.gee_workflow_expansion_audit_row.v1",
            "audit_index": index + 1,
            "proposal_id": f"proposal-{index + 1}",
            "source_sha256": source_sha,
            "source_path": f"data10000/script_{index + 1}.txt",
            "workflow_id": workflow_id,
            "workflow_key": [source_sha, workflow_id],
            "exact_dag_fingerprint": f"{index + 1000:064x}",
            "task_name": f"Task {index + 1}",
            "task_description": f"Description {index + 1}",
            "operator_sequence": ["ee.image.clip"],
            "l3_sequence": ["L3_TEST_00"],
            "risk_stratum": "external_dynamic",
            "source_sha256_verified": True,
            "source_bytes": 100 + index,
            "source_snippet": "L0001: Export.image.toDrive(...);",
            "audit_status": "pending_human_review",
            "training_admission": "not_granted_pending_sampling_audit",
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            **{field: "" for field in HUMAN_FIELDS},
        }
        row["audit_row_authority_sha256"] = _authority_hash(row)
        rows.append(row)
        manifest.append(
            {
                "schema": "gis_recommend.gee_workflow_expansion_audit_source.v1",
                "audit_index": index + 1,
                "source_sha256": source_sha,
                "source_path": row["source_path"],
                "source_bytes": row["source_bytes"],
                "source_sha256_verified": True,
                "resolved_under_source_root": row["source_path"],
                "risk_stratum": row["risk_stratum"],
                "workflow_id": workflow_id,
            }
        )

    original_path = tmp_path / "audit_original.jsonl"
    original_bytes = _write_jsonl(original_path, rows)
    manifest_path = tmp_path / "source_manifest.jsonl"
    manifest_bytes = _write_jsonl(manifest_path, manifest)
    reviewed_packet_path = tmp_path / "reviewed_packet.jsonl"
    _write_jsonl(
        reviewed_packet_path,
        [
            {
                "source_sha256": f"{999:064x}",
                "source_path": "data10000/reviewed.txt",
                "workflow_id": "output-workflow-1",
            }
        ],
    )
    ledger_path = tmp_path / "expansion_hash_ledger.json"
    _write_json(
        ledger_path,
        {
            "schema": "gis_recommend.gee_workflow_expansion_hash_ledger.v1",
            "audit_reviewed_packet_sha256": hashlib.sha256(
                reviewed_packet_path.read_bytes()
            ).hexdigest(),
            "artifact_sha256": {
                f"audit_sample_{row_count}.jsonl": hashlib.sha256(original_bytes).hexdigest(),
                "audit_source_manifest.jsonl": hashlib.sha256(manifest_bytes).hexdigest(),
            },
        },
    )
    reviewed_path = tmp_path / "audit_reviewed.jsonl"
    completed = copy.deepcopy(rows)
    for row in completed:
        for field in HUMAN_FIELDS[:6]:
            row[field] = "pass"
        row["human_critical_failure"] = "no"
        row["human_decision"] = "pass"
        row["human_notes"] = "source-backed review complete"
    _write_jsonl(reviewed_path, completed)
    paths = {
        "original_audit_path": original_path,
        "reviewed_audit_path": reviewed_path,
        "source_manifest_path": manifest_path,
        "reviewed_packet_path": reviewed_packet_path,
        "expansion_hash_ledger_path": ledger_path,
    }
    return paths, completed


def _profile(paths: dict[str, Path], *, expected_rows: int = 30):
    from scripts.evaluate_gee_complete_workflow_expansion_audit import (
        FrozenAuditEvaluationProfile,
    )

    digest = lambda key: hashlib.sha256(paths[key].read_bytes()).hexdigest()
    return FrozenAuditEvaluationProfile(
        name="synthetic-evaluation",
        expansion_hash_ledger_sha256=digest("expansion_hash_ledger_path"),
        original_audit_sha256=digest("original_audit_path"),
        source_manifest_sha256=digest("source_manifest_path"),
        reviewed_packet_sha256=digest("reviewed_packet_path"),
        expected_rows=expected_rows,
    )


def test_all_pass_review_meets_precision_wilson_and_critical_gates(
    tmp_path: Path,
) -> None:
    from scripts.evaluate_gee_complete_workflow_expansion_audit import (
        evaluate_sampling_audit,
    )

    paths, _ = _audit_authorities(tmp_path)
    result = evaluate_sampling_audit(**paths, profile=_profile(paths))

    assert result.summary["decision"] == "passed_for_larger_source_disjoint_replay"
    assert result.summary["reviewed_rows"] == 30
    assert result.summary["pass_rows"] == 30
    assert result.summary["point_precision"] == 1.0
    assert result.summary["wilson_95_lower"] >= 0.85
    assert result.summary["critical_failure_rows"] == 0
    assert result.summary["training_rows_emitted"] == 0


def test_50_row_audit_uses_its_dynamic_ledger_artifact_name(
    tmp_path: Path,
) -> None:
    from scripts.evaluate_gee_complete_workflow_expansion_audit import (
        evaluate_sampling_audit,
    )

    paths, _ = _audit_authorities(tmp_path, row_count=50)
    result = evaluate_sampling_audit(
        **paths,
        profile=_profile(paths, expected_rows=50),
    )

    assert result.summary["reviewed_rows"] == 50
    assert result.summary["pass_rows"] == 50
    assert result.summary["decision"] == "passed_for_larger_source_disjoint_replay"


def test_audit_rejects_expansion_ledger_reviewed_packet_drift(
    tmp_path: Path,
) -> None:
    from scripts.evaluate_gee_complete_workflow_expansion_audit import (
        evaluate_sampling_audit,
    )

    paths, _ = _audit_authorities(tmp_path)
    ledger = json.loads(
        paths["expansion_hash_ledger_path"].read_text(encoding="utf-8")
    )
    ledger["audit_reviewed_packet_sha256"] = "0" * 64
    _write_json(paths["expansion_hash_ledger_path"], ledger)

    with pytest.raises(ValueError, match="reviewed packet hash drift"):
        evaluate_sampling_audit(**paths, profile=_profile(paths))


def test_one_failed_review_fails_rule_gate_even_when_point_precision_is_high(
    tmp_path: Path,
) -> None:
    from scripts.evaluate_gee_complete_workflow_expansion_audit import (
        evaluate_sampling_audit,
    )

    paths, completed = _audit_authorities(tmp_path)
    completed[0]["human_task_text_fidelity"] = "fail"
    completed[0]["human_decision"] = "fail"
    completed[0]["human_notes"] = "task text is not source faithful"
    _write_jsonl(paths["reviewed_audit_path"], completed)

    result = evaluate_sampling_audit(**paths, profile=_profile(paths))

    assert result.summary["point_precision"] >= 0.95
    assert result.summary["wilson_95_lower"] < 0.85
    assert result.summary["decision"] == "failed_rule_repair_required"


def test_incomplete_invalid_and_critical_reviews_fail_closed(tmp_path: Path) -> None:
    from scripts.evaluate_gee_complete_workflow_expansion_audit import (
        evaluate_sampling_audit,
    )

    paths, completed = _audit_authorities(tmp_path)
    completed[0]["human_decision"] = ""
    _write_jsonl(paths["reviewed_audit_path"], completed)
    with pytest.raises(ValueError, match="incomplete audit verdict"):
        evaluate_sampling_audit(**paths, profile=_profile(paths))

    completed[0]["human_decision"] = "maybe"
    _write_jsonl(paths["reviewed_audit_path"], completed)
    with pytest.raises(ValueError, match="invalid audit verdict"):
        evaluate_sampling_audit(**paths, profile=_profile(paths))

    completed[0]["human_decision"] = "pass"
    completed[0]["human_task_text_fidelity"] = "fail"
    _write_jsonl(paths["reviewed_audit_path"], completed)
    with pytest.raises(ValueError, match="inconsistent audit verdict"):
        evaluate_sampling_audit(**paths, profile=_profile(paths))

    completed[0]["human_task_text_fidelity"] = "pass"
    completed[0]["human_decision"] = "fail"
    completed[0]["human_critical_failure"] = "yes"
    completed[0]["human_notes"] = "critical chain hallucination"
    _write_jsonl(paths["reviewed_audit_path"], completed)
    result = evaluate_sampling_audit(**paths, profile=_profile(paths))
    assert result.summary["critical_failure_rows"] == 1
    assert result.summary["decision"] == "failed_rule_repair_required"


def test_authority_drift_and_non_source_disjoint_review_are_rejected(
    tmp_path: Path,
) -> None:
    from scripts.evaluate_gee_complete_workflow_expansion_audit import (
        evaluate_sampling_audit,
    )

    paths, completed = _audit_authorities(tmp_path)
    completed[0]["task_description"] = "drifted immutable text"
    _write_jsonl(paths["reviewed_audit_path"], completed)
    with pytest.raises(ValueError, match="authority drift"):
        evaluate_sampling_audit(**paths, profile=_profile(paths))

    paths, _ = _audit_authorities(tmp_path)
    first_source = json.loads(paths["original_audit_path"].read_text().splitlines()[0])[
        "source_sha256"
    ]
    _write_jsonl(
        paths["reviewed_packet_path"],
        [
            {
                "source_sha256": first_source,
                "source_path": "data10000/overlap.txt",
                "workflow_id": "output-workflow-99",
            }
        ],
    )
    ledger = json.loads(
        paths["expansion_hash_ledger_path"].read_text(encoding="utf-8")
    )
    ledger["audit_reviewed_packet_sha256"] = hashlib.sha256(
        paths["reviewed_packet_path"].read_bytes()
    ).hexdigest()
    _write_json(paths["expansion_hash_ledger_path"], ledger)
    with pytest.raises(ValueError, match="source-disjoint"):
        evaluate_sampling_audit(**paths, profile=_profile(paths))
