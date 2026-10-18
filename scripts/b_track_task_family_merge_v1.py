#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Task-family merge pass V1 (2026-10-18, owner-approved P1).

Goal: find same-task families that the V2 component rule (rare-token J>=0.75 or
shared script id) missed, adjudicate each candidate with multi-axis evidence,
and build Split V3 at family level.

Design (frozen in B_TRACK_TASK_FAMILY_MERGE_SPEC_V1.md):
  - discovery signals are independent: title token-pair blocking, body rare-token
    Jaccard, shared literal assets, exact semantic-chain template, dataset
    family + target token.
  - similarity discovers candidates; it never decides.  A merge needs evidence
    on >=2 axes (text/intent + source/implementation/objective).
  - every candidate family gets a disposition record; cross-split edges are
    listed individually.
  - V2 is read-only and never overwritten.

Usage:
  python scripts/b_track_task_family_merge_v1.py --explore
  python scripts/b_track_task_family_merge_v1.py --build
"""
import argparse
import gzip
import hashlib
import itertools
import json
import pickle
import re
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
POOL = REPO.parent / "04_DIAG_WORK/b1_gee_stage_train.jsonl"
B = (REPO / "docs/reports/route2_p0_contract/plan_pipeline_v1/"
     "planning_capability_audit_v1/diag50_v1/b_track_audit_v1")
MAN = B / "B_TRACK_SPLIT_MANIFEST_V2.json"
TREE = [REPO / ".tmp_gee_batch13_sources/Data", REPO / ".tmp_gee_batch8_ast_bridge/sources"]
SEED = 20261018

STOP = set("""a an the and or of for to from by in on at with using use used via based into over
under between across within without this that these those its their is are was were be been being
as well also then than which where when what how all any both each few more most other some such no
nor not only own same so too very can will just should now we it its it's""".split())
GENERIC_TARGET = set("""data dataset datasets imagery image images satellite raster map maps analysis
result results change changes time year years date dates value values product products method methods
region regions study area areas pixel pixels band bands collection scale resolution level site sites
new different various multiple based using use workflow task""".split())
PURPOSE = {
    "identify": "detect", "detect": "detect", "map": "detect", "classify": "detect",
    "extract": "detect", "find": "detect", "locate": "detect", "delineate": "detect",
    "segment": "detect", "discriminate": "detect", "distinguish": "detect",
    "identification": "detect", "detection": "detect", "mapping": "detect",
    "classification": "detect", "extraction": "detect", "segmentation": "detect",
    "analyze": "analyze", "analyse": "analyze", "assess": "analyze", "evaluate": "analyze",
    "quantify": "analyze", "calculate": "analyze", "compute": "analyze", "estimate": "analyze",
    "measure": "analyze", "derive": "analyze", "monitor": "analyze", "track": "analyze",
    "model": "analyze", "predict": "analyze", "examine": "analyze", "investigate": "analyze",
    "analysis": "analyze", "assessment": "analyze", "estimation": "analyze",
    "monitoring": "analyze", "modeling": "analyze", "prediction": "analyze",
    "evaluation": "analyze", "quantification": "analyze", "calculation": "analyze",
    "generate": "generate", "create": "generate", "produce": "generate", "build": "generate",
    "develop": "generate", "construct": "generate", "prepare": "generate",
    "generation": "generate", "creation": "generate", "production": "generate",
    "compare": "compare", "contrast": "compare", "comparison": "compare",
    "visualize": "visualize", "plot": "visualize", "display": "visualize", "render": "visualize",
    "visualization": "visualize",
    "export": "export",
}
DATASET_PATTERNS = [
    ("landsat", r"\blandsat\b"),
    ("sentinel-1", r"\bsentinel[-\s]?1\b"),
    ("sentinel-2", r"\bsentinel[-\s]?2\b"),
    ("modis", r"\bmodis\b"),
    ("viirs", r"\bviirs\b"),
    ("naip", r"\bnaip\b"),
    ("srtm", r"\bsrtm\b"),
    ("chirps", r"\bchirps\b"),
    ("era5", r"\bera[-\s]?5\b"),
    ("worldpop", r"\bworldpop\b"),
    ("mapbiomas", r"\bmapbiomas\b"),
    ("hansen", r"\bhansen\b"),
    ("jrc", r"\bjrc\b"),
    ("gpm", r"\b(gpm|imerg)\b"),
    ("smap", r"\bsmap\b"),
    ("grace", r"\bgrace\b"),
    ("dynamic-world", r"\bdynamic\s*world\b"),
    ("gfw", r"\bglobal\s*forest\s*watch\b|\bgfw\b"),
]
ASSET_FAMILY_PREFIXES = [
    ("LANDSAT/", "landsat"), ("COPERNICUS/S1", "sentinel-1"),
    ("COPERNICUS/S2", "sentinel-2"), ("MODIS/", "modis"), ("NOAA/", "noaa"),
    ("NASA/", "nasa"), ("HYCOM/", "hycom"), ("UCSB-CHG/", "ucsb-chg"),
    ("JRC/", "jrc"), ("ESA/", "esa"), ("USGS/", "usgs"), ("IDAHO_EPSCOR/", "idaho-epscor"),
    ("OREGONSTATE/", "oregonstate"), ("users/", "custom"), ("projects/", "custom"),
]
TOK = re.compile(r"[a-z0-9]+")


