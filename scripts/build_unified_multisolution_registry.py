#!/usr/bin/env python3
"""Build a unified verified multi-solution registry from all approved sources."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
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


SCHEMA_VERSION = "gis_recommend.v4_qg.verified_multiref_registry.unified.v1"
KB_SCHEMA_VERSION = "gis_recommend.v4_qg.verified_equivalence_kb.unified.v1"
DEFAULT_MRV_REGISTRY = OUTPUT_DIR / "v4_qg_multiref_validation" / "verified_multi_reference_registry_v2.json"
DEFAULT_MRV_KB = OUTPUT_DIR / "v4_qg_multiref_validation" / "verified_equivalence_kb_v2.json"
DEFAULT_CONSERVATIVE_CSV = OUTPUT_DIR / "v4_qg_multisolution_candidates" / "candidate_review_sheet_ai_reviewed.csv"
DEFAULT_STRUCTURAL_CSV = OUTPUT_DIR / "v4_qg_multisolution_candidates_relaxed_probe" / "combined_equivalents.csv"
DEFAULT_FILTER_SWAP_CSV = OUTPUT_DIR / "safe_swap_candidates_v1" / "sampled_filter_swaps_1000.csv"
DEFAULT_OUTPUT_DIR = OUTPUT_DIR / "v4_qg_multisolution_unified_registry_v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _parse_tokens(value: object) -> list[int]:
    current = value
    for _ in range(3):
        if isinstance(current, list):
            return [int(item) for item in current]
        if isinstance(current, str) and current.strip():
            try:
                current = json.loads(current)
            except json.JSONDecodeError:
                return []
        else:
            return []
    return [int(item) for item in current] if isinstance(current, list) else []


def _with_specials(tokens: Sequence[int]) -> list[int]:
    content = [int(token) for token in tokens if int(token) >= 0]
    return [-3, *content, -4]


def _equivalent(row: dict) -> bool:
    return str(row.get("human_label") or row.get("review_label") or "").strip().lower() in {
        "equivalent",
        "verified_equivalent",
    }


def _kb_row(
    *,
    variant_id: str,
    task_type: str,
    task_name: str,
    source_family: str,
    original_tokens: list[int],
    variant_tokens: list[int],
    equivalence_family: str,
    risk_level: str,
    review_source: str,
    reviewer_notes: str = "",
    review_flags: str = "",
    conditional_constraints: str = "",
) -> dict:
    return {
        "variant_id": variant_id,
        "task_type": task_type,
        "task_name": task_name,
        "source_script_id": "",
        "review_source": review_source,
        "source_family": source_family,
        "review_label": "equivalent",
        "equivalence_family": equivalence_family,
        "risk_level": risk_level,
        "swapped_pair": "",
        "swapped_pair_names": "",
        "original_tokens": json.dumps(original_tokens, ensure_ascii=False),
        "variant_tokens": json.dumps(variant_tokens, ensure_ascii=False),
        "source_operator_window": "",
        "conditional_constraints": conditional_constraints,
        "hidden_dependency": "",
        "review_flags": review_flags,
        "reviewer_notes": reviewer_notes,
    }


def _mrv_rows(mrv_kb: dict) -> list[dict]:
    rows = []
    for row in mrv_kb.get("rows", []) or []:
        if str(row.get("review_label", "")).strip() != "equivalent":
            continue
        copied = dict(row)
        copied["source_family"] = "manual_mrv_v2"
        copied.setdefault("review_source", "manual_or_user_confirmed_mrv_v2")
        rows.append(copied)
    return rows


def _structural_rows(rows: Sequence[dict], conservative_candidate_ids: set[str]) -> list[dict]:
    out = []
    for row in rows:
        if not _equivalent(row):
            continue
        candidate_id = str(row.get("candidate_id", "") or "")
        source_family = (
            "structural_equivalence_conservative"
            if candidate_id in conservative_candidate_ids
            else "structural_equivalence_relaxed"
        )
        left_tokens = _with_specials(_parse_tokens(row.get("left_tokens")))
        right_tokens = _with_specials(_parse_tokens(row.get("right_tokens")))
        if not left_tokens or not right_tokens:
            continue
        out.append(
            _kb_row(
                variant_id=f"struct_{candidate_id}",
                task_type=str(row.get("task_type", "") or ""),
                task_name=str(row.get("left_task_name", "") or ""),
                source_family=source_family,
                original_tokens=left_tokens,
                variant_tokens=right_tokens,
                equivalence_family=source_family,
                risk_level="reviewed",
                review_source="structural_equivalence_human_review",
                reviewer_notes=str(row.get("review_notes", "") or ""),
                review_flags=";".join(
                    part
                    for part in (
                        f"set_f1={row.get('set_f1', '')}",
                        f"lcs_ratio={row.get('lcs_ratio', '')}",
                        f"length_delta={row.get('length_delta', '')}",
                        f"text_jaccard={row.get('text_jaccard', '')}",
                    )
                    if not part.endswith("=")
                ),
                conditional_constraints="human_confirmed_same_task_structural_equivalence",
            )
        )
    return out


def _filter_swap_rows(rows: Sequence[dict]) -> list[dict]:
    out = []
    for row in rows:
        if not _equivalent(row):
            continue
        source_family = str(row.get("source_family", "") or "local_filter_swap_sampled")
        if source_family != "local_filter_swap_sampled":
            continue
        tier = str(row.get("tier", "") or "")
        if tier and tier != "auto_verified":
            continue
        swap_type = str(row.get("swap_type", "") or "")
        if swap_type and swap_type != "filter<>filter":
            continue
        original_tokens = _with_specials(_parse_tokens(row.get("original_tokens")))
        variant_tokens = _with_specials(_parse_tokens(row.get("variant_tokens")))
        if not original_tokens or not variant_tokens:
            continue
        out.append(
            _kb_row(
                variant_id=str(row.get("variant_id", "") or ""),
                task_type=str(row.get("task_type", "") or ""),
                task_name=str(row.get("task_name", "") or ""),
                source_family=source_family,
                original_tokens=original_tokens,
                variant_tokens=variant_tokens,
                equivalence_family="filter_filter",
                risk_level="sampled_low",
                review_source="safe_filter_swap_sampler",
                reviewer_notes=str(row.get("review_notes", "") or ""),
                conditional_constraints="adjacent_collection_filter_swap_sampled",
            )
        )
    return out


def _unified_equivalent_rows(rows: Sequence[dict]) -> list[dict]:
    out = []
    for row in rows:
        if not _equivalent(row):
            continue
        source_family = str(row.get("source_family", "") or "")
        if source_family == "structural_equivalence":
            candidate_id = str(row.get("candidate_id", "") or "")
            left_tokens = _with_specials(_parse_tokens(row.get("left_tokens")))
            right_tokens = _with_specials(_parse_tokens(row.get("right_tokens")))
            if not candidate_id or not left_tokens or not right_tokens:
                continue
            out.append(
                _kb_row(
                    variant_id=f"struct_{candidate_id}",
                    task_type=str(row.get("task_type", "") or ""),
                    task_name=str(row.get("left_task_name", "") or ""),
                    source_family="structural_equivalence",
                    original_tokens=left_tokens,
                    variant_tokens=right_tokens,
                    equivalence_family="structural_equivalence",
                    risk_level="reviewed",
                    review_source="structural_equivalence_reviewed_unified_csv",
                    reviewer_notes=str(row.get("review_notes", "") or ""),
                    review_flags=";".join(
                        part
                        for part in (
                            f"set_f1={row.get('set_f1', '')}",
                            f"lcs_ratio={row.get('lcs_ratio', '')}",
                            f"length_delta={row.get('length_delta', '')}",
                            f"text_jaccard={row.get('text_jaccard', '')}",
                        )
                        if not part.endswith("=")
                    ),
                    conditional_constraints="human_or_ai_reviewed_same_task_structural_equivalence",
                )
            )
            continue
        if source_family == "local_filter_swap_sampled":
            tier = str(row.get("tier", "") or "")
            swap_type = str(row.get("swap_type", "") or "")
            if tier != "auto_verified" or swap_type != "filter<>filter":
                continue
            original_tokens = _with_specials(_parse_tokens(row.get("original_tokens")))
            variant_tokens = _with_specials(_parse_tokens(row.get("variant_tokens")))
            variant_id = str(row.get("variant_id", "") or "")
            if not variant_id or not original_tokens or not variant_tokens:
                continue
            out.append(
                _kb_row(
                    variant_id=variant_id,
                    task_type=str(row.get("task_type", "") or ""),
                    task_name=str(row.get("task_name", "") or ""),
                    source_family="local_filter_swap_sampled",
                    original_tokens=original_tokens,
                    variant_tokens=variant_tokens,
                    equivalence_family="filter_filter",
                    risk_level="sampled_low",
                    review_source="safe_filter_swap_sampler_unified_csv",
                    reviewer_notes=str(row.get("review_notes", "") or ""),
                    conditional_constraints="adjacent_collection_filter_swap_sampled",
                )
            )
    return out


def _build_entries(kb_rows: Sequence[dict]) -> list[dict]:
    grouped: dict[tuple[str, str, str], dict] = {}
    for row in kb_rows:
        original_tokens = _parse_tokens(row.get("original_tokens"))
        variant_tokens = _parse_tokens(row.get("variant_tokens"))
        key = (str(row.get("task_type", "")), str(row.get("task_name", "")), "")
        entry = grouped.setdefault(
            key,
            {
                "task_type": key[0],
                "task_name": key[1],
                "task_description": "",
                "references": [],
                "source_variant_ids": [],
                "source_script_ids": [],
                "equivalence_families": [],
                "risk_levels": [],
                "review_sources": [],
                "review_notes": [],
                "source_families": [],
            },
        )
        for tokens in (original_tokens, variant_tokens):
            if tokens and tokens not in entry["references"]:
                entry["references"].append(tokens)
        for field, target in (
            ("variant_id", "source_variant_ids"),
            ("equivalence_family", "equivalence_families"),
            ("risk_level", "risk_levels"),
            ("review_source", "review_sources"),
            ("source_family", "source_families"),
        ):
            value = str(row.get(field, "") or "")
            if value and value not in entry[target]:
                entry[target].append(value)
        note = str(row.get("reviewer_notes", "") or "")
        if note:
            entry["review_notes"].append(f"{row.get('variant_id', '')}: {note}")
    entries = list(grouped.values())
    entries.sort(key=lambda item: (item["task_type"], item["task_name"]))
    return entries


def build_unified_registry(
    *,
    mrv_registry: dict,
    mrv_kb: dict,
    structural_rows: Sequence[dict],
    conservative_candidate_ids: set[str],
    filter_swap_rows: Sequence[dict],
    unified_equivalent_rows: Sequence[dict] | None = None,
) -> tuple[dict, list[dict]]:
    kb_rows = []
    kb_rows.extend(_mrv_rows(mrv_kb))
    if unified_equivalent_rows is not None:
        kb_rows.extend(_unified_equivalent_rows(unified_equivalent_rows))
    else:
        kb_rows.extend(_structural_rows(structural_rows, conservative_candidate_ids))
        kb_rows.extend(_filter_swap_rows(filter_swap_rows))
    deduped = {str(row.get("variant_id", "")): dict(row) for row in kb_rows if row.get("variant_id")}
    kb_rows = [deduped[key] for key in sorted(deduped)]
    entries = _build_entries(kb_rows)
    source_counts = Counter(str(row.get("source_family", "") or "unknown") for row in kb_rows)
    family_counts = Counter(str(row.get("equivalence_family", "") or "unknown") for row in kb_rows)
    registry = {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now(),
        "review_policy": "verified_sources_only_with_source_family_provenance",
        "training_eligible": True,
        "deduplication_key": "variant_id",
        "source_registry_versions": [str(mrv_registry.get("schema_version", ""))],
        "reviewed_equivalent_variant_count": len(kb_rows),
        "reviewed_equivalence_group_count": len(entries),
        "excluded_variant_count": len(mrv_registry.get("excluded_variants", []) or []),
        "review_label_counts": {"equivalent": len(kb_rows)},
        "source_family_counts": dict(source_counts),
        "equivalence_family_counts": dict(family_counts),
        "entries": entries,
        "excluded_variants": list(mrv_registry.get("excluded_variants", []) or []),
    }
    return registry, kb_rows


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mrv-registry", type=Path, default=DEFAULT_MRV_REGISTRY)
    parser.add_argument("--mrv-kb", type=Path, default=DEFAULT_MRV_KB)
    parser.add_argument("--conservative-csv", type=Path, default=DEFAULT_CONSERVATIVE_CSV)
    parser.add_argument("--structural-csv", type=Path, default=DEFAULT_STRUCTURAL_CSV)
    parser.add_argument("--filter-swap-csv", type=Path, default=DEFAULT_FILTER_SWAP_CSV)
    parser.add_argument(
        "--unified-equivalents-csv",
        type=Path,
        default=None,
        help=(
            "Optional pre-merged reviewed equivalents CSV. When provided, structural/filter "
            "CSV inputs are ignored and only auto-verified filter<>filter swaps are included."
        ),
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict:
    args = parse_args(argv)
    mrv_registry = _load_json(args.mrv_registry)
    mrv_kb = _load_json(args.mrv_kb)
    if args.unified_equivalents_csv is not None:
        conservative_ids = set()
        structural_rows = []
        filter_swap_rows = []
        unified_equivalent_rows = _read_csv(args.unified_equivalents_csv)
    else:
        conservative_rows = _read_csv(args.conservative_csv)
        conservative_ids = {
            str(row.get("candidate_id", "") or "")
            for row in conservative_rows
            if _equivalent(row)
        }
        structural_rows = _read_csv(args.structural_csv)
        filter_swap_rows = _read_csv(args.filter_swap_csv)
        unified_equivalent_rows = None
    registry, kb_rows = build_unified_registry(
        mrv_registry=mrv_registry,
        mrv_kb=mrv_kb,
        structural_rows=structural_rows,
        conservative_candidate_ids=conservative_ids,
        filter_swap_rows=filter_swap_rows,
        unified_equivalent_rows=unified_equivalent_rows,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.output_dir / "verified_multi_reference_registry_unified.json", registry)
    _write_json(
        args.output_dir / "verified_equivalence_kb_unified.json",
        {
            "schema_version": KB_SCHEMA_VERSION,
            "created_at": _now(),
            "row_count": len(kb_rows),
            "rows": kb_rows,
        },
    )
    print(
        json.dumps(
            {
                "reviewed_equivalent_variant_count": registry["reviewed_equivalent_variant_count"],
                "reviewed_equivalence_group_count": registry["reviewed_equivalence_group_count"],
                "source_family_counts": registry["source_family_counts"],
                "output_dir": str(args.output_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return registry


if __name__ == "__main__":
    main()
