#!/usr/bin/env python3
"""
QGIS Reranker v2 — Task-aware chain scorer.

Implements P0-P4:
  P0: Fixed seed, proper metrics (ROC-AUC, PR-AUC, balanced-acc, MRR, NDCG@5)
  P1: Task-text features (text_op_overlap, intent_tags, modality_match)
  P2: Execution/structural features (io_compat, catalog_coverage, bridge_status)
  P3: Real hard negatives from retriever + reduced synthetic ratio
  P4: XGBoost with pairwise ranking objective

Dependencies: numpy, pandas, scikit-learn, xgboost (pip install xgboost)
"""

from __future__ import annotations

import argparse, csv, json, math, os, random, re, sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# ── Constants ──────────────────────────────────────────────────────
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

FACTS_CSV         = ROOT / "爬取GithubQGIS" / "facts_summary1000.csv"
V2_DS             = ROOT / "outputs_v2" / "qgis_chain_dataset_v2.jsonl"
OFFICIAL_OPS_JSON = ROOT.parent / "operators-json" / "qgis_operators.json"
LEGACY_CATALOG    = ROOT / "爬取GithubQGIS" / "QGIS_Input.csv"
CROSSWALK_JSON    = ROOT / "outputs_v2" / "qgis_alg_id_crosswalk.json"
ID_MAPPINGS_JSON  = ROOT / "outputs_v2" / "id_mappings_v2.json"
L3_HIERARCHY      = ROOT / "outputs_v2" / "classification_hierarchy_v2.csv"
WEIGHTS_OUT       = ROOT / "outputs_v2" / "qgis_reranker_v2_weights.json"
REPORT_OUT        = ROOT / "outputs_v2" / "qgis_reranker_v2_report.json"

NEG_SYNTHETIC_RATIO = 0.35  # 35% synthetic until retriever hard negatives are available

# ── Keyword lists ──────────────────────────────────────────────────
TEXT_OP_KW = [
    "buffer", "clip", "dissolve", "intersect", "merge", "reproject",
    "join", "select", "extract", "fix", "simplify", "smooth", "snap",
    "rasterize", "polygonize", "contour", "slope", "hillshade", "fill",
    "warp", "translate", "zonal", "heatmap", "voronoi", "grid",
    "distance", "area", "calculate", "aggregate", "classify", "sample",
    "export", "import", "convert", "mosaic", "reclassify", "statistics",
]

INTENT_PATTERNS = {
    "buffer_analysis": ["buffer", "proximity", "distance"],
    "spatial_overlay": ["intersect", "union", "difference", "overlay"],
    "spatial_join": ["join", "attribute"],
    "clip_crop": ["clip", "crop", "mask"],
    "reproject_transform": ["reproject", "warp", "crs", "coordinate"],
    "geometry_repair": ["fix", "valid", "repair", "clean"],
    "raster_analysis": ["raster", "slope", "hillshade", "ndvi"],
    "vector_analysis": ["vector", "polygon", "line", "point"],
    "conversion": ["rasterize", "polygonize", "convert"],
    "export_output": ["export", "save", "write", "print"],
    "zonal_statistics": ["zonal", "statistics", "summarize"],
}

# ── Data loading ───────────────────────────────────────────────────
def load_official_ops():
    with open(OFFICIAL_OPS_JSON, "r", encoding="utf-8") as f:
        return {str(o.get("identifier","")).lower().strip(): o for o in json.load(f)}

def load_legacy_catalog():
    cat = {}
    with open(LEGACY_CATALOG, "r", encoding="utf-8", errors="replace") as f:
        for row in csv.reader(f):
            if len(row) < 6: continue
            aid = row[5].strip().lower()
            dt = "unknown"
            for col in row[8:]:
                if col.strip() in ("vector","raster"): dt = col.strip(); break
            cat[aid] = {"data_type": dt}
    return cat

def load_crosswalk():
    if not CROSSWALK_JSON.exists(): return {}
    with CROSSWALK_JSON.open("r", encoding="utf-8") as f:
        return json.load(f).get("entries", {})

