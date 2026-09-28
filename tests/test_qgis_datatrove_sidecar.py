from __future__ import annotations

import json
import runpy
from pathlib import Path

import pytest

from gis_recommend.data.qgis_datatrove_sidecar import (
    MinHashSidecarConfig,
    build_datatrove_input,
    normalize_datatrove_report,
    write_normalized_report,
)
from gis_recommend.data.qgis_source_authority import source_authority

FIXTURE = Path("tests/fixtures/qgis_external_pilot/dedup_documents.jsonl")
RUNNER = Path("scripts/qgis_external_pilot/run_datatrove_sidecar.py")


def _materialize(tmp_path: Path) -> list[dict[str, str]]:
    rows = [
        json.loads(line)
        for line in FIXTURE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    manifest: list[dict[str, str]] = []
    for row in rows:
        path = tmp_path / f"{row['record_id']}.py"
        path.write_text(row["source_text"], encoding="utf-8")
        manifest.append(
            {
                "record_id": row["record_id"],
                "source_path": str(path),
                "source_sha256": f"file-{row['record_id']}",
            }
        )
    return manifest


def test_datatrove_input_reuses_normalized_body_authority(tmp_path: Path) -> None:
    manifest = _materialize(tmp_path)

    documents = build_datatrove_input(manifest)

    assert [row["record_id"] for row in documents] == sorted(
        row["record_id"] for row in manifest
    )
    for row in documents:
        authority = source_authority(
            Path(row["source_path"]), source_sha256=row["source_sha256"]
        )
        assert row["normalized_source_body_sha256"] == authority[
            "normalized_source_body_sha256"
        ]
        assert row["text"]


def test_exact_clusters_must_equal_authority_groups(tmp_path: Path) -> None:
    documents = build_datatrove_input(_materialize(tmp_path))
    datatrove_exact_clusters = [["exact-b", "exact-a"]]
    config = MinHashSidecarConfig()

    report = normalize_datatrove_report(
        documents,
        datatrove_version="0.9.0",
        datatrove_exact_clusters=datatrove_exact_clusters,
        datatrove_minhash_clusters=[
            ["near-b", "near-a"],
            ["exact-a", "exact-b"],
        ],
        config=config,
    )

    assert report["exact_reconciliation"] == {
        "authority_clusters": [["exact-a", "exact-b"]],
        "datatrove_clusters": [["exact-a", "exact-b"]],
        "matched": True,
    }
    assert ["near-a", "near-b"] in report["minhash_clusters"]
    assert report["minhash_report_only"] is True
    assert report["authority_mutated"] is False
    assert report["training_rows_emitted"] == 0


def test_exact_cluster_mismatch_fails_closed(tmp_path: Path) -> None:
    documents = build_datatrove_input(_materialize(tmp_path))

    with pytest.raises(ValueError, match="exact clusters do not reconcile"):
        normalize_datatrove_report(
            documents,
            datatrove_version="0.9.0",
            datatrove_exact_clusters=[],
            datatrove_minhash_clusters=[],
            config=MinHashSidecarConfig(),
        )


def test_summary_freezes_minhash_and_hash_configuration(tmp_path: Path) -> None:
    documents = build_datatrove_input(_materialize(tmp_path))
    config = MinHashSidecarConfig(
        threshold=0.8,
        ngram_size=5,
        num_buckets=8,
        hashes_per_bucket=10,
        seed=1,
        precision=64,
        hash_function="sha1",
    )

    report = normalize_datatrove_report(
        documents,
        datatrove_version="0.9.0",
        datatrove_exact_clusters=[["exact-a", "exact-b"]],
        datatrove_minhash_clusters=[["near-a", "near-b"]],
        config=config,
    )

    assert report["config"] == {
        "threshold": 0.8,
        "ngram_size": 5,
        "num_buckets": 8,
        "hashes_per_bucket": 10,
        "seed": 1,
        "tokenizer": "qgis_source_code_regex_v1",
        "hash_config": {"precision": 64, "hash_function": "sha1"},
        "lsh_inflection_threshold": pytest.approx(0.8122523963562356),
    }
    assert report["datatrove_version"] == "0.9.0"


def test_normalized_report_is_byte_stable_and_atomic(tmp_path: Path) -> None:
    documents = build_datatrove_input(_materialize(tmp_path))
    config = MinHashSidecarConfig()
    first = normalize_datatrove_report(
        documents,
        datatrove_version="0.9.0",
        datatrove_exact_clusters=[["exact-b", "exact-a"]],
        datatrove_minhash_clusters=[["near-b", "near-a"]],
        config=config,
    )
    second = normalize_datatrove_report(
        list(reversed(documents)),
        datatrove_version="0.9.0",
        datatrove_exact_clusters=[["exact-a", "exact-b"]],
        datatrove_minhash_clusters=[["near-a", "near-b"]],
        config=config,
    )
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"

    write_normalized_report(first_path, first)
    write_normalized_report(second_path, second)

    assert first_path.read_bytes() == second_path.read_bytes()
    assert not (tmp_path / "first.json.partial").exists()


def test_datatrove_runner_uses_lazy_real_pipeline_imports() -> None:
    namespace = runpy.run_path(str(RUNNER), run_name="qgis_datatrove_import_test")
    script = RUNNER.read_text(encoding="utf-8")

    assert callable(namespace["run_datatrove"])
    assert "from datatrove.data import Document" in script
    assert "ExactDedupSignature" in script
    assert "ExactFindDedups" in script
    assert "ExactDedupFilter" in script
    assert "MinhashDedupSignature" in script
    assert "MinhashDedupBuckets" in script
    assert "MinhashDedupCluster" in script
    assert "MinhashDedupFilter" in script
    assert "class QgisSourceCodeTokenizer" in script
    assert 'tokenizer="qgis_source_code_regex_v1"' in script
    assert 'language="eng"' not in script
    assert "minhash_removed_record_ids" not in script
    cluster_call = script.split("MinhashDedupCluster(", 1)[1].split(
        "minhash_excluded", 1
    )[0]
    assert ").run(None, 0, world_size=1)" in cluster_call
    assert ").run(None, rank=0, world_size=1)" not in cluster_call
