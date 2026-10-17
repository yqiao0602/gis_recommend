#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A1 full-evidence adjudication packet (owner ruling 2026-10-18:
A1_OWNER_ADJUDICATION_V1.md - the 52-pair review packet lacked full task
requirements, full candidate sets and both card versions; directional screening
was possible but final four-metric counts need complete evidence).

For each of the 52 changed pairs this materializes:
  - full task text + step definition (name/purpose/input/output)
  - full Top-10 candidate list
  - BOTH card versions for every changed oid; single (identical) card for
    unchanged candidates
  - BOTH arms' complete decision sections (no truncation)
  - the owner's initial-review-V1 tendency (status=initial_not_gold)
  - orthogonal ledger fields per arm: decision_quality (pending) +
    output_validity (preliminary from the mechanical class, finalized by owner)

Written through the a1_short junction (MAX_PATH-safe).
Output: a1_v1/A1_FULL_EVIDENCE_PACKET_V1/{INDEX.md, LEDGER_V1.json, P*/....md}
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from dx_common import PCA2  # noqa: E402
from diag50_b3_build_pack_v1 import full_card  # noqa: E402

SHORT_BASE = REPO.parent  # Algorithm_classification/
A1 = SHORT_BASE / "a1_short"          # junction to .../dx50_full_v1/a1_v1
CTRL_RUNS = SHORT_BASE / "dx50_short" / "runs"
EXP_RUNS = SHORT_BASE / "_a1_work" / "runs_local"
OUT = A1 / "A1_FULL_EVIDENCE_PACKET_V1"

