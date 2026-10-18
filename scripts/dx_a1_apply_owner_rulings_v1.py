#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Apply owner rulings (2026-10-18, two batches: 6 samples) to the A1 ledger,
plus the clarified cross-cutting rules, and recompute the four metrics.

Owner rules introduced/clarified with these rulings:
  R1 复合步骤闭合原则: partial capability hit (e.g. radiometric calibration only
     when the step also demands atmospheric correction) does NOT count as
     correct -> 证据不足不可判 (T-032#S2).
  R2 截断 ≠ 无判定: a truncated think that nevertheless contains reasoning is
     output_validity="truncated" + decision_quality="indeterminate", NOT NODEC
     and NOT reasonable abstention (T-068#S4 / T-092#S9 / T-090#S4 control arms).
     Only a genuinely empty output is NODEC (not counted).
  R3 大小写笔误不改变算子身份: 'otb:ImageClassifier' resolves to
     otb:imageclassifier (in candidates) -> correct selection; the text anomaly
     is recorded (T-090#S4).
  R4 卡面字段完整度 ≠ 决策证据完整度 (T-009#S6: classifier(Choice) without enum
     values does not prove CART).
  R5 因果归因保守: a better outcome does not automatically equal "card
     unlocked"; direct causal attribution requires the control arm to have
     formed a closed decision.

Owner-ruled pairs (6):
  T-009#S3 control RA / exp W (mechanism: functional-generalization error,
          card-induced NOT established; keep as indirect/context candidate)
  T-009#S6 control RA / exp IND (missing enum evidence)
  T-032#S2 control RA / exp IND (partial capability; overall step not closed)
  T-068#S4 control IND(truncated) / exp RA (owner: r.statistics card lacks
          explicit vector-zonal input/output/method evidence -> abstention
          is reasonable; control cannot be retro-labelled as wrong)
  T-092#S9 control IND(truncated) / exp RA
  T-090#S4 control IND(truncated) / exp C (operator identity by typo-tolerant
          reading; card matches the step)
