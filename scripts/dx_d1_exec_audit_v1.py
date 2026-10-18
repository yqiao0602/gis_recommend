#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D1 execution-completeness audit (FROZEN before results).

Verifies, over the pulled mirror:
  - 94 expected records present (A + B per step), missing itemized;
  - every record's prompt_sha16 equals the frozen prompt hash;
  - raw/gen hashes match the commit markers;
  - collects failed/anomalous records (never deletes them).
Writes D1_EXEC_AUDIT_V1.json.
"""
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
D1 = (REPO / ("docs/reports/route2_p0_contract/plan_pipeline_v1/"
              "planning_capability_audit_v1/diag50_v1/dx_v1/dx50_v1/"
              "dx50_full_v1/d1_v1"))


def sha16(s):
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def main(root):
    root = Path(root)
    prompts = json.loads((D1 / "D1_PROMPTS_V1.json").read_text(encoding="utf-8"))
    frozen = {(p["step_key"], p["arm"]): p for p in prompts}
    missing, bad_prompt, bad_commit, anomalous = [], [], [], []
    n = 0
    for (key, arm), p in sorted(frozen.items()):
        tid, snum = key.split("#S")
        d = root / tid / "S2" / f"S{snum}" / arm
        raw_p, gen_p, cm_p = d / "raw_output.txt", d / "gen.json", d / "commit.json"
        if not (raw_p.exists() and gen_p.exists() and cm_p.exists()):
            missing.append(f"{key}|{arm}")
            continue
        n += 1
        g = json.loads(gen_p.read_text(encoding="utf-8"))
        if g.get("prompt_sha16") != sha16(p["prompt"]):
            bad_prompt.append(f"{key}|{arm}")
        cm = json.loads(cm_p.read_text(encoding="utf-8"))
        rb = raw_p.read_bytes()
        gb = gen_p.read_bytes()
        if hashlib.sha256(rb).hexdigest() != cm.get("raw_sha256") \
                or hashlib.sha256(gb).hexdigest() != cm.get("metadata_sha256"):
            bad_commit.append(f"{key}|{arm}")
        if g.get("status") != "OK" or g.get("term") is None:
            anomalous.append({"key": f"{key}|{arm}", "status": g.get("status"),
                              "term": g.get("term")})
    out = {"n_expected": len(frozen), "n_records": n, "missing": missing,
           "all_prompt_sha_ok": not bad_prompt, "bad_prompt": bad_prompt,
           "all_commit_ok": not bad_commit, "bad_commit": bad_commit,
           "failed_or_anomalous": anomalous,
           "model": "/home/qy/models/Qwen3.5/Qwen3.5-9B-Base",
           "runner": "dx_run_stage_v2 (sha 0a615fb7...)",
           "termination": "dx_termination_v2 (sha 3742a97e...)"}
    (D1 / "D1_EXEC_AUDIT_V1.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
    print(json.dumps({k: out[k] for k in
                      ("n_expected", "n_records", "missing",
                       "all_prompt_sha_ok", "all_commit_ok", "failed_or_anomalous")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1])
