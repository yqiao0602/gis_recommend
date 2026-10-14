#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""r5 requirement parser + coverage scorer v0.6 (RL line, diagnostic).

v0.3 (frozen before synthetic round-2 per owner round-7): primary_family
per slot - coverage via the primary family counts as plain `covered`;
coverage via an alternative family is `covered_coarse` (uncertain).

Implements R5_DESIGN_V0.md as amended by owner round-6 review:
  F1  three requirement states per slot: required / plausible / (per-parser)
      abstain - v0 scores coverage ONLY on `required` slots.
  F2  conditional equivalence: family alternatives are recorded per slot with
      an applicability note; they are NOT unconditional merges.
  F3  certainty-based abstain: r5 abstains (masked) when NO explicit required
      slot can be parsed - a single clear requirement is a valid, scoreable
      case; trigger counts are never used as an uncertainty proxy.
  F4  full audit trail: every slot records hit text, rule id, state, family
      alternatives + applicability note; abstain carries its reason.

Additional (owner blind-label finding, k=17970): a required capability with NO
representable family in the stage vocabulary is emitted as
`unrepresentable_required` - excluded from candidate scoring, reported as
vocabulary-expressiveness evidence (never counted against a candidate).

Pipeline families (LOAD/EXPORT/COLLECTION_MGMT/GEOMETRY_DEFINE) never enter the
requirement set. `unsupported` detection is audit-only in v0: content families
with no rule linkage are logged, never penalized.

Deterministic. No learning components, no LLM calls.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PIPELINE_FAMILIES = {"RASTER_LOAD", "VECTOR_LOAD", "EXPORT_OUTPUT",
                     "COLLECTION_MGMT", "GEOMETRY_DEFINE"}

# Unrepresentable-capability detectors (vocab-gap evidence only; never scored).
VOCAB_GAP_SIGNALS = [
    ("PROFILE_TRANSECT", re.compile(r"profile|transect|along a? ?specified longitudinal", re.I)),
    ("CHART_PLOT", re.compile(r"chart|plot|visualiz|time-series|scatter", re.I)),
    ("ACCURACY_ASSESSMENT", re.compile(r"kappa|overall accuracy|accuracy assessment", re.I)),
    ("CHANGE_DETECTION", re.compile(r"change detection|expansion map|urban expansion|deforestation|change map", re.I)),
]

