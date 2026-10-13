# -*- coding: utf-8 -*-
"""Cumulative transcription of annotator-1 final rulings into the results file.

MECHANICAL TRANSCRIPTION ONLY: values are verbatim from the annotator's
finalized tables; no judgment is added, altered, or filled in. Unfinalized
units stay null. Re-running regenerates the cumulative results file from the
frozen template + all recorded batches.

Batches:
  batch1 2026-10-10  script_7900  A2 (53 units)
  batch2 2026-10-10  script_10021 A2 (8 units) + A3 (20 units via line->role)
"""

import json
import os
import sys
from datetime import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREP = os.path.join(REPO, "docs", "reports", "gee_semantic_planner_v1_pilot_round3",
                    "expansion_validation_prep_v1")
WS = os.path.join(PREP, "annotator1_workspace_v1")

ANNOTATOR = "annotator1_owner"
# (A1_EXTRA_NOTES is defined after the batch dicts below)

# ---------------- batch 1: script_7900 A2 ----------------
A2_7900 = {
    "image": ("analysis_chain", 2, "形参(cloudMask)；仅统计其所属函数内引用。"
              "注意: NDVI/EVI/NBR 中另有同名形参，文件级单位与之合并——留待 F2 开封裁定"),
    "cloudMask": ("analysis_chain", 1, "传入 .map(cloudMask)"),
    "cloudShadowBitMask": ("analysis_chain", 1, "用于云影位掩膜"),
    "cloudsBitMask": ("analysis_chain", 1, "用于云位掩膜"),
    "qa": ("analysis_chain", 2, "用于两次位运算筛选"),
    "NDVI": ("analysis_chain", 1, "传入 .map(NDVI)"),
    "ndvi": ("analysis_chain", 1, "传入 addBands()"),
    "EVI": ("analysis_chain", 2, "函数先用于 .map(EVI)；之后同名变量被重新赋值为 EVI 影像并导出"),
    "evi": ("analysis_chain", 1, "传入 addBands()"),
    "NBR": ("unconsumed", 0, "函数已定义，但完整源码中没有调用"),
    "nbr": ("analysis_chain", 1, "保留区别: 仅函数内部链，父函数 NBR 未调用——局部存在、全局不可达，"
            "不描述为实际运行的分析步骤"),
    "scale": ("unconsumed", 0, "未使用；区域统计实际使用字面量 scale: 300"),
    "dem": ("analysis_chain", 2, "用于坡度和坡向计算"),
    "degree2radian": ("unconsumed", 0, "完整源码中没有引用；角度转换直接使用数值常量"),
    "img": ("analysis_chain", 8, "形参(illuminationCondition)；用于太阳角度、几何范围与输出影像构建"),
    "illuminationCondition": ("analysis_chain", 1, "传入 .map(illuminationCondition)"),
    "SZ_rad": ("analysis_chain", 2, "用于余弦、正弦计算"),
    "SA_rad": ("analysis_chain", 1, "用于方位角差计算"),
    "slp": ("analysis_chain", 1, "加入输出影像的 slope 波段"),
    "slp_rad": ("analysis_chain", 2, "用于坡面余弦、正弦计算"),
    "asp_rad": ("analysis_chain", 1, "用于方位角差计算"),
    "cosZ": ("analysis_chain", 2, "用于照度计算并加入影像"),
    "cosS": ("analysis_chain", 3, "用于照度计算并加入影像"),
    "slope_illumination": ("analysis_chain", 1, "与坡向照度相加"),
    "sinZ": ("analysis_chain", 2, "用于坡向照度计算"),
    "sinS": ("analysis_chain", 1, "用于坡向照度计算"),
    "cosAziDiff": ("analysis_chain", 1, "用于坡向照度计算"),
    "aspect_illumination": ("analysis_chain", 1, "参与合成照度计算"),
    "ic": ("analysis_chain", 2, "用于合成照度波段并加入影像"),
    "illuminationCorrection": ("analysis_chain", 1, "传入 .map(illuminationCorrection)"),
    "props": ("analysis_chain", 1, "用于 setMulti(props) 恢复影像属性"),
    "st": ("analysis_chain", 1, "用于恢复 system:time_start"),
    "img_plus_ic": ("analysis_chain", 7, "illuminationCondition 内定义；用于掩膜、波段选择及影像合成。"
                    "注意: illuminationCorrection 内另有同名局部绑定(第109行 img_plus_ic = img)——文件级单位合并，留待 F2"),
    "mask1": ("unconsumed", 0, "构建后没有使用；实际使用的是 mask2"),
    "mask2": ("analysis_chain", 1, "用于 updateMask(mask2)"),
    "img_plus_ic_mask2": ("analysis_chain", 7, "用于区域统计、校正表达式及波段选择"),
    "bandList": ("analysis_chain", 4, "用于移除波段、映射校正函数、构造波段列表及恢复波段"),
    "compositeBands": ("analysis_chain", 1, "用于 removeAll(bandList)"),
    "nonCorrectBands": ("analysis_chain", 1, "用于输出影像的 addBands()"),
    "geom": ("unconsumed", 0, "几何范围被构建，但没有后继使用"),
    "apply_SCSccorr": ("analysis_chain", 1, "传入 bandList.map()"),
    "band": ("analysis_chain", 3, "形参(apply_SCSccorr)；用于波段选择及校正表达式；按局部作用域统计"),
    "method": ("unconsumed", 0, "赋值为 'SCSc' 后未使用"),
    "out": ("analysis_chain", 4, "用于空值判断和提取拟合系数"),
    "out_a": ("analysis_chain", 1, "用于计算 out_c"),
    "out_b": ("analysis_chain", 1, "用于计算 out_c"),
    "out_c": ("analysis_chain", 1, "用于校正表达式的 cvalue 参数"),
    "SCSc_output": ("analysis_chain", 1, "用于返回校正后的影像"),
    "img_SCSccorr": ("analysis_chain", 2, "用于波段恢复并返回结果"),
    "bandList_IC": ("analysis_chain", 1, "用于恢复波段时的选择"),
    "landsat8": ("analysis_chain", 3, "包含自引用读取、打印和合成输入读取。保留区别: A2 的 analysis_chain "
                 "不代表 A1 的定义来源问题已解决"),
    "landsat8_composite": ("analysis_chain", 4, "用于构建掩膜、更新掩膜、地图展示及提取 EVI"),
    "mask": ("analysis_chain", 1, "第 217 行绑定，用于 updateMask(mask)。注意: cloudMask 函数内第 9 行"
             "另有同名绑定(用于第 13 行)——文件级单位合并，留待 F2"),
}

# ---------------- batch 2: script_10021 A2 + A3 ----------------
A2_10021 = {
    "c": ("analysis_chain", 2, "被 filterBounds(c) 和 Map.centerObject(c, 8) 使用；"
          "前者进入影像筛选链，后者用于地图定位"),
    "landsat": ("analysis_chain", 2, "被 filterDate(...) 和 filterBounds(c) 链式处理，"
                "最终传入 simpleComposite 的 collection 参数"),
    "composite": ("analysis_chain", 5, "5 次读取分别是第 17、19、23、27、29 行"),
    "b5": ("analysis_chain", 2, "用于 ndvi_1 的减法与加法计算"),
    "b4": ("analysis_chain", 2, "用于 ndvi_1 的减法与加法计算"),
    "ndvi_1": ("presentation_only", 1, "仅传入 Map.addLayer 展示"),
    "ndvi_2": ("presentation_only", 1, "仅传入 Map.addLayer 展示"),
    "ndvi_3": ("presentation_only", 1, "仅传入 Map.addLayer 展示"),
}
A2_10021_NOTES = ("标注者口径: presentation_only = 变量结果只用于展示，尽管生成该结果的计算"
                  "本身属于分析操作；三种 NDVI 计算路径不因输入相同而合并——三个独立源码计算路径")
A3_10021_LINES = {
    1: "analysis", 3: "analysis", 9: "analysis", 17: "analysis", 19: "analysis",
    21: "analysis", 23: "analysis", 25: "analysis", 27: "analysis", 29: "analysis",
    33: "presentation", 35: "presentation", 37: "presentation", 39: "presentation",
}

# ---------------- batch 3: script_10224 A2 + A3 ----------------
A2_10224 = {
    "COL_FILTER": ("analysis_chain", 2, "被两个影像集合的 .filter() 使用，控制空间和时间范围"),
    "dwCol": ("analysis_chain", 1, "作为动态世界影像集合传入 Join"),
    "s2Col": ("analysis_chain", 1, "作为 Sentinel-2 影像集合传入 Join"),
    "DwS2Col": ("analysis_chain", 1, "调用 .first() 获取匹配后的首个要素"),
    "dwImage": ("analysis_chain", 3, "标注者自纠: 直接引用口径为 get('s2_img')/select('label')/"
                "select(CLASS_NAMES) 共 3 次；Map 展示链中衍生结果的间接使用不计入直接引用，"
                "故最终记录 3 而非 4"),
    "s2Image": ("presentation_only", 1, "仅用于 Sentinel-2 底图展示"),
    "CLASS_NAMES": ("analysis_chain", 1, "用于选择 Dynamic World 的类别概率波段，支持最大概率计算"),
    "dwRgb": ("analysis_chain", 1, "标注者边界: 虽由 visualize() 生成，但结果继续参与 "
              ".multiply(top1ProbHillshade)，故整体 analysis_chain；中间渲染操作与最终展示用途不混同"),
    "top1Prob": ("analysis_chain", 1, "由最大值归约得到最高类别概率，用于地形阴影计算"),
    "top1ProbHillshade": ("analysis_chain", 1, "用于调制 dwRgb，形成最终展示影像"),
    "dwRgbHillshade": ("presentation_only", 1, "仅用于最终 Map.addLayer 展示"),
}
A3_10224_LINES = {
    1: "analysis", 3: "analysis", 5: "analysis", 7: "analysis", 9: "analysis",
    11: "analysis", 13: "analysis", 15: "analysis", 17: "analysis",
    41: "analysis", 45: "analysis", 49: "analysis",
    51: "presentation", 53: "presentation", 61: "presentation",
}
# line 33 is MIXED per-call (annotator ruled each call separately):
#   A3:10 = .divide -> analysis; A3:11 = .visualize -> presentation;
#   A3:12 = .select -> analysis  (identity resolved mechanically from source AST)
A3_10224_UNITS = {
    "script_10224:A3:10": "analysis",
    "script_10224:A3:11": "presentation",
    "script_10224:A3:12": "analysis",
}
A2_10224_NOTES = ("标注者口径: 直接标识符引用计数（间接/衍生使用不计）；presentation_only "
                  "即使经多个中间变量传递最终进入 Map.addLayer 仍归之")

# ---------------- batch 4: script_25214 A2 + A3 ----------------
A2_25214 = {
    "tiempo1": ("analysis_chain", 1, "用于生成第一时段的中位数合成影像"),
    "tiempo1b": ("analysis_chain", 1, "用于计算第一时段的 NDVI"),
    "tiempo2": ("analysis_chain", 1, "用于生成第二时段的中位数合成影像"),
    "tiempo2b": ("analysis_chain", 1, "用于计算第二时段的 NDVI"),
    "NDVI1": ("analysis_chain", 2, "一次用于多时相影像合成，一次用于地图展示。注意: 虽参与地图展示，"
              "但同时进入 NDVImultitemporal 构建，整体归 analysis_chain"),
    "NDVI2": ("analysis_chain", 2, "一次用于多时相影像合成，一次用于地图展示；同 NDVI1 口径"),
    "NDVImultitemporal": ("presentation_only", 1, "仅用于 Map.addLayer 展示。标注者记录细节: "
                          "表达式 NDVI1.addBands(NDVI1).addBands(NDVI2) 将 NDVI1 添加了两次"
                          "（可能是重复引用错误），不影响变量使用状态判定"),
}
A2_25214_NOTES = "标注者口径: 直接后继引用计数，间接依赖不计"
A3_25214_LINES = {
    1: "analysis", 7: "analysis", 9: "analysis", 15: "analysis",
    17: "analysis", 19: "analysis", 21: "analysis",
    23: "presentation", 27: "presentation", 31: "presentation",
    33: "presentation",
}

# ---------------- batch 5: script_35821 A1 + A2 + A3 ----------------
A1_35821 = {
    "geometry": ("external_prebinding", "采用标注者建议: 疑似 Code Editor 平台预绑定 geometry；"
                 "源码内无显式证据（标注者注明: 若规程要求源码内证据则应改判 indeterminable）"),
}
A2_35821 = {
    "scale": ("unconsumed", 0, "定义为 300，但实际 reduceRegion 使用字面量 scale: 300，未引用该变量"),
    "dem": ("analysis_chain", 3, "用于坡度和坡向计算；ee.Terrain.slope(dem) 两次，aspect 一次"),
    "degree2radian": ("unconsumed", 0, "定义后未使用；角度转换直接使用圆周率和 180"),
    "terrainCorrection": ("unconsumed", 0, "定义了地形校正函数，但脚本未调用该函数"),
    "img": ("analysis_chain", 8, "形参(illuminationCondition)；用于获取太阳角度、影像几何、添加波段等处理"),
    "illuminationCondition": ("analysis_chain", 1, "传入 collection.map()，但所属 terrainCorrection "
                              "函数本身未被调用"),
    "SZ_rad": ("analysis_chain", 3, "用于计算太阳天顶角的正弦和余弦，并参与照明计算"),
    "SA_rad": ("analysis_chain", 1, "用于计算太阳方位角与坡向的角度差"),
    "slp": ("analysis_chain", 1, "坡度影像被加入 img_plus_ic"),
    "slp_rad": ("analysis_chain", 2, "用于计算坡度余弦和正弦"),
    "asp_rad": ("analysis_chain", 1, "用于计算太阳方位角与坡向的角度差"),
    "cosZ": ("analysis_chain", 3, "参与坡面照明计算，并作为辅助波段加入影像"),
    "cosS": ("analysis_chain", 3, "参与坡面照明计算，并作为辅助波段加入影像"),
    "slope_illumination": ("analysis_chain", 1, "与坡向照明项相加，形成照明条件"),
    "sinZ": ("analysis_chain", 1, "参与坡向照明计算"),
    "sinS": ("analysis_chain", 1, "参与坡向照明计算"),
    "cosAziDiff": ("analysis_chain", 1, "参与坡向照明计算"),
    "aspect_illumination": ("analysis_chain", 1, "与坡面照明项相加"),
    "ic": ("analysis_chain", 1, "作为 IC 波段加入影像"),
    "illuminationCorrection": ("unconsumed", 1, "仅在未调用的 terrainCorrection 函数体内作为 .map() "
                               "回调被引用，运行主流程并不会触发它"),
    "props": ("analysis_chain", 1, "用于恢复影像属性"),
    "st": ("analysis_chain", 1, "用于恢复 system:time_start 属性"),
    "img_plus_ic": ("analysis_chain", 7, "用于筛选、掩膜、波段选择和校正结果构建"),
    "mask1": ("unconsumed", 0, "计算后未使用；实际掩膜使用的是 mask2"),
    "mask2": ("analysis_chain", 1, "用于 updateMask()"),
    "img_plus_ic_mask2": ("analysis_chain", 11, "用于区域统计、SCS+C 校正、掩膜影像波段恢复"),
    "bandList": ("analysis_chain", 4, "用于逐波段校正、波段恢复和非校正波段区分"),
    "compositeBands": ("analysis_chain", 1, "用于移除需要校正的波段"),
    "nonCorrectBands": ("analysis_chain", 1, "与校正结果重新组合"),
    "geom": ("unconsumed", 0, "定义了缓冲几何，但后续 reduceRegion() 使用的是另一个几何表达式"),
    "apply_SCSccorr": ("analysis_chain", 1, "作为 bandList.map() 的回调"),
    "band": ("analysis_chain", 4, "形参(apply_SCSccorr)；用于选择目标波段、获取回归结果及构建校正影像"),
    "method": ("unconsumed", 0, "定义为 'SCSc'，后续未使用"),
    "out": ("analysis_chain", 3, "用于判空，并提取回归系数"),
    "out_a": ("analysis_chain", 1, "用于计算校正系数 out_c"),
    "out_b": ("analysis_chain", 1, "用于计算校正系数 out_c"),
    "out_c": ("analysis_chain", 1, "作为 SCS+C 校正公式中的参数"),
    "SCSc_output": ("unconsumed", 0, "虽然构建了校正影像，但没有返回该变量；else 分支最终没有有效的 "
                    "return SCSc_output"),
    "img_SCSccorr": ("analysis_chain", 3, "用于添加 IC 波段、填补掩膜缺失值并恢复波段"),
    "bandList_IC": ("analysis_chain", 1, "用于恢复校正结果中的波段"),
    "cloudMasking": ("analysis_chain", 1, "传入主流程的 collection.map()"),
    "qa": ("analysis_chain", 4, "用于 QA 位运算构造云和阴影掩膜"),
    "aero": ("analysis_chain", 2, "用于气溶胶 QA 掩膜及波段重命名输入"),
    "mask": ("analysis_chain", 1, "用于 img.updateMask(mask)"),
    "inBands": ("analysis_chain", 1, "用于 collection.select(inBands, outBands)"),
    "outBands": ("analysis_chain", 1, "用于波段重命名"),
    "collection": ("analysis_chain", 6, "用于空间与时间筛选、云掩膜、波段选择、中位数合成；另有两次赋值及"
                   "一次最终合成调用，具体引用次数取决于是否将赋值左值纳入计数"),
    "image": ("analysis_chain", 2, "用于地图展示和导出到 Cloud Storage"),
}
A2_35821_NOTES = ("标注者特别标记三处结构问题: (1) terrainCorrection 未被主流程调用，其内部函数与变量"
                  "不应误认为已进入实际分析链; (2) mask1/geom/method/degree2radian/scale 为典型未使用"
                  "定义; (3) SCSc_output 疑似返回值缺陷（else 分支未返回），建议数据质量审计单独记录。"
                  "标注者结论: 实际主流程 = Landsat 筛选→云掩膜→重命名→中位数合成→展示/导出；地形照明"
                  "校正虽定义完整但不在实际执行链中")
