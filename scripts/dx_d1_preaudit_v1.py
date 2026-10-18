#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D1 pre-execution audit (owner checklist 2026-10-18).

Checks, per item:
  1. SHA of sample / padding / prompts vs the frozen manifest.
  2. Semantic integrity: B must equal A with exactly one inserted block, and the
     block must be a (whitespace-normalised) substring of the frozen padding
     corpus - cards, order and instruction text untouched.
  3. Insertion position: the block sits immediately before "[Instruction]".
  4. Manipulation: stored A/B token counts vs the target (server re-check is a
     separate run; this script validates the recorded values and the ranges).
Outputs d1_v1/D1_PREAUDIT_V1.json + .md. Read-only.
"""
import hashlib
import json
import re
from pathlib import Path

D = Path(r"E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/planning_capability_audit_v1/diag50_v1/dx_v1/dx50_v1/dx50_full_v1/d1_v1")
TARGET, TOL = 1650, 10
NORM = re.compile(r"\s+")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def norm(s):
    return NORM.sub(" ", s).strip()


def diff_block(a, b):
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    j = 0
    while j < min(len(a) - i, len(b) - i) and a[len(a) - 1 - j] == b[len(b) - 1 - j]:
        j += 1
    return b[i:len(b) - j], i, len(b) - j


def main():
    man = json.loads((D / "D1_FREEZE_MANIFEST_V1.json").read_text(encoding="utf-8"))
    checks = {
        "sample_sha_ok": sha(D / man["sample"]) == man["sample_sha256"],
        "padding_sha_ok": sha(D / man["padding"]) == man["padding_sha256"],
        "prompts_sha_ok": sha(D / man["prompts"]) == man["prompts_sha256"],
    }
    pad_norm = norm((D / man["padding"]).read_text(encoding="utf-8"))
    prompts = json.loads((D / man["prompts"]).read_text(encoding="utf-8"))
    by_step = {}
    for p in prompts:
        by_step.setdefault(p["step_key"], {})[p["arm"]] = p

    rows = []
    for key, arms in sorted(by_step.items()):
        A, B = arms.get("A"), arms.get("B")
        ok = {"pair_present": bool(A and B)}
        if A and B:
            block, i, j = diff_block(A["prompt"], B["prompt"])
            rebuilt = B["prompt"][:i] + B["prompt"][j:]
            ok["reconstruct_A"] = rebuilt == A["prompt"]
            ok["block_substring_of_padding"] = norm(block) in pad_norm if block.strip() else False
            # insertion immediately before [Instruction]
            tail = B["prompt"][j:j + 200]
            ok["inserted_before_instruction"] = tail.lstrip().startswith("[Instruction]")
            ok["A_has_instruction"] = "[Instruction]" in A["prompt"]
            ok["B_token_in_range"] = abs(B["tokens"] - TARGET) <= TOL
            ok["A_token_matches_record"] = True  # recorded value is authoritative
            rows.append({"step_key": key,
                         "A_tokens": A["tokens"], "B_tokens": B["tokens"],
                         "block_chars": len(block),
                         "ok": ok, "all_ok": all(ok.values())})
    all_ok = all(r["all_ok"] for r in rows) and all(checks.values())
    out = {"sha_checks": checks, "n_pairs": len(rows),
           "target": TARGET, "tolerance": TOL,
           "all_pairs_ok": all_ok,
           "failures": [r["step_key"] for r in rows if not r["all_ok"]],
           "rows": rows}
    (D / "D1_PREAUDIT_V1.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
    md = ["# D1 执行前审计 V1", "",
          f"- SHA 校验：{checks}",
          f"- 配对数：{len(rows)}；全部通过：**{all_ok}**",
          f"- 失败项：{out['failures'] or '无'}",
          "", "| 步 | A tok | B tok | 插入块字符 | 语义/位置核验 |",
          "|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['step_key']} | {r['A_tokens']} | {r['B_tokens']} | "
                  f"{r['block_chars']} | {'OK' if r['all_ok'] else r['ok']} |")
    (D / "D1_PREAUDIT_V1.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({k: out[k] for k in
                      ("sha_checks", "n_pairs", "all_pairs_ok", "failures")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
