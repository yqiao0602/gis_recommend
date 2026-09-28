from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _candidate(
    number: int,
    *,
    workflow_id: str = "output-workflow-1",
    length: int = 2,
    task_name: str | None = None,
    task_description: str | None = None,
) -> tuple[dict, dict]:
    source_sha = f"{number:064x}"
    source_path = f"data10000/script_{number}.txt"
    operators = [f"ee.image.op{step}" for step in range(length)]
    l3_sequence = [f"L3_TEST_{step % 94:02d}" for step in range(length)]
    fact_ids = [f"transform:{number}:{step}" for step in range(length)]
    name = task_name or f"Task {number}"
    description = task_description or f"Description {number}"
    fact = {
        "schema": "gis_recommend.gee_workflow_fact_bundle.v1",
        "source_sha256": source_sha,
        "source_path": source_path,
        "workflow_id": workflow_id,
        "workflow_key": [source_sha, workflow_id],
        "exact_dag_fingerprint": f"{number + 1000:064x}",
        "dataset_facts": [{"fact_id": f"dataset:{number}"}],
        "temporal_facts": [],
        "spatial_input_facts": [],
        "transformation_facts": [
            {
                "fact_id": fact_id,
                "canonical_operator": operator,
                "l3_code": code,
            }
            for fact_id, operator, code in zip(
                fact_ids, operators, l3_sequence, strict=True
            )
        ],
        "output_facts": [
            {"fact_id": f"output:{number}", "export_kind": "Export.image.toDrive"}
        ],
        "operator_sequence": operators,
        "l3_sequence": l3_sequence,
        "known_omissions": [],
        "fact_status": "source_backed_complete",
        "calibration_stratum": "test-complete-workflow",
    }
    text = {
        "schema": "gis_recommend.gee_workflow_task_text_candidate.v1",
        "source_sha256": source_sha,
        "source_path": source_path,
        "workflow_id": workflow_id,
        "workflow_key": [source_sha, workflow_id],
        "task_name": name,
        "task_description": description,
        "clauses": [
            {
                "text": description,
                "used_fact_ids": [
                    f"dataset:{number}",
                    *fact_ids,
                    f"output:{number}",
                ],
            }
        ],
        "operator_sequence": operators,
        "l3_sequence": l3_sequence,
        "known_omissions": [],
        "task_text_status": "generated_source_backed",
        "risk_flags": [],
        "calibration_stratum": "test-complete-workflow",
    }
    return fact, text


def _authorities(tmp_path: Path) -> dict[str, Path]:
    reviewed_fact, reviewed = _candidate(1)
    overlap_fact, overlap = _candidate(1, workflow_id="output-workflow-2")
    eligible_fact, eligible = _candidate(
        2, task_name="Eligible task", task_description="Eligible description"
    )
    existing_duplicate_fact, existing_duplicate = _candidate(
        3, task_name=" Existing   Task ", task_description=" Existing description "
    )
    batch_duplicate_fact, batch_duplicate = _candidate(
        4, task_name=" eligible TASK ", task_description="Eligible  description"
    )
    long_fact, long_text = _candidate(5, length=99)
    invalid_fact, invalid_text = _candidate(6)
    invalid_text["clauses"][0]["used_fact_ids"].append("unknown:fact")

    # Proves source-overlap routing happens before semantic validation.
    overlap["clauses"][0]["used_fact_ids"].append("unknown:overlap")

    facts = [
        reviewed_fact,
        overlap_fact,
        eligible_fact,
        existing_duplicate_fact,
        batch_duplicate_fact,
        long_fact,
        invalid_fact,
    ]
    texts = [
        reviewed,
        overlap,
        eligible,
        existing_duplicate,
        batch_duplicate,
        long_text,
        invalid_text,
    ]
    existing_rows = [
        {
            "schema": "gis_recommend.gee_workflow_train_row.v1",
            "source_sha256": f"{99:064x}",
            "source_path": "existing/script.txt",
            "workflow_id": "output-workflow-1",
            "task_name": "existing task",
            "task_description": "existing   description",
            "l3_sequence": list(existing_duplicate["l3_sequence"]),
            "training_admission": "granted_train_only_gee_complete_workflow_v1",
        }
    ]
    paths = {
        "fact_bundles_path": tmp_path / "facts.jsonl",
        "task_text_candidates_path": tmp_path / "texts.jsonl",
        "reviewed_packet_path": tmp_path / "reviewed.jsonl",
        "existing_semantic_rows_path": tmp_path / "semantic.jsonl",
        "id_mappings_path": tmp_path / "mappings.json",
    }
    _write_jsonl(paths["fact_bundles_path"], facts)
    _write_jsonl(paths["task_text_candidates_path"], texts)
    _write_jsonl(paths["reviewed_packet_path"], [reviewed])
    _write_jsonl(paths["existing_semantic_rows_path"], existing_rows)
    _write_json(
        paths["id_mappings_path"],
        {"l3": {f"L3_TEST_{index:02d}": index for index in range(94)}},
    )
    return paths


def _profile(paths: dict[str, Path], expected_counts: dict[str, int]):
    from scripts.build_gee_complete_workflow_expansion_batch import (
        FrozenExpansionProfile,
    )

    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    return FrozenExpansionProfile(
        name="synthetic_expansion",
        fact_bundles_sha256=digest(paths["fact_bundles_path"]),
        task_text_candidates_sha256=digest(paths["task_text_candidates_path"]),
        reviewed_packet_sha256=digest(paths["reviewed_packet_path"]),
        existing_semantic_rows_sha256=digest(paths["existing_semantic_rows_path"]),
        mapping_sha256=digest(paths["id_mappings_path"]),
        expected_counts=expected_counts,
    )


