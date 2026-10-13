#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PCA generation-instrument FREEZE + manifest + discipline (owner round-15).

Four pre-generation verifications materialized:
  V1 frozen-object SHA consistency (recomputed full digests, load paths);
  V2 instrument freeze (prompt text, retrieval rules, model/tokenizer,
     decode params, output schema, seed strategy, retry rules, arm diffs);
  V3 manifest: 183 = 177 main-formal (59 tasks x 3 arms) + 6 B-prime
     diagnostics; retry/cache/sample-count conventions preregistered;
  V4 storage discipline (per-task/arm/run layout, read-only raw outputs,
     separated parse/score/review stores, exclusion fields consumed).
"""
import json, hashlib

D = "docs/reports/route2_p0_contract/plan_pipeline_v1/planning_capability_audit_v1/"
OUT = D + "pca_generation_instrument_freeze_v1.json"
MAN = D + "pca_generation_manifest_v1.json"

PROMPT = """[Task]
{task_text}

[Instruction]
You are a GIS workflow planner. Decompose the task above into an ordered plan of operation steps. For each step write:
1. a short step name;
2. what the step does semantically (its inputs and outputs);
3. which earlier steps it depends on, if any.
State any data conditions the plan must respect (coordinate systems, data types, units, missing values) where relevant. Do not limit yourself to any fixed vocabulary of operations. End your plan with the line: END OF PLAN"""

ARM_C_INSERT = """[OPERATOR REFERENCE]
The following operator cards may be relevant to this task; you may use them or not:
{cards}
"""

BPRIME_SEP = ("\nWorkflow blueprint: output JSON with keys stages (ordered semantic stages with per-stage "
              "repeat counts) and repetition_groups (groups with repeat>1, each with iteration_hint from: "
              "per_band, per_class, per_year, per_feature, generic_each, unspecified).")

def main():
    sha_v = json.load(open(D + "_sha_verify_tmp.json", encoding="utf-8"))

    prompt_sha = hashlib.sha256(PROMPT.encode()).hexdigest()
    insert_sha = hashlib.sha256(ARM_C_INSERT.encode()).hexdigest()
    bprime_sha = hashlib.sha256(BPRIME_SEP.encode()).hexdigest()

    freeze = {
      "_meta": {
        "freeze": "PCA generation instrument v1 (owner round-15 four verifications)",
        "authorization": "round-15: after the four verifications are recorded, launch per frozen protocol "
                         "without a further principle-approval round",
      },
      "V1_frozen_objects": {
        "full_sha256_and_paths": sha_v,
        "load_rule": "generation and scoring scripts MUST load files from these paths and MUST re-verify "
                     "sha256 at load time; any mismatch aborts before generation",
      },
      "V2_instrument": {
        "prompt": {
          "template": PROMPT,
          "template_sha256": prompt_sha,
          "placeholders": ["{task_text}"],
          "constraints": ["no 21-family vocabulary", "no operator IDs required", "no training-format cues",
                          "operator names in model output are neither rewarded nor penalized (semantic scoring only)"],
        },
        "arm_C_operator_reference": {"insert_text": ARM_C_INSERT, "insert_sha256": insert_sha,
                                     "placeholder": ["{cards}"]},
        "retrieval": {
          "source": sha_v["capability_profile"]["path"] + " (SHA 95ae97bc36004292...)",
          "model": "sentence-transformers/all-MiniLM-L6-v2 (revision hash recorded at execution into pca_retrieval_v1.json)",
          "config": {"normalize_embeddings": True, "similarity": "cosine",
                     "query": "task_text", "corpus": "operator_id + ' | ' + description",
                     "top_k": 15},
          "card_render": "{operator_id} | {description} | inputs: {normalized inputs} -> outputs: {normalized outputs} | params: {mandatory params: name(type), truncated at 12 params}",
          "freezing": "one-shot materialization into pca_retrieval_v1.json (per-task top-15 ids + scores + rendered card text) BEFORE first generation; SHA recorded; shared by all arms/runs; never recomputed at run time",
        },
        "model": {
          "base": "/home/qy/models/Qwen3.5/Qwen3.5-9B-Base (tokenizer same path; weight fingerprint recorded at load into run ledger)",
          "adapter_B_C": "/home/qy/stage1_run_planner_v2_fmt/stage1_adapter (frozen; file SHA ledger recorded at load)",
          "precision": "NF4 double-quant, bnb4bit_compute_dtype=bfloat16, bnb4bit_quant_type=nf4, use_double_quant=True",
          "arm_A": "Base only (no adapter)",
        },
        "decode": {"greedy": True, "no_repeat_penalty": True, "no_ngram_constraints": True,
                   "max_new_tokens": 768, "batch_size": 8, "left_padding": True,
                   "input_truncation": 1024, "eos_pad_tokens": "tokenizer eos + pad",
                   "recorded_per_row": ["gen_tokens", "hit_cap"]},
        "termination_health": {"captured": ["END_OF_PLAN hit", "EOS", "CAP_TRUNC", "DEGENERATE_LOOP"],
                               "note": "termination quality is a MEASURED capability signal; no termination fixes applied"},
        "arm_Bprime_diag": {
          "purpose": "format-sensitivity diagnostic ONLY (never enters main comparison)",
          "prompt": "B-group frozen task text + training-format separator (below) -> Blueprint JSON -> deterministic restatement to semantic steps via frozen translator",
          "separator": BPRIME_SEP, "separator_sha256": bprime_sha,
          "tasks": ["W000473", "W056274", "W44487(A)", "W79576(A)", "PCA-C-07", "PCA-C-11"],
          "expansion_rule": "if arm-B content_assessable_rate < 0.70 over the 60 main tasks -> extend B' to all B tasks (mechanical, preregistered)",
        },
        "seeds": {"strategy": "greedy decoding is deterministic; seed 20261013 governs retrieval tie-breaks "
                              "and human-review sampling (both preregistered)"},
        "retry": {"hardware_retry": "OOM/CUDA/transient errors: up to 2 retries, each recorded with attempt number in run ledger",
                  "semantic_non_retry": "hit_cap / degenerate loops / empty content are MEASURED signals — never retried",
                  "first_result_rule": "first successful completion is the recorded result; retries never overwrite"},
      },
      "V3_manifest": {
        "main_formal": {"tasks": 59, "arms": 3, "generations": 177,
                        "breakdown": {"B_group": "19 x 3 = 57", "A_group": "20 x 3 = 60", "C_group": "20 x 3 = 60"}},
        "bprime_diagnostic": {"tasks": 6, "arms": 1, "generations": 6},
        "total_attempts": 183,
        "counting_conventions": {
          "cache": "no caching — every generation is an independent recorded attempt",
          "multi_sampling": "one sample per (task, arm) — no temperature sampling",
          "retry_counting": "hardware retries logged separately; do NOT inflate the 183 count",
          "W056058": "GENERATED and SCORED for diagnostics; EXCLUDED from main scoring denominator (ledger field consumed)"},
      },
      "V4_discipline": {
        "layout": "outputs/{arm}/{task_id}/run_{run_id}.json (raw) — arms never share files; overwriting foreign outputs forbidden",
        "raw_readonly": "raw model outputs are read-only after write; parse, score, and human-review stores are separate files",
        "immutability": "after first formal result: no prompt/retrieval-card/gold/scoring-rule modification; defects -> versioned amendment per protocol",
        "exclusions": {"W056058": "EXCLUDED_FROM_MAIN_SCORING (consumed from ledger owner_disposition field)",
                       "P05": "exploratory — reported separately", "P06": "structural_exploratory — excluded from main pairing aggregation"},
      },
    }
    blob = json.dumps(freeze, ensure_ascii=False, indent=1)
    open(OUT, "w", encoding="utf-8", newline="").write(blob)
    print("instrument freeze sha256:", hashlib.sha256(blob.encode()).hexdigest()[:16])

    # ---- manifest: explicit per-(task, arm) list ----
    a = json.load(open(D + "pca_a_gold_worksheet_v1.json", encoding="utf-8"))
    c = json.load(open(D + "pca_c_group_tasks_gold_v2.json", encoding="utf-8"))
    b = json.load(open(D + "pca_b_chain_audit_v1.json", encoding="utf-8"))
    items = []
    for arm in ("A_base", "B_stage1", "C_stage1_tool"):
        for r in b["rows"]:
            items.append({"run_key": f"{arm}/{r['wid']}", "group": "B", "task_id": r["wid"], "arm": arm,
                          "main_scoring": r["wid"] != "W056058"})
        for r in a["rows"]:
            items.append({"run_key": f"{arm}/{r['task_id']}", "group": "A", "task_id": r["task_id"], "arm": arm,
                          "main_scoring": True})
        for r in c["rows"]:
            items.append({"run_key": f"{arm}/{r['task_id']}", "group": "C", "task_id": r["task_id"], "arm": arm,
                          "main_scoring": True})
    for tid in freeze["V2_instrument"]["arm_Bprime_diag"]["tasks"]:
        grp = "B" if tid.startswith("W") and not tid.startswith("PCA") else tid.split("-")[1][:1]
        items.append({"run_key": f"Bprime_diag/{tid}", "group": "Bprime", "task_id": tid, "arm": "Bprime_diag",
                      "main_scoring": False})
    man = {"_meta": {"total": len(items),
                     "main_formal": sum(1 for i in items if i["arm"] != "Bprime_diag"),
                     "bprime_diag": sum(1 for i in items if i["arm"] == "Bprime_diag"),
                     "instrument_freeze": OUT},
           "items": items}
    mblob = json.dumps(man, ensure_ascii=False, indent=1)
    open(MAN, "w", encoding="utf-8", newline="").write(mblob)
    print("manifest items:", len(items), "| main:", man["_meta"]["main_formal"],
          "| bprime:", man["_meta"]["bprime_diag"])
    print("manifest sha256:", hashlib.sha256(mblob.encode()).hexdigest()[:16])

if __name__ == "__main__":
    main()
