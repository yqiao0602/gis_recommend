#!/usr/bin/env python3
"""Persist source-backed proposal-only decisions for the 40-row rule audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REVIEW = ROOT / "docs/reports/qgis_recovery_split_calibration_v1/review_40_v1.jsonl"
DEFAULT_OUTPUT_DIR = DEFAULT_REVIEW.parent / "proposals_v1"


# position: (proposal, recoverable boundary, principal reason)
PROPOSALS: dict[int, tuple[str, str, str]] = {
    1: ("defer_dynamic", "per-respondent repeated DAG", "dynamic outer loop and an omitted GRASS call"),
    2: ("split_local_units", "conditional reproject/centroid paths", "mutually optional branches and low-level main logic"),
    3: ("defer_dynamic", "recursive join chain then save", "runtime layer count determines chain cardinality"),
    4: ("split_local_units", "two extracts fan into difference then singleparts", "fixed local unit repeats in nested loops"),
    5: ("split_local_units", "extract-by-attribute then clip", "fixed local unit repeats per region"),
    6: ("defer_helper_expansion", "merge then buffer suffix", "external helper produces core geometry and distance semantics"),
    7: ("recoverable_rule_candidate", "seven-step linear Processing DAG", "parameter-dict and result-subscript def-use can recover all edges"),
    8: ("split_local_units", "extract-by-attribute then extract-by-location", "low-level intersection and aggregation remain outside the local unit"),
    9: ("defer_dynamic", "repeated warps fan into merge", "runtime file count and path-based fan-in"),
    10: ("split_local_units", "guarded reproject then buffer", "geometry/CRS branches are mutually optional"),
    11: ("recoverable_rule_candidate", "fix-geometries then zonal statistics", "result-subscript alias propagation restores the edge"),
    12: ("split_local_units", "two independent extract/join branches", "shared-looking paths do not make a four-step chain"),
    13: ("recoverable_rule_candidate", "three preprocessing branches fan into intersections and field calculations", "dictionary-key SSA and multi-input DAG recovery"),
    14: ("split_local_units", "shared NDVI branch plus separate NDVI/LST outputs", "backward slicing is required and style calls are sidecars"),
    15: ("recoverable_rule_candidate", "buffer, clip, difference, then merge", "normalized static paths restore side-effect dependencies"),
    16: ("recoverable_rule_candidate", "reclassify then mask clip", "local direct-variable edge and deterministic file sink"),
    17: ("split_local_units", "two independent multipart-to-singlepart calls", "no producer-consumer relationship"),
    18: ("split_local_units", "maximum executable clip/extract/buffer prefixes", "undefined misspelled result blocks the downstream graph"),
    19: ("recoverable_rule_candidate", "fix-geometries then zonal statistics", "same alias-propagation family as position 11"),
    20: ("exclude_current_candidate", "none", "unbound polygonize output and raster input passed to vector buffer"),
    21: ("split_local_units", "two-intersection stable suffix", "conditional helper reprojects have multiplicity and optionality"),
    22: ("recoverable_repeat_template_candidate", "raster calculation map then VRT fan-in", "repeat cardinality must remain metadata"),
    23: ("exclude_current_candidate", "none", "configuration-driven action dispatcher can reorder and repeat algorithms"),
    24: ("split_local_units", "merge then clip stable suffix", "conditional CRS helpers and a wrong source variable prevent full recovery"),
    25: ("exclude_current_candidate", "none", "vector and raster clips are mutually exclusive type branches"),
    26: ("split_local_units", "one or two reclassify/raster-calculate branches then fan-in", "cross-file helper expansion and branch recovery required"),
    27: ("exclude_current_candidate", "none", "independent nested helpers share no entrypoint data flow"),
    28: ("recoverable_repeat_template_candidate", "fix-geometries then clip", "fixed helper chain repeats per WFS layer"),
    29: ("split_local_units", "multipolygon reproject then singleparts", "backward slice corrects reversed candidate order"),
    30: ("defer_helper_expansion", "watershed, fill-nodata, then raster calculation", "candidate omits the upstream GRASS call and reverses order"),
    31: ("split_local_units", "two clip helpers and one reproject helper", "three independent lexical scopes"),
    32: ("split_local_units", "difference and hillshade single-step units", "independent functions with no data flow"),
    33: ("split_local_units", "fix-geometries then reproject plus independent single steps", "multiple independent helper scopes"),
    34: ("split_local_units", "five independent reprojection helpers", "distant functions do not form one workflow"),
    35: ("split_local_units", "warp then fill-nodata plus rasterize and clip units", "three independent helper scopes"),
    36: ("split_local_units", "two independent clip units", "distinct methods and outputs"),
    37: ("split_local_units", "buffer; area/select; ID field; X/Y field units", "four helper workflows were concatenated"),
    38: ("split_local_units", "reproject then spatial join plus independent multi-intersection", "low-level attribute mutation remains a sidecar"),
    39: ("split_local_units", "five independent raster helper units", "function definitions are not runtime chaining evidence"),
    40: ("split_local_units", "buffer, location extract, and reproject helpers", "duplicate calls are mutually exclusive output branches"),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_proposals(review_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_position = {int(row["review_position"]): row for row in review_rows}
    if set(by_position) != set(PROPOSALS) or len(review_rows) != 40:
        raise ValueError("review packet must contain exactly positions 1..40")
    rows: list[dict[str, Any]] = []
    for position in range(1, 41):
        review = by_position[position]
        if review.get("source_execution_decision") or review.get("final_rule_decision"):
            raise ValueError(f"raw review human fields must remain blank: {position}")
        proposal, boundary, reason = PROPOSALS[position]
        rows.append(
            {
                "schema": "gis_recommend.qgis_recovery_split_rule_proposal.v1",
                "review_position": position,
                "record_id": review["record_id"],
                "source_sha256": review["source_sha256"],
                "signature_hash": review["signature_hash"],
                "rule_id": review["rule_id"],
                "operator_ids": review["operator_ids"],
                "mapped_l3_chain": review["mapped_l3_chain"],
                "proposal": proposal,
                "recoverable_boundary": boundary,
                "proposal_reason": reason,
                "proposal_source": "source_backed_agent_review_not_human_adjudication",
                "human_adjudication": "not_granted",
                "training_admission": "not_granted_proposal_only",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
    counts = Counter(row["proposal"] for row in rows)
    summary = {
        "schema": "gis_recommend.qgis_recovery_split_rule_proposal_summary.v1",
        "rows": len(rows),
        "proposal_counts": dict(sorted(counts.items())),
        "rules_covered": dict(sorted(Counter(row["rule_id"] for row in rows).items())),
        "unique_sources": len({row["source_sha256"] for row in rows}),
        "unique_signatures": len({row["signature_hash"] for row in rows}),
        "decision": {
            "human_adjudication": "not_granted",
            "training_rows_emitted": 0,
            "next_gate": "confirm proposals then implement rule families and expand support to 30",
        },
    }
    return rows, summary


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def write_outputs(
    rows: list[dict[str, Any]], summary: dict[str, Any], *, review_path: Path, output_dir: Path
) -> dict[str, Path]:
    jsonl_path = output_dir / "rule_proposals_40_v1.jsonl"
    summary_path = output_dir / "summary_v1.json"
    report_path = output_dir / "report_v1.md"
    hash_path = output_dir / "hash_ledger_v1.json"
    _atomic_write(
        jsonl_path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        ),
    )
    _atomic_write(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    counts = summary["proposal_counts"]
    report = (
        "# QGIS recovery/split rule proposals v1\n\n"
        "Proposal-only source review; no human adjudication or training admission is granted.\n\n"
        + "\n".join(f"- `{name}`: {count}" for name, count in counts.items())
        + "\n\nNext: confirm proposals, implement bounded rule families, and audit at support >= 30 before any batch admission.\n"
    )
    _atomic_write(report_path, report)
    hashes = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {review_path.name: {"path": str(review_path), "sha256": _sha256(review_path)}},
        "artifacts": {
            path.name: {"path": str(path), "sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in (jsonl_path, summary_path, report_path)
        },
    }
    _atomic_write(hash_path, json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {"jsonl": jsonl_path, "summary": summary_path, "report": report_path, "hash_ledger": hash_path}


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    rows, summary = build_proposals(_load_jsonl(args.review))
    return write_outputs(rows, summary, review_path=args.review, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
