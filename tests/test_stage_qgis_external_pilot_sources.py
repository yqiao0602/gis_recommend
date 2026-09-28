from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from gis_recommend.data.qgis_source_authority import source_authority
from scripts.stage_qgis_external_pilot_sources import stage_sources


def _target(path: Path, *, index: int, declared_path: Path | None = None) -> dict:
    source_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    authority = source_authority(path, source_sha256=source_sha256)
    return {
        "schema": "gis_recommend.qgis_external_pilot_target.v1",
        "target_index": index,
        "target_id": f"target-{index}",
        "record_id": source_sha256[:24],
        "corpus_kind": "processing" if index == 1 else "api",
        "source_path": str(declared_path or path),
        "source_sha256": source_sha256,
        "normalized_source_body_sha256": authority[
            "normalized_source_body_sha256"
        ],
        "source_authority_key": authority["source_authority_key"],
        "training_admission": "not_granted_external_analysis_pilot_only",
        "training_row_emitted": False,
    }


def test_staging_verifies_declared_and_prefix_alias_sources(tmp_path: Path) -> None:
    declared = tmp_path / "declared.py"
    declared.write_text("value = 1\n", encoding="utf-8")
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    aliased = new_root / "aliased.py"
    aliased.parent.mkdir()
    aliased.write_text(
        "# Source repo: owner/repo\n"
        "# Source path: aliased.py\n"
        "# Source kind: python_file\n"
        "# Code block id: whole_file\n"
        "value = 2\n",
        encoding="utf-8",
    )
    rows = [
        _target(declared, index=1),
        _target(aliased, index=2, declared_path=old_root / "aliased.py"),
    ]

    staged, summary = stage_sources(
        rows,
        stage_root=tmp_path / "stage",
        expected_count=2,
        prefix_aliases=((old_root, new_root),),
    )

    assert summary["source_count"] == 2
    assert summary["source_sha_verified"] == 2
    assert summary["unique_normalized_bodies"] == 2
    assert summary["prefix_alias_count"] == 1
    assert [row["source_path_resolution"] for row in staged] == [
        "declared_path",
        "fixed_prefix_alias",
    ]
    assert all(Path(row["staged_source_path"]).is_file() for row in staged)
    assert all(row["authority_verdict"] == "unresolved" for row in staged)
    assert all(row["training_row_emitted"] is False for row in staged)


def test_staging_fails_closed_on_normalized_authority_mismatch(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.py"
    source.write_text("value = 1\n", encoding="utf-8")
    row = _target(source, index=1)
    row["normalized_source_body_sha256"] = "f" * 64

    with pytest.raises(ValueError, match="normalized authority mismatch"):
        stage_sources(
            [row],
            stage_root=tmp_path / "stage",
            expected_count=1,
            prefix_aliases=(),
        )