A3_35821_LINES = {
    3: "analysis", 9: "analysis", 11: "analysis", 19: "analysis", 21: "analysis",
    23: "analysis", 25: "analysis", 27: "analysis", 29: "analysis", 31: "analysis",
    33: "analysis", 37: "analysis", 39: "analysis", 41: "analysis", 43: "analysis",
    45: "analysis", 53: "analysis", 55: "analysis", 63: "analysis", 65: "analysis",
    69: "analysis", 71: "analysis", 73: "analysis", 75: "analysis", 77: "analysis",
    81: "analysis", 83: "analysis", 85: "analysis", 91: "analysis", 93: "analysis",
    95: "analysis", 105: "analysis", 111: "analysis", 113: "analysis",
    115: "analysis", 117: "analysis", 121: "analysis", 123: "analysis",
    125: "analysis", 127: "analysis", 139: "analysis", 141: "analysis",
    143: "analysis", 145: "analysis", 155: "analysis", 157: "analysis",
    159: "analysis", 161: "analysis", 163: "analysis", 167: "analysis",
    169: "analysis", 171: "analysis", 181: "analysis",
    183: "presentation", 185: "presentation", 187: "export",
}

# ---------------- batch 6: script_45485 A1 + A2 + A3 ----------------
A1_45485 = {
    "MCD12Q2_2003_Full": ("indeterminable",
                          "仅第 1 行使用，源码未见定义、require、注释说明或足以确认平台预绑定的证据；"
                          "不能仅凭命名判断为外部预绑定或缺失定义"),
    "Lai_Global_2003_1500_unseason_G_D_erci_unmask_greenup_lt_Dormancy":
        ("external_prebinding",
         "第 1、51 行均引用且第 51 行用于地图展示；源码没有定义。可能来自 EE 编辑器外部预置对象或"
         "此前导入的资产，当前无法确认具体来源。标注者注明: 若严格要求源码内明确外部证据，建议改为 "
         "indeterminable；并建议不要仅因出现在 Map.addLayer 就认定平台预绑定"),
    "Alashanzuoqi_T_Greenup_Dormancy": ("indeterminable",
                                        "仅第 53 行用于 Map.addLayer，没有定义或来源证据；"
                                        "可能是外部导入对象但不能据此直接判定"),
}
A1_45485_NOTES = "标注者口径建议: 严格口径（须源码内明确外部证据）下三项均可标 indeterminable；本转录按标注者主裁定记录"
A2_45485 = {
    "MCD12Q2_North": ("unconsumed", 0, "第 1 行生成带掩膜的影像，但后续未引用、展示或导出"),
    "MCD12Q2": ("analysis_chain", 1, "第 25 行用于 .map(DOY1)，进入物候数据处理链"),
    "DOY1": ("analysis_chain", 1, "第 25 行作为回调函数传入 MCD12Q2.map()"),
    "image": ("analysis_chain", 8, "形参(DOY1)；函数内用于选择波段、读取日期、生成时间影像及复制属性"),
    "QA": ("unconsumed", 0, "读取 QA_Detailed_1，但后续仅在注释掉的代码中出现，没有实际使用"),
    "bitMask_Dormancy_1": ("unconsumed", 0, "位掩码常量仅在已注释的 QA 掩膜表达式中出现"),
    "mask": ("analysis_chain", 1, "用于 Pheno.updateMask(mask)"),
    "time": ("analysis_chain", 2, "用于 Pheno.subtract(time) 和 time.addBands(Pheno)"),
    "year": ("unconsumed", 0, "创建年份影像，但后续未使用"),
    "Pheno": ("analysis_chain", 3, "函数内部局部变量口径: 初始选择物候波段，随后减法、掩膜、类型转换，"
              "并用于返回结果；不含函数外同名变量"),
    "Greenup_1": ("unconsumed", 0, "第 29 行提取波段后未继续使用或展示"),
    "Dormancy_1": ("unconsumed", 0, "第 31 行提取波段后未继续使用或展示"),
    "lai_2003_raw": ("presentation_only", 2, "print 一次、Map.addLayer 一次；按统一口径 return/"
                     "定义表达式内操作不计入，后继直接引用为 2"),
    "img": ("analysis_chain", 1, "map 回调形参；第 39 行通过 ee.Image(img) 转换"),
    "Image_col_2003": ("analysis_chain", 2, "用于 .where() 的输入和 .gt(100) 的比较"),
    "Image_2003": ("analysis_chain", 1, "按统一口径（return 计为一次消费）后继使用数 1。标注者原注: "
                   "未被再次引用，但函数最终返回的是它——按纯后继引用口径为 0，语义上实际进入返回链"),
}
A2_45485_NOTES = ("标注者统一口径裁定（本批起采用）: return 计为一次后继使用（更适合工作流分析）；"
                  "定义表达式内的处理操作不计入后继引用；lai_2003_raw=2（print+addLayer）、"
                  "Image_2003=1（return）。补充审计备注: DOY1 内 QA/bitMask_Dormancy_1/year 未参与"
                  "实际返回；QA 掩膜代码被注释掉不算实际数据处理；实际主链两条 = MCD12Q2→DOY1→Pheno "
                  "与 MCD15A3H→filterDate→map→lai_2003_raw；脚本无显式导出")
A3_45485_LINES = {
    1: "analysis", 3: "analysis", 7: "analysis", 9: "analysis", 13: "analysis",
    15: "analysis", 17: "analysis", 19: "analysis", 21: "analysis", 25: "analysis",
    27: "presentation", 29: "analysis", 31: "analysis", 33: "analysis",
    39: "analysis", 41: "analysis",
    47: "presentation", 49: "presentation", 51: "presentation", 53: "presentation",
}

# ---------------- batch 7: script_100110 A1 + A2 + A3 ----------------
A1_100110 = {
    "LandsatLST": ("external_prebinding",
                   "以 LandsatLST.collection(...) 形式调用，明显具有模块/命名空间对象特征，常见于 EE "
                   "用户脚本的外部代码模块；但源码未展示 require()，无法核实模块路径；若要求数据集提供"
                   "显式来源证据则改标 indeterminable。不建议 missing_definition"),
    "cloudmask": ("external_prebinding",
                  "以 cloudmask.toa 作为 .map() 回调，表现为外部云掩膜模块接口而非普通内置 GEE API；"
                  "源码未见导入语句或定义，不能进一步确认模块来源；严格证据口径下可标 indeterminable。"
                  "不建议 missing_definition"),
}
A2_100110 = {
    "geometry2": ("unconsumed", 0, "定义了墨西哥城范围，但后续未引用"),
    "AddisWoredas": ("unconsumed", 0, "加载行政区 FeatureCollection，后续未使用"),
    "geoBadm2": ("unconsumed", 0, "加载 geoBoundaries 数据，后续未使用"),
    "SVI": ("analysis_chain", 1, "用于构造 citySVI"),
    "AddisLanduse": ("analysis_chain", 1, "用于 AddisLanduseImage 的 paint()"),
    "satellite": ("analysis_chain", 1, "传入 LandsatLST.collection()"),
    "date_start": ("analysis_chain", 3, "用于 LandsatLST 模块调用和两条 TOA 集合的日期过滤"),
    "date_end": ("analysis_chain", 3, "同 date_start"),
    "month_start": ("analysis_chain", 3, "用于三条影像集合链的月份过滤"),
    "month_end": ("analysis_chain", 3, "同 month_start"),
    "use_ndvi": ("analysis_chain", 1, "传入 LandsatLST.collection()"),
    "citySVI": ("analysis_chain", 2, "用于赋值 AOI，并作为 reduceRegions() 的统计区域集合"),
    "AOI": ("analysis_chain", 4, "用于地图定位、LandsatLST 模块调用及两条 TOA 集合的 filterBounds()"),
    "BACKGROUND": ("presentation_only", 1, "用于设置地图底图样式"),
    "ZOOM": ("presentation_only", 1, "用于 Map.centerObject() 的地图缩放参数"),
    "LandsatColl": ("analysis_chain", 4, "用于月份过滤、控制台打印、生成 exImage 及计算 LSTmean"),
    "exImage": ("unconsumed", 0, "qualityMosaic('pixel_qa') 的结果未被后续引用"),
    "albedo": ("analysis_chain", 2, "分别传入 landsatTOAcloudmask 和 landsatTOA 的 .map()"),
    "image": ("analysis_chain", 7, "形参(albedo)；一次 expression()、五次 select() 和一次 addBands()"),
    "alb": ("analysis_chain", 1, "重命名后添加到输入影像"),
    "landsatTOAcloudmask": ("unconsumed", 1, "被赋值给 albedodataset，但该别名也未继续使用；"
                            "属于未接入后续结果的分支；备注保留该引用事实"),
    "landsatTOA": ("unconsumed", 0, "构造并处理 TOA 集合，但后续未引用"),
    "albedodataset": ("unconsumed", 0, "仅引用 landsatTOAcloudmask 赋值，之后未使用"),
    "LSTmean": ("analysis_chain", 1, "用于 reduceRegions() 生成分区统计结果"),
    "LSTlanduse": ("analysis_chain", 4, "用于打印、绘制温度图、重映射及赋值给图表数据变量"),
    "mapdicAddis": ("unconsumed", 0, "字典已创建，但没有被任何后续表达式引用"),
    "AddisLanduseImage": ("unconsumed", 0, "绘制土地利用影像后未被展示或继续使用"),
    "cmap2": ("unconsumed", 0, "调色板定义后未使用"),
    "indexRemappingFunction": ("analysis_chain", 1, "用于生成 equityImage 的输入 FeatureCollection"),
    "collection": ("analysis_chain", 2, "形参(重映射函数)；用于 aggregate_count() 和 remap()"),
    "orig": ("analysis_chain", 1, "作为 remap() 的原始值映射数组"),
    "final": ("analysis_chain", 1, "作为 remap() 的目标值映射数组"),
    "equityImage": ("presentation_only", 1, "仅被 Map.addLayer() 展示；其上游重映射仍执行数据处理"),
    "paletteBlueRed": ("presentation_only", 1, "用于 equityImage 的显示调色板"),
    "minScale": ("presentation_only", 1, "用作 Map.addLayer() 的最小显示值"),
    "maxScale": ("presentation_only", 1, "用作 Map.addLayer() 的最大显示值"),
    "emptyImage": ("analysis_chain", 3, "同一变量名在第 169/195/229 行重复赋值；var 语义下是同一变量的"
                   "重复赋值，三次 paint() 都引用该变量，不拆成三个独立变量"),
    "LSTlanduseImage": ("presentation_only", 1, "仅被 Map.addLayer() 展示"),
    "cmap1": ("presentation_only", 1, "用于温度图层的显示调色板"),
    "data": ("presentation_only", 1, "传入 getTheChart()，用于生成图表数据"),
    "xVals": ("presentation_only", 1, "全局变量传入 getTheChart()；函数内部同名参数属局部作用域"),
    "xValLabels": ("presentation_only", 1, "全局变量传入 getTheChart()"),
    "xField": ("presentation_only", 1, "传入 getTheChart()，指定图表分组字段"),
    "xLabel": ("presentation_only", 1, "传入 getTheChart()，指定横轴标题"),
    "yField": ("presentation_only", 1, "传入 getTheChart()，指定统计字段"),
    "yLabel": ("presentation_only", 1, "传入 getTheChart()，指定纵轴标题"),
    "getTheChart": ("presentation_only", 1, "在 chartPanel.add() 参数中调用，生成图表"),
    "maxValue": ("analysis_chain", 2, "函数内更新最大值并用于设置图表纵轴范围；初始化左值赋值不计使用"),
    "maxMedian": ("analysis_chain", 2, "函数内更新四分位数统计量并用于设置纵轴范围"),
    "minValue": ("analysis_chain", 2, "函数内更新最小值；后续没有用于最终图表配置，主要是中间统计变量"),
    "minMedian": ("analysis_chain", 2, "函数内更新四分位数统计量；后续没有用于最终图表配置"),
    "myRows": ("presentation_only", 1, "作为 myDataTable.rows 的值，构建图表行数据"),
    "label": ("analysis_chain", 1, "xVals.map() 形参；用于筛选 data 中对应分组"),
    "i": ("analysis_chain", 1, "xVals.map() 形参；用于按索引读取 xValLabels[i]"),
    "stats": ("analysis_chain", 9, "读取多个百分位统计值，生成图表行和统计范围"),
    "myDataTable": ("presentation_only", 1, "传入 ui.Chart()"),
    "chart": ("presentation_only", 1, "作为 getTheChart() 的返回值交给面板展示"),
    "chartPanel": ("presentation_only", 3, "用于设置样式、添加图表和添加到地图界面"),
}
A2_100110_NOTES = ("标注者口径: return/函数调用/对象属性引用均属实际消费；同名 emptyImage 按 var 语义"
                   "视为同一变量重复赋值；landsatTOAcloudmask 虽有别名赋值引用但别名链无下游消费 → "
                   "unconsumed；maxValue/maxMedian/minValue/minMedian/stats 计数不含初始化左值。"
                   "脚本无显式 Export.*；主要输出为地图图层与图表面板；getInfo() 为同步客户端取值，"
                   "用于图表统计行构造，不属导出")
