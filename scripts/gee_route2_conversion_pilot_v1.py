#!/usr/bin/env python3
"""Route-2 conversion pilot v1: 3,000-row feasibility gate (owner-approved 2026-09-17).

Turns a stratified sample of the GEE reasoning tier (>=2 core operator
families, 44,231 scripts) into candidate training pairs through a four-gate
funnel, and measures where rows die:

  Gate 1  chain cleaning       noise-filtered semantic ee-chain, len >= 2
  Gate 2  canonical folding   method tokens -> 1,079 canonical GEE APIs
                              (1:1 / ambiguous / UNMAPPED recorded, never forced)
  Gate 3  instruction rewrite Task Name + light imperative rewrite of the
                              third-person description
  Gate 4  source-disjoint     repository-level group split via
                              collected_scripts/index.json + data400000 mapping

Run on the compute server (read-only on /home/yll and /data/yll):
  python3 gee_route2_conversion_pilot_v1.py --out <dir> [--sample 3000]
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import random
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

CHAIN_CSV = "/data/yll/GeoWorkflow-Knowledge-Dataset/01原始代码/GEE/GEE_OPs/15_Operator_Relationship_Chain_Knowledge_Table.csv"
API_TABLE = "/data/yll/GeoWorkflow-Knowledge-Dataset/01原始代码/GEE/GEE_OPs/06_Operator_Syntax_Knowledge_Table.csv"
DESC_GLOB = "/home/yll/GEE/描述性知识抽取汇总/facts_summary*.csv"
SOURCE_INDEX = "/home/yll/GEE/爬取gee脚本/collected_scripts/index.json"
RENAME_400K = "/home/yll/GEE/Data/data400000_original_rename_mapping.csv"

SYS_PREFIX = ("ee.", "Map.", "ui.", "Export.")
NOISE_M = {"print", "addLayer", "setCenter", "centerObject", "setChartType", "setOptions", "main"}
EE = re.compile(r"^(ee\.|Export\.)")
FAM = {
    "filter": re.compile(r"filter(Date|Bounds|Metadata)?$", re.I),
    "map": re.compile(r"\.map$|\.iterate$"),
    "reduce": re.compile(r"reduce|mean|median|sum|min|max|composite", re.I),
    "select": re.compile(r"\.select$|band"),
    "classify": re.compile(r"classif|smileRandom|svm|CART", re.I),
    "math": re.compile(r"\.(add|subtract|multiply|divide|expression|normalizedDifference|rename|updateMask|gt|lt|gte|lte|and|or|eq|neq)", re.I),
    "mask": re.compile(r"mask", re.I),
    "join": re.compile(r"join|intersect|union|difference", re.I),
}
VERB_MAP = {
    "classifies": "classify", "identifies": "identify", "analyzes": "analyze",
    "computes": "compute", "calculates": "calculate", "generates": "generate",
    "creates": "create", "maps": "map", "uses": "use", "processes": "process",
    "detects": "detect", "monitors": "monitor", "estimates": "estimate",
    "extracts": "extract", "compares": "compare", "applies": "apply",
    "downloads": "download", "exports": "export", "visualizes": "visualize",
    "filters": "filter", "merges": "merge", "clips": "clip", "loads": "load",
    "combines": "combine", "converts": "convert", "produces": "produce",
    "displays": "display", "calculates": "calculate", "demonstrates": "demonstrate",
    "builds": "build", "defines": "define", "shows": "show", "outputs": "output",
}

# canonical-table supplement (2026-09-17 pilot finding): entries present in the
# GEE corpus but missing from 06_Operator_Syntax_Knowledge_Table. Kept in-script
# so /home/yll stays read-only and the supplement is version-controlled.
CANONICAL_SUPPLEMENT = {
    "ee.ImageCollection.filterMetadata",
    "ee.FeatureCollection.filterMetadata",
    "ee.Image.filterMetadata",
    "ee.Filter.metadata",
    "ee.Classifier.gmoMaxent",
}
# legacy JS API names -> current canonical names (verified against the 06 table)
API_ALIAS = {
    "randomForest": "ee.Classifier.smileRandomForest",
    "cart": "ee.Classifier.smileCart",
    "svm": "ee.Classifier.libsvm",
    "naiveBayes": "ee.Classifier.smileNaiveBayes",
    "gmoMaxEnt": "ee.Classifier.gmoMaxent",
    "focal_median": "ee.Image.focalMedian",
    "focal_mean": "ee.Image.focalMean",
    "focal_max": "ee.Image.focalMax",
    "focal_min": "ee.Image.focalMin",
    "focal_mode": "ee.Image.focalMode",
}
# class segments that appear in chains without the ee. prefix
EE_CLASSES = {
    "Classifier", "Reducer", "Join", "Algorithms", "Filter", "Image",
    "ImageCollection", "FeatureCollection", "Geometry", "Number", "List",
    "Date", "DateRange", "Feature", "Table", "TurbidWater" "Crosshair",
}

# ── load ───────────────────────────────────────────────────────────────────

def load_all():
    chains = {}
    with open(CHAIN_CSV, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            ops = [o.strip() for o in (r["Operator Chain"] or "").split("->") if o.strip()]
            chains[r["Script Name"]] = ops
    desc, tname, ttype = {}, {}, {}
    for f in sorted(glob.glob(DESC_GLOB)):
        if "row_counts" in f:
            continue
        with open(f, encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                k = r["File Name"].replace(".txt", "")
                desc[k] = (r.get("Task Description") or "").strip()
                tname[k] = (r.get("Task Name") or "").strip()
                ttype[k] = (r.get("Task Type") or "").strip()
    return chains, desc, tname, ttype


def load_canonical():
    canon = set()
    rows = []
    for enc in ("utf-8-sig", "gbk", "latin-1"):
        try:
            with open(API_TABLE, encoding=enc) as fh:
                rows = list(csv.DictReader(fh))
            break
        except UnicodeDecodeError:
            continue
    for r in rows:
        canon.add((r.get("full_name") or "").strip())
    canon |= CANONICAL_SUPPLEMENT
    # method -> set of canonical full names ending with .method
    by_method = defaultdict(set)
    for full in canon:
        parts = full.split(".")
        if len(parts) >= 2:
            by_method[parts[-1]].add(full)
    return canon, by_method


def load_sources():
    src = {}
    idx = json.load(open(SOURCE_INDEX, encoding="utf-8"))
    for k, v in idx.items():
        repo = (v or {}).get("repository") or ""
        if repo:
            src[k] = repo.split("/")[0] + "/" + repo.split("/")[-1] if "/" in repo else repo
    with open(RENAME_400K, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            orig = (r.get("original_filename") or "")
            stem = (r.get("new_stem") or "")
            if orig and stem and stem not in src:
                seg = orig.split("__")
                if len(seg) >= 2:
                    src[stem] = f"{seg[0]}/{seg[1]}"
    return src

# ── normalization (mirrors gee_workflow_diversity_audit_v1) ─────────────────

def norm_element(e):
    if e.startswith(SYS_PREFIX):
        if e.startswith(("Map.", "ui.")):
            return None
        return None if e.split(".")[1] in NOISE_M else e
    parts = e.split(".")
    if len(parts) > 1:
        return ".".join(parts[1:])
    return None if e in NOISE_M else e


def ee_chain(ops):
    return [x for x in (norm_element(o) for o in ops) if x and EE.match(x)]


def core_families(eeops):
    fams = set()
    for op in eeops:
        for fam, pat in FAM.items():
            if pat.search(op):
                fams.add(fam)
    return fams

# ── canonical folding ───────────────────────────────────────────────────────

def _clean_token(tok: str) -> str:
    return tok.strip(" }{]);[\t ")


def fold_element(elem, canon, by_method):
    """-> (status, folded). Greedy longest canonical prefix, then method folding.

    ee.Classifier.smileRandomForest.train:
      prefix ee.Classifier.smileRandomForest (canonical leaf) + method train.
    Junk tokens from `for () {` wrappers are stripped before matching.
    """
    parts = [_clean_token(p) for p in elem.split(".")]
    parts = [p for p in parts if p]
    if not parts or parts == ["ee"]:
        return "empty", []
    # bare legacy-alias method, e.g. focal_median in a stripped chain
    if len(parts) == 1 and parts[0] in API_ALIAS:
        return "alias", [API_ALIAS[parts[0]]]
    # alias normalization: chain segments often drop the ee. prefix
    # (Classifier.smileRandomForest.train -> ee.Classifier.smileRandomForest + train)
    if parts[0] in EE_CLASSES and f"ee.{'.'.join(parts)}" in canon:
        parts = ["ee"] + parts
    if ".".join(parts) in canon:
        return "exact", [".".join(parts)]
    # legacy alias, e.g. ee.Classifier.randomForest.train -> ee.Classifier.smileRandomForest + train
    if parts[0] in ("ee", "Export") and len(parts) >= 3 and parts[2] in API_ALIAS:
        aliased = API_ALIAS[parts[2]].split(".")
        return "alias", [".".join(aliased)] + list(parts[3:])
    out = []
    i = 0
    # greedy: consume the longest leading run of segments forming a canonical name
    if parts[0] in ("ee", "Export"):
        for end in range(min(len(parts), 6), 1, -1):
            cand = ".".join(parts[:end])
            if cand in canon:
                out.append(cand)
                i = end
                break
        else:
            # bare factory/class reference (ee.Classifier, ee.Reducer): keep the
            # 2-segment class token, fold remaining segments as methods
            if len(parts) >= 2:
                out.append(f"{parts[0]}.{parts[1]}")
                i = 2
    unmapped = False
    for tok in parts[i:]:
        if tok in API_ALIAS and API_ALIAS[tok] in canon:
            out.append(API_ALIAS[tok])
            continue
        owners = by_method.get(tok)
        if owners is None:
            unmapped = True
            out.append(f"UNMAPPED:{tok}")
        elif len(owners) == 1:
            out.append(next(iter(owners)))
        else:
            # method shared by several classes: fold to method-level name
            out.append(f"{tok}")
    status = "unmapped" if unmapped and not out else ("split" if out else "unmapped")
    return status, out


def fold_chain(eeops, canon, by_method):
    folded, n_tok, n_map, n_amb, n_unmap = [], 0, 0, 0, 0
    for e in eeops:
        _, f = fold_element(e, canon, by_method)
        for t in f:
            n_tok += 1
            if t.startswith("UNMAPPED:"):
                n_unmap += 1
            else:
                n_map += 1
                # ambiguity: folded to bare method (no class)
                if "." not in t:
                    n_amb += 1
        folded.extend(f)
    return folded, n_tok, n_map, n_amb, n_unmap

# ── instruction rewrite ────────────────────────────────────────────────────

def rewrite_instruction(name, desc):
    """Task Name (imperative) + third-person description lightly de-scripted."""
    lead = re.match(r"^(The (script|code|workflow|analysis)\s+(?:then\s+)?)(\w+)",
                    desc, re.I)
    body = desc
    if lead:
        verb = lead.group(3)
        base = VERB_MAP.get(verb.lower())
        if base:
            body = base.capitalize() + desc[lead.end():]
    body = re.sub(r"\bthe script\b", "the workflow", body, flags=re.I)
    return f"Task: {name}\n{body}" if name else body


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--sample", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=20260917)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    args.out.mkdir(parents=True, exist_ok=True)

    chains, desc, tname, ttype = load_all()
    canon, by_method = load_canonical()
    sources = load_sources()
    print(f"loaded: {len(chains)} chains | {len(desc)} descriptions | "
          f"{len(canon)} canonical APIs | {len(sources)} source repos")

    # ── reasoning tier ──
    tier = {}
    for s in set(chains) & set(desc):
        eeops = ee_chain(chains[s])
        if len(eeops) < 2:
            continue
        fams = core_families(eeops)
        if len(fams) >= 2:
            tier[s] = (eeops, fams)
    print(f"reasoning tier: {len(tier)}")

    # ── stratified sample: length bucket x core-family count ──
    # (tier is built from set intersection; sort for deterministic sampling
    #  across runs regardless of PYTHONHASHSEED)
    def bucket(n):
        return "2-4" if n <= 4 else "5-8" if n <= 8 else "9-16" if n <= 16 else ">16"
    strata = defaultdict(list)
    for s in sorted(tier):
        eeops, fams = tier[s]
        strata[(bucket(len(eeops)), min(len(fams), 4))].append(s)
    sample = []
    quota = args.sample
    for k in sorted(strata):
        take = round(quota * len(strata[k]) / len(tier))
        sample.extend(rng.sample(strata[k], min(take, len(strata[k]))))
    rng.shuffle(sample)
    sample = sample[:quota]
    print(f"stratified sample: {len(sample)} across {len(strata)} strata")

    # ── funnel ──
    rows, funnel = [], Counter()
    unmapped_ops, amb_ops = Counter(), Counter()
    for s in sample:
        eeops = tier[s][0]
        funnel["g0_sampled"] += 1
        if len(eeops) < 2:  # already guaranteed, kept as explicit gate
            funnel["g1_drop_structural"] += 1
            continue
        funnel["g1_pass"] += 1
        folded, n_tok, n_map, n_amb, n_unmap = fold_chain(eeops, canon, by_method)
        for t in folded:
            if t.startswith("UNMAPPED:"):
                unmapped_ops[t.split(":", 1)[1]] += 1
            elif "." not in t:
                amb_ops[t] += 1
        # gate 2: require >=80% tokens mapped to canonical (incl. method-level)
        if n_tok == 0 or n_map / n_tok < 0.8:
            funnel["g2_drop_canonical_lt80"] += 1
            continue
        funnel["g2_pass"] += 1
        instr = rewrite_instruction(tname[s], desc[s])
        if not instr or len(instr) < 40:
            funnel["g3_drop_instruction"] += 1
            continue
        funnel["g3_pass"] += 1
        rows.append({
            "script": s,
            "task_type": ttype[s],
            "task_name": tname[s],
            "instruction": instr,
            "ee_chain_raw": " -> ".join(eeops),
            "ee_chain_folded": " -> ".join(folded),
            "n_tokens": n_tok, "n_mapped": n_map,
            "n_ambiguous": n_amb, "n_unmapped": n_unmap,
            "repository": sources.get(s, ""),
        })
    # gate 4: source-disjoint group split among rows WITH source; report the rest
    with_src = [r for r in rows if r["repository"]]
    repos = defaultdict(list)
    for r in with_src:
        repos[r["repository"]].append(r)
    repo_list = sorted(repos)
    rng.shuffle(repo_list)
    n_r = len(repo_list)
    train_cut, val_cut = int(n_r * 0.8), int(n_r * 0.9)
    for i, repo in enumerate(repo_list):
        split = "train" if i < train_cut else "val" if i < val_cut else "test"
        for r in repos[repo]:
            r["split"] = split
    for r in rows:
        r.setdefault("split", "nosource")
    # gate 4b: rows without repo provenance are split at folded-chain family level
    # so exact template mirrors cannot straddle train/test
    nosrc = defaultdict(list)
    for r in rows:
        if r["split"] == "nosource":
            nosrc[r["ee_chain_folded"]].append(r)
    fam_list = sorted(nosrc)
    rng.shuffle(fam_list)
    n_f = len(fam_list)
    t_cut, v_cut = int(n_f * 0.8), int(n_f * 0.9)
    for i, fam in enumerate(fam_list):
        sp = "train_chainfamily" if i < t_cut else "val_chainfamily" if i < v_cut else "test_chainfamily"
        for r in nosrc[fam]:
            r["split"] = sp
    funnel["g4_with_source"] = len(with_src)
    funnel["g4_no_source_chainfamily_split"] = sum(len(v) for v in nosrc.values())

    # ── outputs ──
    out_rows = args.out / "pilot_3000_rows.jsonl"
    with open(out_rows, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    lens = [r["n_tokens"] for r in rows]
    mapped_ratio = [r["n_mapped"] / max(r["n_tokens"], 1) for r in rows]
    stats = {
        "funnel": dict(funnel),
        "final_rows": len(rows),
        "source_coverage": f"{len(with_src)}/{len(rows)}",
        "canonical_token_coverage": {
            "mean": round(statistics.mean(mapped_ratio), 4),
            "p10": round(sorted(mapped_ratio)[max(0, int(len(mapped_ratio)*0.1)-1)], 4),
        },
        "ee_chain_len": {"median": statistics.median(lens), "p90": sorted(lens)[int(len(lens)*0.9)]},
        "split_counts": dict(Counter(r["split"] for r in rows)),
        "top_unmapped_ops": unmapped_ops.most_common(30),
        "top_ambiguous_methods": amb_ops.most_common(15),
        "task_type_top10": Counter(r["task_type"] for r in rows).most_common(10),
        "sample_strata_sizes": {str(k): len(v) for k, v in sorted(strata.items())},
    }
    (args.out / "pilot_3000_stats.json").write_text(
        json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: stats[k] for k in ("funnel", "final_rows", "source_coverage",
                                            "canonical_token_coverage", "split_counts")},
                     indent=2, ensure_ascii=False))
    print(f"\nwrote {out_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
