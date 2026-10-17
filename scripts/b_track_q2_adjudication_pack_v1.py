#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the owner adjudication evidence pack for the 117-record Q2 sample.

Owner request (2026-10-17 late): "本批次的 diff 文件或判读账本" — the worksheet
summaries are enough to set review order but NOT enough to fill final
fidelity A/B per record; the owner needs the actual code / diff per pair.

Per-record dossier S{n}.md contains:
  - metadata (scripts, sha1, sizes, diff-line count, run-count RLE rendering,
    mechanical flags, fidelity nominations)
  - Instruction A / B in FULL (raw text, re-derived from the pool)
  - Source A / B in FULL (fenced; evidence frozen into the repo)
  - unified diff A->B
  - the owner's seven-field adjudication block (blank):
    structural_equivalence / literal_equivalence / execution_equivalence /
    difference_source / fidelity_A / fidelity_B / decision_confidence /
    evidence_required

Plus INDEX.md (owner priority batches + watch list + three misjudgment guards
+ stratified-estimation statistical caliber) and LEDGER_V1.json (machine-
readable, ids pre-filled, seven fields empty).

Deterministic, read-only over pool + corpus. Output dir:
b_track_audit_v1/q2_rescan_adjudication_evidence_v1/
"""
import difflib
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
POOL = REPO.parent / "04_DIAG_WORK/b1_gee_stage_train.jsonl"
OUT_BASE = (REPO / ("docs/reports/route2_p0_contract/plan_pipeline_v1/"
                    "planning_capability_audit_v1/diag50_v1/b_track_audit_v1"))
SMP = OUT_BASE / "Q2_POOL_RESCAN_ADJUDICATION_SAMPLE_V1.json"
OUT = OUT_BASE / "q2_rescan_adjudication_evidence_v1"

OWNER_WATCH = {
    "S039": "owner 高优先：数据集差异真实性（landsat 5/7 提名）+ B 缺 SPATIAL_FILTER 的成因（省略/替代/抽取遗漏）",
    "S042": "owner 高优先：NEIGHBORHOOD 结构差 + 数字 2.5 缺失提名（阈值/半径/其他参数？）",
    "S043": "owner 结构审查：B 多 SPATIAL_JOIN->ATTRIBUTE_FILTER->SPATIAL_JOIN——新分析步骤 or 字段恢复/中间构建",
    "S026": "owner 语义审查：多重集同、TEMPORAL/SPATIAL_FILTER 换序——过滤是否独立、是否同对象",
    "S001": "owner 点名：尾部 RASTER_LOAD 增删核对实际代码",
    "S002": "owner 点名：尾部 RASTER_LOAD 增删核对实际代码",
    "S025": "owner 点名：顺序/重复差异核对实际代码",
    "S027": "owner 点名：顺序/重复差异核对实际代码",
    "S028": "owner 点名：顺序/重复差异核对实际代码",
    "S052": "owner：B 多 SPATIAL_FILTER+操作数与数据集变化——新增空间过滤是否有实际作用；勿直接判 B 更完整",
    "S053": "owner：B 少 ATTRIBUTE_FILTER/COLLECTION_MGMT——勿直接判功能退化",
    "S054": "owner：勿仅凭相似序列认定模板重复",
    "S055": "owner：勿仅凭相似序列认定模板重复",
    "S056": "owner：123 步长链——检查真实依赖与节点映射；J=0.95 不足以归并",
    "S059": "owner：34v13 步差异大、UI/重复计数不同——勿把全部差异归因 UI",
    "S061": "owner：82v34 步、ui_delta=35、dup_delta=349——勿直接视为脚手架噪声",
    "S062": "owner：代码差异大、操作数/重复/数据集变化",
    "S063": "owner：number_sym_diff_n=1301——检查规范化实现/重复展开/实际结构",
    "S064": "owner：核对算子增减是否改变依赖链",
    "S065": "owner：核对算子增减是否改变依赖链",
    "S066": "owner：核对算子增减是否改变依赖链",
    "S068": "owner：新增/移位操作是否改变数据流",
    "S069": "owner：新增/移位操作是否改变数据流",
    "S058": "owner：先判 UI 与重复节点差异是否污染相似度",
    "S067": "owner：先判 UI 与重复节点差异是否污染相似度",
    "S070": "owner：序列同可先归代码结构相似组（非任务等价）",
    "S071": "owner：序列同可先归代码结构相似组（非任务等价）",
    "S072": "owner：序列同可先归代码结构相似组（非任务等价）",
    "S073": "owner：序列同可先归代码结构相似组（非任务等式）",
    "S074": "owner：序列同可先归代码结构相似组（非任务等价）",
    "S075": "owner：序列同可先归代码结构相似组（非任务等价）",
    "S076": "owner：序列同可先归代码结构相似组（非任务等价）",
    "S077": "owner：序列同可先归代码结构相似组（非任务等价）",
    "S078": "owner：数据集缺失提名——单独处理",
    "S079": "owner：序列同可先归代码结构相似组（非任务等价）",
    "S080": "owner：序列同可先归代码结构相似组（非任务等价）",
    "S081": "owner：序列同可先归代码结构相似组（非任务等价）",
    "S082": "owner：SHA 同=代码文本同；不能证明描述对应任务相同",
    "S083": "owner：SHA 同=代码文本同；不能证明描述对应任务相同",
    "S084": "owner：SHA 同=代码文本同；不能证明描述对应任务相同",
    "S085": "owner：SHA 同=代码文本同；不能证明描述对应任务相同",
    "S086": "owner：SHA 同=代码文本同；不能证明描述对应任务相同",
    "S087": "owner：SHA 同=代码文本同；不能证明描述对应任务相同",
    "S088": "owner：SHA 同=代码文本同；不能证明描述对应任务相同",
    "S089": "owner：SHA 同=代码文本同；不能证明描述对应任务相同",
    "S090": "owner：SHA 同=代码文本同；不能证明描述对应任务相同",
    "S091": "owner：SHA 同=代码文本同；不能证明描述对应任务相同",
    "S092": "owner：SHA 同=代码文本同；不能证明描述对应任务相同",
    "S093": "owner：SHA 同=代码文本同；不能证明描述对应任务相同",
    "S094": "owner：序列同代码不同——重点参数与 API 语义",
    "S095": "owner：序列同代码不同——重点参数与 API 语义",
    "S096": "owner：序列同代码不同——重点参数与 API 语义",
    "S097": "owner：序列同代码不同——重点参数与 API 语义",
    "S098": "owner：序列同代码不同——重点参数与 API 语义",
    "S099": "owner：序列同代码不同——重点参数与 API 语义",
    "S100": "owner：序列同代码不同——重点参数与 API 语义",
    "S101": "owner：序列同代码不同——重点参数与 API 语义",
    "S102": "owner：序列同代码不同——重点参数与 API 语义",
    "S103": "owner：序列同代码不同——重点参数与 API 语义",
    "S104": "owner：序列同代码不同——重点参数与 API 语义",
    "S105": "owner：序列同代码不同——重点参数与 API 语义",
    "S106": "owner：优先检查 Landsat 7/5 差异",
    "S110": "owner：优先检查数据集与参数是否真正相同",
    "S112": "owner：优先检查数据集与参数是否真正相同",
}


def rle_render(rle):
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
    return " -> ".join(lb if k == 1 else f"{lb}x{k}" for lb, k in runs)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    smp = json.loads(SMP.read_text(encoding="utf-8"))

    # raw instructions: norm -> raw (first occurrence in pool order)
    norm2raw = {}
    with POOL.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            ni = re.sub(r"\s+", " ", r.get("instruction", "").strip().lower())
            if ni not in norm2raw:
                norm2raw[ni] = r.get("instruction", "")
    print(f"raw instruction map: {len(norm2raw)}", flush=True)

    index = {}
    for tree in [REPO / ".tmp_gee_batch13_sources/Data",
                 REPO / ".tmp_gee_batch8_ast_bridge/sources"]:
        if not tree.exists():
            continue
        for d in sorted(tree.iterdir()):
            if d.is_dir():
                for f in d.glob("script_*.txt"):
                    index.setdefault(f.name[:-4], f)

    ledger = []
    cls_N = {}   # filled below from mech JSON for the index
    mech = json.loads((OUT_BASE / "Q2_POOL_RESCAN_MECHANICAL_V1.json").read_text(encoding="utf-8"))
    for grp in ("diff_template_class_distribution", "same_template_class_distribution"):
        for k, v in mech[grp].items():
            cls_N[(grp.split("_")[0], k)] = v
    sampled_n = Counter()

    for i, r in enumerate(smp["records"], 1):
        sid = f"S{i:03d}"
        sampled_n[(r["bucket"], r["class"])] += 1
        raw_a = norm2raw.get(r["a"], r["a"])
        raw_b = norm2raw.get(r["b"], r["b"])
        pa, pb = index.get(r["script_a"]), index.get(r["script_b"])
        src_a = pa.read_text(encoding="utf-8", errors="replace") if pa else "(脚本未在本地语料中)"
        src_b = pb.read_text(encoding="utf-8", errors="replace") if pb else "(脚本未在本地语料中)"
        sha_a = hashlib.sha1(src_a.encode()).hexdigest()[:12]
        sha_b = hashlib.sha1(src_b.encode()).hexdigest()[:12]
        diff = list(difflib.unified_diff(
            src_a.splitlines(), src_b.splitlines(), lineterm="", n=2,
            fromfile=f"A/{r['script_a']}", tofile=f"B/{r['script_b']}"))
        fl = r.get("flags") or {}
        fls = "; ".join(f"{k}={v}" for k, v in fl.items()) or "—"
        fid = []
        for side in ("a", "b"):
            ff = r.get(f"fidelity_{side}")
            if ff:
                parts = []
                if ff["numbers_missing"]:
                    parts.append("数缺:" + ",".join(ff["numbers_missing"][:8]))
                if ff["dataset_absent"]:
                    parts.append("数据集缺:" + ",".join(ff["dataset_absent"][:4]))
                fid.append(f"{side}[{' ; '.join(parts)}]")
        watch = OWNER_WATCH.get(sid, "")
        md = [
            f"# {sid} [{r['bucket']}/{r['class']}] J={r['jaccard']}",
            "",
            f"- scripts: `{r['script_a']}` ({len(src_a):,} chars, sha1 {sha_a})"
            f" vs `{r['script_b']}` ({len(src_b):,} chars, sha1 {sha_b})",
            f"- diff lines: {len(diff)} | 机械 flags: {fls}",
            f"- RLE A（{len(r['rle_a'].split(' -> '))} 步，游程渲染）: `{rle_render(r['rle_a'])}`",
            f"- RLE B（{len(r['rle_b'].split(' -> '))} 步，游程渲染）: `{rle_render(r['rle_b'])}`",
            f"- 保真度提名（机械，仅提名）: {'; '.join(fid) if fid else '无'}",
        ]
        if watch:
            md.append(f"- **owner 审查指引**: {watch}")
        md += ["",
               "## Instruction A（全文）", "", raw_a, "",
               "## Instruction B（全文）", "", raw_b, "",
               "## Source A（全文）", "", "```javascript", src_a, "```", "",
               "## Source B（全文）", "", "```javascript", src_b, "```", "",
               "## Unified diff（A→B）", "", "```diff"] + (diff or ["(identical)"]) + [
               "```", "",
               "## 判读栏（owner 七字段，2026-10-17 schema）", "",
               "- structural_equivalence（结构等价: 等价/不等价/不可判）:",
               "- literal_equivalence（参数与数据源等价: 等价/可替换差异/影响结果差异/不可判）:",
               "- execution_equivalence（执行语义等价证据: 充分/部分/不足）:",
               "- difference_source（差异来源，可多选: 规划结构/参数字面量/实现与脚手架/证据不足）:",
               "- fidelity_A（失实/欠描述/忠实/不可判）:",
               "- fidelity_B（失实/欠描述/忠实/不可判）:",
               "- decision_confidence（高/中/低）:",
               "- evidence_required（尚需查看的具体代码证据）:", ""]
        (OUT / f"{sid}.md").write_text("\n".join(md), encoding="utf-8")
        ledger.append({"id": sid, "bucket": r["bucket"], "class": r["class"],
                       "jaccard": r["jaccard"], "script_a": r["script_a"],
                       "script_b": r["script_b"],
                       "structural_equivalence": "", "literal_equivalence": "",
                       "execution_equivalence": "", "difference_source": [],
                       "fidelity_A": "", "fidelity_B": "",
                       "decision_confidence": "", "evidence_required": ""})

    (OUT / "LEDGER_V1.json").write_text(
        json.dumps({"artifact": "Q2_POOL_RESCAN_ADJUDICATION_LEDGER_V1",
                    "schema": "owner 2026-10-17 七字段（差异来源可多选；保真度分轴独立）",
                    "records": ledger}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    # index
    idx = ["# Q2 池级复核判读证据包索引 V1（117 卷宗）", "",
           "- 每卷宗 = 指令全文 × 双侧源码全文 × 统一 diff × 机械 flags × 保真度提名 × 七字段判读栏。",
           "- 七字段 schema 与三防误判守则按 owner 2026-10-17 前置审查登记（见 `Q2_POOL_RESCAN_RULING_OWNER_V1.md`）。",
           "", "## 分层统计口径（owner 锁定）", "",
           "估计池级占比须按分层加权：p̂ = Σ_h (N_h/N)·p̂_h（N_h=机械类层总体，n_h=该层抽样数）；",
           "置信区间按分层抽样设计；证据不足/不可判/缺失样本处理规则单列；十对源码级已知证据",
           "保留为既有证据但不计入概率抽样比例；**机械漏检（机械层不可见的任务差异）需另设",
           "审计样本**，本包不能估计其发生率。", "",
           "| 层（bucket/类） | 层总体 N_h | 抽样 n_h |", "| --- | --- | --- |"]
    for (bucket, cls), N in sorted(cls_N.items()):
        idx.append(f"| {bucket}/{cls} | {N} | {sampled_n.get((bucket, cls), 0)} |")
    idx += ["", "## owner 审查优先序（登记）", "",
            "1. **S058–S069**（第一优先：脚手架/重复节点/操作语义差异；S059/S061-S063 重点；",
            "   S060/S064-S066 依赖链；S068/S069 数据流；S058/S067 相似度污染）",
            "2. **S051–S057**（第二：操作多重集/参数/数据来源；S052/S053/S056 重点）",
            "3. **S070–S117**（第三：先批量分类再复核例外；S078 数据集缺失、S106 Landsat 7/5、",
            "   S110/S112 数据集参数）",
            "4. **S001–S050 中的 owner 点名**: S039/S042/S043/S026（高优先）+ S001/S002/S025/S027/S028",
            "", "## 三防误判守则（owner）", "",
            "1. 重复块不必然无害——须查数据依赖与输出使用；",
            "2. 字面量变化不必然表面——数据集/阈值/波段/日期可决定结果；",
            "3. 同码双描述≠指令失实——须独立核对代码与指令对应关系；",
            "结构相似/代码相同/任务等价不得混为一个标签。", "",
            "## 已知十对的处置", "",
            "源码级已核验十对（V3 四对 + V2-P0 六对）保留为既有证据；落入本样本即注明沿用。", ""]
    (OUT / "INDEX.md").write_text("\n".join(idx), encoding="utf-8")

    total = sum(f.stat().st_size for f in OUT.glob("*.md"))
    print(f"dossiers: {len(ledger)} | pack size: {total/1e6:.2f} MB")


if __name__ == "__main__":
    main()
