#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0 calibration runner: old vs calibrated flags on the 12-component wave.

Read-only.  Outputs B_TRACK_RISK_FLAG_CALIBRATION_V1.json.
Old definitions are the ones embedded in scripts/b_track_s1_sampling_v1.py
(ui regex / any repeated line >= 8 chars / broad nonliteral regex).
"""
import json
import re
from collections import Counter
from pathlib import Path

import sys
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from b_track_risk_flags_v1 import analyze_source  # noqa: E402

B = (REPO / "docs/reports/route2_p0_contract/plan_pipeline_v1/"
     "planning_capability_audit_v1/diag50_v1/b_track_audit_v1")
TREE = [REPO / ".tmp_gee_batch13_sources/Data", REPO / ".tmp_gee_batch8_ast_bridge/sources"]


def build_index():
    cache = REPO / ".tmp_script_index.json"
    if cache.exists():
        d = json.loads(cache.read_text(encoding="utf-8"))
        return {k: REPO / v for k, v in d.items()}
    idx = {}
    for tree in TREE:
        if not tree.exists():
            continue
        for d in sorted(tree.iterdir()):
            if d.is_dir():
                for f in d.glob("script_*.txt"):
                    idx.setdefault(f.stem, f)
    return idx


def old_flags(src):
    flags = []
    if re.search(r"\bui\.|Map\.(addLayer|setCenter|centerObject|add|setOptions)", src):
        flags.append("ui_scaffold")
    lines = [re.sub(r"\s+", "", l.split("//")[0]) for l in src.splitlines()]
    lines = [l for l in lines if len(l) >= 8]
    if any(v > 1 for v in Counter(lines).values()):
        flags.append("duplicate_lines")
    if re.search(r"ee\.(?:ImageCollection|Image|FeatureCollection)\(\s*(?:[A-Za-z_$]|['\"][^'\"]*['\"]\s*\+)", src):
        flags.append("indirect_asset")
    return flags


MANUAL_EXPECTED = {
    45165: ["nonliteral_asset_arg"],
    48878: ["map_display", "duplicate_block", "duplicate_line",
            "nonliteral_asset_arg", "literal_asset"],
    103943: ["ui_interactive", "ui_chart", "ui_display", "map_display",
             "duplicate_block", "duplicate_line", "nonliteral_asset_arg",
             "literal_asset"],
    51891: ["map_display", "duplicate_block", "nonliteral_asset_arg", "literal_asset"],
    50842: ["map_display", "duplicate_block", "duplicate_line",
            "nonliteral_asset_arg", "literal_asset"],
    42446: ["map_display", "duplicate_block", "duplicate_line", "literal_asset"],
    58126: ["ui_interactive", "ui_chart", "map_display", "duplicate_block",
            "duplicate_line", "nonliteral_asset_arg", "literal_asset"],
    74228: ["map_display", "duplicate_block", "duplicate_line",
            "nonliteral_asset_arg", "literal_asset"],
    17106: ["ui_interactive", "ui_chart", "ui_display", "map_display",
            "duplicate_block", "duplicate_line", "nonliteral_asset_arg",
            "literal_asset"],
    48801: ["map_display", "duplicate_block", "duplicate_line",
            "nonliteral_asset_arg", "literal_asset"],
    35770: ["map_display", "duplicate_block", "duplicate_line",
            "nonliteral_asset_arg"],
    45703: ["map_display", "literal_asset"],
}


def main():
    digest = json.loads((B / "B_TRACK_S1_WAVE1_DIGEST_V1.json").read_text(encoding="utf-8"))
    idx = build_index()
    out = []
    for item in digest:
        p = idx.get(item["script"])
        if not p:
            out.append({"component_id": item["component_id"], "script": item["script"],
                        "missing": True})
            continue
        src = p.read_text(encoding="utf-8", errors="replace")
        new = analyze_source(src)
        old = old_flags(src)
        expected = MANUAL_EXPECTED.get(item["component_id"], [])
        out.append({
            "component_id": item["component_id"],
            "split": item["split"],
            "task_type": item["task_type"],
            "script": item["script"],
            "path": str(p.relative_to(REPO)),
            "old_flags": old,
            "old_wave_counts": {"ui_calls": item["ui_calls"],
                                "dup_lines": item["dup_lines"],
                                "indirect_asset": item["indirect_asset"]},
            "manual_expected_flags": expected,
            "new": new,
            "match": sorted(expected) == sorted(new["flags"]),
        })
    (B / "B_TRACK_RISK_FLAG_CALIBRATION_V1.json").write_text(
        json.dumps({"artifact": "B_TRACK_RISK_FLAG_CALIBRATION_V1",
                    "date": "2026-10-18", "rules_version": new["rules_version"],
                    "components": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("components", len(out))
    for c in out:
        if c.get("missing"):
            print("MISSING", c["component_id"], c["script"])
            continue
        n = c["new"]
        print(c["component_id"], c["split"], c["script"],
              "| old", c["old_flags"],
              "| new", n["flags"],
              "| ui_ctrl", n["ui_control_calls"], "map", n["map_display_calls"],
              "dupL", n["dup_line_max"], "dupT", n["dup_triple_max"],
              "bare", len(n["bare_identifier_args"]), "concat", len(n["concat_args"]),
              "assets", len(n["literal_assets"]))


if __name__ == "__main__":
    main()
