#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PCA one-shot retrieval materialization (instrument V2 rules, frozen).

Rules (pca_generation_instrument_freeze_v1.json §V2.retrieval):
  source: capability profile v0.4 (SHA 95ae97bc...)
  model: sentence-transformers/all-MiniLM-L6-v2 (revision recorded)
  normalize_embeddings=True; similarity=cosine
  query=task_text; corpus=operator_id + ' | ' + description; top_k=15
  card render: "{oid} | {desc} | inputs: {in} -> outputs: {out} | params: {mandatory name(type) x<=12}"
  tie-break seed 20261013; output frozen ONCE, never recomputed at run time.
Queries: all 59 main tasks (B 19 + A 20 + C 20) — arm C only, but materialized
for the whole manifest set in one pass.
"""
import json, hashlib, numpy as np

D = "docs/reports/route2_p0_contract/plan_pipeline_v1/planning_capability_audit_v1/"
OUT = D + "pca_retrieval_v1.json"
SEED = 20261013

def _embed(model, tok, texts, bs=64):
    """MiniLM mean-pooling + L2 normalize (equivalent to ST encode with
    normalize_embeddings=True); frozen rule implementation via transformers."""
    import torch
    out = []
    with torch.no_grad():
        for i in range(0, len(texts), bs):
            enc = tok(texts[i:i + bs], padding=True, truncation=True,
                      max_length=256, return_tensors="pt")
            o = model(**enc).last_hidden_state
            m = enc["attention_mask"].unsqueeze(-1).float()
            v = (o * m).sum(1) / m.sum(1).clamp(min=1e-9)
            v = torch.nn.functional.normalize(v, p=2, dim=1)
            out.append(v.cpu().numpy())
    import numpy as np
    return np.vstack(out)

def main():
    from transformers import AutoModel, AutoTokenizer
    _mname = "../pca_data_ref/minilm"
    tok = AutoTokenizer.from_pretrained(_mname)
    model = AutoModel.from_pretrained(_mname)
    model.eval()
    rev_name = model.name_or_path

    prof = json.load(open("route2_training/profile/qgis_operator_capability_profile_v0_4.json", encoding="utf-8"))
    ops = []
    for oid, v in prof.items():
        if oid == "_meta":
            continue
        desc = (v.get("description") or oid.replace(":", " ")).strip()
        ins = ", ".join(v.get("input_types_norm", [])) or "-"
        lb = v.get("layer_b_params") or {}
        outs = ", ".join(p.get("type", "") for p in (lb.get("outputs") or [])) or "-"
        params = [p for p in (lb.get("parameters") or []) if p.get("mandatory")]
        ptxt = "; ".join(f"{p['name']}({p.get('type','')})" for p in params[:12])
        card = f"{oid} | {desc} | inputs: {ins} -> outputs: {outs} | params: {ptxt}"
        ops.append({"oid": oid, "corpus": f"{oid} | {desc}", "card": card})
    print("operators:", len(ops))

    # queries: all 59 main tasks
    queries = []
    b = json.load(open(D + "pca_b_chain_audit_v1.json", encoding="utf-8"))
    a = json.load(open(D + "pca_a_gold_worksheet_v1.json", encoding="utf-8"))
    c = json.load(open(D + "pca_c_group_tasks_gold_v2.json", encoding="utf-8"))
    for r in b["rows"]:
        q = next(x for x in json.load(open(D + "pca_b_group_final_inputs_v1.json", encoding="utf-8"))["rows"]
                 if x["wid"] == r["wid"])
        queries.append({"task_id": r["wid"], "group": "B", "task_text": q["final_text"]})
    for r in a["rows"]:
        queries.append({"task_id": r["task_id"], "group": "A", "task_text": r["task_text"]})
    for r in c["rows"]:
        queries.append({"task_id": r["task_id"], "group": "C", "task_text": r["task_text"]})
    assert len(queries) == 59

    import random
    rng = random.Random(SEED)
    cemb = _embed(model, tok, [o["corpus"] for o in ops])
    out_rows = []
    for q in queries:
        qe = _embed(model, tok, [q["task_text"]])[0]
        sims = cemb @ qe
        order = sorted(range(len(ops)), key=lambda i: (-sims[i], rng.random()))
        top = [{"rank": k + 1, "operator_id": ops[i]["oid"], "score": round(float(sims[i]), 6),
                "card": ops[i]["card"]} for k, i in enumerate(order[:15])]
        out_rows.append({"task_id": q["task_id"], "group": q["group"], "top15": top})
    payload = {"_meta": {
        "freeze": "PCA retrieval one-shot materialization v1 (frozen; never recomputed at run time)",
        "model": rev_name, "hf_revision": "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
        "local_copy": "../pca_data_ref/minilm",
        "rules": "normalize+cosine, corpus=oid+desc, top_k=15, tie-break seed 20261013",
        "profile_sha_prefix": "95ae97bc36004292", "n_queries": len(queries), "n_operators": len(ops)},
        "rows": out_rows}
    blob = json.dumps(payload, ensure_ascii=False, indent=1)
    open(OUT, "w", encoding="utf-8", newline="").write(blob)
    print("queries:", len(queries), "| file_sha256:", hashlib.sha256(blob.encode()).hexdigest()[:16])

if __name__ == "__main__":
    main()
