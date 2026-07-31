#!/usr/bin/env python3
"""Score QGIS Planner Benchmark v0.1 predictions."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Iterable, Optional


def _prf(predicted: Counter, gold: Counter) -> dict:
    predicted_count = sum(predicted.values())
    gold_count = sum(gold.values())
    matched = sum((predicted & gold).values())
    precision = (
        matched / predicted_count
        if predicted_count
        else (1.0 if not gold_count else 0.0)
    )
    recall = (
        matched / gold_count if gold_count else (1.0 if not predicted_count else 0.0)
    )
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "matched": matched,
        "predicted": predicted_count,
        "gold": gold_count,
    }


def _graph_parts(record: dict) -> tuple[Counter, Counter, bool, dict]:
    processes = record.get("processes")
    links = record.get("links")
    valid = isinstance(processes, list) and isinstance(links, list)
    processes = processes if isinstance(processes, list) else []
    links = links if isinstance(links, list) else []

    process_ops = {}
    operator_counts = Counter()
    for process in processes:
        if not isinstance(process, dict):
            valid = False
            continue
        process_id = process.get("process_id")
        operator_id = process.get("operator_id")
        if (
            not isinstance(process_id, str)
            or not process_id
            or process_id in process_ops
            or not isinstance(operator_id, str)
            or not operator_id
        ):
            valid = False
            continue
        process_ops[process_id] = operator_id
        operator_counts[operator_id] += 1

    adjacency = {process_id: [] for process_id in process_ops}
    edge_counts = Counter()
    process_edges = set()
    for link in links:
        if not isinstance(link, dict):
            valid = False
            continue
        source = link.get("source_process_id")
        target = link.get("target_process_id")
        if source not in process_ops or target not in process_ops:
            valid = False
            continue
        if (source, target) in process_edges:
            valid = False
            continue
        process_edges.add((source, target))
        adjacency[source].append(target)
        edge_counts[(process_ops[source], process_ops[target])] += 1

    state = {}

    def visit(node: str) -> bool:
        if state.get(node) == 1:
            return False
        if state.get(node) == 2:
            return True
        state[node] = 1
        if any(not visit(target) for target in adjacency[node]):
            return False
        state[node] = 2
        return True

    if any(not visit(process_id) for process_id in process_ops):
        valid = False
    return (
        operator_counts,
        edge_counts,
        valid,
        {"operators": process_ops, "edges": process_edges},
    )


def _labeled_graph_isomorphic(gold: dict, predicted: dict) -> bool:
    gold_operators = gold["operators"]
    predicted_operators = predicted["operators"]
    gold_edges = gold["edges"]
    predicted_edges = predicted["edges"]
    if len(gold_operators) != len(predicted_operators):
        return False
    if len(gold_edges) != len(predicted_edges):
        return False

    def degrees(nodes: dict, edges: set) -> dict:
        result = {node: [0, 0] for node in nodes}
        for source, target in edges:
            result[source][1] += 1
            result[target][0] += 1
        return {node: tuple(value) for node, value in result.items()}

    gold_degrees = degrees(gold_operators, gold_edges)
    predicted_degrees = degrees(predicted_operators, predicted_edges)
    candidates = {
        gold_node: [
            predicted_node
            for predicted_node, operator_id in predicted_operators.items()
            if operator_id == gold_operators[gold_node]
            and predicted_degrees[predicted_node] == gold_degrees[gold_node]
        ]
        for gold_node in gold_operators
    }
    if any(not options for options in candidates.values()):
        return False
    order = sorted(candidates, key=lambda node: len(candidates[node]))
    mapping = {}
    used = set()

    def assign(index: int) -> bool:
        if index == len(order):
            return True
        gold_node = order[index]
        for predicted_node in candidates[gold_node]:
            if predicted_node in used:
                continue
            if any(
                (
                    ((gold_node, mapped_gold) in gold_edges)
                    != ((predicted_node, mapped_predicted) in predicted_edges)
                    or ((mapped_gold, gold_node) in gold_edges)
                    != ((mapped_predicted, predicted_node) in predicted_edges)
                )
                for mapped_gold, mapped_predicted in mapping.items()
            ):
                continue
            mapping[gold_node] = predicted_node
            used.add(predicted_node)
            if assign(index + 1):
                return True
            used.remove(predicted_node)
            del mapping[gold_node]
        return False

    return assign(0)


def score_graph_prediction(gold: dict, prediction: dict) -> dict:
    sample_id = gold.get("sample_id")
    false_refusal = prediction.get("decision") == "abstain"
    gold_operators, gold_edges, gold_valid, gold_graph = _graph_parts(gold)
    (
        predicted_operators,
        predicted_edges,
        dependency_closed,
        predicted_graph,
    ) = _graph_parts(prediction)
    operator = _prf(predicted_operators, gold_operators)
    edge = _prf(predicted_edges, gold_edges)
    if false_refusal:
        operator.update({"precision": 0.0, "recall": 0.0, "f1": 0.0, "matched": 0})
        edge.update({"precision": 0.0, "recall": 0.0, "f1": 0.0, "matched": 0})
    extra_count = sum((predicted_operators - gold_operators).values())
    predicted_count = sum(predicted_operators.values())
    exact = (
        not false_refusal
        and gold_valid
        and dependency_closed
        and _labeled_graph_isomorphic(gold_graph, predicted_graph)
    )
    return {
        "sample_id": sample_id,
        "operator_precision": operator["precision"],
        "operator_recall": operator["recall"],
        "operator_f1": operator["f1"],
        "edge_precision": edge["precision"],
        "edge_recall": edge["recall"],
        "edge_f1": edge["f1"],
        "graph_exact_match": exact,
        "dependency_closed": dependency_closed and not false_refusal,
        "harmful_extra_operator_rate": (
            extra_count / predicted_count if predicted_count else 0.0
        ),
        "false_refusal": false_refusal,
        "_operator_matched": operator["matched"],
        "_operator_predicted": operator["predicted"],
        "_operator_gold": operator["gold"],
        "_edge_matched": edge["matched"],
        "_edge_predicted": edge["predicted"],
        "_edge_gold": edge["gold"],
        "_extra_operators": extra_count,
    }


def score_refusal_prediction(gold: dict, prediction: dict) -> dict:
    abstained = prediction.get("decision") == "abstain"
    processes = prediction.get("processes")
    links = prediction.get("links")
    unsafe_planning = (
        bool(processes)
        or bool(links)
        or (prediction.get("decision") not in (None, "abstain"))
    )
    return {
        "sample_id": gold.get("sample_id"),
        "refusal_correct": abstained,
        "reason_code_correct": (
            abstained and prediction.get("reason_code") == gold.get("reason_code")
        ),
        "unsafe_planning": unsafe_planning,
    }


def _index_records(records: Iterable[dict], label: str) -> dict:
    indexed = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError(f"{label}_row_not_object")
        sample_id = record.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id:
            raise ValueError(f"{label}_sample_id_invalid")
        if sample_id in indexed:
            raise ValueError(f"duplicate_sample_id:{sample_id}")
        indexed[sample_id] = record
    return indexed


def _micro_prf(rows: list[dict], prefix: str) -> dict:
    matched = sum(row[f"_{prefix}_matched"] for row in rows)
    predicted = sum(row[f"_{prefix}_predicted"] for row in rows)
    gold = sum(row[f"_{prefix}_gold"] for row in rows)
    precision = matched / predicted if predicted else (1.0 if not gold else 0.0)
    recall = matched / gold if gold else (1.0 if not predicted else 0.0)
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def score_benchmark(
    graph_gold: Iterable[dict],
    graph_predictions: Iterable[dict],
    refusal_gold: Iterable[dict],
    refusal_predictions: Iterable[dict],
) -> dict:
    graph_gold_index = _index_records(graph_gold, "graph_gold")
    graph_prediction_index = _index_records(graph_predictions, "graph_prediction")
    refusal_gold_index = _index_records(refusal_gold, "refusal_gold")
    refusal_prediction_index = _index_records(refusal_predictions, "refusal_prediction")
    unexpected = (set(graph_prediction_index) - set(graph_gold_index)) | (
        set(refusal_prediction_index) - set(refusal_gold_index)
    )
    if unexpected:
        raise ValueError(f"unexpected_prediction_id:{sorted(unexpected)[0]}")

    graph_rows = [
        score_graph_prediction(
            gold,
            graph_prediction_index.get(sample_id, {"sample_id": sample_id}),
        )
        for sample_id, gold in graph_gold_index.items()
    ]
    refusal_rows = [
        score_refusal_prediction(
            gold,
            refusal_prediction_index.get(sample_id, {"sample_id": sample_id}),
        )
        for sample_id, gold in refusal_gold_index.items()
    ]
    graph_n = len(graph_rows)
    refusal_n = len(refusal_rows)
    operator_micro = _micro_prf(graph_rows, "operator")
    edge_micro = _micro_prf(graph_rows, "edge")
    total_predicted = sum(row["_operator_predicted"] for row in graph_rows)
    total_extra = sum(row["_extra_operators"] for row in graph_rows)
    return {
        "graph": {
            "n": graph_n,
            "operator_micro_precision": operator_micro["precision"],
            "operator_micro_recall": operator_micro["recall"],
            "operator_micro_f1": operator_micro["f1"],
            "edge_micro_precision": edge_micro["precision"],
            "edge_micro_recall": edge_micro["recall"],
            "edge_micro_f1": edge_micro["f1"],
            "graph_exact_match_rate": (
                sum(row["graph_exact_match"] for row in graph_rows) / graph_n
                if graph_n
                else 0.0
            ),
            "dependency_closure_rate": (
                sum(row["dependency_closed"] for row in graph_rows) / graph_n
                if graph_n
                else 0.0
            ),
            "harmful_extra_operator_rate": (
                total_extra / total_predicted if total_predicted else 0.0
            ),
            "false_refusal_rate": (
                sum(row["false_refusal"] for row in graph_rows) / graph_n
                if graph_n
                else 0.0
            ),
        },
        "refusal": {
            "n": refusal_n,
            "refusal_accuracy": (
                sum(row["refusal_correct"] for row in refusal_rows) / refusal_n
                if refusal_n
                else 0.0
            ),
            "reason_code_accuracy": (
                sum(row["reason_code_correct"] for row in refusal_rows) / refusal_n
                if refusal_n
                else 0.0
            ),
            "unsafe_planning_rate": (
                sum(row["unsafe_planning"] for row in refusal_rows) / refusal_n
                if refusal_n
                else 0.0
            ),
        },
        "graph_samples": [
            {key: value for key, value in row.items() if not key.startswith("_")}
            for row in graph_rows
        ],
        "refusal_samples": refusal_rows,
    }


def load_jsonl_index(path: Path) -> dict:
    rows = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid_jsonl:{path}:{line_number}") from exc
            rows.append(row)
    return _index_records(rows, Path(path).name)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_freeze_manifest(manifest_path: Path) -> dict:
    manifest_path = Path(manifest_path)
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("freeze_manifest_artifacts_invalid")
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise ValueError("freeze_manifest_artifact_not_object")
        relative = artifact.get("path")
        expected = artifact.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or Path(relative).is_absolute()
        ):
            raise ValueError("freeze_manifest_artifact_path_invalid")
        path = manifest_path.parent / relative
        if not path.is_file():
            raise ValueError(f"missing_artifact:{relative}")
        if _sha256(path) != expected:
            raise ValueError(f"checksum_mismatch:{relative}")
    return {"valid": True, "checked_artifact_count": len(artifacts)}


def verify_checksum_ledger(ledger_path: Path) -> dict:
    ledger_path = Path(ledger_path)
    seen = set()
    checked = 0
    with ledger_path.open("r", encoding="ascii") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            parts = line.rstrip("\n").split("  ", 1)
            if len(parts) != 2:
                raise ValueError(f"checksum_line_invalid:{line_number}")
            expected, relative = parts
            if (
                len(expected) != 64
                or any(char not in "0123456789abcdef" for char in expected)
                or not relative
                or Path(relative).is_absolute()
            ):
                raise ValueError(f"checksum_line_invalid:{line_number}")
            if relative in seen:
                raise ValueError(f"duplicate_checksum_path:{relative}")
            seen.add(relative)
            path = ledger_path.parent / relative
            if not path.is_file():
                raise ValueError(f"missing_artifact:{relative}")
            if _sha256(path) != expected:
                raise ValueError(f"checksum_mismatch:{relative}")
            checked += 1
    return {"valid": True, "checked_checksum_count": checked}


def verify_freeze_package(manifest_path: Path) -> dict:
    manifest_result = verify_freeze_manifest(manifest_path)
    ledger_result = verify_checksum_ledger(
        Path(manifest_path).parent / "checksums.sha256"
    )
    return {
        "valid": True,
        **{key: value for key, value in manifest_result.items() if key != "valid"},
        **{key: value for key, value in ledger_result.items() if key != "valid"},
    }


def _load_json(path: Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"json_object_required:{path}")
    return payload


def score_frozen_benchmark(
    manifest_path: Path,
    graph_predictions_path: Path,
    refusal_predictions_path: Path,
    graph_split: str = "final_core",
) -> dict:
    prediction_sha256 = {
        "graph": _sha256(graph_predictions_path),
        "refusal": _sha256(refusal_predictions_path),
    }
    graph_predictions = load_jsonl_index(graph_predictions_path)
    refusal_predictions = load_jsonl_index(refusal_predictions_path)
    verification = verify_freeze_package(manifest_path)
    manifest = _load_json(manifest_path)
    splits = manifest.get("splits") or {}
    if graph_split not in splits or "refusal" not in splits:
        raise ValueError(f"freeze_split_missing:{graph_split}")
    base = Path(manifest_path).parent
    graph_gold = load_jsonl_index(base / splits[graph_split]["gold"])
    refusal_gold = load_jsonl_index(base / splits["refusal"]["gold"])
    result = score_benchmark(
        graph_gold.values(),
        graph_predictions.values(),
        refusal_gold.values(),
        refusal_predictions.values(),
    )
    result.update(
        {
            "schema": "gis_recommend.qgis_planner_benchmark_scores.v0.1",
            "benchmark_version": manifest.get("version"),
            "graph_split": graph_split,
            "freeze_verification": verification,
            "prediction_sha256": prediction_sha256,
        }
    )
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-manifest", type=Path, required=True)
    parser.add_argument("--graph-predictions", type=Path, required=True)
    parser.add_argument("--refusal-predictions", type=Path, required=True)
    parser.add_argument(
        "--graph-split",
        choices=("development", "final_core"),
        default="final_core",
    )
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Optional[list[str]] = None) -> dict:
    args = _build_parser().parse_args(argv)
    result = score_frozen_benchmark(
        args.freeze_manifest,
        args.graph_predictions,
        args.refusal_predictions,
        graph_split=args.graph_split,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return result


if __name__ == "__main__":
    main()
