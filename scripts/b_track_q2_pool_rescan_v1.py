#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B-track Q2 pool-level read-only re-scan (owner ruling 2026-10-17 evening).

Owner directive: pool-level mechanical re-scan FIRST (read-only), to estimate
the occurrence range of the four difference classes + description-fidelity
issues over the near-duplicate pair population; A/B design freeze only after;
no RLE modification, no chain cleansing, no training.

Method (owner-specified division of labor):
  - mechanical full scan: SHA-1 / normalized-source / canonical-multiset /
    literal-set comparisons CAN detect code identity and where literals
    differ, but CANNOT judge analytical significance;
  - therefore every class label below is a CANDIDATE (flags kept separately,
    classes NOT forced mutually exclusive: difference-source axis separate
    from description-fidelity axis);
  - substantive-difference candidates go to a seeded stratified adjudication
    sample for semantic reading (owner).

Calibration: the ten source-verified pairs (Q2_V3 / Q2_V2P0 findings) are
re-classified by the same classifier; agreement/disagreement disclosed.

Population: EXACT replication of the Q2 pair finder in
b_track_q23_pool_audit_v1.py (rare-token df<=60, >=3 shared rare tokens,
token-set Jaccard >= 0.75, seed-independent deterministic enumeration).
Sanity gate: n_near_dup_pairs must equal 4,554.

Coverage honesty: local script corpus = .tmp_gee_batch13_sources/Data (full
B-pool scripts subset) + .tmp_gee_batch8_ast_bridge/sources (subset). Pairs
whose member scripts are not locally available are counted and EXCLUDED from
source-level classes (kept in denominators).

Outputs (b_track_audit_v1/):
  Q2_POOL_RESCAN_MECHANICAL_V1.json   full mechanical results
  Q2_POOL_RESCAN_MECHANICAL_V1.md     report (denominators, coverage,
                                      class distribution, calibration,
                                      uncertainty statements)
  Q2_POOL_RESCAN_ADJUDICATION_SAMPLE_V1.md / .json  stratified owner sample

Read-only; deterministic; seed 20261017.
"""
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
POOL = REPO.parent / "04_DIAG_WORK/b1_gee_stage_train.jsonl"
OUT_DIR = (REPO / ("docs/reports/route2_p0_contract/plan_pipeline_v1/"
                   "planning_capability_audit_v1/diag50_v1/b_track_audit_v1"))
TREES = [REPO / ".tmp_gee_batch13_sources/Data",
         REPO / ".tmp_gee_batch8_ast_bridge/sources"]
SEED = 20261017
RARE_DF_CAP = 60
MIN_SHARED_RARE = 3
JACCARD_MIN = 0.75
SAMPLE_PER_CLASS = 12

TOKEN_RE = re.compile(r"[a-z0-9]+")
NUM_RE = re.compile(r"(?<![\\w.])(\d{1,4}(?:\.\d+)?)(?![\\w.])")
DS_RE = re.compile(r"ee\.(?:ImageCollection|Image|FeatureCollection)\(\s*['\"]([^'\"]+)['\"]")

FAMILY_PATTERNS = [
    (r"landsat\s*5", ["lt05"]), (r"landsat\s*7", ["le07"]),
    (r"landsat\s*8", ["lc08", "lo08"]),
    (r"sentinel[- ]1", ["sentinel-1", "copernicus/s1", "sar"]),
    (r"sentinel[- ]2", ["sentinel-2", "copernicus/s2"]),
    (r"modis", ["modis", "mod/"]), (r"chelsa", ["chelsa"]),
    (r"gedi", ["gedi"]), (r"hansen", ["hansen", "global_forest_change"]),
    (r"worldcover", ["worldcover"]), (r"srtm", ["srtm", "nasadem"]),
    (r"grace", ["grace"]), (r"chirps", ["chirps"]), (r"gldas", ["gldas"]),
    (r"terraclimate", ["terraclimate"]),
    (r"dynamic\s*world", ["dynworld", "dynamicworld"]),
    (r"worldclim", ["worldclim"]),
]


def norm_text(s):
    return re.sub(r"\s+", " ", s.strip().lower())


def tokens(s):
    return set(TOKEN_RE.findall(s))


def canon_hash(s):
    return hashlib.sha256(re.sub(r"\s+", " ", s.strip()).encode()).hexdigest()[:16]


def src_normalize(src):
    """Strip //-comments and all whitespace for formatting-only comparison."""
    lines = [l.split("//")[0] for l in src.splitlines()]
    return re.sub(r"\s+", "", "\n".join(lines))


