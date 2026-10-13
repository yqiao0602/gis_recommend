#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-shot patch: r5_requirement_parser v0.4.1 -> v0.5 (owner round-11 approved).

L1: `area` requires statistical-action context ("deforested areas" no longer
    triggers STATS; k=9210 false requirement eliminated).
L2: INDEX definition FROZEN as "computing a NEW spectral index from bands".
    Product-band reading/scaling (MOD13A1 etc.) -> requirement_determination =
    not_required (k=9854). Task ambiguous between compute vs product use ->
    uncertain. Named-index + raw-band/compute context -> required.
L3: every evaluated slot emits requirement_determination
    (required / not_required / uncertain); only `required` enters the coverage
    denominator. not_required and uncertain never enter omission or coverage
    numerators (owner statistical-caliber requirement).
"""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "scripts/r5_requirement_parser_v0.py"
src = p.read_text(encoding="utf-8")

# ---------------- L1: STATS area pattern -> statistical-action context ----------------
src = src.replace(
    '(r"(?<!study )\\bareas?\\b", "area computation (excludes \'study area\')", "required"),',
    '(r"(?:calculat|comput|estimat|generat)\\w*\\W{0,20}\\bareas?\\b|'
    '\\bareas?\\b\\W{0,20}(?:calculation|estimates|statistics|per\\b)", '
    '"area computation with statistical-action context (v0.5 L1: bare area '
    'mentions, e.g. land-cover class names, do NOT trigger; k=9210)", "required"),')

# ---------------- L2: INDEX patterns -> determination-based ----------------
old_index = '''    {"id": "INDEX", "families": ["SPECTRAL_INDEX", "BAND_ARITHMETIC"],
     "primary_family": "SPECTRAL_INDEX",
     "conditional_equivalence": "either family may realize an index computation "
        "(candidate-only equivalence; not all band arithmetic is an index)",
     "patterns": [
         (r"\\b(?:NDVI|NDWI|EVI|SAVI)\\b", "named spectral index (word-bounded; "
          "v0.4: unbounded pattern matched 'deVIation')", "required"),
         (r"normalized difference", "normalized-difference formula", "required"),
         (r"\\bindex\\b", "generic index mention", "plausible")]},'''
new_index = '''    {"id": "INDEX", "families": ["SPECTRAL_INDEX", "BAND_ARITHMETIC"],
     "primary_family": "SPECTRAL_INDEX",
     "definition": "v0.5 (owner round-11, FROZEN): INDEX = computing a NEW "
        "spectral index from bands. Reading/scaling a product-provided index "
        "band does NOT require INDEX (recorded as not_required); ambiguous "
        "tasks are recorded as uncertain",
     "conditional_equivalence": "either family may realize an index computation "
        "(candidate-only equivalence; not all band arithmetic is an index)",
     "patterns": [
         (r"\\b(?:NDVI|NDWI|EVI|SAVI|UVVR)\\b", "named spectral index "
          "(word-bounded)", "required"),
         (r"normalized difference", "normalized-difference formula", "required"),
         (r"\\bindex\\b", "generic index mention", "plausible")],
     "compute_context": r"comput|calculat|deriv|formula|band ratio|ratio of|"
        r"from (?:red|nir|near-?infrared|green|swir)|(?:sr|b)_b?\\d|reflectance",
     "product_context": r"MOD13\\w*|MYD13\\w*|product.{0,20}band|"
        r"scaled\\s+\\w+\\s*values|existing\\s+(?:\\w+\\s+)?index"},'''
src = src.replace(old_index, new_index)

# ---------------- parse_task: INDEX determination + requirement_determination ----------------
old_parse = '''    slots, gaps = [], []
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
                          "hits": hits_by_state["plausible"]})'''
new_parse = '''    slots, gaps = [], []
    for rule in SLOT_RULES:
        hits_by_state = {"required": [], "plausible": []}
        for pat, label, state in rule["patterns"]:
            for m in re.finditer(pat, task, re.I):
                hits_by_state[state].append(
                    {"rule": rule["id"], "pattern_label": label, "state": state,
                     "hit_text": task[max(0, m.start() - 25):m.end() + 25].strip()})
        determination = None
        if rule["id"] == "INDEX" and (hits_by_state["required"] or
                                      hits_by_state["plausible"]):
            # L2 (owner round-11): compute-vs-product-use determination
            compute = re.search(rule["compute_context"], task, re.I)
            product = re.search(rule["product_context"], task, re.I)
            if product and not compute:
                determination = "not_required"
                note = ("product-provided index band reading/scaling does not "
                        "require INDEX computation (v0.5 definition)")
            elif compute:
                determination = "required"
                note = None
            else:
                determination = "uncertain"
                note = ("task does not clarify compute-vs-product use; both "
                        "interpretations plausible")
            hits = hits_by_state["required"] or hits_by_state["plausible"]
            slots.append({"id": rule["id"],
                          "state": ("required" if determination == "required"
                                    else "requirement_uncertain"),
                          "requirement_determination": determination,
                          "determination_note": note,
                          "families": rule["families"],
                          "primary_family": rule.get("primary_family"),
                          "conditional_equivalence": rule.get("conditional_equivalence"),
                          "hits": hits})
            continue
        if hits_by_state["required"]:
            slots.append({"id": rule["id"], "state": "required",
                          "requirement_determination": "required",
                          "families": rule["families"],
                          "primary_family": rule.get("primary_family"),
                          "conditional_equivalence": rule.get("conditional_equivalence"),
                          "granularity_note": rule.get("granularity_note"),
                          "hits": hits_by_state["required"]})
        elif hits_by_state["plausible"]:
            slots.append({"id": rule["id"], "state": "requirement_uncertain",
                          "requirement_determination": "uncertain",
                          "families": rule["families"],
                          "primary_family": rule.get("primary_family"),
                          "hits": hits_by_state["plausible"]})'''
src = src.replace(old_parse, new_parse)

# ---------------- score_candidate: skip not_required determination ----------------
src = src.replace('''    for slot in slot_result["slots"]:
        if slot["state"] == "requirement_uncertain":
            uncertain.append(slot["id"])
            continue''',
'''    for slot in slot_result["slots"]:
        if slot.get("requirement_determination") == "not_required":
            uncertain.append(slot["id"])  # not_required: excluded, reported
            continue
        if slot["state"] == "requirement_uncertain":
            uncertain.append(slot["id"])
            continue''')

src = src.replace('"""r5 requirement parser + coverage scorer v0.4.1 (RL line, diagnostic).',
                  '"""r5 requirement parser + coverage scorer v0.5 (RL line, diagnostic).')
p.write_text(src, encoding="utf-8")
print("rules rewritten to v0.5 (L1 contextual area; L2 INDEX determination; L3 requirement_determination field)")
