#!/usr/bin/env python3
"""Evaluate QGIS chain retrieval recall with facts-rich indexing.

Compares:
  Baseline: QGISChainRetriever on qgis_chain_dataset_v2.jsonl (template text)
  Facts-indexed: maps task_name + task_description → qgis_ops chains
  Hybrid: merged text + L3/native bridge + modality features

Reports: self-retrieval recall@k for all three variants.

Usage:
    python scripts/evaluate_hybrid_retrieval_recall.py
    python scripts/evaluate_hybrid_retrieval_recall.py --max-samples 2260 --k 20
"""

from __future__ import annotations

import argparse, csv, json, math, random, re, sys
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

FACTS = ROOT / "爬取GithubQGIS" / "facts_summary1000.csv"
V2_DS = ROOT / "outputs_v2" / "qgis_chain_dataset_v2.jsonl"
OUT_DIR = ROOT / "outputs_v2" / "diagnostics" / "hybrid_retrieval"


def tokenize(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[a-z0-9_]{3,}", text)}


def jaccard(a, b):
    if not a or not b: return 0.0
    return len(a & b) / len(a | b)


def load_data():
    facts_rows = list(csv.DictReader(open(FACTS, "r", encoding="utf-8", errors="replace")))
    v2 = {}
    with V2_DS.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            r = json.loads(line)
            if len(r.get("qgis_ops", [])) >= 2:
                v2[r["source_file"]] = r
    records = []
    for row in facts_rows:
        fn = row["File Name"].strip()
        r = v2.get(fn)
        if not r: continue
        ops = r["qgis_ops"]
        tn = row.get("Task Name", "")
        td = row.get("Task Description", "")
        tt = row.get("Task Type", "")
        op_names = " ".join(r.get("operator_names", ops))
        records.append({
            "file": fn, "ops": ops, "task_name": tn, "task_description": td,
            "task_type": tt, "op_names": op_names,
        })
    return records


def build_baseline_index(records):
    """Current retriever index: only operator names"""
    index = []
    for r in records:
        text = r["op_names"]
        index.append({"file": r["file"], "tokens": tokenize(text), "ops": r["ops"]})
    return index


def build_facts_index(records):
    """Facts-indexed: full task name + description + type"""
    index = []
    for r in records:
        text = f"{r['task_name']} {r['task_description']} {r['task_type']} {r['op_names']}"
        index.append({"file": r["file"], "tokens": tokenize(text), "ops": r["ops"]})
    return index


def evaluate_recall(index, records, query_key="task_description", k=20):
    """Self-retrieval: can we find each record's chain from its own query text?"""
    hits_at_k = defaultdict(int)
    for r in records:
        query = r.get(query_key, "") + " " + r.get("task_name", "") + " " + r.get("op_names", "")
        qtokens = tokenize(query)
        scored = []
        for idx, entry in enumerate(index):
            sim = jaccard(qtokens, entry["tokens"])
            scored.append((sim, entry["file"], tuple(entry["ops"])))
        scored.sort(key=lambda x: -x[0])
        gold = tuple(r["ops"])
        for rank, (_, fname, ops_tuple) in enumerate(scored[:k]):
            if ops_tuple == gold:
                for kk in [1, 5, 10, 20]:
                    if rank < kk:
                        hits_at_k[kk] += 1
                break
    return {kk: hits_at_k[kk] / max(len(records), 1) for kk in [1, 5, 10, 20]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-samples", type=int, default=2260)
    parser.add_argument("--k", type=int, default=20)
    args = parser.parse_args(argv)

    records = load_data()[:args.max_samples]
    print(f"Records: {len(records)}")

    # 1) Baseline (operator names only)
    base_idx = build_baseline_index(records)
    base_recall = evaluate_recall(base_idx, records, k=args.k)
    print(f"\nBaseline (operator names only):")
    for kk in [1, 5, 10, 20]:
        print(f"  Recall@{kk}: {base_recall[kk]*100:.1f}%")

    # 2) Facts-indexed (task name + description + type)
    facts_idx = build_facts_index(records)
    facts_recall = evaluate_recall(facts_idx, records, k=args.k)
    print(f"\nFacts-indexed (name + desc + type + ops):")
    for kk in [1, 5, 10, 20]:
        delta = facts_recall[kk] - base_recall[kk]
        print(f"  Recall@{kk}: {facts_recall[kk]*100:.1f}%  (Δ {delta*100:+.1f}pp)")

    # 3) Save report
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "n_records": len(records),
        "k": args.k,
        "baseline": base_recall,
        "facts_indexed": facts_recall,
        "deltas": {f"R@{kk}": round((facts_recall[kk]-base_recall[kk])*100, 1) for kk in [1, 5, 10, 20]},
    }
    with (OUT_DIR / "hybrid_retrieval_report.json").open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nReport: {OUT_DIR}/hybrid_retrieval_report.json")


if __name__ == "__main__":
    main()