A3_100110_LINES = {
    1: "analysis", 13: "analysis", 23: "analysis", 25: "analysis", 27: "analysis",
    29: "analysis", 43: "analysis", 45: "analysis",
    55: "presentation", 57: "presentation",
    59: "analysis", 61: "analysis", 63: "presentation", 67: "analysis",
    73: "analysis", 79: "analysis", 81: "analysis", 83: "analysis", 85: "analysis",
    87: "analysis", 91: "analysis", 95: "analysis", 97: "analysis", 101: "analysis",
    107: "analysis", 113: "analysis", 121: "analysis", 123: "analysis",
    125: "presentation", 127: "analysis",
    169: "analysis", 171: "analysis", 181: "presentation", 183: "presentation",
    185: "presentation", 191: "analysis", 195: "analysis", 197: "analysis",
    199: "analysis", 227: "presentation", 229: "analysis", 231: "analysis",
    239: "presentation", 265: "presentation", 267: "analysis", 269: "analysis",
    273: "analysis", 333: "presentation", 411: "presentation", 413: "presentation",
    421: "presentation", 423: "presentation",
}

# ---------------- batch 8: script_100133 A1 + A2 + A3 ----------------
A1_100133 = {
    "HIGH_LEVEL": ("indeterminable", "用作 filter() 的输入，可能是外部导入的 FeatureCollection，"
                   "但源码无定义、导入或注释证据"),
    "ABEGs": ("indeterminable", "用作 filter() 的输入，可能是外部导入的 FeatureCollection，"
              "但缺少可验证的外部绑定证据"),
    "AddisResPcts": ("indeterminable", "被赋值给 AOI，后续用于空间过滤、统计和地图绘制；源码未说明其来源"),
    "PM25r": ("indeterminable", "被打印、按 system:index 过滤并参与区域统计；可能是外部影像集合，"
              "但源码未给出定义或导入"),
    "CdMxISU": ("indeterminable", "传入 indexRemappingFunction()，用于重映射和绘制；没有源码证据确定其来源"),
    "ULU2020": ("indeterminable", "调用 filterBounds(AOI) 并添加地图图层；可能是外部影像集合，"
                "但没有定义或导入证据"),
}
A1_100133_NOTES = ("标注者统一口径: 以上变量都可能来自 Code Editor Imports 或其他外部环境，但仅凭当前源码"
                   "无法证实，统一标 indeterminable 而非直接判 external_prebinding；若项目已有经核实的"
                   "统一规则（特定 Imports 变量视为外部预绑定），应按该规则一致调整")
A2_100133 = {
    "CdMxmunis": ("analysis_chain", 1, "用作 reduceRegions() 的统计区域集合"),
    "CdMxABEGs": ("unconsumed", 0, "筛选后没有后续引用；当前主统计链未使用它"),
    "AOI": ("analysis_chain", 5, "用于地图定位、reduceRegions、filterBounds、Ppctfills 绘制及 AOIimage 绘制"),
    "BACKGROUND": ("presentation_only", 1, "仅用于设置地图底图"),
    "PM25rfiltered": ("analysis_chain", 4, "用于打印、两次区域统计映射，以及 PM2.5 图层展示"),
    "image": ("analysis_chain", 1, "第 25 行回调形参；该回调内调用 image.reduceRegions()。"
              "第 41 行同名参数是另一独立作用域"),
    "reducedM": ("analysis_chain", 1, "传入 flatten()，生成 muniFeaturesR"),
    "muniFeaturesR": ("analysis_chain", 2, "用于打印首个要素，并作为 Mfills.paint() 的输入；"
                      "但 Mfills 本身未添加到地图"),
    "reducedA": ("analysis_chain", 1, "传入 flatten()，生成 ABEGFeaturesR"),
    "ABEGFeaturesR": ("analysis_chain", 6, "用于打印、绘制输入、均值统计、图表数据赋值、相关性计算和排序"),
    "paletteBlueRed": ("unconsumed", 0, "定义后未引用"),
    "paletteMono": ("unconsumed", 0, "定义后未引用"),
    "minScale": ("unconsumed", 0, "定义后未引用"),
    "maxScale": ("unconsumed", 0, "定义后未引用"),
    "indexRemappingFunction": ("analysis_chain", 1, "用于 equityImage 的要素属性重映射"),
    "collection": ("analysis_chain", 3, "函数形参；用于两次调试输出和一次 remap()"),
    "orig": ("analysis_chain", 1, "作为 remap() 的原始分类值"),
    "final": ("analysis_chain", 1, "作为 remap() 的目标分类值"),
    "emptyImage": ("analysis_chain", 1, "用于构造 equityImage"),
    "equityImage": ("unconsumed", 0, "虽然完成了绘制对象构造，但没有被 Map.addLayer() 或其他下游调用使用"),
    "CLASSES_7": ("analysis_chain", 1, "赋值给 CLASSES，用于图例构造"),
    "COLORS_7": ("analysis_chain", 1, "赋值给 colors，用于图层配色和图例"),
    "CLASSES": ("presentation_only", 1, "传给 legend.build()"),
    "colors": ("presentation_only", 2, "用于图层参数和图例构造"),
    "ULUfiltered": ("presentation_only", 1, "筛选后仅添加为地图图层"),
    "legend": ("presentation_only", 2, "用于构建土地利用图例和 PM2.5 图例"),
    "ULUlgnd": ("presentation_only", 1, "传给 Map.add()"),
    "Mfills": ("unconsumed", 0, "虽然由 muniFeaturesR 绘制得到，但没有后续展示或计算引用"),
    "Ppctfills": ("presentation_only", 1, "添加到地图显示非正规用地居住人口比例"),
    "YEAR": ("analysis_chain", 1, "用于计算 BANDnum"),
    "BANDnum": ("analysis_chain", 1, "用于生成影像波段名 BAND"),
    "BAND": ("analysis_chain", 2, "用于构建黑碳和二氧化硫图层的可视化参数"),
    "BCimage": ("presentation_only", 1, "仅用于地图展示"),
    "SO2image": ("presentation_only", 1, "仅用于地图展示"),
    "BCimageVisParam": ("presentation_only", 1, "仅用于黑碳图层的可视化参数"),
    "SO2imageVisParam": ("presentation_only", 1, "仅用于二氧化硫图层的可视化参数"),
    "MIN": ("analysis_chain", 2, "用于 PM25params 和 AQrange"),
    "MAX": ("analysis_chain", 2, "用于 PM25params 和 AQrange"),
    "Afills": ("presentation_only", 1, "添加为 Woreda PM2.5 地图图层"),
    "AQrange": ("presentation_only", 1, "标注者自纠: 原稿误写 presentation_chain，此状态应填 "
                "presentation_only；仅用于构建 PM2.5 图例"),
    "empty": ("analysis_chain", 4, "同一作用域内多次重赋值，后续用于 Mfills、Ppctfills、Afills 和 "
              "AOIimage 的绘制"),
    "AOIimage": ("presentation_only", 1, "添加为边界图层"),
    "G_CATEGORIES": ("unconsumed", 0, "定义后未引用"),
    "G_COLORS": ("analysis_chain", 1, "用于配置 VIZ"),
    "G_MAX": ("analysis_chain", 1, "用于配置 VIZ 的最大值"),
    "VIZ": ("unconsumed", 0, "配置对象未被后续调用使用"),
    "data": ("presentation_only", 1, "作为参数传入 getTheChart()，用于生成统计图表"),
    "xVals": ("presentation_only", 1, "作为参数传入 getTheChart()，用于生成图表行"),
    "xValLabels": ("presentation_only", 1, "作为参数传入 getTheChart()，用于图表横轴标签"),
    "xField": ("presentation_only", 1, "作为参数传入 getTheChart()，指定分组字段"),
    "xLabel": ("presentation_only", 1, "作为参数传入 getTheChart()，指定横轴标题"),
    "yField": ("presentation_only", 1, "作为参数传入 getTheChart()，指定统计字段"),
    "yLabel": ("presentation_only", 1, "作为参数传入 getTheChart()，指定纵轴标题"),
    "getTheChart": ("presentation_only", 1, "调用一次，生成并加入图表面板"),
    "maxValue": ("presentation_only", 4, "函数内更新最大统计值，并用于确定图表纵轴范围"),
    "maxMedian": ("presentation_only", 4, "函数内更新四分位数相关的最大值，并用于确定图表纵轴范围"),
    "myRows": ("presentation_only", 1, "用于构建图表数据表的 rows"),
    "label": ("analysis_chain", 1, "第 305 行回调形参；用于按当前分类值过滤数据"),
    "i": ("presentation_only", 1, "第 305 行回调形参；用于索引横轴标签"),
    "stats": ("presentation_only", 12, "由 reduceColumns() 和 getInfo() 获取统计量，"
              "后续用于构造图表数据和提示信息"),
    "myDataTable": ("presentation_only", 1, "传入 ui.Chart()"),
    "binary": ("analysis_chain", 1, "保存皮尔逊相关性计算结果，随后打印"),
    "pop_pctsFiltSort": ("analysis_chain", 1, "排序结果传给散点图构造函数"),
    "chart": ("presentation_only", 1, "第 369 行函数局部变量: 返回生成的图表对象；与第 473 行全局 chart "
              "是不同作用域的绑定"),
    "chartPanel": ("presentation_only", 3, "第 447 与 509 行重复声明；var 不创建新块级绑定，第二次赋值"
                   "覆盖原面板对象——第一个面板中的箱线图不会通过最后的 Map.add(chartPanel) 展示，"
                   "最终可见的是第二个面板中的散点图"),
}
A2_100133_NOTES = ("标注者补充审计: (1) 主分析链 PM25r→PM25rfiltered→reduceRegions→flatten→"
                   "ABEGFeaturesR→统计/相关性/图表; (2) 疑似未消费分支 CdMxABEGs/equityImage/Mfills/VIZ "
                   "——不因构造语句含分析 API 就认定输出已被消费; (3) 第 307 行 getInfo() 同步取值服务于"
                   "图表统计，不是地图展示调用; (4) 结构问题: CdMxABEGs 未用于区域统计、equityImage 未展示、"
                   "第 447 行 chartPanel 被同名覆盖——记录为未消费结果或潜在逻辑缺陷，不影响 A3 角色分类")
A3_100133_LINES = {
    1: "analysis", 3: "analysis", 5: "analysis", 7: "analysis",
    13: "presentation", 17: "presentation", 19: "presentation", 21: "analysis",
    23: "presentation", 25: "analysis", 27: "analysis", 31: "analysis",
    37: "analysis", 39: "presentation", 41: "analysis", 43: "analysis",
    47: "analysis", 53: "analysis", 55: "presentation",
    97: "presentation", 99: "presentation", 105: "analysis", 109: "analysis",
    111: "analysis", 113: "analysis",
    153: "analysis", 155: "presentation",
    # 157 handled per-unit (require -> unknown)
    159: "presentation", 161: "presentation", 163: "analysis", 165: "analysis",
    173: "analysis", 175: "analysis", 187: "presentation", 195: "analysis",
    197: "analysis", 201: "presentation", 205: "presentation", 215: "presentation",
    217: "analysis", 219: "analysis", 227: "presentation", 231: "presentation",
    233: "presentation", 235: "analysis", 237: "analysis", 245: "presentation",
    275: "analysis", 277: "analysis", 305: "analysis", 307: "analysis",
    309: "analysis", 313: "analysis", 369: "presentation", 447: "presentation",
    449: "presentation", 457: "presentation", 461: "analysis", 463: "analysis",
    469: "presentation", 471: "analysis", 475: "presentation", 509: "presentation",
    511: "presentation", 519: "presentation", 521: "presentation",
}
A3_100133_UNITS = {}
# line 157: require('users/brookwilliams/utils:apps/legend') -> unknown (annotator ruled)
# resolve which unit(s) sit on line 157 via the frozen blind-unit lines map:
# filled at runtime below (all line-157 units get 'unknown').

# ---------------- batch 9: script_100145 A1 + A2 + A3 ----------------
_A1_100145_VARS = [
    "MAXbuiltup_density", "GHSL2pctBD", "GHSL2pctUErem", "GHSL2pctUEshanghai",
    "GHSL2pctUElarge", "GHSL5pctBD", "GHSL5pctUE2015", "GHSL10pctBD",
    "GHSL10pctUE2015", "GHSLbuiltup_density", "GHSLue", "aue_ue",
    "AUEuniverse", "KigaliBD", "KigaliUE",
]
A1_100145 = {
    v: ("indeterminable",
        "源码无定义或导入证据；不足以区分外部预绑定与定义遗漏"
        + ("（仅用于 yearfilter()）" if v.startswith("GHSL") and v != "GHSLue"
           else "（仅在 Map.addLayer() 中引用）" if v in ("aue_ue", "AUEuniverse")
           else "（作为 testcityfilter() 的输入使用）" if v == "MAXbuiltup_density"
           else "（在 FeatureCollection 数组中引用）"))
    for v in _A1_100145_VARS
}
A1_100145_NOTES = ("标注者总体判断: 15 个候选均 indeterminable——当前源码能证明其未声明，但不足以"
                   "区分外部预绑定与定义遗漏；若取得原始 GEE 脚本导入区或项目元数据可再复核")
A2_100145 = {
    "GHSL": ("analysis_chain", 1, "用于构造 BU_GHSL"),
    "WSF": ("analysis_chain", 1, "用于构造 BU_WSF"),
    "WSF19": ("analysis_chain", 1, "用于构造 BU_WSF19"),
    "DW": ("analysis_chain", 1, "用于构造 BU_DW"),
    "WC21": ("analysis_chain", 1, "用于构造 BU_WC21"),
    "BU_GHSL": ("unconsumed", 0, "虽然完成了影像处理，但没有被后续引用"),
    "BU_WSF": ("analysis_chain", 1, "被 BU 的影像集合使用"),
    "BU_WSF19": ("analysis_chain", 1, "被 BU 的影像集合使用"),
    "BU_DW": ("unconsumed", 0, "构造后未被引用；没有进入 BU 集合"),
    "BU_WC21": ("analysis_chain", 1, "被 BU 的影像集合使用"),
    "BU": ("unconsumed", 0, "汇总多种建成区数据后，没有后续引用"),
    "wsf_evo": ("analysis_chain", 1, "用于生成 wsf_evoImg"),
    "wsf_evoImg": ("unconsumed", 0, "生成后未被后续引用"),
    "GHSL2023release": ("analysis_chain", 5, "被多个 GHSL2023releaseYear 计算表达式引用；"
                        "按不同阈值重复生成年度建成区结果"),
    "count": ("analysis_chain", 5, "多次作为 remap() 的参数"),
    "toyear": ("analysis_chain", 5, "多次作为 remap() 的参数"),
    "test_cities": ("analysis_chain", 1, "在 testcityfilter() 函数体中作为过滤条件使用"),
    "IC": ("analysis_chain", 3, "visfilter 形参；函数内被赋值、读取并返回（按函数体参数口径计数）"),
    "visfilter": ("analysis_chain", 6, "在多个建成区处理分支中被调用"),
    "testcityfilter": ("analysis_chain", 1, "用于生成 maxbud"),
    "dataset": ("presentation_only", 1, "只传给 Map.addLayer() 展示人口数据"),
    "visualization": ("presentation_only", 1, "仅作为人口图层的显示参数"),
    "maxbud": ("analysis_chain", 2, "由 testcityfilter(MAXbuiltup_density) 赋值后作为 "
               "visfilter(maxbud) 输入；其源输入未定义，存在运行失败风险"),
    "yearfilter": ("analysis_chain", 7, "被多个年份/建成区数据处理分支调用"),
    "year": ("analysis_chain", 11, "用于影像掩膜、过滤和图层名称等；源码中多次重新赋值"),
    "GHSL2023releaseYear": ("analysis_chain", 4, "多次声明/赋值，后续作为 GHSLyear 的输入；"
                            "同名变量在同一作用域内被反复覆盖"),
    "GHSLyear": ("presentation_only", 5, "每个阈值分支中用于 Map.addLayer()；其值由最近一次赋值决定"),
    "GHSLbud": ("presentation_only", 9, "在多个分支中调用 yearfilter()/visfilter() 后展示分类图层；"
                "同名赋值覆盖前值"),
    "GHSLueyear": ("presentation_only", 8, "用于地图展示，并在末尾缓冲处理后再次展示；"
                   "其来源在前面分支中存在差异"),
    "feat": ("analysis_chain", 1, "map 回调形参；用于 feat.buffer(50) 并通过 return 返回"),
}
A2_100145_NOTES = ("标注者特别注意事项: (1) GHSLueyear 首次来源与后续覆盖——2% 分支组合了三个未声明变量，"
                   "最后 map 依赖当前变量值而非保留各分支独立结果; (2) GHSLbud 自引用风险——"
                   "var GHSLbud = visfilter(GHSLbud) 右侧读取当前绑定值，var 无块级作用域，"
                   "结合未声明输入可能导致执行错误; (3) GHSL2023releaseYear/GHSLyear 被反复覆盖，"
                   "保留各阈值结果应使用不同变量名; (4) BU/BU_GHSL/BU_DW/wsf_evoImg 构造后未使用，"
                   "不因含分析操作就判入分析链; (5) GHSLyear/GHSLbud 主要服务于展示。"
                   "计数说明: 重复赋值变量按同名绑定整体统计，数值用于使用审计而非计算图节点数")
