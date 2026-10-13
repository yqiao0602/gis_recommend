#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PCA Stage-3 — A-group eligibility review (owner round-10, four dimensions
x three statuses KEEP / KEEP-STRATIFIED / REPLACE).

Rule anchors:
  - not excluded for being detailed: native GEE verbosity is the in-domain
    construct; the risk to control is MISREADING task-text-supplied process
    info as model-planned capability.
  - REPLACE for construct mismatch (concept demo / export utility), never
    for verbosity.
  - replacements drawn from the frozen reserve pool (same selection rules,
    seed 20261013 lineage), each reviewed with the same four dimensions.
"""
import json, hashlib

D = "docs/reports/route2_p0_contract/plan_pipeline_v1/planning_capability_audit_v1/"
CAND = D + "pca_a_group_candidates_v1.json"
OUT = D + "pca_a_group_eligibility_v1.json"

R = {
57816: ("KEEP-STRATIFIED",
  "构念：空间分析工作流（时序计算+分类+异常+导出）✓。",
  "题面明示：QA60 云掩膜、NDVI/EVI/NDRE/SAVI、月度时序、五级分类、异常检测、导出清单（GeoTIFF+CSV）。",
  "剩余规划：集合过滤/合成与逐月 reduce 的组织、异常与分类的依赖顺序、统计导出的分区方式。",
  "金标边界：明示项=硬约束；NDVI 阈值数值未给→underdetermined；导出物清单=硬约束。",
  "过程描述丰富度高——分层报告，防把题面信息计为模型规划。"),
114710: ("KEEP",
  "构念：空间数据时序提取工作流 ✓。",
  "题面明示：日期范围、HGT 变量、按日 mean、按日期重命名、时间元数据。",
  "剩余规划：过滤/聚合/映射的组织顺序、日合成实现方式、区域裁剪。",
  "金标边界：日粒度+元数据=硬约束；实现路径自由。",
  "信息量适中。"),
72291: ("KEEP-STRATIFIED",
  "构念：统计提取为主（reduceRegion 逐景均值+属性附加），附大块可视化（12 幅假彩色）。",
  "题面明示：B1 波段、日期/AOI 过滤、clip、reduceRegion mean、Aerosol_Mean 属性。",
  "剩余规划：集合过滤与 clip 顺序、属性附加机制。",
  "金标边界：统计语义=硬约束；可视化张数/配色=展示手段（题面要求则记录，不计规划能力）。",
  "可视化占比高——分层。"),
33652: ("KEEP",
  "构念：站点级时序提取与多年聚合 ✓。",
  "题面明示：ERA5、2000–2020、ASOS 站点、月均、20 年平均、按站导出。",
  "剩余规划：站点-格网匹配方式、按月分组聚合组织、导出结构。",
  "金标边界：月×站×20 年均值语义=硬约束；聚合实现自由。",
  "信息量适中。"),
62586: ("KEEP-STRATIFIED",
  "构念：回归建模工作流（SDB 水深反演）✓。",
  "题面明示：S2_SR+云概率连接、对数波段比（蓝绿红）、线性回归、80/20 划分、R²/RMSE、资产导出。",
  "剩余规划：回归实现路径（EE reduce vs 导出训练）、波段比组合细节、样本划分执行。",
  "金标边界：方法学要素（连接/对数比/回归/划分/精度）=硬约束；系数数值=underdetermined。",
  "过程丰富——分层。"),
85688: ("KEEP-STRATIFIED",
  "构念：大气校正+监督分类工作流 ✓。",
  "题面明示：DOS 校正、RF 四类、deglinted 波段+DII23 指数、ROI 训练样本、Drive 导出。",
  "剩余规划：校正-采样-训练-分类的顺序、验证环节。",
  "金标边界：校正/分类器/类别数=硬约束；DII23 公式细节=underdetermined（题面仅命名）。",
  "分层。"),
15071: ("KEEP",
  "构念：水柱校正+双分类器+精度评估 ✓。",
  "题面明示：Lyzenga 校正、Landsat 8 SR、B2_median、RF+SVM、训练数据精度评估。",
  "剩余规划：校正实现、中值合成组织、精度评估机制。",
  "金标边界：校正+分类+评估=硬约束；分类器超参=underdetermined。",
  "信息量适中。"),
53359: ("KEEP-STRATIFIED",
  "构念：气候指标建模工作流 ✓。",
  "题面明示：CESM1-BGC、历史+RCP45/85、日均值、模糊阈值（含 3 日平均变体）、2000/2050 及差值、MODIS 陆地掩膜。",
  "剩余规划：模糊隶属实现、差值计算组织、掩膜应用点。",
  "金标边界：情景/年份/输出清单=硬约束；模糊阈值数值=underdetermined。",
  "分层。"),
4432: ("REPLACE",
  "构念不符：主 outcome 是图像导出工具（下载 URL/缩略图/元数据/批量 Drive 任务），与分析型工作流规划不同构念——与 B 组已替换的 W001034（KMZ 打包）同类。",
  "（信息量不构成排除理由；排除仅因构念。）",
  "—", "—",
  "替换原因记录在案；从 reserve 池同规则补足。"),
29502: ("REPLACE",
  "构念不符：客户端/服务器概念演示与 API 行为教学，非空间分析工作流任务（owner round-10 点名）；保留会降低 A 组构念一致性。",
  "（—）", "（—）", "（—）",
  "替换原因记录在案；从 reserve 池同规则补足。"),
90727: ("KEEP-STRATIFIED",
  "构念：指数合成+阈值制图工作流 ✓。",
  "题面明示：Landsat 7 LST+NDVI、2013–2020、TCI/VCI 组合、热季 3–5 月、NDVI>0.2 掩膜、VHI<20 干旱判定、Drive+CSV 导出。",
  "剩余规划：TCI/VCI 的 min/max 归一化实现、年度循环组织、面积统计方式。",
  "金标边界：指数组合/掩膜/阈值/输出=硬约束；归一化基准期=underdetermined。",
  "分层。"),
78050: ("KEEP-STRATIFIED",
  "构念：多步生态完整性建模 ✓。",
  "题面明示：Method 1（Doherty 2022）、STEPWAT 生物量 delta-S、RAP 覆盖层、生态区 q 曲线、Q1–Q5 乘积、SEI560/SEI2000、十分位分类。",
  "剩余规划：乘积整合与平滑的实现顺序、分类与重分类组织。",
  "金标边界：方法步骤链=硬约束（题面即方法学）；曲线数值=underdetermined（数据给定）。",
  "过程极丰富——分层（题面即方法规范，防计为规划）。"),
23443: ("KEEP-STRATIFIED",
  "构念：SEI 现势变体 ✓（与 78050 同族不同变体：现势 vs 未来情景）。",
  "题面明示：STEPWAT 三功能群、q 曲线、威胁层乘积、SEI560/SEI2000、三分管理类。",
  "剩余规划：同上族。",
  "金标边界：同族。",
  "分层；与 78050 的同族关系记录（多样性可控，不做配对）。"),
112319: ("KEEP-STRATIFIED",
  "构念：混合（可视化时序为主 + 火点置信度过滤的分析成分）。",
  "题面明示：MCMIPF scale/offset、合成绿波段、FDCF 置信度映射、≥0.3 过滤、红色叠加、时序集合输出。",
  "剩余规划：波段合成公式组织、火点-影像叠加机制。",
  "金标边界：校正/过滤阈值/叠加语义=硬约束；可视化形式=展示手段。",
  "可视化主导——分层。"),
55222: ("KEEP-STRATIFIED",
  "构念：空间聚合统计工作流 ✓。",
  "题面明示：VNP14IMGML、四互斥指标（AF/AFnoAqua/AFnoBA/AFnoMODIS）、GFEDv4 区域、reduceRegions 求和、CSV 导出。",
  "剩余规划：互斥条件的实现顺序、空间叠加组织。",
  "金标边界：四指标定义/聚合语义/导出=硬约束；0.25° 网格细节=underdetermined（题面自注 implicit）。",
  "分层。"),
54712: ("KEEP",
  "构念：地统计+ML 回归建模工作流 ✓。",
  "题面明示：克里金插值 ALT 点位、环境协变量（土壤/气候/NDVI/NDSI）、RF 回归、精度与变量重要性、资产导出。",
  "剩余规划：克里金实现、协变量堆叠与采样、验证组织。",
  "金标边界：两阶段建模语义=硬约束；克里金参数=underdetermined。",
  "信息量适中。"),
7698: ("KEEP",
  "构念：阈值分类工作流 ✓（信息量低——域内池的自然多样性）。",
  "题面明示：SAR HH 归一化阈值、光学暗影掩膜、三类（frozen/undecided/floating）。",
  "剩余规划：归一化/阈值执行、光学-SAR 掩膜组合顺序、分类决策结构。",
  "金标边界：输入模态+三分类=硬约束；阈值数值=underdetermined（题面未给）。",
  "剩余规划空间大——不分层。"),
79576: ("KEEP-STRATIFIED",
  "构念：时序提取+统计图表工作流 ✓（图表为附属性输出）。",
  "题面明示：GLDAS CLSM、伊朗多边形范围、2003–2024、月均 GWS、两图（面均+两点）、裁剪多波段 GeoTIFF、日期序列/元数据。",
  "剩余规划：逐月合成组织、区域均值与点提取机制。",
  "金标边界：时序语义+双图+导出=硬约束；点位坐标=underdetermined（user-defined）。",
  "分层。"),
98033: ("KEEP",
  "构念：监督分类+时间外推验证 ✓。",
  "题面明示：Landsat TOA、四类（水/清冰/浊冰/雪）、标注样本训练、按 2019 前后时间划分验证。",
  "剩余规划：样本-特征组织、训练/验证执行、模型产出形态。",
  "金标边界：类别集+时间验证设计=硬约束；特征清单细节=underdetermined（spectral predictors 概述）。",
  "信息量适中。"),
56465: ("KEEP-STRATIFIED",
  "构念：合成+统计监测（VV/VH 中值合成 + 月度获取密度统计）。",
  "题明示：Sentinel-1、2023 中值合成、月度影像计数（总/升/降）、裁剪合成+边界层+汇总统计+柱状图。",
  "剩余规划：合成组织、计数聚合机制。",
  "金标边界：合成/统计/输出清单=硬约束；可视化配色=展示手段。",
  "统计+可视化混合——分层。"),
}

REFILL = {
41652: ("KEEP",
  "构念：栖息地适宜性建模（RF+空间块交叉验证）✓——替换 4432。",
  "题面明示：presence 点+环境预测变量、概率图+二进制分布图、空间块 CV。",
  "剩余规划：块划分实现、训练-预测组织。",
  "金标边界：建模语义+CV 设计=硬约束；块参数=underdetermined。",
  "同 split（test）；同规则审查通过。"),
44487: ("KEEP",
  "构念：光谱分解（SMA）+覆盖度估算 ✓——替换 29502。",
  "题面明示：MCD43A4、SMA 三分量（bare/PV/NPV）、森林面积与百分比、2020-03、尼加拉瓜。",
  "剩余规划：SMA 端元实现、覆盖率换算组织。",
  "金标边界：SMA 语义+输出=硬约束；端元谱=underdetermined。",
  "同 split（test）；同规则审查通过。"),
}

def main():
    cand = json.load(open(CAND, encoding="utf-8"))
    by_line = {r["line_id"]: r for r in cand["primary"] + cand["reserve"]}
    rows, final20 = [], []
    for r in cand["primary"]:
        lid = r["line_id"]
        st, construct, given, remaining, boundary, note = R[lid]
        rows.append({"line_id": lid, "wid": None, "split": r["split"],
                     "task_type": r["task_type"], "status": st,
                     "construct_fit": construct, "info_given": given,
                     "remaining_planning_space": remaining,
                     "gold_boundary": boundary, "review_note": note,
                     "instruction_head": r["instruction"][:160]})
        if st != "REPLACE":
            final20.append(lid)
    refill_rows = []
    for lid, (st, construct, given, remaining, boundary, note) in REFILL.items():
        r = by_line[lid]
        refill_rows.append({"line_id": lid, "split": r["split"],
                            "task_type": r["task_type"], "status": st,
                            "construct_fit": construct, "info_given": given,
                            "remaining_planning_space": remaining,
                            "gold_boundary": boundary, "review_note": note,
                            "instruction_head": r["instruction"][:160]})
        if st != "REPLACE":
            final20.append(lid)
    assert len(final20) == 20, f"final pool {len(final20)} != 20"
    from collections import Counter
    payload = {"_meta": {
        "gate": "owner round-10 eligibility review (4 dimensions x 3 statuses)",
        "rule": "REPLACE only for construct mismatch, never verbosity; "
                "refills from frozen reserve pool with same review",
        "status_distribution": dict(Counter(r["status"] for r in rows)),
        "n_final_pool": len(final20),
        "final_pool_line_ids": sorted(final20),
        "stratification_note": "KEEP-STRATIFIED rows reported separately on "
                               "process-description richness; text-supplied "
                               "process info never counted as model planning"},
        "primary_review": rows, "refill_review": refill_rows}
    blob = json.dumps(payload, ensure_ascii=False, indent=1)
    open(OUT, "w", encoding="utf-8", newline="").write(blob)
    print("status:", dict(Counter(r["status"] for r in rows)))
    print("final pool:", len(final20), "| refills:", [r["line_id"] for r in refill_rows])
    print("file_sha256:", hashlib.sha256(blob.encode()).hexdigest()[:16])

if __name__ == "__main__":
    main()
