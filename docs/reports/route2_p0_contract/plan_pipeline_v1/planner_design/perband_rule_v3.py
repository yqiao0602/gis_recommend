#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""per_band weak-label rule v3 (calibrated on owner Batch-1 verdicts).

Owner-established standard: "task mentions band" is NOT per_band evidence.
Requires structural three-condition judgment; negative lexicon for proper-noun
band words; index-repetition signature is counter-evidence.
"""
import json, re

PROPER_NEG = [r"C-?band", r"QA\d+\s+band", r"Sentinel-2A/B"]
INDEX = r"\b(NDVI|NDWI|SAVI|MNDWI|EVI|NBR|BI)\b"

def revised_per_band(task, repetition_groups):
    proper = any(re.search(p, task, re.I) for p in PROPER_NEG)
    band_enum = bool(re.search(r"\bB\d{1,2}\b(?:\s*,?\s*\bB\d{1,2}\b)+", task)) or \
                bool(re.search(r"\bred\b[^.]{0,40}\bgreen\b|\bgreen\b[^.]{0,40}\b(blue|red)\b", task, re.I))
    n_enum = len(set(re.findall(r"\bB\d{1,2}\b", task)))
    if n_enum < 2 and re.search(r"\bred\b[^.]{0,40}\bgreen\b|\bgreen\b[^.]{0,40}\b(blue|red)\b", task, re.I):
        n_enum = 3
    iter_phrase = bool(re.search(r"for (each|every) (band|spectral)|per band|each of the .{0,20}bands|bands (separately|respectively)", task, re.I))
    counts = [g["repeat"] for g in repetition_groups]
    align = bool(n_enum >= 2) and any(c in (n_enum, 2 * n_enum) for c in counts)
    rep_fams = {g["family"] for g in repetition_groups}
    idx_signature = (len(set(re.findall(INDEX, task, re.I))) >= 2) or \
                    ("BAND_ARITHMETIC" in rep_fams and re.search(INDEX, task, re.I))
    # index context invalidates B-code enumeration: B4/B8-style codes in index
    # formulas are band identifiers for arithmetic, not bands to iterate over
    if idx_signature:
        band_enum = False
    if proper and not band_enum and not align:
        return "FP"
    if band_enum and (iter_phrase or align):
        return "TP"
    if idx_signature and not band_enum:
        return "FP"
    return "ABSTAIN"

BATCH1_IDS = [91497, 17662, 70561, 93911, 70486, 6460, 112779, 104569, 19803, 127897, 48503, 35762]
OWNER = {91497: "ABSTAIN", 17662: "FP", 70561: "FP", 93911: "FP", 70486: "ABSTAIN",
         6460: "FP", 112779: "ABSTAIN", 104569: "TP", 19803: "FP", 127897: "FP",
         48503: "FP", 35762: "TP"}

if __name__ == "__main__":
    rows = [json.loads(l) for l in open(r"E:/Route2_Migration_20260928/04_DIAG_WORK/iteration_hint_review_sample_v1.jsonl", encoding="utf-8")]
    agree = 0; n = 0
    print("row_id    owner    rule_v3")
    for r in rows:
        if r["source_row_id"] not in BATCH1_IDS: continue
        new = revised_per_band(r["task"], r["repetition_groups"])
        o = OWNER[r["source_row_id"]]
        n += 1; agree += int(new == o)
        mark = "" if new == o else "   <-- differs"
        print(f"{r['source_row_id']:7d} {o:8s} {new:8s}{mark}")
    print(f"\nrule-owner agreement: {agree}/{n}")
