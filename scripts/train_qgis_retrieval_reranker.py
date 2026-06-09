#!/usr/bin/env python3
"""
QGIS Retrieval Reranker — trains directly on retriever candidate pools.

For each facts_summary task:
  1. Retrieve top-K QGIS chains via QGISChainRetriever
  2. Mark real chain (from facts) as positive, others as negative
  3. Extract features for each candidate
  4. Train XGBoost rank:pairwise
  5. Evaluate with MRR, Top-1 hit, NDCG@5, Recall@5

This aligns training with deployment: ranking within a per-task candidate set.

Dependencies: numpy, scikit-learn, xgboost
"""

from __future__ import annotations

import argparse, csv, json, math, os, random, re, sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.planning.qgis_chain_planner import (
    QGISChainRetriever, QGISChainEvaluator, build_qgis_chain_planner,
)

SEED = 42
random.seed(SEED); np.random.seed(SEED)

FACTS_CSV     = ROOT / "爬取GithubQGIS" / "facts_summary1000.csv"
V2_DS         = ROOT / "outputs_v2" / "qgis_chain_dataset_v2.jsonl"
CATALOG       = ROOT / "爬取GithubQGIS" / "QGIS_Input.csv"
WEIGHTS_OUT   = ROOT / "outputs_v2" / "qgis_retrieval_reranker_weights.pkl"
REPORT_OUT    = ROOT / "outputs_v2" / "qgis_retrieval_reranker_report.json"

VECTOR_KW = {
    "buffer","clip","dissolve","intersection","difference","mergevectorlayers",
    "extractbyexpression","extractbylocation","joinattributesbylocation",
    "joinattributestable","reprojectlayer","fixgeometries","simplifygeometries",
    "snapgeometries","creategrid","joinbynearest","centroids","countpointsinpolygon",
    "polygonstolines","splitwithlines","refactorfields","symmetricaldifference",
}
RASTER_KW = {
    "cliprasterbymasklayer","cliprasterbyextent","rastercalculator",
    "warpreproject","fillnodata","zonalstatisticsfb","buildvirtualraster",
    "reclassifybytable","translate","rearrange_bands","merge",
}
INTENT_PATTERNS = {
    "buffer":["buffer","proximity","distance"],"overlay":["intersect","union","difference","overlay"],
    "join":["join","attribute"],"clip":["clip","crop","mask"],
    "reproject":["reproject","warp","crs","coordinate"],"repair":["fix","valid","repair","clean"],
    "raster":["raster","slope","hillshade","ndvi"],"vector":["vector","polygon","line","point"],
    "convert":["rasterize","polygonize","convert"],"export":["export","save","write"],
    "zonal":["zonal","statistics","summarize"],
}
TEXT_OP_KW = [kw for kws in INTENT_PATTERNS.values() for kw in kws]


def _modality(ops, legacy):
    v=sum(1 for o in ops if legacy.get(o.lower(),{}).get("data_type","")=="vector")
    r=sum(1 for o in ops if legacy.get(o.lower(),{}).get("data_type","")=="raster")
    return "vector" if v>r else ("raster" if r>v else "mixed")