def _freezer_authorities(tmp_path: Path, *, candidate_count: int = 30) -> dict[str, Path]:
    risk_flags = (
        ["dynamic_transformation_arguments", "external_spatial_identifier"],
        ["repeated_operator"],
        ["multiple_dataset_facts"],
        ["no_source_backed_temporal_operation"],
        ["external_spatial_identifier"],
        ["no_source_backed_spatial_input"],
    )
    pairs = [_candidate(number) for number in range(1, candidate_count + 1)]
    for index, (_, text) in enumerate(pairs):
        text["risk_flags"] = list(risk_flags[index % len(risk_flags)])

    paths = {
        "fact_bundles_path": tmp_path / "facts.jsonl",
        "task_text_candidates_path": tmp_path / "texts.jsonl",
        "reviewed_packet_path": tmp_path / "reviewed.jsonl",
        "existing_semantic_rows_path": tmp_path / "semantic.jsonl",
        "id_mappings_path": tmp_path / "mappings.json",
    }
    _write_jsonl(paths["fact_bundles_path"], [fact for fact, _ in pairs])
    _write_jsonl(paths["task_text_candidates_path"], [text for _, text in pairs])
    _write_jsonl(paths["reviewed_packet_path"], [])
    _write_jsonl(paths["existing_semantic_rows_path"], [])
    _write_json(
        paths["id_mappings_path"],
        {"l3": {f"L3_TEST_{index:02d}": index for index in range(94)}},
    )
    return paths


def test_freezer_writes_deterministic_replayable_hash_bound_profile(
    tmp_path: Path,
) -> None:
    from scripts.build_gee_complete_workflow_expansion_batch import (
        build_expansion_census,
        load_expansion_batch_profile,
    )
    from scripts.freeze_gee_expansion_profile import main as freeze_main

    paths = _freezer_authorities(tmp_path)
    output_a = tmp_path / "profile-a.json"
    output_b = tmp_path / "profile-b.json"
    common = [
        "--fact-bundles", str(paths["fact_bundles_path"]),
        "--task-text-candidates", str(paths["task_text_candidates_path"]),
        "--reviewed-packet", str(paths["reviewed_packet_path"]),
        "--existing-semantic-rows", str(paths["existing_semantic_rows_path"]),
        "--id-mappings", str(paths["id_mappings_path"]),
        "--profile-name", "synthetic_freezer_batch",
        "--audit-name", "synthetic_freezer_audit_30",
    ]

    payload_a = freeze_main([*common, "--output", str(output_a)])
    payload_b = freeze_main([*common, "--output", str(output_b)])

    assert output_a.read_bytes() == output_b.read_bytes()
    assert payload_a == payload_b
    assert (
        payload_a["schema"]
        == "gis_recommend.gee_workflow_expansion_batch_profile.v1"
    )
    assert payload_a["expected_counts"] == {
        "canonical_candidates": 30,
        "reviewed_identities": 0,
        "remaining": 30,
        "excluded_reviewed_source_overlap": 0,
        "proposal_eligible": 30,
        "excluded_existing_or_batch_duplicate": 0,
        "deferred_length": 0,
        "fail_closed_semantic_gate": 0,
    }
    expected_strata = {
        "external_dynamic": 5,
        "long_or_repeated": 5,
        "multi_dataset_private": 5,
        "no_temporal_operation": 5,
        "other": 5,
        "spatial_omission": 5,
    }
    assert payload_a["audit"] == {
        "name": "synthetic_freezer_audit_30",
        "sample_size": 30,
        "expected_source_support": expected_strata,
        "quotas": expected_strata,
    }
    assert payload_a["training_admission"] == "not_granted_pending_sampling_audit"
    assert payload_a["validation_eligible"] is False
    assert payload_a["test_eligible"] is False
    assert payload_a["production_merge"] == "not_granted"

    profile, audit_profile = load_expansion_batch_profile(output_a)
    replay = build_expansion_census(**paths, profile=profile)
    assert replay.summary["counts"] == payload_a["expected_counts"]
    assert dict(audit_profile.expected_source_support) == expected_strata
    assert dict(audit_profile.quotas) == expected_strata

    paths["task_text_candidates_path"].write_bytes(
        paths["task_text_candidates_path"].read_bytes() + b"\n"
    )
    with pytest.raises(ValueError, match="task text candidates SHA256"):
        build_expansion_census(**paths, profile=profile)


def test_freezer_cli_is_directly_executable() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "freeze_gee_expansion_profile.py"),
            "--help",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "--fact-bundles" in result.stdout


def test_freezer_cli_writes_a_50_row_audit_profile(tmp_path: Path) -> None:
    from scripts.freeze_gee_expansion_profile import main as freeze_main

    paths = _freezer_authorities(tmp_path, candidate_count=50)
    output = tmp_path / "profile-50.json"

    payload = freeze_main(
        [
            "--fact-bundles",
            str(paths["fact_bundles_path"]),
            "--task-text-candidates",
            str(paths["task_text_candidates_path"]),
            "--reviewed-packet",
            str(paths["reviewed_packet_path"]),
            "--existing-semantic-rows",
            str(paths["existing_semantic_rows_path"]),
            "--id-mappings",
            str(paths["id_mappings_path"]),
            "--profile-name",
            "synthetic_freezer_batch_50",
            "--audit-name",
            "synthetic_freezer_audit_50",
            "--audit-sample-size",
            "50",
            "--output",
            str(output),
        ]
    )

    written = json.loads(output.read_text(encoding="utf-8"))
    assert payload["audit"]["sample_size"] == 50
    assert sum(payload["audit"]["quotas"].values()) == 50
    assert written == payload


