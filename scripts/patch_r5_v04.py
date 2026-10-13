#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-shot patch: r5_requirement_parser_v0.py v0.3 -> v0.4.

v0.4 changes (owner rounds 8-9 reverse controls):
  1. word-boundary on index acronyms (unbounded EVI matched 'deVIation' -> k=32751 FP)
  2. SPATIAL: operation verbs only; scope words demoted to plausible (k=32593)
  3. COMPOSITE: 'composite indices' excluded (k=26102)
  4. TEMPORAL: seasonal mention -> plausible (k=26102)
  5. MASK: metadata cloud-cover filtering -> plausible (k=22822)
  6. STATS: accuracy metrics moved out (ACCURACY_ASSESSMENT gap-signal only; k=30160)
  7. new slot state requirement_uncertain: plausible hits reported, excluded from
     the coverage denominator (owner round-9 fourth state)
"""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "scripts/r5_requirement_parser_v0.py"
src = p.read_text(encoding="utf-8")

old_rules_start = src.index("SLOT_RULES = [")
old_rules_end = src.index("]\n\n\ndef parse_task")
new_rules = '''SLOT_RULES = [
    {"id": "TEMPORAL", "families": ["TEMPORAL_FILTER"],
     "primary_family": "TEMPORAL_FILTER",
     "patterns": [
         (r"\\b(19|20)\\d{2}\\b", "explicit year", "required"),
         (r"annual|monthly", "explicit period adjective", "required"),
         (r"seasonal|growing season", "seasonal analysis mention", "plausible"),
         (r"(January|February|March|April|May|June|July|August|September|October|November|December)\\s*(to|and|-|\\u2013)\\s*(January|February|March|April|May|June|July|August|September|October|November|December|\\d{4})", "explicit month range", "required"),
         (r"\\bfrom\\s+.{0,30}\\bto\\b", "explicit from-to range", "required")]},
    {"id": "MASK", "families": ["MASKING"],
     "primary_family": "MASKING",
     "patterns": [
         (r"\\bmask(?:ed|ing|s)?\\b", "explicit masking", "required"),
         (r"cloud(?!\\s*cover)|shadow", "explicit cloud/shadow handling", "required"),
         (r"cloud\\s*cover", "metadata cloud-percentage filtering", "plausible")]},
    {"id": "INDEX", "families": ["SPECTRAL_INDEX", "BAND_ARITHMETIC"],
     "primary_family": "SPECTRAL_INDEX",
     "conditional_equivalence": "either family may realize an index computation "
        "(candidate-only equivalence; not all band arithmetic is an index)",
     "patterns": [
         (r"\\b(?:NDVI|NDWI|EVI|SAVI)\\b", "named spectral index (word-bounded; "
          "v0.4: unbounded pattern matched 'deVIation')", "required"),
         (r"normalized difference", "normalized-difference formula", "required"),
         (r"\\bindex\\b", "generic index mention", "plausible")]},
    {"id": "SPATIAL", "families": ["SPATIAL_CLIP", "SPATIAL_FILTER"],
     "primary_family": "SPATIAL_CLIP",
     "conditional_equivalence": "clip vs relational filter may differ in "
        "semantics; applicability decided per task wording",
     "patterns": [
         (r"\\bclip(?:ped|s)?\\b", "explicit clip operation", "required"),
         (r"\\bcrop(?:ped)?\\b", "explicit crop operation", "required"),
         (r"watershed|study area|boundary|within the", "spatial scope mention "
          "(scope != operation; v0.4 demoted per k=32593)", "plausible")]},
    {"id": "COMPOSITE", "families": ["AGGREGATION"],
     "primary_family": "AGGREGATION",
     "granularity_note": "AGGREGATION may represent median compositing, but one "
        "aggregation stage cannot be assumed to also cover distinct statistics",
     "patterns": [
         (r"median composite|median .{0,20}composite", "explicit median composite", "required"),
         (r"\\bcomposite\\b(?!\\s+indices?\\b)", "explicit composite (v0.4: "
          "'composite indices' excluded per k=26102)", "required")]},
    {"id": "STATS", "families": ["REGIONAL_STATS", "AGGREGATION"],
     "primary_family": "REGIONAL_STATS",
     "conditional_equivalence": "equivalence plausible in regional-statistics "
        "tasks; generic aggregation is not always regional statistics",
     "patterns": [
         (r"(?<!study )\\bareas?\\b", "area computation (excludes 'study area')", "required"),
         (r"mean .{0,25}per|per[- ]class|time-series", "per-group statistics", "required"),
         (r"kappa|overall accuracy|accuracy assessment", "accuracy metrics - "
          "moved OUT of STATS in v0.4 (represented only by the "
          "ACCURACY_ASSESSMENT gap signal; owner k=30160)", "plausible")]},
    {"id": "CLASSIFY", "families": ["CLASSIFICATION"],
     "primary_family": "CLASSIFICATION",
     "patterns": [
         (r"classif|classification", "explicit classification", "required"),
         (r"cluster|k-means", "explicit clustering", "required"),
         (r"random forest|CART", "explicit classifier", "required"),
         (r"land cover", "land-cover mapping", "required")]},
    {"id": "TERRAIN", "families": ["TERRAIN_DERIVED"],
     "primary_family": "TERRAIN_DERIVED",
     "patterns": [
         (r"slope|hillshade", "terrain derivation", "required")],
     "note": "'elevation' alone is NOT a terrain-derivation requirement (DEM "
             "loading != derivation); fixed after S2 blind-run audit (k=17970)"},
'''
src = src[:old_rules_start] + new_rules + src[old_rules_end:]

old_parse_start = src.index("def parse_task(task: str) -> dict:")
old_parse_end = src.index("def score_candidate")
new_parse = '''def parse_task(task: str) -> dict:
    """Extract requirement slots.

    v0.4 states: pattern hits carry a state - `required` enters the coverage
    denominator; `plausible` marks the slot as requirement_uncertain (reported,
    excluded from scoring) per owner round-9.
    """
    slots, gaps = [], []
    for rule in SLOT_RULES:
        hits_by_state = {"required": [], "plausible": []}
        for pat, label, state in rule["patterns"]:
            for m in re.finditer(pat, task, re.I):
                hits_by_state[state].append(
                    {"rule": rule["id"], "pattern_label": label, "state": state,
                     "hit_text": task[max(0, m.start() - 25):m.end() + 25].strip()})
        if hits_by_state["required"]:
            slots.append({"id": rule["id"], "state": "required",
                          "families": rule["families"],
                          "primary_family": rule.get("primary_family"),
                          "conditional_equivalence": rule.get("conditional_equivalence"),
                          "granularity_note": rule.get("granularity_note"),
                          "hits": hits_by_state["required"]})
        elif hits_by_state["plausible"]:
            slots.append({"id": rule["id"], "state": "requirement_uncertain",
                          "families": rule["families"],
                          "primary_family": rule.get("primary_family"),
                          "hits": hits_by_state["plausible"]})
    for gid, pat in VOCAB_GAP_SIGNALS:
        m = pat.search(task)
        if m:
            gaps.append({"signal": gid, "hit_text": task[max(0, m.start() - 25):m.end() + 25].strip()})
    abstain = not any(s["state"] == "required" for s in slots)
    return {"slots": slots, "vocab_gap_signals": gaps,
            "abstain": abstain,
            "abstain_reason": ("no explicit requirement slot could be parsed "
                               "(F3: abstain when zero required slots)" if abstain else None)}


'''
src = src[:old_parse_start] + new_parse + src[old_parse_end:]

old_sc_start = src.index("    per_slot, covered, missing, coarse = [], 0, 0, 0")
old_sc_end = src.index("    # audit-only: content families with no rule linkage (never penalized)")
new_sc = '''    per_slot, covered, missing, coarse = [], 0, 0, 0
    uncertain = []
    for slot in slot_result["slots"]:
        if slot["state"] == "requirement_uncertain":
            uncertain.append(slot["id"])
            continue
        present = [f for f in slot["families"] if f in fams]
        if not present:
            per_slot.append({"slot": slot["id"], "coverage": "missing",
                             "required_families": slot["families"]})
            missing += 1
        else:
            entry = {"slot": slot["id"], "coverage": "covered",
                     "matched_family": present[0]}
            primary = slot.get("primary_family")
            if primary is not None and present[0] != primary:
                entry["coverage"] = "covered_coarse"  # alternative-family coverage
                entry["note"] = slot.get("conditional_equivalence") or \\
                    slot.get("granularity_note")
                coarse += 1
            if slot["id"] == "COMPOSITE" and slot.get("granularity_note"):
                entry.setdefault("note", slot["granularity_note"])
            per_slot.append(entry)
            covered += 1
'''
src = src[:old_sc_start] + new_sc + src[old_sc_end:]

src = src.replace('''    return {"per_slot": per_slot,
            "covered": covered, "missing": missing, "covered_coarse": coarse,
            "coverage_ratio": (round(covered / denom, 4) if denom else None),''',
'''    return {"per_slot": per_slot,
            "covered": covered, "missing": missing, "covered_coarse": coarse,
            "requirement_uncertain_slots": uncertain,
            "coverage_ratio": (round(covered / denom, 4) if denom else None),''')
src = src.replace('"""r5 requirement parser + coverage scorer v0.3 (RL line, diagnostic).',
                  '"""r5 requirement parser + coverage scorer v0.4 (RL line, diagnostic).')
p.write_text(src, encoding="utf-8")
print("rules rewritten to v0.4")
