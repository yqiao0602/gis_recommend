#!/usr/bin/env python3
"""Generate comprehensive QGIS reranker baseline experiment report."""

import json, random, csv
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score, confusion_matrix, average_precision_score

ROOT = Path(__file__).resolve().parents[1]
random.seed(42)

# Load data
facts = list(csv.DictReader(open(ROOT / "爬取GithubQGIS" / "facts_summary1000.csv", "r", encoding="utf-8", errors="replace")))
v2_records = []
with open(ROOT / "outputs_v2" / "qgis_chain_dataset_v2.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            r = json.loads(line)
            if len(r.get("qgis_ops", [])) >= 2:
                v2_records.append(r)
by_file = {r["source_file"]: r for r in v2_records}

# Positives
positives = []
for row in facts:
    fn = row["File Name"].strip()
    r = by_file.get(fn)
    if not r: continue
    ops = r["qgis_ops"]
    if len(ops) < 2: continue
    positives.append({"ops": ops, "file": fn, "task_type": row.get("Task Type", ""),
                       "task_name": row.get("Task Name", "")})
print(f"Positives: {len(positives)}")

# Features
VECTOR_KW = {
    "buffer", "clip", "dissolve", "intersection", "difference",
    "mergevectorlayers", "extractbyexpression", "extractbylocation",
    "joinattributesbylocation", "joinattributestable",
    "reprojectlayer", "fixgeometries", "simplifygeometries",
    "snapgeometries", "creategrid", "joinbynearest",
    "centroids", "countpointsinpolygon", "polygonstolines",
    "splitwithlines", "refactorfields", "symmetricaldifference",
}
RASTER_KW = {
    "cliprasterbymasklayer", "cliprasterbyextent", "rastercalculator",
    "warpreproject", "fillnodata", "zonalstatisticsfb",
    "buildvirtualraster", "reclassifybytable", "translate",
    "rearrange_bands", "merge",
}

def extract_features(ops):
    n = len(ops)
    vk = sum(1 for op in ops if any(kw in op.lower().replace("native:", "").replace("qgis:", "") for kw in VECTOR_KW))
    rk = sum(1 for op in ops if any(kw in op.lower().replace("native:", "").replace("gdal:", "") for kw in RASTER_KW))
    uniq = len(set(ops))
    dr = 1.0 - uniq / max(n, 1) if n > 0 else 0
    cs = sum(1 for i in range(n - 1) if ops[i] == ops[i + 1])
    cr = cs / max(n - 1, 1) if n > 1 else 0
    return np.array([float(n), float(vk), float(rk), vk / max(n, 1), rk / max(n, 1),
        dr, cr, float(n >= 3), float(n >= 5), float(vk >= 2),
        float(vk > rk), float(rk > vk)], dtype=np.float64)

# Negatives
RASTER_TMPL = [
    ["gdal:warpreproject", "gdal:cliprasterbymasklayer", "native:zonalstatisticsfb"],
    ["native:buffer", "gdal:cliprasterbymasklayer", "qgis:rastercalculator"],
    ["gdal:buildvirtualraster", "gdal:warpreproject", "gdal:cliprasterbymasklayer", "gdal:translate"],
    ["native:fillnodata", "gdal:cliprasterbymasklayer", "native:zonalstatisticsfb"],
]
negatives = []
neg_methods = Counter()
for p in positives:
    ops = p["ops"]; n = len(ops)
    if n >= 3:
        idx = random.randint(1, n - 2)
        negatives.append({"ops": ops[:idx] + ops[idx + 1:], "method": "drop_middle", "pos_file": p["file"]})
        neg_methods["drop_middle"] += 1
    if n >= 3:
        i, j = random.sample(range(n), 2)
        sw = list(ops); sw[i], sw[j] = sw[j], sw[i]
        if sw != ops:
            negatives.append({"ops": sw, "method": "swap", "pos_file": p["file"]})
            neg_methods["swap"] += 1
    if random.random() < 0.6:
        negatives.append({"ops": random.choice(RASTER_TMPL), "method": "raster_tmpl", "pos_file": p["file"]})
        neg_methods["raster_tmpl"] += 1
    cnt = sum(1 for x in negatives if x["pos_file"] == p["file"])
    while cnt < 3:
        if n >= 2:
            ng = list(ops); ng.insert(random.randint(0, n - 1), ng[random.randint(0, n - 1)])
            negatives.append({"ops": ng, "method": "dup_insert", "pos_file": p["file"]})
        else:
            negatives.append({"ops": ["native:reprojectlayer", "native:savefeatures"], "method": "safe_tmpl", "pos_file": p["file"]})
        cnt += 1
        neg_methods["dup_insert" if n >= 2 else "safe_tmpl"] += 1

# Split by source_file
pos_files = list(set(p["file"] for p in positives))
random.shuffle(pos_files)
n_test = int(len(pos_files) * 0.2)
test_files = set(pos_files[:n_test])
train_pos = [p for p in positives if p["file"] not in test_files]
test_pos = [p for p in positives if p["file"] in test_files]
train_neg = [n for n in negatives if n["pos_file"] not in test_files]
test_neg = [n for n in negatives if n["pos_file"] in test_files]

# Train
X_tr = np.array([extract_features(p["ops"]) for p in train_pos] + [extract_features(n["ops"]) for n in train_neg], dtype=np.float64)
y_tr = np.array([1] * len(train_pos) + [0] * len(train_neg), dtype=np.int64)
X_te = np.array([extract_features(p["ops"]) for p in test_pos] + [extract_features(n["ops"]) for n in test_neg], dtype=np.float64)
y_te = np.array([1] * len(test_pos) + [0] * len(test_neg), dtype=np.int64)

clf = LogisticRegression(penalty="l2", C=1.0, max_iter=2000, solver="lbfgs", class_weight="balanced")
clf.fit(X_tr, y_tr)
y_pred = clf.predict(X_te)
y_prob = clf.predict_proba(X_te)[:, 1]

feature_names = ["length", "vec_kw_count", "rast_kw_count", "vec_ratio", "rast_ratio",
                 "dup_ratio", "consec_dup_ratio", "len_ge_3", "len_ge_5",
                 "has_2plus_vec", "vec_dominant", "rast_dominant"]

report = {
    "schema": "qgis_reranker_baseline_experiment.v1",
    "data": {
        "total_v2_chains": len(v2_records),
        "matched_with_facts": len(positives),
        "n_positives": len(positives),
        "n_negatives": len(negatives),
        "neg_methods": dict(neg_methods),
        "neg_descriptions": {
            "drop_middle": "Remove one middle operator from the real chain",
            "swap": "Swap two random operators in the real chain",
            "raster_tmpl": "Replace with a generic raster template",
            "dup_insert": "Duplicate a random operator and insert it",
            "safe_tmpl": "Replace with generic vector safe template",
        },
        "split_method": "grouped_by_source_file",
        "train": {"n_pos": len(train_pos), "n_neg": len(train_neg)},
        "test": {"n_pos": len(test_pos), "n_neg": len(test_neg), "n_unique_files": len(test_files)},
    },
    "features": {
        "n_features": 12,
        "names": feature_names,
        "definitions": {
            "length": "Number of QGIS operators in the chain",
            "vec_kw_count": "Count of vector-specific keyword hits",
            "rast_kw_count": "Count of raster-specific keyword hits",
            "vec_ratio": "Fraction of ops that are vector",
            "rast_ratio": "Fraction of ops that are raster",
            "dup_ratio": "1 - unique_ops/total_ops",
            "consec_dup_ratio": "Fraction of adjacent pairs that are identical",
            "len_ge_3": "Binary: chain has >= 3 steps",
            "len_ge_5": "Binary: chain has >= 5 steps",
            "has_2plus_vec": "Binary: contains >= 2 vector ops",
            "vec_dominant": "Binary: vector ops > raster ops",
            "rast_dominant": "Binary: raster ops > vector ops",
        },
    },
    "model": {
        "type": "LogisticRegression (L2, C=1.0, class_weight=balanced)",
        "weights": {n: round(float(w), 6) for n, w in zip(feature_names, clf.coef_[0])},
        "intercept": round(float(clf.intercept_[0]), 6),
    },
    "metrics": {
        "accuracy": round(float(accuracy_score(y_te, y_pred)), 4),
        "roc_auc": round(float(roc_auc_score(y_te, y_prob)), 4),
        "pr_auc": round(float(average_precision_score(y_te, y_prob)), 4),
        "confusion_matrix": [[int(confusion_matrix(y_te, y_pred)[0, 0]), int(confusion_matrix(y_te, y_pred)[0, 1])],
                              [int(confusion_matrix(y_te, y_pred)[1, 0]), int(confusion_matrix(y_te, y_pred)[1, 1])]],
    },
    "files": {
        "qgis_reranker_weights.json": str(ROOT / "outputs_v2" / "qgis_reranker_weights.json"),
        "report_json": str(ROOT / "outputs_v2" / "qgis_reranker_baseline_report.json"),
    },
}

out = ROOT / "outputs_v2" / "qgis_reranker_baseline_report.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"Report: {out}")
print(f"\nMetrics: acc={report['metrics']['accuracy']:.4f}, AUC={report['metrics']['roc_auc']:.4f}, PR-AUC={report['metrics']['pr_auc']:.4f}")
print(f"Confusion: {report['metrics']['confusion_matrix']}")
print(f"\nWeights: {json.dumps(report['model']['weights'], indent=2)}")
print(f"Intercept: {report['model']['intercept']}")
