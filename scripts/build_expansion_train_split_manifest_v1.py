# -*- coding: utf-8 -*-
"""Build the G0 train-split sampling manifest for expansion validation v1.

One-shot, deterministic. Reads the FROZEN G0 corpus (b1_gee_stage_train.jsonl,
SHA 09c37104...02a2, path pinned in schema_pilot_summary_v1.json), keeps
split=='train' rows, resolves each script id to its raw source path under
.tmp_gee_batch13_sources/Data, and writes a jsonl manifest consumed by
build_expansion_validation_sample_v1.py --execute --train-split.

No sampling happens here; no detector runs; no pilot exclusion (the sampling
script excludes pilots itself, single source of truth).
"""

import glob
import hashlib
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G0_CORPUS = os.path.abspath(os.path.join(REPO, "..", "04_DIAG_WORK",
                                         "b1_gee_stage_train.jsonl"))
FROZEN_G0_SHA = "09c37104d2fd33138cbc15d5d23676d4d169acf1d0cfb8057a0baf3a100c02a2"
SRC_ROOT = os.path.join(REPO, ".tmp_gee_batch13_sources", "Data")
OUT = os.path.join(
    REPO, "docs", "reports", "gee_semantic_planner_v1_pilot_round3",
    "expansion_validation_prep_v1", "expansion_train_split_manifest_v1.jsonl")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    got = sha256_file(G0_CORPUS)
    if got != FROZEN_G0_SHA:
        print(f"FATAL: G0 corpus SHA drifted: {got}", file=sys.stderr)
        return 2

    idx = {}
    for p in glob.glob(os.path.join(SRC_ROOT, "data*", "*.txt")):
        sid = os.path.splitext(os.path.basename(p))[0]
        idx.setdefault(sid, os.path.relpath(p, REPO).replace(os.sep, "/"))

    n = missing = 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(G0_CORPUS, encoding="utf-8") as f, \
            open(OUT, "w", encoding="utf-8") as out:
        for line in f:
            d = json.loads(line)
            if d.get("split") != "train":
                continue
            sid = d["script"]
            if sid in idx:
                out.write(json.dumps({"script": sid, "path": idx[sid]},
                                     ensure_ascii=False) + "\n")
                n += 1
            else:
                missing += 1

    meta = {
        "g0_corpus": G0_CORPUS,
        "g0_sha256": got,
        "train_rows_with_source": n,
        "train_rows_missing_source": missing,
        "manifest": OUT,
        "manifest_sha256": sha256_file(OUT),
        "note": "train split only; per-script source SHA pinned at sampling time",
    }
    with open(OUT.replace(".jsonl", "_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