A3_100145_LINES = {
    1: "analysis", 3: "analysis", 5: "analysis", 7: "analysis", 9: "analysis",
    11: "analysis", 13: "analysis", 15: "analysis", 17: "analysis", 19: "analysis",
    21: "analysis", 31: "analysis", 33: "analysis", 35: "analysis", 37: "analysis",
    69: "analysis", 71: "analysis", 79: "analysis", 87: "analysis", 93: "analysis",
    107: "presentation", 109: "analysis", 111: "analysis", 115: "analysis",
    117: "analysis", 119: "presentation", 121: "analysis", 123: "analysis",
    125: "presentation", 127: "analysis", 131: "analysis", 133: "analysis",
    135: "presentation", 137: "analysis", 139: "analysis", 141: "presentation",
    143: "analysis", 147: "analysis", 149: "analysis", 151: "presentation",
    153: "analysis", 155: "analysis", 157: "presentation", 159: "analysis",
    161: "presentation", 165: "analysis", 167: "analysis", 169: "presentation",
    171: "analysis", 173: "analysis", 175: "presentation", 177: "analysis",
    179: "presentation", 181: "presentation", 185: "analysis", 193: "analysis",
    195: "analysis", 197: "presentation", 199: "analysis", 201: "analysis",
    203: "presentation", 205: "analysis", 207: "presentation", 209: "analysis",
    211: "presentation",
}

# ---------------- batch 10: script_100870 A1 + A2 + A3 ----------------
A1_100870 = {
    "geometry5": ("indeterminable",
                  "当前源码中没有定义、require() 或注释等来源证据；可能来自 Code Editor Imports "
                  "或遗漏定义；仅凭 filterBounds()/reduceRegion() 的使用无法确认"),
}
A2_100870 = {
    "date_1": ("analysis_chain", 4, "在四个 filterDate() 调用中使用，参与日期过滤"),
    "date_2": ("analysis_chain", 4, "在四个 filterDate() 调用中使用，参与日期过滤"),
    "year_cur": ("analysis_chain", 4, "在四个 filterDate() 调用中使用，参与日期拼接"),
    "collTOres": ("analysis_chain", 7, "四次初始化后的集合分别进入过滤、选择和统计流程；最后一次集合还"
                  "用于 map()、图表及点击回调筛选。按同一全局绑定统计引用，未把赋值左侧算作读取。"
                  "标注者审计: 重复赋值覆盖此前集合，图表实际使用的是 Rrs_412 集合而非前三个变量对应集合"),
    "collTOres_im": ("analysis_chain", 4, "标注者自纠: 四个统计区块重复赋值，按区块累计为 4 而非 1；"
                     "每次由集合 reduce() 得到后传给 reduceRegion()"),
    "collTOres_im_mean": ("analysis_chain", 4, "标注者自纠: 四区块累计 4；每次 reduceRegion() 结果均被"
                          "下一行 get() 读取"),
    "mean_cur": ("presentation_only", 4, "标注者自纠: 四区块累计 4；每次提取统计值后都传给对应 print()"),
    "chart": ("presentation_only", 3, "用于设置样式、添加到地图，以及注册点击回调"),
    "label": ("presentation_only", 1, "仅用于 Map.add(label) 展示提示文字"),
    "xValue": ("analysis_chain", 2, "点击回调形参：用于空值判断及构建时间过滤条件"),
    "yValue": ("unconsumed", 0, "点击回调形参未被使用"),
    "seriesName": ("unconsumed", 0, "点击回调形参未被使用"),
    "equalDate": ("analysis_chain", 1, "用于 collTOres.filter(equalDate) 筛选对应日期影像"),
    "image": ("analysis_chain", 1, "用于构造 ui.Map.Layer 的影像输入。标注者审计: "
              "image.divide(1).select([0],['l3smi']) 只是把首个波段重命名为 l3smi——集合此前选择的是 "
              "Rrs_412，图表实际绘制该波段时间序列，不能认为数据是 L3SMI 原始专用波段"),
    "l8Layer": ("presentation_only", 1, "传入 Map.layers().reset([l8Layer])，用于更新地图显示"),
}
A2_100870_NOTES = ("标注者口径: 函数形参按各自局部作用域单独计数，不同作用域同名变量不合并；重复 var 声明"
                   "按同一作用域绑定处理；四统计区块中重复赋值变量（collTOres_im/collTOres_im_mean/"
                   "mean_cur）按区块累计。两处审计备注: (1) collTOres 重复赋值覆盖——图表实际使用 "
                   "Rrs_412 集合; (2) 波段重命名核验——l3smi 仅为名称，数据实为 Rrs_412")
A3_100870_LINES = {
    7: "analysis", 15: "analysis", 17: "analysis", 19: "analysis", 27: "analysis",
    29: "presentation", 31: "analysis", 39: "analysis", 41: "analysis",
    43: "analysis", 51: "analysis", 53: "presentation", 55: "analysis",
    63: "analysis", 65: "analysis", 67: "analysis", 75: "analysis",
    77: "presentation", 79: "analysis", 87: "analysis", 89: "analysis",
    91: "analysis", 99: "analysis", 101: "presentation", 103: "analysis",
    105: "analysis", 109: "presentation", 111: "analysis", 115: "analysis",
    121: "presentation", 131: "presentation", 133: "presentation",
    135: "presentation", 137: "presentation", 141: "analysis", 143: "analysis",
    145: "presentation", 155: "presentation",
}

# ---------------- batch 11: script_100916 A2 + A3 ----------------
A2_100916 = {
    "polygon": ("analysis_chain", 2, "用于 filterBounds(polygon) 和 clip(polygon)，参与影像筛选与裁剪"),
    "DayStart": ("analysis_chain", 2, "用于构造 DayAfterEnd，并在 Map.addLayer() 的图层名称中使用。"
                 "兼具分析参数和展示标签作用，主状态取 analysis_chain"),
    "sceneID": ("analysis_chain", 1, "用于 if (sceneID === '') 条件判断，控制是否执行影像处理分支。"
                "当前为空字符串，本次执行进入处理分支；若设为非空则分支被跳过"),
    "DayAfterEnd": ("analysis_chain", 1, "用于 filterDate(DayStart, DayAfterEnd)，作为日期过滤的结束时间"),
    "SENT2parameter": ("analysis_chain", 1, "用于 .select(SENT2parameter)，选择 Sentinel-2 的 B4/B3/B2 波段"),
    "datasetTRUECs2": ("presentation_only", 2, "处理结果分别用于 print 和 Map.addLayer，"
                       "没有进入后续分析或导出链"),
}
A2_100916_NOTES = ("标注者审计: datasetTRUECs2 处理链 = S2_SR 加载→日期过滤→研究区过滤→云量过滤→"
                   "选择 B4/B3/B2→mosaic→clip；Map.addLayer 标签写 SENTINEL-1 但数据源是 S2_SR——"
                   "属图层命名不一致，不是数据源变化（重建冲突登记素材）")
A3_100916_LINES = {
    1: "analysis", 9: "presentation", 23: "presentation", 25: "analysis",
    39: "presentation", 41: "presentation",
}

# ---------------- batch 12: script_101051 A2 + A3 ----------------
A2_101051 = {
    "regions": ("analysis_chain", 1, "作为 ui.Chart.image.seriesByRegion() 的区域输入，参与分区统计"),
    "temps2013": ("analysis_chain", 1, "作为 seriesByRegion() 的影像集合输入，参与时间序列统计"),
    "tempTimeSeries": ("presentation_only", 1, "传入 print() 输出图表；没有进入后续分析或导出链"),
}
A2_101051_NOTES = ("标注者口径: regions/temps2013 虽最终服务于图表，但参与了实际数据统计计算，"
                   "状态应为 analysis_chain，不能仅因最终产物是图表就标 presentation_only。"
                   "另注: BAND 'B11' 与历史数据集 LANDSAT/LC8_L1T_32DAY_TOA 的匹配性需另行核验数据集文档")
A3_101051_LINES = {
    1: "analysis", 3: "analysis", 5: "analysis", 7: "analysis", 9: "analysis",
    11: "analysis", 13: "analysis", 17: "analysis", 23: "presentation",
    25: "analysis", 49: "presentation",
}

# ---------------- batch 13: script_101095 A2 + A3 ----------------
A2_101095 = {
    "imgVV": ("analysis_chain", 2, "分别用于构建降轨集合 desc 和升轨集合 asc"),
    "image": ("analysis_chain", 4, ".map() 回调形参；用于 image.lt()/image.mask()/image.updateMask()"
              "并作为 updateMask 的接收对象，按实际标识符引用计数为 4"),
    "edge": ("analysis_chain", 1, "用于 edge.not()，参与边缘掩膜构建"),
    "maskedImage": ("analysis_chain", 1, "用于 image.updateMask(maskedImage)"),
    "desc": ("analysis_chain", 3, "分别用于春季、晚春和夏季三个时段的过滤及均值计算"),
    "asc": ("analysis_chain", 3, "分别用于春季、晚春和夏季三个时段的过滤及均值计算"),
    "spring": ("analysis_chain", 2, "分别用于 desc.filter(spring) 和 asc.filter(spring)"),
    "lateSpring": ("analysis_chain", 2, "分别用于 desc.filter(lateSpring) 和 asc.filter(lateSpring)"),
    "summer": ("analysis_chain", 2, "分别用于 desc.filter(summer) 和 asc.filter(summer)"),
    "descChange": ("presentation_only", 1, "仅用于 Map.addLayer() 显示降轨合成影像。虽进入分析处理链，"
                   "但后继用途仅是地图显示，按最终消费用途标 presentation_only"),
    "ascChange": ("presentation_only", 1, "仅用于 Map.addLayer() 显示升轨合成影像；同 descChange 口径"),
}
A2_101095_NOTES = ("标注者审计: ee.Image.cat() 将三个时段均值影像合并为多波段影像，不是计算变化差值——"
                   "图层名称中的 Change 不代表代码实际计算了相邻时段差分（名称≠语义，重建登记素材）")
A3_101095_LINES = {
    1: "analysis", 3: "analysis", 5: "analysis", 11: "analysis", 13: "analysis",
    15: "analysis", 19: "analysis", 21: "analysis", 23: "analysis", 25: "analysis",
    27: "analysis", 29: "analysis", 31: "analysis", 33: "analysis", 35: "analysis",
    37: "analysis", 39: "analysis", 41: "analysis", 43: "analysis",
    45: "presentation", 47: "presentation", 49: "presentation",
}

# ---------------- batch 14: script_101218 A2 + A3 ----------------
A2_101218 = {
    "BA": ("analysis_chain", 3, "三处 filterBounds(BA)；filterMetadata 和 geometry(200) 是定义表达式"
           "内的链式调用，不计为定义之后的引用"),
    "L8_2016": ("analysis_chain", 1, "用于构建 L8_16_filt"),
    "L8_2017": ("analysis_chain", 1, "用于构建 L8_17_filt"),
    "L8_2018": ("analysis_chain", 1, "用于构建 L8_18_filt"),
    "func_FiltroNube": ("analysis_chain", 3, "分别传入三个年度集合的 map"),
    "imagen": ("analysis_chain", 3, "函数形参（局部作用域）；select、mask 的接收对象、return 表达式中"
               "的 imagen——mask 接收对象在 return 表达式中属同一处调用不重复计数，严格标识符出现次数为 3"),
    "bqa": ("analysis_chain", 1, "用于构建云掩膜条件 bqa.eq(2720)；是否正确识别云像元取决于数据集质量"
            "波段编码，不影响 A3 角色"),
    "mask": ("analysis_chain", 1, "传入 imagen.mask(mask)"),
    "L8_16_filt": ("analysis_chain", 1, "用于计算 2016 年中位数合成"),
    "L8_17_filt": ("analysis_chain", 1, "用于计算 2017 年中位数合成"),
    "L8_18_filt": ("analysis_chain", 1, "用于计算 2018 年中位数合成"),
    "L8_2016_mediana": ("analysis_chain", 1, "放入最终的 L8IC 影像集合"),
    "L8_2017_mediana": ("analysis_chain", 1, "放入最终的 L8IC 影像集合"),
    "L8_2018_mediana": ("analysis_chain", 1, "放入最终的 L8IC 影像集合"),
    "L8IC": ("presentation_only", 1, "仅传给 print 展示，没有继续进入分析或导出链"),
}
A3_101218_LINES = {
    1: "analysis", 7: "analysis", 13: "analysis", 19: "analysis", 27: "analysis",
    29: "analysis", 31: "analysis", 35: "analysis", 37: "analysis", 39: "analysis",
    41: "analysis", 43: "analysis", 45: "analysis", 47: "analysis",
    49: "presentation",
}

# ---------------- batch 15: script_101353 A1 + A2 + A3 ----------------
A1_101353 = {
    "geometry": ("indeterminable",
                 "源码中 12 次调用 .clip(geometry)，但完整脚本没有 geometry 的定义、require 或注释证据；"
                 "无法确认来自 EE Imports 预绑定还是遗漏定义"),
}
A1_101353_NOTES = ("跨样本对照: script_35821 的 geometry 判 external_prebinding（多行使用+定位用途），"
                   "本脚本 geometry 判 indeterminable——标注者按逐样本证据独立裁定，两条判例已并列登记")
A2_101353 = {
    "map1": ("presentation_only", 6, "标注者自纠: 7→6，后继引用为 add/addLayer/setControlVisibility/"
             "Linker 数组/ui.Panel 布局/setCenter 共 6 处"),
    "map2": ("presentation_only", 5, "标签、图层、控件、Linker、mapPanel 共 5 处"),
    "map3": ("presentation_only", 5, "同 map2 口径"),
    "map4": ("presentation_only", 5, "同 map2 口径"),
    "map5": ("presentation_only", 5, "同 map2 口径"),
    "map6": ("presentation_only", 5, "同 map2 口径"),
    "map7": ("presentation_only", 5, "标注者自纠: 4→5（标签、图层、控件、Linker、mapPanel）"),
    "map8": ("presentation_only", 5, "标注者自纠: 4→5"),
    "map9": ("presentation_only", 5, "标注者自纠: 4→5"),
    "map10": ("presentation_only", 5, "标注者自纠: 4→5"),
    "map11": ("presentation_only", 5, "标注者自纠: 4→5"),
    "map12": ("presentation_only", 5, "标注者自纠: 4→5"),
    "modis_chlor_a": ("presentation_only", 1, "12 个重复声明区块中各使用一次（按各自声明后的局部引用统计）。"
                      "标注者注明: 若系统将重复 var 视为同一绑定则应合并计 12 次——本模板单位为文件级绑定，"
                      "计数口径留待开封统一（对照 emptyImage 判例: 100110 按同绑定合并计 3）"),
    "linker": ("unconsumed", 0, "创建地图联动对象后未再引用；创建时传入的地图列表不计作 linker 的后继使用"),
    "mapPanel": ("presentation_only", 1, "传入 ui.root.widgets().reset(...)，用于界面展示"),
    "title": ("presentation_only", 1, "传入 ui.root.widgets().reset(...)，用于界面展示"),
    "colorBar": ("presentation_only", 1, "放入 legendPanel，用于图例展示"),
    "legendLabels": ("presentation_only", 1, "放入 legendPanel，用于图例标签展示"),
    "legendTitle": ("presentation_only", 1, "放入 legendPanel，用于图例标题展示"),
    "legendPanel": ("presentation_only", 1, "传入 ui.root.widgets().reset(...)，用于界面展示"),
}
A2_101353_NOTES = ("标注者计数口径: map1–map12 均服务地图展示与界面布局 → presentation_only；"
                   "构造函数参数不计后继（linker 判例）；行 323 的 pixelLonLat().select(0) 属图例色带"
                   "流程但调用本身是影像创建与波段选择 → analysis（API 自身角色不被最终消费场景改变）")
