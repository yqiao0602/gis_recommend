#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""per_year weak-label rule v1 (calibrated on owner Batch-3 verdicts: 5TP/2FP/5AB).

Strong TP evidence: for each year / each year / annually + yearly processing /
annual composites|mean|maximum + time range / annual + repetition aligned with
year-span. NOT sufficient: bare year ranges (between X and Y), year as dataset
background, seasonal / 16-day / monthly / temporal dynamics, single year.
Y2 is the ABSTAIN anchor: before/after comparison uses the year dimension but
is not per-year workflow iteration.
"""
import json, re
import statistics as st

STRONG_ANNUAL = re.compile(r"\bannual(ly)?\b", re.I)
ITER_YEAR = re.compile(r"for each year|each year in|per year|yearly (mean|median|composite|values)", re.I)
RANGE = re.compile(r"(?:from|between)\s+(\d{4})\s*(?:to|and|-|–)\s*(\d{4})", re.I)
SINGLE_YEAR = re.compile(r"\bin (\d{4})\b", re.I)
SEASON = re.compile(r"seasonal|seasons|spring|summer|autumn|fall|winter|16-day|monthly", re.I)

def per_year_verdict(task, repetition_groups):
    strong = bool(STRONG_ANNUAL.search(task))
    itery = bool(ITER_YEAR.search(task))
    season = bool(SEASON.search(task))
    m = RANGE.search(task)
    span = (int(m.group(2)) - int(m.group(1)) + 1) if m else None
    counts = [g["repeat"] for g in repetition_groups]
    loads = [g["repeat"] for g in repetition_groups if g["family"] in ("RASTER_LOAD", "TEMPORAL_FILTER")]
    # structural alignment: a load/temporal repeat equals the year-span
    align = bool(span and span >= 3 and any(c == span for c in counts))
    if season and not strong:
        # structural season evidence (Y9-style: enumerated seasons x orbit) -> FP;
        # bare seasonal wording -> ABSTAIN (different dimension, not counter-evidence)
        structural_season = bool(re.search(r"(three|two|four) seasonal|ascending and descending|spring.{0,40}summer", task, re.I))
        return "FP" if structural_season else "ABSTAIN"
    if strong or itery:
        return "TP"          # annual composites/mean/maximum + range, or explicit yearly iteration
    if align:
        return "TP"          # repetition count == year span (strong structural match)
    if m and span and span <= 2:
        return "ABSTAIN"     # bare two-year range (Y2/Y11 anchor)
    if re.search(r"\b(in|during)\s+\d{4}\b", task) and not strong:
        return "FP"          # single year (Y1)
    return "ABSTAIN"

OWNER_B3 = {66886: "FP", 122650: "ABSTAIN", 9661: "TP", 76269: "TP", 87169: "ABSTAIN",
            40813: "ABSTAIN", 39969: "TP", 39464: "TP", 13147: "FP", 28778: "TP",
            28819: "ABSTAIN", 28315: "ABSTAIN"}

if __name__ == "__main__":
    rows = [json.loads(l) for l in open(r"E:/Route2_Migration_20260928/04_DIAG_WORK/iteration_hint_review_sample_v1_1.jsonl", encoding="utf-8")]
    by_id = {r["source_row_id"]: r for r in rows}
    agree = n = 0
    print("row_id    owner    rule_v1")
    for sid, o in OWNER_B3.items():
        r = by_id[sid]
        v = per_year_verdict(r["task"], r["repetition_groups"])
        n += 1; agree += int(v == o)
        mark = "" if v == o else "   <-- differs"
        print(f"{sid:7d} {o:8s} {v:8s}{mark}")
    print(f"\nrule-owner agreement: {agree}/{n}")
