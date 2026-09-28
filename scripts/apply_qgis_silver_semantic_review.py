#!/usr/bin/env python3
"""Freeze the independent semantic review for the bounded QGIS Silver pilot.

The source review packet and its original 21-row Silver export remain
immutable.  This script writes a separate review ledger, explicit revocation
manifest, and curated experimental train-only packages.  It never modifies
the 508-row authority, validation/test splits, benchmarks, or checkpoints.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

PACKET_SCHEMA = "gis_recommend.qgis_silver_semantic_review_packet.v1"
SILVER_SCHEMA = "gis_recommend.qgis_silver_train_only.v1"
REVIEW_SCHEMA = "gis_recommend.qgis_silver_independent_semantic_review.v1"
GOLD_ADMISSION = "granted_independent_semantic_reviewed_gold_pilot_v1"
SILVER_ADMISSION = "retained_independent_semantic_reviewed_silver_pilot_v1"


def verdicts(
    execution: str, intent: str, chain: str, l3: str, decision: str, notes: str
) -> dict[str, str]:
    return {
        "source_execution_logic_verdict": execution,
        "task_source_intent_verdict": intent,
        "operator_chain_verdict": chain,
        "l3_alignment_verdict": l3,
        "semantic_review_decision": decision,
        "semantic_review_notes": notes,
    }


# This is an explicit source-row adjudication, not a heuristic promotion rule.
REVIEWS: dict[str, dict[str, str]] = {
    "010ff49e96ce3688497cc143": verdicts(
        "pass", "pass", "pass", "pass", "gold",
        "Function accepts input and overlay, invokes intersection, and returns the verified output.",
    ),
    "01bacc5af067b04a1b95b7ce": verdicts(
        "pass", "pass", "pass", "pass", "gold",
        "Reprojected grid feeds clip; three field calculations consume predecessor outputs in order.",
    ),
    "02b86d787966cef28bfa6a2a": verdicts(
        "pass", "not_gold", "pass", "pass", "retain_silver",
        "Rasterize feeds slope, aspect, and ruggedness as sibling derivatives; the generic linear wording is not Gold-quality.",
    ),
    "0a585631aa5d6a9842c40762": verdicts(
        "pass", "pass", "pass", "pass", "gold",
        "The guarded supplied layer is passed to createspatialindex; task and L3 describe the same operation.",
    ),
    "0ff337f7c99eb748e8db8ccf": verdicts(
        "pass", "not_gold", "pass", "pass", "retain_silver",
        "Select-by-location is source-supported, but its in-place selection state and external writer output are omitted from the generic task text.",
    ),
    "1032cd430cf2b8cdc0c0bac5": verdicts(
        "pass", "pass", "pass", "pass", "gold",
        "The source explicitly samples DEM values at lake-layer points with the recorded prefix and output.",
    ),
    "152350be2ffbb094bfece005": verdicts(
        "pass", "not_gold", "pass", "pass", "retain_silver",
        "The polygonize/save/select workflow is source-supported, but GUI active-layer and selection-state transitions make the generic linear task text insufficient for Gold.",
    ),
    "1546da932140e6c163d704c9": verdicts(
        "pass", "pass", "pass", "pass", "gold",
        "The helper accepts input and extent, clips geometry, and validates the returned extraction output.",
    ),
    "2dcaba6bf38eb869d9aa96b8": verdicts(
        "pass", "pass", "pass", "pass", "gold",
        "Zonal statistics uses the recorded raster, grid, and majority statistic before reading the created field.",
    ),
    "3d2310d2bfb7ec50fcd15b19": verdicts(
        "pass", "pass", "pass", "fail", "reject",
        "The Boolean raster expression uses comparisons and AND, but qgis:rastercalculator is mapped to Arithmetic & Math instead of Logical & Comparison.",
    ),
    "49ecf916517b7954a88367b3": verdicts(
        "pass", "pass", "pass", "pass", "gold",
        "Raster sampling output is the input to the recorded spatial attribute join.",
    ),
    "61c0404b17fc3b0155639c9e": verdicts(
        "pass", "pass", "pass", "pass", "gold",
        "The helper documents and supplies INPUT, INTERSECT, PREDICATE, and output for extract-by-location.",
    ),
    "632fea18482f1643b8fd2131": verdicts(
        "fail", "pass", "pass", "pass", "reject",
        "Rasterize writes to parameters['OUTPUT'], the declared vector point destination, while the declared RASTER_OUTPUT is unused; do not repair the source output contract.",
    ),
    "73cfb0be71a14e6034dbe6ae": verdicts(
        "pass", "pass", "pass", "pass", "gold",
        "The invoked clipping helper receives municipalities and the 5 km buffer and returns its clipped output.",
    ),
    "7cdec0e669e3cdd2164747e9": verdicts(
        "pass", "pass", "pass", "pass", "gold",
        "The QGIS example feeds buffer output into rasterize and declares distinct vector and raster outputs.",
    ),
    "91d64aaa5af55984398b13b1": verdicts(
        "pass", "pass", "pass", "pass", "gold",
        "The helper builds a two-layer merge list and writes the requested merged-vector output.",
    ),
    "9bf4101477032f67dd01d3bd": verdicts(
        "pass", "pass", "pass", "pass", "gold",
        "The direct buffer call and all recorded buffer parameters agree with the task description.",
    ),
    "a89a011bd6ccb398728d700c": verdicts(
        "pass", "pass", "pass", "pass", "gold",
        "The direct union call explicitly supplies building input, walkway overlay, and output path.",
    ),
    "af12a73ac38d9fa984274671": verdicts(
        "pass", "pass", "pass", "pass", "gold",
        "The documented expression template supplies its expression and output to extract-by-expression.",
    ),
    "be32243bb3e49a08a8272451": verdicts(
        "pass", "not_gold", "pass", "pass", "retain_silver",
        "The processing calls exist, but selection state, active-layer transitions, and the non-linear dissolve provenance are hidden by the generic linear description.",
    ),
    "d7f271dbf83a5abfd79db301": verdicts(
        "pass", "pass", "pass", "pass", "gold",
        "The initialized QGIS script directly transforms the stated DEM into a slope raster with Z_FACTOR=1.",
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def apply_review(
    packet: list[dict[str, Any]], silver_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if len(packet) != len(REVIEWS) or {row.get("record_id") for row in packet} != set(REVIEWS):
        raise ValueError("review packet identity does not exactly match the frozen 21-row adjudication")
    if len(silver_rows) != len(packet) or {row.get("record_id") for row in silver_rows} != set(REVIEWS):
        raise ValueError("Silver export identity does not exactly match the review packet")
    silver_by_id = {str(row["record_id"]): row for row in silver_rows}
    reviewed: list[dict[str, Any]] = []
    gold: list[dict[str, Any]] = []
    retained: list[dict[str, Any]] = []
    revoked: list[dict[str, Any]] = []
    for row in packet:
        record_id = str(row["record_id"])
        original = silver_by_id[record_id]
        if row.get("schema") != PACKET_SCHEMA or original.get("schema_version") != SILVER_SCHEMA:
            raise ValueError(f"unexpected schema: {record_id}")
        if row.get("source_sha256") != original.get("source_sha256"):
            raise ValueError(f"source identity mismatch: {record_id}")
        adjudication = REVIEWS[record_id]
        decision = adjudication["semantic_review_decision"]
        reviewed_row = {
            **row,
            **adjudication,
            "schema": REVIEW_SCHEMA,
            "semantic_review_version": "qgis_silver_independent_semantic_review_v1",
            "reviewer_mode": "independent_full_source_review",
            "source_verification": "verified_sha256",
            "production_merge": "not_granted",
            "validation_eligible": False,
            "test_eligible": False,
        }
        if decision == "gold":
            reviewed_row.update({"gold_admission": GOLD_ADMISSION, "training_admission": "unchanged_granted_train_only_qgis_silver_pilot_v1"})
            gold.append({
                **original,
                "semantic_review_decision": "gold",
                "semantic_review_version": "qgis_silver_independent_semantic_review_v1",
                "gold_admission": GOLD_ADMISSION,
                "production_merge": "not_granted",
                "validation_eligible": False,
                "test_eligible": False,
                "_training_quality": {"tier": "source_verified_processing_gold_pilot", "sample_weight": 1.0, "gold_status": "granted_independent_semantic_review"},
            })
        elif decision == "retain_silver":
            reviewed_row.update({"gold_admission": "not_granted_semantic_review_not_gold", "training_admission": SILVER_ADMISSION})
            retained.append({
                **original,
                "semantic_review_decision": "retain_silver",
                "semantic_review_version": "qgis_silver_independent_semantic_review_v1",
                "gold_admission": "not_granted_semantic_review_not_gold",
                "training_admission": SILVER_ADMISSION,
                "production_merge": "not_granted",
                "validation_eligible": False,
                "test_eligible": False,
            })
        elif decision == "reject":
            reviewed_row.update({"gold_admission": "not_granted_semantic_review_reject", "training_admission": "revoked_semantic_review_reject"})
            revoked.append({
                "record_id": record_id,
                "sample_id": original["sample_id"],
                "source_sha256": original["source_sha256"],
                "prior_training_admission": original["training_admission"],
                "revocation_reason": adjudication["semantic_review_notes"],
                "training_admission": "revoked_semantic_review_reject",
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            })
        else:
            raise ValueError(f"unsupported review decision: {record_id}")
        reviewed.append(reviewed_row)
    decisions = Counter(row["semantic_review_decision"] for row in reviewed)
    summary = {
        "schema": f"{REVIEW_SCHEMA}.summary",
        "input_rows": len(reviewed),
        "source_sha256_verified": len(reviewed),
        "gold_rows": len(gold),
        "retained_silver_rows": len(retained),
        "rejected_rows": len(revoked),
        "curated_train_only_rows": len(gold) + len(retained),
        "decision_counts": dict(sorted(decisions.items())),
        "formal_authority_modified": False,
        "validation_eligible": False,
        "test_eligible": False,
        "training_run": False,
        "checkpoint_written": False,
    }
    return reviewed, gold, retained, revoked, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--silver", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    reviewed, gold, retained, revoked, summary = apply_review(read_jsonl(args.packet), read_jsonl(args.silver))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "reviewed_semantic_ledger_v1.jsonl": reviewed,
        "qgis_gold_reviewed_train_only_v1.jsonl": gold,
        "qgis_retained_silver_train_only_v1.jsonl": retained,
        "revoked_silver_rows_v1.jsonl": revoked,
        "qgis_curated_gold_silver_train_only_v1.jsonl": [*gold, *retained],
    }
    written: list[Path] = []
    for name, rows in artifacts.items():
        path = args.output_dir / name
        write_jsonl(path, rows)
        written.append(path)
    summary_path = args.output_dir / "summary_v1.json"
    write_json(summary_path, summary)
    written.append(summary_path)
    report = [
        "# QGIS Silver Independent Semantic Review v1",
        "",
        "The original 21-row Silver export is immutable. This review produces a separate curated experimental package and never changes the 508-row formal authority, validation/test, benchmark, or checkpoints.",
        "",
        "| decision | rows | train-only treatment |",
        "|---|---:|---|",
        f"| Gold | {summary['gold_rows']} | isolated reviewed train-only, weight 1.0 |",
        f"| Retained Silver | {summary['retained_silver_rows']} | isolated reviewed train-only, weight 0.7 |",
        f"| Reject | {summary['rejected_rows']} | explicit revocation, excluded from curated package |",
        f"| Curated Gold + Silver | {summary['curated_train_only_rows']} | train-only experimental package |",
        "",
        "## Rejected Rows",
        "",
        "| record_id | reason |",
        "|---|---|",
    ]
    for row in revoked:
        report.append(f"| `{row['record_id']}` | {row['revocation_reason']} |")
    report.extend([
        "",
        "## Constraints",
        "",
        "No model training was run. The Gold package is not a formal-authority merge and remains excluded from validation, test, benchmark, and production checkpoint workflows.",
    ])
    report_path = args.output_dir / "report_v1.md"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    written.append(report_path)
    write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                args.packet.name: {"sha256": sha256(args.packet), "bytes": args.packet.stat().st_size},
                args.silver.name: {"sha256": sha256(args.silver), "bytes": args.silver.stat().st_size},
            },
            "artifacts": {path.name: {"sha256": sha256(path), "bytes": path.stat().st_size} for path in written},
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