def _external_profile_payload() -> dict:
    return {
        "schema": "gis_recommend.gee_workflow_expansion_batch_profile.v1",
        "name": "synthetic_external_batch",
        "authority_sha256": {
            "existing_semantic_rows": "a" * 64,
            "fact_bundles": "b" * 64,
            "mapping": "c" * 64,
            "reviewed_packet": "d" * 64,
            "task_text_candidates": "e" * 64,
        },
        "expected_counts": {
            "canonical_candidates": 0,
            "reviewed_identities": 0,
            "remaining": 0,
            "excluded_reviewed_source_overlap": 0,
            "proposal_eligible": 0,
            "excluded_existing_or_batch_duplicate": 0,
            "deferred_length": 0,
            "fail_closed_semantic_gate": 0,
        },
        "audit": {
            "name": "synthetic_external_audit",
            "sample_size": 0,
            "expected_source_support": {
                "external_dynamic": 0,
                "long_or_repeated": 0,
                "multi_dataset_private": 0,
                "no_temporal_operation": 0,
                "other": 0,
                "spatial_omission": 0,
            },
            "quotas": {
                "external_dynamic": 0,
                "long_or_repeated": 0,
                "multi_dataset_private": 0,
                "no_temporal_operation": 0,
                "other": 0,
                "spatial_omission": 0,
            },
        },
        "training_admission": "not_granted_pending_sampling_audit",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def test_external_batch_profile_loader_returns_frozen_profiles(tmp_path: Path) -> None:
    from scripts.build_gee_complete_workflow_expansion_batch import (
        load_expansion_batch_profile,
    )

    path = tmp_path / "authority_profile.json"
    _write_json(path, _external_profile_payload())

    expansion, audit = load_expansion_batch_profile(path)

    assert expansion.name == "synthetic_external_batch"
    assert expansion.fact_bundles_sha256 == "b" * 64
    assert expansion.expected_counts["proposal_eligible"] == 0
    assert audit.name == "synthetic_external_audit"
    assert audit.sample_size == 0
    assert tuple(audit.quotas) == (
        "external_dynamic",
        "long_or_repeated",
        "multi_dataset_private",
        "no_temporal_operation",
        "other",
        "spatial_omission",
    )
    with pytest.raises(TypeError):
        expansion.expected_counts["proposal_eligible"] = 1
    with pytest.raises(TypeError):
        audit.quotas["other"] = 1


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda payload: payload.update(schema="wrong"), "schema"),
        (
            lambda payload: payload["authority_sha256"].pop("mapping"),
            "authority_sha256",
        ),
        (
            lambda payload: payload.update(training_admission="granted_train_only"),
            "training_admission",
        ),
        (
            lambda payload: payload["audit"].update(sample_size=1),
            "audit quotas",
        ),
    ],
)
def test_external_batch_profile_loader_fails_closed(
    tmp_path: Path, mutate, message: str
) -> None:
    from scripts.build_gee_complete_workflow_expansion_batch import (
        load_expansion_batch_profile,
    )

    payload = _external_profile_payload()
    mutate(payload)
    path = tmp_path / "bad_profile.json"
    _write_json(path, payload)

    with pytest.raises(ValueError, match=message):
        load_expansion_batch_profile(path)


def test_cli_optionally_wires_external_profiles_and_preserves_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.build_gee_complete_workflow_expansion_batch as module

    profile_path = tmp_path / "authority_profile.json"
    _write_json(profile_path, _external_profile_payload())
    observed: list[tuple[str, str]] = []
    observed_audit_reviewed_packets: list[Path | None] = []

    def fake_census(**kwargs):
        observed.append(("census", kwargs["profile"].name))
        return SimpleNamespace(proposal_rows=[], summary={"profile": kwargs["profile"].name})

    def fake_audit(**kwargs):
        observed.append(("audit", kwargs["profile"].name))
        observed_audit_reviewed_packets.append(
            kwargs["audit_reviewed_packet_path"]
        )
        return SimpleNamespace(summary={"profile": kwargs["profile"].name})

    monkeypatch.setattr(module, "build_expansion_census", fake_census)
    monkeypatch.setattr(module, "build_stratified_audit_packet", fake_audit)
    monkeypatch.setattr(module, "write_expansion_outputs", lambda **kwargs: {"ok": True})
    common = [
        "--fact-bundles", str(tmp_path / "facts.jsonl"),
        "--task-text-candidates", str(tmp_path / "texts.jsonl"),
        "--reviewed-packet", str(tmp_path / "reviewed.jsonl"),
        "--existing-semantic-rows", str(tmp_path / "semantic.jsonl"),
        "--id-mappings", str(tmp_path / "mapping.json"),
        "--source-root", str(tmp_path / "source"),
        "--output-dir", str(tmp_path / "output"),
    ]

    audit_reviewed_path = tmp_path / "audit_reviewed.jsonl"
    module.main(
        [
            *common,
            "--authority-profile",
            str(profile_path),
            "--audit-reviewed-packet",
            str(audit_reviewed_path),
        ]
    )
    module.main(common)

    assert observed == [
        ("census", "synthetic_external_batch"),
        ("audit", "synthetic_external_audit"),
        ("census", module.PRODUCTION_EXPANSION_PROFILE.name),
        ("audit", module.PRODUCTION_AUDIT_SAMPLING_PROFILE.name),
    ]
    assert observed_audit_reviewed_packets == [audit_reviewed_path, None]

def test_census_assigns_every_remaining_identity_by_fixed_priority(tmp_path: Path) -> None:
    from scripts.build_gee_complete_workflow_expansion_batch import (
        build_expansion_census,
    )

    paths = _authorities(tmp_path)
    expected_counts = {
        "canonical_candidates": 7,
        "reviewed_identities": 1,
        "remaining": 6,
        "excluded_reviewed_source_overlap": 1,
        "proposal_eligible": 1,
        "excluded_existing_or_batch_duplicate": 2,
        "deferred_length": 1,
        "fail_closed_semantic_gate": 1,
    }

    result = build_expansion_census(
        **paths, profile=_profile(paths, expected_counts)
    )

    assert result.summary["counts"] == expected_counts
    assert len(result.remaining_ledger) == expected_counts["remaining"]
    by_identity = {
        (row["source_sha256"], row["workflow_id"]): row
        for row in result.remaining_ledger
    }
    assert len(by_identity) == len(result.remaining_ledger)
    assert (f"{1:064x}", "output-workflow-1") not in by_identity
    assert by_identity[(f"{1:064x}", "output-workflow-2")][
        "terminal_status"
    ] == "excluded_reviewed_source_overlap"
    assert by_identity[(f"{2:064x}", "output-workflow-1")][
        "terminal_status"
    ] == "proposal_eligible"
    assert by_identity[(f"{3:064x}", "output-workflow-1")][
        "terminal_status"
    ] == "excluded_existing_or_batch_duplicate"
    assert by_identity[(f"{4:064x}", "output-workflow-1")][
        "terminal_status"
    ] == "excluded_existing_or_batch_duplicate"
    assert by_identity[(f"{5:064x}", "output-workflow-1")][
        "terminal_status"
    ] == "deferred_length"
    assert by_identity[(f"{6:064x}", "output-workflow-1")][
        "terminal_status"
    ] == "fail_closed_semantic_gate"

    terminal_counts = {
        status: sum(row["terminal_status"] == status for row in result.remaining_ledger)
        for status in (
            "excluded_reviewed_source_overlap",
            "proposal_eligible",
            "excluded_existing_or_batch_duplicate",
            "deferred_length",
            "fail_closed_semantic_gate",
        )
    }
    assert sum(terminal_counts.values()) == expected_counts["remaining"]
    assert all(row["reason"] for row in result.remaining_ledger)
    assert all(
        row["training_admission"] == "not_granted_pending_sampling_audit"
        and row["validation_eligible"] is False
        and row["test_eligible"] is False
        and row["production_merge"] == "not_granted"
        for row in result.remaining_ledger
    )

    assert len(result.source_overlap_sidecar) == 1
    assert len(result.fail_closed_sidecar) == 1
    assert len(result.duplicate_sidecar) == 2
    assert len(result.length_sidecar) == 1
    assert result.length_sidecar[0]["content_length"] == 99
    assert result.length_sidecar[0]["model_sequence_length"] == 101
    assert len(result.length_sidecar[0]["l3_sequence"]) == 99

    assert len(result.proposal_rows) == 1
    proposal = result.proposal_rows[0]
    assert proposal["schema"] == "gis_recommend.gee_workflow_expansion_proposal.v1"
    assert proposal["proposal_status"] == "pending_sampling_audit"
    assert proposal["training_admission"] == "not_granted_pending_sampling_audit"
    assert proposal["validation_eligible"] is False
    assert proposal["test_eligible"] is False
    assert proposal["production_merge"] == "not_granted"
    assert proposal["schema"] != "gis_recommend.gee_workflow_train_row.v1"


