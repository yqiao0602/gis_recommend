#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Expand the QGIS alg-id -> L3 crosswalk with alias + semantic mappings.

Reads the existing crosswalk (only l3_bridge entries are active), adds:
  1. qgis:<->native: alias normalization — e.g. qgis:fieldcalculator -> maps to
     the same L3 as native:fieldcalculator (which is already crosswalked).
  2. Semantic mappings — operators that fit existing L3_02 (vector) or L3_01/03
     slots but were left as pending / native_bridge / unseen.

Does NOT change the 94-L3 vocabulary, existing crosswalk entries, or the model
architecture. Output is a NEW crosswalk file (--out); the original is untouched.

Usage:
    python expand_qgis_l3_crosswalk.py --out outputs_v2/qgis_alg_id_crosswalk_expanded.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

DEFAULT_CROSSWALK = ROOT / "outputs_v2" / "qgis_alg_id_crosswalk.json"
DEFAULT_OUT = ROOT / "outputs_v2" / "qgis_alg_id_crosswalk_expanded.json"

# ── Semantic mappings: top real-gap operators that fit EXISTING L3 slots ──
# Rationale: each entry is assessed against the 94-code vector/raster families;
# non-core (IO / GRASS / postgis download) intentionally skipped.
SEMANTIC_MAP = {
    # ── vector / geometry (L3_02) ──
    "native:aggregate": ("L3_02_03_05", "Aggregate"),
    "native:joinbynearest": ("L3_02_04_01", "Join attributes by nearest"),
    "native:splitwithlines": ("L3_02_05_06", "Split with lines"),
    "native:extractvertices": ("L3_02_05_11", "Extract vertices"),
    "native:extractspecificvertices": ("L3_02_05_11", "Extract specific vertices"),
    "native:deleteduplicategeometries": ("L3_02_03_05", "Delete duplicate geometries"),
    "native:deleteholes": ("L3_02_07_01", "Delete holes"),
    "native:explodelines": ("L3_02_07_01", "Explode lines"),
    "native:multipartsingleparts": ("L3_02_07_01", "Multipart to singleparts"),
    "native:polygonfromlayerextent": ("L3_02_05_12", "Extract layer extent"),
    "native:simplifygeometries": ("L3_02_07_01", "Simplify geometries"),
    "native:smoothgeometry": ("L3_02_07_01", "Smooth geometry"),
    "native:pointsalonglines": ("L3_02_05_06", "Points along geometry"),
    "native:difference": ("L3_02_02_04", "Difference"),
    # ── raster (L3_03) ──
    "gdal:cliprasterbyextent": ("L3_03_01_01", "Clip raster by extent"),
    "native:pixelstopoints": ("L3_03_01_01", "Raster pixels to points"),
    "gdal:translate": ("L3_07_04_05", "Translate"),
    # ── field / attribute ──
    "qgis:exportaddgeometrycolumns": ("L3_01_02_06", "Add geometry attributes"),
    "qgis:refactorfields": ("L3_01_02_02", "Refactor fields"),
    "native:fieldcalculator": ("L3_01_02_06", "Field calculator"),
    # ── heatmap via nearest L3 cluster (density -> proximity = Buffer, closest 94 slot) ──
    "qgis:heatmapkerneldensityestimation": ("L3_02_01_01", "Heatmap"),
    # ── export ──
    "native:saveselectedfeatures": ("L3_07_04_01", "Save selected features"),
}


def _alias_map(crosswalk_entries: dict) -> dict:
    """Generate qgis:<->native: aliases from existing 'native:' crosswalk entries."""
    aliases = {}
    for alg_id, entry in crosswalk_entries.items():
        if entry.get("bridge_type") != "l3_bridge":
            continue
        lid = alg_id.lower()
        # native:foo -> qgis:foo (QGIS renamed many native ops from qgis: prefix)
        if lid.startswith("native:"):
            alias = lid.replace("native:", "qgis:")
            aliases[alias] = entry["l3_code"]
        elif lid.startswith("qgis:"):
            aliases[lid.replace("qgis:", "native:")] = entry["l3_code"]
    return aliases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--crosswalk", default=str(DEFAULT_CROSSWALK))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    cw = json.loads(Path(args.crosswalk).read_text(encoding="utf-8"))
    entries = cw["entries"]  # {alg_id: {alg_id, official_name, l3_code, bridge_type, ...}}

    original_l3_bridge = sum(1 for e in entries.values() if e.get("bridge_type") == "l3_bridge")
    added = 0
    added_roles = []  # for summary

    # 1. alias normalization
    aliases = _alias_map(entries)
    for alias, l3_code in aliases.items():
        if alias in entries:
            continue  # already present
        base_alg = alias.split(":", 1)[1]
        entries[alias] = {
            "alg_id": alias,
            "official_name": f"(alias of {alias.replace('qgis:', 'native:').replace('native:', 'qgis:')})",
            "l3_code": l3_code,
            "bridge_type": "l3_bridge",
            "_expansion_source": "alias_normalization",
        }
        added += 1
        if added <= 5:
            added_roles.append(f"  alias: {alias} -> {l3_code}")

    # 2. semantic mappings (only if not already present)
    for alg_id, (l3_code, official_name) in SEMANTIC_MAP.items():
        if alg_id in entries:
            # if it's already l3_bridge, skip; if pending/native_bridge, upgrade
            existing = entries[alg_id]
            if existing.get("bridge_type") == "l3_bridge":
                continue
            existing["l3_code"] = l3_code
            existing["bridge_type"] = "l3_bridge"
            existing["_expansion_source"] = "semantic_upgrade"
        else:
            entries[alg_id] = {
                "alg_id": alg_id,
                "official_name": official_name,
                "l3_code": l3_code,
                "bridge_type": "l3_bridge",
                "_expansion_source": "semantic_mapping",
            }
        added += 1
        if added <= 15:
            added_roles.append(f"  semantic: {alg_id} -> {l3_code} (was {existing.get('bridge_type','absent')})")

    cw["total_entries"] = len(entries)
    final_l3_bridge = sum(1 for e in entries.values() if e.get("bridge_type") == "l3_bridge")
    cw["coverage_rate"] = round(final_l3_bridge / max(len(entries), 1), 4)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(cw, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"crosswalk entries: {original_l3_bridge} l3_bridge -> {final_l3_bridge} l3_bridge  (total {len(entries)})")
    print(f"l3_bridge added: {final_l3_bridge - original_l3_bridge}")
    print("first additions:")
    for a in added_roles[:12]:
        print(a)
    print(f"out -> {args.out}")


if __name__ == "__main__":
    main()
