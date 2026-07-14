#!/usr/bin/env python3
"""Merge reviewed stable-94 QGIS bridges with the frozen 114 taxonomy aliases."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.data.qgis_pilot import file_sha256, normalize_qgis_operation  # noqa: E402

REVIEWED_SEMANTIC_REASSIGNMENTS = {
    ("qgis:joinattributestable", "L3_02_04_01", "L3_01_03_05"),
    ("native:deleteduplicategeometries", "L3_02_03_05", "L3_01_05_04"),
    ("qgis:deleteduplicategeometries", "L3_02_03_05", "L3_01_05_04"),
    ("native:assignprojection", "L3_01_02_03", "L3_01_10_02"),
    ("gdal:assignprojection", "L3_01_02_03", "L3_01_10_02"),
    ("native:simplifygeometries", "L3_02_07_01", "L3_02_05_01"),
    ("native:smoothgeometry", "L3_02_07_01", "L3_02_05_02"),
    ("native:deleteholes", "L3_02_07_01", "L3_02_05_13"),
    ("native:extractvertices", "L3_02_05_11", "L3_02_05_15"),
    ("native:extractspecificvertices", "L3_02_05_11", "L3_02_05_15"),
}


def build_crosswalk(
    taxonomy: Mapping[str, Any],
    base_crosswalk: Mapping[str, Any],
) -> dict[str, Any]:
    code_to_id = taxonomy["code_to_token_id"]
    base_count = int(taxonomy["base_class_count"])
    entries: dict[str, dict[str, Any]] = {}
    alias_to_code: dict[str, str] = {}
    for raw_operation, raw_entry in base_crosswalk.get("entries", {}).items():
        operation = normalize_qgis_operation(raw_operation)
        entry = dict(raw_entry)
        previous = entries.get(operation)
        if previous is not None and previous != entry:
            raise ValueError(f"normalized base crosswalk collision: {operation}")
        if entry.get("bridge_type") == "l3_bridge":
            code = entry.get("l3_code")
            if code not in code_to_id or code_to_id[code] >= base_count:
                raise ValueError(f"base crosswalk target is not in stable base: {operation}:{code}")
            alias_to_code[operation] = code
        entries[operation] = entry

    overrides = []
    for raw_alias, code in taxonomy.get("alias_to_code", {}).items():
        alias = normalize_qgis_operation(raw_alias)
        previous = entries.get(alias, {})
        reassignment = (alias, previous.get("l3_code"), code)
        if (
            previous.get("bridge_type") == "l3_bridge"
            and previous.get("l3_code") != code
            and reassignment not in REVIEWED_SEMANTIC_REASSIGNMENTS
        ):
            raise ValueError(
                f"reviewed alias conflicts with stable L3 bridge: {alias}:"
                f"{previous.get('l3_code')}->{code}"
            )
        overrides.append(
            {
                "operation": alias,
                "new_l3_code": code,
                "previous_bridge_type": previous.get("bridge_type", "absent"),
                "previous_l3_code": previous.get("l3_code", ""),
                "semantic_reassignment": reassignment in REVIEWED_SEMANTIC_REASSIGNMENTS,
            }
        )
        entries[alias] = {
            **previous,
            "alg_id": alias,
            "l3_code": code,
            "l3_token_id": code_to_id[code],
            "bridge_type": "l3_bridge",
            "status": "accepted",
            "source": "taxonomy_114_reviewed_alias",
        }
        alias_to_code[alias] = code

    counts = Counter(entry.get("bridge_type", "unknown") for entry in entries.values())
    return {
        "schema": "gis_recommend.qgis_alg_id_crosswalk.v2",
        "profile": taxonomy.get("profile"),
        "base_profile": taxonomy.get("base_profile"),
        "entries": dict(sorted(entries.items())),
        "alias_to_code": dict(sorted(alias_to_code.items())),
        "reviewed_overrides": sorted(overrides, key=lambda row: row["operation"]),
        "summary": {
            "entries": len(entries),
            "exact_l3_aliases": len(alias_to_code),
            "bridge_types": dict(sorted(counts.items())),
            "reviewed_taxonomy_aliases": len(overrides),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--base-crosswalk", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    taxonomy = json.loads(args.taxonomy.read_text(encoding="utf-8"))
    base = json.loads(args.base_crosswalk.read_text(encoding="utf-8"))
    merged = build_crosswalk(taxonomy, base)
    merged["inputs"] = {
        "taxonomy_file": args.taxonomy.name,
        "taxonomy_sha256": file_sha256(args.taxonomy),
        "base_crosswalk_file": args.base_crosswalk.name,
        "base_crosswalk_sha256": file_sha256(args.base_crosswalk),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes((json.dumps(merged, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps(merged["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