A3_101353_ANALYSIS = {
    5, 7, 9, 27, 29, 31, 49, 51, 53, 71, 73, 75, 93, 95, 97, 115, 117, 119,
    137, 139, 141, 159, 161, 163, 181, 183, 185, 203, 205, 207, 225, 227, 229,
    247, 249, 251, 323,
}
A3_101353_LINES = {}
for _l in [1, 3, 5, 7, 9, 19, 21, 23, 25, 27, 29, 31, 41, 43, 45, 47, 49, 51, 53,
           63, 65, 67, 69, 71, 73, 75, 85, 87, 89, 91, 93, 95, 97, 107, 109, 111,
           113, 115, 117, 119, 129, 131, 133, 135, 137, 139, 141, 151, 153, 155,
           157, 159, 161, 163, 173, 175, 177, 179, 181, 183, 185, 195, 197, 199,
           201, 203, 205, 207, 217, 219, 221, 223, 225, 227, 229, 239, 241, 243,
           245, 247, 249, 251, 261, 263, 265, 267, 271, 273, 275, 277, 279, 281,
           285, 287, 289, 321, 323, 325, 331, 335, 337, 343, 347, 351, 359, 361,
           363]:
    A3_101353_LINES[_l] = "analysis" if _l in A3_101353_ANALYSIS else "presentation"

# ---------------- batch 16: script_102167 A2 + A3 ----------------
A2_102167 = {
    "countries": ("analysis_chain", 1, "在 Brazil 的定义表达式中用于筛选国家边界"),
    "Brazil": ("analysis_chain", 2, "标注者修正: 既用于 Map.centerObject 定位也进入 "
               "collection.filterBounds(Brazil) 影像筛选 → analysis_chain（初稿 presentation_only "
               "已由标注者自行更正）"),
    "collection": ("analysis_chain", 2, "分别传入默认合成和自定义合成的 simpleComposite；"
                   "定义表达式内的引用不计（第 5 行定义后于第 11、14 行各引用一次）"),
    "composite": ("presentation_only", 1, "仅传入 Map.addLayer 展示"),
    "customComposite": ("presentation_only", 1, "仅传入 Map.addLayer 展示"),
}
A3_102167_LINES = {
    1: "analysis", 3: "analysis", 5: "analysis", 11: "analysis", 13: "analysis",
    23: "presentation", 25: "presentation", 27: "presentation",
}

# ---------------- batch 17+18: script_102466 / script_102794 (identical source) ----------------
A2_S1GRD = {
    "imgVV": ("analysis_chain", 2, "分别用于构建 desc 和 asc 两个轨道方向的影像集合"),
    "image": ("analysis_chain", 3, "回调形参；image.lt(-30.0)/image.mask()/image.updateMask()"
              "各一次；不额外把 return 计为变量引用"),
    "edge": ("analysis_chain", 1, "用于 edge.not()，参与掩膜构建"),
    "maskedImage": ("analysis_chain", 1, "用于 image.updateMask(maskedImage)"),
    "desc": ("analysis_chain", 3, "分别用于三个季节时段的筛选与均值计算"),
    "asc": ("analysis_chain", 3, "分别用于三个季节时段的筛选与均值计算"),
    "spring": ("analysis_chain", 2, "用于 desc.filter(spring) 和 asc.filter(spring)"),
    "lateSpring": ("analysis_chain", 2, "用于 desc.filter(lateSpring) 和 asc.filter(lateSpring)"),
    "summer": ("analysis_chain", 2, "用于 desc.filter(summer) 和 asc.filter(summer)"),
    "descChange": ("presentation_only", 1, "仅用于 Map.addLayer 展示"),
    "ascChange": ("presentation_only", 1, "仅用于 Map.addLayer 展示"),
}
A3_S1GRD_LINES = {
    1: "analysis", 3: "analysis", 5: "analysis", 11: "analysis", 13: "analysis",
    15: "analysis", 19: "analysis", 21: "analysis", 23: "analysis", 25: "analysis",
    27: "analysis", 29: "analysis", 31: "analysis", 33: "analysis", 35: "analysis",
    37: "analysis", 39: "analysis", 41: "analysis", 43: "analysis",
    45: "presentation", 47: "presentation", 49: "presentation",
}

# ---------------- batch 19: script_116725 A1 + A2 + A3 ----------------
A1_116725 = {
    "limit": ("indeterminable", "在 sma(image).clip(limit) 和 .filterBounds(limit) 中使用，"
              "但源码中没有定义、require 或注释证据；可能来自 Code Editor Imports，但证据不足"),
    "l8_col": ("indeterminable", "在 rename_bands(l8_col, bands_l8) 中使用，但源码中没有定义或"
               "外部来源证据；可能是预先导入的影像集合或遗漏定义，现有证据不足以区分"),
}
A2_116725 = {
    "year": ("analysis_chain", 1, "用于 ee.Date.fromYMD(year, 1, 1)"),
    "start": ("analysis_chain", 2, "用于生成 end，并在 .filterDate(start, end) 中再次引用"),
    "end": ("analysis_chain", 1, "用于 .filterDate(start, end)"),
    "grad": ("presentation_only", 1, "用于图层调色板 grad.reverse()"),
    "bandnamed": ("analysis_chain", 2, "在 rename_bands 函数体内引用一次，在 sma 函数体内引用一次"),
    "bands_l8": ("analysis_chain", 1, "用于 rename_bands(l8_col, bands_l8)"),
    "rename_bands": ("analysis_chain", 1, "用于构建 l8_ready"),
    "imgCol": ("analysis_chain", 1, "函数形参；在 imgCol.select(input, bandnamed) 中引用一次"),
    "input": ("analysis_chain", 1, "函数形参；在 imgCol.select(input, bandnamed) 中引用一次"),
    "endmembers": ("analysis_chain", 1, "用于 fractions 的 .unmix(endmembers)；虽然数组为空仍计一次引用"),
    "sma": ("analysis_chain", 1, "用于 process_image 中的 sma(image)"),
    "outBandNames": ("analysis_chain", 1, "用于 fractions.rename(outBandNames)"),
    "fractions": ("analysis_chain", 5, "用于 rename/expression/addBands(shade) 右侧及 image.addBands"
                  "(fractions)；赋值左侧不计入引用"),
    "summed": ("analysis_chain", 1, "用于 summed.subtract(100)"),
    "shade": ("analysis_chain", 1, "用于 fractions.addBands(shade)"),
    "cloudScore": ("unconsumed", 0, "函数已定义但没被调用，也没有其他后继引用。函数体内的处理逻辑"
                   "不能使其进入实际执行链（l8_ready 只调用 rename_bands(...).map(process_image)）"),
    "rescale": ("analysis_chain", 4, "被调用四次（调用处位于未被调用的 cloudScore 函数体内——"
                "标注者按源码引用计数记 4/analysis_chain）"),
    "obj": ("analysis_chain", 4, "函数形参；obj.image/obj.min/obj.max/第二处 obj.min 共四次"),
    "image": ("analysis_chain", 1, "rescale 内局部变量，用于 return image；与外层同名形参是不同绑定，"
              "不合并计数"),
    "cloudThresh": ("analysis_chain", 1, "用于 score.lt(cloudThresh)"),
    "score": ("analysis_chain", 6, "初始化后四次 score.min(...) 赋值调用及一次 score.lt(...)；"
              "赋值左侧不作为引用计数"),
    "ndsi": ("analysis_chain", 1, "用于 rescale 参数对象中的 'image': ndsi"),
    "cond": ("analysis_chain", 1, "用于 image.updateMask(cond)"),
    "process_image": ("analysis_chain", 1, "用于 .map(process_image)"),
    "l8_ready": ("analysis_chain", 1, "用于构建 processed_col"),
    "processed_col": ("analysis_chain", 2, "分别用于构建 mosaic 和 soil_max"),
    "mosaic": ("presentation_only", 1, "仅用于 Map.addLayer(mosaic, ...)"),
    "soil_max": ("analysis_chain", 2, "用于图层展示，并用于构建 embargo"),
    "embargo": ("presentation_only", 1, "仅用于 Map.addLayer(embargo, ...)"),
}
A2_116725_NOTES = ("标注者口径: cloudScore 未被调用 → unconsumed（内部逻辑不改变状态）；cloudScore "
                   "函数体的 image 形参与 rescale 内局部 image 属不同作用域不合并。审计备注: 不能把该"
                   "脚本描述为实际执行了云评分流程")
A3_116725_LINES = {
    3: "analysis", 5: "analysis", 31: "analysis", 43: "analysis", 55: "analysis",
    57: "analysis", 59: "analysis", 69: "analysis", 71: "analysis", 79: "analysis",
    87: "analysis", 89: "analysis", 91: "analysis", 99: "analysis", 101: "analysis",
    109: "analysis", 111: "analysis", 119: "analysis", 121: "analysis",
    131: "analysis", 133: "analysis", 139: "analysis", 143: "analysis",
    145: "analysis", 147: "analysis", 153: "analysis",
    159: "presentation", 161: "presentation", 163: "analysis",
    165: "presentation",
}

FILLED_A1 = {
    "script_35821": A1_35821,
    "script_45485": A1_45485,
    "script_100110": A1_100110,
    "script_100133": A1_100133,
    "script_100145": A1_100145,
    "script_100870": A1_100870,
    "script_101353": A1_101353,
}
FILLED_A2 = {
    "script_7900": A2_7900,
    "script_10021": A2_10021,
    "script_10224": A2_10224,
    "script_25214": A2_25214,
    "script_35821": A2_35821,
    "script_45485": A2_45485,
    "script_100110": A2_100110,
    "script_100133": A2_100133,
    "script_100145": A2_100145,
    "script_100870": A2_100870,
    "script_100916": A2_100916,
    "script_101051": A2_101051,
    "script_101095": A2_101095,
    "script_101218": A2_101218,
    "script_101353": A2_101353,
    "script_102167": A2_102167,
}
A2_EXTRA_NOTES = {
    "script_10021": A2_10021_NOTES,
    "script_10224": A2_10224_NOTES,
    "script_25214": A2_25214_NOTES,
    "script_35821": A2_35821_NOTES,
    "script_45485": A2_45485_NOTES,
    "script_100110": A2_100110_NOTES,
    "script_100133": A2_100133_NOTES,
    "script_100145": A2_100145_NOTES,
    "script_100870": A2_100870_NOTES,
    "script_100916": A2_100916_NOTES,
    "script_101051": A2_101051_NOTES,
    "script_101095": A2_101095_NOTES,
    "script_101353": A2_101353_NOTES,
}
A1_EXTRA_NOTES = {
    "script_45485": A1_45485_NOTES,
    "script_100133": A1_100133_NOTES,
    "script_100145": A1_100145_NOTES,
    "script_101353": A1_101353_NOTES,
    "script_116725": None,  # set below after dict definitions
}

FILLED_A3_LINES = {
    "script_10021": A3_10021_LINES,
    "script_10224": A3_10224_LINES,
    "script_25214": A3_25214_LINES,
    "script_35821": A3_35821_LINES,
    "script_45485": A3_45485_LINES,
    "script_100110": A3_100110_LINES,
    "script_100133": A3_100133_LINES,
    "script_100145": A3_100145_LINES,
    "script_100870": A3_100870_LINES,
    "script_100916": A3_100916_LINES,
    "script_101051": A3_101051_LINES,
    "script_101095": A3_101095_LINES,
    "script_101218": A3_101218_LINES,
    "script_101353": A3_101353_LINES,
    "script_102167": A3_102167_LINES,
}
FILLED_A3_UNITS = {k: v for k, v in A3_10224_UNITS.items()}
A3_UNKNOWN_LINES = {}  # 100133@157 was 'unknown' in batch 8; revision (batch 26)
                       # reclassified it to presentation — entry removed
# ---------------- batch 20: script_184426 A2 + A3 ----------------
A2_184426 = {
    "imageCollection": ("unconsumed", 0, "定义后没有后继引用；后续另行定义了 collection"),
    "myanmar": ("analysis_chain", 2, "用于 Map.addLayer 展示和 myanmar.filter(filter)；"
                "虽有展示用途但也进入分析筛选链"),
    "filter": ("analysis_chain", 1, "用于 myanmar.filter(filter)"),
    "filtered_area": ("analysis_chain", 3, "用于定义 roi、地图展示，以及最后的图层展示"),
    "roi": ("analysis_chain", 4, "用于 anomalies.sum().clip(roi)、Map.centerObject(roi, 6)、"
            "图表 regions: roi 和导出区域 region: roi"),
    "collection": ("analysis_chain", 2, "分别用于定义 reference 和 recent"),
    "reference": ("analysis_chain", 2, "用于 reference.mean() 和 reference.first()"),
    "mean": ("analysis_chain", 1, "用于 image.subtract(mean)，计算异常值"),
    "recent": ("analysis_chain", 2, "标注者自纠: 3→2；实际只有 recent.mean() 和 "
               "recent.map(subtractmean) 两处引用"),
    "meanRecent": ("unconsumed", 0, "已计算，但后续没有引用"),
    "image": ("analysis_chain", 2, "subtractmean 形参；用于 image.subtract(mean) 和 "
              "copyProperties(image, ...)"),
    "subtractmean": ("analysis_chain", 1, "用于 recent.map(subtractmean)"),
    "anomalies": ("analysis_chain", 4, "地图异常值图层、anomalies.iterate(...)，以及导出表达式中的 "
                  "anomalies.sum()（地图展示和导出中各出现一次，共 4）"),
    "time0": ("analysis_chain", 1, "用于初始化影像的 system:time_start 属性"),
    "first": ("analysis_chain", 1, "用于 anomalies.iterate(accumulate, first)"),
    "accumulate": ("analysis_chain", 1, "用于 anomalies.iterate(accumulate, first)"),
    "list": ("analysis_chain", 2, "标注者自纠: 3→2；严格按源码标识符计数为 ee.List(list).get(-1) 和 "
             "ee.List(list).add(added) 各一次"),
    "previous": ("analysis_chain", 1, "用于 image.add(previous)"),
    "added": ("analysis_chain", 1, "用于 ee.List(list).add(added)"),
    "cumulative": ("presentation_only", 1, "用于图表配置中的 imageCollection: cumulative"),
    "chartParam": ("presentation_only", 1, "用于 chart.setOptions(chartParam)"),
    "chart": ("presentation_only", 1, "用于 print(chart.setOptions(chartParam))"),
    "shown": ("presentation_only", 1, "用于最后一个 Map.addLayer 的显示参数"),
    "opacity": ("presentation_only", 1, "用于最后一个 Map.addLayer 的透明度参数"),
}
A2_184426_NOTES = ("标注者补充: 源码另定义了 vis，未出现在模板清单中；按其无后继引用如需补标可记 "
                   "unconsumed/0（模板无该单位，仅登记于此）。脚本含显式导出 Export.image.toDrive")
