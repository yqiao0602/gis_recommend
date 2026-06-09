#!/usr/bin/env python3
"""Build a verified multi-solution registry from human-reviewed candidates.

This script consumes `candidate_review_sheet.csv` from
`build_multisolution_candidates.py`. It only promotes rows explicitly labeled
`equivalent` or `verified_equivalent`; every other row is retained as excluded
review evidence and is not training-eligible.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.config.transformer_config import OUTPUT_DIR  # noqa: E402


SCHEMA_VERSION = "gis_recommend.v4_qg.verified_multiref_registry.v3"
KB_SCHEMA_VERSION = "gis_recommend.v4_qg.verified_equivalence_kb.v3"
DEFAULT_REVIEW_CSV = OUTPUT_DIR / "v4_qg_multisolution_candidates" / "candidate_review_sheet.csv"
DEFAULT_OUTPUT_DIR = OUTPUT_DIR / "v4_qg_multisolution_candidates" / "verified_registry_v3"

EQUIVALENT_LABELS = {"equivalent", "verified_equivalent"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_tokens(value: object) -> list[int]:
    if isinstance(value, list):
        return [int(item) for item in value]
    if isinstance(value, str) and value.strip():
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [int(item) for item in parsed]
    return []


def _with_specials(tokens: Sequence[int]) -> list[int]:
    content = [int(token) for token in tokens if int(token) >= 0]
    return [-3, *content, -4]


def _read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: Sequence[dict], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _variant_id(row: dict) -> str:
    candidate_id = str(row.get("candidate_id", "") or "").strip()
    if not candidate_id:
        candidate_id = f"{row.get('left_workflow_index', '')}_{row.get('right_workflow_index', '')}"
    return f"auto_{candidate_id}"


def _normalized_row(row: dict) -> dict:
    label = str(row.get("human_label", "") or "").strip().lower()
    original_tokens = _with_specials(_parse_tokens(row.get("left_tokens")))
    variant_tokens = _with_specials(_parse_tokens(row.get("right_tokens")))
    return {
        "variant_id": _variant_id(row),
        "review_label": label,
        "review_source": "auto_candidate_human_review",
        "task_type": str(row.get("task_type", "") or ""),
        "task_name": str(row.get("left_task_name", "") or ""),
        "task_description": str(row.get("right_task_name", "") or ""),
        "source_script_id": "",
        "equivalence_family": str(row.get("review_bucket", "") or "auto_mined_pair"),
        "risk_level": "human_review_required" if label not in EQUIVALENT_LABELS else "reviewed",
        "original_tokens": original_tokens,
        "variant_tokens": variant_tokens,
        "review_flags": ";".join(
            part
            for part in (
                f"set_f1={row.get('set_f1', '')}",
                f"lcs_ratio={row.get('lcs_ratio', '')}",
                f"length_delta={row.get('length_delta', '')}",
                f"text_jaccard={row.get('text_jaccard', '')}",
            )
            if not part.endswith("=")
        ),
        "reviewer_notes": str(row.get("review_notes", "") or ""),
        "is_training_eligible": label in EQUIVALENT_LABELS,
    }


def _kb_row(row: dict) -> dict:
    return {
        "variant_id": row["variant_id"],
        "task_type": row["task_type"],
        "task_name": row["task_name"],
        "source_script_id": row["source_script_id"],
        "review_source": row["review_source"],
        "review_label": row["review_label"],
        "equivalence_family": row["equivalence_family"],
        "risk_level": row["risk_level"],
        "swapped_pair": "",
        "swapped_pair_names": "",
        "original_tokens": json.dumps(row["original_tokens"], ensure_ascii=False),
        "variant_tokens": json.dumps(row["variant_tokens"], ensure_ascii=False),
        "source_operator_window": "",
        "conditional_constraints": "human_confirmed_from_auto_mined_same_task_pair",
        "hidden_dependency": "",
        "review_flags": row["review_flags"],
        "reviewer_notes": row["reviewer_notes"],
    }


def build_registry_from_rows(rows: Sequence[dict]) -> tuple[dict, list[dict]]:
    normalized = [_normalized_row(row) for row in rows]
    deduped = {row["variant_id"]: row for row in normalized}
    ordered = [deduped[key] for key in sorted(deduped)]
    equivalent = [row for row in ordered if row["is_training_eligible"]]
    excluded = [row for row in ordered if not row["is_training_eligible"]]

    grouped: dict[str, dict] = {}
    for row in equivalent:
        key = json.dumps(
            {
                "task_type": row["task_type"],
                "task_name": row["task_name"],
                "task_description": row["task_description"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        entry = grouped.setdefault(
            key,
            {
                "task_type": row["task_type"],
                "task_name": row["task_name"],
                "task_description": row["task_description"],
                "references": [],
                "source_variant_ids": [],
                "source_script_ids": [],
                "equivalence_families": [],
                "risk_levels": [],
                "review_sources": [],
                "review_notes": [],
            },
        )
        for tokens in (row["original_tokens"], row["variant_tokens"]):
            if tokens and tokens not in entry["references"]:
                entry["references"].append(tokens)
        entry["source_variant_ids"].append(row["variant_id"])
        for field, target in (
            ("equivalence_family", "equivalence_families"),
            ("risk_level", "risk_levels"),
            ("review_source", "review_sources"),
        ):
            value = row[field]
            if value and value not in entry[target]:
                entry[target].append(value)
        if row["reviewer_notes"]:
            entry["review_notes"].append(f"{row['variant_id']}: {row['reviewer_notes']}")

    entries = list(grouped.values())
    entries.sort(key=lambda item: (item["task_type"], item["task_name"], item["task_description"]))
    label_counts = Counter(row["review_label"] or "blank" for row in ordered)
    family_counts = Counter(row["equivalence_family"] or "unknown" for row in equivalent)
    review_source_counts = Counter(row["review_source"] or "unknown" for row in equivalent)
    kb_rows = [_kb_row(row) for row in equivalent]
    return (
        {
            "schema_version": SCHEMA_VERSION,
            "created_at": _now(),
            "review_policy": "human_equivalent_only_from_auto_candidates",
            "training_eligible": True,
            "deduplication_key": "variant_id",
            "input_review_row_count": len(rows),
            "unique_reviewed_variant_count": len(ordered),
            "reviewed_equivalence_group_count": len(entries),
            "reviewed_equivalent_variant_count": len(equivalent),
            "excluded_variant_count": len(excluded),
            "review_label_counts": dict(label_counts),
            "equivalence_family_counts": dict(family_counts),
            "review_source_counts": dict(review_source_counts),
            "excluded_variants": [
                {
                    "variant_id": row["variant_id"],
                    "review_label": row["review_label"],
                    "equivalence_family": row["equivalence_family"],
                    "risk_level": row["risk_level"],
                    "reviewer_notes": row["reviewer_notes"],
                }
                for row in excluded
            ],
            "entries": entries,
        },
        kb_rows,
    )


def _write_markdown(path: Path, payload: dict) -> None:
    lines = [
        "# Verified Multi-Solution Registry V3",
        "",
        "This registry is built only from human-reviewed auto-mined candidates.",
        "Only rows labeled `equivalent` or `verified_equivalent` are training-eligible.",
        "",
        f"- Unique reviewed variants: {payload['unique_reviewed_variant_count']}",
        f"- Equivalent variants: {payload['reviewed_equivalent_variant_count']}",
        f"- Task groups: {payload['reviewed_equivalence_group_count']}",
        f"- Excluded variants: {payload['excluded_variant_count']}",
        f"- Label counts: {json.dumps(payload['review_label_counts'], ensure_ascii=False, sort_keys=True)}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-csv", type=Path, default=DEFAULT_REVIEW_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict:
    args = parse_args(argv)
    rows = _read_csv(args.review_csv)
    registry, kb_rows = build_registry_from_rows(rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.output_dir / "verified_multi_reference_registry_v3.json", registry)
    _write_json(
        args.output_dir / "verified_equivalence_kb_v3.json",
        {
            "schema_version": KB_SCHEMA_VERSION,
            "created_at": _now(),
            "row_count": len(kb_rows),
            "rows": kb_rows,
        },
    )
    _write_csv(
        args.output_dir / "verified_equivalence_kb_v3.csv",
        kb_rows,
        [
            "variant_id",
            "task_type",
            "task_name",
            "source_script_id",
            "review_source",
            "review_label",
            "equivalence_family",
            "risk_level",
            "swapped_pair",
            "swapped_pair_names",
            "original_tokens",
            "variant_tokens",
            "source_operator_window",
            "conditional_constraints",
            "hidden_dependency",
            "review_flags",
            "reviewer_notes",
        ],
    )
    _write_markdown(args.output_dir / "verified_multi_reference_registry_v3_summary.md", registry)
    print(
        json.dumps(
            {
                "unique_reviewed_variant_count": registry["unique_reviewed_variant_count"],
                "equivalent_variants": registry["reviewed_equivalent_variant_count"],
                "task_groups": registry["reviewed_equivalence_group_count"],
                "excluded_variants": registry["excluded_variant_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return registry


if __name__ == "__main__":
    main()
