from pathlib import Path

from scripts.build_qgis_production_yield_ledger import build_ledger


def test_ledger_counts_quality_provenance_and_overlap(tmp_path: Path):
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    first.write_text(
        '\n'.join([
            '{"sample_id":"a","source_sha256":"s1","training_pair_key":"p1","operator_sequence":["native:buffer"],"task_type":"buffer","_training_quality":{"sample_weight":1.0,"tier":"gold"}}',
            '{"sample_id":"b","source_sha256":"s2","parent_source_sha256":"parent","training_pair_key":"p2","operator_sequence":["native:clip","native:dissolve"],"task_type":"overlay","_training_quality":{"sample_weight":0.7,"tier":"silver"}}',
        ]) + '\n',
        encoding="utf-8",
    )
    second.write_text(
        '{"sample_id":"c","source_sha256":"s1","training_pair_key":"p3","training_row_emitted":false}',
        encoding="utf-8",
    )
    ledger = build_ledger([("first", first)], [("second", second)])
    assert ledger["authority_modified"] is False
    assert ledger["training_data_modified"] is False
    first_metrics = ledger["entries"][0]["metrics"]
    assert first_metrics["rows"] == 2
    assert first_metrics["unique_source_sha256"] == 2
    assert first_metrics["unique_parent_source_sha256"] == 2
    assert first_metrics["quality_tiers"]["Gold"] == 1
    assert first_metrics["quality_tiers"]["Silver"] == 1
    assert first_metrics["operator_sequence_length"] == {"min": 1, "max": 2, "mean": 1.5}
    assert ledger["cross_entry_overlap"] == [{
        "left": "first",
        "right": "second",
        "source_sha256_overlap": 1,
        "training_pair_key_overlap": 0,
    }]


def test_ledger_handles_candidate_without_provenance(tmp_path: Path):
    path = tmp_path / "candidate.jsonl"
    path.write_text('{"candidate_id":"x","review_status":"pending"}\n', encoding="utf-8")
    ledger = build_ledger([], [("candidate", path)])
    metrics = ledger["entries"][0]["metrics"]
    assert metrics["rows"] == 1
    assert metrics["unique_source_sha256"] == 0
    assert metrics["unique_sample_ids"] == 1
