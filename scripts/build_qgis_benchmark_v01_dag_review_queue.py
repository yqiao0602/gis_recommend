#!/usr/bin/env python3
"""Build the immutable QGIS Planner v0.1 distinct-DAG review queue."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_DIR = ROOT / "benchmarks/qgis_planner_v1/authority"
QUEUE_SCHEMA = "gis_recommend.qgis_benchmark_v01_dag_review_queue.v1"
SUMMARY_SCHEMA = "gis_recommend.qgis_benchmark_v01_dag_review_queue_summary.v1"


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _process_id_sort_key(process_id: str) -> tuple[int, int | str]:
    match = re.fullmatch(r"p(\d+)", process_id)
    if match:
        return (0, int(match.group(1)))
    return (1, process_id)


def canonical_graph(
    processes: list[dict[str, Any]], links: list[dict[str, Any]]
) -> dict[str, list[dict[str, str]]]:
    """Return process-id-normalized, sorted parameter-free graph content."""
    if not processes:
        raise ValueError("canonical graph must contain at least one process")

    process_by_id: dict[str, dict[str, str]] = {}
    for process in processes:
        process_id = str(process.get("process_id", "")).strip()
        operator_id = str(process.get("operator_id", "")).strip().lower()
        stable101_l3 = str(process.get("stable101_l3", "")).strip()
        if not process_id or not operator_id or not stable101_l3:
            raise ValueError("process authority fields must be nonempty")
        if process_id in process_by_id:
            raise ValueError(f"duplicate process_id: {process_id}")
        if "parameters" in process:
            raise ValueError("canonical graph must be parameter-free")
        process_by_id[process_id] = {
            "operator_id": operator_id,
            "stable101_l3": stable101_l3,
        }

    ordered_ids = sorted(process_by_id, key=_process_id_sort_key)
    canonical_ids = {
        process_id: f"p{index}" for index, process_id in enumerate(ordered_ids)
    }
    canonical_processes = [
        {
            "process_id": canonical_ids[process_id],
            **process_by_id[process_id],
        }
        for process_id in ordered_ids
    ]

    canonical_link_pairs: set[tuple[str, str]] = set()
    for link in links:
        source = str(link.get("source_process_id", "")).strip()
        target = str(link.get("target_process_id", "")).strip()
        if source not in canonical_ids or target not in canonical_ids:
            raise ValueError("link references an unknown process_id")
        if source == target:
            raise ValueError("self-linked processes are not valid DAG authority")
        canonical_link_pairs.add((canonical_ids[source], canonical_ids[target]))
    canonical_links = [
        {"source_process_id": source, "target_process_id": target}
        for source, target in sorted(canonical_link_pairs)
    ]
    return {"processes": canonical_processes, "links": canonical_links}


def _consistent(group: list[dict[str, Any]], field: str) -> Any:
    serialized = {
        json.dumps(row.get(field), ensure_ascii=False, sort_keys=True): row.get(field)
        for row in group
    }
    if len(serialized) != 1:
        raise ValueError(
            f"normalized DAG {group[0]['normalized_dag_key']} has conflicting {field}"
        )
    value = next(iter(serialized.values()))
    if value is None or value == "" or value == []:
        raise ValueError(
            f"normalized DAG {group[0]['normalized_dag_key']} has empty {field}"
        )
    return value


def _sorted_nonempty(group: list[dict[str, Any]], field: str) -> list[str]:
    values = {
        str(row.get(field, "")).strip()
        for row in group
        if str(row.get(field, "")).strip()
    }
    return sorted(values)


def _consistent_sorted_list(
    group: list[dict[str, Any]], field: str
) -> list[str]:
    normalized = {
        tuple(
            sorted(
                {
                    str(value).strip()
                    for value in row.get(field, [])
                    if str(value).strip()
                }
            )
        )
        for row in group
    }
    if len(normalized) != 1:
        raise ValueError(
            f"normalized DAG {group[0]['normalized_dag_key']} has conflicting {field}"
        )
    values = list(next(iter(normalized)))
    if not values:
        raise ValueError(
            f"normalized DAG {group[0]['normalized_dag_key']} has empty {field}"
        )
    return values


def build_queue(candidate_path: Path) -> dict[str, object]:
    """Collapse candidate rows into immutable normalized-DAG review units."""
    candidate_bytes = candidate_path.read_bytes()
    candidates = [
        json.loads(line)
        for line in candidate_bytes.decode("utf-8-sig").splitlines()
        if line.strip()
    ]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_candidate_ids: set[str] = set()
    for row in candidates:
        candidate_id = str(row.get("candidate_id", "")).strip()
        normalized_dag_key = str(row.get("normalized_dag_key", "")).strip()
        if not candidate_id or not normalized_dag_key:
            raise ValueError("candidate_id and normalized_dag_key must be nonempty")
        if candidate_id in seen_candidate_ids:
            raise ValueError(f"duplicate candidate_id: {candidate_id}")
        if row.get("parameters_included") is not False:
            raise ValueError(f"candidate {candidate_id} must be parameter-free")
        seen_candidate_ids.add(candidate_id)
        grouped[normalized_dag_key].append(row)

    queue_rows: list[dict[str, Any]] = []
    for normalized_dag_key in sorted(grouped):
        group = grouped[normalized_dag_key]
        graphs = [
            canonical_graph(row.get("processes", []), row.get("links", []))
            for row in group
        ]
        graph_encodings = {_json_bytes(graph) for graph in graphs}
        if len(graph_encodings) != 1:
            raise ValueError(
                f"normalized DAG {normalized_dag_key} has conflicting "
                "canonical graph content"
            )
        graph = graphs[0]

        candidate_ids = _sorted_nonempty(group, "candidate_id")
        provenance_classes = _sorted_nonempty(group, "provenance_class")
        if len(candidate_ids) != len(group) or not provenance_classes:
            raise ValueError(
                f"normalized DAG {normalized_dag_key} has incomplete "
                "candidate provenance"
            )
        source_authority_keys = sorted(
            {
                str(
                    row.get("supply_authority_key")
                    or row.get("source_authority_key")
                    or ""
                ).strip()
                for row in group
                if str(
                    row.get("supply_authority_key")
                    or row.get("source_authority_key")
                    or ""
                ).strip()
            }
        )
        if not source_authority_keys:
            raise ValueError(
                f"normalized DAG {normalized_dag_key} has no source authority"
            )

        covered_l3 = _consistent_sorted_list(group, "covered_l3")
        queue_rows.append(
            {
                "schema": QUEUE_SCHEMA,
                "canonical_graph_id": normalized_dag_key,
                "canonical_graph_sha256": _sha256_bytes(_json_bytes(graph)),
                "normalized_dag_key": normalized_dag_key,
                "semantic_dag_key": _consistent(group, "semantic_dag_key"),
                "forbidden_near_dag_keys": _sorted_nonempty(
                    group, "forbidden_near_dag_key"
                ),
                "candidate_ids": candidate_ids,
                "source_authority_keys": source_authority_keys,
                "provenance_classes": provenance_classes,
                "quota_anchor_l3": _consistent(group, "quota_anchor_l3"),
                "covered_l3": covered_l3,
                "modality": _consistent(group, "modality"),
                "topology": _consistent(group, "topology"),
                "graph_size_stratum": _consistent(
                    group, "graph_size_stratum"
                ),
                **graph,
                "parameters_included": False,
                "review_status": "pending",
            }
        )

    summary = {
        "schema": SUMMARY_SCHEMA,
        "candidate_input_sha256": _sha256_bytes(candidate_bytes),
        "candidate_count": len(candidates),
        "distinct_dag_count": len(queue_rows),
        "modality_counts": dict(
            sorted(Counter(row["modality"] for row in queue_rows).items())
        ),
        "topology_counts": dict(
            sorted(Counter(row["topology"] for row in queue_rows).items())
        ),
        "graph_size_counts": dict(
            sorted(
                Counter(row["graph_size_stratum"] for row in queue_rows).items()
            )
        ),
        "provenance_class_dag_counts": dict(
            sorted(
                Counter(
                    provenance
                    for row in queue_rows
                    for provenance in row["provenance_classes"]
                ).items()
            )
        ),
        "review_status_counts": {"pending": len(queue_rows)},
        "parameters_included": False,
        "queue_status": "pending_review",
    }
    return {"rows": queue_rows, "summary": summary}


def write_outputs(result: dict[str, object], output_dir: Path) -> dict[str, Path]:
    """Write canonical JSONL and summary artifacts using LF endings."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "queue": output_dir / "v01_dag_review_queue.jsonl",
        "summary": output_dir / "v01_dag_review_queue_summary.json",
    }
    with paths["queue"].open("w", encoding="utf-8", newline="\n") as handle:
        for row in result["rows"]:
            handle.write(_json_bytes(row).decode("utf-8") + "\n")
    with paths["summary"].open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(
                result["summary"],
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate-supply",
        type=Path,
        default=AUTHORITY_DIR / "candidate_supply.jsonl",
    )
    parser.add_argument("--output-dir", type=Path, default=AUTHORITY_DIR)
    args = parser.parse_args(argv)

    result = build_queue(args.candidate_supply)
    write_outputs(result, args.output_dir)
    print(
        f"candidates={result['summary']['candidate_count']} "
        f"dags={result['summary']['distinct_dag_count']} "
        f"status={result['summary']['queue_status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
