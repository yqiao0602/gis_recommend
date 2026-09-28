from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "verify_qgis_training_manifest_sources.py"
)


def _load_module():
    assert SCRIPT.exists(), "source manifest verifier is not implemented"
    spec = importlib.util.spec_from_file_location(
        "verify_qgis_training_manifest_sources", SCRIPT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_verifies_unique_sources_and_preserves_row_coverage() -> None:
    module = _load_module()
    payloads = {"/source/a.py": b"a", "/source/b.py": b"b"}
    rows = [
        {
            "sample_id": "one",
            "source_path": "/source/a.py",
            "source_sha256": hashlib.sha256(b"a").hexdigest(),
        },
        {
            "sample_id": "two",
            "source_path": "/source/a.py",
            "source_sha256": hashlib.sha256(b"a").hexdigest(),
        },
        {
            "sample_id": "three",
            "source_path": "/source/b.py",
            "source_sha256": hashlib.sha256(b"b").hexdigest(),
        },
    ]

    ledger, summary = module.verify_manifest_sources(
        rows, lambda paths: {path: hashlib.sha256(payloads[path]).hexdigest() for path in paths}
    )

    assert len(ledger) == 2
    assert summary["manifest_rows"] == 3
    assert summary["unique_sources"] == 2
    assert summary["verified_sources"] == 2
    assert summary["covered_manifest_rows"] == 3
    assert summary["source_failures"] == 0


def test_fails_closed_on_conflicting_expected_hashes() -> None:
    module = _load_module()
    rows = [
        {"sample_id": "one", "source_path": "/source/a.py", "source_sha256": "a" * 64},
        {"sample_id": "two", "source_path": "/source/a.py", "source_sha256": "b" * 64},
    ]

    with pytest.raises(ValueError, match="conflicting source hashes"):
        module.verify_manifest_sources(rows, lambda paths: {})


def test_remote_hash_parser_uses_request_order_without_returning_paths() -> None:
    module = _load_module()
    digest = "a" * 64
    output = f"{digest}\n\n".encode("ascii")

    assert module._parse_remote_digest_lines(
        output, ["/home/yll/中文/path.py", "/missing.py"]
    ) == {
        "/home/yll/中文/path.py": digest,
        "/missing.py": "",
    }


def test_binds_successful_remote_replay_to_every_training_row() -> None:
    module = _load_module()
    rows = [
        {
            "sample_id": "one",
            "source_path": "/source/a.py",
            "source_sha256": "a" * 64,
            "source_verification": "source_reviewed_evidence",
        }
    ]
    ledger = [
        {
            "source_path": "/source/a.py",
            "source_verification": "verified_sha256",
        }
    ]

    verified = module.bind_verified_sources(rows, ledger)

    assert verified[0]["source_verification"] == "verified_sha256"
    assert verified[0]["prior_source_verification"] == "source_reviewed_evidence"
    assert verified[0]["source_authority_key"] == f"source_sha256:{'a' * 64}"

    ledger[0]["source_verification"] = "source_sha256_mismatch"
    with pytest.raises(ValueError, match="not verified"):
        module.bind_verified_sources(rows, ledger)
