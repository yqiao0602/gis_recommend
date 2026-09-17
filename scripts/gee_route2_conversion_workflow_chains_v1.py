#!/usr/bin/env python3
"""Route-2 conversion, chain source v2: Workflowoutput (pool B) chains.

Replaces the GEE-OPs 15_ table (pool A) after the 2026-09-17 pool-confusion
audit proved same-id scripts differ between pools (~61% of sampled ids):
descriptions come from dataNNNNN (pool B), so chains must too.

  chain source   /data/yll/工作流抽取结果/Workflowoutput*/merged_nodes_process.csv
                 (per-script rows in step order; token from raw_api_name)
  descriptions   /home/yll/GEE/描述性知识抽取汇总/facts_summary*.csv (pool B)
  author proxy   merged_nodes_datasource.csv users|projects/{author}/ asset refs

Gates identical to v1: cleaning -> canonical folding -> instruction rewrite
-> union-find split (author + chain, hub components by author subgroup).
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

csv.field_size_limit(sys.maxsize)

WO_GLOB = "/data/yll/工作流抽取结果/Workflowoutput*/merged_nodes_process.csv"
DS_GLOB = "/data/yll/工作流抽取结果/Workflowoutput*/merged_nodes_datasource.csv"
DESC_GLOB = "/home/yll/GEE/描述性知识抽取汇总/facts_summary*.csv"
API_TABLE = "/data/yll/GeoWorkflow-Knowledge-Dataset/01原始代码/GEE/GEE_OPs/06_Operator_Syntax_Knowledge_Table.csv"

NOISE_TOKEN = {"print", "Map.setCenter", "Map.centerObject"}
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
    "displays": "display", "demonstrates": "demonstrate",
    "builds": "build", "defines": "define", "shows": "show", "outputs": "output",
}
CANONICAL_SUPPLEMENT = {
    "ee.ImageCollection.filterMetadata", "ee.FeatureCollection.filterMetadata",
    "ee.Image.filterMetadata", "ee.Filter.metadata", "ee.Classifier.gmoMaxent",
}
API_ALIAS = {
    "randomForest": "ee.Classifier.smileRandomForest", "cart": "ee.Classifier.smileCart",
    "svm": "ee.Classifier.libsvm", "naiveBayes": "ee.Classifier.smileNaiveBayes",
    "gmoMaxEnt": "ee.Classifier.gmoMaxent", "focal_median": "ee.Image.focalMedian",
    "focal_mean": "ee.Image.focalMean", "focal_max": "ee.Image.focalMax",
    "focal_min": "ee.Image.focalMin", "focal_mode": "ee.Image.focalMode",
}
EE_CLASSES = {
    "Classifier", "Reducer", "Join", "Algorithms", "Filter", "Image",
    "ImageCollection", "FeatureCollection", "Geometry", "Number", "List",
    "Date", "DateRange", "Feature", "Table",
}
EE_PREFIX_RE = re.compile(r"^(ee\.|Export\.)")


# ── loading ────────────────────────────────────────────────────────────────

def load_descriptions():
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
    return desc, tname, ttype


def _step_token(raw: str, norm: str) -> str | None:
    """Canonical token for one step, preserving true method names."""
    raw = (raw or "").strip()
    norm = (norm or "").strip()
    if raw and EE_PREFIX_RE.match(raw):
        parts = [p for p in raw.split(".") if p]
        if len(parts) == 1:
            return raw
        cls, last = parts[1], parts[-1]
        if last in API_ALIAS:
            return API_ALIAS[last]
        if len(parts) == 2:                      # ee.ImageCollection
            return raw
        return f"{parts[0]}.{cls}.{last}"        # ee.ImageCollection.filterBounds
    if norm and EE_PREFIX_RE.match(norm):
        return norm                              # receiver-prefixed -> canonical
    if raw and "." in raw:
        return raw.split(".")[-1]                # boundary.filter -> filter
    return raw or None


def build_chains():
    """Per-script ordered token chains from merged process tables (pool B)."""
    chains = {}
    for mp in sorted(glob.glob(WO_GLOB)):
        with open(mp, encoding="utf-8-sig") as fh:
            rdr = csv.DictReader(fh)
            idkey = next((k for k in (rdr.fieldnames or []) if k.strip() == "id"), None)
            if idkey is None:
                continue
            cur_script, cur_tokens = None, []
            def flush():
                if cur_script is not None and len(cur_tokens) >= 2:
                    chains[cur_script] = cur_tokens
            for row in rdr:
                s = (row.get("source_script") or "").replace(".txt", "")
                if s != cur_script:
                    flush()
                    cur_script, cur_tokens = s, []
                tok = _step_token(row.get("raw_api_name", ""), row.get("normalized_api_name", ""))
                if not tok or tok in NOISE_TOKEN or tok.startswith(("Map.", "ui.")):
                    continue
                if tok == "main":
                    continue
                if not cur_tokens or cur_tokens[-1] != tok:
                    cur_tokens.append(tok)
            flush()
    return chains


def load_author_proxies():
    """script -> author from users|projects/{author}/ asset references."""
    pat = re.compile(r"^(?:users|projects)/([A-Za-z0-9_.-]+)/")
    authors = defaultdict(set)
    for dp in sorted(glob.glob(DS_GLOB)):
        with open(dp, encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                m = pat.match((row.get("name") or "").strip())
                if m:
                    a = m.group(1)
                    if a not in ("google", "earthengine", "GEE", "sample", "assets"):
                        authors[(row.get("source_script") or "").replace(".txt", "")].add(a)
    return {k: sorted(v)[0] for k, v in authors.items() if v}


def load_canonical():
    canon, rows = set(), []
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
    by_method = defaultdict(set)
    for full in canon:
        parts = full.split(".")
        if len(parts) >= 2:
            by_method[parts[-1]].add(full)
    return canon, by_method


# ── folding (subset of v1 logic; tokens are mostly canonical already) ──────

def _clean(tok: str) -> str:
    return tok.strip(" }{]);[\t ")


def fold_chain(tokens, canon, by_method):
    folded, n_tok, n_map, n_amb, n_unmap = [], 0, 0, 0, 0
    for t in tokens:
        t = _clean(t)
        if not t:
            continue
        if t in canon:
            out = [t]
        elif t in API_ALIAS and API_ALIAS[t] in canon:
            out = [API_ALIAS[t]]
        else:
            parts = [p for p in t.split(".") if p]
            if not parts or parts == ["ee"]:
                continue
            if parts[0] in EE_CLASSES and f"ee.{'.'.join(parts)}" in canon:
                parts = ["ee"] + parts
            if ".".join(parts) in canon:
                out = [".".join(parts)]
            elif parts[0] in ("ee", "Export") and len(parts) >= 3 and parts[2] in API_ALIAS:
                out = [API_ALIAS[parts[2]]] + parts[3:]
            else:
                out = []
                i = 0
                if parts[0] in ("ee", "Export"):
                    for end in range(min(len(parts), 6), 1, -1):
                        if ".".join(parts[:end]) in canon:
                            out.append(".".join(parts[:end]))
                            i = end
                            break
                    else:
                        if len(parts) >= 2:
                            out.append(f"{parts[0]}.{parts[1]}")
                            i = 2
                for tok in parts[i:]:
                    if tok in API_ALIAS and API_ALIAS[tok] in canon:
                        out.append(API_ALIAS[tok])
                        continue
                    owners = by_method.get(tok)
                    if owners is None:
                        out.append(f"UNMAPPED:{tok}")
                    elif len(owners) == 1:
                        out.append(next(iter(owners)))
                    else:
                        out.append(tok)
        for x in out:
            n_tok += 1
            if x.startswith("UNMAPPED:"):
                n_unmap += 1
            else:
                n_map += 1
                if "." not in x:
                    n_amb += 1
        folded.extend(out)
    return folded, n_tok, n_map, n_amb, n_unmap


def core_families(tokens):
    fams = set()
    for t in tokens:
        for fam, pat in FAM.items():
            if pat.search(t):
                fams.add(fam)
    return fams


def rewrite_instruction(name, desc):
    lead = re.match(r"^(The (script|code|workflow|analysis)\s+(?:then\s+)?)(\w+)", desc, re.I)
    body = desc
    if lead:
        base = VERB_MAP.get(lead.group(3).lower())
        if base:
            body = base.capitalize() + desc[lead.end():]
    body = re.sub(r"\bthe script\b", "the workflow", body, flags=re.I)
    return f"Task: {name}\n{body}" if name else body


# ── split ──────────────────────────────────────────────────────────────────

def assign_splits(rows, rng, hub_max=200):
    parent: dict[str, str] = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for r in rows:
        rn = f"R:{r['script']}"
        parent[rn] = rn
        union(rn, f"C:{r['ee_chain_folded']}")
        if r["author_proxy"]:
            union(rn, f"A:{r['author_proxy']}")

    comp_members = defaultdict(list)
    for r in rows:
        comp_members[find(f"R:{r['script']}")].append(r)
    comps = sorted(comp_members, key=lambda c: (len(comp_members[c]), c))
    rng.shuffle(comps)

    def _fallback(r):
        h = hash(r["script"]) % 10
        return "train" if h < 8 else "val" if h == 8 else "test"

    n_small = sum(1 for c in comps if len(comp_members[c]) <= hub_max)
    t_cut, v_cut = int(n_small * 0.8), int(n_small * 0.9)
    split_of = {}
    for i, c in enumerate(comps):
        members = comp_members[c]
        if len(members) <= hub_max:
            split_of[c] = "train" if i < t_cut else "val" if i < v_cut else "test"
        else:
            chain_author = defaultdict(set)
            for r in members:
                if r["author_proxy"]:
                    chain_author[r["ee_chain_folded"]].add(r["author_proxy"])
            sub = defaultdict(list)
            for r in members:
                if r["author_proxy"]:
                    sub[r["author_proxy"]].append(r)
                else:
                    owners = chain_author.get(r["ee_chain_folded"])
                    key = (next(iter(owners)) if owners and len(owners) == 1
                           else f"chain:{r['ee_chain_folded']}")
                    sub[key].append(r)
            keys = sorted(sub)
            rng.shuffle(keys)
            stc, svc = int(len(keys) * 0.8), int(len(keys) * 0.9)
            for j, k in enumerate(keys):
                sp = "train" if j < stc else "val" if j < svc else "test"
                for r in sub[k]:
                    r["split"] = sp
    for r in rows:
        if "split" not in r:
            root = find(f"R:{r['script']}")
            r["split"] = split_of.get(root) or split_of.get(find(f"C:{r['ee_chain_folded']}")) or _fallback(r)
    return len(comps)


# ── main ───────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--sample", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=20260917)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    args.out.mkdir(parents=True, exist_ok=True)

    desc, tname, ttype = load_descriptions()
    print(f"descriptions: {len(desc)}")
    chains = build_chains()
    print(f"chains built (pool B, Workflowoutput): {len(chains)}")
    authors = load_author_proxies()
    print(f"author proxies: {len(authors)}")
    canon, by_method = load_canonical()
    print(f"canonical APIs: {len(canon)}")

    # reasoning tier on pool-B chains
    tier = {}
    for s in sorted(set(chains) & set(desc)):
        toks = [t for t in chains[s] if EE_PREFIX_RE.match(t) or t in API_ALIAS]
        if len(toks) < 2:
            continue
        if len(core_families(toks)) >= 2:
            tier[s] = toks
    print(f"reasoning tier: {len(tier)}")

    def bucket(n):
        return "2-4" if n <= 4 else "5-8" if n <= 8 else "9-16" if n <= 16 else ">16"
    strata = defaultdict(list)
    for s, toks in tier.items():
        strata[(bucket(len(toks)), min(len(core_families(toks)), 4))].append(s)
    sample = []
    for k in sorted(strata):
        take = round(args.sample * len(strata[k]) / len(tier))
        sample.extend(rng.sample(strata[k], min(take, len(strata[k]))))
    rng.shuffle(sample)
    sample = sample[:args.sample]
    print(f"stratified sample: {len(sample)} across {len(strata)} strata")

    rows, funnel = [], Counter()
    unmapped_ops = Counter()
    for s in sample:
        toks = tier[s]
        funnel["g0_sampled"] += 1
        folded, n_tok, n_map, n_amb, n_unmap = fold_chain(toks, canon, by_method)
        for x in folded:
            if x.startswith("UNMAPPED:"):
                unmapped_ops[x.split(":", 1)[1]] += 1
        if n_tok == 0 or n_map / n_tok < 0.8:
            funnel["g2_drop_canonical_lt80"] += 1
            continue
        funnel["g2_pass"] += 1
        instr = rewrite_instruction(tname[s], desc[s])
        if len(instr) < 40:
            funnel["g3_drop_instruction"] += 1
            continue
        funnel["g3_pass"] += 1
        rows.append({
            "script": s, "task_type": ttype[s], "task_name": tname[s],
            "instruction": instr,
            "ee_chain_raw": " -> ".join(toks),
            "ee_chain_folded": " -> ".join(folded),
            "n_tokens": n_tok, "n_mapped": n_map,
            "n_ambiguous": n_amb, "n_unmapped": n_unmap,
            "author_proxy": authors.get(s, ""),
        })

    n_comps = assign_splits(rows, rng)
    funnel["g4_components"] = n_comps
    funnel["g4_author_proxy_rows"] = sum(1 for r in rows if r["author_proxy"])

    out_rows = args.out / "pilot_rows.jsonl"
    with open(out_rows, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    lens = [r["n_tokens"] for r in rows]
    ratios = [r["n_mapped"] / max(r["n_tokens"], 1) for r in rows]
    stats = {
        "funnel": dict(funnel),
        "final_rows": len(rows),
        "author_proxy_coverage": f"{sum(1 for r in rows if r['author_proxy'])}/{len(rows)}",
        "canonical_token_coverage": {
            "mean": round(statistics.mean(ratios), 4) if ratios else 0,
            "p10": round(sorted(ratios)[max(0, int(len(ratios) * 0.1) - 1)], 4) if ratios else 0,
        },
        "chain_len": {"median": statistics.median(lens) if lens else 0,
                      "p90": sorted(lens)[int(len(lens) * 0.9)] if lens else 0},
        "split_counts": dict(Counter(r["split"] for r in rows)),
        "top_unmapped_ops": unmapped_ops.most_common(20),
        "task_type_top10": Counter(r["task_type"] for r in rows).most_common(10),
    }
    (args.out / "pilot_stats.json").write_text(
        json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print(f"\nwrote {out_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
