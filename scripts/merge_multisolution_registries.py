#!/usr/bin/env python3
"""Merge v2 and v3 verified multi-solution registries into v4.

This is an offline consolidation step only. It does not change training data
unless a later ablation builder consumes the merged registry explicitly.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.config.transformer_config import OUTPUT_DIR  # noqa: E402


DEFAULT_V2_PATH = OUTPUT_DIR / "v4_qg_multiref_validation" / "verified_multi_reference_registry_v2.json"
DEFAULT_V3_PATH = OUTPUT_DIR / "v4_qg_multisolution_candidates" / "verified_registry_v3" / "verified_multi_reference_registry_v3.json"
DEFAULT_KB_V2_PATH = OUTPUT_DIR / "v4_qg_multiref_validation" / "verified_equivalence_kb_v2.json"
DEFAULT_KB_V3_PATH = OUTPUT_DIR / "v4_qg_multisolution_candidates" / "verified_registry_v3" / "verified_equivalence_kb_v3.json"
DEFAULT_OUTPUT_DIR = OUTPUT_DIR / "v4_qg_multisolution_candidates" / "merged_registry_v4"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _merge_entry_maps(payloads: list[dict]) -> tuple[list[dict], list[dict]]:
    grouped: dict[tuple[str, str, str], dict] = {}
    excluded: list[dict] = []
    for payload in payloads:
        for entry in payload.get("entries", []) or []:
            key = (
                str(entry.get("task_type", "")),
                str(entry.get("task_name", "")),
                str(entry.get("task_description", "")),
            )
            merged = grouped.setdefault(
                key,
                {
                    "task_type": entry.get("task_type", ""),
                    "task_name": entry.get("task_name", ""),
                    "task_description": entry.get("task_description", ""),
                    "references": [],
                    "source_variant_ids": [],
                    "source_script_ids": [],
                    "equivalence_families": [],
                    "risk_levels": [],
                    "review_sources": [],
                    "review_notes": [],
                },
            )
            for ref in entry.get("references", []) or []:
                if ref and ref not in merged["references"]:
                    merged["references"].append(ref)
            for field in ("source_variant_ids", "source_script_ids", "equivalence_families", "risk_levels", "review_sources", "review_notes"):
                for value in entry.get(field, []) or []:
                    if value and value not in merged[field]:
                        merged[field].append(value)
        excluded.extend(payload.get("excluded_variants", []) or [])
    entries = list(grouped.values())
    entries.sort(key=lambda item: (item["task_type"], item["task_name"], item["task_description"]))
    return entries, excluded


def merge_registries(registry_v2: dict, registry_v3: dict, kb_v2: dict | None = None, kb_v3: dict | None = None) -> dict:
    entries, excluded = _merge_entry_maps([registry_v2, registry_v3])
    kb_rows = []
    for kb in (kb_v2 or {}).get("rows", []) or []:
        kb_rows.append(dict(kb))
    for kb in (kb_v3 or {}).get("rows", []) or []:
        kb_rows.append(dict(kb))
    kb_rows.sort(key=lambda row: str(row.get("variant_id", "")))
    label_counts = Counter({"equivalent": int(registry_v2.get("reviewed_equivalent_variant_count", 0)) + int(registry_v3.get("reviewed_equivalent_variant_count", 0))})
    return {
        "schema_version": "gis_recommend.v4_qg.verified_multiref_registry.v4",
        "created_at": _now(),
        "source_registry_versions": [
            str(registry_v2.get("schema_version", "")),
            str(registry_v3.get("schema_version", "")),
        ],
        "review_policy": "manual_and_human_confirmed_equivalent_only",
        "training_eligible": True,
        "deduplication_key": "variant_id",
        "input_registry_counts": {
            "v2_reviewed_equivalent_variant_count": int(registry_v2.get("reviewed_equivalent_variant_count", 0)),
            "v3_reviewed_equivalent_variant_count": int(registry_v3.get("reviewed_equivalent_variant_count", 0)),
        },
        "reviewed_equivalent_variant_count": int(registry_v2.get("reviewed_equivalent_variant_count", 0)) + int(registry_v3.get("reviewed_equivalent_variant_count", 0)),
        "reviewed_equivalence_group_count": len(entries),
        "excluded_variant_count": len(excluded),
        "review_label_counts": dict(label_counts),
        "entries": entries,
        "excluded_variants": excluded,
        "kb_rows": kb_rows,
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry-v2", type=Path, default=DEFAULT_V2_PATH)
    parser.add_argument("--registry-v3", type=Path, default=DEFAULT_V3_PATH)
    parser.add_argument("--kb-v2", type=Path, default=DEFAULT_KB_V2_PATH)
    parser.add_argument("--kb-v3", type=Path, default=DEFAULT_KB_V3_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    registry_v2 = _load_json(args.registry_v2)
    registry_v3 = _load_json(args.registry_v3)
    kb_v2 = _load_json(args.kb_v2) if args.kb_v2.exists() else {}
    kb_v3 = _load_json(args.kb_v3) if args.kb_v3.exists() else {}
    merged = merge_registries(registry_v2, registry_v3, kb_v2, kb_v3)
    kb_rows = merged["kb_rows"]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.output_dir / "verified_multi_reference_registry_v4.json", merged)
    _write_json(
        args.output_dir / "verified_equivalence_kb_v4.json",
        {
            "schema_version": "gis_recommend.v4_qg.verified_equivalence_kb.v4",
            "created_at": _now(),
            "row_count": len(kb_rows),
            "rows": kb_rows,
        },
    )
    print(
        json.dumps(
            {
                "reviewed_equivalent_variant_count": merged["reviewed_equivalent_variant_count"],
                "reviewed_equivalence_group_count": merged["reviewed_equivalence_group_count"],
                "output_dir": str(args.output_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return merged


if __name__ == "__main__":
    main()