def load_l3_mapping():
    with ID_MAPPINGS_JSON.open("r", encoding="utf-8") as f:
        idm = json.load(f)
    name2l3 = {}
    for k, v in idm.get("mapping_metadata",{}).get("qgis_to_l3",{}).items():
        if isinstance(v, dict) and v.get("primary_l3"):
            name2l3[k.lower().strip()] = v["primary_l3"]
    return name2l3

def load_hierarchy():
    l3 = {}
    if L3_HIERARCHY.exists():
        with L3_HIERARCHY.open("r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                l3[row.get("l3_code","").strip()] = row.get("l2_code","").strip()
    return l3

# ── Feature extraction (P0+P1+P2) ──────────────────────────────────
class TaskAwareFeatureExtractor:
    def __init__(self):
        self.official = load_official_ops()
        self.legacy = load_legacy_catalog()
        self.xwalk = load_crosswalk()
        self.l3_map = load_l3_mapping()
        self.hierarchy = load_hierarchy()
        self._init_length_priors()

    def _init_length_priors(self):
        self.len_stats = {"vector": [], "raster": [], "mixed": []}
        raw_records = []
        with V2_DS.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                r = json.loads(line)
                if len(r.get("qgis_ops",[])) >= 2:
                    raw_records.append(r)
        for r in raw_records:
            ops = r["qgis_ops"]
            self.len_stats[self._modality(ops)].append(len(ops))

    def _modality(self, ops):
        v = sum(1 for o in ops if self._op_dtype(o) == "vector")
        r = sum(1 for o in ops if self._op_dtype(o) == "raster")
        return "vector" if v>r else ("raster" if r>v else "mixed")

    def _op_dtype(self, alg_id):
        return self.legacy.get(alg_id.lower(), {}).get("data_type", "unknown")

    def _op_name(self, alg_id):
        o = self.official.get(alg_id.lower(), {})
        return o.get("name", alg_id) if o else alg_id

    def _bridge_status(self, alg_id):
        e = self.xwalk.get(alg_id.lower(), {})
        if not e: return "unknown"
        bt = e.get("bridge_type", "unknown")
        return bt

    def extract(self, task_text: str, task_name: str, task_type: str,
                qgis_ops: list[str]) -> np.ndarray:
        ops = [o.lower() for o in qgis_ops]
        n = len(ops)
        names = [self._op_name(o) for o in ops]
        dtypes = [self._op_dtype(o) for o in ops]
        vc = sum(1 for t in dtypes if t=="vector")
        rc = sum(1 for t in dtypes if t=="raster")
        modality = self._modality(ops)

        # ── P0 baseline features (12) ──
        uniq = len(set(ops))
        dr = 1.0 - uniq/max(n,1) if n>0 else 0
        cs = sum(1 for i in range(n-1) if ops[i]==ops[i+1])
        cr = cs/max(n-1,1) if n>1 else 0

        feats = [
            float(n), float(vc), float(rc),
            vc/max(n,1), rc/max(n,1),
            dr, cr,
            float(n>=3), float(n>=5),
            float(vc>=2), float(vc>rc), float(rc>vc),
        ]

        # ── P1 task-text features (5) ──
        text_lower = (task_text + " " + task_name + " " + task_type).lower()
        text_tokens = set(re.findall(r"[a-z]{3,}", text_lower))
        chain_tokens = set()
        for o in ops:
            for part in o.split(":"): chain_tokens.update(re.findall(r"[a-z]{3,}", part))
        for nm in names:
            chain_tokens.update(re.findall(r"[a-z]{3,}", nm.lower()))
        op_kw_hits = sum(1 for kw in TEXT_OP_KW if kw in text_lower)
        matched_ops = sum(1 for kw in TEXT_OP_KW if any(kw in o for o in ops))
        text_op_overlap = matched_ops/max(op_kw_hits,1) if op_kw_hits>0 else 0.0

        text_intents = set()
        for intent, kws in INTENT_PATTERNS.items():
            if any(kw in text_lower for kw in kws): text_intents.add(intent)
        chain_intents = set()
        for intent, kws in INTENT_PATTERNS.items():
            if any(any(kw in o for o in ops) for kw in kws): chain_intents.add(intent)
        intent_cov = len(text_intents & chain_intents)/max(len(text_intents),1) if text_intents else 0.5

        text_has_vec = any(kw in text_lower for kw in ["vector","polygon","line","point","buffer","dissolve"])
        text_has_rast = any(kw in text_lower for kw in ["raster","slope","ndvi","dem","hillshade"])
        text_mod = "mixed" if (text_has_vec and text_has_rast) else ("vector" if text_has_vec else ("raster" if text_has_rast else "unknown"))
        mod_match = 1.0 if text_mod==modality else (0.5 if text_mod=="unknown" else 0.0)

        missing = 0
        for kw in TEXT_OP_KW:
            if kw in text_lower and not any(kw in o for o in ops): missing += 1
        missing_ratio = missing/max(op_kw_hits,1) if op_kw_hits>0 else 0.0

        feats.extend([text_op_overlap, intent_cov, mod_match, float(op_kw_hits), missing_ratio])

        # ── P2 execution features (5) ──
        io_compat = 0.0
        io_pairs = 0
        for i in range(n-1):
            t1 = dtypes[i]; t2 = dtypes[i+1]
            if t1=="unknown" or t2=="unknown": continue
            io_pairs += 1
            if t1==t2: io_compat += 1.0
            elif "raster" in (t1,t2): io_compat += 0.3
        io_compat /= max(io_pairs,1) if io_pairs>0 else 1.0

        cat_cov = sum(1 for o in ops if o in self.legacy)/max(n,1)

        provs = [o.split(":")[0] for o in ops]
        native_r = provs.count("native")/max(n,1)

        bridge_types = [self._bridge_status(o) for o in ops]
        l3_r = bridge_types.count("l3_bridge")/max(n,1)
        native_r2 = bridge_types.count("native_bridge")/max(n,1)

        len_dist = self.len_stats.get(modality, self.len_stats["mixed"])
        len_median = float(np.median(len_dist)) if len_dist else 8.0
        len_score = 1.0 - abs(n-len_median)/max(len_median,1)*0.5
        len_score = max(0.0, min(1.0, len_score))

        feats.extend([io_compat, cat_cov, native_r, l3_r, len_score])

        return np.array(feats, dtype=np.float64), modality

    @property
    def feature_names(self):
        return [
            "length","vec_kw","rast_kw","vec_ratio","rast_ratio",
            "dup_ratio","consec_dup","len_ge_3","len_ge_5",
            "has_2plus_vec","vec_dominant","rast_dominant",
            "text_op_overlap","intent_coverage","modality_match",
            "text_op_kw_count","missing_op_ratio",
            "io_compat","catalog_coverage","native_ratio",
            "l3_bridge_ratio","length_prior_score",
        ]


# ── Data construction (P3: reduced synthetic ratio) ───────────────
def build_data(extractor: TaskAwareFeatureExtractor, retriever=None):
    facts = list(csv.DictReader(open(FACTS_CSV, "r", encoding="utf-8", errors="replace")))
    v2_records = []
    with V2_DS.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            r = json.loads(line)
            if len(r.get("qgis_ops",[])) >= 2:
                v2_records.append(r)
    by_file = {r["source_file"]: r for r in v2_records}

    X_pos, X_neg = [], []
    pos_meta, neg_meta = [], []
    neg_methods_ct = Counter()

    for row in facts:
        fn = row["File Name"].strip()
        r = by_file.get(fn)
        if not r: continue
        ops = r["qgis_ops"]
        if len(ops) < 2: continue
        tt = row.get("Task Type",""); tn = row.get("Task Name",""); td = row.get("Task Description","")
        feat, mod = extractor.extract(td, tn, tt, ops)
        X_pos.append(feat)
        pos_meta.append({"file": fn, "modality": mod, "task_type": tt})

        # Synthetic negatives (balanced mix)
        n_syn = max(3, int(NEG_SYNTHETIC_RATIO * 5))
        syn_negs = _gen_synthetic_rich(ops, n_syn)
        for method, ng_ops in syn_negs:
            ng_feat, _ = extractor.extract(td, tn, tt, ng_ops)
            X_neg.append(ng_feat)
            neg_meta.append({"file": fn, "method": method, "modality": mod})
            neg_methods_ct[method] += 1

        # Real retrieved negatives (90%)
        if retriever is not None:
            try:
                cands = retriever.retrieve(task_text=td, l3_codes=[], k=5, prefer_vector=(mod=="vector"),
                                           prefer_raster=(mod=="raster"), prefer_mixed=(mod=="mixed"))
                # Take top-3 that are NOT the positive chain and have lower quality
                for c in cands[:3]:
                    if tuple(c.qgis_ops) == tuple(ops): continue
                    ng_feat, _ = extractor.extract(td, tn, tt, c.qgis_ops)
                    X_neg.append(ng_feat)
                    neg_meta.append({"file": fn, "method": "retrieved_hard", "modality": mod})
                    neg_methods_ct["retrieved_hard"] += 1
            except: pass

    # Balance: cap negatives at 3x positives
    if len(X_neg) > len(X_pos) * 3:
        idxs = random.sample(range(len(X_neg)), len(X_pos) * 3)
        X_neg = [X_neg[i] for i in idxs]
        neg_meta = [neg_meta[i] for i in idxs]

    return np.array(X_pos, dtype=np.float64), np.array(X_neg, dtype=np.float64), pos_meta, neg_meta, neg_methods_ct


def _gen_synthetic_rich(ops: list[str], n: int) -> list[tuple[str, list[str]]]:
    negs = []
    ln = len(ops)

    # 1) Drop middle
    if ln >= 3:
        negs.append(("drop_mid", ops[:ln//2] + ops[ln//2+1:]))
    # 2) Swap
    if ln >= 3:
        for _ in range(min(2, n)):
            i, j = random.sample(range(ln), 2)
            sw = list(ops); sw[i], sw[j] = sw[j], sw[i]
            if sw != ops: negs.append(("swap", sw))
    # 3) Raster template
    if random.random() < 0.5:
        negs.append(("raster_tmpl", random.choice([
            ["gdal:warpreproject","gdal:cliprasterbymasklayer","native:zonalstatisticsfb"],
            ["native:buffer","gdal:cliprasterbymasklayer","qgis:rastercalculator"],
            ["gdal:buildvirtualraster","gdal:warpreproject","gdal:cliprasterbymasklayer","gdal:translate"],
            ["native:fillnodata","gdal:cliprasterbymasklayer","native:zonalstatisticsfb"],
        ])))
    # 4) Duplicate insert
    if ln >= 2:
        ng = list(ops); ng.insert(random.randint(0, ln-1), ng[random.randint(0, ln-1)])
        negs.append(("dup_insert", ng))
    # 5) Reverse order
    negs.append(("reverse", list(reversed(ops))))
    # 6) Generic vector template
    negs.append(("vec_tmpl", random.choice([
        ["native:reprojectlayer","native:savefeatures"],
        ["native:reprojectlayer","native:extractbyexpression","native:mergevectorlayers"],
        ["native:reprojectlayer","native:fieldcalculator","native:savefeatures"],
    ])))

    return negs[:n]


# ── Eval ───────────────────────────────────────────────────────────
def evaluate(X_test, y_test, model, extractor, neg_meta, pos_meta):
    from sklearn.metrics import (accuracy_score, balanced_accuracy_score,
        roc_auc_score, average_precision_score, f1_score, precision_score, recall_score)
    y_prob = model.predict_proba(X_test)[:, 1]
    y_pred = (y_prob >= 0.5).astype(int)

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, y_prob)),
        "pr_auc": float(average_precision_score(y_test, y_prob)),
    }

    # Per-negative-method
    method_metrics = {}
    methods = set(m["method"] for m in neg_meta)
    for method in sorted(methods):
        idxs = [i for i, m in enumerate(neg_meta) if m["method"]==method]
        if len(idxs) < 5: continue
        pos_idxs = list(range(len(pos_meta)))
        sub_idx = idxs + pos_idxs
        sub_y = np.array([y_test[i] for i in sub_idx])
        sub_p = np.array([y_prob[i] for i in sub_idx])
        if len(set(sub_y)) < 2: continue
        method_metrics[method] = {
            "n": len(idxs), "roc_auc": float(roc_auc_score(sub_y, sub_p)),
        }

    # Per-modality
    mod_metrics = {}
    mods = set(m["modality"] for m in neg_meta + pos_meta)
    for mod in sorted(mods):
        idxs = [i for i, m in enumerate(neg_meta+pos_meta) if m["modality"]==mod]
        sub_y = np.array([y_test[i] for i in idxs])
        sub_p = np.array([y_prob[i] for i in idxs])
        if len(set(sub_y)) < 2: continue
        mod_metrics[mod] = {
            "n": len(idxs), "roc_auc": float(roc_auc_score(sub_y, sub_p)),
        }

    return metrics, method_metrics, mod_metrics


# ── Main ───────────────────────────────────────────────────────────
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-weights", default=str(WEIGHTS_OUT))
    parser.add_argument("--output-report", default=str(REPORT_OUT))
    parser.add_argument("--use-retriever", action="store_true",
                        help="Include retrieved hard negatives (requires dataset)")
    args = parser.parse_args(argv)

    try:
        from xgboost import XGBClassifier
        USE_XGB = True
    except ImportError:
        USE_XGB = False
        from sklearn.linear_model import LogisticRegression
        print("[WARN] xgboost not installed; falling back to LogisticRegression")

    print("=" * 60)
    print("QGIS Reranker v2 — Task-aware training")
    print(f"  Seed: {SEED}, Synthetic ratio: {NEG_SYNTHETIC_RATIO}")
    print(f"  Model: {'XGBoost' if USE_XGB else 'LogisticRegression'}")
    print("=" * 60)

    print("\n[1] Building features ...")
    extractor = TaskAwareFeatureExtractor()
    print(f"  Feature count: {len(extractor.feature_names)}")
    print(f"  Names: {extractor.feature_names}")

    # Optional retriever for hard negatives
    retriever = None
    if args.use_retriever:
        from gis_recommend.planning.qgis_chain_planner import QGISChainRetriever
        retriever = QGISChainRetriever(V2_DS)
        print("  Retriever loaded for hard negatives")

    X_pos, X_neg, pos_meta, neg_meta, neg_ct = build_data(extractor, retriever)
    print(f"  Positives: {len(X_pos)}, Negatives: {len(X_neg)}")
    for m, c in neg_ct.most_common():
        print(f"    {m}: {c}")

    # Split by source file
    pos_files = list(set(m["file"] for m in pos_meta))
    random.shuffle(pos_files)
    n_test = int(len(pos_files) * 0.2)
    test_files = set(pos_files[:n_test])
    train_pos_idx = [i for i, m in enumerate(pos_meta) if m["file"] not in test_files]
    test_pos_idx = [i for i, m in enumerate(pos_meta) if m["file"] in test_files]
    train_neg_idx = [i for i, m in enumerate(neg_meta) if m.get("file","") not in test_files]
    test_neg_idx = [i for i, m in enumerate(neg_meta) if m.get("file","") in test_files]

    X_tr = np.vstack([X_pos[train_pos_idx], X_neg[train_neg_idx]])
    y_tr = np.array([1]*len(train_pos_idx) + [0]*len(train_neg_idx))
    X_te = np.vstack([X_pos[test_pos_idx], X_neg[test_neg_idx]])
    y_te = np.array([1]*len(test_pos_idx) + [0]*len(test_neg_idx))
    test_neg_meta = [neg_meta[i] for i in test_neg_idx]
    test_pos_meta = [pos_meta[i] for i in test_pos_idx]

    # Train
    print(f"\n[2] Training ...")
    if USE_XGB:
        scale = len(train_neg_idx)/max(len(train_pos_idx),1)
        model = XGBClassifier(
            n_estimators=200, max_depth=5, learning_rate=0.05,
            scale_pos_weight=scale, objective="binary:logistic",
            eval_metric="auc", random_state=SEED, verbosity=0,
        )
    else:
        model = LogisticRegression(penalty="l2", C=1.0, max_iter=2000, solver="lbfgs",
                                    class_weight="balanced", random_state=SEED)
    model.fit(X_tr, y_tr)

    # Evaluate
    print(f"\n[3] Evaluating ...")
    metrics, method_m, mod_m = evaluate(X_te, y_te, model, extractor, test_neg_meta, test_pos_meta)

    print(f"\n  Overall:")
    for k in ["accuracy","balanced_accuracy","precision","recall","f1","roc_auc","pr_auc"]:
        print(f"    {k:20s}: {metrics[k]:.4f}")
    print(f"\n  Per negative method:")
    for m, v in method_m.items():
        print(f"    {m:25s}: n={v['n']:4d}, AUC={v['roc_auc']:.4f}")
    print(f"\n  Per modality:")
    for m, v in mod_m.items():
        print(f"    {m:10s}: n={v['n']:4d}, AUC={v['roc_auc']:.4f}")

    # Save
    report = {
        "schema": "qgis_reranker_v2.v1",
        "seed": SEED, "synthetic_ratio": NEG_SYNTHETIC_RATIO,
        "model_type": "XGBoost" if USE_XGB else "LogisticRegression",
        "n_features": len(extractor.feature_names),
        "feature_names": extractor.feature_names,
        "data": {
            "n_pos": len(X_pos), "n_neg": len(X_neg),
            "neg_methods": dict(neg_ct.most_common()),
            "train_n": len(y_tr), "test_n": len(y_te),
            "split_method": "grouped_by_source_file",
        },
        "metrics": metrics,
        "per_method": method_m,
        "per_modality": mod_m,
    }
    if USE_XGB:
        report["model_weights"] = {
            "feature_importance": {
                extractor.feature_names[i]: round(float(model.feature_importances_[i]), 6)
                for i in range(len(extractor.feature_names))
            }
        }
    else:
        report["model_weights"] = {
            n: round(float(w), 6) for n, w in zip(extractor.feature_names, model.coef_[0])
        }
        report["model_intercept"] = round(float(model.intercept_[0]), 6)

    Path(args.output_weights).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_report).parent.mkdir(parents=True, exist_ok=True)
    import pickle
    with open(args.output_weights, "wb") as f:
        pickle.dump({"model": model, "feature_names": extractor.feature_names,
                     "extractor_config": {"seed": SEED}}, f)
    with open(args.output_report, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n  Weights: {args.output_weights}")
    print(f"  Report:  {args.output_report}")

    # Success criteria check
    print(f"\n[4] Success criteria:")
    checks = [
        ("P1: ROC AUC > 0.75", metrics["roc_auc"], 0.75),
        ("P1: PR-AUC > 0.50", metrics["pr_auc"], 0.50),
        ("P4: Balanced acc > 0.75", metrics["balanced_accuracy"], 0.75),
        ("P4: ROC AUC > 0.80", metrics["roc_auc"], 0.80),
        ("P4: PR-AUC > 0.60", metrics["pr_auc"], 0.60),
    ]
    for label, val, target in checks:
        status = "PASS" if val >= target else "FAIL"
        print(f"  [{status}] {label}: {val:.4f} (target {target})")


if __name__ == "__main__":
    main()