A3_184426_LINES = {
    1: "analysis", 3: "analysis", 5: "presentation", 7: "analysis", 9: "analysis",
    13: "analysis", 15: "analysis", 19: "analysis", 23: "analysis", 25: "analysis",
    29: "analysis", 33: "analysis", 35: "presentation", 47: "analysis",
    49: "analysis", 51: "analysis", 57: "analysis", 59: "analysis", 61: "analysis",
    63: "analysis", 67: "analysis", 69: "analysis", 73: "presentation",
    85: "presentation", 91: "analysis", 103: "presentation", 109: "presentation",
    121: "export", 123: "analysis",
}

# ---------------- batch 21: script_191158 A2 + A3 ----------------
A2_191158 = {
    "l8toa": ("analysis_chain", 1, "用于构建 Landsat 影像处理链"),
    "roi": ("analysis_chain", 8, "用于空间过滤、地图定位及多处图表统计"),
    "timeField": ("analysis_chain", 5, "用于获取时间属性和构建时间匹配条件"),
    "image": ("analysis_chain", 2, "maskClouds 形参；用于选择 BQA 波段及更新掩膜"),
    "maskClouds": ("analysis_chain", 1, "传入 .map(maskClouds)"),
    "quality": ("analysis_chain", 3, "用于三次云质量值比较"),
    "cloud01": ("analysis_chain", 1, "参与掩膜逻辑组合"),
    "cloud02": ("analysis_chain", 1, "参与掩膜逻辑组合"),
    "cloud03": ("analysis_chain", 1, "参与掩膜逻辑组合"),
    "mask": ("analysis_chain", 1, "传入 image.updateMask(mask)"),
    "addVariables": ("analysis_chain", 1, "传入 .map(addVariables)"),
    "date": ("analysis_chain", 1, "用于计算时间差"),
    "years": ("analysis_chain", 1, "转为时间波段 t"),
    "filteredLandsat": ("analysis_chain", 10, "用于图表、回归、去趋势、滞后匹配和填补流程"),
    "l8Chart": ("presentation_only", 1, "传入 print(l8Chart)"),
    "independents": ("analysis_chain", 3, "用于选择波段、计算回归参数及影像运算"),
    "dependent": ("analysis_chain", 7, "用于选择 NDVI、构建滞后波段和回归输入"),
    "trend": ("analysis_chain", 1, "提取回归系数"),
    "coefficients": ("analysis_chain", 1, "用于去趋势计算"),
    "detrended": ("analysis_chain", 5, "用于图表和多次滞后匹配"),
    "detrendedChart": ("presentation_only", 1, "传入 print(detrendedChart)"),
    "harmonicIndependents": ("analysis_chain", 3, "用于谐波回归的波段选择、参数设置和影像运算"),
    "harmonicLandsat": ("analysis_chain", 2, "用于谐波回归和拟合影像生成"),
    "timeRadians": ("analysis_chain", 2, "分别计算余弦和正弦波段"),
    "harmonicTrend": ("analysis_chain", 1, "用于提取谐波回归系数"),
    "harmonicTrendCoefficients": ("analysis_chain", 5, "用于拟合影像、相位和振幅计算"),
    "fittedHarmonic": ("analysis_chain", 1, "传入谐波拟合图表"),
    "phase": ("analysis_chain", 1, "用于构建 RGB 合成影像"),
    "amplitude": ("analysis_chain", 1, "用于构建 RGB 合成影像"),
    "rgb": ("presentation_only", 1, "用于地图显示"),
    "lag": ("analysis_chain", 5, "用于多种滞后时间匹配"),
    "leftCollection": ("analysis_chain", 1, "作为 Join 的主集合"),
    "rightCollection": ("analysis_chain", 1, "作为 Join 的次集合"),
    "lagDays": ("analysis_chain", 1, "用于计算时间差阈值"),
    "filter": ("analysis_chain", 1, "lag 函数内部：作为 Join 的匹配条件"),
    "lagged17": ("analysis_chain", 2, "用于打印和生成合并影像集合"),
    "merge": ("analysis_chain", 4, "用于多个集合的映射合并"),
    "current": ("analysis_chain", 1, "merger 形参；传入 addBands(current)"),
    "merger": ("analysis_chain", 1, "传入 .iterate(merger, image)"),
    "previous": ("analysis_chain", 1, "转换为影像后参与合并"),
    "merged17": ("analysis_chain", 1, "用于计算滞后协方差"),
    "mergedCollection": ("analysis_chain", 1, "用于选择波段并计算协方差"),
    "band": ("analysis_chain", 1, "用于选择协方差计算的波段"),
    "lagBand": ("analysis_chain", 1, "全局变量（定义行 257）：作为 covariance 函数的实参；"
                "函数内部同名参数的引用不混入计数"),
    "covariance17": ("analysis_chain", 2, "用于地图展示和相关系数计算"),
    "correlation": ("analysis_chain", 3, "用于计算多个相关系数结果"),
    "vcArrayImage": ("analysis_chain", 3, "用于提取协方差和两个标准差"),
    "covariance": ("analysis_chain", 1, "correlation 函数内部：用于计算相关系数"),
    "sd0": ("analysis_chain", 1, "用于相关系数计算"),
    "sd1": ("analysis_chain", 1, "用于相关系数计算"),
    "correlation17": ("presentation_only", 1, "用于地图展示"),
    "covariance34": ("presentation_only", 1, "用于地图展示"),
    "chirps": ("analysis_chain", 2, "用于两个不同时间滞后的降水匹配"),
    "lag1PrecipNDVI": ("analysis_chain", 2, "用于打印及生成合并集合"),
    "merged1PrecipNDVI": ("analysis_chain", 2, "用于打印和计算协方差"),
    "cov1PrecipNDVI": ("analysis_chain", 3, "用于地图表达式和相关系数计算。标注者审计: 第 327 行 "
                        "Map.addLayer 标签写 lag=30 但实际传入 cov1PrecipNDVI 而非 cov30PrecipNDVI"
                        "——疑似变量使用错误，不改变该行 presentation 角色"),
    "corr1PrecipNDVI": ("presentation_only", 1, "用于地图展示"),
    "lag30PrecipNDVI": ("analysis_chain", 2, "用于打印及构建降水累计集合"),
    "sum30PrecipNDVI": ("analysis_chain", 1, "用于计算累计降水与 NDVI 的协方差"),
    "laggedImages": ("analysis_chain", 1, "用于计算滞后影像集合的总和"),
    "cov30PrecipNDVI": ("analysis_chain", 1, "用于相关系数计算"),
    "corr30PrecipNDVI": ("presentation_only", 1, "用于地图展示"),
    "lagged34": ("analysis_chain", 1, "定义行 333；用于构建第二个 merged34。重复 var 声明按同一"
                 "函数作用域绑定理解，按模板所指后一次定义行统计"),
    "merged34": ("analysis_chain", 2, "定义行 335；用于 AR(2) 回归及拟合影像生成。重复 var 同上口径"),
    "arIndependents": ("analysis_chain", 3, "用于选择波段、设置回归参数和展开系数"),
    "ar2": ("analysis_chain", 1, "用于提取 AR 回归系数"),
    "arCoefficients": ("analysis_chain", 6, "用于 AR 拟合及预测计算"),
    "fittedAR": ("analysis_chain", 1, "用于 AR(2) 拟合图表"),
    "list": ("analysis_chain", 2, "fill 形参；用于获取最后一幅影像并追加影像"),
    "fill": ("analysis_chain", 1, "传入 filteredLandsat.iterate(fill, ...)"),
    "latestDate": ("analysis_chain", 1, "用于计算填补影像的起始时间"),
    "current": ("analysis_chain", 2, "fill 形参；用于读取当前影像日期并追加影像"),
    "currentDate": ("analysis_chain", 1, "用于计算填补影像的结束时间"),
    "start": ("analysis_chain", 1, "用于判断是否需要生成填补影像"),
    "end": ("analysis_chain", 1, "用于判断是否需要生成填补影像"),
    "blankImages": ("analysis_chain", 1, "追加到迭代列表"),
    "first": ("analysis_chain", 1, "作为迭代初始列表的元素"),
    "filled": ("analysis_chain", 3, "用于截取、初始化预测列表和构建集合"),
    "indices": ("unconsumed", 0, "定义后没有后继引用"),
    "forecast": ("analysis_chain", 1, "传入 .iterate(forecast, startList)"),
    "ndvi": ("analysis_chain", 1, "用于填补缺失 NDVI 值"),
    "size": ("analysis_chain", 2, "用于取得列表末尾的两幅影像"),
    "image1": ("analysis_chain", 1, "用于预测表达式中的 p1"),
    "image2": ("analysis_chain", 1, "用于预测表达式中的 p2"),
    "predicted": ("analysis_chain", 2, "用于条件分支及缺失值填补"),
    "replaced": ("analysis_chain", 1, "追加到迭代列表"),
    "startList": ("analysis_chain", 1, "作为预测迭代的初始列表"),
    "modeled": ("analysis_chain", 3, "用于图表和后续时间邻域 Join"),
    "join": ("analysis_chain", 1, "调用 .apply() 构建邻域 Join"),
    "diffFilter": ("analysis_chain", 1, "作为 Join 的时间匹配条件"),
    "threeNeighborJoin": ("analysis_chain", 1, "用于生成平滑集合"),
    "smoothed": ("analysis_chain", 1, "用于平滑结果图表"),
    "collection": ("analysis_chain", 1, "平滑回调内部：用于计算邻域影像均值"),
}
A2_191158_NOTES = ("标注者口径: 函数参数即使所在函数未被调用也统计函数体内引用；重复 var（lagged34/"
                   "merged34）按同一作用域绑定、按模板所指后一次定义行统计；lagBand 全局变量与函数"
                   "同名参数分开计数")
A3_191158_PRESENTATION = {
    5, 49, 51, 71, 99, 111, 153, 155, 183, 231, 261, 277, 293, 299, 303, 307,
    311, 315, 327, 331, 375, 377, 491, 493, 541, 543,
}
A3_191158_LINES = {
    _l: ("presentation" if _l in A3_191158_PRESENTATION else "analysis")
    for _l in [1, 3, 5, 11, 13, 15, 17, 19, 21, 27, 29, 31, 33, 35, 37, 41, 49,
               51, 71, 73, 75, 77, 79, 81, 87, 89, 91, 99, 111, 113, 115, 117,
               119, 121, 123, 127, 129, 131, 133, 139, 141, 143, 153, 155, 169,
               171, 173, 175, 177, 179, 181, 183, 187, 189, 199, 207, 229, 231,
               237, 241, 245, 249, 251, 253, 257, 259, 261, 265, 267, 269, 271,
               275, 277, 279, 281, 285, 289, 291, 293, 295, 297, 299, 301, 303,
               305, 307, 309, 311, 313, 315, 317, 319, 321, 325, 327, 329, 331,
               333, 335, 337, 339, 341, 343, 345, 347, 349, 355, 357, 359, 361,
               363, 365, 367, 369, 375, 377, 393, 395, 397, 399, 401, 403, 405,
               415, 419, 429, 433, 435, 437, 441, 443, 445, 447, 449, 451, 453,
               455, 457, 459, 463, 465, 467, 471, 473, 481, 485, 487, 489, 491,
               493, 507, 513, 523, 533, 535, 537, 541, 543]
}

# ---------------- batch 22: script_216850 A1 + A2 + A3 ----------------
_A1_216850_VARS = ["table", "table2", "roi", "snflwr", "water", "built", "bare",
                   "vege", "wetland"]
A1_216850 = {
    v: ("indeterminable", "源码中未见定义、导入或注释证据；可能是 Code Editor Imports 预绑定对象，"
        "但无法确认（不直接标 external_prebinding 或 missing_definition）")
    for v in _A1_216850_VARS
}
A1_216850_NOTES = ("标注者统一判断: 九个变量均无声明，仅凭当前片段无法区分 Imports 预绑定与脚本遗漏定义")
A2_216850 = {
    "maskCloud_S2TOA": ("analysis_chain", 1, "用于第一段影像集合的 .map(maskCloud_S2TOA)"),
    "img": ("analysis_chain", 4, "标注者核算更正: img.select/updateMask/copyProperties 三处 + "
            "copyProperties 参数中的 img，共 4 次"),
    "image": ("analysis_chain", 1, "第 21 行定义；标注者核算更正: 仅 imagenew 定义中的 image.clip(roi)"
              " 一次引用"),
    "imagenew": ("analysis_chain", 3, "用于训练样本提取、验证样本提取和分类预测"),
    "sampleData": ("analysis_chain", 3, "用于 randomColumn 赋值右侧、训练集筛选、验证集筛选"),
    "bands": ("analysis_chain", 3, "用于训练、验证及分类时的 .select(bands)"),
    "split": ("analysis_chain", 2, "分别用于训练集和验证集筛选条件"),
    "sample_training": ("analysis_chain", 1, "用于 training 的 sampleRegions 配置"),
    "sample_validate": ("analysis_chain", 1, "用于 validation 的 sampleRegions 配置"),
    "training": ("analysis_chain", 1, "用于分类器训练的 features 参数"),
    "validation": ("analysis_chain", 1, "用于 validation.classify(classifier)"),
    "classifier": ("analysis_chain", 3, "用于分类预测、混淆矩阵计算、验证集分类"),
    "classified": ("analysis_chain", 4, "用于地图展示、面积影像构造、类别掩膜和面积统计影像构造"),
    "trainAccuracy": ("unconsumed", 0, "只保存混淆矩阵，没有后续引用"),
    "validated": ("analysis_chain", 1, "用于计算测试误差矩阵"),
    "testAccuracy": ("unconsumed", 0, "只保存误差矩阵，没有后续引用"),
    "LULC": ("unconsumed", 0, "定义表达式疑似写法错误；后续未引用"),
    "area": ("analysis_chain", 1, "用于 area.reduceRegion(...)"),
    "Area_Sqm": ("unconsumed", 0, "保存区域统计结果，但后续未引用"),
    "sunflower": ("analysis_chain", 2, "用于地图展示和 reduceToVectors(...)"),
    "proj7762": ("analysis_chain", 1, "用于 reduceToVectors 的 crs 参数"),
    "final_table": ("unconsumed", 0, "生成矢量结果后未再引用"),
    "areaImage": ("analysis_chain", 2, "用于 reduceRegion 和图表配置"),
    "areas": ("analysis_chain", 1, "用于 areas.get('groups')"),
    "classAreas": ("unconsumed", 0, "获取分组结果后未再引用"),
    "areaChart": ("analysis_chain", 2, "标注者核算更正: areaChart.style() 和 Map.add(areaChart) "
                  "共 2 次；定义链中 .setOptions 是创建表达式的一部分不计"),
    "s2": ("analysis_chain", 1, "用于构建 filtered 影像集合"),
    "maskS2clouds": ("analysis_chain", 1, "用于 s2.map(maskS2clouds)"),
    "qa": ("analysis_chain", 3, "两次 bitwiseAnd 及 and 链中另一处 bitwiseAnd，共 3 次"),
    "cloudBitMask": ("analysis_chain", 1, "用于 qa.bitwiseAnd(cloudBitMask)"),
    "cirrusBitMask": ("analysis_chain", 1, "用于 qa.bitwiseAnd(cirrusBitMask)"),
    "mask": ("analysis_chain", 1, "maskS2clouds 内；用于 .updateMask(mask)"),
    "ndvi": ("analysis_chain", 1, "用于 image.addBands(ndvi)"),
    "wi": ("analysis_chain", 1, "用于 image.addBands(wi)"),
    "wi1": ("analysis_chain", 1, "用于 image.addBands(wi1)"),
    "ccci": ("analysis_chain", 1, "用于 image.addBands(ccci)"),
    "evi2": ("analysis_chain", 1, "用于 image.addBands(evi2)"),
    "filtered": ("analysis_chain", 9, "标注者核算更正: 5 次地图图层表达式、图表影像集合、点击回调中"
                 "两次筛选及回调中 filtered.first()，共 9 次"),
    "ClassChart": ("presentation_only", 2, "设置样式及注册点击回调（核算更正 2 次）"),
    "label": ("presentation_only", 2, "添加 UI 标签和点击回调中更新标签内容（核算更正 2 次）"),
    "xValue": ("analysis_chain", 3, "点击回调形参：空值判断、筛选条件、日期转换（核算更正 3 次）"),
    "yValue": ("unconsumed", 0, "回调形参没有被引用"),
    "seriesName": ("unconsumed", 0, "回调形参没有被引用"),
    "equalDate": ("analysis_chain", 2, "用于两次 filtered.filter(equalDate)"),
    "classification": ("presentation_only", 1, "用于地图展示"),
    "SARimage": ("presentation_only", 1, "用于构造 ui.Map.Layer"),
    "S1Layer": ("unconsumed", 0, "创建图层对象后未引用，也没有添加到地图"),
}
A2_216850_NOTES = ("标注者核算更正汇总: img=4、image(21)=1、imagenew=3、sampleData=3、classified=4、"
                   "areaChart=2、filtered=9、ClassChart=2、label=2、xValue=3、equalDate=2；"
                   "S1Layer 创建后未添加到地图 → unconsumed")