# owner initial review V1 (2026-10-18; status=initial_not_gold)
# fields: batch, exp_quality (tendency for experiment arm), note, checks
INITIAL = {
 "PCA2-T-009#S3": ("P1", "wrong_selection_tendency",
   "统计波段变化≠可靠计算指定植被指数；需核对实际输出与表达式能力",
   ["saga:multibandvariation 实际输出与表达式能力"]),
 "PCA2-T-009#S6": ("P1", "correct_selection_tendency",
   "训练矢量分类器与训练 CART 任务方向一致；最有价值的正向证据候选",
   ["卡面是否足以证明算法选择及参数配置"]),
 "PCA2-T-042#S1": ("P1", None, "NODEC 无可审查完整决策，暂不计入弃权指标", []),
 "PCA2-T-056#S5": ("P1", None, "输出不完整，暂不计入", []),
 "PCA2-T-056#S6": ("P1", "correct_selection_tendency",
   "预训练 RF 应用于栅格与任务目标一致", ["模型文件输入和参数语义"]),
 "PCA2-T-083#S6": ("P1", None, "输出不完整，暂不计入", []),
 "PCA2-T-083#S7": ("P1", "both_possibly_correct",
   "算子替换（SAGA 分类→OTB 分类）≠收益；按决策质量评分",
   ["模型格式、输入数据和输出要求"]),
 "PCA2-T-084#S2": ("P1", "reasonable_abstention_tendency",
   "连续干旱指数阈值重分类需明确重分类能力", []),
 "PCA2-T-084#S5": ("P1", None, "无完整判定，暂不计入", []),
 "PCA2-T-090#S4": ("P1", "wrong_selection",
   "OOC 越选按预注册口径判错（不再归 POS）", []),
 "PCA2-T-092#S9": ("P1", "reasonable_abstention_tendency",
   "平滑分类图与生成混淆矩阵是两个功能；单候选无法覆盖全部要求时弃权合理", []),
 "PCA2-T-001#S3": ("P3", "correct_selection_tendency",
   "多时相影像堆叠与任务目的相符", ["是否要求逐像元统计而非仅拼接波段"]),
 "PCA2-T-001#S4": ("P3", None,
   "输出不完整；对照合理弃权与实验无判定必须分开", []),
 "PCA2-T-001#S5": ("P3", "reasonable_abstention_tendency",
   "逐像元中位数合成需明确跨影像统计能力", []),
 "PCA2-T-001#S6": ("P3", "reasonable_abstention_tendency",
   "暂判合理弃权；输出格式化/资产交付未必是镶嵌功能",
   ["结合实际步骤目标确认"]),
 "PCA2-T-025#S5": ("P3", "correct_selection_tendency",
   "min=-25 max=5 线性拉伸与描述匹配", []),
 "PCA2-T-046#S4": ("P3", None, "无完整结论，暂不计入", []),
 "PCA2-T-046#S5": ("P3", "correct_selection_tendency",
   "合并多矢量集合方向合理",
   ["输入是否同类要素集合", "拼接算子输出语义"]),
 "PCA2-T-056#S3": ("P3", "partial_match_pending",
   "镶嵌≠波段堆叠；若目标是组合多波段影像仅靠镶嵌可能不满足", []),
 "PCA2-T-060#S1": ("P3", None, "输出不完整，暂不计入", []),
 "PCA2-T-062#S4": ("P3", None, "输出不完整，暂不计入", []),
 "PCA2-T-073#S1": ("P3", None, "输出不完整，暂不计入", []),
 "PCA2-T-079#S5": ("P3", "reasonable_abstention_tendency",
   "同心环≠逐要素可变缓冲距离", []),
 "PCA2-T-086#S4": ("P3", None, "输出不完整，暂不计入", []),
 "PCA2-T-089#S5": ("P3", None, "输出不完整，暂不计入", []),
 "PCA2-T-092#S5": ("P3", None, "输出不完整，暂不计入", []),
 "PCA2-T-003#S2": ("P4", "correct_selection_tendency",
   "前提=传感器辐射定标且输入元数据/校准参数满足", []),
 "PCA2-T-005#S3": ("P4", "reasonable_abstention_tendency",
   "二值云掩膜≠云量比例统计", []),
 "PCA2-T-005#S5": ("P4", "correct_selection_retained",
   "选择未变非新增收益；确认可执行性未变", []),
 "PCA2-T-012#S3": ("P4", "reasonable_abstention_tendency",
   "多时相栅格均值需跨影像统计能力", []),
 "PCA2-T-021#S4": ("P4", None, "暂不计入", []),
 "PCA2-T-022#S6": ("P4", "conditional_correct",
   "R/G/B 三独立栅格合成 RGB=匹配；从多波段提取=不匹配", []),
 "PCA2-T-025#S4": ("P4", "correct_selection_tendency",
   "确认多栅格统计与 MEAN 输出结构一致", []),
 "PCA2-T-026#S4": ("P4", None,
   "对照臂 native:rasterize 的'合并多栅格'描述本身待复核", []),
 "PCA2-T-032#S2": ("P4", "conditional_correct",
   "仅辐射定标=可判正确；明确要求含大气校正=不足", []),
 "PCA2-T-033#S1": ("P4", "correct_selection_tendency",
   "波段索引重排/选取可能满足波段提取",
   ["参数是否支持目标输出形式"]),
 "PCA2-T-052#S2": ("P4", None, "若候选确无栅格转面工具则弃权合理", []),
 "PCA2-T-056#S2": ("P4", "reasonable_abstention_tendency",
   "摘录证据不足以支持中位数合成", []),
 "PCA2-T-056#S4": ("P4", "reasonable_abstention_tendency",
   "分区统计/采样能力待确认", []),
 "PCA2-T-057#S4": ("P4", "conditional_correct",
   "确认 MSE 输出与双滤波结果输入", []),
 "PCA2-T-068#S4": ("P4", "reasonable_abstention_tendency",
   "按公园多边形统计类别像元数需分区统计能力", []),
 "PCA2-T-068#S6": ("P4", "correct_selection_tendency",
   "前提=矢量含分区标识+损失面积字段且聚合表达式正确", []),
 "PCA2-T-070#S1": ("P4", "conditional_correct",
   "重采样≠裁剪；确认目标范围参数支持 ROI", []),
 "PCA2-T-079#S3": ("P4", None, "多级同心缓冲≠单一可变缓冲；弃权可能合理", []),
 "PCA2-T-080#S4": ("P4", None, "弃权可能合理；核验通用栅格计算候选", []),
 "PCA2-T-081#S5": ("P4", "reasonable_abstention_tendency",
   "掩膜+DEM 条件筛选需候选可表达", []),
 "PCA2-T-084#S4": ("P4", "reasonable_abstention_tendency",
   "候选与气候分类输入不匹配（按摘录）", []),
 "PCA2-T-086#S5": ("P4", None, "输出不完整，暂不计入", []),
 "PCA2-T-089#S4": ("P4", None,
   "形态学滤波是合理方向；实验臂输出无法确认最终选择", []),
 "PCA2-T-092#S2": ("P4", None,
   "saga:clouddetection 适用性需按实际输出核对，不能凭名称", []),
 "PCA2-T-098#S1": ("P4", None, "暂不计入", []),
 "PCA2-T-098#S6": ("P4", None, "低通滤波可能合理；无最终结论可审", []),
}

