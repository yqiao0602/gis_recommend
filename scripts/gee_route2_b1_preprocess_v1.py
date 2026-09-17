#!/usr/bin/env python3
"""Route-2 P0-4 preprocessing: semantic workflow RLE + post-RLE run-cap=3.

Owner ruling 2026-09-17 (final):
  1) RLE ON  - consecutive identical categories are repeated calls, not
     distinct semantics; raw chain is preserved for audit.
  2) post-RLE run-cap=3 ON - periodic patterns (A->B->A->B...) that repeat
     >= 3 times are template/parameter-binding artifacts; collapsed to one
     period. Applied AFTER RLE so real workflow structure is never cut.
  3) B1 supervision = Task -> semantic workflow ONLY. GEE canonical chain
     stays in the row as audit evidence, never as a loss target.

Emits the B1 GEE-stage training file with per-row audit fields:
  semantic_chain_raw / semantic_chain_rle (training target) / run_cap_applied
  / original_semantic_length / final_semantic_length / gee_canonical_chain.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path


def rle(seq: list[str]) -> list[str]:
    out = []
    for c in seq:
        if not out or out[-1] != c:
            out.append(c)
    return out


def run_cap(seq: list[str], cap: int = 3) -> list[str]:
    """Collapse any period-p pattern repeating >= cap times to one period.

    Catches alternating noise (A->B->A->B->...) that RLE cannot. Patterns of
    period 1..cap; a longer genuine repetition of the same period counts as
    distinct processing passes only below cap repeats.
    """
    out, i = [], 0
    while i < len(seq):
        placed = False
        for p in range(1, cap + 1):
            pat = seq[i:i + p]
            if len(pat) < p:
                break
            n = 0
            while i + (n + 1) * p <= len(seq) and seq[i + n * p:i + (n + 1) * p] == pat:
                n += 1
            if n >= cap:
                out.extend(pat)
                i += n * p
                placed = True
                break
        if not placed:
            out.append(seq[i])
            i += 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=Path, required=True,
                    help="semantic_rows.jsonl from gee_route2_semantic_workflow_v1")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cap", type=int, default=3)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    out_rows = []
    raw_l, rle_l, fin_l = [], [], []
    n_capped = 0
    with open(args.rows, encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            raw = r["semantic_workflow"].split(" -> ")
            rr = rle(raw)
            fin = run_cap(rr, args.cap)
            if len(fin) < len(rr):
                n_capped += 1
            raw_l.append(len(raw)); rle_l.append(len(rr)); fin_l.append(len(fin))
            out_rows.append({
                "script": r["script"],
                "split": r["split"],
                "task_type": r["task_type"],
                "instruction": r["instruction"],
                "semantic_chain_raw": r["semantic_workflow"],
                "semantic_chain_rle": " -> ".join(fin),
                "run_cap_applied": len(fin) < len(rr),
                "original_semantic_length": len(raw),
                "final_semantic_length": len(fin),
                "gee_canonical_chain": r["gee_canonical_chain"],
                "author_proxy": r["author_proxy"],
            })

    with open(args.out / "b1_gee_stage_train.jsonl", "w", encoding="utf-8") as fh:
        for r in out_rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    for name, ls in (("raw", raw_l), ("rle", rle_l), ("final", fin_l)):
        ls.sort()
        print(f"{name:6s}: median {statistics.median(ls):.0f} mean {statistics.mean(ls):.1f} "
              f"p90 {ls[int(len(ls)*0.9)]} max {ls[-1]}")
    stats = {
        "rows": len(out_rows),
        "run_cap_applied_rows": n_capped,
        "run_cap_applied_pct": round(100 * n_capped / len(out_rows), 2),
        "tokens": {"raw": sum(raw_l), "rle": sum(rle_l), "final": sum(fin_l),
                    "final_pct_of_raw": round(100 * sum(fin_l) / sum(raw_l), 1)},
        "split_counts": dict(Counter(r["split"] for r in out_rows)),
        "cap": args.cap,
    }
    (args.out / "b1_preprocess_stats.json").write_text(
        json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(stats, indent=1, ensure_ascii=False))
    print(f"wrote {args.out / 'b1_gee_stage_train.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
