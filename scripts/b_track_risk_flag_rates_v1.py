#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0: calibrated flag rates over the S1 sampling list V1 (read-only).

Compares the old definitions embedded in b_track_s1_sampling_v1.py with the
frozen calibrated definitions in b_track_risk_flags_v1.py.

Outputs B_TRACK_RISK_FLAG_RATES_V1.json.
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
POOL = REPO.parent / "04_DIAG_WORK/b1_gee_stage_train.jsonl"
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


def main():
    man = json.loads((B / "B_TRACK_SPLIT_MANIFEST_V2.json").read_text(encoding="utf-8"))
    rc = man["row_component"]
    sel = json.loads((B / "B_TRACK_S1_SAMPLING_LIST_V1.json").read_text(encoding="utf-8"))
    wanted = {c["component_id"]: c for c in sel["components"]}
    rep = {}
    with POOL.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            c = rc[i]
            if c in wanted and c not in rep:
                rep[c] = json.loads(line).get("script", "")
    idx = build_index()
    print("index", len(idx), "components", len(wanted))
    recs = []
    miss = 0
    for cid, meta in wanted.items():
        s = rep.get(cid, "")
        p = idx.get(s)
        if not p:
            miss += 1
            recs.append({"component_id": cid, "script": s, "missing": True,
                         "split": meta["split"], "tier": meta["tier"], "band": meta["band"]})
            continue
        src = p.read_text(encoding="utf-8", errors="replace")
        old = old_flags(src)
        new = analyze_source(src)
        recs.append({
            "component_id": cid, "script": s, "split": meta["split"],
            "tier": meta["tier"], "band": meta["band"],
            "old": old, "new": new["flags"],
            "ui_interactive": "ui_interactive" in new["flags"],
            "ui_chart": "ui_chart" in new["flags"],
            "map_display": "map_display" in new["flags"],
            "duplicate_block": new["duplicate_block"],
            "duplicate_line": new["duplicate_line"],
            "nonliteral_asset_arg": new["nonliteral_asset_arg"],
        })
    n = len(recs)
    ok = [r for r in recs if not r.get("missing")]
    m = len(ok)
    rates = {
        "n_components": n, "n_missing_script": miss, "n_scored": m,
        "old": {k: sum(1 for r in ok if k in r["old"]) for k in
                ("ui_scaffold", "duplicate_lines", "indirect_asset")},
        "new": {k: sum(1 for r in ok if r[k]) for k in
                ("ui_interactive", "ui_chart", "map_display", "duplicate_block",
                 "duplicate_line", "nonliteral_asset_arg")},
        "old_pct": {}, "new_pct": {},
    }
    for k, v in rates["old"].items():
        rates["old_pct"][k] = round(100 * v / m, 2)
    for k, v in rates["new"].items():
        rates["new_pct"][k] = round(100 * v / m, 2)
    by_split = {}
    for sp in ("t", "v", "s"):
        sub = [r for r in ok if r["split"] == sp]
        by_split[sp] = {
            "n": len(sub),
            "old_ui_pct": round(100 * sum(1 for r in sub if "ui_scaffold" in r["old"]) / max(1, len(sub)), 2),
            "new_ui_interactive_pct": round(100 * sum(1 for r in sub if r["ui_interactive"]) / max(1, len(sub)), 2),
            "old_dup_pct": round(100 * sum(1 for r in sub if "duplicate_lines" in r["old"]) / max(1, len(sub)), 2),
            "new_dup_block_pct": round(100 * sum(1 for r in sub if r["duplicate_block"]) / max(1, len(sub)), 2),
            "old_indirect_pct": round(100 * sum(1 for r in sub if "indirect_asset" in r["old"]) / max(1, len(sub)), 2),
            "new_nonliteral_pct": round(100 * sum(1 for r in sub if r["nonliteral_asset_arg"]) / max(1, len(sub)), 2),
        }
    out = {"artifact": "B_TRACK_RISK_FLAG_RATES_V1", "date": "2026-10-18",
           "rules_version": "V1_calibrated_20261018",
           "sample": "B_TRACK_S1_SAMPLING_LIST_V1 (7,562 components)",
           "rates": rates, "by_split": by_split,
           "note": "map_display is descriptive (display scaffolding), not a risk flag.",
           "components": recs}
    (B / "B_TRACK_RISK_FLAG_RATES_V1.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"rates": rates, "by_split": by_split}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
