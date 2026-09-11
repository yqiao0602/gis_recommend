from pathlib import Path
import hashlib
import importlib.util
import json

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCORER = ROOT / "scripts" / "score_qgis_planner_benchmark_v01.py"
FREEZE = ROOT / "benchmarks" / "qgis_planner_v1" / "releases" / "v0.1-freeze"


def _module():
    spec = importlib.util.spec_from_file_location("qgis_planner_v01_scorer", SCORER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_unified_scoring_entrypoint_exists() -> None:
    assert SCORER.is_file()


def _graph(sample_id: str = "sample-1") -> dict:
    return {
        "sample_id": sample_id,
        "processes": [
            {"process_id": "p0", "operator_id": "native:buffer"},
            {"process_id": "p1", "operator_id": "native:clip"},
        ],
        "links": [
            {"source_process_id": "p0", "target_process_id": "p1"},
        ],
    }


def test_graph_scoring_is_process_id_and_serialization_invariant() -> None:
    prediction = {
        "sample_id": "sample-1",
        "processes": [
            {"process_id": "result", "operator_id": "native:clip"},
            {"process_id": "source", "operator_id": "native:buffer"},
        ],
        "links": [
            {"source_process_id": "source", "target_process_id": "result"},
        ],
    }

    score = _module().score_graph_prediction(_graph(), prediction)

    assert score["graph_exact_match"] is True
    assert score["operator_f1"] == 1.0
    assert score["edge_f1"] == 1.0
    assert score["dependency_closed"] is True
    assert score["false_refusal"] is False


def test_graph_scoring_penalizes_missing_edge_without_losing_operator_match() -> None:
    prediction = {**_graph(), "links": []}

    score = _module().score_graph_prediction(_graph(), prediction)

    assert score["operator_f1"] == 1.0
    assert score["edge_recall"] == 0.0
    assert score["edge_f1"] == 0.0
    assert score["graph_exact_match"] is False
    assert score["dependency_closed"] is True


def test_graph_scoring_flags_extra_operator_invalid_link_and_cycle() -> None:
    prediction = {
        "sample_id": "sample-1",
        "processes": [
            {"process_id": "x", "operator_id": "native:buffer"},
            {"process_id": "y", "operator_id": "native:dissolve"},
        ],
        "links": [
            {"source_process_id": "x", "target_process_id": "missing"},
            {"source_process_id": "x", "target_process_id": "y"},
            {"source_process_id": "y", "target_process_id": "x"},
        ],
    }

    score = _module().score_graph_prediction(_graph(), prediction)

    assert score["harmful_extra_operator_rate"] == 0.5
    assert score["dependency_closed"] is False
    assert score["graph_exact_match"] is False


def test_exact_match_distinguishes_topology_with_repeated_operators() -> None:
    gold = {
        "sample_id": "repeated",
        "processes": [
            {"process_id": "p0", "operator_id": "native:fieldcalculator"},
            {"process_id": "p1", "operator_id": "native:fieldcalculator"},
            {"process_id": "p2", "operator_id": "native:fieldcalculator"},
        ],
        "links": [
            {"source_process_id": "p0", "target_process_id": "p1"},
            {"source_process_id": "p1", "target_process_id": "p2"},
        ],
    }
    prediction = {
        "sample_id": "repeated",
        "processes": [
            {"process_id": "x", "operator_id": "native:fieldcalculator"},
            {"process_id": "y", "operator_id": "native:fieldcalculator"},
            {"process_id": "z", "operator_id": "native:fieldcalculator"},
        ],
        "links": [
            {"source_process_id": "x", "target_process_id": "y"},
            {"source_process_id": "x", "target_process_id": "z"},
        ],
    }

    score = _module().score_graph_prediction(gold, prediction)

    assert score["operator_f1"] == 1.0
    assert score["edge_f1"] == 1.0
    assert score["graph_exact_match"] is False


def test_supported_abstention_is_a_false_refusal() -> None:
    score = _module().score_graph_prediction(
        _graph(),
        {"sample_id": "sample-1", "decision": "abstain"},
    )

    assert score["false_refusal"] is True
    assert score["graph_exact_match"] is False
    assert score["operator_f1"] == 0.0
    assert score["edge_f1"] == 0.0


def test_refusal_scoring_keeps_accuracy_and_unsafe_planning_separate() -> None:
    gold = {
        "sample_id": "refusal-1",
        "decision": "abstain",
        "reason_code": "unsupported_capability",
    }

    correct = _module().score_refusal_prediction(
        gold,
        {
            "sample_id": "refusal-1",
            "decision": "abstain",
            "reason_code": "unsupported_capability",
        },
    )
    unsafe = _module().score_refusal_prediction(
        gold,
        {
            "sample_id": "refusal-1",
            "processes": [{"process_id": "p0", "operator_id": "native:buffer"}],
            "links": [],
        },
    )

    assert correct == {
        "sample_id": "refusal-1",
        "refusal_correct": True,
        "reason_code_correct": True,
        "unsafe_planning": False,
    }
    assert unsafe["refusal_correct"] is False
    assert unsafe["unsafe_planning"] is True


def test_refusal_scoring_treats_links_only_output_as_unsafe_planning() -> None:
    score = _module().score_refusal_prediction(
        {
            "sample_id": "refusal-1",
            "decision": "abstain",
            "reason_code": "unsupported_capability",
        },
        {
            "sample_id": "refusal-1",
            "processes": [],
            "links": [
                {"source_process_id": "missing-1", "target_process_id": "missing-2"}
            ],
        },
    )

    assert score["unsafe_planning"] is True


def test_benchmark_aggregate_uses_separate_graph_and_refusal_denominators() -> None:
    graph_gold = [_graph("g1"), _graph("g2")]
    graph_predictions = [
        _graph("g1"),
        {"sample_id": "g2", "decision": "abstain"},
    ]
    refusal_gold = [
        {
            "sample_id": "r1",
            "decision": "abstain",
            "reason_code": "underspecified_goal",
        }
    ]
    refusal_predictions = [
        {
            "sample_id": "r1",
            "decision": "abstain",
            "reason_code": "underspecified_goal",
        }
    ]

    result = _module().score_benchmark(
        graph_gold,
        graph_predictions,
        refusal_gold,
        refusal_predictions,
    )

    assert result["graph"]["n"] == 2
    assert result["graph"]["graph_exact_match_rate"] == 0.5
    assert result["graph"]["false_refusal_rate"] == 0.5
    assert result["refusal"] == {
        "n": 1,
        "refusal_accuracy": 1.0,
        "reason_code_accuracy": 1.0,
        "unsafe_planning_rate": 0.0,
    }


def test_jsonl_loader_rejects_duplicate_sample_ids(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.jsonl"
    row = {"sample_id": "same", "decision": "abstain"}
    path.write_text(
        json.dumps(row) + "\n" + json.dumps(row) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate_sample_id:same"):
        _module().load_jsonl_index(path)


def test_freeze_manifest_verification_detects_checksum_mismatch(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "data.json"
    artifact.write_text('{"ok": true}\n', encoding="utf-8")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest = tmp_path / "benchmark_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": "gis_recommend.qgis_planner_benchmark_freeze.v0.1",
                "version": "0.1.0",
                "artifacts": [
                    {"path": "data.json", "sha256": digest},
                ],
            }
        ),
        encoding="utf-8",
    )

    assert _module().verify_freeze_manifest(manifest) == {
        "valid": True,
        "checked_artifact_count": 1,
    }

    artifact.write_text('{"ok": false}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="checksum_mismatch:data.json"):
        _module().verify_freeze_manifest(manifest)


def test_checksum_ledger_detects_package_metadata_change(tmp_path: Path) -> None:
    metadata = tmp_path / "VERSION"
    metadata.write_text("0.1.0\n", encoding="ascii")
    digest = hashlib.sha256(metadata.read_bytes()).hexdigest()
    ledger = tmp_path / "checksums.sha256"
    ledger.write_text(f"{digest}  VERSION\n", encoding="ascii")

    assert _module().verify_checksum_ledger(ledger) == {
        "valid": True,
        "checked_checksum_count": 1,
    }

    metadata.write_text("0.1.1\n", encoding="ascii")
    with pytest.raises(ValueError, match="checksum_mismatch:VERSION"):
        _module().verify_checksum_ledger(ledger)


def test_predictions_are_hashed_and_loaded_before_sealed_freeze_verification(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _module()
    graph_predictions = tmp_path / "graph.jsonl"
    refusal_predictions = tmp_path / "refusal.jsonl"
    events = []

    def fake_sha256(path: Path) -> str:
        events.append(("hash", Path(path).name))
        return "0" * 64

    def fake_load_jsonl(path: Path) -> dict:
        events.append(("load", Path(path).name))
        return {}

    def fake_verify(path: Path) -> dict:
        events.append(("verify", Path(path).name))
        return {"valid": True}

    monkeypatch.setattr(module, "_sha256", fake_sha256)
    monkeypatch.setattr(module, "load_jsonl_index", fake_load_jsonl)
    monkeypatch.setattr(module, "verify_freeze_package", fake_verify)
    monkeypatch.setattr(
        module,
        "_load_json",
        lambda path: {
            "version": "0.1.0",
            "splits": {
                "final_core": {"gold": "graph-gold.jsonl"},
                "refusal": {"gold": "refusal-gold.jsonl"},
            },
        },
    )

    module.score_frozen_benchmark(
        tmp_path / "benchmark_manifest.json",
        graph_predictions,
        refusal_predictions,
    )

    verify_index = events.index(("verify", "benchmark_manifest.json"))
    assert events.index(("hash", "graph.jsonl")) < verify_index
    assert events.index(("hash", "refusal.jsonl")) < verify_index
    assert events.index(("load", "graph.jsonl")) < verify_index
    assert events.index(("load", "refusal.jsonl")) < verify_index


def test_committed_freeze_manifest_binds_expected_splits_and_artifacts() -> None:
    manifest_path = FREEZE / "benchmark_manifest.json"

    verification = _module().verify_freeze_package(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert verification["valid"] is True
    assert verification["checked_artifact_count"] == 24
    assert verification["checked_checksum_count"] == 27
    assert manifest["version"] == "0.1.0"
    assert manifest["status"] == "internal_sealed_freeze"
    assert {
        name: split["task_count"] for name, split in manifest["splits"].items()
    } == {"development": 40, "final_core": 120, "refusal": 12}
    assert manifest["splits"]["final_core"]["gold"].endswith("gold_graphs.sealed.jsonl")
    assert manifest["splits"]["refusal"]["gold"].endswith("gold.sealed.jsonl")


def test_full_freeze_scores_perfect_synthetic_predictions(
    tmp_path: Path,
) -> None:
    manifest_path = FREEZE / "benchmark_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    def copy_as_predictions(split: str, name: str) -> Path:
        gold_path = FREEZE / manifest["splits"][split]["gold"]
        output = tmp_path / name
        output.write_bytes(gold_path.read_bytes())
        return output

    graph_predictions = copy_as_predictions("final_core", "graph.jsonl")
    refusal_predictions = copy_as_predictions("refusal", "refusal.jsonl")

    result = _module().score_frozen_benchmark(
        manifest_path,
        graph_predictions,
        refusal_predictions,
    )

    assert result["graph"]["n"] == 120
    assert result["graph"]["graph_exact_match_rate"] == 1.0
    assert result["graph"]["operator_micro_f1"] == 1.0
    assert result["graph"]["edge_micro_f1"] == 1.0
    assert result["refusal"] == {
        "n": 12,
        "refusal_accuracy": 1.0,
        "reason_code_accuracy": 1.0,
        "unsafe_planning_rate": 0.0,
    }
    assert result["freeze_verification"] == {
        "valid": True,
        "checked_artifact_count": 24,
        "checked_checksum_count": 27,
    }
    assert set(result["prediction_sha256"]) == {"graph", "refusal"}
