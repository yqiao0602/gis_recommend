#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B-track joint audit Q2+Q3 (+ label-flattening Q1.5) over the frozen GEE pool.

Owner ruling B_TRACK_Q2Q4_RULING_OWNER_V1.md:
  Q3: near/exact-duplicate instructions mapping to different workflows - ratio +
      multi-reference candidate list (human semantic verification follows).
  Q2: within near-duplicate instruction clusters, does structure change with the
      description? Mechanical rate + semantic review sample (structure change must
      be judged against the analytical logic the task change requires).
  Q1.5 (owner "identify which semantic differences the 30 labels flatten"):
      canonical-chain diversity inside one RLE template + AGGREGATION context
      flattening evidence.

READ-ONLY over 04_DIAG_WORK/b1_gee_stage_train.jsonl (128,447 rows). No training
data is modified; deterministic (seed 20261017).

Outputs (diag50_v1/b_track_audit_v1/):
  Q23_MECHANICAL_RESULTS_V1.json
  Q2_SEMANTIC_REVIEW_SAMPLE_V1.md
  Q3_MULTIREF_CANDIDATES_V1.md / .json
  LABEL_FLATTENING_AUDIT_V1.md
"""
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
POOL = REPO.parent / "04_DIAG_WORK/b1_gee_stage_train.jsonl"
OUT_DIR = (REPO / ("docs/reports/route2_p0_contract/plan_pipeline_v1/"
                   "planning_capability_audit_v1/diag50_v1/b_track_audit_v1"))
SEED = 20261017
JACCARD_MIN = 0.75
RARE_DF_CAP = 200          # tokens with df > this are not used as pair candidates
MIN_SHARED_RARE = 3        # candidate pairs must share >= this many rare tokens
Q2_SAMPLE_PER_STRATUM = 20
Q3_SAMPLE_GROUPS = 20

TOKEN_RE = re.compile(r"[a-z0-9]+")


def norm_text(s):
    return re.sub(r"\s+", " ", s.strip().lower())


def tokens(s):
    return set(TOKEN_RE.findall(s))


class UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def main():
    import random
    rng = random.Random(SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ---------- pass 1: load + Q3 exact-duplicate groups ----------
    rows = []           # (norm_instr, rle, canon, task_type, run_cap)
    print("loading pool ...", flush=True)
    with POOL.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            rows.append((norm_text(r.get("instruction", "")),
                         re.sub(r"\s+", " ", r.get("semantic_chain_rle", "").strip()),
                         r.get("gee_canonical_chain") or "",
                         r.get("task_type") or "",
                         bool(r.get("run_cap_applied"))))
    n_rows = len(rows)
    print(f"rows: {n_rows}", flush=True)

    instr_groups = defaultdict(list)   # norm_instr -> [row idx]
    for i, (ni, *_rest) in enumerate(rows):
        instr_groups[ni].append(i)
    n_unique_instr = len(instr_groups)

    multi_groups = {}                  # norm_instr -> {rle: count}
    for ni, idxs in instr_groups.items():
        tcnt = Counter(rows[i][1] for i in idxs)
        if len(tcnt) > 1:
            multi_groups[ni] = tcnt
    multi_rows = sum(sum(tcnt.values()) for tcnt in multi_groups.values())
    q3 = {
        "n_rows": n_rows,
        "n_unique_instructions": n_unique_instr,
        "n_exact_duplicate_groups": sum(1 for v in instr_groups.values() if len(v) > 1),
        "n_multi_template_groups": len(multi_groups),
        "multi_template_group_ratio": round(len(multi_groups) / n_unique_instr, 6),
        "rows_in_multi_template_groups": multi_rows,
        "row_weighted_multi_template_ratio": round(multi_rows / n_rows, 6),
        "template_multiplicity_dist": Counter(
            len(t) for t in multi_groups.values()),
    }

    # ---------- Q2: near-duplicate pairs (rare-token inverted index) ----------
    # ids for unique instructions to keep pair bookkeeping small
    ids = {ni: k for k, ni in enumerate(instr_groups)}
    NID = len(ids)
    df = Counter()
    tok_sets = {}
    for ni in instr_groups:
        ts = tokens(ni)
        tok_sets[ni] = ts
        df.update(ts)
    tok_sets_by_id = {ids[ni]: ts for ni, ts in tok_sets.items()}
    RARE_DF_CAP = 60
    rare = {t for t, c in df.items() if c <= RARE_DF_CAP}
    inv = defaultdict(list)
    for ni, ts in tok_sets.items():
        for t in ts & rare:
            inv[t].append(ids[ni])
    print(f"unique instrs: {NID} | rare tokens: {len(rare)}", flush=True)

    pairs = []            # (jaccard, id_a, id_b), deduped
    seen = set()          # packed (a*NID+b) for pairs that passed the >=3 filter
    incidence = 0
    for t, doc_ids in inv.items():
        doc_ids.sort()
        for a_i in range(len(doc_ids)):
            a = doc_ids[a_i]
            ta = None
            for b_i in range(a_i + 1, len(doc_ids)):
                b = doc_ids[b_i]
                incidence += 1
                packed = a * NID + b
                if packed in seen:
                    continue
                sa, sb = tok_sets_by_id[a], tok_sets_by_id[b]
                inter = sa & sb
                if len(inter) < MIN_SHARED_RARE:
                    continue
                seen.add(packed)
                j = len(inter) / len(sa | sb)
                if j >= JACCARD_MIN:
                    pairs.append((j, a, b))
    print(f"rare-token incidences: {incidence} | "
          f"near-dup pairs (j>={JACCARD_MIN}): {len(pairs)}", flush=True)

    uf = UF()
    for _j, a, b in pairs:
        uf.union(a, b)
    id2ni = {v: k for k, v in ids.items()}
    clusters = defaultdict(list)
    for _j, a, b in pairs:
        clusters[uf.find(a)].append(a)
        clusters[uf.find(b)].append(b)
    clusters = {r: sorted(set(ms)) for r, ms in clusters.items()}

    def tmpl_set(nid):
        return {rows[i][1] for i in instr_groups[id2ni[nid]]}

    band_stat = defaultdict(lambda: [0, 0])   # band -> [n_pairs, n_struct_diff]
    for j, a, b in pairs:
        band = "0.75-0.85" if j < 0.85 else ("0.85-0.95" if j < 0.95 else ">=0.95")
        band_stat[band][0] += 1
        band_stat[band][1] += (tmpl_set(a) != tmpl_set(b))

    cluster_sizes = Counter(len(set(ms)) for ms in clusters.values())
    n_multi_t_clusters = 0
    for ms in clusters.values():
        tset = set()
        for nid in set(ms):
            tset |= tmpl_set(nid)
        if len(tset) > 1:
            n_multi_t_clusters += 1
    q2 = {
        "jaccard_threshold": JACCARD_MIN,
        "rare_df_cap": RARE_DF_CAP,
        "min_shared_rare_tokens": MIN_SHARED_RARE,
        "n_near_dup_pairs": len(pairs),
        "n_near_dup_clusters": len(clusters),
        "cluster_size_dist": cluster_sizes,
        "n_multi_template_clusters": n_multi_t_clusters,
        "multi_template_cluster_ratio": round(
            n_multi_t_clusters / max(1, len(clusters)), 6),
        "pair_struct_diff_rate_by_jaccard_band": {
            b: {"n_pairs": v[0], "n_struct_diff": v[1],
                "rate": round(v[1] / v[0], 6) if v[0] else None}
            for b, v in sorted(band_stat.items())},
    }

    # ---------- Q1.5 label-flattening: canonical diversity per template ----------
    tmpl = defaultdict(lambda: [0, set()])
    for ni, rle, canon, *_ in rows:
        h = hashlib.sha256(re.sub(r"\s+", " ", canon.strip()).encode()).hexdigest()[:16]
        tmpl[rle][0] += 1
        tmpl[rle][1].add(h)
    canon_div = sorted(((len(s), c, r) for r, (c, s) in
                        ((k, v) for k, v in tmpl.items())),
                       key=lambda x: (-x[1], -x[0]))
    # AGGREGATION context flattening
    ctx_flags = {
        "reduceRegion": re.compile(r"reduceRegion"),
        "reduceColumns": re.compile(r"reduceColumns|reduceToImage"),
        "reduce_region_or_image": re.compile(r"reduce\b"),
        "combine_reducers": re.compile(r"combine\s*\(|combine2"),
        "map_iterate": re.compile(r"\.map\(|\.iterate\("),
        "temporal_composite": re.compile(r"median|mean\(|mosaic|composite"),
    }
    agg_rows = [r for r in rows if "AGGREGATION" in r[1].split(" -> ")]
    ctx_counter = Counter()
    agg_tmpl_ctx = defaultdict(set)
    for ni, rle, canon, *_ in agg_rows:
        flags = frozenset(name for name, rx in ctx_flags.items() if rx.search(canon))
        for name in flags:
            ctx_counter[name] += 1
        agg_tmpl_ctx[rle].add(flags)
    mixed_ctx_tmpls = sum(1 for s in agg_tmpl_ctx.values() if len(s) > 1)
    q15 = {
        "n_templates": len(tmpl),
        "mean_distinct_canonical_per_template": round(
            sum(len(s) for _c, s in tmpl.values()) / max(1, len(tmpl)), 3),
        "templates_with_multiple_canonical_forms": sum(
            1 for _c, s in tmpl.values() if len(s) > 1),
        "top_templates_by_canonical_diversity": [
            {"rle": r, "n_rows": c, "n_distinct_canonical": d}
            for d, c, r in canon_div[:15]],
        "aggregation_rows": len(agg_rows),
        "aggregation_context_flag_rows": dict(ctx_counter),
        "aggregation_templates_with_mixed_context": mixed_ctx_tmpls,
        "aggregation_templates_total": len(agg_tmpl_ctx),
    }

    # ---------- samples ----------
    # Q3 sample: multi-template exact groups
    grp_items = sorted(multi_groups.items(), key=lambda kv: -sum(kv[1].values()))
    q3_sample = rng.sample(grp_items, min(Q3_SAMPLE_GROUPS, len(grp_items)))
    q3_sample_rows = []
    for ni, tcnt in q3_sample:
        i0 = instr_groups[ni][0]
        q3_sample_rows.append({
            "instruction": rows[i0][0], "task_type": rows[i0][3],
            "n_rows": sum(tcnt.values()),
            "templates": [{"rle": t, "n": c} for t, c in tcnt.most_common()]})

    # Q2 sample: same-template pairs + diff-template pairs (ids -> instructions)
    same_t, diff_t = [], []
    for j, a, b in pairs:
        (same_t if tmpl_set(a) == tmpl_set(b) else diff_t).append((j, a, b))
    rng.shuffle(same_t)
    rng.shuffle(diff_t)
    def pair_row(j, a, b):
        ra, rb = rows[instr_groups[id2ni[a]][0]], rows[instr_groups[id2ni[b]][0]]
        return {"jaccard": round(j, 4),
                "instruction_a": ra[0], "rle_a": ra[1],
                "instruction_b": rb[0], "rle_b": rb[1]}
    q2_sample = {"same_template_pairs": [pair_row(*p) for p in same_t[:Q2_SAMPLE_PER_STRATUM]],
                 "diff_template_pairs": [pair_row(*p) for p in diff_t[:Q2_SAMPLE_PER_STRATUM]]}

    # ---------- write outputs ----------
    results = {"seed": SEED, "q3_exact_duplicates": q3, "q2_near_duplicates": q2,
               "q15_label_flattening": q15,
               "q3_sample_groups": q3_sample_rows,
               "q2_sample_pairs": q2_sample}
    (OUT_DIR / "Q23_MECHANICAL_RESULTS_V1.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1, default=dict),
        encoding="utf-8")

    # markdown: Q2 semantic review sample
    def pair_md(p, idx, kind):
        lines = [f"### {kind}-{idx}  (J={p['jaccard']})",
                 f"- **Instruction A**: {p['instruction_a']}",
                 f"- **Chain A**: `{p['rle_a']}`",
                 f"- **Instruction B**: {p['instruction_b']}",
                 f"- **Chain B**: `{p['rle_b']}`", ""]
        return "\n".join(lines)
    md = ["# Q2 语义抽验样本 V1（owner 裁定：结构变化是否符合任务变化要求的分析逻辑）", "",
          f"seed {SEED}；同模板对与异模板对各 {Q2_SAMPLE_PER_STRATUM}；"
          "判读任务：对每个对回答 —— 两指令的分析逻辑差异是否要求工作流结构差异？", ""]
    md.append("## A 组：近重复指令、结构相同（数据说'描述变了结构不变'）\n")
    for k, p in enumerate(q2_sample["same_template_pairs"], 1):
        md.append(pair_md(p, k, "SAME"))
    md.append("## B 组：近重复指令、结构不同（数据说'描述变了结构也变'）\n")
    for k, p in enumerate(q2_sample["diff_template_pairs"], 1):
        md.append(pair_md(p, k, "DIFF"))
    (OUT_DIR / "Q2_SEMANTIC_REVIEW_SAMPLE_V1.md").write_text(
        "\n".join(md), encoding="utf-8")

    # markdown: Q3 multi-reference candidates
    md = ["# Q3 多参考候选清单 V1（精确同指令 → 异模板；语义等价性待人工抽验）", "",
          f"seed {SEED}；按组内行数降序抽 {len(q3_sample_rows)} 组。", ""]
    for k, g in enumerate(q3_sample_rows, 1):
        md.append(f"## G-{k}  (n_rows={g['n_rows']}, task_type={g['task_type']})")
        md.append(f"- **Instruction**: {g['instruction']}")
        for t in g["templates"]:
            md.append(f"  - `{t['rle']}`  x{t['n']}")
        md.append("")
    (OUT_DIR / "Q3_MULTIREF_CANDIDATES_V1.md").write_text("\n".join(md), encoding="utf-8")

    # markdown: label flattening
    md = ["# 标签抹平审计 V1（owner：先识别被 30 标签抹平的语义差异）", "",
          f"- 模板总数：{q15['n_templates']}；模板内 canonical 链平均形数："
          f"{q15['mean_distinct_canonical_per_template']}",
          f"- 有 >1 种 canonical 形态的模板：{q15['templates_with_multiple_canonical_forms']}", "",
          "## canonical 多样性 Top-15 模板", "",
          "| RLE 模板 | 行数 | 不同 canonical 形态数 |", "|---|---|---|"]
    for t in q15["top_templates_by_canonical_diversity"]:
        md.append(f"| `{t['rle']}` | {t['n_rows']} | {t['n_distinct_canonical']} |")
    md += ["", "## AGGREGATION 语境抹平证据", "",
           f"- 含 AGGREGATION 的行：{q15['aggregation_rows']}；"
           f"涉及模板：{q15['aggregation_templates_total']}",
           f"- 同一模板内出现 >1 种聚合语境的模板数：{mixed_ctx_tmpls}",
           "- 语境旗标行数分布：" + json.dumps(q15["aggregation_context_flag_rows"], ensure_ascii=False)]
    (OUT_DIR / "LABEL_FLATTENING_AUDIT_V1.md").write_text("\n".join(md), encoding="utf-8")

    print(json.dumps({"q3": {k: v for k, v in q3.items() if k != "template_multiplicity_dist"},
                      "q2": {k: v for k, v in q2.items() if "dist" not in k},
                      "q15_summary": {k: v for k, v in q15.items()
                                      if not isinstance(v, list)}},
                     ensure_ascii=False, indent=1, default=dict))


if __name__ == "__main__":
    main()