def extract_features(task_text, task_name, task_type, ops, legacy, len_stats):
    n=len(ops); txt=(task_text+" "+task_name+" "+task_type).lower()
    vc=sum(1 for o in ops if any(kw in o.lower().replace("native:","").replace("qgis:","") for kw in VECTOR_KW))
    rc=sum(1 for o in ops if any(kw in o.lower().replace("native:","").replace("gdal:","") for kw in RASTER_KW))
    uniq=len(set(ops)); dr=1.0-uniq/max(n,1); cr=sum(1 for i in range(n-1) if ops[i]==ops[i+1])/max(n-1,1) if n>1 else 0
    op_kw_hits=sum(1 for kw in TEXT_OP_KW if kw in txt)
    matched=sum(1 for kw in TEXT_OP_KW if any(kw in o for o in ops))
    t_overlap=matched/max(op_kw_hits,1) if op_kw_hits>0 else 0.0
    txt_intents=set(); chain_intents=set()
    for intent,kws in INTENT_PATTERNS.items():
        if any(kw in txt for kw in kws): txt_intents.add(intent)
        if any(any(kw in o for o in ops) for kw in kws): chain_intents.add(intent)
    i_cov=len(txt_intents&chain_intents)/max(len(txt_intents),1) if txt_intents else 0.5
    tv=any(kw in txt for kw in ["vector","polygon","line","point","buffer","dissolve"])
    tr=any(kw in txt for kw in ["raster","slope","ndvi","dem","hillshade"])
    tmod="mixed" if (tv and tr) else ("vector" if tv else ("raster" if tr else "unknown"))
    chain_mod=_modality(ops,legacy); mm=1.0 if tmod==chain_mod else (0.5 if tmod=="unknown" else 0.0)
    miss=sum(1 for kw in TEXT_OP_KW if kw in txt and not any(kw in o for o in ops))
    miss_r=miss/max(op_kw_hits,1) if op_kw_hits>0 else 0.0
    io=0;io_n=0
    for i in range(n-1):
        t1=legacy.get(ops[i].lower(),{}).get("data_type","unknown"); t2=legacy.get(ops[i+1].lower(),{}).get("data_type","unknown")
        if t1=="unknown" or t2=="unknown": continue
        io_n+=1; io+=1.0 if t1==t2 else (0.3 if "raster" in (t1,t2) else 0.0)
    io/=max(io_n,1) if io_n>0 else 1.0
    cat_cov=sum(1 for o in ops if o.lower() in legacy)/max(n,1)
    native_r=sum(1 for o in ops if o.startswith("native:"))/max(n,1)
    mod_key=_modality(ops,legacy)
    ld=len_stats.get(mod_key,len_stats.get("mixed",[]))
    med=float(np.median(ld)) if ld else 8.0
    ls=1.0-abs(n-med)/max(med,1)*0.5; ls=max(0.0,min(1.0,ls))
    return np.array([float(n),float(vc),float(rc),vc/max(n,1),rc/max(n,1),dr,cr,
        float(n>=3),float(n>=5),float(vc>=2),float(vc>rc),float(rc>vc),
        t_overlap,i_cov,mm,float(op_kw_hits),miss_r,io,cat_cov,native_r,ls],dtype=np.float64)


def _load_legacy():
    cat={}
    with open(CATALOG,"r",encoding="utf-8",errors="replace") as f:
        for row in csv.reader(f):
            if len(row)<6: continue
            aid=row[5].strip().lower(); dt="unknown"
            for col in row[8:]:
                if col.strip() in ("vector","raster"): dt=col.strip(); break
            cat[aid]={"data_type":dt}
    return cat


def build_candidate_pools(retriever, facts, v2_by_file, legacy, max_samples=500):
    """For each task, retrieve candidates and build per-task ranking pools."""
    pools=[]; skipped=0; retrieval_miss=[]; train_pos_all=[]
    len_stats={"vector":[],"raster":[],"mixed":[]}
    for r in v2_by_file.values():
        m=_modality(r["qgis_ops"],legacy); len_stats[m].append(len(r["qgis_ops"]))
    for row in facts[:max_samples]:
        fn=row["File Name"].strip(); r=v2_by_file.get(fn)
        if not r: continue
        ops=r["qgis_ops"]
        if len(ops)<2: continue
        tt=row.get("Task Type",""); tn=row.get("Task Name",""); td=row.get("Task Description","")
        chain_mod=_modality(ops,legacy)
        try:
            cands=retriever.retrieve(task_text=td,l3_codes=[],k=20,
                prefer_vector=(chain_mod=="vector"),prefer_raster=(chain_mod=="raster"),
                prefer_mixed=(chain_mod=="mixed"))
        except Exception: skipped+=1; continue
        # Check if gold appears naturally in retriever results
        gold_key=tuple(ops)
        gold_found=False; gold_rank=-1; gold_score=0.0
        seen=set()
        pool=[]
        for rank,c in enumerate(cands):
            ckey=tuple(c.qgis_ops)
            if ckey in seen: continue
            seen.add(ckey)
            label=1 if ckey==gold_key else 0
            score=getattr(c,'score',0.0)
            if label==1:
                gold_found=True; gold_rank=rank; gold_score=score
            feat=extract_features(td,tn,tt,c.qgis_ops,legacy,len_stats)
            pool.append({"features":feat,"label":label,"source":"retriever","retriever_score":score})
            if len(pool)>=11: break
        if not gold_found:
            # Gold not in top-20 -> retrieval miss, add at end for completeness
            gold_feat=extract_features(td,tn,tt,ops,legacy,len_stats)
            pool.insert(0,{"features":gold_feat,"label":1,"source":"gold_injected","retriever_score":0.0})
            retrieval_miss.append(True)
        else:
            retrieval_miss.append(False)
        if len(pool)>=2 and sum(1 for p in pool if p["label"]==0)>=1:
            train_pos_all.append({"features":gold_feat if not gold_found else extract_features(td,tn,tt,ops,legacy,len_stats),"label":1})
            pools.append(pool)
    n_total=len(retrieval_miss)
    n_found=sum(1 for m in retrieval_miss if not m)
    n_miss=sum(1 for m in retrieval_miss if m)
    print(f"  Pools: {len(pools)} | Retrieval: {n_found}/{n_total} found ({n_found/max(n_total,1)*100:.1f}%), {n_miss} miss")
    return pools, retrieval_miss, train_pos_all


