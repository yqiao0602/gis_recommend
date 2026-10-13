#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the r5 round-2 SYNTHETIC validation packet (owner round-7).

Three sample types per owner ruling:
  Type A (reasonable complete alternatives) - tests multisolution tolerance /
          false-punishing. Canonical-family and alternative-family variants.
  Type B (clear single-capability omissions) - tests omission detection.
  Type C (unrepresentable / semantically vague) - tests ABSTAIN + vocab-gap.

ALL candidates are synthetic and labeled `synthetic`; they test RULE LOGIC,
not real-distribution reliability (owner round-7). Construction intent is
sealed in the JSON; the MD sheet is blind (task + stages, shuffled).

Rules frozen at v0.3 (primary_family semantics + CHANGE_DETECTION gap detector)
BEFORE this packet was scored. Self-check against construction intent is
provisional; the authoritative comparison is the owner's blind labels.
"""
import json
import random
from pathlib import Path

RL = Path(__file__).resolve().parents[1] / \
    "docs/reports/route2_p0_contract/plan_pipeline_v1/rl_line"
random.seed(20261013)


def bp(*stages):
    return json.dumps({"stages": [{"seq": i + 1, "family": f, "repeat": 1}
                                   for i, f in enumerate(stages)],
                       "repetition_groups": []}, ensure_ascii=False)


# ---------------- synthetic tasks (clearly marked synthetic) ----------------
T_NDWI = ("Task: [SYNTHETIC] Reservoir surface water mapping\n"
          "Compute the NDWI from green and near-infrared bands of Sentinel-2 "
          "imagery acquired between March and May 2021, apply cloud masking, "
          "clip to the reservoir boundary, and export a median NDWI composite "
          "for the study period.")
T_CROP = ("Task: [SYNTHETIC] Parcel crop classification\n"
          "Classify crops using Sentinel-2 imagery from April to October 2022, "
          "train a random forest classifier on labeled parcels, and export the "
          "classification with per-class area statistics.")
T_CHANGE = ("Task: [SYNTHETIC] Urban expansion mapping\n"
            "Detect urban expansion between 2010 and 2020 using Landsat "
            "imagery and produce an expansion map with yearly built-up area "
            "statistics.")
T_VAGUE = ("Task: [SYNTHETIC] Imagery screening\n"
           "Perform a suitable analysis of the available imagery for the "
           "region of interest.")

# construction intent (sealed): expected r5 behavior per rules v0.3
INTENT = [
    {"id": "A1_canonical_complete", "type": "A_reasonable_complete",
     "task": T_NDWI,
     "stages": ["RASTER_LOAD", "TEMPORAL_FILTER", "MASKING", "BAND_ARITHMETIC",
                "SPATIAL_CLIP", "AGGREGATION", "EXPORT_OUTPUT"],
     "expected": "complete_coarse_uncertain (INDEX via BAND_ARITHMETIC = "
                 "alternative family; owner: not all band arithmetic is an "
                 "index) - NOT omission",
     "intent": "all required capabilities present; r5 must NOT false-punish; "
               "coarse uncertainty on INDEX is the honest conservative call"},
    {"id": "A2_alternative_complete", "type": "A_reasonable_complete",
     "task": T_NDWI,
     "stages": ["RASTER_LOAD", "TEMPORAL_FILTER", "MASKING", "SPECTRAL_INDEX",
                "SPATIAL_FILTER", "AGGREGATION", "EXPORT_OUTPUT"],
     "expected": "complete_coarse_uncertain (SPATIAL via alternative family) - "
                 "NOT omission",
     "intent": "alternative families for SPATIAL (SPATIAL_FILTER) and INDEX "
               "(SPECTRAL_INDEX as primary) - multisolution tolerance test; "
               "AGGREGATION retained: median composite has no alternative "
               "family (REGIONAL_STATS cannot realize compositing)"},
    {"id": "A4_crop_complete_coarse", "type": "A_reasonable_complete",
     "task": T_CROP,
     "stages": ["RASTER_LOAD", "TEMPORAL_FILTER", "CLASSIFICATION",
                "AGGREGATION", "EXPORT_OUTPUT"],
     "expected": "complete_coarse_uncertain + ACCURACY_ASSESSMENT gap signal "
                 "(per-class area via AGGREGATION is alternative-family "
                 "coverage; accuracy is unrepresentable) - NOT omission",
     "intent": "partially_scorable task: coverage of expressible requirements "
               "with honest uncertainty, gap signal for accuracy"},
    {"id": "A3_iterative_boundary", "type": "C_boundary_untransparent",
     "task": T_NDWI,
     "stages": ["RASTER_LOAD", "TEMPORAL_FILTER", "MASKING", "ITERATIVE_APPLY",
                "SPATIAL_CLIP", "AGGREGATION", "EXPORT_OUTPUT"],
     "expected": "incomplete (missing INDEX) per the frozen "
                 "representation-sufficiency caliber",
     "intent": "NDWI possibly wrapped inside ITERATIVE_APPLY - unknowable "
               "from stages; documents the gray zone (not counted in the "
               "false-punish denominator)"},
    {"id": "B1_drop_mask", "type": "B_clear_omission",
     "task": T_NDWI,
     "stages": ["RASTER_LOAD", "TEMPORAL_FILTER", "BAND_ARITHMETIC",
                "SPATIAL_CLIP", "AGGREGATION", "EXPORT_OUTPUT"],
     "expected": "incomplete, missing MASK",
     "intent": "cloud masking removed - omission detection"},
    {"id": "B2_drop_index", "type": "B_clear_omission",
     "task": T_NDWI,
     "stages": ["RASTER_LOAD", "TEMPORAL_FILTER", "MASKING", "SPATIAL_CLIP",
                "AGGREGATION", "EXPORT_OUTPUT"],
     "expected": "incomplete, missing INDEX",
     "intent": "NDWI computation removed - omission detection"},
    {"id": "B3_drop_temporal", "type": "B_clear_omission",
     "task": T_NDWI,
     "stages": ["RASTER_LOAD", "MASKING", "BAND_ARITHMETIC", "SPATIAL_CLIP",
                "AGGREGATION", "EXPORT_OUTPUT"],
     "expected": "incomplete, missing TEMPORAL",
     "intent": "date range removed - omission detection"},
    {"id": "C1_change_detection", "type": "C_unrepresentable",
     "task": T_CHANGE,
     "stages": ["RASTER_LOAD", "TEMPORAL_FILTER", "CLASSIFICATION",
                "AGGREGATION", "EXPORT_OUTPUT"],
     "expected": "coverage verdict complete_coarse_uncertain AND "
                 "CHANGE_DETECTION gap signal fires (together = the "
                 "partially_scorable task classification in the audit; "
                 "expansion mapping itself is unrepresentable)",
     "intent": "tests vocab-gap handling on a task whose CORE capability has "
               "no family"},
    {"id": "C2_vague_abstain", "type": "C_vague",
     "task": T_VAGUE,
     "stages": ["RASTER_LOAD", "SPATIAL_FILTER", "AGGREGATION"],
     "expected": "abstain (no explicit requirement slot parseable)",
     "intent": "vague task - F3 certainty abstain"},
]

# ---- blind MD sheet (shuffle) ----
md = ["# r5 合成正样本盲评包 v1（第二轮，synthetic）", "",
      "> **全部候选为合成样本**（规则逻辑测试，不代表真实分布可靠性；owner 七轮）。",
      "> 规则版本冻结 v0.3；标注口径沿用冻结协议（4 主标签 + 两证据字段）。",
      "> 每项给一个主判定；`both_reasonable` 仅用于组内比较类条目。", "",
      "| 判定 | 含义 |", "|---|---|",
      "| `omission` | 缺少任务明确需要的能力（注明缺什么） |",
      "| `unsupported` | 含无依据阶段（注明） |",
      "| `complete_reasonable` | 满足任务全部明确需求（多解容忍：等价/替代路径也算） |",
      "| `unclear` | 无法判定 |", "",
      "---"]
order = list(range(len(INTENT)))
random.shuffle(order)
for slot, ii in enumerate(order, 1):
    it = INTENT[ii]
    md += [f"## S{slot}（{it['type']}）", "", "**任务全文：**", "", it["task"], "",
           "### 候选", "```",
           *[f"{i+1}. {f}" for i, f in enumerate(it["stages"])], "```",
           "**判定：** ______（附注：______）", ""]
(RL / "R5_SYNTHETIC_PACKET_V1.md").write_text("\n".join(md), encoding="utf-8")

json.dump({"synthetic": True, "rules_version": "v0.3 (frozen)",
           "blind": True, "count": len(INTENT), "items": INTENT},
          open(RL / "r5_synthetic_packet_v1.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"synthetic packet: {len(INTENT)} items; MD sheet "
      f"R5_SYNTHETIC_PACKET_V1.md (shuffled S1-S{len(INTENT)})")

# ---- self-check (provisional; authoritative = owner blind labels) ----
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from r5_requirement_parser_v0 import evaluate_pair

ok = 0
print("\n=== self-check vs construction intent (PROVISIONAL) ===")
for it in INTENT:
    blueprint = json.loads(bp(*it["stages"]))
    res = evaluate_pair(it["task"], blueprint)
    verdict = res["score"]["coverage_verdict"]
    gaps = [g["signal"] for g in res["parse"]["vocab_gap_signals"]]
    exp = it["expected"]
    hit = verdict in exp or (verdict == "abstain" and "abstain" in exp) or \
          (verdict.startswith("complete") and "NOT omission" in exp) or \
          (verdict == "incomplete" and "incomplete" in exp)
    ok += hit
    print(f"[{'OK' if hit else 'CHECK'}] {it['id']}: r5={verdict} "
          f"missing={[s['slot'] for s in res['score']['per_slot'] if s['coverage'] == 'missing']} "
          f"gaps={gaps} | expected: {exp}")
print(f"self-check: {ok}/{len(INTENT)} consistent with construction intent")
