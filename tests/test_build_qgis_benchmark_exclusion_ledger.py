from __future__ import annotations

import importlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _module():
    return importlib.import_module("scripts.build_qgis_benchmark_exclusion_ledger")


def test_default_inventory_freezes_all_known_exposure_surfaces() -> None:
    module = _module()
    inventory = module.inspect_inventory(ROOT, module.DEFAULT_ARTIFACTS)

    assert len(inventory) == 15
    assert sum(row["actual_record_count"] for row in inventory) == 106_547
    assert {row["artifact_id"] for row in inventory} == {
        "gee_quality_gate_v4",
        "qgis_canonical_685",
        "qgis_vector_unified_10768",
        "qgis_api_trace_6031",
        "qgis_unified_train_v1_107",
        "gee_raster_core_train_11397",
        "qgis_multistep_audit_50",
        "qgis_stable101_audit_first_50",
        "qgis_stable101_audit_second_50",
        "gee_raster_core_audit_50",
        "unseen_vector_prompts_70",
        "end_to_end_probes_50",
        "heldout_v46_150",
        "open_landing_v46_80",
        "qgis_stable106_direct_descriptions_125",
    }
    assert all(row["record_count_matches"] for row in inventory)


def test_hash_identity_catches_body_dag_and_order_independent_near_dag_overlap(
    tmp_path: Path,
) -> None:
    module = _module()
    source_a = tmp_path / "a.py"
    source_b = tmp_path / "b.py"
    source_c = tmp_path / "c.py"
    source_a.write_text(
        "# Source repo: repo-a\n# Source path: x.py\n\nrun()\n",
        encoding="utf-8",
    )
    source_b.write_text(
        "# Source repo: repo-b\n# Source path: y.py\n\nrun()\n",
        encoding="utf-8",
    )
    source_c.write_text("different()\n", encoding="utf-8")
    records = [
        {
            "source_path": str(source_a),
            "source_sha256": module.file_sha256(source_a),
            "task_description": "Buffer roads, then clip the result.",
            "operator_sequence": ["native:buffer", "native:clip"],
            "l3_code_sequence": ["L3_BUFFER", "L3_CLIP"],
            "dependency_edges": [[0, 1]],
        },
        {
            "source_path": str(source_b),
            "source_sha256": module.file_sha256(source_b),
            "task_description": "Clip the buffer output to the study area.",
            "operator_sequence": ["native:buffer", "native:clip"],
            "l3_code_sequence": ["L3_BUFFER", "L3_CLIP"],
            "dependency_edges": [[0, 1]],
        },
        {
            "source_path": str(source_c),
            "source_sha256": module.file_sha256(source_c),
            "task_description": "Run two independent preparations.",
            "operator_sequence": ["native:fixgeometries", "native:reprojectlayer"],
            "l3_code_sequence": ["L3_FIX", "L3_REPROJECT"],
            "dependency_edges": [],
        },
        {
            "source_path": str(source_c),
            "source_sha256": module.file_sha256(source_c),
            "task_description": "Run the same independent preparations.",
            "operator_sequence": ["native:reprojectlayer", "native:fixgeometries"],
            "l3_code_sequence": ["L3_REPROJECT", "L3_FIX"],
            "dependency_edges": [],
        },
    ]
    rows = [
        module.fingerprint_record(record, artifact_id="synthetic", record_index=index)
        for index, record in enumerate(records)
    ]

    assert rows[0]["source_sha256"] != rows[1]["source_sha256"]
    assert (
        rows[0]["normalized_source_body_sha256"]
        == rows[1]["normalized_source_body_sha256"]
    )
    assert rows[0]["normalized_dag_key"] == rows[1]["normalized_dag_key"]
    assert rows[2]["normalized_dag_key"] != rows[3]["normalized_dag_key"]
    assert rows[2]["forbidden_near_dag_key"] == rows[3]["forbidden_near_dag_key"]

    indexes = module.build_overlap_indexes(rows)
    overlap = module.check_candidate_overlap(records[1], indexes)
    assert {
        "source_sha256",
        "normalized_source_body_sha256",
        "normalized_dag_key",
        "forbidden_near_dag_key",
        "semantic_dag_key",
        "task_text_signature",
        "task_text_token_signature",
    } >= set(overlap)
    assert set(overlap["normalized_source_body_sha256"]) == {
        "synthetic:0",
        "synthetic:1",
    }
    assert set(overlap["normalized_dag_key"]) == {"synthetic:0", "synthetic:1"}


def test_fingerprint_adapts_json_string_sequences_without_retaining_raw_text() -> None:
    module = _module()
    row = module.fingerprint_record(
        {
            "task_description": "A UNIQUE SECRET TASK STRING",
            "operator_sequence_json": '["native:buffer", "native:clip"]',
            "l3_codes_json": '["L3_BUFFER", "L3_CLIP"]',
            "dependency_edges": [
                {"producer_ordinal": 0, "consumer_ordinal": 1}
            ],
        },
        artifact_id="synthetic",
        record_index=7,
    )

    encoded = json.dumps(row, ensure_ascii=False)
    assert "A UNIQUE SECRET TASK STRING" not in encoded
    assert "native:buffer" not in encoded
    assert "L3_BUFFER" not in encoded
    assert row["record_type"] == "exclusion"
    assert row["source_identity_status"] == "unavailable"
    assert row["normalized_dag_key"]
    assert row["semantic_dag_key"]
    assert row["task_text_signature"]


def test_write_output_creates_only_gate2_ledger(tmp_path: Path) -> None:
    module = _module()
    rows = [
        {
            "record_type": "artifact",
            "artifact_id": "synthetic",
            "artifact_path": "synthetic.jsonl",
            "artifact_sha256": "0" * 64,
            "platform": "qgis",
            "exposure_class": "test",
            "expected_record_count": 0,
            "actual_record_count": 0,
        }
    ]

    output = module.write_output(rows, tmp_path)

    assert output == tmp_path / "source_exclusion_ledger.jsonl"
    assert [path.name for path in tmp_path.iterdir()] == [
        "source_exclusion_ledger.jsonl"
    ]
    assert json.loads(output.read_text(encoding="utf-8")) == rows[0]
