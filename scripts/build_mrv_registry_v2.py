#!/usr/bin/env python3
"""Build a consolidated verified MRV registry and equivalence KB.

This script only consolidates already-reviewed equivalence rows. It does not
train, mutate checkpoints, or overwrite the original manual registry.
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


SCHEMA_VERSION = "gis_recommend.v4_qg.verified_multiref_registry.v2"
KB_SCHEMA_VERSION = "gis_recommend.v4_qg.verified_equivalence_kb.v2"
DEFAULT_MANUAL_REVIEW = OUTPUT_DIR / "v4_qg_multiref_validation" / "equivalence_review_packet.csv"
DEFAULT_EXPANSION_REVIEW = (
    OUTPUT_DIR
    / "v4_qg_multiref_validation_expansion_500"
    / "equivalence_review_packet_ai_review.csv"
)
DEFAULT_OUTPUT_DIR = OUTPUT_DIR / "v4_qg_multiref_validation"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_tokens(value: object) -> list[int]:
    if isinstance(value, list):
        return [int(item) for item in value]
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [int(item) for item in parsed]
    return []


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
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _normalize_manual_row(row: dict) -> dict:
    semantic_risk = _normalize_risk_level(row.get("semantic_risk", ""))
    return {
        "variant_id": row.get("variant_id", ""),
        "review_label": row.get("human_label", "").strip(),
        "review_source": "manual_initial_review",
        "task_type": row.get("task_type", ""),
        "task_family": row.get("task_family", ""),
        "task_name": row.get("task_name", ""),
        "task_description": row.get("task_description", ""),
        "source_script_id": row.get("source_script_id", ""),
        "swap_position": row.get("swap_position", ""),
        "swapped_pair": row.get("swapped_pair", ""),
        "swapped_pair_names": row.get("swapped_pair_names", ""),
        "equivalence_family": row.get("equivalence_family", "") or _infer_family_from_flags(row),
        "risk_level": semantic_risk or _infer_risk_from_flags(row) or "unknown",
        "original_tokens": row.get("original_tokens", ""),
        "variant_tokens": row.get("variant_tokens", ""),
        "original_l3_names": row.get("original_l3_names", ""),
        "variant_l3_names": row.get("variant_l3_names", ""),
        "source_operator_window": row.get("source_operator_window", ""),
        "conditional_constraints": row.get("conditional_constraints", ""),
        "hidden_dependency": row.get("hidden_dependency", ""),
        "reviewer_notes": row.get("reviewer_notes") or row.get("human_notes", ""),
        "review_flags": row.get("review_flags", ""),
        "is_training_eligible": row.get("human_label", "").strip() == "equivalent",
    }


def _normalize_expansion_row(row: dict) -> dict:
    return {
        "variant_id": row.get("variant_id", ""),
        "review_label": row.get("assistant_review_label", "").strip(),
        "review_source": "expansion_ai_review_user_confirmed",
        "task_type": row.get("task_type", ""),
        "task_family": row.get("task_family", ""),
        "task_name": row.get("task_name", ""),
        "task_description": "",
        "source_script_id": row.get("source_script_id", ""),
        "swap_position": row.get("swap_position", ""),
        "swapped_pair": row.get("swapped_pair", ""),
        "swapped_pair_names": row.get("swapped_pair_names", ""),
        "equivalence_family": row.get("equivalence_family", ""),
        "risk_level": _normalize_risk_level(row.get("risk_level", "")) or "unknown",
        "original_tokens": row.get("original_tokens", ""),
        "variant_tokens": row.get("variant_tokens", ""),
        "original_l3_names": "",
        "variant_l3_names": "",
        "source_operator_window": row.get("source_operator_window", ""),
        "conditional_constraints": row.get("conditional_constraints", ""),
        "hidden_dependency": row.get("hidden_dependency", ""),
        "reviewer_notes": row.get("reviewer_notes", ""),
        "review_flags": _drift_flags(row),
        "is_training_eligible": row.get("assistant_review_label", "").strip() == "equivalent",
    }


def _infer_family_from_flags(row: dict) -> str:
    flags = row.get("review_flags", "")
    if "object_chain" in flags or "filtermetadata_after_image_select" in flags:
        return "object_chain_break_filtermetadata_after_image_select"
    if "filter_commute" in flags:
        return "filter_filter"
    if "select_clip" in flags:
        return "select_clip"
    if "select_date_commute" in flags:
        return "select_filter"
    if "metadata_select" in flags:
        return "select_filter"
    if "clip_arithmetic" in flags:
        return "clip_arithmetic"
    if "mask" in flags or "threshold" in flags:
        return "mask_threshold_or_logic"
    return ""


def _infer_risk_from_flags(row: dict) -> str:
    flags = row.get("review_flags", "")
    if "object_chain" in flags or "filtermetadata_after_image_select" in flags:
        return "high"
    if "clip_arithmetic" in flags:
        return "medium_high"
    if "select_clip" in flags or "metadata_select" in flags:
        return "medium"
    if "mask_drift" in flags or "threshold_drift" in flags or "classification_drift" in flags:
        return "high"
    if "filter_commute" in flags or "select_date_commute" in flags:
        return "low"
    return "unknown"


def _normalize_risk_level(value: object) -> str:
    risk = str(value or "").strip()
    if not risk:
        return ""
    aliases = {
        "medium-high": "medium_high",
        "medium high": "medium_high",
        "medium_high": "medium_high",
        "low": "low",
        "medium": "medium",
        "high": "high",
        "unknown": "unknown",
    }
    return aliases.get(risk.lower(), risk)


def _drift_flags(row: dict) -> str:
    flags = []
    for key in ("crs_drift", "mask_drift", "nodata_drift", "threshold_drift", "aggregation_drift", "temporal_drift"):
        if row.get(key) == "yes":
            flags.append(key)
    return ";".join(flags)


def load_review_rows(manual_review: Path, expansion_review: Path | None) -> list[dict]:
    rows = [_normalize_manual_row(row) for row in _read_csv(manual_review)]
    if expansion_review and expansion_review.exists():
        rows.extend(_normalize_expansion_row(row) for row in _read_csv(expansion_review))
    return rows


def _review_source_rank(source: str) -> int:
    if source == "manual_initial_review":
        return 0
    return 1


def deduplicate_rows(rows: Sequence[dict]) -> list[dict]:
    """Deduplicate by variant_id, preferring manual rows over expansion rows."""
    chosen: dict[str, dict] = {}
    for row in rows:
        variant_id = row.get("variant_id", "")
        if not variant_id:
            continue
        current = chosen.get(variant_id)
        if current is None or _review_source_rank(row.get("review_source", "")) < _review_source_rank(current.get("review_source", "")):
            chosen[variant_id] = dict(row)
    return [chosen[key] for key in sorted(chosen)]


def build_registry_payload(rows: Sequence[dict]) -> tuple[dict, list[dict]]:
    deduped = deduplicate_rows(rows)
    label_counts = Counter(row.get("review_label", "") for row in deduped)
    equivalent = [row for row in deduped if row.get("review_label") == "equivalent"]
    excluded = [row for row in deduped if row.get("review_label") != "equivalent"]

    grouped: dict[str, dict] = {}
    kb_rows: list[dict] = []
    family_counts: Counter[str] = Counter()
    risk_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    family_aliases: Counter[str] = Counter()

    for row in equivalent:
        original_tokens = parse_tokens(row.get("original_tokens"))
        variant_tokens = parse_tokens(row.get("variant_tokens"))
        key = json.dumps(
            {
                "task_type": row.get("task_type", ""),
                "task_name": row.get("task_name", ""),
                "task_description": row.get("task_description", ""),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        entry = grouped.setdefault(
            key,
            {
                "task_type": row.get("task_type", ""),
                "task_name": row.get("task_name", ""),
                "task_description": row.get("task_description", ""),
                "references": [],
                "source_variant_ids": [],
                "source_script_ids": [],
                "equivalence_families": [],
                "risk_levels": [],
                "review_sources": [],
                "review_notes": [],
            },
        )
        for tokens in (original_tokens, variant_tokens):
            if tokens and tokens not in entry["references"]:
                entry["references"].append(tokens)
        if row.get("variant_id") not in entry["source_variant_ids"]:
            entry["source_variant_ids"].append(row.get("variant_id", ""))
        if row.get("source_script_id") and row.get("source_script_id") not in entry["source_script_ids"]:
            entry["source_script_ids"].append(row.get("source_script_id", ""))
        for field, target in (
            ("equivalence_family", "equivalence_families"),
            ("risk_level", "risk_levels"),
            ("review_source", "review_sources"),
        ):
            value = row.get(field, "")
            if value and value not in entry[target]:
                entry[target].append(value)
        family_alias = _family_alias(row.get("equivalence_family", ""))
        if family_alias and family_alias not in entry["equivalence_families"]:
            entry["equivalence_families"].append(family_alias)
        if family_alias:
            family_aliases[family_alias] += 1
        note = row.get("reviewer_notes", "")
        if note:
            entry["review_notes"].append(f"{row.get('variant_id')}: {note}")

        family_counts[family_alias or row.get("equivalence_family", "") or "unknown"] += 1
        risk_counts[row.get("risk_level", "") or "unknown"] += 1
        source_counts[row.get("review_source", "") or "unknown"] += 1
        kb_rows.append(_kb_row(row, original_tokens, variant_tokens))

    entries = list(grouped.values())
    entries.sort(key=lambda item: (item["task_type"], item["task_name"]))
    kb_rows.sort(key=lambda item: item["variant_id"])
    payload = {
        "schema_version": SCHEMA_VERSION,
        "created_at": now(),
        "review_policy": "manual_or_user_confirmed_equivalent_only",
        "training_eligible": True,
        "deduplication_key": "variant_id",
        "input_review_row_count": len(rows),
        "unique_reviewed_variant_count": len(deduped),
        "reviewed_equivalence_group_count": len(entries),
        "reviewed_equivalent_variant_count": len(equivalent),
        "excluded_variant_count": len(excluded),
        "review_label_counts": dict(label_counts),
        "equivalence_family_counts": dict(family_counts),
        "equivalence_family_alias_counts": dict(family_aliases),
        "risk_level_counts": dict(risk_counts),
        "review_source_counts": dict(source_counts),
        "excluded_variants": [
            {
                "variant_id": row.get("variant_id", ""),
                "review_label": row.get("review_label", ""),
                "equivalence_family": row.get("equivalence_family", ""),
                "risk_level": row.get("risk_level", ""),
                "reviewer_notes": row.get("reviewer_notes", ""),
            }
            for row in excluded
        ],
        "entries": entries,
    }
    return payload, kb_rows


def _kb_row(row: dict, original_tokens: list[int], variant_tokens: list[int]) -> dict:
    return {
        "variant_id": row.get("variant_id", ""),
        "task_type": row.get("task_type", ""),
        "task_name": row.get("task_name", ""),
        "source_script_id": row.get("source_script_id", ""),
        "review_source": row.get("review_source", ""),
        "review_label": row.get("review_label", ""),
        "equivalence_family": row.get("equivalence_family", ""),
        "risk_level": row.get("risk_level", ""),
        "swapped_pair": row.get("swapped_pair", ""),
        "swapped_pair_names": row.get("swapped_pair_names", ""),
        "original_tokens": json.dumps(original_tokens, ensure_ascii=False),
        "variant_tokens": json.dumps(variant_tokens, ensure_ascii=False),
        "source_operator_window": row.get("source_operator_window", ""),
        "conditional_constraints": row.get("conditional_constraints", ""),
        "hidden_dependency": row.get("hidden_dependency", ""),
        "review_flags": row.get("review_flags", ""),
        "reviewer_notes": row.get("reviewer_notes", ""),
    }


def _family_alias(value: str) -> str:
    value = (value or "").strip()
    aliases = {
        "metadata_filter_select_bands": "select_filter",
        "clip_pixelwise_arithmetic": "clip_arithmetic",
        "object_chain_break_filtermetadata_after_image_select": "not_equivalent",
        "mask_threshold_or_logic": "mask_threshold_or_logic",
        "select_bands_temporal_reducer": "reducer_or_aggregation",
        "select_zonal": "reducer_or_aggregation",
        "select_temporal": "reducer_or_aggregation",
        "select_logical": "mask_threshold_or_logic",
        "metadata_mosaic": "other",
    }
    return aliases.get(value, value or "unknown")


def _write_markdown(path: Path, payload: dict) -> None:
    lines = [
        "# Verified Multi-Reference Registry V2",
        "",
        "This registry consolidates manually accepted and user-confirmed MRV expansion equivalents.",
        "It is the first training-eligible KB artifact, but training should still be run only as a controlled ablation.",
        "",
        f"- Unique reviewed variants: {payload['unique_reviewed_variant_count']}",
        f"- Equivalent variants: {payload['reviewed_equivalent_variant_count']}",
        f"- Task groups: {payload['reviewed_equivalence_group_count']}",
        f"- Excluded variants: {payload['excluded_variant_count']}",
        f"- Label counts: {json.dumps(payload['review_label_counts'], ensure_ascii=False, sort_keys=True)}",
        f"- Family counts: {json.dumps(payload['equivalence_family_counts'], ensure_ascii=False, sort_keys=True)}",
        f"- Risk counts: {json.dumps(payload['risk_level_counts'], ensure_ascii=False, sort_keys=True)}",
        "",
        "## Excluded Variants",
        "",
        "| variant_id | label | family | risk | note |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["excluded_variants"]:
        note = str(row.get("reviewer_notes", "")).replace("|", "/")
        lines.append(
            f"| {row.get('variant_id', '')} | {row.get('review_label', '')} | "
            f"{row.get('equivalence_family', '')} | {row.get('risk_level', '')} | {note} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manual-review", type=Path, default=DEFAULT_MANUAL_REVIEW)
    parser.add_argument("--expansion-review", type=Path, default=DEFAULT_EXPANSION_REVIEW)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = load_review_rows(args.manual_review, args.expansion_review)
    payload, kb_rows = build_registry_payload(rows)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "verified_multi_reference_registry_v2.json", payload)
    _write_json(
        output_dir / "verified_equivalence_kb_v2.json",
        {
            "schema_version": KB_SCHEMA_VERSION,
            "created_at": now(),
            "row_count": len(kb_rows),
            "rows": kb_rows,
        },
    )
    _write_csv(
        output_dir / "verified_equivalence_kb_v2.csv",
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
    _write_markdown(output_dir / "verified_multi_reference_registry_v2_summary.md", payload)
    print(
        json.dumps(
            {
                "unique_reviewed_variant_count": payload["unique_reviewed_variant_count"],
                "equivalent_variants": payload["reviewed_equivalent_variant_count"],
                "task_groups": payload["reviewed_equivalence_group_count"],
                "excluded_variants": payload["excluded_variant_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
