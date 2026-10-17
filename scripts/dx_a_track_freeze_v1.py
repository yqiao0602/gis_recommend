#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A-track P0 pre-completion hash freeze (DX_RESEARCH_ROUTE_RULING_OWNER_V1.md
appendix: "freeze profile/pack/prompt/model/decode hashes before card completion";
experiment-design ruling A1: freeze S1 retrieval text + Top-10, cards are the
ONLY variable).

Freezes, at run time:
  1. profile v0_4 full SHA-256 (v0_5+ must be a NEW file; v0_4 never overwritten).
  2. S1-relevant structural snapshot: ops with a top-level `description` key
     (S1-corpus guard, expected 0), ops with layer_c_intent.text, and recomputed
     card-completeness aggregates cross-checked against
     A_TRACK_CARD_COMPLETENESS_BASELINE_V1.json.
  3. SHA-256 of every dx50_full_v1 runs/<task>/S1/retrieval.json - the frozen
     Top-10 anchor that A1 S2 packs must reuse (no S1 re-run for A1).
  4. Recorded DX-50 pack SHA-16 prefixes (server-built; referenced, not
     recomputed locally) + the frozen instrument block (model/decode/encoder).

Output: dx50_full_v1/A_TRACK_P0_HASH_FREEZE_V1.json
"""
import hashlib
import json
from pathlib import Path

from dx_common import DX, PROFILE, MODEL, DECODE, HF_REV, load_profile

FULL = DX / "dx50_v1/dx50_full_v1"
BASELINE = FULL / "A_TRACK_CARD_COMPLETENESS_BASELINE_V1.json"
OUT = FULL / "A_TRACK_P0_HASH_FREEZE_V1.json"

# Server-built pack SHA-16 prefixes as recorded in the DX-50 execution log
# (plan_of_record). Not recomputed here: packs were not mirrored locally.
PACKS = {
    "S0_pack": {"sha16_prefix": "335a8b6f", "note": "50 items; items == frozen 6896f542 baseline"},
    "S2_pack": {"sha16_prefix": "a5370692", "note": "293 items; excluded_s0_tasks={T-050}"},
    "S3_pack": {"sha16_prefix": "b8c8af07", "note": "49 items"},
}


def full_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def recompute_completeness(prof):
    agg = {"total": len(prof), "params_layer": 0, "outputs_layer": 0,
           "fully_bare": 0}
    by_provider = {}
    desc_keys = 0
    intent_n = 0
    for oid, e in prof.items():
        lb = e.get("layer_b_params") or {}
        has_p = bool(lb.get("parameters"))
        has_o = bool(lb.get("outputs"))
        agg["params_layer"] += has_p
        agg["outputs_layer"] += has_o
        agg["fully_bare"] += (not has_p and not has_o)
        if "description" in e:
            desc_keys += 1
        if (e.get("layer_c_intent") or {}).get("text"):
            intent_n += 1
        p = by_provider.setdefault(e.get("provider", "?"),
                                   {"n": 0, "params": 0, "outputs": 0})
        p["n"] += 1
        p["params"] += has_p
        p["outputs"] += has_o
    return agg, by_provider, desc_keys, intent_n


def main():
    prof = load_profile()
    agg, by_provider, desc_keys, intent_n = recompute_completeness(prof)

    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    def prov_trip(p):
        return {k: p.get(k) for k in ("n", "params", "outputs")}

    bl_prov = baseline["by_provider"]
    bl_base = baseline["baseline"]
    recompute_ext = dict(agg,
                         no_params=agg["total"] - agg["params_layer"],
                         no_outputs=agg["total"] - agg["outputs_layer"])
    common = {k: v for k, v in bl_base.items() if k in recompute_ext}
    checks = {
        "baseline_file_sha256": full_sha(BASELINE),
        "aggregate_match": (
            common == {k: recompute_ext[k] for k in common}
            and set(bl_base) <= set(recompute_ext)),
        "provider_match": all(
            prov_trip(bl_prov[name]) == prov_trip(by_provider.get(name, {}))
            for name in bl_prov),
        "otb_all_bare": (by_provider.get("otb", {}).get("params") == 0
                         and by_provider.get("otb", {}).get("outputs") == 0),
        "grass7_outputs_all_missing": by_provider.get("grass7", {}).get("outputs") == 0,
    }

    retrievals = {}
    for f in sorted((FULL / "runs").glob("*/S1/retrieval.json")):
        retrievals[f.parent.parent.name] = full_sha(f)

    manifest = {
        "date": "2026-10-17",
        "purpose": "A-track P0 pre-completion freeze (OTB 115 cards next; "
                   "A1 = card-completion experiment, S1 retrieval + Top-10 frozen)",
        "rules": [
            "profile v0_4 is immutable: any completed-card version is a NEW file "
            "(v0_5+), never an overwrite",
            "A1 S2 packs must reuse the frozen retrieval.json Top-10 (no S1 re-run)",
            "card completion must NOT write a top-level `description` key "
            "(S1 corpus silent-change guard); descriptions go to layer_c_intent",
        ],
        "profile": {
            "path": "route2_training/profile/qgis_operator_capability_profile_v0_4.json",
            "sha256": full_sha(PROFILE),
        },
        "s1_guard_snapshot": {
            "ops_with_top_level_description_key": desc_keys,
            "expected": 0,
            "ops_with_layer_c_intent_text": intent_n,
            "n_operators": agg["total"],
        },
        "completeness_recomputed": agg,
        "baseline_cross_check": checks,
        "frozen_retrieval_top10": {
            "n_tasks": len(retrievals),
            "retrieval_json_sha256": retrievals,
        },
        "recorded_packs": PACKS,
        "instrument": {"model": MODEL, "hf_revision": HF_REV, "decode": DECODE,
                       "encoder": "pca_data_ref/minilm", "top_k": 10},
    }
    OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print("freeze written:", OUT)
    print("profile sha256:", manifest["profile"]["sha256"])
    print("desc_keys:", desc_keys, "| intent:", intent_n, "| ops:", agg["total"])
    print("baseline aggregate_match:", checks["aggregate_match"],
          "| provider_match:", checks["provider_match"],
          "| otb_all_bare:", checks["otb_all_bare"],
          "| grass7_outputs_all_missing:", checks["grass7_outputs_all_missing"])
    print("retrieval.json frozen:", len(retrievals))


if __name__ == "__main__":
    main()