def script_signals(src):
    low = src.lower()
    ui = len(re.findall(r"\bui\.\w", src))
    viz = len(re.findall(r"\bMap\.(?:addLayer|setCenter|centerObject|add|setOptions)", src))
    datasets = set(DS_RE.findall(src))
    fams = set("/".join(re.sub(r"\d+", "", c) for c in d.lower().split("/")[:2])
               for d in datasets)
    numbers = set(NUM_RE.findall(src))
    nlines = [re.sub(r"\s+", "", l.split("//")[0]) for l in src.splitlines()]
    nlines = [l for l in nlines if len(l) >= 8]
    cnt = Counter(nlines)
    dup = sum(c - 1 for c in cnt.values() if c > 1)
    return {"ui": ui, "viz": viz, "datasets": datasets, "families": fams,
            "numbers": numbers, "dup_lines": dup,
            "sha": hashlib.sha1(src.encode("utf-8", "replace")).hexdigest()[:12],
            "norm_sha": hashlib.sha1(src_normalize(src).encode()).hexdigest()[:12],
            "n_chars": len(src)}


def fidelity_flags(instruction, src):
    """Mechanical LOWER-BOUND candidates only (no semantic claim).

    numbers_missing: numbers asserted in the instruction absent from source.
    dataset_absent: dataset family named in the instruction with no matching
    literal in source.
    """
    low = norm_text(instruction)
    missing = []
    for n in set(NUM_RE.findall(low)):
        if n not in src:
            missing.append(n)
    ds_absent = []
    for pat, keys in FAMILY_PATTERNS:
        if re.search(pat, low) and not any(k in src.lower() for k in keys):
            ds_absent.append(pat)
    return {"numbers_missing": missing, "dataset_absent": ds_absent}


def classify_diff(sa, sb, sig_a, sig_b, rle_shared):
    """Primary mechanical class + all flags (classes are candidates)."""
    ca = sig_a["canon_list"]; cb = sig_b["canon_list"]
    ordered_eq = ca == cb
    multiset_eq = sorted(ca) == sorted(cb)
    sym_diff = set(ca) ^ set(cb)
    num_diff = sig_a["numbers"] ^ sig_b["numbers"]
    fam_eq = sig_a["families"] == sig_b["families"]
    ds_exact_diff = bool(sig_a["datasets"] ^ sig_b["datasets"])
    ui_delta = abs((sig_a["ui"] + sig_a["viz"]) - (sig_b["ui"] + sig_b["viz"]))
    dup_delta = abs(sig_a["dup_lines"] - sig_b["dup_lines"])
    flags = {
        "rle_shared": rle_shared,
        "src_sha_equal": sig_a["sha"] == sig_b["sha"],
        "src_norm_equal": sig_a["norm_sha"] == sig_b["norm_sha"],
        "canon_ordered_equal": ordered_eq,
        "canon_multiset_equal": multiset_eq,
        "canon_sym_diff_n": len(sym_diff),
        "number_sym_diff_n": len(num_diff),
        "families_equal": fam_eq,
        "datasets_exact_differ": ds_exact_diff,
        "ui_delta": ui_delta,
        "dup_delta": dup_delta,
    }
    if rle_shared:
        cls = "template_multiplicity_artifact"
    elif sig_a["norm_sha"] == sig_b["norm_sha"]:
        cls = "formatting_only"
    elif ordered_eq:
        cls = "literal_param_only"
    elif multiset_eq:
        cls = "reorder_refactor_candidate"
    elif len(sym_diff) <= 2 and len(num_diff) <= 8:
        cls = "small_literal_cosmetic_candidate"
    elif fam_eq and ds_exact_diff:
        cls = "asset_version_candidate"
    elif ui_delta >= 3:
        cls = "ui_scaffold_candidate"
    elif dup_delta >= 5:
        cls = "duplicate_block_candidate"
    else:
        cls = "substantive_structural_candidate"
    return cls, flags


