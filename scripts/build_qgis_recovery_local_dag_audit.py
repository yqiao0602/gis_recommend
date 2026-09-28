#!/usr/bin/env python3
"""Build the source-disjoint census audit for recovery local-DAG candidates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATES = (
    ROOT
    / "docs/reports/qgis_recovery_local_dag_units_v1"
    / "recovery_local_dag_candidates_v1.jsonl"
)
DEFAULT_OUTPUT_DIR = (
    ROOT / "docs/reports/qgis_recovery_local_dag_units_v1/audit_census_v1"
)
HUMAN_FIELDS = (
    "human_dependency_correct",
    "human_operator_order_correct",
    "human_boundary_correct",
    "human_fanin_semantics_correct",
    "human_description_faithful",
    "human_final_decision",
    "human_notes",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def filter_candidates_by_replay(
    candidate_rows: list[dict[str, Any]], replay_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    allowed = {
        str(row.get("record_id") or "")
        for row in replay_rows
        if row.get("replay_status") == "rule_candidate"
    }
    return [
        row
        for row in candidate_rows
        if str(row.get("parent_record_id") or "") in allowed
    ]


def _source_snippet(source_text: str, call_sites: list[dict[str, Any]]) -> str:
    lines = source_text.splitlines()
    start = max(1, min(int(site["line_start"]) for site in call_sites) - 4)
    end = min(
        len(lines),
        max(int(site.get("line_end") or site["line_start"]) for site in call_sites)
        + 4,
    )
    return "\n".join(
        f"{line_number}: {lines[line_number - 1]}"
        for line_number in range(start, end + 1)
    )


def build_audit_packet(
    candidate_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    eligible = [
        row
        for row in candidate_rows
        if row.get("recovery_structure_status") == "eligible"
        and row.get("description_fidelity_passed") is True
    ]
    eligible.sort(
        key=lambda row: (
            str(row.get("normalized_dag_key") or ""),
            str(row.get("source_sha256") or ""),
            str(row.get("parent_record_id") or ""),
        )
    )
    source_ids = [str(row.get("source_sha256") or "") for row in eligible]
    if not all(source_ids) or len(source_ids) != len(set(source_ids)):
        raise ValueError("recovery census must be source-disjoint")

    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eligible:
        clusters[str(row["normalized_dag_key"])].append(row)

    verified: dict[str, tuple[str, str]] = {}
    for source in eligible:
        path = Path(str(source.get("source_path") or ""))
        if not path.is_file():
            raise ValueError(f"source file missing for {source.get('parent_record_id')}")
        if _sha256(path) != source.get("source_sha256"):
            raise ValueError(f"source SHA mismatch for {source.get('parent_record_id')}")
        call_sites = list(source.get("call_sites") or [])
        if not call_sites:
            raise ValueError(f"call sites missing for {source.get('parent_record_id')}")
        verified[str(source["parent_record_id"])] = (
            str(path),
            _source_snippet(path.read_text(encoding="utf-8"), call_sites),
        )

    packet: list[dict[str, Any]] = []
    for position, source in enumerate(eligible, start=1):
        cluster = clusters[str(source["normalized_dag_key"])]
        cluster_position = cluster.index(source)
        comparison = (
            cluster[(cluster_position + 1) % len(cluster)]
            if len(cluster) > 1
            else None
        )
        source_path, source_snippet = verified[str(source["parent_record_id"])]
        row = dict(source)
        row.update(
            {
                "schema": "gis_recommend.qgis_recovery_local_dag_audit.v1",
                "review_position": position,
                "source_path": source_path,
                "source_hash_verified": True,
                "source_snippet": source_snippet,
                "cluster_size": len(cluster),
                "cluster_position": cluster_position + 1,
                "comparison_parent_record_id": (
                    comparison["parent_record_id"] if comparison else ""
                ),
                "comparison_source_path": (
                    verified[str(comparison["parent_record_id"])][0]
                    if comparison
                    else ""
                ),
                "comparison_source_snippet": (
                    verified[str(comparison["parent_record_id"])][1]
                    if comparison
                    else ""
                ),
                "review_status": "pending_human_review",
                "training_admission": "not_granted_recovery_census_audit_only",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
                **{field: "" for field in HUMAN_FIELDS},
            }
        )
        packet.append(row)

    summary = {
        "schema": "gis_recommend.qgis_recovery_local_dag_audit_summary.v1",
        "input_candidates": len(candidate_rows),
        "eligible_units": len(packet),
        "source_disjoint_support": len({row["source_sha256"] for row in packet}),
        "unique_parent_records": len(
            {row["parent_record_id"] for row in packet}
        ),
        "unique_normalized_dags": len(
            {row["normalized_dag_key"] for row in packet}
        ),
        "recovery_rule_counts": dict(
            sorted(
                {
                    rule_id: sum(row["recovery_rule_id"] == rule_id for row in packet)
                    for rule_id in {row["recovery_rule_id"] for row in packet}
                }.items()
            )
        ),
        "population_census": True,
        "rule_support_requirement": 30,
        "rule_training_eligible": False,
        "review_status": "pending_human_review",
        "training_rows_emitted": 0,
        "training_admission": "not_granted_recovery_census_audit_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }
    return packet, summary


def _atomic_write(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding=encoding, newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def write_outputs(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    candidates_path: Path,
    output_dir: Path,
    additional_input_paths: tuple[Path, ...] = (),
) -> dict[str, Path]:
    if not rows:
        raise ValueError("no eligible recovery candidates found")
    jsonl_path = output_dir / "review_packet.jsonl"
    csv_path = output_dir / "review_packet.csv"
    summary_path = output_dir / "review_summary.json"
    hash_path = output_dir / "hash_manifest.json"
    _atomic_write(
        jsonl_path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
    )
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(
        {key: _csv_value(value) for key, value in row.items()} for row in rows
    )
    _atomic_write(csv_path, buffer.getvalue(), encoding="utf-8-sig")
    _atomic_write(
        summary_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    hashes = {
        "schema": "gis_recommend.qgis_recovery_local_dag_audit_hashes.v1",
        "inputs": {
            str(path): _sha256(path)
            for path in (candidates_path, *additional_input_paths)
        },
        "outputs": {
            path.name: _sha256(path)
            for path in (jsonl_path, csv_path, summary_path)
        },
    }
    _atomic_write(
        hash_path,
        json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return {
        "jsonl": jsonl_path,
        "csv": csv_path,
        "summary": summary_path,
        "hash_manifest": hash_path,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--replay-allowlist", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    candidates = _load_jsonl(args.candidates)
    if args.replay_allowlist:
        candidates = filter_candidates_by_replay(
            candidates, _load_jsonl(args.replay_allowlist)
        )
    rows, summary = build_audit_packet(candidates)
    return write_outputs(
        rows,
        summary,
        candidates_path=args.candidates,
        output_dir=args.output_dir,
        additional_input_paths=(args.replay_allowlist,) if args.replay_allowlist else (),
    )


if __name__ == "__main__":
    main()
