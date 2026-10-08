#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""per_class weak-label rule v1 (calibrated on owner Batch-2 verdicts).

Owner taxonomy: "class" has four roles — input attribute labels, output class
space, QA/flag classes, TRUE class-wise iteration. Only the last supports TP.
Per-class ACTION semantics (for each class / within each class / separately for
each class / group-by class) = iteration evidence. "N classes" / class labels /
classification op = presence only. ABSTAIN anchors preserved.
"""
import json, re

ACTION = re.compile(r"(for each|for every|within each|separately for each) (land.?cover )?(class|classes|type|types)"
                    r"|(group|aggregate|aggregated|stratif\w*)[^.]{0,30}by (land.?cover )?class"
                    r"|within specific land.?cover classes", re.I)
ENUM = re.compile(r"\b\d+\s+(distinct\s+)?(classes|land.?cover types)\b"
                  r"|classes? (including|such as|representing|:)"
                  r"|(Matorral|Pastos|Bosque|Herbaceo)", re.I)
ALT = re.compile(r"two time periods|before and after|ascending|descending|polarization"
                 r"|cloud.mask|QA\d+|bit flag", re.I)
CLASSW = re.compile(r"class|land.?cover", re.I)
INPUT_PRODUCT = re.compile(r"using the (ESRI|dynamic world|dw) \w*(LULC|land cover|landcover)", re.I)
CLASSIF_OP = re.compile(r"\b(classif\w*|cluster\w*)\b", re.I)
WORDNUM = re.compile(r"\b(two|three|five|seven|ten)\s+(distinct\s+)?(land\.?cover\s+)?(types|classes)\b", re.I)
WORDNUM_NUM = {"two": 2, "three": 3, "four": 4, "five": 5, "seven": 7, "ten": 10}

def revised_per_class(task, repetition_groups):
    has_action = bool(ACTION.search(task))
    has_enum = bool(ENUM.search(task))
    has_class = bool(CLASSW.search(task))
    has_alt = bool(ALT.search(task))
    counts = [g["repeat"] for g in repetition_groups]
    rep_fams = {g["family"] for g in repetition_groups}
    temporal_alt = "TEMPORAL_FILTER" in rep_fams
    classif_op = any(CLASSIF_OP.search(f or "") for f in rep_fams) or \
                 bool(re.search(r"\b(classif\w*|cluster\w*)\b", task, re.I))
    input_product = bool(INPUT_PRODUCT.search(task))
    if has_enum and not has_action:
        if WORDNUM.search(task):
            has_enum = True

    def alt_counts():
        """Counts the ALT phrase can explain (2 for before/after, two time
        periods, ascending/descending; cloud-masking has no count)."""
        out = []
        if re.search(r"two time periods|before and after|ascending|descending", task, re.I):
            out.append(2)
        m = re.search(r"\b(two|three|four)\s+(time periods|dates|seasons|sensors)", task, re.I)
        if m: out.append(WORDNUM_NUM[m.group(1).lower()])
        return out
    def enum_list_len():
        """Count items in an enumerated class list (types including X, Y, and Z)."""
        m = re.search(r"(types|classes)\s+(including|such as|:)\s+([^.]{10,400}?)[.]", task, re.I)
        if not m: return None
        items = re.split(r",|\band\b", m.group(3))
        items = [x for x in items if x.strip()]
        return len(items) if len(items) >= 2 else None

    alt_n = alt_counts()
    alt_aligned = bool(alt_n) and any(c in alt_n for c in counts)
    enum_n = enum_list_len()
    enum_aligned = bool(enum_n) and any(c == enum_n for c in counts)

    if has_action and has_enum:
        return "TP"
    if has_enum and not has_action and enum_n is not None and not enum_aligned:
        return "FP"   # enumerated output class space; repetition does not follow classes
    if input_product and not has_action:
        return "FP"
    if has_alt and alt_aligned and not has_action:
        return "FP"   # repetition explained by the alternative dimension
    if (has_alt and not alt_aligned) or (temporal_alt and not has_action):
        return "ABSTAIN"
    if classif_op and not has_action:
        return "ABSTAIN"
    if has_class and not has_action:
        return "ABSTAIN" if has_enum else "FP"
    if not has_class:
        return "FP"
    return "ABSTAIN"

OWNER_B2 = {128135: "FP", 40518: "FP", 17639: "TP", 63576: "FP", 29220: "ABSTAIN",
            28513: "FP", 116212: "FP", 38206: "FP", 73950: "FP", 58568: "ABSTAIN",
            3447: "ABSTAIN", 41306: "FP"}

if __name__ == "__main__":
    rows = [json.loads(l) for l in open(r"E:/Route2_Migration_20260928/04_DIAG_WORK/iteration_hint_review_sample_v1_1.jsonl", encoding="utf-8")]
    by_id = {r["source_row_id"]: r for r in rows}
    agree = n = 0
    print("row_id    owner    rule_v1")
    for sid, o in OWNER_B2.items():
        r = by_id[sid]
        v = revised_per_class(r["task"], r["repetition_groups"])
        n += 1; agree += int(v == o)
        mark = "" if v == o else "   <-- differs"
        print(f"{sid:7d} {o:8s} {v:8s}{mark}")
    print(f"\nrule-owner agreement: {agree}/{n}")