"""
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from dx_s23 import parse_s2_v2  # noqa: E402

P = Path(r"E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/a1_short/A1_FULL_EVIDENCE_PACKET_V1")
LEDGER = P / "LEDGER_V1.json"
CTRL = Path(r"E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/dx50_short/runs")
EXP = Path(r"E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/_a1_work/runs_local")

OWNER = {
 "PCA2-T-009#S3": {
   "control": "reasonable_abstention", "experiment": "wrong_selection",
   "validity": {"control": "valid", "experiment": "valid"},
   "mechanism": "其他——功能泛化型错误选择，可能受上下文影响（补卡⇒错误：间接，未认定直接因果）",
   "note": "owner：DIFF 是多波段差异统计，不实现 NDVI/NDSI 公式；双臂该卡相同，实验臂无新增指数证据；"
           "对照的弃权是在给定候选内合理识别能力缺口，实验臂降低了语义正确性。"},
 "PCA2-T-009#S6": {
   "control": "reasonable_abstention", "experiment": "indeterminate",
   "validity": {"control": "valid", "experiment": "valid"},
   "mechanism": "其他——卡面暴露分类器配置入口，但关键枚举证据缺失",
   "note": "owner：方向匹配（训练对象/输入类型/分类任务），但 classifier(Choice) 枚举未展开，CART 不受证；"
           "io.out 只证明存在文件输出接口，不证明是 CART 决策树模型。卡片字段完整度≠决策证据完整度。"},
 "PCA2-T-032#S2": {
   "control": "reasonable_abstention", "experiment": "indeterminate",
   "validity": {"control": "valid", "experiment": "valid"},
   "mechanism": "其他——卡片补全暴露有效辐射定标能力，但任务要求超出单算子已证实能力",
   "note": "owner：TOA/TOC+手动参数为实质证据，但 level(Choice) 未展开、Landsat 4–8 大气校正未证明；"
           "复合步骤（定标+大气校正）部分能力命中不升级为整体正确——不记补卡解锁金标。"},
 "PCA2-T-068#S4": {
   "control": "indeterminate", "experiment": "reasonable_abstention",
   "validity": {"control": "truncated", "experiment": "valid"},
   "mechanism": "其他——从开放式推理转为明确弃权；不能证明补卡收益",
   "note": "owner：对照 think 内已指向 r.statistics 但无闭合决策（截断），不得追溯补答；"
           "r.statistics 卡面（base/cover/method 均为 literal，无矢量分区输入/输出类型/统计方法明文）"
           "不足以证适用，实验弃权理由成立。变化算子 smallregionsmerging 与目标无关。"},
 "PCA2-T-092#S9": {
   "control": "indeterminate", "experiment": "reasonable_abstention",
   "validity": {"control": "truncated", "experiment": "valid"},
   "mechanism": "其他——复合步骤能力边界识别；不能归因为补卡解锁",
   "note": "owner：需同时平滑+混淆矩阵/总体精度报告；classificationmapregularization 支撑平滑，"
           "trainimagesclassifier 的 confmatout 不能证明可对既有分类图独立验证；对照截断→不可判。"},
 "PCA2-T-090#S4": {
   "control": "indeterminate", "experiment": "correct_selection",
   "validity": {"control": "truncated", "experiment": "valid"},
   "mechanism": "其他——卡面补全使已有正确候选的功能变得可验证（非新增候选解锁）",
   "note": "owner：'otb:ImageClassifier' 按 otb:imageclassifier 计（大小写笔误不改变算子身份）；"
           "in/model/out 与描述完全匹配步骤；对照截断→不可判，因果归因保守。"},
}

DEC = {"C": "correct_selection", "W": "wrong_selection",
       "RA": "reasonable_abstention", "WA": "wrong_abstention",
       "IND": "indeterminate", "NODEC": "n/a_no_decision"}


AFFECTED = json.loads((P / ".." / "A1_AFFECTED_SET_V1.json").read_text(encoding="utf-8"))
OIDS = {}
for _row in AFFECTED["affected_steps"]:
    _tid, _s = _row["step_key"].split("#S")
    _retr = json.loads((CTRL.parent.parent / "dx50_short" / "runs" / _tid / "S1"
                        / "retrieval.json").read_text(encoding="utf-8"))
    _top = next(x for x in _retr["steps"] if x["step"] == int(_s))
    OIDS[_row["step_key"]] = [c["operator_id"] for c in _top["top10"]]


def derive_validity(key, arm):
    """Owner rule R2: truncated-with-reasoning -> truncated + indeterminate;
    empty raw -> no_decision (NODEC)."""
    tid, snum = key.split("#S")
    d = (CTRL if arm == "control" else EXP) / tid / "S2" / f"S{snum}"
    raw = (d / "raw_output.txt").read_text(encoding="utf-8")
    if not raw.strip():
        return "no_decision"
    pv2 = d / "parsed_v2.json"
    if arm == "control" and pv2.exists():
        parsed = json.loads(pv2.read_text(encoding="utf-8"))
    else:
        pp = d / "parsed.json"
        parsed = json.loads(pp.read_text(encoding="utf-8")) if pp.exists() else None
    if parsed is None or parsed.get("parser") != "s2_v2":
        parsed = parse_s2_v2(raw, OIDS.get(key, []))
    if parsed.get("decision_section") == "think_unterminated":
        return "truncated"
    return "valid"


def main():
    d = json.loads(LEDGER.read_text(encoding="utf-8"))
    # 1) apply R2 across all pairs still carrying NODEC on either arm
    reclassed = []
    for e in d["entries"]:
        q = e["ledger_fields_pending_owner"]["decision_quality"]
        for arm, cur in (("control", q["control"]), ("experiment", q["experiment"])):
            if cur != "n/a_no_decision":
                continue
            v = derive_validity(e["step_key"], arm)
            if v == "truncated":
                q[arm] = "indeterminate"
                reclassed.append((e["step_key"], arm))
        # validity refresh
        for arm in ("control", "experiment"):
            if e["ledger_fields_pending_owner"]["output_validity"][arm] == "no_decision":
                e["ledger_fields_pending_owner"]["output_validity"][arm] = \
                    derive_validity(e["step_key"], arm)

    # 2) apply the six owner rulings (authoritative)
    ruled = 0
    for e in d["entries"]:
        o = OWNER.get(e["step_key"])
        if not o:
            continue
        ruled += 1
        q = e["ledger_fields_pending_owner"]
        q["decision_quality"] = {"control": o["control"], "experiment": o["experiment"]}
        q["output_validity"] = dict(o["validity"])
        q["mechanism"] = o["mechanism"]
        q["final_note"] = o["note"]
        q["status"] = "owner_ruled"
        q["agent_initial"] = q.get("agent_initial") or {
            "note": "agent 初判保留于 git 历史（commit b4875dc）"}
    d["owner_ruling"] = {
        "date": "2026-10-18", "n_ruled": ruled,
        "rules": [
            "R1 复合步骤闭合：部分能力命中≠整体正确（T-032）",
            "R2 截断≠无判定：截断但有推理→output_validity=truncated + 证据不足不可判；空输出才是无判定（T-068/T-092/T-090 对照臂）",
            "R3 大小写笔误不改变算子身份（T-090: otb:ImageClassifier→otb:imageclassifier）",
            "R4 卡面字段完整度≠决策证据完整度（T-009#S6）",
            "R5 因果归因保守：改善≠补卡解锁，须对照臂形成闭合决策方可直接归因",
        ],
        "R2_reclassified_arms": reclassed,
    }
    LEDGER.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")

    def tally(arm):
        return Counter(e["ledger_fields_pending_owner"]["decision_quality"][arm]
                       for e in d["entries"])

    def rates(c):
        formed = c["correct_selection"] + c["wrong_selection"] + \
                 c["reasonable_abstention"] + c["wrong_abstention"]
        return {"n_formed": formed,
                "correct": c["correct_selection"], "wrong": c["wrong_selection"],
                "reasonable_abst": c["reasonable_abstention"],
                "wrong_abst": c["wrong_abstention"],
                "indeterminate": c["indeterminate"],
                "no_decision": c["n/a_no_decision"],
                "correct_rate": round(c["correct_selection"] / formed, 4) if formed else None,
                "wrong_rate": round(c["wrong_selection"] / formed, 4) if formed else None,
                "reasonable_abst_rate": round(c["reasonable_abstention"] / formed, 4) if formed else None,
                "wrong_abst_rate": round(c["wrong_abstention"] / formed, 4) if formed else None}

    ctl, exp = tally("control"), tally("experiment")
    trans = Counter()
    for e in d["entries"]:
        q = e["ledger_fields_pending_owner"]["decision_quality"]
        trans[(q["control"], q["experiment"])] += 1
    summary = {"after_owner_rulings": True,
               "control": rates(ctl), "experiment": rates(exp),
               "transitions": {f"{a} -> {b}": n for (a, b), n in trans.items()},
               "owner_ruled_pairs": list(OWNER)}
    (P / "A1_ADJUDICATION_SUMMARY_V1.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("R2 reclassified NODEC->indeterminate arms:", len(reclassed))


if __name__ == "__main__":
    main()
