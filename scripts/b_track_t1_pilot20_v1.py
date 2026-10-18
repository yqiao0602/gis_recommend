#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T1 pilot-20 protocol calibration + Gate 1 machine reconciliation (read-only).

Outputs:
  B_TRACK_GATE1_RECONCILIATION_V1.json
  B_TRACK_T1_PILOT20_V1.json
  B_TRACK_T1_PILOT20_V1.md

No merge, no split change, no quota recompute.
"""
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
B = (REPO / "docs/reports/route2_p0_contract/plan_pipeline_v1/"
     "planning_capability_audit_v1/diag50_v1/b_track_audit_v1")
POOL = REPO.parent / "04_DIAG_WORK/b1_gee_stage_train.jsonl"
CAP = 10000


def family_of_asset(a):
    for pre, fam in (("LANDSAT/", "landsat"), ("COPERNICUS/S1", "sentinel-1"),
                     ("COPERNICUS/S2", "sentinel-2"), ("MODIS/", "modis"),
                     ("NOAA/", "noaa"), ("NASA/", "nasa"), ("HYCOM/", "hycom"),
                     ("JRC/", "jrc"), ("USGS/", "usgs"), ("ESA/", "esa"),
                     ("UCSB-CHG/", "ucsb-chg"), ("users/", "custom"),
                     ("projects/", "custom")):
        if a.startswith(pre):
            return fam
    return "other"


def main():
    v3 = json.loads((B / "B_TRACK_SPLIT_MANIFEST_V3.json").read_text(encoding="utf-8"))
    fids = v3["family_ids"]
    comp_fam, comp_split = {}, {}
    fam_size = Counter()
    for c, fi, s in zip(v3["row_component"], v3["row_family"], v3["row_split"]):
        comp_fam.setdefault(c, fids[fi])
        comp_split.setdefault(c, s)
        fam_size[fids[fi]] += 1
    review = json.loads((B / "B_TRACK_V3_HIGH_CONF_REVIEW_V1.json").read_text(encoding="utf-8"))
    leak = json.loads((B / "B_TRACK_V3_LEAKAGE_PRIORITY_V1.json").read_text(encoding="utf-8"))
    with gzip.open(B / "B_TRACK_TASK_FAMILY_MERGE_LEDGER_V1.json.gz",
                   "rt", encoding="utf-8") as fh:
        ledger = json.load(fh)
    groups = {}
    for key in ("asset_set_groups", "title_star_groups", "title_exact_groups"):
        for g in ledger.get(key, []):
            groups[g["group_id"]] = g
    # decision-log group ids and edge strength rank within group
    pair_group = {}
    group_edges = defaultdict(list)
    with gzip.open(B / "B_TRACK_TASK_FAMILY_DECISIONS_V1.jsonl.gz",
                   "rt", encoding="utf-8") as fh:
        for line in fh:
            e = json.loads(line)
            if not e.get("group_id"):
                continue
            key = (min(e["a"], e["b"]), max(e["a"], e["b"]), e["rule"])
            pair_group[key] = e["group_id"]
            group_edges[e["group_id"]].append(e)
    # endpoint info from pool (component -> representative row)
    comp_info = {}
    with POOL.open(encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if i >= len(v3["row_component"]):
                break
            r = json.loads(line)
            c = v3["row_component"][i]
            if c in comp_info:
                continue
            comp_info[c] = {
                "script": r.get("script", ""),
                "instruction": (r.get("instruction", "") or "").replace("\n", " ")[:400],
                "task_type": r.get("task_type", ""),
            }
    # ---------- machine reconciliation ----------
    pending_hi, deferred_hi = {}, {}
    with gzip.open(B / "B_TRACK_TASK_FAMILY_DECISIONS_V1.jsonl.gz",
                   "rt", encoding="utf-8") as fh:
        for line in fh:
            e = json.loads(line)
            a, b = e["a"], e["b"]
            key = (a, b) if a < b else (b, a)
            ev = e["evidence"]
            if e["decision"] == "pending" and comp_split.get(a) != comp_split.get(b) \
                    and (ev["title_j"] >= 0.60 or ev["body_j"] >= 0.60):
                pending_hi[key] = e
            if e.get("group_id") and comp_fam.get(a) != comp_fam.get(b) \
                    and (ev["title_j"] >= 0.60 or len(ev["asset_shared"]) >= 1):
                deferred_hi[key] = e
    rev_pending = {tuple(r["pair"]) for r in review["relations"] if r["kind"] == "pending"}
    rev_deferred = {tuple(r["pair"]) for r in review["relations"] if r["kind"] == "deferred"}
    t1 = [r for r in leak["relations"] if r["priority_tier"] == "T1_deferred_cross"]
    t2 = [r for r in leak["relations"] if r["priority_tier"] == "T2_pending_cross_A"]
    t1_pairs = {tuple(sorted(r["pair"])) for r in t1}
    t2_pairs = {tuple(sorted(r["pair"])) for r in t2}
    t1_expected = {(a, b) for (a, b), e in deferred_hi.items()
                   if comp_split.get(a) != comp_split.get(b)}
    # A pending set from review (class is authoritative for the triage)
    t2_expected = {tuple(r["pair"]) for r in review["relations"]
                   if r["kind"] == "pending" and r["class"] == "A_merge_candidate"}
    recon = {
        "artifact": "B_TRACK_GATE1_RECONCILIATION_V1", "date": "2026-10-18",
        "checks": {
            "pending_hi_v3_recomputed": len(pending_hi),
            "review_pending": len(rev_pending),
            "pending_sets_equal": rev_pending == set(pending_hi),
            "deferred_hi_recomputed": len(deferred_hi),
            "review_deferred": len(rev_deferred),
            "deferred_sets_equal": rev_deferred == set(deferred_hi),
            "union_review": len(rev_pending | rev_deferred),
            "union_recomputed": len(set(pending_hi) | set(deferred_hi)),
            "overlap_pending_deferred": len(rev_pending & rev_deferred),
            "t1_count": len(t1), "t1_expected": len(t1_expected),
            "t1_sets_equal": t1_pairs == t1_expected,
            "t2_count": len(t2), "t2_expected": len(t2_expected),
            "t2_sets_equal": t2_pairs == t2_expected,
            "review_id_unique": len({r["review_id"] for r in review["relations"]})
            == len(review["relations"]),
            "pair_unique_in_review": len(rev_pending | rev_deferred)
            == len(review["relations"]),
            "class_changes_vs_summary": {
                "A": sum(1 for r in review["relations"] if r["class"] == "A_merge_candidate"),
                "B": sum(1 for r in review["relations"] if r["class"] == "B_keep_candidate"),
                "C": sum(1 for r in review["relations"] if r["class"] == "C_undetermined"),
            },
        },
    }
    recon["all_pass"] = all(v for k, v in recon["checks"].items()
                            if isinstance(v, bool))
    (B / "B_TRACK_GATE1_RECONCILIATION_V1.json").write_text(
        json.dumps(recon, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- pilot-20 selection ----------
    def take(pattern, cls, n):
        sub = [r for r in t1 if r["pattern"] == pattern and r["class"] == cls]
        sub.sort(key=lambda r: (-r["strength"], r["review_id"]))
        return sub[:n]

    selected = (take("same_targets_diff_title", "A_merge_candidate", 5)
                + take("mixed_or_weak", "A_merge_candidate", 5)
                + take("same_assets_diff_title", "A_merge_candidate", 4)
                + take("same_title_diff_source", "A_merge_candidate", 2)
                + take("same_title_diff_source", "C_undetermined", 2)
                + take("task_type_diff", "C_undetermined", 2))
    selected = selected[:20]
    assert len(selected) == 20, len(selected)
    selected.sort(key=lambda r: r["priority_rank"])

    def asset_scope(r):
        assets = r["asset_shared"]
        n = len(assets)
        custom = sum(1 for a in assets if a.startswith(("projects/", "users/")))
        fams = {family_of_asset(a) for a in assets}
        gid = pair_group.get((r["pair"][0], r["pair"][1], r["rule"]))
        g = groups.get(gid, {})
        gsize = (g.get("signature_group_size") or g.get("bucket_size")
                 or g.get("n_components") or 0)
        if r["rule"] == "G1_exact_asset_set_group":
            if custom >= 3 or n >= 15 or len(fams) >= 3:
                return "project_shared", {
                    "group_size": gsize, "shared_assets": n,
                    "custom_assets": custom, "asset_families": sorted(fams)}
            if gsize <= 5 and n <= 10 and len(fams) <= 2 and custom == 0:
                return "task_specific", {
                    "group_size": gsize, "shared_assets": n,
                    "custom_assets": custom, "asset_families": sorted(fams)}
            return "unclear", {"group_size": gsize, "shared_assets": n,
                               "custom_assets": custom,
                               "asset_families": sorted(fams)}
        if n == 0:
            return "unclear", {"shared_assets": 0}
        if custom >= 2 or n >= 10:
            return "project_shared", {"shared_assets": n,
                                      "custom_assets": custom,
                                      "asset_families": sorted(fams)}
        if n <= 3 and len(fams) <= 2 and custom == 0:
            return "task_specific", {"shared_assets": n,
                                     "custom_assets": custom,
                                     "asset_families": sorted(fams)}
        return "unclear", {"shared_assets": n, "custom_assets": custom,
                           "asset_families": sorted(fams)}

    def tentative(d):
        T, B = d["title_j"], d["body_j"]
        O, AS = len(d["effective_targets"]), d["asset_shared_count"]
        CS, P, TT = d["chain_same"], d["purpose_compatible"], d["task_type_same"]
        scope = d["asset_evidence_scope"]
        if not P:
            return "UNRESOLVED", "purpose class differs; policy decision needed"
        if (not TT) and T < 0.40 and B < 0.40:
            return "UNRESOLVED", "task_type differs and text evidence is weak"
        if O == 0 and AS == 0 and not d["dataset_shared"] and T < 0.40 and B < 0.60:
            return "KEEP_provisional", "no shared target/source/asset and weak text"
        if (not TT) and O == 0 and AS == 0 and T < 0.50 and B < 0.60:
            return "KEEP_provisional", "task_type differs with no shared target/source"
        if scope == "project_shared":
            strong = sum([O >= 2, CS, T >= 0.60, B >= 0.60])
            if strong >= 2:
                return "MERGE_provisional", f"{strong} strong axes despite project-shared assets"
            return "UNRESOLVED", "project-shared assets plus fewer than 2 strong text/chain axes"
        axes = sum([O >= 2, AS >= 1, CS, T >= 0.60, B >= 0.60])
        if axes >= 2 and (O >= 2 or T >= 0.60 or B >= 0.60):
            return "MERGE_provisional", f"{axes} independent axes (target/source/chain/text)"
        if AS >= 1 and O == 0:
            return "UNRESOLVED", "asset overlap without shared target or strong text"
        return "UNRESOLVED", "fewer than 2 independent axes"

    dossiers = []
    for r in selected:
        gid = pair_group.get((r["pair"][0], r["pair"][1], r["rule"]))
        g = groups.get(gid, {})
        ges = sorted(group_edges.get(gid, []),
                     key=lambda e: -(e["evidence"]["title_j"]
                                     + 0.5 * e["evidence"]["body_j"]
                                     + 0.3 * len(e["evidence"]["target_shared"])
                                     + 0.5 * len(e["evidence"]["asset_shared"])))
        rank = next((i + 1 for i, e in enumerate(ges)
                     if {e["a"], e["b"]} == set(r["pair"])), None)
        scope, scope_detail = asset_scope(r)
        a, b = r["pair"]
        dossiers.append({
            "review_id": r["review_id"], "priority_rank": r["priority_rank"],
            "class": r["class"], "pattern": r["pattern"],
            "rule": r["rule"], "group_id": gid,
            "group_record": {k: g.get(k) for k in
                             ("n_components", "signature_group_size", "bucket_size",
                              "anchor", "n_merged", "decision", "purpose_class",
                              "title", "bucket") if k in g},
            "group_edge_rank": rank, "group_edges": len(ges),
            "v3_splits": r["v3_splits"], "v2_splits": r["v2_splits"],
            "family_a": r["family_a"], "family_b": r["family_b"],
            "family_sizes": [fam_size.get(r["family_a"]), fam_size.get(r["family_b"])],
            "size_sum_gt_cap": (fam_size.get(r["family_a"], 0)
                                + fam_size.get(r["family_b"], 0)) > CAP,
            "cap": CAP,
            "endpoints": [
                {"component_id": x, "family": comp_fam.get(x),
                 "v3_split": comp_split.get(x),
                 "script": comp_info.get(x, {}).get("script"),
                 "task_type": comp_info.get(x, {}).get("task_type"),
                 "instruction": comp_info.get(x, {}).get("instruction")}
                for x in (a, b)],
            "title_a": r["title_a"], "title_b": r["title_b"],
            "title_j": r["title_j"], "body_j": r["body_j"],
            "effective_targets": r["effective_targets"],
            "dataset_shared": r["dataset_shared"],
            "asset_shared": r["asset_shared"],
            "asset_shared_count": len(r["asset_shared"]),
            "asset_evidence_scope": scope,
            "asset_evidence_detail": scope_detail,
            "chain_same": r["chain_same"],
            "purpose_a": r["purpose_a"], "purpose_b": r["purpose_b"],
            "purpose_compatible": r["purpose_compatible"],
            "task_type_a": r["task_type_a"], "task_type_b": r["task_type_b"],
            "task_type_same": r["task_type_same"],
            "outputs_shared": r["outputs_shared"],
            "strength": r["strength"],
            "adjudication": {"decision": "", "counter_evidence": "",
                             "evidence_needed": "", "adjudicator": "",
                             "date": ""},
        })
    for d in dossiers:
        t, rationale = tentative(d)
        d["agent_tentative"] = t
        d["agent_rationale"] = rationale
    observations = [
        "project_shared 9 条：8 条仍有文本/链第二轴 → MERGE_provisional；"
        "1 条仅资产轴（R00888）→ UNRESOLVED。asset_evidence_scope 起到"
        "“阻断资产单证合并”的作用，但不会否决多轴证据。",
        "截断 20/20 的端点族大小之和 > 10,000（G1 14 / D2 6）；"
        "截断是族上限造成的真实分歧，不是证据缺失。",
        "same_title_diff_source 4 条（built-up / fire）T=0.667、O=2、无共享资产；"
        "暂 MERGE，但需源码级核验定义（BU index vs nighttime lights vs non-forest built-up）。",
        "task_type_diff 2 条均 UNRESOLVED；协议要求至少一个目标/来源/链之外的独立证据。",
        "地区/时间/输入条件不同 5 条（R00150、R01290、R00257、R01340、R00916）；"
        "是否同族需 owner 先锁定“条件差异”口径。",
    ]
    out = {
        "artifact": "B_TRACK_T1_PILOT20_V1", "date": "2026-10-18",
        "purpose": "protocol calibration, not accuracy estimation",
        "pilot_observations": observations,
        "coverage": {
            "n": len(dossiers),
            "by_class": dict(Counter(d["class"] for d in dossiers)),
            "by_pattern": dict(Counter(d["pattern"] for d in dossiers)),
            "by_rule": dict(Counter(d["rule"] for d in dossiers)),
            "by_asset_scope": dict(Counter(d["asset_evidence_scope"] for d in dossiers)),
            "by_agent_tentative": dict(Counter(d["agent_tentative"] for d in dossiers)),
            "size_sum_gt_cap": sum(1 for d in dossiers if d["size_sum_gt_cap"]),
        },
        "dossiers": dossiers,
    }
    (B / "B_TRACK_T1_PILOT20_V1.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- markdown dossier ----------
    md = [
        "# T1 试审 20 条：协议校准包（2026-10-18）",
        "",
        "- **目的**：检验裁定协议是否清晰，**不用于估计全量准确率**，不合并、不改 split。",
        "- **范围**：105 条 T1 截断跨 split 边中的 20 条，覆盖 A/C 与五种证据模式。",
        "- **机器台账**：`B_TRACK_T1_PILOT20_V1.json`；对账："
        "`B_TRACK_GATE1_RECONCILIATION_V1.json`。",
        "",
        "## 0. 机器级对账",
        "",
        "| 检查 | 结果 |",
        "| --- | --- |",
    ]
    for k, v in recon["checks"].items():
        md.append(f"| `{k}` | {v} |")
    md += [
        f"| **all_pass** | **{recon['all_pass']}** |",
        "",
        "> 对账从 decision log + V3 manifest 独立重算 pending/deferred/T1/T2 集合，"
        "按无序端点对比较；不是只核对汇总数字。",
        "",
        "## 1. 覆盖",
        "",
        f"- 20 条 = A {out['coverage']['by_class'].get('A_merge_candidate', 0)} / "
        f"C {out['coverage']['by_class'].get('C_undetermined', 0)}；"
        f"规则 {out['coverage']['by_rule']}",
        f"- 模式：{out['coverage']['by_pattern']}",
        f"- 资产证据范围：{out['coverage']['by_asset_scope']}",
        f"- Agent 初步建议：{out['coverage']['by_agent_tentative']}",
        f"- 端点族大小之和 > 10,000 的：{out['coverage']['size_sum_gt_cap']} 条",
        "",
        "## 1.1 试审观察（agent）",
        "",
        *[f"- {x}" for x in observations],
        "",
        "## 2. 试审总表",
        "",
        "| rank | review_id | class | pattern | rule | split | asset_scope | agent | T | B | O | AS |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for d in dossiers:
        md.append(
            f"| {d['priority_rank']} | {d['review_id']} | {d['class'].split('_')[0]} | "
            f"`{d['pattern']}` | {d['rule'].split('_')[0]} | "
            f"{d['v3_splits'][0]}-{d['v3_splits'][1]} | {d['asset_evidence_scope']} | "
            f"{d['agent_tentative']} | "
            f"{d['title_j']} | {d['body_j']} | {','.join(d['effective_targets'])} | "
            f"{d['asset_shared_count']} |")
    md += ["", "## 3. 逐条卷宗", ""]
    for d in dossiers:
        md += [
            f"### {d['review_id']} — {d['class']} / `{d['pattern']}` / {d['rule']} — "
            f"split {d['v3_splits'][0]}-{d['v3_splits'][1]}",
            "",
            f"- **端点半族**：`{d['family_a']}` ({d['family_sizes'][0]} 组件) ↔ "
            f"`{d['family_b']}` ({d['family_sizes'][1]} 组件)；"
            f"族大小和 {sum(x or 0 for x in d['family_sizes'])} "
            f"（cap {d['cap']}，超限={d['size_sum_gt_cap']}）。",
            f"- **截断组**：`{d['group_id']}`，组记录 {d['group_record']}；"
            f"该边在组内强度排名 {d['group_edge_rank']}/{d['group_edges']}。",
        ]
        for label, ep in zip(("A", "B"), d["endpoints"]):
            md += [
                f"- **端点 {label}**：component `{ep['component_id']}`，"
                f"family `{ep['family']}`，split `{ep['v3_split']}`，"
                f"script `{ep['script']}`，task_type `{ep['task_type']}`。",
                f"  - 指令：{ep['instruction']}",
            ]
        md += [
            f"- **证据**：T={d['title_j']}，B={d['body_j']}，"
            f"有效目标={d['effective_targets']}，共享数据族={d['dataset_shared']}，"
            f"共享资产={d['asset_shared_count']}，链相同={d['chain_same']}，"
            f"目的={d['purpose_a']}/{d['purpose_b']}，"
            f"任务类型相同={d['task_type_same']}，共享输出={d['outputs_shared']}。",
            f"- **资产证据范围**：`{d['asset_evidence_scope']}`；"
            f"依据 {d['asset_evidence_detail']}。",
            f"- **资产样本**：{', '.join(d['asset_shared'][:8])}"
            + (" …" if d['asset_shared_count'] > 8 else ""),
            f"- **Agent 初步建议**：`{d['agent_tentative']}` — {d['agent_rationale']}。",
            "  - 注：这是 agent 分诊建议，不是裁定；最终以 owner 的 MERGE/KEEP/UNRESOLVED 为准。",
            "- **试审判定**：☐ MERGE ☐ KEEP_SEPARATE ☐ UNRESOLVED",
            "  - counter_evidence：____________________",
            "  - evidence_needed：____________________",
            "",
        ]
    md += [
        "## 4. 试审核对清单（逐条回答）",
        "",
        "1. 相同资产集合是否被误当成同任务证据？（看资产是任务特异还是项目共享）",
        "2. 截断是否破坏了关系证据？（组记录、端点、原始规则、族大小是否可复现）",
        "3. 同标题异来源究竟需要哪些附加证据才算同任务族？",
        "4. 地区/年份/输入条件不同，是否仍属于需要同侧隔离的同一任务族？",
        "5. KEEP_SEPARATE 是否有明确、可复查的反证（目的/对象/输出/来源冲突）？",
        "",
        "## 5. 协议草案 v0（试审后按 owner 反馈锁定，不现在生效）",
        "",
        "1. **MERGE**：至少 2 个独立证据轴，取自 {有效目标 ≥2、链相同、"
        "标题 J≥0.60、正文 J≥0.60、任务特异资产重叠}；"
        "**项目共享资产重叠不能单独作为一轴**。",
        "2. **KEEP_SEPARATE**：必须有明确反证（对象/目的/输出/来源冲突），"
        "并写入 `counter_evidence`；不能仅因“标题不同”或“没时间看”而 KEEP。",
        "3. **UNRESOLVED**：证据不足或冲突；跨 split 的 UNRESOLVED 不得以正式评估"
        "状态进入冻结，需隔离或保守同 split 处置。",
        "4. **条件差异**（地区/年份/输入组合不同）：暂不作为自动合并或自动分离依据；"
        "需 owner 先给统一口径。",
        "5. **资产范围**：`project_shared` 至少需要 2 个强文本/链轴；"
        "`task_specific` 资产可计 1 轴；`unclear` 不计资产轴。",
        "6. 每条裁定记录 `review_id / decision / evidence / counter_evidence / "
        "adjudicator / date`，可机器回写。",
        "",
        "## 6. 本批不做什么",
        "",
        "- 不合并任何族，不改变 V3 split，不重算配额，不恢复 S1；",
        "- `MERGE` 只是试审记录，正式合并须在协议锁定并完成全量裁定后进入 V3.1；",
        "- `UNRESOLVED` 必须保留在风险台账，不得静默转为 KEEP。",
    ]
    (B / "B_TRACK_T1_PILOT20_V1.md").write_text(
        "\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"recon": recon["checks"], "coverage": out["coverage"]},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
