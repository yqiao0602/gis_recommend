#!/usr/bin/env python3
"""Gate 0 v2: composition-capability audit of the frozen B1 GEE corpus.

Read-only, stdlib-only, deterministic. Spec (frozen before the run):
docs/plans/gee_composition_audit_gate0_v2_spec.md
Corpus: /home/qy/system_redesign/outputs_v2/gee_b1_stage_data_v1/b1_gee_stage_train.jsonl
"""
import argparse
import hashlib
import json
import math
import time
from collections import Counter
from pathlib import Path

BANDS = [(1, 2), (3, 5), (6, 8), (9, 16), (17, 32), (33, 10 ** 9)]


def band_of(n):
    for lo, hi in BANDS:
        if lo <= n <= hi:
            return "%d-%d" % (lo, hi) if hi < 10 ** 9 else ">%d" % (lo - 1)
    return "?"


def chain_stats(chains):
    """chains: list of token lists."""
    n = len(chains)
    lengths = [len(c) for c in chains]
    lengths_sorted = sorted(lengths)

    def q(p):
        return lengths_sorted[min(int(p * n), n - 1)]

    exact = Counter(tuple(c) for c in chains)
    uniq = len(exact)
    counts_desc = sorted(exact.values(), reverse=True)
    top20_cov = sum(counts_desc[:20]) / n
    acc = 0
    n80 = 0
    for v in counts_desc:
        acc += v
        n80 += 1
        if acc >= 0.8 * n:
            break
    bigrams = Counter()
    trigrams = Counter()
    for c in chains:
        t = tuple(c)
        bigrams.update(zip(t, t[1:]))
        # errata 2026-09-20: was zip(t, t[2:]) (skip-2 pairs, mislabeled as
        # trigrams); true 3-grams now (all-corpus distinct: 126,840 vs 40,969)
        trigrams.update(zip(t, t[1:], t[2:]))
    bg_total = sum(bigrams.values())
    bg_desc = sorted(bigrams.values(), reverse=True)

    def spectrum(cnt):
        vals = sorted(cnt.values(), reverse=True)
        return {"ge1": len(vals), "ge2": sum(1 for v in vals if v >= 2),
                "ge10": sum(1 for v in vals if v >= 10),
                "ge100": sum(1 for v in vals if v >= 100)}

    uni = Counter()
    for c in chains:
        uni.update(c)
    n_tok = sum(uni.values())
    h_uni = -sum(v / n_tok * math.log2(v / n_tok) for v in uni.values())
    h_cond = 0.0
    for (a, b), v in bigrams.items():
        p_ab = v / bg_total
        h_cond -= p_ab * math.log2(v / uni[a])
    bag = Counter(tuple(sorted(c)) for c in chains)
    pre5 = Counter(tuple(c[:5]) for c in chains)

    runs_rows = 0
    run_max_hist = Counter()
    abab_rows = 0
    for c in chains:
        mx, cur = 1, 1
        has_run = False
        for i in range(1, len(c)):
            if c[i] == c[i - 1]:
                cur += 1
                has_run = True
            else:
                cur = 1
            mx = max(mx, cur)
        if has_run:
            runs_rows += 1
            run_max_hist[band_max(mx)] += 1
        if any(c[i] == c[i + 2] and c[i + 1] == c[i + 3] and c[i] != c[i + 1]
               for i in range(len(c) - 3)):
            abab_rows += 1

    return {
        "n_rows": n,
        "length": {"median": q(0.5), "mean": round(sum(lengths) / n, 2),
                   "p90": q(0.9), "p99": q(0.99), "max": lengths_sorted[-1],
                   "bands": dict(Counter(band_of(l) for l in lengths))},
        "exact_chains": {"unique": uniq, "singleton_rate": round(
            sum(1 for v in exact.values() if v == 1) / uniq, 4),
            "clusters_ge100": sum(1 for v in exact.values() if v >= 100),
            "top20_coverage": round(top20_cov, 4), "N80": n80},
        "bigrams": {"distinct": len(bigrams),
                    "top50_behavior_coverage": round(sum(bg_desc[:50]) / bg_total, 4),
                    "spectrum": spectrum(bigrams)},
        "trigrams": spectrum(trigrams),
        "entropy": {"vocab": len(uni), "H_unigram_bits": round(h_uni, 4),
                    "H_next_given_prev_bits": round(h_cond, 4),
                    "uniform_bits": round(math.log2(len(uni)), 4)},
        "near_dup": {"bag_identical_unique": len(bag),
                     "prefix5_unique": len(pre5),
                     "prefix5_top20_coverage": round(
                         sum(v for _, v in sorted(pre5.items(),
                                                  key=lambda kv: -kv[1])[:20]) / n, 4)},
        "repetition": {"rows_with_consecutive_run": runs_rows,
                       "rows_with_consecutive_run_rate": round(runs_rows / n, 4),
                       "row_max_run_bands": dict(run_max_hist),
                       "ABAB_rows": abab_rows,
                       "ABAB_rate": round(abab_rows / n, 4)},
    }