A3_216850_PRESENTATION = {
    1, 3, 87, 117, 165, 197, 207, 253, 255, 257, 259, 261, 263, 287, 297, 299,
    301, 303, 313, 323, 335, 337, 339, 343, 345, 347,
}
A3_216850_LINES = {
    _l: ("presentation" if _l in A3_216850_PRESENTATION else "analysis")
    for _l in [1, 3, 7, 13, 15, 17, 21, 33, 35, 39, 43, 45, 47, 55, 57, 65, 67,
               77, 79, 81, 83, 87, 89, 97, 99, 115, 117, 119, 121, 139, 141, 143,
               163, 165, 175, 197, 207, 209, 213, 219, 221, 223, 225, 227, 229,
               231, 233, 235, 239, 241, 243, 247, 251, 253, 255, 257, 259, 261,
               263, 265, 269, 287, 297, 299, 301, 303, 307, 309, 311, 313, 323,
               335, 337, 339, 343, 345, 347]
}
A3_216850_NOTES = ("标注者特别说明: ui.Chart 参数内的 Reducer 仍是 analysis；reduceToVectors 归 "
                   "analysis；style().set 为 presentation；ui.Map.Layer 创建与 layers.reset 归 "
                   "presentation；label.setValue 归 presentation")

# ---------------- batch 23: script_217669 A2 + A3 ----------------
A2_217669 = {
    "grid_name": ("analysis_chain", 5, "用于网格筛选、样本资产路径、图层名称及分类影像资产路径"),
    "region_institution": ("analysis_chain", 1, "拼接样本资产路径"),
    "version_samples": ("analysis_chain", 1, "拼接样本资产版本路径"),
    "version_class": ("analysis_chain", 1, "拼接分类影像资产路径"),
    "year_list": ("analysis_chain", 2, "用于 for...in 循环及按索引读取年份"),
    "percent_03": ("analysis_chain", 1, "计算类别 3 的训练样本数量"),
    "percent_05": ("unconsumed", 0, "定义后未引用"),
    "percent_11": ("unconsumed", 0, "定义后未引用"),
    "percent_13": ("analysis_chain", 1, "计算类别 13 的训练样本数量"),
    "percent_21": ("analysis_chain", 1, "计算类别 21 的训练样本数量"),
    "percent_24": ("unconsumed", 0, "定义后未引用"),
    "percent_25": ("analysis_chain", 1, "计算类别 25 的训练样本数量"),
    "percent_33": ("analysis_chain", 1, "计算类别 33 的训练样本数量"),
    "nSamplesMin": ("analysis_chain", 5, "在五个类别样本数量计算中作为下限"),
    "nSamplesMax": ("analysis_chain", 5, "在五个类别样本数量计算中作为基数"),
    "grids": ("presentation_only", 1, "筛选后用于绘制网格轮廓"),
    "myGrid": ("presentation_only", 1, "仅用于生成网格轮廓"),
    "dir_pre_class": ("analysis_chain", 1, "拼接分类影像资产路径"),
    "dirasset": ("unconsumed", 0, "定义后未引用"),
    "dir_class": ("unconsumed", 0, "定义后未引用"),
    "dir_Samples": ("analysis_chain", 1, "拼接样本资产路径"),
    "stage": ("analysis_chain", 1, "拼接分类影像资产路径"),
    "options": ("unconsumed", 0, "配置对象定义后未引用"),
    "names": ("presentation_only", 2, "用于循环长度判断及读取图例类别名称"),
    "colors": ("presentation_only", 1, "读取图例颜色"),
    "palettes": ("presentation_only", 1, "获取分类显示调色板；源码重复声明并赋值，按第 83 行定义后的"
                 "引用计数"),
    "legend": ("presentation_only", 3, "添加标题、类别行，并将图例添加到地图"),
    "legendTitle": ("presentation_only", 1, "添加到图例面板"),
    "makeRow": ("presentation_only", 1, "循环中调用以生成图例行"),
    "name": ("presentation_only", 1, "makeRow 形参，用于设置标签文本"),
    "colorBox": ("unconsumed", 0, "标签对象创建后没有通过变量名再次引用；对象本身已放入返回面板"),
    "description": ("unconsumed", 0, "标签对象创建后没有通过变量名再次引用；对象本身已放入返回面板"),
    "i": ("presentation_only", 4, "用于循环判断、递增及访问 names[i]、colors[i]"),
    "visParMedian2": ("unconsumed", 0, "定义后未引用"),
    "totalSample": ("analysis_chain", 1, "传入 shuffle 生成训练样本集合"),
    "blank": ("presentation_only", 1, "生成轮廓图层的空掩膜影像"),
    "outline": ("presentation_only", 1, "仅传入 Map.addLayer"),
    "visPar": ("presentation_only", 1, "设置网格轮廓图层的显示参数"),
    "shuffle": ("analysis_chain", 1, "调用函数打乱样本集合"),
    "collection": ("analysis_chain", 6, "函数形参；用于随机列、排序、映射、列归约、取大小及重映射"),
    "seed": ("analysis_chain", 1, "用于 randomColumn 的随机种子"),
    "feature": ("analysis_chain", 2, "回调形参；读取随机值并设置 new_id 属性"),
    "rescaled": ("analysis_chain", 3, "乘法、取整及写入 new_id 属性"),
    "randomIdList": ("analysis_chain", 1, "传入 collection.remap"),
    "sequentialIdList": ("analysis_chain", 1, "传入 collection.remap"),
    "shuffled": ("analysis_chain", 1, "通过 return shuffled 返回重映射后的集合"),
    "shuffledtraining": ("analysis_chain", 5, "分别用于五个类别的筛选"),
    "num_train_03": ("analysis_chain", 1, "限制类别 3 的样本数量"),
    "train_03": ("analysis_chain", 2, "合并至平衡样本集，并添加到地图"),
    "num_train_13": ("analysis_chain", 1, "限制类别 13 的样本数量"),
    "train_13": ("analysis_chain", 2, "合并至平衡样本集，并添加到地图"),
    "num_train_21": ("analysis_chain", 1, "限制类别 21 的样本数量"),
    "train_21": ("analysis_chain", 2, "合并至平衡样本集，并添加到地图"),
    "num_train_25": ("analysis_chain", 1, "限制类别 25 的样本数量"),
    "train_25": ("analysis_chain", 2, "合并至平衡样本集，并添加到地图"),
    "num_train_33": ("analysis_chain", 1, "限制类别 33 的样本数量"),
    "train_33": ("analysis_chain", 2, "合并至平衡样本集，并添加到地图"),
    "balancedtraining": ("analysis_chain", 1, "传入年度分类影像的 sampleRegions"),
    "class_map": ("analysis_chain", 1, "按年份选择分类波段"),
    "year_id": ("analysis_chain", 1, "用作 year_list 的索引"),
    "year": ("analysis_chain", 3, "用于选择年度波段、构造图层名称及误差矩阵波段名"),
    "class_map_year": ("analysis_chain", 2, "添加分类图层，并提取训练样本区域的分类值"),
    "valida_reg": ("analysis_chain", 1, "计算误差矩阵"),
    "errorMatrix_abs": ("analysis_chain", 1, "输出总体精度 accuracy()"),
}
A2_217669_NOTES = ("标注者口径: train_03 等类别集合虽也用于地图展示但同时进入 balancedtraining 参与"
                   "精度评估 → analysis_chain；blank/outline/myGrid 只服务地图轮廓显示 → "
                   "presentation_only")
A3_217669_PRESENTATION = {
    45, 83, 91, 95, 107, 125, 129, 143, 151, 155, 163, 179, 249, 255, 259, 261,
    263, 265, 267, 269,
}
A3_217669_LINES = {
    _l: ("presentation" if _l in A3_217669_PRESENTATION else "analysis")
    for _l in [31, 33, 45, 83, 91, 95, 107, 125, 129, 143, 151, 155, 163, 169,
               173, 175, 179, 183, 191, 197, 203, 205, 209, 211, 217, 219, 221,
               223, 225, 227, 229, 231, 233, 235, 237, 239, 241, 247, 249, 251,
               253, 255, 259, 261, 263, 265, 267, 269]
}
A3_217669_NOTES = ("标注者裁定: require(...) 两处（45/83 行重复导入调色板模块）归 presentation"
                   "——与 script_100133 第 157 行 require 归 unknown 形成跨样本口径差，"
                   "开封时作为 annotator_criteria_divergence 候选核对；print 精度结果仍归 "
                   "presentation（计算在 errorMatrix/accuracy）")

# ---------------- batch 24: script_271544 A1 + A2 + A3 ----------------
A1_271544 = {
    "canopy_height": ("indeterminable", "源码中没有定义、require 导入或注释说明；可能是 Code Editor "
                      "预绑定影像或遗漏定义，现有证据不足以区分"),
    "roi": ("indeterminable", "仅在 .clip(roi) 中使用，源码未见定义或外部来源说明；不能仅凭使用情况"
            "判为缺失定义"),
    "FAO": ("indeterminable", "在 FAO.map(...) 中使用，但源码没有定义或导入；无法确定是外部预绑定"
            "集合还是遗漏定义"),
}
A2_271544 = {
    "karnataka": ("analysis_chain", 3, "用于地图展示、计算边界，以及裁剪全局影像"),
    "bounds": ("analysis_chain", 1, "提取边界坐标"),
    "coords": ("analysis_chain", 4, "分别读取四个边界坐标值"),
    "xmin": ("analysis_chain", 1, "传入网格生成函数"),
    "ymin": ("analysis_chain", 1, "传入网格生成函数"),
    "xmax": ("analysis_chain", 1, "传入网格生成函数"),
    "ymax": ("analysis_chain", 1, "传入网格生成函数"),
    "gridModule": ("analysis_chain", 1, "调用 generateGrid 生成网格"),
    "spacing": ("analysis_chain", 2, "作为网格生成函数的两个间距参数"),
    "gridVector": ("analysis_chain", 3, "地图展示、映射处理及回调内获取网格要素"),
    "height_40": ("analysis_chain", 1, "生成高度阈值掩膜后续使用的影像"),
    "height_divide_40": ("analysis_chain", 2, "地图展示，并用于全局影像裁剪"),
    "grid_value": ("presentation_only", 1, "后续仅用于地图展示"),
    "i": ("analysis_chain", 1, "gridVector.map 回调形参，用于 gridVector.get(i)"),
    "roi1": ("analysis_chain", 2, "分别作为两个 reduceRegion 的几何区域"),
    "img": ("analysis_chain", 2, "第 39 行回调内定义；两次调用 img.select('b1')。标注者注意: 全局"
            "作用域另有同名 img 定义，必须分开统计（模板单位指回调内 img）"),
    "n1": ("analysis_chain", 1, "用于计算 n_p"),
    "n2": ("analysis_chain", 1, "用于计算 n_p"),
    "n_p": ("analysis_chain", 2, "写入 dict，并作为回调返回值"),
    "dict": ("unconsumed", 0, "后续没有引用；Feature 构造表达式位于注释中，不计为有效使用"),
    "FAO_feature": ("unconsumed", 0, "定义后未引用"),
    "feature": ("analysis_chain", 2, "获取几何对象，并传入 ProjectionTransform"),
    "geom": ("analysis_chain", 1, "获取几何对象的投影"),
    "proj": ("analysis_chain", 2, "用于 atScale 和 coveringGrid"),
    "geom_reproject": ("analysis_chain", 1, "获取几何并生成覆盖网格"),
    "covGrid": ("unconsumed", 0, "计算后未返回，也没有其他引用"),
}
A2_271544_NOTES = ("标注者四条源码问题备注（不改变标签）: (1) karnataka 变量名与 ADM0_NAME='Ukraine' "
                   "筛选条件不一致; (2) 网格回调参数 i 实为要素而非整数索引; (3) 回调内 var img = "
                   "ee.Image(1) 遮蔽外部 img，两次 reduceRegion 统计的是常量影像; (4) covGrid 未 "
                   "return 也未被使用，映射结果未明确返回预期网格要素")
A3_271544_PRESENTATION = {5, 25, 31, 73}
A3_271544_LINES = {
    _l: ("presentation" if _l in A3_271544_PRESENTATION else "analysis")
    for _l in [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 23, 25, 27, 29, 31, 33, 35, 37,
               39, 41, 43, 53, 55, 65, 73, 75, 77, 79, 81, 85, 91]
}

# ---------------- batch 25: script_7900 A1 + A3 finals ----------------
A1_7900 = {
    "genhe": ("indeterminable", "完整源码中未见定义、导入或明确的预绑定说明；可能来自 Code Editor "
              "Imports，也可能是遗漏定义；现有证据不足以区分"),
    "landsat8": ("indeterminable", "第 195 行 landsat8 = landsat8 是自引用式赋值，不能证明来自外部"
                 "预绑定，也不能单独证明定义缺失。self_reference_in_initializing_assignment 是风险"
                 "线索，不是 external_prebinding 的充分证据；不因复核强行改判"),
}
_A3_7900_ANALYSIS = set()
for _grp in ["7,9,11,13", "19,21", "27,31,33,35,41", "47,49", "55", "61,63",
             "65,67,69", "71,73,75,79,81,83,85,87,95", "97", "105,107",
             "111,113,115,117,119", "123,125,127", "133,135,137", "147",
             "153,155,157", "159,163,165,167,169", "181,183,185,187", "195",
             "199", "201", "215", "217,219", "223"]:
    for _x in _grp.split(","):
        _A3_7900_ANALYSIS.add(int(_x))
A3_7900_LINES = {}
for _l in [7, 9, 11, 13, 19, 21, 27, 31, 33, 35, 41, 47, 49, 55, 61, 63, 65, 67,
           69, 71, 73, 75, 79, 81, 83, 85, 87, 95, 97, 105, 107, 111, 113, 115,
           117, 119, 123, 125, 127, 133, 135, 137, 147, 153, 155, 157, 159, 163,
           165, 167, 169, 181, 183, 185, 187, 195, 199, 201, 213, 215, 217, 219,
           221, 223, 225]:
    if _l == 225:
        A3_7900_LINES[_l] = "export"
    elif _l in (213, 221):
        A3_7900_LINES[_l] = "presentation"
    else:
        A3_7900_LINES[_l] = "analysis"
A3_7900_NOTES = ("标注者最终规则: 未列为 presentation/export 的调用全部归 analysis；195 行集合处理链、"
                 "213 行 print、223 行波段选择不因同处一条流程而混淆角色")