SLOT_RULES = [
    {"id": "TEMPORAL", "families": ["TEMPORAL_FILTER"],
     "primary_family": "TEMPORAL_FILTER",
     "patterns": [
         (r"\b(19|20)\d{2}\b", "explicit year", "required"),
         (r"annual|monthly", "explicit period adjective", "required"),
         (r"seasonal|growing season", "seasonal analysis mention", "plausible"),
         (r"(January|February|March|April|May|June|July|August|September|October|November|December)\s*(to|and|-|\u2013)\s*(January|February|March|April|May|June|July|August|September|October|November|December|\d{4})", "explicit month range", "required"),
         (r"\bfrom\s+.{0,30}\bto\b", "explicit from-to range", "required")]},
    {"id": "MASK", "families": ["MASKING"],
     "primary_family": "MASKING",
     "patterns": [
         (r"\bmask(?:ed|ing|s)?\b", "explicit masking", "required"),
         (r"cloud(?!\s*cover)|shadow", "explicit cloud/shadow handling", "required"),
         (r"cloud\s*cover", "metadata cloud-percentage filtering", "plausible")]},
    {"id": "INDEX", "families": ["SPECTRAL_INDEX", "BAND_ARITHMETIC"],
     "primary_family": "SPECTRAL_INDEX",
     "definition": "v0.5 (owner round-11, FROZEN): INDEX = computing a NEW "
        "spectral index from bands. Reading/scaling a product-provided index "
        "band does NOT require INDEX (recorded as not_required); ambiguous "
        "tasks are recorded as uncertain",
     "conditional_equivalence": "either family may realize an index computation "
        "(candidate-only equivalence; not all band arithmetic is an index)",
     "patterns": [
         (r"\b(?:NDVI|NDWI|EVI|SAVI|UVVR)\b", "named spectral index "
          "(word-bounded)", "required"),
         (r"normalized difference", "normalized-difference formula", "required"),
         (r"\bindex\b", "generic index mention", "plausible")],
     "compute_context": r"band ratio|normalized difference|ratio of\s+\w+"
        r"|(?:from|using)\s+(?:the\s+)?(?:red|nir|near-?infrared|green|swir|shortwave)"
        r"|(?:sr|b)_b?\d|reflectance"
        r"|comput(?:e|es|ed)\s+(?:the\s+)?(?:NDVI|NDWI|EVI|SAVI)"
        r"|deriv\w*\s+(?:the\s+)?(?:NDVI|NDWI|EVI|SAVI)"
        r"|(?:NDVI|NDWI|EVI|SAVI)\b.{0,30}?derived\s+from",
     "product_context": r"MOD13\w*|MYD13\w*|product.{0,20}band|"
        r"scaled\s+\w+\s*values|existing\s+(?:\w+\s+)?index"},
    {"id": "SPATIAL", "families": ["SPATIAL_CLIP", "SPATIAL_FILTER"],
     "primary_family": "SPATIAL_CLIP",
     "conditional_equivalence": "clip vs relational filter may differ in "
        "semantics; applicability decided per task wording",
     "patterns": [
         (r"\bclip(?:ped|s)?\b", "explicit clip operation", "required"),
         (r"\bcropp(?:ed|ing)\b|\bcrops?\s+to\b", "explicit crop operation "
          "(v0.4.1: noun 'crops' excluded per A4 polysemy)", "required"),
         (r"watershed|study area|boundary|within the", "spatial scope mention "
          "(scope != operation; v0.4 demoted per k=32593)", "plausible")]},
    {"id": "COMPOSITE", "families": ["AGGREGATION"],
     "primary_family": "AGGREGATION",
     "granularity_note": "AGGREGATION may represent median compositing, but one "
        "aggregation stage cannot be assumed to also cover distinct statistics",
     "patterns": [
         (r"median composite|median .{0,20}composite", "explicit median composite", "required"),
         (r"\bcomposite\b(?!\s+indices?\b)", "explicit composite (v0.4: "
          "'composite indices' excluded per k=26102)", "required")]},
    {"id": "STATS", "families": ["REGIONAL_STATS", "AGGREGATION"],
     "primary_family": "REGIONAL_STATS",
     "conditional_equivalence": "equivalence plausible in regional-statistics "
        "tasks; generic aggregation is not always regional statistics",
     "patterns": [
         (r"(?:calculat|comput|estimat|generat)\w*\W{0,20}\bareas?\b|\bareas?\b\W{0,20}(?:calculation|estimates|statistics|per\b)", "area computation with statistical-action context (v0.5 L1: bare area mentions, e.g. land-cover class names, do NOT trigger; k=9210)", "required"),
         (r"mean\s+\w{0,20}\s*(?:NDVI|NDWI|EVI|values?)\w*\s+(?:within|inside|over|across)", "mean-statistic over a region (v0.5.1: restored k=9854 STATS - 'Calculate the mean NDVI within a 10 km radius area' had the computation verb outside the L1 context window)", "required"),
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
     "scoring": "unscored_representation_boundary",  # v0.6, owner-approved:
     # stage-family summaries cannot reliably adjudicate terrain processing;
     # excluded from coverage numerator AND denominator; requirement label
     # preserved for audit; restore scoring when a terrain family or reliable
     # dataflow rule exists
     "patterns": [
         (r"slope|hillshade", "terrain derivation", "required")],
     "note": "'elevation' alone is NOT a terrain-derivation requirement (DEM "
             "loading != derivation); fixed after S2 blind-run audit (k=17970)"},
]


def parse_task(task: str) -> dict:
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
        determination = None
        if rule["id"] == "INDEX" and (hits_by_state["required"] or
                                      hits_by_state["plausible"]):
            # L2 (owner round-11): product use beats generic compute verbs
            # ("Calculate the mean NDVI" from MOD13A1 = product use, not
            # index computation); raw-band/formula/direct-compute evidence
            # establishes genuine index computation.
            product = re.search(rule["product_context"], task, re.I)
            compute = re.search(rule["compute_context"], task, re.I)
            if product:
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
                          "scoring": rule.get("scoring", "scored"),
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


def score_candidate(slot_result: dict, blueprint: dict) -> dict:
    """Coverage over REQUIRED slots only. Unrepresentable capabilities are not
    in the slot table; vocab-gap signals are reported separately. Same-family
    slots: covered_coarse + uncertainty flag (never claimed as verified)."""
    fams = {s.get("family") for s in blueprint.get("stages", [])
            if isinstance(s, dict) and isinstance(s.get("family"), str)}
    per_slot, covered, missing, coarse = [], 0, 0, 0
    uncertain = []
    unscored = []
    for slot in slot_result["slots"]:
        if slot.get("scoring") == "unscored_representation_boundary":
            unscored.append(slot["id"])  # v0.6: unadjudicable at stage granularity
            continue
        if slot.get("requirement_determination") == "not_required":
            uncertain.append(slot["id"])  # not_required: excluded, reported
            continue
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
                entry["note"] = slot.get("conditional_equivalence") or \
                    slot.get("granularity_note")
                coarse += 1
            if slot["id"] == "COMPOSITE" and slot.get("granularity_note"):
                entry.setdefault("note", slot["granularity_note"])
            per_slot.append(entry)
            covered += 1
    # audit-only: content families with no rule linkage (never penalized)
    linked = set()
    for slot in slot_result["slots"]:
        linked.update(slot["families"])
    unlinked = sorted(f for f in fams
                      if f not in linked and f not in PIPELINE_FAMILIES)
    denom = covered + missing
    # Owner round-6 semantics: covered_coarse (single coarse family standing in
    # for a requirement) is NOT verified coverage - 'complete' requires all
    # slots covered unconditionally.
    if denom == 0:
        verdict = "abstain"
    elif missing == 0 and coarse == 0:
        verdict = "complete"
    elif missing == 0:
        verdict = "complete_coarse_uncertain"
    else:
        verdict = "incomplete"
    return {"per_slot": per_slot,
            "covered": covered, "missing": missing, "covered_coarse": coarse,
            "unscored_representation_boundary_slots": unscored,
            "requirement_uncertain_slots": uncertain,
            "coverage_ratio": (round(covered / denom, 4) if denom else None),
            "coverage_verdict": verdict,
            "unlinked_content_families_audit_only": unlinked}


def evaluate_pair(task: str, blueprint: dict) -> dict:
    pr = parse_task(task)
    sc = score_candidate(pr, blueprint)
    return {"parse": pr, "score": sc}


def load_blueprint(pred_text: str):
    try:
        b = json.loads(pred_text)
        return b if isinstance(b, dict) else None
    except Exception:
        return None


def main(argv):
    RL = Path(__file__).resolve().parents[1] / \
        "docs/reports/route2_p0_contract/plan_pipeline_v1/rl_line"
    packet = json.loads((RL / "r5_validation_packet_v1.json").read_text(encoding="utf-8"))
    labels = json.loads((RL / "r5_labels_frozen_v1.json").read_text(encoding="utf-8"))
    out = {"label": "r5_v0_blind_run_vs_owner_labels", "groups": []}
    for item in packet["items"]:
        k = str(item["k"])
        pr = parse_task(item["task"])
        cands = []
        for c in item["candidates"]:
            b = load_blueprint(next(p["pred_text"] for p in json.loads(
                (RL / "s2_dryrun/preds.json").read_text(encoding="utf-8"))
                if p["k"] == item["k"] and p["cand"] == c["true_cand"]))
            sc = score_candidate(pr, b) if b else {"coverage_verdict": "unparseable"}
            cands.append({"letter": c["letter"], "true_cand": c["true_cand"],
                          "r5": sc, "owner_label": "omission"})
        lab = next(l for l in labels["items"] if str(l["k"]) == k)
        out["groups"].append({
            "k": item["k"], "band": item["band"],
            "required_slots": [s["id"] for s in pr["slots"]],
            "slot_detail": pr["slots"], "vocab_gap_signals": pr["vocab_gap_signals"],
            "abstain": pr["abstain"], "abstain_reason": pr["abstain_reason"],
            "candidates": cands,
            "owner_omission_detail": lab["omission_detail"],
            "owner_group_note": lab["group_note"]})
    (RL / "r5_v0_blind_run_v1.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    # console summary
    for g in out["groups"]:
        cov = [c["r5"].get("coverage_verdict") for c in g["candidates"]]
        print(f"k={g['k']}: required={g['required_slots']} gaps={g['vocab_gap_signals']} "
              f"abstain={g['abstain']} verdicts={cov}")
    print("written: r5_v0_blind_run_v1.json")


if __name__ == "__main__":
    main(sys.argv[1:])