def main():
    rng = random.Random(SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ---------- pass 1: pool rows (keep instruction text for fidelity proxy)
    rows = []      # (norm_instr, rle, canon, script_id, raw_instr)
    print("loading pool ...", flush=True)
    with POOL.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            rows.append((norm_text(r.get("instruction", "")),
                         re.sub(r"\s+", " ", r.get("semantic_chain_rle", "").strip()),
                         r.get("gee_canonical_chain") or "",
                         r.get("script") or "",
                         r.get("instruction", "")))
    n_rows = len(rows)

    instr_groups = defaultdict(list)
    for i, (ni, *_rest) in enumerate(rows):
        instr_groups[ni].append(i)

    # ---------- pass 2: replicate Q2 pair finder exactly ----------
    ids = {ni: k for k, ni in enumerate(instr_groups)}
    NID = len(ids)
    df = Counter()
    tok_sets = {}
    for ni in instr_groups:
        ts = tokens(ni)
        tok_sets[ni] = ts
        df.update(ts)
    tok_sets_by_id = {ids[ni]: ts for ni, ts in tok_sets.items()}
    rare = {t for t, c in df.items() if c <= RARE_DF_CAP}
    inv = defaultdict(list)
    for ni, ts in tok_sets.items():
        for t in ts & rare:
            inv[t].append(ids[ni])
    pairs = []
    seen = set()
    for t, doc_ids in inv.items():
        doc_ids.sort()
        for a_i in range(len(doc_ids)):
            a = doc_ids[a_i]
            for b_i in range(a_i + 1, len(doc_ids)):
                b = doc_ids[b_i]
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
    print(f"pairs: {len(pairs)} (expected 4554)", flush=True)
    if len(pairs) != 4554:
        sys.exit("SANITY GATE FAILED: pair count != 4554; aborting")

    id2ni = {v: k for k, v in ids.items()}

    # per-instruction representative (first row) + rle set
    rep = {}
    rle_sets = {}
    for ni, idxs in instr_groups.items():
        i0 = idxs[0]
        rep[ni] = {"rle": rows[i0][1], "canon": rows[i0][2], "script": rows[i0][3],
                   "raw": rows[i0][4]}
        rle_sets[ni] = {rows[i][1] for i in idxs}

    # ---------- script index + coverage ----------
    print("indexing local corpus trees ...", flush=True)
    index = {}
    name_collisions = 0
    for tree in TREES:
        if not tree.exists():
            continue
        for d in sorted(tree.iterdir()):
            if not d.is_dir():
                continue
            for f in d.glob("script_*.txt"):
                name = f.name[:-4]
                if name in index:
                    name_collisions += 1
                else:
                    index[name] = f
    print(f"corpus index: {len(index)} scripts, {name_collisions} name collisions",
          flush=True)

    member_scripts = set()
    for _j, a, b in pairs:
        member_scripts.add(rep[id2ni[a]]["script"])
        member_scripts.add(rep[id2ni[b]]["script"])
    covered = {s: index[s] for s in member_scripts if s in index}
    print(f"pair-member unique scripts: {len(member_scripts)}; covered: "
          f"{len(covered)} ({len(covered)/max(1,len(member_scripts)):.1%})",
          flush=True)

    # ---------- read + signal-cache covered scripts ----------
    cache = {}
    for s, path in covered.items():
        try:
            src = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        cache[s] = (src, script_signals(src))
    # canonical lists are ROW-level and attached at classification time below.

    # ---------- classify pairs ----------
    diff_pairs, same_pairs = [], []
    for j, a, b in pairs:
        nia, nib = id2ni[a], id2ni[b]
        ra, rb = rep[nia], rep[nib]
        key = {"jaccard": round(j, 4),
               "a": nia, "b": nib,
               "rle_a": ra["rle"], "rle_b": rb["rle"],
               "script_a": ra["script"], "script_b": rb["script"]}
        is_diff = rle_sets[nia] != rle_sets[nib]
        rle_shared = bool(rle_sets[nia] & rle_sets[nib])
        sa_ok = ra["script"] in cache
        sb_ok = rb["script"] in cache
        rec = {**key, "scripts_covered": sa_ok and sb_ok}
        if sa_ok and sb_ok:
            src_a, sig_a = cache[ra["script"]]
            src_b, sig_b = cache[rb["script"]]
            sig_a = dict(sig_a); sig_b = dict(sig_b)
            sig_a["canon_list"] = [c.strip() for c in ra["canon"].split("->")] if ra["canon"] else []
            sig_b["canon_list"] = [c.strip() for c in rb["canon"].split("->")] if rb["canon"] else []
            if is_diff:
                cls, flags = classify_diff(ra["script"], rb["script"], sig_a, sig_b, rle_shared)
                rec.update({"primary_class": cls, "flags": flags,
                            "sha_a": sig_a["sha"], "sha_b": sig_b["sha"]})
            else:
                # same-template axis: same RLE template; what differs underneath?
                if sig_a["sha"] == sig_b["sha"]:
                    cls = "same_code_two_descriptions"
                elif sig_a["norm_sha"] == sig_b["norm_sha"]:
                    cls = "formatting_only"
                elif sig_a["canon_list"] == sig_b["canon_list"]:
                    cls = "same_template_literal_diff"
                else:
                    cls = "same_template_canonical_diff"
                rec.update({"primary_class": cls,
                            "sha_a": sig_a["sha"], "sha_b": sig_b["sha"]})
            # fidelity proxy per side (difference-source vs fidelity = 2 axes)
            for side, instr, src in (("a", ra["raw"], src_a), ("b", rb["raw"], src_b)):
                ff = fidelity_flags(instr, src)
                if ff["numbers_missing"] or ff["dataset_absent"]:
                    rec[f"fidelity_{side}"] = ff
        (diff_pairs if is_diff else same_pairs).append(rec)

    n_diff_uncovered = sum(1 for r in diff_pairs if not r["scripts_covered"])
    n_same_uncovered = sum(1 for r in same_pairs if not r["scripts_covered"])

    # ---------- calibration on the ten source-verified pairs ----------
    pkt_path = OUT_DIR / "Q2_PRIORITY_VERIFICATION_PACKET_V1.json"
    calib = []
    if pkt_path.exists():
        pkt = json.loads(pkt_path.read_text(encoding="utf-8"))
        by_pair = {}
        for r in diff_pairs + same_pairs:
            by_pair[(r["a"], r["b"])] = r
        known = {
            "SAME-15": "same_code_two_descriptions", "SAME-19": "same_template_literal_diff",
            "SAME-11": "same_code_two_descriptions", "SAME-9": "same_template_literal_diff",
            "DIFF-6": "ui_scaffold_candidate", "DIFF-4": "substantive_structural_candidate",
            "DIFF-5": "duplicate_block_candidate", "DIFF-1": "substantive_structural_candidate",
            "DIFF-12": "asset_version_candidate",
            "DIFF-19": "small_literal_cosmetic_candidate",
            "DIFF-20": "template_multiplicity_artifact",
        }
        for pid, mpair in iter_packet_pairs(pkt):
            hit = by_pair.get((norm_text(mpair["instruction_a"]),
                               norm_text(mpair["instruction_b"])))
            if hit is None:  # representative order may flip
                hit = by_pair.get((norm_text(mpair["instruction_b"]),
                                   norm_text(mpair["instruction_a"])))
            if hit is None or not hit.get("scripts_covered"):
                calib.append({"id": pid, "found": False})
                continue
            agree = hit.get("primary_class") == known.get(pid)
            calib.append({"id": pid, "found": True, "covered": True,
                          "mechanical_class": hit.get("primary_class"),
                          "source_verified_class": known.get(pid),
                          "agree": agree})

    # ---------- aggregates ----------
    def dist(recs):
        return dict(Counter(r.get("primary_class", "UNCOVERED") for r in recs))

    fidelity_rates = {
        "diff_pairs_with_any_fidelity_flag": sum(
            1 for r in diff_pairs if r.get("scripts_covered") and
            ("fidelity_a" in r or "fidelity_b" in r)),
        "same_pairs_with_any_fidelity_flag": sum(
            1 for r in same_pairs if r.get("scripts_covered") and
            ("fidelity_a" in r or "fidelity_b" in r)),
    }
    covered_diff = [r for r in diff_pairs if r.get("scripts_covered")]
    covered_same = [r for r in same_pairs if r.get("scripts_covered")]

    # ---------- stratified adjudication sample ----------
    sample = []
    for bucket, recs in (("diff", covered_diff), ("same", covered_same)):
        by_cls = defaultdict(list)
        for r in recs:
            by_cls[r["primary_class"]].append(r)
        for cls, items in sorted(by_cls.items()):
            take = rng.sample(items, min(SAMPLE_PER_CLASS, len(items)))
            for r in take:
                sample.append({"bucket": bucket, "class": cls,
                               "jaccard": r["jaccard"], "a": r["a"], "b": r["b"],
                               "rle_a": r["rle_a"], "rle_b": r["rle_b"],
                               "script_a": r["script_a"], "script_b": r["script_b"],
                               "flags": r.get("flags"),
                               "fidelity_a": r.get("fidelity_a"),
                               "fidelity_b": r.get("fidelity_b")})

    out = {
        "artifact": "Q2_POOL_RESCAN_MECHANICAL_V1",
        "date": "2026-10-17",
        "owner_ruling_ref": "chat ruling 2026-10-17 evening (registered in MD)",
        "read_only": True, "seed": SEED,
        "population": {
            "pool_rows": n_rows,
            "n_near_dup_pairs": len(pairs),
            "n_diff_template_pairs": len(diff_pairs),
            "n_same_template_pairs": len(same_pairs),
            "unique_member_scripts": len(member_scripts),
            "scripts_locally_covered": len(covered),
            "member_coverage_ratio": round(len(covered) / max(1, len(member_scripts)), 4),
        },
        "uncovered": {"diff_pairs": n_diff_uncovered,
                      "same_pairs": n_same_uncovered},
        "diff_template_class_distribution": dist(covered_diff),
        "same_template_class_distribution": dist(covered_same),
        "fidelity_proxy": fidelity_rates,
        "fidelity_caveat": ("numbers_missing/dataset_absent 是机械下界候选"
                            "（数字/数据集名在源码中缺失即标记；不含语义级失实"
                            "如 SAME-15 目标变量写错——机械层不可见）"),
        "calibration_ten_known_pairs": calib,
        "class_definitions": {
            "template_multiplicity_artifact": "两指令共享至少一个模板但模板集合不同（DIFF-20 型：代表链可能相同）",
            "formatting_only": "归一化源码相同（仅格式差异）",
            "literal_param_only": "canonical API 序列完全相同，仅字面量不同（SAME-19/19 型）",
            "reorder_refactor_candidate": "canonical 多重集相同但顺序不同（重构候选）",
            "small_literal_cosmetic_candidate": "canonical 对称差≤2 且数字对称差≤8（DIFF-19 型小差异）",
            "asset_version_candidate": "数据集族相同但精确 ID 不同（DIFF-12 型版本差异）",
            "ui_scaffold_candidate": "UI/可视化调用差≥3（DIFF-6 型脚手架）",
            "duplicate_block_candidate": "重复行差≥5（DIFF-5 型拼接变体）",
            "substantive_structural_candidate": "以上规则均不匹配——需人工语义判读（规划结构差异的候选居所）",
            "same_code_two_descriptions": "源码逐字节相同、双描述（SAME-15/11 型）",
            "same_template_literal_diff": "同模板、canonical 相同、字面量不同（SAME-19/9 型）",
            "same_template_canonical_diff": "同模板（RLE）但 canonical 序列不同",
        },
    }
    (OUT_DIR / "Q2_POOL_RESCAN_MECHANICAL_V1.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT_DIR / "Q2_POOL_RESCAN_ADJUDICATION_SAMPLE_V1.json").write_text(
        json.dumps({"artifact": "Q2_POOL_RESCAN_ADJUDICATION_SAMPLE_V1",
                    "seed": SEED, "per_class_cap": SAMPLE_PER_CLASS,
                    "n_sampled": len(sample), "records": sample},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out["population"], ensure_ascii=False, indent=1))
    print("diff classes:", json.dumps(out["diff_template_class_distribution"],
                                      ensure_ascii=False))
    print("same classes:", json.dumps(out["same_template_class_distribution"],
                                      ensure_ascii=False))
    print("fidelity:", fidelity_rates)
    print("sample:", len(sample))


def iter_packet_pairs(pkt):
    """Yield (pair_id, {instruction_a, instruction_b}) from the verification
    packet (its records store the RAW instruction texts)."""
    for rec in pkt.get("pairs", []):
        pid = rec.get("id")
        sa = rec.get("side_a", {})
        sb = rec.get("side_b", {})
        if pid and sa.get("normalized_instruction") and sb.get("normalized_instruction"):
            yield pid, {"instruction_a": sa["normalized_instruction"],
                        "instruction_b": sb["normalized_instruction"]}


if __name__ == "__main__":
    main()