# ---------------- batch 26: script_100133 revision (supersedes batch 8 values) ----------------
A2_100133_V2 = {
    "CdMxmunis": ("analysis_chain", 1, "作为 reduceRegions 的区域集合"),
    "CdMxABEGs": ("unconsumed", 0, "定义后未被引用；后续分析使用的是 AOI 和 ABEGFeaturesR"),
    "AOI": ("analysis_chain", 5, "用于地图定位、区域统计、土地利用影像筛选及区域绘制等操作"),
    "BACKGROUND": ("presentation_only", 1, "用于设置地图底图类型"),
    "PM25rfiltered": ("analysis_chain", 4, "用于打印、两次区域统计映射及地图展示；因进入分析链"),
    "image": ("analysis_chain", 1, "第 25 行回调形参；调用 image.reduceRegions(...)"),
    "reducedM": ("analysis_chain", 1, "用于 flatten() 展平区域统计结果"),
    "muniFeaturesR": ("analysis_chain", 2, "用于打印首个要素及绘制行政区统计结果"),
    "reducedA": ("analysis_chain", 1, "用于 flatten() 展平区域统计结果"),
    "ABEGFeaturesR": ("analysis_chain", 6, "用于打印、绘制、统计均值、赋值给 data、相关性计算及排序"),
    "paletteBlueRed": ("unconsumed", 0, "定义后未被引用"),
    "paletteMono": ("unconsumed", 0, "定义后未被引用"),
    "minScale": ("unconsumed", 0, "定义后未被引用"),
    "maxScale": ("unconsumed", 0, "定义后未被引用"),
    "indexRemappingFunction": ("analysis_chain", 1, "用于重映射 CdMxISU 的类别值"),
    "collection": ("analysis_chain", 2, "函数形参；修订稿核算: 分别传入 console.log 和 "
                   "collection.remap(...)（batch 8 记 3，修订为 2）"),
    "orig": ("analysis_chain", 1, "作为 remap 的原始类别列表"),
    "final": ("analysis_chain", 1, "作为 remap 的目标数值列表"),
    "emptyImage": ("analysis_chain", 1, "用于构建 equityImage"),
    "equityImage": ("unconsumed", 0, "创建后未被引用或展示"),
    "CLASSES_7": ("analysis_chain", 1, "赋值给 CLASSES"),
    "COLORS_7": ("analysis_chain", 1, "赋值给 colors"),
    "CLASSES": ("analysis_chain", 1, "修订: 传入图例构建函数 → analysis_chain（batch 8 曾记 "
                "presentation_only）"),
    "colors": ("analysis_chain", 2, "修订: 用于图层参数和图例构建 → analysis_chain"),
    "ULUfiltered": ("presentation_only", 1, "仅用于 Map.addLayer 展示"),
    "legend": ("presentation_only", 2, "两次调用 legend.build(...) 构建图例"),
    "ULUlgnd": ("presentation_only", 1, "仅添加到地图界面"),
    "Mfills": ("unconsumed", 0, "生成填充影像后未被引用或展示"),
    "Ppctfills": ("analysis_chain", 1, "修订: 由 paint 生成，随后用于地图展示 → analysis_chain"),
    "YEAR": ("analysis_chain", 1, "用于计算波段序号 BANDnum"),
    "BANDnum": ("analysis_chain", 1, "用于构造波段名 BAND"),
    "BAND": ("analysis_chain", 2, "用于黑碳与二氧化硫影像的可视化参数"),
    "BCimage": ("presentation_only", 1, "仅用于地图图层展示"),
    "SO2image": ("presentation_only", 1, "仅用于地图图层展示"),
    "BCimageVisParam": ("presentation_only", 1, "仅用于黑碳图层的显示参数"),
    "SO2imageVisParam": ("presentation_only", 1, "仅用于二氧化硫图层的显示参数"),
    "MIN": ("analysis_chain", 2, "用于 PM2.5 可视化参数和图例数值范围"),
    "MAX": ("analysis_chain", 2, "用于 PM2.5 可视化参数和图例数值范围"),
    "Afills": ("analysis_chain", 1, "修订: 由区域统计结果绘制生成，并用于地图展示 → analysis_chain"),
    "AQrange": ("presentation_only", 1, "仅用于构建 PM2.5 图例"),
    "AQlgnd": ("presentation_only", 1, "仅添加到地图界面（此前缺标，修订稿补齐）"),
    "empty": ("analysis_chain", 4, "重复 var 声明（163/173/217/235 行），按文件级绑定合并计 4；"
              "修订稿按各定义位置分行记录（每处 1，用于各自 paint）"),
    "AOIimage": ("analysis_chain", 1, "修订: 由 paint 生成，随后用于地图展示 → analysis_chain"),
    "G_CATEGORIES": ("unconsumed", 0, "定义后未被引用"),
    "G_COLORS": ("analysis_chain", 1, "用于构建 VIZ 参数对象"),
    "G_MAX": ("analysis_chain", 1, "用于构建 VIZ 参数对象"),
    "VIZ": ("unconsumed", 0, "参数对象创建后未被引用"),
    "data": ("analysis_chain", 1, "修订: 作为参数传入 getTheChart(...) → analysis_chain"),
    "xVals": ("analysis_chain", 1, "修订: 传入 getTheChart(...) → analysis_chain"),
    "xValLabels": ("analysis_chain", 1, "修订: 同上"),
    "xField": ("analysis_chain", 1, "修订: 同上"),
    "xLabel": ("analysis_chain", 1, "修订: 同上"),
    "yField": ("analysis_chain", 1, "修订: 同上"),
    "yLabel": ("analysis_chain", 1, "修订: 同上"),
    "getTheChart": ("presentation_only", 1, "调用后生成用于界面展示的统计图表"),
    "maxValue": ("analysis_chain", 4, "修订: 函数内最大值更新和图表纵轴范围 → analysis_chain"),
    "maxMedian": ("analysis_chain", 3, "修订: analysis_chain（batch 8 曾记 presentation_only/4，"
                  "修订计数 3）"),
    "myRows": ("analysis_chain", 1, "修订: 用于填充 myDataTable.rows → analysis_chain"),
    "label": ("analysis_chain", 1, "xVals.map 回调形参；用于筛选对应类别的数据"),
    "i": ("analysis_chain", 1, "修订: xVals.map 回调形参，用作 xValLabels[i] 索引 → analysis_chain"),
    "stats": ("analysis_chain", 10, "修订: 读取并使用百分位统计结果 → analysis_chain（batch 8 曾记 "
              "presentation_only/12，修订计数 10）"),
    "myDataTable": ("presentation_only", 1, "传入 ui.Chart 创建图表"),
    "binary": ("analysis_chain", 1, "保存相关性计算结果，随后打印"),
    "pop_pctsFiltSort": ("analysis_chain", 1, "排序后传入散点图分组数据"),
    "chart": ("presentation_only", 1, "第 473 行全局变量：保存散点图，后续添加到图表面板；"
              "getTheChart 函数内另有局部 chart 经 return chart 返回，属不同绑定"),
    "chartPanel": ("presentation_only", 3, "重复声明分行裁定: 第 447 行(2 处)/第 509 行(3 处)；"
                   "文件级单位取修订稿第 509 行值 3（最终经 Map.add 展示的面板），两行裁定均保留"),
}
A2_100133_V2_NOTES = ("修订稿（supersedes batch 8）要点: require@157 改判 presentation（导入图例 UI "
                      "工具）；CLASSES/colors/Ppctfills/Afills/AOIimage/data-xLabel 七参/maxValue/"
                      "maxMedian/myRows/i/stats 由 presentation_only 改 analysis_chain（参与计算或"
                      "构建过程）；计数修订 collection 3→2、maxMedian 4→3、stats 12→10；AQlgnd 补标"
                      "presentation_only/1。潜在问题备注: CdMxABEGs/equityImage/Mfills/VIZ 未进入"
                      "后续链；empty 重复赋值；getInfo() 同步取值风险")
A3_100133_V2_LINES = dict(A3_100133_LINES)
A3_100133_V2_LINES[157] = "presentation"   # revised: unknown -> presentation
A3_100133_V2_LINES[275] = "presentation"   # revised: outer print -> presentation
A3_100133_V2_NOTES = ("修订稿: 157 行 require 改判 presentation；275 行外层 print 归 presentation"
                      "（内部 reduceColumns/Reducer 仍 analysis）；105/107/127 等此前待核查行已全部"
                      "确认 analysis")

# deferred registrations (after all dict definitions)
FILLED_A1["script_116725"] = A1_116725
FILLED_A1["script_216850"] = A1_216850
FILLED_A1["script_271544"] = A1_271544
FILLED_A1["script_7900"] = A1_7900
FILLED_A2["script_102466"] = A2_S1GRD
FILLED_A2["script_102794"] = A2_S1GRD
FILLED_A2["script_116725"] = A2_116725
FILLED_A2["script_184426"] = A2_184426
FILLED_A2["script_191158"] = A2_191158
FILLED_A2["script_216850"] = A2_216850
FILLED_A2["script_217669"] = A2_217669
FILLED_A2["script_271544"] = A2_271544
FILLED_A2["script_100133"] = A2_100133_V2  # revision supersedes batch-8 dict
FILLED_A2["script_7900"] = A2_7900
A2_EXTRA_NOTES["script_116725"] = A2_116725_NOTES
A2_EXTRA_NOTES["script_184426"] = A2_184426_NOTES
A2_EXTRA_NOTES["script_191158"] = A2_191158_NOTES
A2_EXTRA_NOTES["script_216850"] = A2_216850_NOTES
A2_EXTRA_NOTES["script_217669"] = A2_217669_NOTES
A2_EXTRA_NOTES["script_271544"] = A2_271544_NOTES
A2_EXTRA_NOTES["script_100133"] = A2_100133_V2_NOTES
FILLED_A3_LINES["script_102466"] = A3_S1GRD_LINES
FILLED_A3_LINES["script_102794"] = A3_S1GRD_LINES
FILLED_A3_LINES["script_116725"] = A3_116725_LINES
FILLED_A3_LINES["script_184426"] = A3_184426_LINES
FILLED_A3_LINES["script_191158"] = A3_191158_LINES
FILLED_A3_LINES["script_216850"] = A3_216850_LINES
FILLED_A3_LINES["script_217669"] = A3_217669_LINES
FILLED_A3_LINES["script_271544"] = A3_271544_LINES
FILLED_A3_LINES["script_7900"] = A3_7900_LINES
FILLED_A3_LINES["script_100133"] = A3_100133_V2_LINES
A3_SCRIPT_NOTES = {
    "script_216850": A3_216850_NOTES,
    "script_217669": A3_217669_NOTES,
    "script_7900": A3_7900_NOTES,
    "script_100133": A3_100133_V2_NOTES,
}


def main():
    template_path = os.path.join(WS, "results", "annotation_results_template_v1.jsonl")
    rows = [json.loads(l) for l in open(template_path, encoding="utf-8") if l.strip()]

    # A3 line lookup from frozen blind units
    bu = json.load(open(os.path.join(PREP, "blind_annotation_units_v1.json"),
                        encoding="utf-8"))
    a3_line_by_unit = {}
    for sid, s in bu["scripts"].items():
        for u in s["A3_units"]:
            a3_line_by_unit[u["unit_id"]] = u["line"]

    filled_a1 = filled_a2 = filled_a3 = 0
    for r in rows:
        uid = r["unit_id"]
        if ":A1:" in uid:
            sid, var = uid.split(":A1:")
            if sid in FILLED_A1 and var in FILLED_A1[sid]:
                r["human"], r["note"] = FILLED_A1[sid][var]
                if sid in A1_EXTRA_NOTES:
                    r["annotator_convention"] = A1_EXTRA_NOTES[sid]
                r["annotator"] = ANNOTATOR
                r["date"] = "2026-10-10"
                filled_a1 += 1
        elif ":A2:" in uid:
            sid, var = uid.split(":A2:")
            if sid in FILLED_A2 and var in FILLED_A2[sid]:
                status, uses, note = FILLED_A2[sid][var]
                r["human"] = status
                r["uses_count"] = uses
                r["note"] = note
                if sid in A2_EXTRA_NOTES:
                    r["annotator_convention"] = A2_EXTRA_NOTES[sid]
                r["annotator"] = ANNOTATOR
                r["date"] = "2026-10-10"
                filled_a2 += 1
        elif ":A3:" in uid:
            sid = uid.split(":A3:")[0]
            if uid in FILLED_A3_UNITS:
                r["human"] = FILLED_A3_UNITS[uid]
                r["note"] = "per-call ruling (mixed-role line); call identity " \
                            "resolved mechanically from source AST"
                r["annotator"] = ANNOTATOR
                r["date"] = "2026-10-10"
                filled_a3 += 1
            elif sid in A3_UNKNOWN_LINES:
                line = a3_line_by_unit.get(uid)
                unk = A3_UNKNOWN_LINES[sid].get(line)
                if unk:
                    r["human"] = unk
                    r["note"] = "annotator ruled this call's role directly " \
                                "(line-specific override)"
                    r["annotator"] = ANNOTATOR
                    r["date"] = "2026-10-10"
                    filled_a3 += 1
                elif sid in FILLED_A3_LINES:
                    role = FILLED_A3_LINES[sid].get(line)
                    if role:
                        r["human"] = role
                        r["note"] = "line-based ruling; all calls on this line share the role"
                        r["annotator"] = ANNOTATOR
                        r["date"] = "2026-10-10"
                        filled_a3 += 1
            elif sid in FILLED_A3_LINES:
                line = a3_line_by_unit.get(uid)
                role = FILLED_A3_LINES[sid].get(line)
                if role:
                    r["human"] = role
                    r["note"] = "line-based ruling; all calls on this line share the role"
                    r["annotator"] = ANNOTATOR
                    r["date"] = "2026-10-10"
                    filled_a3 += 1

    ts = datetime.now().strftime("%Y%m%dT%H%M")
    out = os.path.join(WS, "results", f"annotation_results_v1_{ts}.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # clean up superseded earlier results files (keep template + latest)
    for fn in os.listdir(os.path.join(WS, "results")):
        if fn.startswith("annotation_results_v1_2") and fn != os.path.basename(out):
            os.remove(os.path.join(WS, "results", fn))

    print(json.dumps({
        "results_file": os.path.relpath(out, REPO),
        "units_total": len(rows),
        "A1_filled": filled_a1,
        "A2_filled": filled_a2,
        "A3_filled": filled_a3,
        "batches": ["script_7900 A2 (53)", "script_10021 A2 (8) + A3 (20)",
                    "script_10224 A2 (11) + A3 (28, incl. mixed line 33 per-call)",
                    "script_25214 A2 (7) + A3 (18)",
                    "script_35821 A1 (1) + A2 (48) + A3 (133)",
                    "script_45485 A1 (3) + A2 (16) + A3 (43)",
                    "script_100110 A1 (2) + A2 (58) + A3 (77)",
                    "script_100133 A1 (6) + A2 (65/66) + A3 (85, incl. require=unknown @157)",
                    "script_100145 A1 (15) + A2 (30) + A3 (146)",
                    "script_100870 A1 (1) + A2 (15, 含三处自纠 1→4) + A3 (60 单位/38 行)",
                    "script_100916 A2 (6) + A3 (14 单位/6 行)",
                    "script_101051 A2 (3) + A3 (16 单位/11 行)",
                    "script_101095 A2 (11) + A3 (36 单位/22 行)",
                    "script_101218 A2 (15) + A3 (26 单位/15 行)",
                    "script_101353 A1 (1) + A2 (20) + A3 (182 单位/107 行)",
                    "script_102167 A2 (5) + A3 (13 单位/8 行)",
                    "script_102466 + script_102794（同源重复）A2 (11x2) + A3 (36x2)",
                    "script_116725 A1 (2) + A2 (29) + A3 (57 单位/30 行)",
                    "script_184426 A2 (24) + A3 (44 单位/29 行)",
                    "script_191158 A2 (92) + A3 (299 单位/158 行)",
                    "script_216850 A1 (9) + A2 (47, 含 11 处核算更正) + A3 (153 单位/77 行)",
                    "script_217669 A2 (64) + A3 (83 单位/48 行, require=presentation)",
                    "script_271544 A1 (3) + A2 (26) + A3 (52 单位/31 行)"],
        "transcription": "mechanical values only; no judgment added",
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
