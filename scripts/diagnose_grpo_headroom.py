#!/usr/bin/env python3
"""GRPO headroom diagnosis: can beam search produce better vector chains?
For each of 591 vector described tasks, runs beam search and scores
top1 vs group-best to determine if GRPO training would help.
"""

from __future__ import annotations
import json, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path: sys.path.insert(0, str(SRC))
import torch
from gis_recommend.inference.infer_l3_candidates_v4 import L3SequenceInferencerV4
from gis_recommend.config.transformer_config import DEVICE, V4_6_TRANSFORMER_CHECKPOINT_DIR, V4_QG_TASK_TYPE_VOCAB_PATH

DESCRIBED = ROOT / "outputs_v2" / "qgis_vector_chain_described.jsonl"
CKPT = V4_6_TRANSFORMER_CHECKPOINT_DIR / "best_model.pth"
# Try DPO checkpoint
DPO_CKPT = ROOT / "outputs_v2" / "transformer_checkpoints_v4_6_preference_dpo_v2_quality_cycle_fixed" / "best_preference_model.pth"
if DPO_CKPT.exists(): CKPT = DPO_CKPT

VECTOR_KW = {"buffer","clip","dissolve","intersection","difference","mergevectorlayers",
    "extractbyexpression","extractbylocation","joinattributesbylocation",
    "joinattributestable","reprojectlayer","fixgeometries","simplifygeometries",
    "snapgeometries","creategrid","joinbynearest","centroids","countpointsinpolygon",
    "polygonstolines","splitwithlines","refactorfields","symmetricaldifference"}

def score_candidate(tokens, prefer="vector"):
    n=len(tokens)
    if n<2: return 0.0
    vc=sum(1 for t in tokens if t>=0)  # content tokens
    dup=len(set(tokens))/max(n,1)
    return 0.4*dup + 0.3*min(n/6.0,1.0) + 0.3*(1.0 if prefer=="vector" else 0.5)

def main():
    records = [json.loads(line) for line in open(DESCRIBED,"r",encoding="utf-8") if line.strip()]
    vec_tasks = [r for r in records if r.get("modality") in ("pure_vector","mixed")]
    print(f"Vector tasks: {len(vec_tasks)}")

    qg_vocab = V4_QG_TASK_TYPE_VOCAB_PATH if Path(str(V4_QG_TASK_TYPE_VOCAB_PATH)).exists() else None
    inferencer = L3SequenceInferencerV4(checkpoint_path=CKPT, device=DEVICE,
        task_vocab_path=Path(str(qg_vocab)) if qg_vocab else None)
    stats = Counter(); headroom_samples = []
    for i, r in enumerate(vec_tasks[:100]):  # 100 for speed
        zh = r.get("task_description_zh","")
        en = r.get("task_description_en","")
        desc = f"{en} {zh}"[:300] if en or zh else "QGIS vector task"
        # Generate k=5 candidates (beam search)
        try:
            cands = inferencer.infer(task_name="", task_description=desc, task_type="GIS Processing")
        except: continue
        if not cands: continue
        scores = [score_candidate(c.tokens) for c in cands[:5]]
        if len(scores) < 2: continue
        top1 = scores[0]; best = max(scores)
        gap = best - top1
        stats["total"] += 1
        if gap > 0.05: stats["headroom_present"] += 1
        if gap > 0.10: stats["strong_headroom"] += 1
        if best > 0.6 and top1 < 0.5: stats["worth_training"] += 1
        stats["sum_gap"] += gap
        if len(headroom_samples) < 5 and gap > 0.10:
            headroom_samples.append({"gap":gap,"top1":top1,"best":best,"desc":desc[:100]})
    n = stats["total"]
    print(f"\nBeam evaluated: {n}")
    print(f"  Headroom (>0.05 gap): {stats['headroom_present']}/{n} ({stats['headroom_present']/max(n,1)*100:.1f}%)")
    print(f"  Strong (>0.10 gap):   {stats['strong_headroom']}/{n} ({stats['strong_headroom']/max(n,1)*100:.1f}%)")
    print(f"  Worth training:       {stats['worth_training']}/{n} ({stats['worth_training']/max(n,1)*100:.1f}%)")
    print(f"  Mean gap: {stats['sum_gap']/max(n,1):.4f}")
    # Verdict
    if stats['worth_training']/max(n,1) >= 0.3: print("\nVERDICT: GRPO worth trying (>=30% training-worthy)")
    else: print(f"\nVERDICT: GRPO not worth it ({stats['worth_training']/max(n,1)*100:.1f}% < 30%)")
    # Save report
    out = ROOT / "outputs_v2" / "diagnostics" / "grpo_headroom.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    json.dump({"n":n,"headroom_pct":stats['headroom_present']/max(n,1),
        "strong_pct":stats['strong_headroom']/max(n,1),"worth_pct":stats['worth_training']/max(n,1),
        "mean_gap":stats['sum_gap']/max(n,1),"samples":headroom_samples}, out.open("w"), indent=2)
    print(f"\nReport: {out}")

if __name__=="__main__": main()