PRIORITY_FIVE = ["PCA2-T-009#S6", "PCA2-T-001#S3", "PCA2-T-025#S5",
                 "PCA2-T-033#S1", "PCA2-T-068#S6"]


def load_profile_path(p):
    d = json.loads(Path(p).read_text(encoding="utf-8"))
    return {k: v for k, v in d.items() if k != "_meta"}


def decision_text(raw):
    raw = raw or ""
    if "</think>" in raw:
        return raw.split("</think>", 1)[1].strip()
    return "[no closed think - full raw]\n" + raw.strip()


def validity_from_class(cls):
    return ("valid_preliminary" if cls in ("POS", "OOC", "ABST")
            else "no_decision_preliminary")


def main():
    prof4 = load_profile_path(REPO / "route2_training/profile/"
                              "qgis_operator_capability_profile_v0_4.json")
    prof5 = load_profile_path(REPO / "route2_training/profile/"
                              "qgis_operator_capability_profile_v0_5.json")
    results = json.loads((A1 / "A1_PAIRED_RESULTS_V1.json").read_text(
        encoding="utf-8"))
    affected = {r["step_key"]: r for r in json.loads(
        (A1 / "A1_AFFECTED_SET_V1.json").read_text(encoding="utf-8")
    )["affected_steps"]}
    tasks = {}
    for line in (PCA2 / "pca2_taskset_100.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        tasks[r["pid"]] = r["instruction"]

    OUT.mkdir(parents=True, exist_ok=True)
    ledger = []
    order = {"P1": 0, "P3": 1, "P4": 2}

    def pair_rows():
        rows = []
        for p in results["pairs"]:
            key = p["step_key"]
            if p["cls_control"] == p["cls_experiment"] and not p["sel_changed"]:
                continue
            rows.append(p)
        rows.sort(key=lambda p: (order.get(
            INITIAL.get(p["step_key"], ("P4",))[0], 3), p["step_key"]))
        return rows

    for p in pair_rows():
        key = p["step_key"]
        tid, snum = key.split("#S")
        snum = int(snum)
        batch, exp_q, note, checks = INITIAL.get(
            key, ("P4", None, "(owner 初判未覆盖)", []))
        s0 = json.loads((CTRL_RUNS / tid / "S0" / "parsed.json")
                        .read_text(encoding="utf-8"))
        st = next(s for s in s0["steps"] if s["num"] == snum)
        retr = {x["step"]: x for x in json.loads(
            (CTRL_RUNS / tid / "S1" / "retrieval.json").read_text(
                encoding="utf-8")).get("steps", [])}
        oids = [c["operator_id"] for c in retr[snum]["top10"]]
        changed = set(affected[key]["changed_oids"])

        card_blocks = []
        for o in oids:
            c5 = full_card(o, prof5)[0]
            if o in changed:
                c4 = full_card(o, prof4)[0]
                card_blocks.append(f"#### {o} — v0_4 卡（对照臂所见）\n```\n{c4}\n```")
                card_blocks.append(f"#### {o} — v0_5 卡（实验臂所见）\n```\n{c5}\n```")
            else:
                card_blocks.append(f"#### {o} — 双臂相同（v0_5 版）\n```\n{c5}\n```")

        craw = (CTRL_RUNS / tid / "S2" / f"S{snum}" / "raw_output.txt"
                ).read_text(encoding="utf-8")
        eraw = (EXP_RUNS / tid / "S2" / f"S{snum}" / "raw_output.txt"
                ).read_text(encoding="utf-8")

        init = INITIAL.get(key)
        entry = {
            "step_key": key, "batch": batch,
            "mechanical": {"control": p["cls_control"],
                           "experiment": p["cls_experiment"]},
            "selections": {"control": p["sel_control"],
                           "experiment": p["sel_experiment"]},
            "changed_oids": sorted(changed),
            "owner_initial_v1": {
                "status": "initial_not_gold",
                "experiment_decision_quality_tendency": exp_q,
                "note": note,
                "evidence_checks": checks,
            },
            "ledger_fields_pending_owner": {
                "decision_quality": {"control": None, "experiment": None},
                "output_validity": {"control": validity_from_class(p["cls_control"]),
                                    "experiment": validity_from_class(p["cls_experiment"])},
                "final_note": None, "confidence": None,
            },
            "sel_contains_unverified_exp": p["sel_contains_unverified_exp"],
        }
        ledger.append(entry)

        priority_mark = " ★优先核验" if key in PRIORITY_FIVE else ""
        md = [f"# [{batch}] {key}{priority_mark}", "",
              f"- 机械判定：对照 `{p['cls_control']}` → 实验 `{p['cls_experiment']}`",
              f"- 对照选择：{p['sel_control'] or '(无)'} ｜ 实验选择：{p['sel_experiment'] or '(无)'}",
              f"- 卡面变化算子：{', '.join(sorted(changed)) or '(无)'}",
              (f"- ⚠ 实验臂选中 provenance_unverified 算子"
               if p["sel_contains_unverified_exp"] else ""),
              f"- **Owner 初判 V1（非金标）**：实验臂倾向 = {exp_q or '(未计指标/NODEC)'}；{note}",
              (f"- 待核证据：{'；'.join(checks)}" if checks else ""),
              "", "## 任务与步骤要求", "",
              f"**Task {tid} 全文**：", "", tasks[tid], "",
              f"**Step {snum}**：{st['name']} ｜ purpose: "
              f"{st['fields'].get('purpose', '-')} ｜ input: "
              f"{st['fields'].get('input', '-')} ｜ output: "
              f"{st['fields'].get('output', '-')}", "",
              "## 候选集合（Top-10，双臂相同、顺序冻结）", ""]
        md += [f"{i+1}. {o}" for i, o in enumerate(oids)]
        md += ["", "## 候选卡面（变化算子给双版本）", ""] + card_blocks
        md += ["", "## 对照臂 (v0_4) 完整决策段", "```",
               decision_text(craw), "```", "",
               "## 实验臂 (v0_5) 完整决策段", "```",
               decision_text(eraw), "```", "",
               "## 终判栏（owner 填）", "",
               "- decision_quality：control=＿＿ experiment=＿＿"
               "（正确选择/错误选择/合理弃权/误弃权/证据不足不可判）",
               "- output_validity 复核：control=＿＿ experiment=＿＿"
               "（有效/无判定/格式错误/截断）",
               "- 机制归类：□补卡解锁正确选择 □补卡诱发错误选择 □选择保持 "
               "□生成波动 □其他：＿＿", ""]
        safe = key.replace("#", "_")
        (OUT / f"{batch}_{safe}.md").write_text("\n".join(md), encoding="utf-8")

    (OUT / "LEDGER_V1.json").write_text(
        json.dumps({"schema": "A1_ADJUDICATION_LEDGER_V1",
                    "rules": "decision_quality 与 output_validity 正交；NODEC 不入四指标；"
                             "OOC=错误选择；初判=initial_not_gold",
                    "priority_five": PRIORITY_FIVE,
                    "n_pairs": len(ledger), "entries": ledger},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    idx = ["# A1 全证据卷宗包 INDEX V1", "",
           f"共 {len(ledger)} 对（初判批次排序 P1→P3→P4）；★=owner 点名优先核验五对："
           + "、".join(PRIORITY_FIVE), "",
           "裁决序：P1 11 对（T-009#S6 / T-009#S3 重点）→ P3 15 对 → P4 26 对 → "
           "四指标汇总 → 解释表选行。此前不宣称补卡有效、不启动 A2。", "",
           "| 卷宗 | 批次 | 实验臂初判倾向 |", "|---|---|---|"]
    for e in ledger:
        md_name = f"{e['batch']}_{e['step_key'].replace('#', '_')}.md"
        idx.append(f"| [{md_name}]({md_name}) | {e['batch']} | "
                   f"{e['owner_initial_v1']['experiment_decision_quality_tendency'] or '(NODEC 未计)'} |")
    (OUT / "INDEX.md").write_text("\n".join(idx), encoding="utf-8")
    print("dossiers:", len(ledger), "->", OUT)


if __name__ == "__main__":
    main()
