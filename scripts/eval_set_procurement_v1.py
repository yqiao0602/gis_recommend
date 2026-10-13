#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reward-synthesis eval-set procurement (owner round-14, item 1).

Source pool: b1_gee_stage authority (128,447 rows, local SHA-verified backup)
  = the model NEVER trained on any task we select, by construction:
  candidates exclude every task in planner_v2_train (P0's training data) by
  BOTH normalized-instruction match AND script-number match.
Stratification: task_type x final chain-length bands, seed 20261013.
Audit trail: pool sizes, exclusion reasons, input/output SHA-256, full
  provenance per selected task.
"""
import hashlib
import json
import random
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RL = REPO / "docs/reports/route2_p0_contract/plan_pipeline_v1/rl_line"
B1 = Path(r"E:\02_projects\03_PythonProject\Operator-recommend-system"
          r"\Algorithm_classification\server_backup_mdzhang_20260927"
          r"\home\qy\system_redesign\outputs_v2\gee_b1_stage_data_v1"
          r"\b1_gee_stage_train.jsonl")
TRAIN = RL / "eval_procurement/planner_v2_train.jsonl"
OUT = RL / "eval_procurement"
SEED = 20261013
N_TASKS = 24


def norm(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "")).strip().lower()


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    random.seed(SEED)
    # ---- training-set exclusion universe ----
    train_norm, train_scripts = set(), set()
    n_train = 0
    with open(TRAIN, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            n_train += 1
            train_norm.add(norm(r.get("task", "")))
            s = r.get("source_row_id")
            if s is not None:
                train_scripts.add(str(s))
                train_scripts.add(f"script_{s}")
    print(f"planner_v2_train: {n_train} rows, "
          f"{len(train_norm)} unique instructions, "
          f"{len(train_scripts)} script ids")

    # ---- candidate pool: never-trained b1 rows ----
    pool = []
    excl = Counter()
    n_b1 = 0
    with open(B1, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            n_b1 += 1
            inst = r.get("instruction", "")
            if not inst or len(norm(inst)) < 40:
                excl["empty_or_too_short"] += 1
                continue
            script = str(r.get("script", ""))
            sid = script.replace("script_", "")
            if norm(inst) in train_norm:
                excl["instruction_in_train"] += 1
                continue
            if script in train_scripts or sid in train_scripts:
                excl["script_in_train"] += 1
                continue
            L = r.get("final_semantic_length") or 0
            if L < 2:
                excl["chain_too_short"] += 1
                continue
            pool.append({"script": script,
                         "task_type": r.get("task_type", ""),
                         "instruction": inst,
                         "final_semantic_length": L,
                         "split_field": r.get("split", "")})
    print(f"b1 rows: {n_b1}, exclusions: {dict(excl)}, pool: {len(pool)}")

    # ---- stratified selection: task_type groups x length bands ----
    for p in pool:
        L = p["final_semantic_length"]
        p["band"] = "short_2_4" if L <= 4 else ("mid_5_8" if L <= 8 else "long_9plus")
    by_key = defaultdict(list)
    for p in pool:
        by_key[(p["task_type"], p["band"])].append(p)
    keys = sorted(by_key, key=lambda kv: -len(by_key[kv]))
    selected, seen_types = [], set()
    # round-robin over (type, band) cells: 3 per band x 8 types = 24
    band_quota = {"short_2_4": 8, "mid_5_8": 8, "long_9plus": 8}
    got = Counter()
    # sort cells for determinism then round-robin by band
    for band in ["short_2_4", "mid_5_8", "long_9plus"]:
        cells = [kv for kv in keys if kv[1] == band]
        random.shuffle(cells)
        per_cell = max(1, band_quota[band] // max(1, min(len(cells), band_quota[band])))
        for kv in cells:
            if got[band] >= band_quota[band]:
                break
            take = min(per_cell, band_quota[band] - got[band], len(by_key[kv]))
            picks = random.sample(by_key[kv], take)
            for p in picks:
                p["band"] = band
                selected.append(p)
                got[band] += 1
    selected = selected[:N_TASKS]
    print(f"selected {len(selected)}: bands {Counter(p['band'] for p in selected)}, "
          f"types {len({p['task_type'] for p in selected})}")

    # ---- manifest + audit ----
    manifest = {
        "purpose": "reward-synthesis EVAL set (never-trained tasks; one-shot)",
        "rules_version_for_later_scoring": "v0.5.1 frozen",
        "seed": SEED,
        "inputs": {
            "b1_gee_stage_train_jsonl": {"path": str(B1),
                                         "sha256": sha256(B1),
                                         "rows": n_b1},
            "planner_v2_train_jsonl": {"path": str(TRAIN),
                                       "sha256": sha256(TRAIN),
                                       "rows": n_train},
        },
        "exclusion_universe": {"by_normalized_instruction": True,
                               "by_script_number": True,
                               "reasons": dict(excl)},
        "contamination_statement": (
            "every selected task is absent from planner_v2_train by BOTH "
            "normalized instruction and script number => P0 never trained on "
            "them; they are also absent from the S2 dry-run/Gate-B sets, which "
            "were drawn FROM planner_v2_train"),
        "stratification": {"bands": dict(band_quota),
                           "got": dict(got),
                           "task_types": sorted({p["task_type"] for p in selected})},
        "selected": selected,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / "eval_set_manifest_v1.json"
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    tasks_path = OUT / "eval_set_24_tasks.jsonl"
    with open(tasks_path, "w", encoding="utf-8") as f:
        for p in selected:
            f.write(json.dumps({"script": p["script"], "task": p["instruction"],
                                "band": p["band"],
                                "final_semantic_length": p["final_semantic_length"]},
                               ensure_ascii=False) + "\n")
    print("manifest:", out_path)
    print("tasks:", tasks_path)
    print("manifest sha256:", sha256(out_path))
    print("tasks sha256:", sha256(tasks_path))


if __name__ == "__main__":
    from collections import defaultdict
    main()