def norm_text(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def words(s):
    return TOK.findall(s or "")


def stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if w.endswith(("is", "us", "ss")):
        return w
    if len(w) > 4 and w.endswith("es"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s"):
        return w[:-1]
    return w


def title_of(instr):
    first = (instr or "").split("\n", 1)[0]
    m = re.match(r"^\s*task\s*:\s*(.*)$", first, re.I)
    return norm_text(m.group(1) if m else first)


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


FAST_ASSET_RE = re.compile(
    r"ee\.(?:ImageCollection|Image|FeatureCollection)\(\s*['\"]([^'\"]+)['\"]")


def find_assets(src):
    """Fast literal-asset extraction for the corpus scan.

    Captures the leading string literal of the first argument; concatenated
    suffixes are not resolved (documented limitation).  The full first-arg
    scanner in b_track_risk_flags_v1 is used for the flag artifact.
    """
    return sorted(set(FAST_ASSET_RE.findall(src)))


def asset_family(a):
    for pre, fam in ASSET_FAMILY_PREFIXES:
        if a.startswith(pre):
            return fam
    return "other"


def dataset_families(text, assets):
    out = set()
    for fam, pat in DATASET_PATTERNS:
        if re.search(pat, text or "", re.I):
            out.add(fam)
    for a in assets:
        out.add(asset_family(a))
    return out


def purpose_of(title_tokens):
    for t in title_tokens:
        if t in PURPOSE:
            return PURPOSE[t], t
    return "", ""


def output_types(canon, instr):
    out = set()
    text = (canon or "") + " " + (instr or "")
    if re.search(r"Export\.image|export.*(geotiff|raster|map)", text, re.I):
        out.add("image_export")
    if re.search(r"Export\.table|shapefile|csv|feature\s*collection", text, re.I):
        out.add("table_export")
    if re.search(r"ui\.Chart|chart|histogram|time\s*series|plot", text, re.I):
        out.add("chart")
    if re.search(r"Map\.addLayer|visualiz", text, re.I):
        out.add("map_view")
    return out


IDX_CACHE = REPO / ".tmp_script_index.json"
ASSET_CACHE = REPO / ".tmp_asset_index.json"
FEAT_CACHE = REPO / ".tmp_feat_cache_v1.pkl"


def build_index():
    if IDX_CACHE.exists():
        d = json.loads(IDX_CACHE.read_text(encoding="utf-8"))
        return {k: REPO / v for k, v in d.items()}
    idx = {}
    for tree in TREE:
        if not tree.exists():
            continue
        for d in sorted(tree.iterdir()):
            if d.is_dir():
                for f in d.glob("script_*.txt"):
                    idx.setdefault(f.stem, f)
    IDX_CACHE.write_text(json.dumps(
        {k: str(v.relative_to(REPO)) for k, v in idx.items()}), encoding="utf-8")
    return idx


def load_asset_cache():
    if ASSET_CACHE.exists():
        return json.loads(ASSET_CACHE.read_text(encoding="utf-8"))
    return {}


def build_features():
    cache_key = ("feature_v2_title_raw|" + str(POOL.stat().st_mtime))
    if FEAT_CACHE.exists():
        try:
            d = pickle.loads(FEAT_CACHE.read_bytes())
            if d.get("key") == cache_key:
                print("features cache hit", flush=True)
                return d["feats"], d["rc"], d["rows"]
        except Exception as exc:  # corrupt/stale cache is non-fatal
            print("feature cache ignored:", exc, flush=True)
    man = json.loads(MAN.read_text(encoding="utf-8"))
    rc = man["row_component"]
    rs = man["row_split"]
    idx = build_index()
    print("script index", len(idx), flush=True)
    comp_instr = defaultdict(list)
    comp_scripts = defaultdict(set)
    comp_tt = defaultdict(Counter)
    comp_split = {}
    comp_rle = defaultdict(Counter)
    comp_canon = {}
    comp_title = {}
    row_scripts = []
    with POOL.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            r = json.loads(line)
            c = rc[i]
            row_scripts.append(r.get("script", ""))
            comp_split[c] = rs[i]
            comp_instr[c].append(norm_text(r.get("instruction", "")))
            if c not in comp_title:
                comp_title[c] = title_of(r.get("instruction", ""))
            comp_scripts[c].add(r.get("script", ""))
            comp_tt[c][r.get("task_type", "")] += 1
            comp_rle[c][r.get("semantic_chain_rle", "")] += 1
            if c not in comp_canon:
                comp_canon[c] = r.get("gee_canonical_chain", "")
    assets = {}
    cache = load_asset_cache()
    dirty = False
    missing = 0
    for n_done, (c, scripts) in enumerate(comp_scripts.items(), 1):
        a = set()
        for s in scripts:
            if s in cache:
                a.update(cache[s])
                continue
            p = idx.get(s)
            if not p:
                missing += 1
                continue
            src = p.read_text(encoding="utf-8", errors="replace")
            la = find_assets(src)
            cache[s] = la
            dirty = True
            a.update(la)
        assets[c] = a
        if n_done % 20000 == 0:
            print("assets", n_done, "/", len(comp_scripts), flush=True)
    if dirty:
        ASSET_CACHE.write_text(json.dumps(cache), encoding="utf-8")
    print("components", len(comp_instr), "missing scripts", missing, flush=True)
    feats = {}
    for c, instrs in comp_instr.items():
        uniq = sorted(set(instrs))
        title = comp_title[c]
        ttoks = [stem(t) for t in words(title)]
        tset = [t for t in ttoks if t not in STOP]
        purpose_class, purpose_word = purpose_of(tset)
        targets = {t for t in tset if t not in GENERIC_TARGET and t not in PURPOSE}
        rle = comp_rle[c].most_common(1)[0][0]
        fams = set()
        outs = set()
        for x in uniq:
            fams |= dataset_families(x, assets[c])
            outs |= output_types(comp_canon[c], x)
        feats[c] = {
            "cid": c, "split": comp_split[c], "n_rows": len(instrs),
            "scripts": sorted(s for s in comp_scripts[c] if s),
            "instrs": uniq,
            "title": title, "title_tokens": tset, "target_tokens": targets,
            "purpose_class": purpose_class, "purpose_word": purpose_word,
            "task_type": comp_tt[c].most_common(1)[0][0],
            "rle": rle, "rle_steps": [x.strip() for x in rle.split("->") if x.strip()],
            "canon": comp_canon[c], "assets": sorted(assets[c]),
            "asset_families": sorted(fams),
            "outputs": sorted(outs),
        }
    for f in feats.values():
        f["_title"] = set(f["title_tokens"])
    FEAT_CACHE.write_bytes(pickle.dumps(
        {"key": cache_key, "feats": feats, "rc": rc, "rows": row_scripts},
        protocol=4))
    return feats, rc, row_scripts


def chain_counter(f):
    return Counter(f["rle_steps"])


def pair_evidence(fa, fb, utok):
    body = 0.0
    for sa in fa["instrs"][:8]:
        ta = utok[sa]
        for sb in fb["instrs"][:8]:
            j = jaccard(ta, utok[sb])
            if j > body:
                body = j
    title_a, title_b = fa["_title"], fb["_title"]
    ca, cb = fa["_chain"], fb["_chain"]
    chain_j = sum((ca & cb).values()) / max(1, sum((ca | cb).values()))
    shared_out = len(set(fa["outputs"]) & set(fb["outputs"]))
    return {
        "title_j": round(jaccard(title_a, title_b), 4),
        "body_j": round(body, 4),
        "target_shared": sorted(fa["target_tokens"] & fb["target_tokens"]),
        "dataset_shared": sorted(set(fa["asset_families"]) & set(fb["asset_families"])),
        "asset_shared": sorted(set(fa["assets"]) & set(fb["assets"])),
        "asset_j": round(jaccard(set(fa["assets"]), set(fb["assets"])), 4),
        "chain_same": bool(fa["rle"]) and fa["rle"] == fb["rle"],
        "chain_j": round(chain_j, 4),
        "purpose_a": fa["purpose_class"], "purpose_b": fb["purpose_class"],
        "purpose_compatible": (not fa["purpose_class"] or not fb["purpose_class"]
                               or fa["purpose_class"] == fb["purpose_class"]),
        "task_type_same": fa["task_type"] == fb["task_type"],
        "task_type_a": fa["task_type"], "task_type_b": fb["task_type"],
        "outputs_shared": shared_out,
        "title_a": fa["title"], "title_b": fb["title"],
    }


def decide(ev):
    T, B = ev["title_j"], ev["body_j"]
    O, DF = len(ev["target_shared"]), len(ev["dataset_shared"])
    AS, A = len(ev["asset_shared"]), ev["asset_j"]
    CS, P, TT = ev["chain_same"], ev["purpose_compatible"], ev["task_type_same"]
    if (not P) and O == 0 and B < 0.50:
        return "keep_separate", "K1_purpose_conflict"
    if O == 0 and DF == 0 and AS == 0 and B < 0.50 and T < 0.60:
        return "keep_separate", "K2_no_target_or_source_overlap"
    if (not TT) and DF == 0 and AS == 0 and T < 0.40 and B < 0.50:
        return "keep_separate", "K3_structure_only"
    if AS >= 3 and A >= 0.60 and T >= 0.25 and (O >= 1 or T >= 0.50):
        return "merge", "M1_same_asset_set"
    if T >= 0.60 and (AS >= 1 or (DF >= 2 and T >= 0.70)) and P and (O >= 1 or AS >= 1):
        return "merge", "M2_title_and_source"
    if B >= 0.60 and AS >= 1 and T >= 0.25:
        return "merge", "M3_body_and_asset"
    if O >= 2 and DF >= 1 and P and T >= 0.40:
        return "merge", "M4_objective_and_dataset"
    if CS and T >= 0.50 and P and TT:
        return "merge", "M5_structure_and_title"
    if T >= 0.75 and P:
        return "merge", "M6_near_identical_title"
    if B >= 0.70 and T >= 0.40:
        return "merge", "M7_strong_body"
    return "pending", "PENDING_borderline"


def family_id(members):
    return "F" + hashlib.sha1(
        ",".join(str(x) for x in sorted(members)).encode()).hexdigest()[:16]


def edge_strength(e):
    ev = e["evidence"]
    s = (ev["title_j"] + 0.5 * ev["body_j"]
         + 0.3 * len(ev["target_shared"]) + 0.5 * len(ev["asset_shared"]))
    if e["rule"] in ("G1_exact_asset_set_group", "M1_same_asset_set"):
        s += 2.0
    elif e["rule"] in ("D2_star_group", "T1_exact_title_group"):
        s += 1.0
    return s


def build_split_v3(feats, edges, rc, max_family=10000):
    """T1-first capped union.

    1. Exact-title (T1) edges union first, unbounded: identical normalized
       titles are authoritative and must never be split across families.
    2. G1/D2 group edges are added strongest-first only if the resulting
       family stays <= max_family.  Deferred edges are recorded.
    3. No M2/M4/M5/M6/M7 pairwise edges enter family construction; they were
       the source of the 47k-component transitive chain.
    """
    parent = {c: c for c in feats}
    size = {c: 1 for c in feats}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b, cap):
        ra, rb = find(a), find(b)
        if ra == rb:
            return True
        if size[ra] + size[rb] > cap:
            return False
        if size[ra] < size[rb]:
            ra, rb = rb, ra
        parent[ra] = rb
        size[rb] += size[ra]
        return True

    t1 = [e for e in edges if e.get("group_id")
          and e["rule"] == "T1_exact_title_group"]
    others = [e for e in edges if e.get("group_id")
              and e["rule"] != "T1_exact_title_group"]
    for e in t1:
        union(e["a"], e["b"], 10 ** 9)
        e["applied"] = True
    deferred = []
    for e in sorted(others, key=edge_strength, reverse=True):
        if union(e["a"], e["b"], max_family):
            e["applied"] = True
        else:
            e["applied"] = False
            deferred.append(e)
    groups = defaultdict(list)
    for c in feats:
        groups[find(c)].append(c)
    fam = {}
    fam_members = {}
    for members in groups.values():
        fid = family_id(members)
        fam_members[fid] = members
        for c in members:
            fam[c] = fid
    ids = sorted(fam_members)
    rng = __import__("random").Random(SEED)
    rng.shuffle(ids)
    n = len(ids)
    ntr, nv = round(n * 0.8), round(n * 0.1)
    assign = {}
    for i, fid in enumerate(ids):
        assign[fid] = "train" if i < ntr else ("val" if i < ntr + nv else "test")
    fam_splits = {"train": [], "val": [], "test": []}
    for fid in ids:
        fam_splits[assign[fid]].append(fid)
    row_split_v3 = [{"train": "t", "val": "v", "test": "s"}[assign[fam[c]]] for c in rc]
    return fam, assign, fam_members, row_split_v3, fam_splits, deferred


def audit_family(members, feats, edges_by_family):
    purposes = {feats[c]["purpose_class"] for c in members if feats[c]["purpose_class"]}
    inter = None
    for c in members:
        t = feats[c]["target_tokens"]
        inter = set(t) if inter is None else (inter & t)
    flags = []
    if len(purposes) > 1 and not (inter or set()):
        flags.append("heterogeneous_purpose_and_no_shared_target")
    if len(members) > 200:
        flags.append("oversized")
    if len(members) > 50:
        es = edges_by_family
        weakest = min(es, key=lambda e: e["evidence"]["title_j"]) if es else None
        if weakest and weakest["evidence"]["title_j"] < 0.30 \
                and not weakest["evidence"]["asset_shared"] \
                and not weakest["evidence"]["dataset_shared"]:
            flags.append("weak_chain")
    return flags, sorted(inter or set())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--explore", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--max-family", type=int, default=10000)
    args = ap.parse_args()
    feats, rc, row_scripts = build_features()
    man_row_split = json.loads(MAN.read_text(encoding="utf-8"))["row_split"]
    # ---- discovery candidate generation ----
    candidates = {}

    def add(a, b, signal):
        if a == b:
            return
        k = (a, b) if a < b else (b, a)
        d = candidates.setdefault(k, {"signals": set()})
        d["signals"].add(signal)

    # body rare-token index (instruction level)
    uniq2comp = {}
    for c, f in feats.items():
        for s in f["instrs"]:
            uniq2comp.setdefault(s, c)
    uniq = sorted(uniq2comp)
    utok = {s: set(words(s)) for s in uniq}
    df = Counter()
    for ts in utok.values():
        df.update(ts)
    rare = {t for t, n in df.items() if n <= 60}
    inv = defaultdict(list)
    for s in uniq:
        for t in utok[s] & rare:
            inv[t].append(s)
    body_pairs = 0
    for t, docs in inv.items():
        docs.sort()
        for i in range(len(docs)):
            for j in range(i + 1, len(docs)):
                sa, sb = utok[docs[i]], utok[docs[j]]
                inter = sa & sb
                if len(inter) < 3:
                    continue
                if len(inter) / len(sa | sb) >= 0.45:
                    ca, cb = uniq2comp[docs[i]], uniq2comp[docs[j]]
                    if ca != cb:
                        add(ca, cb, "body_j_ge_0.45")
                        body_pairs += 1
    print("body candidate instruction pairs", body_pairs, flush=True)
    print("phase title start", flush=True)

    # title token-pair blocking: moderate-frequency tokens (df<=3000);
    # small buckets -> pairwise; large buckets -> deterministic star clusters.
    title_df = Counter()
    for c, f in feats.items():
        title_df.update(f["_title"])
    print("title_df done", len(title_df), flush=True)
    tb = defaultdict(list)
    common_title_hits = Counter()
    for c, f in feats.items():
        tt = sorted(f["_title"] - STOP)
        eligible, common_tt = [], []
        for t in tt:
            (eligible if title_df[t] <= 1500 else common_tt).append(t)
        common_title_hits.update(common_tt)
        for pair in itertools.combinations(eligible, 2):
            tb[pair].append(c)
    print("tb built", len(tb), sum(len(v) for v in tb.values()), flush=True)
    title_pairs = 0
    title_skipped = []
    title_star_groups = []
    star_merges = []
    star_buckets_processed = 0
    STAR_BUCKET_LIMIT = 30000
    for idx, (k, cs) in enumerate(tb.items()):
        if idx % 5000 == 0:
            print("tb progress", idx, "pairs", title_pairs,
                  "stars", len(star_merges), flush=True)
        cs = sorted(set(cs))
        if len(cs) < 2:
            continue
        if len(cs) <= 40:
            for a, b in itertools.combinations(cs, 2):
                if jaccard(feats[a]["_title"], feats[b]["_title"]) >= 0.40:
                    add(a, b, "title_pair")
                    title_pairs += 1
            continue
        if star_buckets_processed >= STAR_BUCKET_LIMIT:
            title_skipped.append((len(cs), k))
            continue
        star_buckets_processed += 1
        # deterministic purpose-stratified stars: avoid mixing purposes
        by_purpose = defaultdict(list)
        for c in cs:
            by_purpose[feats[c]["purpose_class"]].append(c)
        for pc, sub in sorted(by_purpose.items()):
            if len(sub) < 2:
                continue
            if len(title_star_groups) >= 50000:
                title_skipped.append((len(cs), k))
                break
            sub = sorted(sub)
            sample = sub[:10] + sub[-10:]
            anchor = max(sub[:20], key=lambda c: sum(
                jaccard(feats[c]["_title"], feats[s]["_title"])
                for s in sample))
            members = [c for c in sub if c != anchor and
                       (jaccard(feats[anchor]["_title"], feats[c]["_title"]) >= 0.50
                        or len(feats[anchor]["target_tokens"]
                               & feats[c]["target_tokens"]) >= 2)]
            gid = "S" + hashlib.sha1(
                ("|".join(k) + "|" + pc).encode()).hexdigest()[:16]
            title_star_groups.append({"group_id": gid, "bucket": list(k),
                                      "purpose_class": pc,
                                      "bucket_size": len(cs), "anchor": anchor,
                                      "n_members": len(members),
                                      "decision": "merge" if members else "keep_separate"})
            for c in members:
                star_merges.append((anchor, c, gid))
    print("title token-pair candidate pairs", title_pairs,
          "star_edges", len(star_merges), "star_groups", len(title_star_groups),
          "skipped_keys", len(title_skipped),
          "top", sorted(title_skipped, reverse=True)[:5],
          "common_title_tokens", common_title_hits.most_common(5), flush=True)
    print("phase title done", flush=True)

    # exact-title groups (strongest same-family evidence)
    by_title = defaultdict(list)
    for c, f in feats.items():
        if f["title"]:
            by_title[f["title"]].append(c)
    title_exact_groups = []
    title_group_merges = []
    for title, cs in by_title.items():
        if len(cs) < 2:
            continue
        cs = sorted(set(cs))
        anchor = cs[0]
        gid = "T" + hashlib.sha1(title.encode()).hexdigest()[:16]
        for c in cs[1:]:
            title_group_merges.append((anchor, c, gid))
        title_exact_groups.append({"group_id": gid, "n_components": len(cs),
                                   "title": title})
    print("exact-title groups", len(title_exact_groups), "edges",
          len(title_group_merges), flush=True)

    # exact asset-set groups: purpose-stratified group adjudication (O(n) edges)
    asset_sets = defaultdict(list)
    for c, f in feats.items():
        if len(f["assets"]) >= 2:
            asset_sets[tuple(f["assets"])].append(c)
    asset_set_groups = []
    group_merges = []
    for sig, cs in asset_sets.items():
        if len(cs) < 2:
            continue
        cs = sorted(set(cs))
        by_purpose = defaultdict(list)
        for c in cs:
            by_purpose[feats[c]["purpose_class"]].append(c)
        for pc, sub in sorted(by_purpose.items()):
            if len(sub) < 2:
                continue
            sub = sorted(sub)
            sample = sub[:10] + sub[-10:]
            anchor = max(sub[:20], key=lambda c: sum(
                jaccard(feats[c]["_title"], feats[s]["_title"]) for s in sample))
            members = []
            for c in sub:
                if c == anchor:
                    continue
                shared = feats[anchor]["target_tokens"] & feats[c]["target_tokens"]
                if jaccard(feats[anchor]["_title"], feats[c]["_title"]) >= 0.50 \
                        or len(shared) >= 2:
                    members.append(c)
            gid = "G" + hashlib.sha1(
                ("|".join(sig) + "|" + pc).encode()).hexdigest()[:16]
            asset_set_groups.append({
                "group_id": gid, "n_components": len(sub),
                "signature_group_size": len(cs),
                "asset_set_size": len(sig), "assets": list(sig),
                "purpose_class": pc, "anchor": anchor,
                "n_merged": len(members),
                "decision": "merge" if members else "keep_separate",
                "rule": "G1_exact_asset_set_group" if members else "G1_incoherent_group"})
            for c in members:
                group_merges.append((anchor, c, gid))
    print("asset-set groups", len(asset_set_groups), "group merges",
          len(group_merges), flush=True)
    print("phase asset done", flush=True)

    # exact semantic chain template + title overlap
    rle_bucket = defaultdict(list)
    for c, f in feats.items():
        if f["rle"]:
            rle_bucket[f["rle"]].append(c)
    chain_pairs = 0
    chain_skipped = []
    for k, cs in rle_bucket.items():
        if len(cs) < 2:
            continue
        if len(cs) > 100:
            chain_skipped.append((len(cs), k[:80]))
            continue
        for a, b in itertools.combinations(sorted(set(cs)), 2):
            fa, fb = feats[a], feats[b]
            if jaccard(fa["_title"], fb["_title"]) >= 0.35:
                add(a, b, "chain_template")
                chain_pairs += 1
    print("chain candidate pairs", chain_pairs, "skipped_keys", len(chain_skipped),
          "top", chain_skipped[:3], flush=True)
    print("phase chain done", flush=True)

    # dataset family + rare target token blocking
    target_df = Counter()
    for c, f in feats.items():
        target_df.update(f["target_tokens"])
    db = defaultdict(list)
    for c, f in feats.items():
        for fam in f["asset_families"]:
            for t in f["target_tokens"]:
                if target_df[t] <= 100:
                    db[(fam, t)].append(c)
    ds_pairs = 0
    ds_skipped = []
    for k, cs in db.items():
        if len(cs) < 2:
            continue
        if len(cs) > 10:
            ds_skipped.append((len(cs), k))
            continue
        for a, b in itertools.combinations(sorted(set(cs)), 2):
            add(a, b, "dataset_target")
            ds_pairs += 1
    print("dataset-target candidate pairs", ds_pairs,
          "rare_target_tokens", sum(1 for t, n in target_df.items() if n <= 100),
          "skipped_keys", len(ds_skipped),
          "top", sorted(ds_skipped, reverse=True)[:5], flush=True)
    print("TOTAL unique candidate component pairs", len(candidates), flush=True)
    pair_set = set(candidates)
    group_parent = {}

    def gfind(x):
        group_parent.setdefault(x, x)
        while group_parent[x] != x:
            group_parent[x] = group_parent[group_parent[x]]
            x = group_parent[x]
        return x

    def gunion(a, b):
        ra, rb = gfind(a), gfind(b)
        if ra != rb:
            group_parent[ra] = rb

    for (a, b, gid) in group_merges + star_merges + title_group_merges:
        k = (a, b) if a < b else (b, a)
        pair_set.add(k)
        gunion(a, b)
    print("known family check:", flush=True)
    for a, b in [(48801, 50842), (48801, 74228), (50842, 74228), (45165, 103943)]:
        k = (a, b) if a < b else (b, a)
        print(" ", a, b, "direct_candidate=", k in pair_set,
              "same_group_or_star=", gfind(a) == gfind(b),
              candidates.get(k, {}).get("signals"))
    if args.explore:
        return
    if not args.build:
        return
    for f in feats.values():
        f["_chain"] = Counter(f["rle_steps"])
    dec_path = B / "B_TRACK_TASK_FAMILY_DECISIONS_V1.jsonl.gz"
    edges = []
    decision_counts = Counter()
    rule_counts = Counter()
    keep_rule_counts = Counter()

    def emit(e, fh):
        fh.write(json.dumps(e, ensure_ascii=False, separators=(",", ":")) + "\n")
        decision_counts[e["decision"]] += 1
        rule_counts[e["rule"]] += 1
        if e["decision"] == "keep_separate":
            keep_rule_counts[e["rule"]] += 1
        else:
            edges.append(e)

    def edge_from_ev(a, b, ev, decision, rule, signals, group_id=None):
        fa, fb = feats[a], feats[b]
        conflicts = []
        if fa["purpose_class"] and fb["purpose_class"] and not ev["purpose_compatible"]:
            conflicts.append("purpose_differs")
        if fa["outputs"] and fb["outputs"] and not ev["outputs_shared"]:
            conflicts.append("output_differs")
        if not ev["task_type_same"]:
            conflicts.append("task_type_differs")
        e = {"a": a, "b": b, "split_a": fa["split"], "split_b": fb["split"],
             "decision": decision, "rule": rule,
             "review_status": "pending_owner" if decision == "pending" else "rule_decided",
             "conflicts": conflicts, "signals": signals, "evidence": ev}
        if group_id:
            e["group_id"] = group_id
        return e

    with gzip.open(dec_path, "wt", encoding="utf-8") as fh:
        for (a, b), d in candidates.items():
            ev = pair_evidence(feats[a], feats[b], utok)
            decision, rule = decide(ev)
            emit(edge_from_ev(a, b, ev, decision, rule, sorted(d["signals"])), fh)
        for (a, b, gid) in group_merges:
            ev = pair_evidence(feats[a], feats[b], utok)
            emit(edge_from_ev(a, b, ev, "merge", "G1_exact_asset_set_group",
                              ["asset_set_exact"], gid), fh)
        for (a, b, gid) in title_group_merges:
            ev = pair_evidence(feats[a], feats[b], utok)
            emit(edge_from_ev(a, b, ev, "merge", "T1_exact_title_group",
                              ["title_exact"], gid), fh)
        for (a, b, gid) in star_merges:
            ev = pair_evidence(feats[a], feats[b], utok)
            emit(edge_from_ev(a, b, ev, "merge", "D2_star_group",
                              ["title_star"], gid), fh)
    dec_sha = hashlib.sha256(dec_path.read_bytes()).hexdigest()
    fam, assign, fam_members, row_split_v3, fam_splits, deferred = build_split_v3(
        feats, edges, rc, max_family=args.max_family)
    family_ids = sorted(fam_members)
    family_index = {fid: i for i, fid in enumerate(family_ids)}
    row_family = [family_index[fam[c]] for c in rc]
    fam_edges = defaultdict(list)
    for e in edges:
        if e["decision"] == "merge" and e.get("applied"):
            fam_edges[fam[e["a"]]].append(e)
    family_records = []
    for fid, members in fam_members.items():
        if len(members) < 2:
            continue
        es = fam_edges.get(fid, [])
        flags, shared_targets = audit_family(members, feats, es)
        purpose_classes = sorted({feats[c]["purpose_class"] for c in members
                                  if feats[c]["purpose_class"]})
        dataset_union = sorted({x for c in members for x in feats[c]["asset_families"]})
        tvals = [e["evidence"]["title_j"] for e in es] or [0.0]
        target_union = sorted({t for e in es for t in e["evidence"]["target_shared"]})
        asset_union = sorted({a for e in es for a in e["evidence"]["asset_shared"]})
        family_records.append({
            "family_id": fid, "n_components": len(members),
            "n_rows": sum(feats[c]["n_rows"] for c in members),
            "split_v3": assign[fid],
            "v2_splits": sorted({feats[c]["split"] for c in members}),
            "cross_split_v2": len({feats[c]["split"] for c in members}) > 1,
            "audit_flags": flags, "shared_targets": shared_targets,
            "purpose_classes": purpose_classes, "dataset_families": dataset_union,
            "members": [{"component_id": c, "split_v2": feats[c]["split"],
                         "scripts": feats[c]["scripts"],
                         "n_rows": feats[c]["n_rows"], "title": feats[c]["title"],
                         "task_type": feats[c]["task_type"],
                         "purpose": feats[c]["purpose_class"],
                         "assets": feats[c]["assets"]} for c in sorted(members)],
            "edge_summary": {
                "n_edges": len(es),
                "rules": dict(Counter(e["rule"] for e in es)),
                "title_j_min": round(min(tvals), 4),
                "title_j_max": round(max(tvals), 4),
                "shared_targets_union": target_union[:50],
                "shared_assets_union": asset_union[:20],
            },
        })
    family_records.sort(key=lambda x: x["family_id"])
    pending = [e for e in edges if e["decision"] == "pending"]
    cross_merge = [e for e in edges if e["decision"] == "merge"
                   and e.get("applied") and e["split_a"] != e["split_b"]]
    pending_cross = [e for e in pending if e["split_a"] != e["split_b"]]
    changed_rows = sum(1 for i in range(len(rc)) if man_row_split[i] != row_split_v3[i])
    changed_components = sum(
        1 for c in feats
        if {"train": "t", "val": "v", "test": "s"}[assign[fam[c]]] != feats[c]["split"])
    adm = json.loads((B / "Q2_ADMISSION_V1.json").read_text(encoding="utf-8"))
    aud_scripts = {s for r in adm["records"] for s in (r["script_a"], r["script_b"])}
    aud_rows = [i for i, s in enumerate(row_scripts) if s in aud_scripts]
    aud_trans = Counter(f"{man_row_split[i]}->{row_split_v3[i]}" for i in aud_rows)
    pool_sha = hashlib.sha256(POOL.read_bytes()).hexdigest()
    v2_sha = hashlib.sha256(MAN.read_bytes()).hexdigest()
    code_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    fam_map = {str(c): fam[c] for c in sorted(feats)}
    fam_map_sha = hashlib.sha256(
        json.dumps(fam_map, sort_keys=True).encode()).hexdigest()
    split_str = "".join(row_split_v3)
    split_sha = hashlib.sha256(split_str.encode()).hexdigest()
    split_components = Counter()
    for c in feats:
        split_components[{"train": "t", "val": "v", "test": "s"}[assign[fam[c]]]] += 1
    man_v3 = {
        "artifact": "B_TRACK_SPLIT_MANIFEST_V3", "version": "V3",
        "date": "2026-10-18", "seed": SEED,
        "pool_rows": len(rc), "components": len(feats),
        "families": len(family_ids), "families_merged": len(family_records),
        "split_families": {k: len(v) for k, v in fam_splits.items()},
        "split_components": dict(split_components),
        "split_rows": dict(Counter(row_split_v3)),
        "rule": "family-level 80/10/10; family = union of V2 components connected by "
                "merge-disposition task-family edges; component atomic; "
                "split membership != training admission",
        "family_ids": family_ids, "row_split": split_str,
        "row_component": rc, "row_family": row_family,
        "hashes": {"pool_sha256": pool_sha, "v2_manifest_sha256": v2_sha,
                   "code_sha256": code_sha, "family_map_sha256": fam_map_sha,
                   "row_split_sha256": split_sha},
        "note": "V2 preserved; regenerate with scripts/b_track_task_family_merge_v1.py --build",
    }
    ledger = {
        "artifact": "B_TRACK_TASK_FAMILY_MERGE_LEDGER_V1", "date": "2026-10-18",
        "rules_version": "V1_pre_registered",
        "inputs": {"pool_sha256": pool_sha, "v2_manifest_sha256": v2_sha,
                   "code_sha256": code_sha, "seed": SEED},
        "counts": {
            "candidate_pairs": sum(decision_counts.values()),
            "pairwise_merge_edges": decision_counts.get("merge", 0),
            "family_edges_used": sum(
                1 for e in edges if e["decision"] == "merge" and e.get("applied")),
            "pairwise_merge_not_used_for_family": sum(
                1 for e in edges if e["decision"] == "merge" and not e.get("applied")),
            "decisions": dict(decision_counts),
            "rules": dict(rule_counts),
            "families_total": len(family_ids),
            "families_merged": len(family_records),
            "components_in_merged_families": sum(r["n_components"] for r in family_records),
            "largest_family_components": max((r["n_components"] for r in family_records), default=1),
            "cross_split_merge_edges": len(cross_merge),
            "cross_split_pending_edges": len(pending_cross),
            "family_assignment_deferred": len(deferred),
            "deferred_high_confidence": sum(
                1 for e in deferred
                if e["evidence"]["title_j"] >= 0.60
                or len(e["evidence"]["asset_shared"]) >= 1),
            "max_family_cap": args.max_family,
            "title_star_groups": len(title_star_groups),
            "title_star_edges": len(star_merges),
            "title_exact_groups": len(title_exact_groups),
            "title_exact_edges": len(title_group_merges),
            "asset_set_groups": len(asset_set_groups),
            "asset_group_edges": len(group_merges),
            "rows_changed_v2_to_v3": changed_rows,
            "components_changed_v2_to_v3": changed_components,
            "audited_rows": len(aud_rows),
            "audited_split_transitions": dict(aud_trans),
        },
        "families": family_records,
        "asset_set_groups": asset_set_groups,
        "title_star_groups": title_star_groups,
        "title_exact_groups": title_exact_groups,
        "pending_edges_cross_split": pending_cross,
        "pending_summary": {"total": len(pending),
                            "cross_split": len(pending_cross),
                            "same_split": len(pending) - len(pending_cross),
                            "by_rule": dict(Counter(e["rule"] for e in pending))},
        "size_cap_deferred_high_confidence": [
            {"a": e["a"], "b": e["b"], "split_a": e["split_a"],
             "split_b": e["split_b"], "rule": e["rule"],
             "title_j": e["evidence"]["title_j"], "body_j": e["evidence"]["body_j"],
             "target_shared": e["evidence"]["target_shared"],
             "asset_shared": e["evidence"]["asset_shared"]}
            for e in deferred
            if e["evidence"]["title_j"] >= 0.60
            or len(e["evidence"]["asset_shared"]) >= 1][:200],
        "keep_separate_summary": {
            "count": decision_counts.get("keep_separate", 0),
            "by_rule": dict(keep_rule_counts)},
        "decision_log": {"path": dec_path.name, "sha256": dec_sha,
                         "n_edges": sum(decision_counts.values()),
                         "format": "jsonl.gz; one candidate edge per line"},
        "skipped_buckets": {
            "title": [{"size": n, "key": list(k)} for n, k in
                      sorted(title_skipped, reverse=True)[:50]],
            "chain": [{"size": n, "key": k} for n, k in
                      sorted(chain_skipped, reverse=True)[:50]],
            "dataset_target": [{"size": n, "key": list(k)} for n, k in
                               sorted(ds_skipped, reverse=True)[:50]]},
        "limitations": [
            "lexical similarity is not semantic understanding; synonym-heavy families may be missed",
            "asset extraction covers only literal ee constructor args",
            "representative title drives purpose/target evidence",
            "skipped high-volume blocking buckets are listed",
            "one scan cannot prove absence of semantic leakage",
        ],
    }
    (B / "B_TRACK_SPLIT_MANIFEST_V3.json").write_text(
        json.dumps(man_v3, ensure_ascii=False), encoding="utf-8")
    with gzip.open(B / "B_TRACK_TASK_FAMILY_MERGE_LEDGER_V1.json.gz",
                   "wt", encoding="utf-8") as fh:
        json.dump(ledger, fh, ensure_ascii=False, indent=1)
    print(json.dumps(ledger["counts"], ensure_ascii=False, indent=1))
    print("v3 split rows", man_v3["split_rows"], "families",
          man_v3["split_families"], "split_sha", split_sha[:16])


if __name__ == "__main__":
    main()
