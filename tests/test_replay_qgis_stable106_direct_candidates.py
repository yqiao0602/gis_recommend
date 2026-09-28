from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "replay_qgis_stable106_direct_candidates.py"
)
SPEC = importlib.util.spec_from_file_location(
    "replay_qgis_stable106_direct_candidates", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_replays_only_canonical_candidates_and_verifies_source(tmp_path: Path) -> None:
    source = tmp_path / "workflow.py"
    source.write_text(
        "import processing\n"
        "result = processing.run('native:creategrid', {'OUTPUT': 'TEMPORARY_OUTPUT'})\n",
        encoding="utf-8",
    )
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    candidates = [
        {
            "record_id": "keep",
            "source_path": str(source),
            "source_sha256": sha,
            "operator_ids": ["native:creategrid"],
            "call_sites": [
                {
                    "operator_id": "native:creategrid",
                    "line_start": 2,
                    "line_end": 2,
                }
            ],
        },
        {"record_id": "drop", "source_path": "missing.py", "source_sha256": "x"},
    ]
    ledger = [
        {"record_id": "keep", "dedup_decision": "canonical_keep_candidate"},
        {"record_id": "drop", "dedup_decision": "exact_training_pair_suppressed"},
    ]

    rows, summary = MODULE.replay_candidates(candidates, ledger)

    assert len(rows) == 1
    assert rows[0]["source_verification"] == "verified_sha256"
    assert rows[0]["call_span_verification"] == "verified_processing_calls"
    assert rows[0]["source_authority_key"].startswith(
        "normalized_source_body_sha256:"
    )
    assert summary["verified_rows"] == 1
    assert summary["training_rows_emitted"] == 0


def test_sha_mismatch_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "workflow.py"
    source.write_text("processing.run('native:creategrid', {})\n", encoding="utf-8")

    try:
        MODULE.replay_candidates(
            [
                {
                    "record_id": "bad",
                    "source_path": str(source),
                    "source_sha256": "wrong",
                    "operator_ids": ["native:creategrid"],
                    "call_sites": [
                        {
                            "operator_id": "native:creategrid",
                            "line_start": 1,
                            "line_end": 1,
                        }
                    ],
                }
            ],
            [{"record_id": "bad", "dedup_decision": "canonical_keep_candidate"}],
        )
    except ValueError as exc:
        assert "SHA mismatch" in str(exc)
    else:
        raise AssertionError("SHA mismatch must fail closed")


def test_replays_missing_source_from_verified_normalized_body_authority() -> None:
    candidates = [
        {
            "record_id": "keep",
            "source_path": "/home/yll/workflow.py",
            "source_sha256": "source-sha",
            "operator_ids": ["native:buffer", "native:clip"],
            "mapped_l3_chain": ["L3_BUFFER", "L3_CLIP"],
            "call_sites": [
                {"operator_id": "native:buffer", "line_start": 10, "line_end": 10},
                {"operator_id": "native:clip", "line_start": 11, "line_end": 11},
            ],
            "source_snippet": (
                "10 | processing.run('native:buffer', {})\n"
                "11 | processing.run('native:clip', {})"
            ),
            "source_snippet_contains_all_ops": True,
        }
    ]
    ledger = [{"record_id": "keep", "dedup_decision": "canonical_keep_candidate"}]
    authority = [
        {
            "record_id": "keep",
            "source_path": "/home/yll/workflow.py",
            "source_sha256": "source-sha",
            "operator_chain": ["native:buffer", "native:clip"],
            "normalized_source_body_sha256": "body-sha",
            "source_authority_key": "normalized_source_body_sha256:body-sha",
        }
    ]

    rows, summary = MODULE.replay_candidates(
        candidates,
        ledger,
        source_authority_rows=authority,
        replay_profile="lineintersections_correction_v1",
    )

    assert rows[0]["source_verification"] == (
        "carried_forward_verified_normalized_source_body"
    )
    assert rows[0]["call_span_verification"] == (
        "carried_forward_cached_processing_calls"
    )
    assert rows[0]["normalized_source_body_sha256"] == "body-sha"
    assert rows[0]["schema"] == "gis_recommend.qgis_direct_source_replay.v1"
    assert rows[0]["replay_profile"] == "lineintersections_correction_v1"
    assert summary["verification_mode_counts"] == {
        "carried_forward_verified_normalized_source_body": 1
    }
    assert summary["next_gate"] == "explicit train-only export admission"


def test_source_authority_carry_forward_rejects_identity_mismatch() -> None:
    candidate = {
        "record_id": "bad",
        "source_path": "/home/yll/workflow.py",
        "source_sha256": "candidate-sha",
        "operator_ids": ["native:buffer"],
        "call_sites": [
            {"operator_id": "native:buffer", "line_start": 1, "line_end": 1}
        ],
        "source_snippet": "1 | processing.run('native:buffer', {})",
        "source_snippet_contains_all_ops": True,
    }
    authority = {
        **candidate,
        "source_sha256": "different-sha",
        "operator_chain": ["native:buffer"],
        "normalized_source_body_sha256": "body-sha",
        "source_authority_key": "normalized_source_body_sha256:body-sha",
    }

    try:
        MODULE.replay_candidates(
            [candidate],
            [{"record_id": "bad", "dedup_decision": "canonical_keep_candidate"}],
            source_authority_rows=[authority],
        )
    except ValueError as exc:
        assert "authority identity mismatch" in str(exc)
    else:
        raise AssertionError("authority identity mismatch must fail closed")
