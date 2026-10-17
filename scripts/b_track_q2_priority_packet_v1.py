#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B-track Q2 priority verification packet builder.

Materializes the three-way alignment (instruction x raw canonical chain x coarse
RLE labels) for the owner's priority verification queue from
Q2_OWNER_ADJUDICATION_V1.json, joining back to the frozen GEE pool
(04_DIAG_WORK/b1_gee_stage_train.jsonl, 128,447 rows, READ-ONLY).

Queue (owner order): V2-P0 source walkthrough = DIFF-6, DIFF-4, DIFF-5, DIFF-1,
DIFF-12, DIFF-19; V3 label-expressiveness checks = SAME-15, SAME-19, SAME-11,
SAME-9. Second-batch DIFF pairs are included with canonical chains so the next
round needs no pool re-scan.

Instrument lesson (Q2_OWNER_ADJUDICATION_V1.md section 3): RLE chains are
rendered with run-count compression plus an automatic chain diff, so a
one-quad difference (the DIFF-20 case) is impossible to miss.

Outputs (b_track_audit_v1/):
  Q2_PRIORITY_VERIFICATION_PACKET_V1.json  (full canonical chains)
  Q2_PRIORITY_VERIFICATION_PACKET_V1.md    (review sheet, truncated chains)

Deterministic; no sampling; no pool mutation.
"""
import difflib
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
POOL = REPO.parent / "04_DIAG_WORK/b1_gee_stage_train.jsonl"
ADJ = (REPO / ("docs/reports/route2_p0_contract/plan_pipeline_v1/"
               "planning_capability_audit_v1/diag50_v1/b_track_audit_v1/"
               "Q2_OWNER_ADJUDICATION_V1.json"))
MECH = ADJ.parent / "Q23_MECHANICAL_RESULTS_V1.json"
OUT_DIR = ADJ.parent

QUEUE_ORDER = [
    "DIFF-6", "DIFF-4", "DIFF-5", "DIFF-1", "DIFF-12", "DIFF-19",
    "SAME-15", "SAME-19", "SAME-11", "SAME-9",
]
SECOND_BATCH = ["DIFF-2", "DIFF-3", "DIFF-7", "DIFF-8", "DIFF-9", "DIFF-10",
                "DIFF-13", "DIFF-16"]
MAX_CHAINS_PER_SIDE = 3      # distinct canonical chains materialized per side
MD_CANON_CHARS = 1200        # canonical chain preview length in the MD sheet

ID_KEYS = ("source_row_id", "row_id", "source_id", "script", "id")


def norm_text(s):
    return re.sub(r"\s+", " ", s.strip().lower())


def canon_hash(s):
    return hashlib.sha256(re.sub(r"\s+", " ", s.strip()).encode()).hexdigest()[:16]


def row_id(r, idx):
    for k in ID_KEYS:
        if r.get(k):
            return str(r[k])
    return f"pool_index:{idx}"


def rle_runs(rle):
    """Compress consecutive identical labels into runs for display."""
    labels = rle.split(" -> ")
    runs, cur, n = [], None, 0
    for lb in labels:
        if lb == cur:
            n += 1
        else:
            if cur is not None:
                runs.append((cur, n))
            cur, n = lb, 1
    if cur is not None:
        runs.append((cur, n))
    return runs


def rle_render(rle):
    return " -> ".join(lb if n == 1 else f"{lb}x{n}" for lb, n in rle_runs(rle))


def side_record(instr, rle, matches, tmpl_support):
    chains, seen = [], set()
    for r, idx in matches:
        canon = (r.get("gee_canonical_chain") or "").strip()
        h = canon_hash(canon)
        if h in seen:
            continue
        seen.add(h)
        chains.append({
            "row_id": row_id(r, idx),
            "task_type": r.get("task_type") or "",
            "run_cap_applied": bool(r.get("run_cap_applied")),
            "canon_hash16": h,
            "canon_chars": len(canon),
            "canonical_chain": canon,
        })
        if len(chains) >= MAX_CHAINS_PER_SIDE:
            break
    return {
        "normalized_instruction": instr,
        "rle": rle,
        "rle_steps": len(rle.split(" -> ")),
        "rle_rendered_runs": rle_render(rle),
        "n_matching_rows": len(matches),
        "task_types": sorted({r.get("task_type") or "" for r, _ in matches}),
        "any_run_cap_applied": any(bool(r.get("run_cap_applied")) for r, _ in matches),
        "template_global_support_rows": tmpl_support,
        "n_distinct_canonical_in_pool": len(seen),
        "canonical_chains_materialized": chains,
    }


def main():
    adj = json.loads(ADJ.read_text(encoding="utf-8"))
    mech = json.loads(MECH.read_text(encoding="utf-8"))
    # verdicts/notes from the adjudication ledger; instructions/RLEs from the
    # mechanical results (SAME-N/DIFF-N order is identical in both files)
    pairs_by_id = {}
    for grp, prefix in (("same_template_pairs", "SAME"),
                        ("diff_template_pairs", "DIFF")):
        for i, mp in enumerate(mech["q2_sample_pairs"][grp], 1):
            pid = f"{prefix}-{i}"
            ap = next(x for x in adj["pairs"] if x["id"] == pid)
            pairs_by_id[pid] = {**mp, "id": pid, "group": ap["group"],
                                "verdict": ap["verdict"], "note": ap["note"]}
    wanted = QUEUE_ORDER + SECOND_BATCH
    missing = [p for p in wanted if p not in pairs_by_id]
    if missing:
        raise SystemExit(f"pair sources missing pairs: {missing}")

    # group sides by normalized instruction so the pool is scanned once
    sides = {}
    for pid in wanted:
        p = pairs_by_id[pid]
        for tag, key in (("a", "instruction_a"), ("b", "instruction_b")):
            sides.setdefault((norm_text(p[key]), p[f"rle_{tag}"]), []).append((pid, tag))

    matches = defaultdict(list)          # (norm_instr, rle) -> [(row, idx)]
    tmpl_support = Counter()             # rle -> global row count
    n_rows = 0
    print("scanning pool (read-only) ...", flush=True)
    with POOL.open(encoding="utf-8") as f:
        for idx, line in enumerate(f):
            r = json.loads(line)
            n_rows += 1
            rle = re.sub(r"\s+", " ", r.get("semantic_chain_rle", "").strip())
            tmpl_support[rle] += 1
            key = (norm_text(r.get("instruction", "")), rle)
            if key in sides and len(matches[key]) < 50:
                matches[key].append((r, idx))
    print(f"pool rows: {n_rows}", flush=True)

    unmatched = [k for k in sides if not matches.get(k)]
    if unmatched:
        raise SystemExit(f"sides with no pool match (unexpected): {unmatched[:4]} ...")

    packet_pairs, md = [], []
    md += ["# Q2 优先核验包 V1（指令 x 原始 canonical 链 x 粗标签 三对齐材料）", "",
           "- **日期**：2026-10-17；**来源**：`Q2_OWNER_ADJUDICATION_V1.json` 优先核验队列",
           f"- **池**：`04_DIAG_WORK/b1_gee_stage_train.jsonl`（{n_rows:,} 行，只读，未修改）",
           "- **渲染纪律**：RLE 以游程计数显示（`LABELxN`）；每对附自动链 diff——DIFF-20"
           " 教训（1 个重复块肉眼不可辨）自本包起不可能再现",
           "- **用途**：owner 逐步对照指令、原始 GEE API 序列与 30 类粗标签，判断结构差异"
           "来自真实分析逻辑、工作流抽取，还是标签体系。canonical 链在 JSON 中完整、在此处"
           f"截断至前 {MD_CANON_CHARS} 字符（总长已标注）", "",
           "## 机械预观察总表（canonical = API 名级序列，不含字面量）", "",
           "| 对 | 队列 | 粗链步数 A/B | 模板支持 A/B | 双侧 canonical 一致 |",
           "| --- | --- | --- | --- | --- |"]
    for rec in packet_pairs:
        md += [f"| {rec['id']} | {rec['queue']} | "
               f"{rec['side_a']['rle_steps']}/{rec['side_b']['rle_steps']} | "
               f"{rec['side_a']['template_global_support_rows']:,}/"
               f"{rec['side_b']['template_global_support_rows']:,} | "
               f"{'**一致**' if rec['sides_share_canonical_api_sequence'] else '不同'} |"]
    md += ["", "**预观察读法（登记人，供对照时参考，非结论）**：双侧 canonical 一致的对"
           "（含全部 V3 SAME 对）= 两行共享同一 API 调用序列，指令差异属描述层，核验重心"
           "转为'哪一侧描述忠实于源码'（字面量差异须读 script 源码）；canonical 不同的对"
           "（全部 DIFF 对）= 程序确实不同，核验重心转为'程序差异是否任务驱动'。", ""]

    for pid in QUEUE_ORDER + SECOND_BATCH:
        p = pairs_by_id[pid]
        rec = {"id": pid, "group": p["group"], "jaccard": p["jaccard"],
               "verdict": p["verdict"], "owner_note": p["note"],
               "queue": ("v2_p0_source_walkthrough" if pid in QUEUE_ORDER[:6]
                         else "v3_same_semantic_checks" if pid in QUEUE_ORDER[6:]
                         else "second_batch"),
               "side_a": None, "side_b": None}
        for tag in ("a", "b"):
            key = (norm_text(p[f"instruction_{tag}"]), p[f"rle_{tag}"])
            rec[f"side_{tag}"] = side_record(
                p[f"instruction_{tag}"], p[f"rle_{tag}"],
                matches[key], tmpl_support[p[f"rle_{tag}"]])
        # mechanical pre-observation: do both sides share the same API-name
        # sequence? (canonical chains carry NO literals — band names /
        # thresholds / target variables can differ invisibly)
        ha = {c["canon_hash16"] for c in rec["side_a"]["canonical_chains_materialized"]}
        hb = {c["canon_hash16"] for c in rec["side_b"]["canonical_chains_materialized"]}
        rec["sides_share_canonical_api_sequence"] = bool(ha & hb)
        rec["canonical_caveat"] = ("gee_canonical_chain 是 API 名级序列，不含字面量"
                                   "参数；波段名/阈值/目标变量等字面量差异在此层不可见，"
                                   "须读源程序（script 指针）确认")
        packet_pairs.append(rec)

        queue_label = {"v2_p0_source_walkthrough": "V2-P0 原始程序对照",
                       "v3_same_semantic_checks": "V3 标签表达力核验",
                       "second_batch": "第二批"}[rec["queue"]]
        md += [f"## {pid}  (J={p['jaccard']} / {p['verdict']} / {queue_label})", ""]
        md += [f"**owner 判读注记**：{p['note']}", ""]
        md += [f"**机械预观察**：双侧 canonical API 序列"
               f"{'一致（程序同构；字面量差异需读源码）' if rec['sides_share_canonical_api_sequence'] else '不同（程序确实不同）'}"
               f"；模板支持 A/B = {rec['side_a']['template_global_support_rows']:,}/"
               f"{rec['side_b']['template_global_support_rows']:,} 行", ""]
        for tag in ("a", "b"):
            s = rec[f"side_{tag}"]
            md += [f"### {pid} 臂 {tag.upper()}",
                   f"- 匹配池行：{s['n_matching_rows']}（canonical 形态 "
                   f"{s['n_distinct_canonical_in_pool']} 种，物化前 "
                   f"{MAX_CHAINS_PER_SIDE} 种）；task_type："
                   f"{', '.join(s['task_types']) or '∅'}；run_cap："
                   f"{s['any_run_cap_applied']}",
                   f"- 模板全局支持度：该 RLE 在池内出现 "
                   f"**{s['template_global_support_rows']:,} 行**",
                   f"- 粗链（{s['rle_steps']} 步，游程显示）：`{s['rle_rendered_runs']}`",
                   ""]
            for c in s["canonical_chains_materialized"]:
                md += [f"- **canonical**（{c['canon_chars']:,} 字符，sha16 "
                       f"{c['canon_hash16']}，row {c['row_id']}）：",
                       "```",
                       c["canonical_chain"][:MD_CANON_CHARS]
                       + ("…" if c["canon_chars"] > MD_CANON_CHARS else ""),
                       "```", ""]
        ra = rec["side_a"]["rle"].split(" -> ")
        rb = rec["side_b"]["rle"].split(" -> ")
        md += [f"### {pid} 粗链自动 diff（A→B，上下文 1）", "```"]
        md += list(difflib.unified_diff(ra, rb, lineterm="", n=1)) or ["(identical)"]
        md += ["```", "", "---", ""]

    out_json = {"artifact": "Q2_PRIORITY_VERIFICATION_PACKET_V1",
                "date": "2026-10-17",
                "pool": str(POOL), "pool_rows_scanned": n_rows,
                "read_only": True,
                "queue_order": QUEUE_ORDER, "second_batch": SECOND_BATCH,
                "max_chains_per_side": MAX_CHAINS_PER_SIDE,
                "adjudication_ref": "Q2_OWNER_ADJUDICATION_V1.json",
                "pairs": packet_pairs}
    (OUT_DIR / "Q2_PRIORITY_VERIFICATION_PACKET_V1.json").write_text(
        json.dumps(out_json, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT_DIR / "Q2_PRIORITY_VERIFICATION_PACKET_V1.md").write_text(
        "\n".join(md), encoding="utf-8")
    print(f"packet: {len(packet_pairs)} pairs -> "
          f"{OUT_DIR / 'Q2_PRIORITY_VERIFICATION_PACKET_V1.json'}")


if __name__ == "__main__":
    main()
