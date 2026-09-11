# -*- coding: utf-8 -*-
"""Phase 0 pre-check A: task-text language distribution (M1 enhancement route).

Read-only diagnostic over frozen inputs:
  - paper_v1 supervision manifest (train/val/test, GEE + QGIS)
  - benchmark v0.2.1 materialized tasks (dev 20 / final 100 / refusal 12)

Emits sample-level language classes (chinese / english / mixed / empty / other),
character-level script shares, length stats, and the real bert-base-uncased
[UNK] ratio of each text (what the M1 encoder actually sees).

No training, no inference, no modification of any frozen artifact.
Output: docs/reports/m1_phase0_precheck_a_language_v1/language_stats_v1.json
"""

import argparse
import hashlib
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

PAPER_MANIFEST = REPO / "docs/reports/paper_v1_supervision/paper_v1_supervision_manifest.jsonl"
BENCH_DIR = REPO / "docs/reports/qgis_planner_eval_v1/materialized"
OUT_DIR = REPO / "docs/reports/m1_phase0_precheck_a_language_v1"

CJK_RANGES = (
    (0x3400, 0x4DBF),  # CJK ext A
    (0x4E00, 0x9FFF),  # CJK unified ideographs
    (0xF900, 0xFAFF),  # CJK compatibility ideographs
)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_cjk(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in CJK_RANGES)


def classify(text: str) -> dict:
    """Sample-level classification. Decisions happen on alphabetic content
    (CJK ideographs vs Latin letters), mirroring where tokenizer coverage
    actually breaks, not on raw unicode proportions."""
    n_cjk = sum(1 for c in text if is_cjk(c))
    n_lat = sum(1 for c in text if c.isascii() and c.isalpha())
    non_space = sum(1 for c in text if not c.isspace())
    alpha = n_cjk + n_lat

    if not text.strip():
        label = "empty"
    elif alpha == 0:
        label = "other"
    else:
        ratio = n_cjk / alpha
        if ratio >= 0.8:
            label = "chinese"
        elif ratio <= 0.2:
            label = "english"
        else:
            label = "mixed"
    return {
        "label": label,
        "n_cjk": n_cjk,
        "n_latin": n_lat,
        "n_alpha": alpha,
        "n_non_space": non_space,
        "length": len(text),
    }


def pctile(sorted_vals: list, p: float) -> int:
    if not sorted_vals:
        return 0
    idx = min(len(sorted_vals) - 1, max(0, math.ceil(p * len(sorted_vals)) - 1))
    return sorted_vals[idx]


def summarize(rows: list, tokenizer=None) -> dict:
    labels = Counter(r["label"] for r in rows)
    n = len(rows)
    lengths = sorted(r["length"] for r in rows)
    cjk_shares = [r["n_cjk"] / r["n_non_space"] for r in rows if r["n_non_space"]]
    lat_shares = [r["n_latin"] / r["n_non_space"] for r in rows if r["n_non_space"]]

    out = {
        "n": n,
        "labels": {k: labels.get(k, 0) for k in ("chinese", "english", "mixed", "empty", "other")},
        "chinese_ratio": labels.get("chinese", 0) / n if n else 0.0,
        "chinese_or_mixed_ratio": (labels.get("chinese", 0) + labels.get("mixed", 0)) / n if n else 0.0,
        "char_level": {
            "mean_cjk_share": statistics.fmean(cjk_shares) if cjk_shares else 0.0,
            "mean_latin_share": statistics.fmean(lat_shares) if lat_shares else 0.0,
        },
        "length": {
            "mean": round(statistics.fmean(lengths), 1) if lengths else 0,
            "median": statistics.median(lengths) if lengths else 0,
            "p95": pctile(lengths, 0.95),
        },
        "mixed_examples": [
            r["text"][:100] for r in rows if r["label"] == "mixed"
        ][:3],
    }

    if tokenizer is not None:
        unk_ratios, heavy_unk, total_tok, total_unk = [], 0, 0, 0
        for r in rows:
            if not r["text"].strip():
                continue
            enc = tokenizer(r["text"], add_special_tokens=False, truncation=True, max_length=512)
            ids = enc["input_ids"]
            unk = ids.count(tokenizer.unk_token_id)
            total_tok += len(ids)
            total_unk += unk
            ratio = unk / len(ids) if ids else 0.0
            unk_ratios.append(ratio)
            if ratio >= 0.5:
                heavy_unk += 1
        unk_ratios.sort()
        out["bert_unk"] = {
            "aggregate_unk_share": round(total_unk / total_tok, 4) if total_tok else 0.0,
            "mean_sample_unk_ratio": round(statistics.fmean(unk_ratios), 4) if unk_ratios else 0.0,
            "median_sample_unk_ratio": round(statistics.median(unk_ratios), 4) if unk_ratios else 0.0,
            "p95_sample_unk_ratio": round(pctile(unk_ratios, 0.95), 4),
            "samples_with_unk_ratio_ge_0.5": heavy_unk,
            "n_tokenized": len(unk_ratios),
            "note": "plain task_text tokenized (no structured-prompt template words; template words are English and would only dilute the ratio)",
        }
    return out


