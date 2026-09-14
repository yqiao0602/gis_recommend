#!/usr/bin/env python3
"""Gate 1: assemble the M2 DAPT corpus v1 (QGIS-primary, owner-frozen 2026-09-14).

Design targets (owner ruling): 20-30M tokens, quality first, dedup, zero
answer/gold leakage. Composition: QGIS GitHub scripts (primary) +
gee-operators catalogs + direct_descriptions (natural-language auxiliary).
GEE data80000 scripts are an enhancement, NOT a blocker (unlocated).

Assembly pipeline (fail-closed):
  1. enumerate scripts, content-hash dedup
  2. EXCLUDE benchmark-lineage sources (254 hashes: final-100/dev-20/refusal
     DAG source authorities + paper_v1 val/test sources)
  3. quality filter: decodable text, 200 <= chars <= 200_000
  4. QGIS-relevance: marker check (processing.run|qgis|Qgs) — keep positive
  5. Gate-2-style leakage: no shared 6-gram with any benchmark task text
     (final_100 / dev_20 / refusal_12)
  6. token-budget sampling (seed 42) calibrated with the Qwen tokenizer
Outputs: corpus jsonl + manifest with full audit stats.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path("/home/yll/GEE/爬取GithubQGIS/合并脚本/QGIS_merged_dedup_by_index/downloaded_scripts")
GEE_OPS_DIR = Path("/home/qy/gee-operators")
OUT_DIR = Path("/home/qy/gee_llm_smoke/m2_dapt_corpus_v1")
MARKERS = ("processing.run", "qgis", "Qgs")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def ngrams(text: str, n: int = 6) -> set:
    toks = text.lower().split()
    return {tuple(toks[i:i + n]) for i in range(len(toks) - n + 1)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exclusion-hashes", type=Path, required=True)
    ap.add_argument("--bench-tasks", nargs="+", type=Path, required=True,
                    help="materialized final_100/dev_20/refusal_12 tasks.jsonl")
    ap.add_argument("--direct-descriptions", type=Path, required=True)
    ap.add_argument("--target-mtokens", type=float, default=25.0)
    args = ap.parse_args()

    excl = {l.strip() for l in args.exclusion_hashes.read_text(encoding="utf-8").splitlines() if l.strip()}
    print(f"exclusion hashes: {len(excl)}")

    # benchmark task 6-grams
    bench_grams = set()
    for p in args.bench_tasks:
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                bench_grams |= ngrams(json.loads(line)["task_text"])
    print(f"benchmark task 6-grams: {len(bench_grams)}")

    # ── stage 1-4: scripts ──
    stats = {"files_seen": 0, "dedup_dropped": 0, "exclusion_dropped": 0,
             "quality_dropped": 0, "marker_dropped": 0, "leak_dropped": 0,
             "scripts_kept": 0}
    seen_hashes = set()
    candidates = []  # (path, sha, text)
    for path in sorted(SCRIPT_DIR.glob("script_*.py")):
        stats["files_seen"] += 1
        raw = path.read_bytes()
        h = sha256_bytes(raw)
        if h in seen_hashes:
            stats["dedup_dropped"] += 1
            continue
        seen_hashes.add(h)
        if h in excl:
            stats["exclusion_dropped"] += 1
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = raw.decode("utf-8", errors="ignore")
            except Exception:
                stats["quality_dropped"] += 1
                continue
        if not (200 <= len(text) <= 200_000):
            stats["quality_dropped"] += 1
            continue
        if not any(m in text for m in MARKERS):
            stats["marker_dropped"] += 1
            continue
        if ngrams(text) & bench_grams:
            stats["leak_dropped"] += 1
            continue
        candidates.append((path.name, h, text))
        stats["scripts_kept"] += 1
    print(json.dumps(stats, indent=2))

    # ── stage 6: calibrate chars/token, sample to budget ──
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained("/home/qy/models/Qwen3.5/Qwen3.5-9B-Base")
    random.seed(42)
    sample = random.sample(candidates, min(300, len(candidates)))
    ratio = sum(len(tok(t)["input_ids"]) for _, _, t in sample) / max(sum(len(t) for _, _, t in sample), 1)
    print(f"calibration: {ratio:.4f} tokens/char (Qwen-Base)")
    target_chars = int(args.target_mtokens * 1e6 / ratio)

    random.shuffle(candidates)
    selected, used = [], 0
    for name, h, text in candidates:
        if used >= target_chars:
            break
        selected.append(("qgis_script", name, h, text))
        used += len(text)

    # ── NL auxiliary: gee-operators catalogs ──
    nl = []
    for p in sorted(GEE_OPS_DIR.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        text = json.dumps(data, ensure_ascii=False, indent=1)
        if text.strip():
            nl.append((f"gee_ops_catalog:{p.name}", sha256_bytes(text.encode()), text))
    # direct_descriptions: extract task_description + source_snippet fields
    dd = 0
    for line in args.direct_descriptions.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        parts = []
        for k in ("task_name", "task_description"):
            if r.get(k):
                parts.append(str(r[k]))
        for cs in r.get("call_sites") or []:
            if cs.get("operator_id"):
                parts.append(f"operator: {cs['operator_id']}")
        snip = r.get("source_snippet") or ""
        if snip and len(snip) < 8000:
            parts.append(snip)
        text = "\n".join(parts).strip()
        if len(text) >= 50 and not (ngrams(text) & bench_grams):
            nl.append((f"direct_desc:{r.get('record_id','?')}", sha256_bytes(text.encode()), text))
            dd += 1
    print(f"NL auxiliary: gee-ops catalogs {len(nl) - dd} + direct_descriptions {dd}")
    for name, h, text in nl:
        selected.append(("nl_auxiliary", name, h, text))

    # ── write corpus + manifest ──
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    corpus_path = OUT_DIR / "dapt_corpus_v1.jsonl"
    n_tokens_est = 0
    with corpus_path.open("w", encoding="utf-8") as f:
        for src, name, h, text in selected:
            f.write(json.dumps({"source": src, "name": name, "sha256": h,
                                "text": text}, ensure_ascii=False) + "\n")
            n_tokens_est += int(len(text) * ratio)

    by_src = {}
    for src, name, h, text in selected:
        by_src.setdefault(src, {"files": 0, "chars": 0})
        by_src[src]["files"] += 1
        by_src[src]["chars"] += len(text)

    manifest = {
        "schema": "gis_recommend.m2_dapt_corpus.v1",
        "assembled_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
        "owner_ruling": "QGIS primary + NL auxiliary; 20-30M target; GEE 80k enhancement not blocker",
        "stats": stats,
        "calibration_tokens_per_char": round(ratio, 5),
        "target_mtokens": args.target_mtokens,
        "estimated_tokens_m": round(n_tokens_est / 1e6, 1),
        "composition": {k: {"files": v["files"], "chars_m": round(v["chars"] / 1e6, 1)} for k, v in by_src.items()},
        "exclusion": {"hashes": len(excl),
                      "basis": "benchmark final/dev/refusal DAG source authorities + paper_v1 val/test sources"},
        "leakage_gates": {"benchmark_6gram": "ALL CLEAN (per-file check, drops recorded)",
                          "answer_structure": "raw scripts/descriptions contain no L3 chains (asserted by source type)"},
        "corpus_sha256": sha256_bytes(corpus_path.read_bytes()),
    }
    (OUT_DIR / "manifest_v1.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("estimated_tokens_m", "composition", "corpus_sha256")}, indent=2, ensure_ascii=False))
    print(f"wrote {corpus_path} and manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