def evaluate_ranking(pools, model=None, use_retriever_score=False):
    """Per-task ranking metrics. If model is None, ranks by retriever_score."""
    mrrs,top1s,ndcgs,r5s=[],[],[],[]
    traces=[]
    for pool in pools:
        X=np.array([p["features"] for p in pool]); y=np.array([p["label"] for p in pool])
        if model is not None:
            scores=model.predict(X)
        else:
            scores=np.array([p.get("retriever_score",0.0) for p in pool])
        ranked=sorted(zip(scores,y,range(len(pool))),key=lambda x:-x[0])
        trace={"pool_size":len(pool),"labels":[int(l) for _,l,_ in ranked],"scores":[float(s) for s,_,_ in ranked]}
        for i,(_,label,_) in enumerate(ranked):
            if label==1: mrrs.append(1.0/(i+1)); break
        top1s.append(1.0 if ranked[0][1]==1 else 0.0)
        dcg=sum((2**l-1)/math.log2(i+2) for i,(_,l,_) in enumerate(ranked[:5]))
        ideal=sorted(y,reverse=True); idcg=sum((2**l-1)/math.log2(i+2) for i,l in enumerate(ideal[:5]))
        ndcgs.append(dcg/max(idcg,1e-8))
        n_pos=sum(1 for _,l,_ in ranked if l==1)
        r5s.append(min(1.0,sum(1 for _,l,_ in ranked[:5] if l==1)/max(n_pos,1)))
        traces.append(trace)
    return {"mrr":np.mean(mrrs),"top1":np.mean(top1s),"ndcg5":np.mean(ndcgs),"recall5":np.mean(r5s),
            "n_pools":len(pools),"ci_top1":_ci(np.mean(top1s),len(pools))},traces


