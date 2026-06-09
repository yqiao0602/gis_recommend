# -*- coding: utf-8 -*-
"""
Phase B — triage LLM audit proposals.

Reads both outputs_v2/qgis_mapping_llm_proposals.json and
outputs_v2/gee_auto_mapping_llm_proposals.json and partitions each entry into
one of four buckets.  The goal: minimize human review burden by auto-
accepting the clear cases and flagging only the ambiguous ones.

Buckets:
  A. AGREE      — LLM top-1 == current mapping.  No action needed.
  B. STRONG_FIX — LLM top-1 confidence >= 0.85 AND differs from current.
                  Default to LLM's suggestion (user can still override).
  C. SKIP       — LLM's top-1 is "SKIP" (non-op).  Add to skip list.
  D. REVIEW     — Ambiguous (confidence <0.85 or top-1/top-2 gap small).
                  Needs human decision.

Outputs:
  outputs_v2/mapping_audit_triage.md    — human-reviewable table
  outputs_v2/mapping_audit_triage.json  — machine-readable per-op decisions
"""
from __future__ import annotations
import json
import csv
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parents[1]
QGIS_PROPS = ROOT / "outputs_v2" / "qgis_mapping_llm_proposals.json"
GEE_PROPS = ROOT / "outputs_v2" / "gee_auto_mapping_llm_proposals.json"
HIER_V2 = ROOT / "outputs_v2" / "classification_hierarchy_v2.csv"

OUT_MD = ROOT / "outputs_v2" / "mapping_audit_triage.md"
OUT_JSON = ROOT / "outputs_v2" / "mapping_audit_triage.json"

STRONG_FIX_CONF = 0.85
STRONG_FIX_MARGIN = 0.15  # top1-top2 gap
SOLO_CONF = 0.90          # conf alone high enough to auto-apply regardless of margin


def load_l3_names() -> dict[str, str]:
    out = {}
    for r in csv.DictReader(HIER_V2.open(encoding="utf-8")):
        out[r["l3_code"]] = r["l3_name"]
    return out


def triage_one(entry: dict) -> tuple[str, dict]:
    top3 = entry.get("llm_top3", [])
    current = entry.get("current_l3", "")
    if not top3:
        return "REVIEW", {"reason": "empty llm_top3"}
    top1 = top3[0]
    top1_code = top1.get("l3_code", "")
    top1_conf = float(top1.get("confidence", 0))
    top2_conf = float(top3[1].get("confidence", 0)) if len(top3) > 1 else 0.0
    margin = top1_conf - top2_conf

    if top1_code == "SKIP":
        return "SKIP", {"reason": f"LLM says SKIP (conf {top1_conf:.2f})"}
    if top1_code == current:
        return "AGREE", {"reason": f"LLM agrees (conf {top1_conf:.2f})"}
    if top1_conf >= SOLO_CONF:
        return "STRONG_FIX", {
            "reason": f"LLM confidence {top1_conf:.2f} (solo threshold)",
            "proposed": top1_code,
        }
    if top1_conf >= STRONG_FIX_CONF and margin >= STRONG_FIX_MARGIN:
        return "STRONG_FIX", {
            "reason": f"LLM confidence {top1_conf:.2f} margin {margin:.2f}",
            "proposed": top1_code,
        }
    return "REVIEW", {
        "reason": f"ambiguous (conf {top1_conf:.2f}, margin {margin:.2f})",
    }


def format_entry_row(side: str, op: str, entry: dict, bucket: str, extra: dict) -> str:
    """markdown table row"""
    cur = f"{entry.get('current_l3','?')} ({entry.get('current_l3_name','?')[:18]})"
    t1 = entry.get("llm_top3", [])
    if t1:
        t1 = t1[0]
        proposed = f"{t1.get('l3_code','?')} ({t1.get('name','?')[:18]}, c={t1.get('confidence',0):.2f})"
        reason = (t1.get("reason", "") or "")[:40]
    else:
        proposed = "-"
        reason = ""
    desc = (entry.get("description", "") or "")[:50]
    return f"| {side} | `{op[:30]}` | {cur} | {proposed} | {bucket} | {reason} |"