def band_max(mx):
    for lo, hi in [(2, 2), (3, 3), (4, 5), (6, 10), (11, 10 ** 9)]:
        if lo <= mx <= hi:
            return "%d-%s" % (lo, "+" if hi > 10 ** 8 else hi)
    return "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    t0 = time.time()
    h_sha = hashlib.sha256()
    surf = {"gee": [], "sem_raw": []}
    train_chains = {"gee": set(), "sem_raw": set()}
    split_rows = Counter()
    contam = {s: Counter() for s in ("val", "test")}
    eval_buffer = []
    cap_rows = cap_orig = cap_final = 0
    trivial = {"gee": 0, "sem_raw": 0}
    infer_proxy = {"gee": 0, "sem_raw": 0}
    uni_gee_tokens = Counter()
    task_types = Counter()

    with open(args.corpus, "rb") as f:
        for i, raw in enumerate(f):
            h_sha.update(raw)
            r = json.loads(raw.decode("utf-8"))
            gee = [t for t in (x.strip() for x in
                   r.get("gee_canonical_chain", "").split("->")) if t]
            sem = [t for t in (x.strip() for x in
                   r.get("semantic_chain_raw", "").split("->")) if t]
            cache = {}
            gee = [cache.setdefault(t, t) for t in gee]
            sem = [cache.setdefault(t, t) for t in sem]
            surf["gee"].append(gee)
            surf["sem_raw"].append(sem)
            uni_gee_tokens.update(gee)
            sp = r.get("split", "?")
            split_rows[sp] += 1
            key_sem, key_gee = tuple(sem), tuple(gee)
            if sp == "train":
                train_chains["sem_raw"].add(key_sem)
                train_chains["gee"].add(key_gee)
            elif sp in contam:
                # errata 2026-09-20: the file is row-shuffled (splits interleave
                # from row 0), so membership must be tested AFTER the complete
                # train set is built; the original single-pass version
                # undercounted cross-split contamination (test gee 11.75% ->
                # true 13.59%, test sem 23.1% -> true 27.37%).
                contam[sp]["sem_rows"] += 1
                contam[sp]["gee_rows"] += 1
                eval_buffer.append((sp, key_sem, key_gee))
            if r.get("run_cap_applied"):
                cap_rows += 1
                cap_orig += int(r.get("original_semantic_length", 0))
                cap_final += int(r.get("final_semantic_length", 0))
            for name, ch in (("gee", gee), ("sem_raw", sem)):
                if 0 < len(ch) <= 2:
                    trivial[name] += 1
                if len(ch) >= 4 and len(set(ch)) >= 2:
                    infer_proxy[name] += 1
            task_types[r.get("task_type", "?")] += 1
            if (i + 1) % 20000 == 0:
                print("[%d] %.1fs" % (i + 1, time.time() - t0), flush=True)

    n = i + 1
    # complete train sets now built -> membership is order-independent
    for sp, key_sem, key_gee in eval_buffer:
        contam[sp]["sem_hit"] += key_sem in train_chains["sem_raw"]
        contam[sp]["gee_hit"] += key_gee in train_chains["gee"]
    res = {
        "schema": "gis_recommend.transfer.gate0_v2", "n_rows": n,
        "sha256": h_sha.hexdigest(), "split_rows": dict(split_rows),
        "surfaces": {k: chain_stats(v) for k, v in surf.items()},
        "cap3_governance": {"rows_applied": cap_rows,
                            "orig_tokens_sem": cap_orig, "final_tokens_sem": cap_final,
                            "token_loss_pct": round(
                                100 * (cap_orig - cap_final) / max(cap_orig, 1), 2)},
        "trivial_rows_le2": trivial,
        "inference_proxy_len4_distinct2": infer_proxy,
        "gee_vocab": {"distinct_canonical_ops": len(uni_gee_tokens),
                      "top20": [[k, v] for k, v in
                                sorted(uni_gee_tokens.items(),
                                       key=lambda kv: -kv[1])[:20]]},
        "task_type_top15": [[k, v] for k, v in
                            sorted(task_types.items(), key=lambda kv: -kv[1])[:15]],
        "cross_split_exact_chain_contamination": {
            sp: {"sem_rate": round(contam[sp]["sem_hit"] / max(contam[sp]["sem_rows"], 1), 4),
                 "gee_rate": round(contam[sp]["gee_hit"] / max(contam[sp]["gee_rows"], 1), 4),
                 "rows": contam[sp]["sem_rows"]}
            for sp in ("val", "test")},
    }
    Path(args.out).write_text(json.dumps(res, indent=2, ensure_ascii=False),
                              encoding="utf-8")
    print("DONE %d rows in %.1fs -> %s" % (n, time.time() - t0, args.out))


if __name__ == "__main__":
    main()
