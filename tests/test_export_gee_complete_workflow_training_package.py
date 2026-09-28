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


def _jsonl_bytes(rows: list[dict]) -> bytes:
    return b"".join(
        (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        for row in rows
    )


def _authority_rows() -> tuple[list[dict], list[dict], list[dict]]:
    risk_rows: list[dict] = []
    facts: list[dict] = []
    texts: list[dict] = []
    lengths = (2, 99, 1)
    for index, length in enumerate(lengths):
        source_sha = f"{index + 1:064x}"
        workflow_id = "output-workflow-1"
        source_path = f"data10000/script_{index + 1}.txt"
        operators = [f"ee.image.op{step}" for step in range(length)]
        l3 = [f"L3_TEST_{step % 94:02d}" for step in range(length)]
        fact_ids = [f"transform:{step}" for step in range(length)]
        risk_rows.append(
            {
                "schema": "gis_recommend.gee_workflow_task_text_candidate.v1",
                "source_sha256": source_sha,
                "source_path": source_path,
                "workflow_id": workflow_id,
                "workflow_key": [source_sha, workflow_id],
                "task_name": f"Task {index}",
                "task_description": f"Description {index}",
                "operator_sequence": operators,
                "l3_sequence": l3,
                "known_omissions": [],
                "risk_flags": [],
                "task_text_status": "generated_source_backed",
                "calibration_stratum": "test-complete-workflow",
                "clauses": [
                    {
                        "text": f"Description {index}",
                        "used_fact_ids": [f"dataset:{index}", *fact_ids, f"output:{index}"],
                    }
                ],
            }
        )
        transformations = [
            {
                "fact_id": fact_id,
                "canonical_operator": operator,
                "l3_code": code,
            }
            for fact_id, operator, code in zip(fact_ids, operators, l3, strict=True)
        ]
        facts.append(
            {
                "schema": "gis_recommend.gee_workflow_fact_bundle.v1",
                "source_sha256": source_sha,
                "source_path": source_path,
                "workflow_id": workflow_id,
                "workflow_key": [source_sha, workflow_id],
                "exact_dag_fingerprint": f"{index + 1:064x}",
                "dataset_facts": [{"fact_id": f"dataset:{index}"}],
                "temporal_facts": [],
                "spatial_input_facts": [],
                "transformation_facts": transformations,
                "output_facts": [{"fact_id": f"output:{index}", "export_kind": "Export.image.toDrive"}],
                "operator_sequence": operators,
                "l3_sequence": l3,
                "known_omissions": [],
                "fact_status": "source_backed_complete",
                "calibration_stratum": "test-complete-workflow",
            }
        )
        texts.append(
            {
                "schema": "gis_recommend.gee_workflow_task_text_candidate.v1",
                "source_sha256": source_sha,
                "source_path": source_path,
                "workflow_id": workflow_id,
                "workflow_key": [source_sha, workflow_id],
                "task_name": f"Task {index}",
                "task_description": f"Description {index}",
                "clauses": [
                    {
                        "text": f"Description {index}",
                        "used_fact_ids": [f"dataset:{index}", *fact_ids, f"output:{index}"],
                    }
                ],
                "operator_sequence": operators,
                "l3_sequence": l3,
                "known_omissions": [],
                "task_text_status": "generated_source_backed",
                "risk_flags": [],
                "calibration_stratum": "test-complete-workflow",
            }
        )
    return risk_rows, facts, texts


def _ledger(risk_bytes: bytes, risk_rows: list[dict], review_bytes: bytes) -> dict:
    deferred = risk_rows[2]
    return {
        "schema": "gis_recommend.gee_workflow_adjudication_ledger.v1",
        "ledger_id": "test-ledger",
        "risk_packet_sha256": hashlib.sha256(risk_bytes).hexdigest(),
        "review_report_path": "docs/reports/test-review.md",
        "review_report_sha256": hashlib.sha256(review_bytes).hexdigest(),
        "default_decision": "pass",
        "expected_counts": {"rows": 3, "pass": 2, "defer_source_ambiguity": 1},
        "exceptions": [
            {
                "source_sha256": deferred["source_sha256"],
                "source_path": deferred["source_path"],
                "workflow_id": deferred["workflow_id"],
                "decision": "defer_source_ambiguity",
                "reason": "source spatial contract is ambiguous",
            }
        ],
    }


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> bytes:
    content = _jsonl_bytes(rows)
    path.write_bytes(content)
    return content


def _build_paths(tmp_path: Path) -> dict[str, Path]:
    risk, facts, texts = _authority_rows()
    risk_path = tmp_path / "risk.jsonl"
    risk_bytes = _write_jsonl(risk_path, risk)
    review_path = tmp_path / "review.md"
    review_bytes = b"# Closed review\n"
    review_path.write_bytes(review_bytes)
    facts_path = tmp_path / "facts.jsonl"
    _write_jsonl(facts_path, facts)
    texts_path = tmp_path / "texts.jsonl"
    _write_jsonl(texts_path, texts)
    ledger_path = tmp_path / "ledger.json"
    _write_json(ledger_path, _ledger(risk_bytes, risk, review_bytes))
    mappings_path = tmp_path / "mappings.json"
    _write_json(
        mappings_path,
        {"l3": {f"L3_TEST_{index:02d}": index for index in range(94)}},
    )
    return {
        "risk_packet_path": risk_path,
        "review_report_path": review_path,
        "fact_bundles_path": facts_path,
        "task_text_candidates_path": texts_path,
        "adjudication_ledger_path": ledger_path,
        "id_mappings_path": mappings_path,
    }


def _test_profile(paths: dict[str, Path], *, expected_package_counts: dict | None = None):
    from scripts.export_gee_complete_workflow_training_package import FrozenAuthorityProfile

    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    return FrozenAuthorityProfile(
        name="test_profile",
        risk_packet_sha256=digest(paths["risk_packet_path"]),
        fact_bundles_sha256=digest(paths["fact_bundles_path"]),
        task_text_candidates_sha256=digest(paths["task_text_candidates_path"]),
        adjudication_ledger_sha256=digest(paths["adjudication_ledger_path"]),
        review_report_sha256=digest(paths["review_report_path"]),
        mapping_sha256=digest(paths["id_mappings_path"]),
        expected_package_counts=expected_package_counts or {
            "adjudication_rows": 3,
            "adjudication_pass": 2,
            "adjudication_defer": 1,
            "semantic_train_rows": 2,
            "v4_100_rows": 1,
            "length_sidecar_rows": 1,
            "fail_closed_rows": 1,
            "duplicate_rows": 0,
        },
    )


def test_freeze_adjudication_is_hash_bound_and_explicit(tmp_path: Path) -> None:
    from scripts.export_gee_complete_workflow_training_package import (
        freeze_adjudication_manifest,
    )

    paths = _build_paths(tmp_path)
    manifest = freeze_adjudication_manifest(
        risk_packet_path=paths["risk_packet_path"],
        adjudication_ledger_path=paths["adjudication_ledger_path"],
        review_report_path=paths["review_report_path"],
    )

    assert len(manifest) == 3
    assert [row["decision"] for row in manifest].count("pass") == 2
    assert [row["decision"] for row in manifest].count("defer_source_ambiguity") == 1
    assert all(len(row["adjudication_row_sha256"]) == 64 for row in manifest)

    paths["risk_packet_path"].write_bytes(paths["risk_packet_path"].read_bytes() + b"\n")
    with pytest.raises(ValueError, match="risk packet SHA256"):
        freeze_adjudication_manifest(
            risk_packet_path=paths["risk_packet_path"],
            adjudication_ledger_path=paths["adjudication_ledger_path"],
            review_report_path=paths["review_report_path"],
        )


def test_freeze_requires_hash_bound_review_report(tmp_path: Path) -> None:
    from scripts.export_gee_complete_workflow_training_package import (
        freeze_adjudication_manifest,
    )

    paths = _build_paths(tmp_path)
    ledger = json.loads(paths["adjudication_ledger_path"].read_text(encoding="utf-8"))
    ledger["review_report_sha256"] = "bad"
    _write_json(paths["adjudication_ledger_path"], ledger)

    with pytest.raises(ValueError, match="review report SHA256"):
        freeze_adjudication_manifest(
            risk_packet_path=paths["risk_packet_path"],
            adjudication_ledger_path=paths["adjudication_ledger_path"],
            review_report_path=paths["review_report_path"],
        )

    paths = _build_paths(tmp_path)
    paths["review_report_path"].write_text("tampered review\n", encoding="utf-8")
    with pytest.raises(ValueError, match="review report SHA256"):
        freeze_adjudication_manifest(
            risk_packet_path=paths["risk_packet_path"],
            adjudication_ledger_path=paths["adjudication_ledger_path"],
            review_report_path=paths["review_report_path"],
        )


def test_build_routes_pass_long_and_defer_without_truncation(tmp_path: Path) -> None:
    from scripts.export_gee_complete_workflow_training_package import build_training_package

    paths = _build_paths(tmp_path)
    result = build_training_package(**paths, profile=_test_profile(paths))

    assert len(result.adjudication_manifest) == 3
    assert len(result.semantic_train_rows) == 2
    assert len(result.v4_100_rows) == 1
    assert len(result.length_sidecar) == 1
    assert len(result.fail_closed_sidecar) == 1
    assert result.length_sidecar[0]["content_length"] == 99
    assert len(result.semantic_train_rows[1]["operator_sequence"]) == 99
    assert result.summary["counts"] == {
        "adjudication_rows": 3,
        "adjudication_pass": 2,
        "adjudication_defer": 1,
        "semantic_train_rows": 2,
        "v4_100_rows": 1,
        "length_sidecar_rows": 1,
        "fail_closed_rows": 1,
        "duplicate_rows": 0,
    }


def test_build_fails_closed_on_fact_reference_chain_and_lineage_mismatch(
    tmp_path: Path,
) -> None:
    from scripts.export_gee_complete_workflow_training_package import build_training_package

    paths = _build_paths(tmp_path)
    texts = [json.loads(line) for line in paths["task_text_candidates_path"].read_text().splitlines()]
    texts[0]["clauses"][0]["used_fact_ids"].append("missing:fact")
    risk = [json.loads(line) for line in paths["risk_packet_path"].read_text().splitlines()]
    risk[0]["clauses"] = copy.deepcopy(texts[0]["clauses"])
    _write_jsonl(paths["task_text_candidates_path"], texts)
    risk_bytes = _write_jsonl(paths["risk_packet_path"], risk)
    _write_json(
        paths["adjudication_ledger_path"],
        _ledger(risk_bytes, risk, paths["review_report_path"].read_bytes()),
    )
    with pytest.raises(ValueError, match="unknown fact IDs"):
        build_training_package(**paths, profile=_test_profile(paths))

    paths = _build_paths(tmp_path)
    facts = [json.loads(line) for line in paths["fact_bundles_path"].read_text().splitlines()]
    facts[0]["l3_sequence"][0] = "L3_TEST_93"
    _write_jsonl(paths["fact_bundles_path"], facts)
    with pytest.raises(ValueError, match="chain/L3 mismatch"):
        build_training_package(**paths, profile=_test_profile(paths))

    paths = _build_paths(tmp_path)
    facts = [json.loads(line) for line in paths["fact_bundles_path"].read_text().splitlines()]
    facts[0]["source_path"] = "data10000/wrong.txt"
    _write_jsonl(paths["fact_bundles_path"], facts)
    with pytest.raises(ValueError, match="source identity mismatch"):
        build_training_package(**paths, profile=_test_profile(paths))


def test_build_fails_closed_on_duplicate_training_pair(tmp_path: Path) -> None:
    from scripts.export_gee_complete_workflow_training_package import build_training_package

    paths = _build_paths(tmp_path)
    texts = [json.loads(line) for line in paths["task_text_candidates_path"].read_text().splitlines()]
    risk = [json.loads(line) for line in paths["risk_packet_path"].read_text().splitlines()]
    facts = [json.loads(line) for line in paths["fact_bundles_path"].read_text().splitlines()]
    texts[1]["task_name"] = texts[0]["task_name"]
    texts[1]["task_description"] = texts[0]["task_description"]
    texts[1]["l3_sequence"] = texts[0]["l3_sequence"]
    texts[1]["operator_sequence"] = texts[0]["operator_sequence"]
    texts[1]["clauses"] = copy.deepcopy(texts[0]["clauses"])
    risk[1]["task_name"] = risk[0]["task_name"]
    risk[1]["task_description"] = risk[0]["task_description"]
    risk[1]["l3_sequence"] = risk[0]["l3_sequence"]
    risk[1]["operator_sequence"] = risk[0]["operator_sequence"]
    risk[1]["clauses"] = copy.deepcopy(risk[0]["clauses"])
    facts[1]["l3_sequence"] = facts[0]["l3_sequence"]
    facts[1]["operator_sequence"] = facts[0]["operator_sequence"]
    facts[1]["dataset_facts"] = copy.deepcopy(facts[0]["dataset_facts"])
    facts[1]["output_facts"] = copy.deepcopy(facts[0]["output_facts"])
    facts[1]["transformation_facts"] = copy.deepcopy(facts[0]["transformation_facts"])
    _write_jsonl(paths["task_text_candidates_path"], texts)
    risk_bytes = _write_jsonl(paths["risk_packet_path"], risk)
    _write_jsonl(paths["fact_bundles_path"], facts)
    _write_json(
        paths["adjudication_ledger_path"],
        _ledger(risk_bytes, risk, paths["review_report_path"].read_bytes()),
    )

    result = build_training_package(
        **paths,
        profile=_test_profile(
            paths,
            expected_package_counts={
                "adjudication_rows": 3,
                "adjudication_pass": 2,
                "adjudication_defer": 1,
                "semantic_train_rows": 1,
                "v4_100_rows": 1,
                "length_sidecar_rows": 0,
                "fail_closed_rows": 1,
                "duplicate_rows": 1,
            },
        ),
    )

    assert len(result.duplicate_sidecar) == 1
    assert len(result.semantic_train_rows) == 1


def test_build_rejects_joined_authority_schema_status_and_omissions(tmp_path: Path) -> None:
    from scripts.export_gee_complete_workflow_training_package import build_training_package

    paths = _build_paths(tmp_path)
    risk = [json.loads(line) for line in paths["risk_packet_path"].read_text().splitlines()]
    risk[0]["schema"] = "wrong"
    risk_bytes = _write_jsonl(paths["risk_packet_path"], risk)
    _write_json(paths["adjudication_ledger_path"], _ledger(risk_bytes, risk, paths["review_report_path"].read_bytes()))
    with pytest.raises(ValueError, match="risk packet schema"):
        build_training_package(**paths, profile=_test_profile(paths))

    paths = _build_paths(tmp_path)
    texts = [json.loads(line) for line in paths["task_text_candidates_path"].read_text().splitlines()]
    texts[0]["known_omissions"] = ["missing temporal"]
    _write_jsonl(paths["task_text_candidates_path"], texts)
    with pytest.raises(ValueError, match="known_omissions"):
        build_training_package(**paths, profile=_test_profile(paths))

    paths = _build_paths(tmp_path)
    facts = [json.loads(line) for line in paths["fact_bundles_path"].read_text().splitlines()]
    facts[0]["calibration_stratum"] = "different-stratum"
    _write_jsonl(paths["fact_bundles_path"], facts)
    with pytest.raises(ValueError, match="calibration_stratum"):
        build_training_package(**paths, profile=_test_profile(paths))


def test_production_profile_is_not_self_authorized_by_ledger(tmp_path: Path) -> None:
    from scripts.export_gee_complete_workflow_training_package import build_training_package

    paths = _build_paths(tmp_path)
    with pytest.raises(ValueError, match="production profile"):
        build_training_package(**paths)


def test_authority_profile_binds_adjudication_ledger_bytes(tmp_path: Path) -> None:
    from scripts.export_gee_complete_workflow_training_package import build_training_package

    paths = _build_paths(tmp_path)
    profile = _test_profile(paths)
    ledger = json.loads(paths["adjudication_ledger_path"].read_text(encoding="utf-8"))
    ledger["ledger_id"] = "tampered-ledger"
    _write_json(paths["adjudication_ledger_path"], ledger)

    with pytest.raises(ValueError, match="adjudication_ledger SHA256"):
        build_training_package(**paths, profile=profile)


def test_production_profile_pins_ledger_and_counts_are_immutable() -> None:
    from scripts.export_gee_complete_workflow_training_package import (
        PRODUCTION_AUTHORITY_PROFILE,
    )

    assert (
        PRODUCTION_AUTHORITY_PROFILE.adjudication_ledger_sha256
        == "68eca1c40820341ceb647521a6dcfc4087f79901a956fd1f1e7612558c91b879"
    )
    with pytest.raises(TypeError):
        PRODUCTION_AUTHORITY_PROFILE.expected_package_counts["v4_100_rows"] = 0


def test_public_source_backed_candidate_validator_reuses_complete_workflow_gate() -> None:
    from scripts.export_gee_complete_workflow_training_package import (
        validate_source_backed_candidate,
    )

    _, facts, texts = _authority_rows()
    key = validate_source_backed_candidate(fact=facts[0], text=texts[0])
    assert key == (texts[0]["source_sha256"], texts[0]["workflow_id"])

    broken = copy.deepcopy(texts[0])
    broken["clauses"][0]["used_fact_ids"].append("unknown-fact")
    with pytest.raises(ValueError, match="unknown fact IDs"):
        validate_source_backed_candidate(fact=facts[0], text=broken)