def _ci(rate,n):
    if n==0: return "N/A"
    se=math.sqrt(rate*(1-rate)/n)
    return f"[{max(0,rate-1.96*se):.4f},{min(1,rate+1.96*se):.4f}]"


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-samples",type=int,default=500)
    parser.add_argument("--output-weights",default=str(WEIGHTS_OUT))
    parser.add_argument("--output-report",default=str(REPORT_OUT))
    args=parser.parse_args(argv)

    try: from xgboost import XGBRanker; USE_XGB=True
    except ImportError: USE_XGB=False; print("[WARN] xgboost not installed")

    print("="*60); print("QGIS Retrieval Reranker"); print("="*60)
    legacy=_load_legacy()
    v2_by_file={}
    with V2_DS.open("r",encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            r=json.loads(line)
            if len(r.get("qgis_ops",[]))>=2: v2_by_file[r["source_file"]]=r
    facts=list(csv.DictReader(open(FACTS_CSV,"r",encoding="utf-8",errors="replace")))
    retriever,_=build_qgis_chain_planner(V2_DS,CATALOG)

    print(f"\n[1] Building candidate pools (max {args.max_samples} tasks)...")
    pools,retrieval_miss,train_pos_all=build_candidate_pools(retriever,facts,v2_by_file,legacy,args.max_samples)
    n_ret=len(pools); n_gold_found=sum(1 for m in retrieval_miss if not m)
    retrieval_recall={"k":20,"total_tasks":len(retrieval_miss),"gold_found":n_gold_found,"recall":n_gold_found/max(len(retrieval_miss),1)}

    all_X=[]; all_y=[]; all_group=[]
    for i,pool in enumerate(pools):
        for p in pool: all_X.append(p["features"]); all_y.append(p["label"]); all_group.append(i)
    X=np.array(all_X,dtype=np.float64); y=np.array(all_y); groups=np.array(all_group)

    # Train/test split by pool
    pool_ids=list(range(len(pools))); random.shuffle(pool_ids)
    n_test=int(len(pool_ids)*0.2); test_pools=set(pool_ids[:n_test])
    train_idx=[i for i,g in enumerate(groups) if g not in test_pools]
    test_idx=[i for i,g in enumerate(groups) if g in test_pools]
    X_tr,y_tr,g_tr=X[train_idx],y[train_idx],groups[train_idx]
    X_te,y_te,g_te=X[test_idx],y[test_idx],groups[test_idx]
    test_pool_list=[pools[pid] for pid in pool_ids if pid in test_pools]
    print(f"  Train pools: {len(pools)-n_test}, Test pools: {len(test_pool_list)}")

    # Baseline: retriever rank (by retriever score, which we approximate as 0 since we only store features)
    # For proper baseline, we'd need retriever scores. Approximate: random ordering
    base_metrics={"mrr":1.0/len(pools[0]),"top1":1.0/max(len(pools[0]),2),"ndcg5":0.0,"recall5":0.0}
    n_pool=sum(1 for p in pools[0] if p["label"]==1)
    base_mrr=sum(1.0/(i+1) for i in range(len(pools[0])) if pools[0][i]["label"]==1)/max(n_pool,1) if n_pool>0 else 0
    # Better baseline: average across test pools
    base_top1s=[]; base_mrrs=[]
    for pool in test_pool_list:
        y_pool=[p["label"] for p in pool]
        ranked=list(enumerate(y_pool)); random.shuffle(ranked)
        for i,(_,label) in enumerate(ranked):
            if label==1: base_mrrs.append(1.0/(i+1)); break
        base_top1s.append(1.0 if ranked[0][1]==1 else 0.0)
    random_base,_=evaluate_ranking(test_pool_list,model=None)
    retriever_base,ret_traces=evaluate_ranking(test_pool_list,model=None,use_retriever_score=True)

    print(f"\n[2] Training XGBoost rank:pairwise ({X_tr.shape[0]} samples, {X.shape[1]} features)...")
    model=XGBRanker(n_estimators=50,max_depth=3,learning_rate=0.03,objective="rank:pairwise",
                     reg_lambda=1.0,random_state=SEED,verbosity=0)
    model.fit(X_tr,y_tr,qid=g_tr)
    metrics,rerank_traces=evaluate_ranking(test_pool_list,model=model)

    print(f"\n[3] Results (on {len(test_pool_list)} test pools, {n_ret} total with gold present):")
    print(f"  Retrieval recall@20: {n_gold_found}/{len(retrieval_miss)} ({n_gold_found/max(len(retrieval_miss),1)*100:.1f}%)")
    print()
    print(f"  {'Metric':20s} {'Random':>10s} {'Retriever':>10s} {'Reranker':>10s} {'vs-Ret':>10s}")
    for k in ["top1","mrr","ndcg5","recall5"]:
        rnd=random_base[k]; ret=retriever_base[k]; rer=metrics[k]; delta=rer-ret
        print(f"  {k:20s} {rnd:>10.4f} {ret:>10.4f} {rer:>10.4f} {delta:>+10.4f}")

    # Save traces
    trace_out=Path(args.output_report).parent / "reranker_traces.json"
    with open(trace_out,"w",encoding="utf-8") as f:
        json.dump({"retriever":ret_traces,"reranker":rerank_traces},f,indent=2)
    print(f"  Traces: {trace_out}")

    report={"schema":"qgis_retrieval_reranker.v1","seed":SEED,
        "n_train_pools":len(pools)-n_test,"n_test_pools":len(test_pool_list),
        "pool_coverage":f"{len(pools)}/{args.max_samples}",
        "n_features":X.shape[1],"model":"XGBoost rank:pairwise",
        "retrieval_recall":retrieval_recall,
        "baseline_random":random_base,"baseline_retriever":retriever_base,"reranker":metrics,
        "deltas_vs_retriever":{k:f"{metrics[k]-retriever_base[k]:+.4f}" for k in ["top1","mrr","ndcg5","recall5"]}}
    Path(args.output_report).parent.mkdir(parents=True,exist_ok=True)
    with open(args.output_report,"w",encoding="utf-8") as f: json.dump(report,f,indent=2,ensure_ascii=False)
    import pickle
    with open(args.output_weights,"wb") as f: pickle.dump({"model":model},f)
    print(f"\n  Report: {args.output_report}")
    print(f"  Weights: {args.output_weights}")

    print(f"\n[4] Success criteria (vs retriever baseline):")
    for label,val,target in [
        ("Top-1 > retriever+0.15",metrics["top1"]-retriever_base["top1"],0.15),
        ("MRR > retriever+0.10",metrics["mrr"]-retriever_base["mrr"],0.10),
        ("NDCG@5 > retriever+0.10",metrics["ndcg5"]-retriever_base["ndcg5"],0.10),
    ]:
        status="PASS" if val>=target else "FAIL"
        print(f"  [{status}] {label}: {val:+.4f} (target {target:+.2f})")


if __name__=="__main__": main()
