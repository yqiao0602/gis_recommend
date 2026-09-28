from pathlib import Path

from gis_recommend.data.qgis_source_authority import (
    normalized_source_body,
    source_authority,
)


def test_source_authority_collapses_harvest_headers(tmp_path: Path) -> None:
    body = 'processing.run("native:buffer", {})\n'
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    first.write_text(
        "# Source repo: owner/repo\n"
        "# Source path: workflow.py\n"
        "# Query used: first\n"
        "# Harvested at: first-time\n\n"
        + body,
        encoding="utf-8",
    )
    second.write_text(
        "# Source repo: owner/repo\n"
        "# Source path: workflow.py\n"
        "# Query used: second\n"
        "# Harvested at: second-time\n\n"
        + body,
        encoding="utf-8",
    )

    first_authority = source_authority(first, source_sha256="file-a")
    second_authority = source_authority(second, source_sha256="file-b")

    assert first_authority["source_authority_key"] == second_authority[
        "source_authority_key"
    ]
    assert first_authority["source_authority_basis"] == (
        "normalized_source_body_sha256"
    )
    assert first_authority["upstream_source_repo"] == "owner/repo"
    assert first_authority["upstream_source_path"] == "workflow.py"


def test_source_authority_preserves_frozen_extended_header_semantics(
    tmp_path: Path,
) -> None:
    body = '# ordinary source comment\nprocessing.run("native:centroids", {})\n'
    harvested = tmp_path / "harvested.py"
    harvested.write_text(
        "# Source repo: owner/repo\n"
        "# Source path: workflow.py\n"
        "# Source kind: python_file\n"
        "# Code block id: whole_file\n"
        "# Harvested at: 2026-06-05T10:30:33\n\n"
        + body,
        encoding="utf-8",
    )

    normalized = normalized_source_body(harvested)
    authority = source_authority(harvested, source_sha256="harvested-file")

    assert normalized == (
        "# Source kind: python_file\n"
        "# Code block id: whole_file\n"
        "# Harvested at: 2026-06-05T10:30:33\n\n"
        + body.strip()
    )
    assert authority["normalized_source_body_sha256"] == __import__(
        "hashlib"
    ).sha256(normalized.encode("utf-8")).hexdigest()


def test_source_authority_falls_back_to_declared_hash(tmp_path: Path) -> None:
    authority = source_authority(
        tmp_path / "missing.py", source_sha256="declared-source-sha"
    )

    assert authority["source_authority_key"] == "source_sha256:declared-source-sha"
    assert authority["source_authority_basis"] == "source_sha256_fallback"


def test_public_normalized_source_body_preserves_authority_hash(tmp_path: Path) -> None:
    source = tmp_path / "workflow.py"
    source.write_text(
        "# Source repo: owner/repo\n"
        "# Source path: workflow.py\n"
        "# Harvested at: first-time\n\n"
        "value = 1  \n"
        "print(value)\n\n",
        encoding="utf-8",
    )

    normalized = normalized_source_body(source)
    authority = source_authority(source, source_sha256="unused")

    assert normalized == "value = 1\nprint(value)"
    assert authority["normalized_source_body_sha256"] == __import__(
        "hashlib"
    ).sha256(normalized.encode("utf-8")).hexdigest()
