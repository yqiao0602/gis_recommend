from __future__ import annotations

import gzip
import hashlib
from pathlib import Path

import pytest

from scripts.package_qgis_benchmark_release_artifact import package_artifact


def _manifest(raw: bytes) -> dict[str, object]:
    return {
        "freeze_status": "local_authority_unpublished",
        "artifact": {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "byte_count": len(raw),
            "line_ending": "LF",
            "terminal_newline": True,
        },
        "compression": {
            "algorithm": "gzip",
            "level": 9,
            "mtime": 0,
            "filename_header": "",
            "os_header": 255,
            "compressed_sha256": None,
            "compressed_byte_count": None,
            "decoded_sha256": hashlib.sha256(raw).hexdigest(),
        },
    }


def test_package_artifact_is_deterministic_and_updates_manifest(tmp_path: Path) -> None:
    raw = b'{"row":1}\n{"row":2}\n'
    source = tmp_path / "ledger.jsonl"
    source.write_bytes(raw)
    first = tmp_path / "first.jsonl.gz"
    second = tmp_path / "second.jsonl.gz"

    first_manifest = package_artifact(source, first, _manifest(raw))
    second_manifest = package_artifact(source, second, _manifest(raw))

    assert first.read_bytes() == second.read_bytes()
    assert first.read_bytes()[:10] == b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x02\xff"
    assert gzip.decompress(first.read_bytes()) == raw
    assert first_manifest == second_manifest
    assert first_manifest["freeze_status"] == "local_packaged_unpublished"
    assert first_manifest["compression"]["compressed_sha256"] == hashlib.sha256(
        first.read_bytes()
    ).hexdigest()
    assert first_manifest["compression"]["compressed_byte_count"] == len(
        first.read_bytes()
    )


def test_package_artifact_rejects_manifest_raw_hash_mismatch(tmp_path: Path) -> None:
    raw = b'{"row":1}\n'
    source = tmp_path / "ledger.jsonl"
    source.write_bytes(raw)
    manifest = _manifest(raw)
    manifest["artifact"]["sha256"] = "0" * 64

    with pytest.raises(ValueError, match="raw_sha256_mismatch"):
        package_artifact(source, tmp_path / "ledger.jsonl.gz", manifest)


def test_package_artifact_rejects_noncanonical_line_endings(tmp_path: Path) -> None:
    raw = b'{"row":1}\r\n'
    source = tmp_path / "ledger.jsonl"
    source.write_bytes(raw)

    with pytest.raises(ValueError, match="raw_line_endings_not_lf"):
        package_artifact(source, tmp_path / "ledger.jsonl.gz", _manifest(raw))