def load_paper_splits():
    splits = {"paper_v1 train": [], "paper_v1 val": [], "paper_v1 test": []}
    platform_split = {}
    with open(PAPER_MANIFEST, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            text = row.get("task_text") or ""
            key = f"paper_v1 {row['split']}"
            if key not in splits:
                continue
            info = classify(text)
            info["text"] = text
            splits[key].append(info)
            pk = f"{key} [{row['platform']}]"
            platform_split.setdefault(pk, []).append(info)
    return splits, platform_split


def load_bench():
    out = {}
    for fname, key in (
        ("dev_20.tasks.jsonl", "benchmark dev"),
        ("final_100.tasks.jsonl", "benchmark final"),
        ("refusal_12.tasks.jsonl", "benchmark refusal"),
    ):
        rows = []
        with open(BENCH_DIR / fname, encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                info = classify(row.get("task_text") or "")
                info["text"] = row.get("task_text") or ""
                rows.append(info)
        out[key] = rows
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-bert", action="store_true", help="skip [UNK] stats (no transformers)")
    args = ap.parse_args()

    tokenizer = None
    if not args.skip_bert:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")

    paper_splits, platform_split = load_paper_splits()
    bench = load_bench()

    datasets = {}
    datasets.update(paper_splits)
    datasets.update(bench)
    for k, v in platform_split.items():
        datasets[k] = v

    inputs = {
        "paper_manifest": {
            "path": str(PAPER_MANIFEST.relative_to(REPO)),
            "sha256": sha256_of(PAPER_MANIFEST),
        },
        "benchmark_dev": {
            "path": "docs/reports/qgis_planner_eval_v1/materialized/dev_20.tasks.jsonl",
            "sha256": sha256_of(BENCH_DIR / "dev_20.tasks.jsonl"),
        },
        "benchmark_final": {
            "path": "docs/reports/qgis_planner_eval_v1/materialized/final_100.tasks.jsonl",
            "sha256": sha256_of(BENCH_DIR / "final_100.tasks.jsonl"),
        },
        "benchmark_refusal": {
            "path": "docs/reports/qgis_planner_eval_v1/materialized/refusal_12.tasks.jsonl",
            "sha256": sha256_of(BENCH_DIR / "refusal_12.tasks.jsonl"),
        },
    }

    result = {
        "schema": "gis_recommend.m1_phase0_precheck_a_language.v1",
        "classification_rule": (
            "label decided on alphabetic content: cjk_ratio=n_cjk/(n_cjk+n_latin); "
            "chinese >= 0.8, english <= 0.2, mixed in between; empty=blank text; other=no letters"
        ),
        "bert_tokenizer": "bert-base-uncased" if tokenizer else None,
        "inputs": inputs,
        "datasets": {k: summarize(v, tokenizer) for k, v in datasets.items()},
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "language_stats_v1.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(f"wrote {out_path}")
    for name, s in result["datasets"].items():
        lbl = s["labels"]
        unk = s.get("bert_unk", {})
        print(
            f"{name:28s} n={s['n']:5d} zh={lbl['chinese']:5d} en={lbl['english']:5d} "
            f"mix={lbl['mixed']:3d} other={lbl['empty'] + lbl['other']:3d} "
            f"unk_mean={unk.get('mean_sample_unk_ratio', '-')} "
            f"unk>=0.5={unk.get('samples_with_unk_ratio_ge_0.5', '-')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
