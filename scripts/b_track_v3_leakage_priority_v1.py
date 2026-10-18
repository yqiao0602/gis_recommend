#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the ordered leakage-priority list (1,504 relations).

Priority order (deterministic):
  Tier 1  deferred_cross   : high-confidence G1/D2 edge across V3 split
                             (all triage classes; 105 rows)
  Tier 2  pending_cross_A  : A_merge_candidate pending across V3 split
                             (1,399 rows)
Within a tier: strength desc, pattern, pair asc.

Input : B_TRACK_V3_HIGH_CONF_REVIEW_V1.json
Output: B_TRACK_V3_LEAKAGE_PRIORITY_V1.json
        B_TRACK_V3_LEAKAGE_PRIORITY_V1.csv
        B_TRACK_V3_LEAKAGE_PRIORITY_V1.md
"""
import csv
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
B = (REPO / "docs/reports/route2_p0_contract/plan_pipeline_v1/"
     "planning_capability_audit_v1/diag50_v1/b_track_audit_v1")
SRC = B / "B_TRACK_V3_HIGH_CONF_REVIEW_V1.json"


def main():
    review = json.loads(SRC.read_text(encoding="utf-8"))
    rows = review["relations"]
    tier1 = [r for r in rows if r["kind"] == "deferred" and r["v3_cross"]]
    tier2 = [r for r in rows if r["kind"] == "pending"
             and r["class"] == "A_merge_candidate"]
    for tier, sub in (("T1_deferred_cross", tier1), ("T2_pending_cross_A", tier2)):
        sub.sort(key=lambda r: (-r["strength"], r["pattern"],
                                r["pair"][0], r["pair"][1]))
    ordered = []
    for tier, sub in (("T1_deferred_cross", tier1), ("T2_pending_cross_A", tier2)):
        for r in sub:
            ev = r["evidence"]
            ordered.append({
                "priority_rank": len(ordered) + 1,
                "priority_tier": tier,
                "review_id": r["review_id"],
                "class": r["class"], "pattern": r["pattern"],
                "kind": r["kind"], "rule": r["rule"],
                "pair": r["pair"],
                "v3_splits": r["v3_splits"], "v2_splits": r["v2_splits"],
                "family_a": r["family_a"], "family_b": r["family_b"],
                "title_a": ev["title_a"], "title_b": ev["title_b"],
                "title_j": ev["title_j"], "body_j": ev["body_j"],
                "effective_targets": r["effective_targets"],
                "dataset_shared": ev["dataset_shared"],
                "asset_shared": ev["asset_shared"],
                "asset_j": ev["asset_j"],
                "chain_same": ev["chain_same"],
                "purpose_a": ev["purpose_a"], "purpose_b": ev["purpose_b"],
                "purpose_compatible": ev["purpose_compatible"],
                "task_type_a": ev["task_type_a"], "task_type_b": ev["task_type_b"],
                "task_type_same": ev["task_type_same"],
                "outputs_shared": ev["outputs_shared"],
                "strength": r["strength"],
            })
    out = {
        "artifact": "B_TRACK_V3_LEAKAGE_PRIORITY_V1", "date": "2026-10-18",
        "definition": "all deferred group edges crossing V3 split + all A pending crossing V3 split",
        "ordering": "tier asc (T1 deferred, T2 pending A); within tier strength desc, pattern, pair",
        "counts": {
            "total": len(ordered),
            "tier1_deferred_cross": len(tier1),
            "tier1_by_class": dict(Counter(r["class"] for r in tier1)),
            "tier2_pending_cross_A": len(tier2),
            "by_pattern": dict(Counter(r["pattern"] for r in ordered)),
            "by_tier_pattern": {f"{t}|{p}": n for (t, p), n in
                                Counter((r["priority_tier"], r["pattern"])
                                        for r in ordered).items()},
            "affected_components": len({x for r in ordered for x in r["pair"]}),
            "affected_families": len({f for r in ordered
                                      for f in (r["family_a"], r["family_b"]) if f}),
        },
        "note": "T1 includes 11 C_undetermined deferred edges; they remain in the "
                "leakage queue because the direct edge evidence crosses a split.",
        "relations": ordered,
    }
    (B / "B_TRACK_V3_LEAKAGE_PRIORITY_V1.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    cols = ["priority_rank", "priority_tier", "review_id", "class", "pattern",
            "kind", "rule", "v3_splits", "title_a", "title_b", "title_j",
            "body_j", "effective_targets", "dataset_shared", "asset_shared",
            "chain_same", "purpose_a", "purpose_b", "purpose_compatible",
            "task_type_a", "task_type_b", "task_type_same", "family_a",
            "family_b", "strength"]
    with (B / "B_TRACK_V3_LEAKAGE_PRIORITY_V1.csv").open(
            "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in ordered:
            w.writerow({k: ("|".join(map(str, r[k])) if isinstance(r[k], list)
                            else r[k]) for k in cols})
    # markdown summary
    lines = [
        "# V3 泄漏优先集 1,504 条（有序台账）",
        "",
        "- **定义**：跨 V3 split 的全部高置信截断组边（105）+ A_merge_candidate 中"
        "跨 V3 split 的 pending（1,399）。",
        "- **顺序**：T1 截断跨 split → T2 pending A；层内按 `strength` 降序，再按"
        " pattern、组件对升序；`priority_rank` 1–1,504。",
        "- **机器台账**：`B_TRACK_V3_LEAKAGE_PRIORITY_V1.json`；"
        "**表格**：`B_TRACK_V3_LEAKAGE_PRIORITY_V1.csv`（UTF-8 BOM，可直接打开）。",
        "- 每条保留 `review_id`，可回查 `B_TRACK_V3_HIGH_CONF_REVIEW_V1.json`。",
        "",
        "## 1. 构成",
        "",
        f"- T1 截断跨 split：**{len(tier1)}**（A 94 / C 11）",
        f"- T2 pending A 跨 split：**{len(tier2)}**",
        f"- 合计：**{len(ordered)}**；受影响组件 {out['counts']['affected_components']}，"
        f"族 {out['counts']['affected_families']}。",
        "",
        "> T1 中 11 条被分诊为 C 的边仍保留在泄漏队列：分类是“证据是否足够”，"
        "不影响“该边跨 split”这一事实。",
        "",
        "## 2. 模式分布",
        "",
        "| 模式 | 数量 |",
        "| --- | --- |",
    ]
    for p, n in sorted(out["counts"]["by_pattern"].items(), key=lambda x: -x[1]):
        lines.append(f"| `{p}` | {n} |")
    lines += ["", "## 3. 前 30 条（按 priority_rank）", "",
              "| rank | tier | review_id | pattern | split | title_a | title_b | T | B | O | AS |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in ordered[:30]:
        lines.append(
            f"| {r['priority_rank']} | {r['priority_tier']} | {r['review_id']} | "
            f"`{r['pattern']}` | {r['v3_splits'][0]}-{r['v3_splits'][1]} | "
            f"{r['title_a'][:55]} | {r['title_b'][:55]} | {r['title_j']} | "
            f"{r['body_j']} | {','.join(r['effective_targets'])} | "
            f"{len(r['asset_shared'])} |")
    lines += ["", "## 4. 使用方式", "",
              "1. 先按 `priority_rank` 从 1 开始复核；CSV 已含全部字段。",
              "2. 每条只允许三种裁定：合并进 V3.1 / 记录反证保持独立 / 保持 pending。",
              "3. 保持 pending 的跨 split 组件不得以正式评估状态进入冻结。",
              "4. 裁定结果按 `review_id` 回写；不得覆盖 V2/V3 历史。"]
    (B / "B_TRACK_V3_LEAKAGE_PRIORITY_V1.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(out["counts"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