def test_authorities_are_hash_bound_and_default_profile_cannot_self_authorize(
    tmp_path: Path,
) -> None:
    from scripts.build_gee_complete_workflow_expansion_batch import (
        PRODUCTION_EXPANSION_PROFILE,
        build_expansion_census,
    )

    paths = _authorities(tmp_path)
    expected_counts = {
        "canonical_candidates": 7,
        "reviewed_identities": 1,
        "remaining": 6,
        "excluded_reviewed_source_overlap": 1,
        "proposal_eligible": 1,
        "excluded_existing_or_batch_duplicate": 2,
        "deferred_length": 1,
        "fail_closed_semantic_gate": 1,
    }
    profile = _profile(paths, expected_counts)
    paths["task_text_candidates_path"].write_bytes(
        paths["task_text_candidates_path"].read_bytes() + b"\n"
    )

    with pytest.raises(ValueError, match="task text candidates SHA256"):
        build_expansion_census(**paths, profile=profile)
    with pytest.raises(ValueError, match="production profile"):
        build_expansion_census(**paths)

    assert PRODUCTION_EXPANSION_PROFILE.expected_counts == {
        "canonical_candidates": 176,
        "reviewed_identities": 50,
        "remaining": 126,
        "excluded_reviewed_source_overlap": 43,
        "proposal_eligible": 83,
        "excluded_existing_or_batch_duplicate": 0,
        "deferred_length": 0,
        "fail_closed_semantic_gate": 0,
    }
    for value in (
        PRODUCTION_EXPANSION_PROFILE.fact_bundles_sha256,
        PRODUCTION_EXPANSION_PROFILE.task_text_candidates_sha256,
        PRODUCTION_EXPANSION_PROFILE.reviewed_packet_sha256,
        PRODUCTION_EXPANSION_PROFILE.existing_semantic_rows_sha256,
        PRODUCTION_EXPANSION_PROFILE.mapping_sha256,
    ):
        assert len(value) == 64


def test_mapping_authority_must_be_a_stable_94_bijection(tmp_path: Path) -> None:
    from scripts.build_gee_complete_workflow_expansion_batch import (
        build_expansion_census,
    )

    paths = _authorities(tmp_path)
    _write_json(paths["id_mappings_path"], {"l3": {"L3_ONLY": 0}})
    expected_counts = {
        "canonical_candidates": 7,
        "reviewed_identities": 1,
        "remaining": 6,
        "excluded_reviewed_source_overlap": 1,
        "proposal_eligible": 1,
        "excluded_existing_or_batch_duplicate": 2,
        "deferred_length": 1,
        "fail_closed_semantic_gate": 1,
    }

    with pytest.raises(ValueError, match="94"):
        build_expansion_census(
            **paths, profile=_profile(paths, expected_counts)
        )


def test_unmapped_candidate_chain_fails_closed(tmp_path: Path) -> None:
    from scripts.build_gee_complete_workflow_expansion_batch import (
        build_expansion_census,
    )

    paths = _authorities(tmp_path)
    texts = [
        json.loads(line)
        for line in paths["task_text_candidates_path"].read_text().splitlines()
    ]
    facts = [
        json.loads(line)
        for line in paths["fact_bundles_path"].read_text().splitlines()
    ]
    texts[1]["l3_sequence"][0] = "L3_UNMAPPED"
    texts[1]["clauses"][0]["used_fact_ids"].remove("unknown:overlap")
    facts[1]["l3_sequence"][0] = "L3_UNMAPPED"
    facts[1]["transformation_facts"][0]["l3_code"] = "L3_UNMAPPED"
    # Move the candidate off the reviewed source so mapping is the deciding gate.
    for row in (texts[1], facts[1]):
        row["source_sha256"] = f"{7:064x}"
        row["source_path"] = "data10000/script_7.txt"
        row["workflow_key"] = [f"{7:064x}", row["workflow_id"]]
    _write_jsonl(paths["task_text_candidates_path"], texts)
    _write_jsonl(paths["fact_bundles_path"], facts)
    expected_counts = {
        "canonical_candidates": 7,
        "reviewed_identities": 1,
        "remaining": 6,
        "excluded_reviewed_source_overlap": 0,
        "proposal_eligible": 1,
        "excluded_existing_or_batch_duplicate": 2,
        "deferred_length": 1,
        "fail_closed_semantic_gate": 2,
    }

    result = build_expansion_census(
        **paths, profile=_profile(paths, expected_counts)
    )

    failed = {
        (row["source_sha256"], row["workflow_id"]): row
        for row in result.fail_closed_sidecar
    }
    assert "unmapped L3" in failed[(f"{7:064x}", "output-workflow-2")]["reason"]