def main():
    l3_names = load_l3_names()

    # Load proposals
    all_entries = []
    if QGIS_PROPS.exists():
        q = json.load(QGIS_PROPS.open(encoding="utf-8"))["entries"]
        for op, e in q.items():
            all_entries.append(("QGIS", op, e))
        print(f"Loaded QGIS proposals: {len(q)}")
    if GEE_PROPS.exists():
        g = json.load(GEE_PROPS.open(encoding="utf-8"))["entries"]
        for op, e in g.items():
            all_entries.append(("GEE", op, e))
        print(f"Loaded GEE proposals: {len(g)}")

    # Triage
    buckets: dict[str, list] = defaultdict(list)
    for side, op, entry in all_entries:
        bucket, extra = triage_one(entry)
        buckets[bucket].append((side, op, entry, extra))

    print(f"\nTriage buckets:")
    for k in ("AGREE", "STRONG_FIX", "SKIP", "REVIEW"):
        print(f"  {k:<12} {len(buckets[k])}")

    # Per-bucket QGIS/GEE split
    for k, rows in buckets.items():
        sides = Counter(r[0] for r in rows)
        print(f"  {k}: QGIS={sides.get('QGIS',0)}  GEE={sides.get('GEE',0)}")

    # Write triage JSON
    decisions = {}
    for bucket, rows in buckets.items():
        for side, op, entry, extra in rows:
            key = f"{side}:{op}"
            decisions[key] = {
                "side": side,
                "op": op,
                "bucket": bucket,
                "current_l3": entry.get("current_l3", ""),
                "proposed_l3": entry.get("llm_top3", [{}])[0].get("l3_code", ""),
                "proposed_name": entry.get("llm_top3", [{}])[0].get("name", ""),
                "confidence": entry.get("llm_top3", [{}])[0].get("confidence", 0),
                "reason": extra.get("reason", ""),
                "default_final": (
                    entry.get("current_l3", "")         if bucket == "AGREE"
                    else "SKIP"                         if bucket == "SKIP"
                    else entry.get("llm_top3", [{}])[0].get("l3_code", "")
                                                        if bucket == "STRONG_FIX"
                    else ""  # REVIEW — user must decide
                ),
                "user_decision": "",  # filled in during review
            }

    with OUT_JSON.open("w", encoding="utf-8") as f:
        json.dump({
            "thresholds": {"strong_fix_conf": STRONG_FIX_CONF,
                            "strong_fix_margin": STRONG_FIX_MARGIN},
            "summary": {k: len(v) for k, v in buckets.items()},
            "decisions": decisions,
        }, f, ensure_ascii=False, indent=2)

    # Write markdown — focus on REVIEW bucket (human attention)
    md = []
    md.append("# Mapping Audit Triage")
    md.append("")
    md.append(f"Total proposals: {sum(len(v) for v in buckets.values())}")
    md.append("")
    md.append("| Bucket | Count | QGIS | GEE |")
    md.append("|--------|-------|------|-----|")
    for k in ("AGREE", "STRONG_FIX", "SKIP", "REVIEW"):
        rows = buckets[k]
        sides = Counter(r[0] for r in rows)
        md.append(f"| {k} | {len(rows)} | {sides.get('QGIS',0)} | {sides.get('GEE',0)} |")
    md.append("")

    md.append("## Bucket B: STRONG_FIX (LLM disagrees with confidence)")
    md.append("")
    md.append("Default is to accept the LLM's top-1 proposal.  Override by editing mapping_audit_triage.json if any of these look wrong.")
    md.append("")
    md.append("| Side | Op | Current | Proposed | Bucket | LLM reason |")
    md.append("|------|------|---------|----------|--------|------------|")
    for side, op, entry, extra in buckets["STRONG_FIX"]:
        md.append(format_entry_row(side, op, entry, "STRONG_FIX", extra))
    md.append("")

    md.append("## Bucket C: SKIP (LLM says non-op)")
    md.append("")
    md.append("| Side | Op | Current | LLM says | Reason |")
    md.append("|------|------|---------|----------|--------|")
    for side, op, entry, extra in buckets["SKIP"]:
        md.append(format_entry_row(side, op, entry, "SKIP", extra))
    md.append("")

    md.append(f"## Bucket D: REVIEW (needs human — {len(buckets['REVIEW'])} entries)")
    md.append("")
    md.append("These are ambiguous (LLM top-1 confidence < 0.85 OR margin < 0.15).  Please decide for each:")
    md.append("")
    md.append("| # | Side | Op | Current | LLM top1 | top2 | top3 | Reason |")
    md.append("|---|------|------|---------|----------|------|------|--------|")
    for i, (side, op, entry, extra) in enumerate(buckets["REVIEW"], 1):
        t = entry.get("llm_top3", [])
        def _fmt(idx):
            if idx >= len(t): return "-"
            x = t[idx]
            return f"{x.get('l3_code','?')} ({x.get('confidence',0):.2f})"
        cur = f"{entry.get('current_l3','?')}"
        md.append(f"| {i} | {side} | `{op[:30]}` | {cur} | {_fmt(0)} | {_fmt(1)} | {_fmt(2)} | {extra.get('reason','')} |")

    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"\nWrote:\n  {OUT_MD}\n  {OUT_JSON}")
    print(f"\nAction items for you:")
    print(f"  - {len(buckets['REVIEW'])} REVIEW entries need human decision")
    print(f"  - {len(buckets['STRONG_FIX'])} STRONG_FIX auto-applied (spot-check if you want)")
    print(f"  - {len(buckets['SKIP'])} SKIP auto-applied")
    print(f"  - {len(buckets['AGREE'])} already correct per LLM")


if __name__ == "__main__":
    main()