def test_profile_expected_counts_are_immutable(tmp_path: Path) -> None:
    paths = _authorities(tmp_path)
    counts = {
        "canonical_candidates": 7,
        "reviewed_identities": 1,
        "remaining": 6,
        "excluded_reviewed_source_overlap": 1,
        "proposal_eligible": 1,
        "excluded_existing_or_batch_duplicate": 2,
        "deferred_length": 1,
        "fail_closed_semantic_gate": 1,
    }
    profile = _profile(paths, counts)
    counts["proposal_eligible"] = 999

    assert profile.expected_counts["proposal_eligible"] == 1
    with pytest.raises(TypeError):
        profile.expected_counts["proposal_eligible"] = 999


def _source_proposal(
    source_root: Path,
    name: str,
    *,
    risk_flags: list[str],
    workflow_id: str = "output-workflow-1",
) -> dict:
    relative_path = Path("data10000") / f"{name}.txt"
    content = (
        f"var source = ee.Image('{name}');\n"
        f"var result = source.clip(region);\n"
        f"Export.image.toDrive({{image: result, description: '{name}'}});\n"
    ).encode("utf-8")
    path = source_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    source_sha = hashlib.sha256(content).hexdigest()
    return {
        "schema": "gis_recommend.gee_workflow_expansion_proposal.v1",
        "proposal_id": f"proposal-{name}-{workflow_id}",
        "source_sha256": source_sha,
        "source_path": relative_path.as_posix(),
        "workflow_id": workflow_id,
        "workflow_key": [source_sha, workflow_id],
        "exact_dag_fingerprint": hashlib.sha256(
            f"{source_sha}/{workflow_id}".encode("utf-8")
        ).hexdigest(),
        "task_name": f"Task {name}",
        "task_description": f"Process {name} and export the result.",
        "operator_sequence": ["ee.image.clip"],
        "l3_sequence": ["L3_TEST_00"],
        "risk_flags": risk_flags,
        "known_omissions": [],
        "calibration_stratum": "linear_export",
        "evidence_locations": [
            {
                "fact_id": "output-0001",
                "fact_type": "output",
                "source_location": {
                    "start_line": 3,
                    "end_line": 3,
                    "start_column": 0,
                    "end_column": 70,
                },
            }
        ],
        "fact_bundle_sha256": hashlib.sha256(f"fact-{name}".encode()).hexdigest(),
        "task_text_candidate_sha256": hashlib.sha256(f"text-{name}".encode()).hexdigest(),
        "proposal_status": "pending_sampling_audit",
        "training_admission": "not_granted_pending_sampling_audit",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def test_risk_strata_and_largest_remainder_quotas_are_deterministic() -> None:
    from scripts.build_gee_complete_workflow_expansion_batch import (
        RISK_STRATA,
        classify_risk_stratum,
        largest_remainder_quotas,
    )

    cases = {
        "spatial_omission": ["no_source_backed_spatial_input", "repeated_operator"],
        "long_or_repeated": [
            "dynamic_transformation_arguments",
            "external_spatial_identifier",
            "repeated_operator",
        ],
        "multi_dataset_private": [
            "multiple_dataset_facts",
            "private_asset_redacted",
            "no_source_backed_temporal_operation",
        ],
        "no_temporal_operation": ["no_source_backed_temporal_operation"],
        "external_dynamic": [
            "dynamic_transformation_arguments",
            "external_spatial_identifier",
        ],
        "other": ["external_spatial_identifier"],
    }
    for expected, flags in cases.items():
        assert classify_risk_stratum({"risk_flags": flags}) == expected

    support = {
        "external_dynamic": 22,
        "long_or_repeated": 5,
        "multi_dataset_private": 9,
        "no_temporal_operation": 7,
        "other": 1,
        "spatial_omission": 6,
    }
    assert tuple(support) == RISK_STRATA
    assert largest_remainder_quotas(support, sample_size=30) == {
        "external_dynamic": 13,
        "long_or_repeated": 3,
        "multi_dataset_private": 5,
        "no_temporal_operation": 4,
        "other": 1,
        "spatial_omission": 4,
    }


def test_audit_packet_is_source_disjoint_stratified_and_source_verified(
    tmp_path: Path,
) -> None:
    from scripts.build_gee_complete_workflow_expansion_batch import (
        FrozenAuditSamplingProfile,
        RISK_STRATA,
        build_stratified_audit_packet,
    )

    source_root = tmp_path / "source"
    proposals = [
        _source_proposal(
            source_root,
            "external",
            risk_flags=[
                "dynamic_transformation_arguments",
                "external_spatial_identifier",
            ],
        ),
        _source_proposal(
            source_root,
            "long",
            risk_flags=[
                "dynamic_transformation_arguments",
                "external_spatial_identifier",
                "repeated_operator",
            ],
        ),
        _source_proposal(
            source_root,
            "multi",
            risk_flags=["multiple_dataset_facts", "private_asset_redacted"],
        ),
        _source_proposal(
            source_root,
            "temporal",
            risk_flags=["no_source_backed_temporal_operation"],
        ),
        _source_proposal(
            source_root,
            "other",
            risk_flags=["external_spatial_identifier"],
        ),
        _source_proposal(
            source_root,
            "spatial",
            risk_flags=["no_source_backed_spatial_input", "repeated_operator"],
        ),
    ]
    # Same source, lower-risk workflow: the spatial representative must win.
    duplicate_source = dict(proposals[-1])
    duplicate_source["workflow_id"] = "output-workflow-2"
    duplicate_source["workflow_key"] = [
        duplicate_source["source_sha256"],
        duplicate_source["workflow_id"],
    ]
    duplicate_source["proposal_id"] = "proposal-spatial-output-workflow-2"
    duplicate_source["risk_flags"] = [
        "dynamic_transformation_arguments",
        "external_spatial_identifier",
    ]
    proposals.append(duplicate_source)

    reviewed_path = tmp_path / "reviewed.jsonl"
    _, reviewed = _candidate(999)
    _write_jsonl(reviewed_path, [reviewed])
    profile = FrozenAuditSamplingProfile(
        name="synthetic_audit",
        sample_size=6,
        expected_source_support={stratum: 1 for stratum in RISK_STRATA},
        quotas={stratum: 1 for stratum in RISK_STRATA},
    )

    first = build_stratified_audit_packet(
        proposal_rows=proposals,
        reviewed_packet_path=reviewed_path,
        source_root=source_root,
        profile=profile,
    )
    second = build_stratified_audit_packet(
        proposal_rows=list(reversed(proposals)),
        reviewed_packet_path=reviewed_path,
        source_root=source_root,
        profile=profile,
    )

    assert first.audit_rows == second.audit_rows
    assert len(first.source_representatives) == 6
    assert len(first.audit_rows) == 6
    assert len({row["source_sha256"] for row in first.audit_rows}) == 6
    assert {row["risk_stratum"] for row in first.audit_rows} == set(RISK_STRATA)
    assert first.summary["source_support"] == {stratum: 1 for stratum in RISK_STRATA}
    assert first.summary["audit_quotas"] == {stratum: 1 for stratum in RISK_STRATA}
    assert first.summary["training_rows_emitted"] == 0
    assert all(row["source_sha256_verified"] for row in first.audit_rows)
    assert all(len(row["audit_row_authority_sha256"]) == 64 for row in first.audit_rows)
    assert all("Export.image.toDrive" in row["source_snippet"] for row in first.audit_rows)
    assert all(
        row[field] == ""
        for row in first.audit_rows
        for field in (
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
    )

    (source_root / proposals[0]["source_path"]).write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source SHA256"):
        build_stratified_audit_packet(
            proposal_rows=proposals,
            reviewed_packet_path=reviewed_path,
            source_root=source_root,
            profile=profile,
        )


def test_audit_packet_uses_independent_reviewed_authority_without_mutating_proposals(
    tmp_path: Path,
) -> None:
    from scripts.build_gee_complete_workflow_expansion_batch import (
        FrozenAuditSamplingProfile,
        RISK_STRATA,
        build_stratified_audit_packet,
    )

    source_root = tmp_path / "source"
    proposals = [
        _source_proposal(
            source_root,
            name,
            risk_flags=["external_spatial_identifier"],
        )
        for name in ("excluded", "eligible")
    ]
    proposals_before = json.loads(json.dumps(proposals))
    reviewed_path = tmp_path / "census_reviewed.jsonl"
    _, unrelated_reviewed = _candidate(999)
    _write_jsonl(reviewed_path, [unrelated_reviewed])
    audit_reviewed_path = tmp_path / "audit_reviewed.jsonl"
    _write_jsonl(audit_reviewed_path, [proposals[0]])
    support = {stratum: int(stratum == "other") for stratum in RISK_STRATA}

    result = build_stratified_audit_packet(
        proposal_rows=proposals,
        reviewed_packet_path=reviewed_path,
        audit_reviewed_packet_path=audit_reviewed_path,
        source_root=source_root,
        profile=FrozenAuditSamplingProfile(
            name="independent-reviewed-authority",
            sample_size=1,
            expected_source_support=support,
            quotas=support,
        ),
    )

    assert proposals == proposals_before
    assert result.summary["proposal_rows"] == 2
    assert result.summary["eligible_sources"] == 1
    assert result.summary["audit_reviewed_excluded_sources"] == 1
    assert result.summary["audit_reviewed_packet_sha256"] == hashlib.sha256(
        audit_reviewed_path.read_bytes()
    ).hexdigest()
    assert [row["source_sha256"] for row in result.source_representatives] == [
        proposals[1]["source_sha256"]
    ]


def test_audit_packet_defaults_reviewed_authority_to_census_packet(
    tmp_path: Path,
) -> None:
    from scripts.build_gee_complete_workflow_expansion_batch import (
        FrozenAuditSamplingProfile,
        RISK_STRATA,
        build_stratified_audit_packet,
    )

    source_root = tmp_path / "source"
    proposals = [
        _source_proposal(
            source_root,
            name,
            risk_flags=["external_spatial_identifier"],
        )
        for name in ("reviewed", "eligible")
    ]
    reviewed_path = tmp_path / "reviewed.jsonl"
    _write_jsonl(reviewed_path, [proposals[0]])
    support = {stratum: int(stratum == "other") for stratum in RISK_STRATA}

    result = build_stratified_audit_packet(
        proposal_rows=proposals,
        reviewed_packet_path=reviewed_path,
        source_root=source_root,
        profile=FrozenAuditSamplingProfile(
            name="fallback-reviewed-authority",
            sample_size=1,
            expected_source_support=support,
            quotas=support,
        ),
    )

    assert result.summary["audit_reviewed_excluded_sources"] == 1
    assert result.summary["audit_reviewed_packet_sha256"] == hashlib.sha256(
        reviewed_path.read_bytes()
    ).hexdigest()
    assert result.audit_rows[0]["source_sha256"] == proposals[1]["source_sha256"]


def test_expansion_outputs_are_atomic_complete_and_byte_reproducible(
    tmp_path: Path,
) -> None:
    from scripts.build_gee_complete_workflow_expansion_batch import (
        ExpansionCensusResult,
        FrozenAuditSamplingProfile,
        RISK_STRATA,
        build_stratified_audit_packet,
        write_expansion_outputs,
    )

    source_root = tmp_path / "source"
    proposal = _source_proposal(
        source_root,
        "single",
        risk_flags=["external_spatial_identifier"],
    )
    reviewed_path = tmp_path / "reviewed.jsonl"
    _, reviewed = _candidate(999)
    _write_jsonl(reviewed_path, [reviewed])
    support = {stratum: int(stratum == "other") for stratum in RISK_STRATA}
    audit = build_stratified_audit_packet(
        proposal_rows=[proposal],
        reviewed_packet_path=reviewed_path,
        source_root=source_root,
        profile=FrozenAuditSamplingProfile(
            name="single-source-audit",
            sample_size=1,
            expected_source_support=support,
            quotas=support,
        ),
    )
    terminal = {
        "schema": "gis_recommend.gee_workflow_expansion_terminal.v1",
        "source_sha256": proposal["source_sha256"],
        "source_path": proposal["source_path"],
        "workflow_id": proposal["workflow_id"],
        "workflow_key": proposal["workflow_key"],
        "terminal_status": "proposal_eligible",
        "reason": "test fixture",
        "training_admission": "not_granted_pending_sampling_audit",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    census = ExpansionCensusResult(
        remaining_ledger=[terminal],
        proposal_rows=[proposal],
        source_overlap_sidecar=[],
        fail_closed_sidecar=[],
        duplicate_sidecar=[],
        length_sidecar=[],
        summary={
            "schema": "gis_recommend.gee_workflow_expansion_census_summary.v1",
            "authority_profile": "synthetic",
            "authority_sha256": {"facts": "a" * 64},
            "counts": {
                "canonical_candidates": 2,
                "reviewed_identities": 1,
                "remaining": 1,
                "excluded_reviewed_source_overlap": 0,
                "proposal_eligible": 1,
                "excluded_existing_or_batch_duplicate": 0,
                "deferred_length": 0,
                "fail_closed_semantic_gate": 0,
            },
            "proposal_status": "pending_sampling_audit",
            "training_admission": "not_granted_pending_sampling_audit",
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
        },
    )

    first = tmp_path / "run-a"
    second = tmp_path / "run-b"
    write_expansion_outputs(census_result=census, audit_result=audit, output_dir=first)
    write_expansion_outputs(census_result=census, audit_result=audit, output_dir=second)

    expected_names = {
        "remaining_ledger.jsonl",
        "proposal_candidates.jsonl",
        "source_overlap_sidecar.jsonl",
        "semantic_fail_closed_sidecar.jsonl",
        "duplicate_sidecar.jsonl",
        "length_sidecar.jsonl",
        "audit_sample_1.jsonl",
        "audit_sample_1.csv",
        "audit_source_manifest.jsonl",
        "summary.json",
        "report.md",
        "hash_ledger.json",
    }
    assert {path.name for path in first.iterdir()} == expected_names
    assert {path.name for path in second.iterdir()} == expected_names
    assert all(
        (first / name).read_bytes() == (second / name).read_bytes()
        for name in expected_names
    )
    summary = json.loads((first / "summary.json").read_text(encoding="utf-8"))
    hash_ledger = json.loads(
        (first / "hash_ledger.json").read_text(encoding="utf-8")
    )
    assert summary["census"]["counts"]["proposal_eligible"] == 1
    assert summary["audit"]["audit_sample_rows"] == 1
    assert hash_ledger["audit_reviewed_packet_sha256"] == summary["audit"][
        "audit_reviewed_packet_sha256"
    ]
    assert hash_ledger["audit_reviewed_excluded_sources"] == 0
    assert summary["training_rows_emitted"] == 0
    with pytest.raises(FileExistsError):
        write_expansion_outputs(census_result=census, audit_result=audit, output_dir=first)


@pytest.mark.parametrize("sample_rows", [30, 50])
def test_expansion_outputs_name_audit_files_from_sample_row_count(
    tmp_path: Path,
    sample_rows: int,
) -> None:
    from scripts.build_gee_complete_workflow_expansion_batch import (
        ExpansionCensusResult,
        StratifiedAuditPacketResult,
        write_expansion_outputs,
    )

    census = ExpansionCensusResult(
        remaining_ledger=[],
        proposal_rows=[],
        source_overlap_sidecar=[],
        fail_closed_sidecar=[],
        duplicate_sidecar=[],
        length_sidecar=[],
        summary={
            "authority_profile": "synthetic",
            "authority_sha256": {},
            "counts": {
                "remaining": 0,
                "excluded_reviewed_source_overlap": 0,
                "proposal_eligible": 0,
            },
        },
    )
    audit = StratifiedAuditPacketResult(
        source_representatives=[],
        audit_rows=[{"audit_id": index} for index in range(sample_rows)],
        source_manifest=[{"audit_id": index} for index in range(sample_rows)],
        summary={
            "sampling_profile": "batch6",
            "eligible_sources": sample_rows,
            "audit_sample_rows": sample_rows,
        },
    )
    output_dir = tmp_path / f"batch-{sample_rows}"

    write_expansion_outputs(
        census_result=census,
        audit_result=audit,
        output_dir=output_dir,
    )

    assert (output_dir / f"audit_sample_{sample_rows}.jsonl").is_file()
    assert (output_dir / f"audit_sample_{sample_rows}.csv").is_file()
    if sample_rows == 50:
        assert not (output_dir / "audit_sample_30.jsonl").exists()
        assert not (output_dir / "audit_sample_30.csv").exists()


def test_expansion_outputs_reject_audit_row_count_drift(tmp_path: Path) -> None:
    from scripts.build_gee_complete_workflow_expansion_batch import (
        ExpansionCensusResult,
        StratifiedAuditPacketResult,
        write_expansion_outputs,
    )

    census = ExpansionCensusResult(
        remaining_ledger=[],
        proposal_rows=[],
        source_overlap_sidecar=[],
        fail_closed_sidecar=[],
        duplicate_sidecar=[],
        length_sidecar=[],
        summary={"authority_profile": "synthetic", "authority_sha256": {}, "counts": {}},
    )
    audit = StratifiedAuditPacketResult(
        source_representatives=[],
        audit_rows=[{"audit_id": index} for index in range(49)],
        source_manifest=[{"audit_id": index} for index in range(50)],
        summary={
            "sampling_profile": "batch6",
            "eligible_sources": 50,
            "audit_sample_rows": 50,
        },
    )
    output_dir = tmp_path / "invalid-counts"

    with pytest.raises(ValueError, match="audit sample row count drift"):
        write_expansion_outputs(
            census_result=census,
            audit_result=audit,
            output_dir=output_dir,
        )

    assert not output_dir.exists()


def _selection_proposal(
    tmp_path: Path,
    number: int,
    *,
    risk_flags: list[str],
    workflow_id: str = "output-workflow-1",
) -> dict:
    proposal = _source_proposal(
        tmp_path / "selection-sources",
        f"selection-{number}-{workflow_id}",
        risk_flags=risk_flags,
        workflow_id=workflow_id,
    )
    source_sha = f"{number:064x}"
    proposal.update(
        {
            "proposal_id": f"selection-{number}-{workflow_id}",
            "source_sha256": source_sha,
            "source_path": f"data10000/selection_{number}.txt",
            "workflow_key": [source_sha, workflow_id],
        }
    )
    return proposal


def _selection_paths(tmp_path: Path) -> tuple[dict[str, Path], list[dict]]:
    candidates = [
        _selection_proposal(
            tmp_path,
            6,
            risk_flags=["no_source_backed_temporal_operation"],
        ),
        _selection_proposal(
            tmp_path,
            3,
            risk_flags=[
                "dynamic_transformation_arguments",
                "external_spatial_identifier",
            ],
        ),
        _selection_proposal(
            tmp_path,
            1,
            risk_flags=["external_spatial_identifier"],
        ),
        _selection_proposal(
            tmp_path,
            5,
            risk_flags=["multiple_dataset_facts"],
        ),
        _selection_proposal(
            tmp_path,
            3,
            workflow_id="output-workflow-2",
            risk_flags=["no_source_backed_spatial_input"],
        ),
        _selection_proposal(
            tmp_path,
            2,
            risk_flags=["external_spatial_identifier"],
        ),
        _selection_proposal(
            tmp_path,
            4,
            risk_flags=["external_spatial_identifier"],
        ),
    ]
    _, reviewed = _candidate(1)
    prior = _selection_proposal(
        tmp_path,
        2,
        risk_flags=["external_spatial_identifier"],
    )
    paths = {
        "candidate_proposals_path": tmp_path / "larger_candidates.jsonl",
        "reviewed_packet_path": tmp_path / "reviewed_selection.jsonl",
        "prior_proposals_path": tmp_path / "prior_proposals.jsonl",
        "id_mappings_path": tmp_path / "selection_mappings.json",
    }
    _write_jsonl(paths["candidate_proposals_path"], candidates)
    _write_jsonl(paths["reviewed_packet_path"], [reviewed])
    _write_jsonl(paths["prior_proposals_path"], [prior])
    _write_json(
        paths["id_mappings_path"],
        {"l3": {f"L3_TEST_{index:02d}": index for index in range(94)}},
    )
    return paths, candidates


def test_larger_source_disjoint_selection_is_stable_hash_bound_and_proposal_only(
    tmp_path: Path,
) -> None:
    from scripts.build_gee_complete_workflow_expansion_batch import (
        build_source_disjoint_replay_selection,
        write_source_disjoint_selection,
    )

    paths, candidates = _selection_paths(tmp_path)
    first = build_source_disjoint_replay_selection(
        **paths,
        target_source_count=2,
        audit_sample_size=2,
    )
    first_candidate_sha = first.hash_ledger["authority_sha256"][
        "candidate_proposals"
    ]
    _write_jsonl(paths["candidate_proposals_path"], list(reversed(candidates)))
    second = build_source_disjoint_replay_selection(
        **paths,
        target_source_count=2,
        audit_sample_size=2,
    )

    assert first.selection_ledger == second.selection_ledger
    assert first.selection_manifest == second.selection_manifest
    assert first.audit_packet_input == second.audit_packet_input
    assert first_candidate_sha != second.hash_ledger["authority_sha256"][
        "candidate_proposals"
    ]
    assert first.summary["counts"] == {
        "candidate_rows": 7,
        "candidate_sources": 6,
        "reviewed_sources": 1,
        "prior_proposal_rows": 1,
        "prior_proposal_sources": 1,
        "excluded_candidate_sources": 2,
        "eligible_sources": 4,
        "selected_sources": 2,
        "selected_rows": 3,
        "not_selected_target_limit_sources": 2,
        "audit_packet_input_rows": 2,
    }
    assert {
        row["source_sha256"] for row in first.selection_manifest
    } == {f"{3:064x}", f"{4:064x}"}
    assert len(first.selection_manifest) == 3
    assert {
        (row["source_sha256"], row["selection_status"])
        for row in first.selection_ledger
        if row["source_sha256"] in {f"{1:064x}", f"{2:064x}"}
    } == {
        (f"{1:064x}", "excluded_reviewed_source"),
        (f"{2:064x}", "excluded_prior_proposal_source"),
    }
    assert [
        row["risk_stratum"] for row in first.audit_packet_input
    ] == ["other", "spatial_omission"]
    assert all(
        row["training_admission"] == "not_granted_pending_sampling_audit"
        and row["validation_eligible"] is False
        and row["test_eligible"] is False
        and row["production_merge"] == "not_granted"
        for rows in (
            first.selection_ledger,
            first.selection_manifest,
            first.audit_packet_input,
        )
        for row in rows
    )
    assert first.summary["training_rows_emitted"] == 0
    assert set(first.hash_ledger["authority_sha256"]) == {
        "candidate_proposals",
        "reviewed_packet",
        "prior_proposals",
        "mapping",
    }

    output_dir = tmp_path / "selection-output"
    written_ledger = write_source_disjoint_selection(first, output_dir=output_dir)
    assert written_ledger == first.hash_ledger
    assert {path.name for path in output_dir.iterdir()} == {
        "selection_ledger.jsonl",
        "selection_manifest.jsonl",
        "excluded_source_manifest.jsonl",
        "audit_packet_input.jsonl",
        "summary.json",
        "hash_ledger.json",
    }
    assert not any("train" in path.name for path in output_dir.iterdir())
    with pytest.raises(FileExistsError):
        write_source_disjoint_selection(first, output_dir=output_dir)


def test_larger_selection_rejects_permission_and_mapping_drift(tmp_path: Path) -> None:
    from scripts.build_gee_complete_workflow_expansion_batch import (
        build_source_disjoint_replay_selection,
    )

    paths, candidates = _selection_paths(tmp_path)
    candidates[0]["training_admission"] = "granted_train_only"
    _write_jsonl(paths["candidate_proposals_path"], candidates)
    with pytest.raises(ValueError, match="training admission drift"):
        build_source_disjoint_replay_selection(
            **paths,
            target_source_count=2,
            audit_sample_size=1,
        )

    candidates[0]["training_admission"] = "not_granted_pending_sampling_audit"
    candidates[0]["l3_sequence"] = ["L3_UNMAPPED"]
    _write_jsonl(paths["candidate_proposals_path"], candidates)
    with pytest.raises(ValueError, match="unmapped L3"):
        build_source_disjoint_replay_selection(
            **paths,
            target_source_count=2,
            audit_sample_size=1,
        )
