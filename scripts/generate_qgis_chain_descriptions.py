#!/usr/bin/env python3
"""Generate structured task descriptions for unique QGIS chains.

Phase 1 (default, no API): template-based rules using operator names and chain structure.
Phase 2 (--use-llm): LLM-generated descriptions via DashScope for higher quality.

For each unique chain, produces:
    - task_description_zh / task_description_en (1-3 variants)
    - intent_tags
    - modality (pure_vector / pure_raster / mixed)
    - input_data_types / output_data_types
    - confidence
    - ambiguous_chain flag

Usage:
    python scripts/generate_qgis_chain_descriptions.py                           # template-based
    python scripts/generate_qgis_chain_descriptions.py --use-llm --max-chains 50 # LLM with limit
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

DATASET_PATH = ROOT / "outputs_v2" / "qgis_chain_dataset.jsonl"
CATALOG_PATH = ROOT / "爬取GithubQGIS" / "QGIS_Input.csv"
ID_MAPPINGS_PATH = ROOT / "outputs_v2" / "id_mappings_v2.json"
OUTPUT_PATH = ROOT / "outputs_v2" / "qgis_chain_dataset_described.jsonl"

# ── Operator intent mapping ────────────────────────────────────────

OP_INTENT = {
    "buffer": ("proximity_analysis", "建立缓冲区"),
    "clip": ("spatial_clip", "空间裁剪"),
    "dissolve": ("feature_merge", "要素融合"),
    "intersection": ("spatial_overlay", "空间叠加"),
    "difference": ("spatial_difference", "空间差除"),
    "union": ("spatial_union", "空间并集"),
    "mergevectorlayers": ("layer_merge", "图层合并"),
    "reprojectlayer": ("coordinate_transform", "坐标转换"),
    "fixgeometries": ("geometry_repair", "几何修复"),
    "simplifygeometries": ("geometry_simplify", "几何简化"),
    "bufferbym": ("variable_buffer", "变距缓冲区"),
    "centroids": ("centroid_extract", "提取中心点"),
    "extractbyexpression": ("attribute_filter", "属性筛选"),
    "extractbylocation": ("spatial_filter", "空间筛选"),
    "extractbyattribute": ("attribute_filter", "属性筛选"),
    "selectbylocation": ("spatial_select", "空间选择"),
    "joinattributestable": ("table_join", "属性表连接"),
    "joinattributesbylocation": ("spatial_join", "空间连接"),
    "fieldcalculator": ("field_calculate", "字段计算"),
    "zonalstatistics": ("zonal_statistics", "分区统计"),
    "zonalstatisticsfb": ("zonal_statistics", "分区统计"),
    "rastercalculator": ("raster_algebra", "栅格计算"),
    "warpreproject": ("raster_reproject", "栅格重投影"),
    "cliprasterbymasklayer": ("raster_clip", "栅格裁剪"),
    "cliprasterbyextent": ("raster_clip", "栅格裁剪"),
    "polygonize": ("raster_to_vector", "栅格转矢量"),
    "rasterize": ("vector_to_raster", "矢量转栅格"),
    "slope": ("terrain_slope", "坡度分析"),
    "aspect": ("terrain_aspect", "坡向分析"),
    "hillshade": ("terrain_hillshade", "山体阴影"),
    "contour": ("contour_generation", "等值线生成"),
    "reclassifybytable": ("reclassify", "重分类"),
    "fillnodata": ("gap_fill", "空值填充"),
    "saveraster": ("raster_export", "栅格输出"),
    "savefeatures": ("vector_export", "矢量输出"),
    "saveselectedfeatures": ("vector_export", "矢量输出"),
    "translate": ("format_convert", "格式转换"),
    "createconstantrasterlayer": ("raster_create", "创建栅格"),
    "creategrid": ("grid_create", "创建格网"),
    "multiparttosingleparts": ("geometry_explode", "多部件拆分"),
    "singlepartstomultipart": ("geometry_merge", "单部件合并"),
    "polygonstolines": ("polygon_to_line", "面转线"),
    "linestopolygons": ("line_to_polygon", "线转面"),
    "countpointsinpolygon": ("point_count", "点计数"),
    "randomextract": ("random_sample", "随机抽样"),
    "rastersampling": ("raster_sampling", "栅格采样"),
    "rastersurfacevolume": ("surface_volume", "表面体积"),
    "pixelstopolygons": ("raster_to_vector", "栅格转面"),
    "heatmapkerneldensityestimation": ("density_heatmap", "密度热力图"),
    "smooth": ("geometry_smooth", "几何平滑"),
    "setlayerstyle": ("visualization", "样式设置"),
    "printlayouttoimage": ("map_export", "地图导出"),
    "extenttolayer": ("extent_extract", "范围提取"),
    "refactorfields": ("field_refactor", "字段重构"),
}


def classify_op(op_name: str) -> dict:
    """Classify a single QGIS operator."""
    result = {"intent": "unknown", "intent_zh": "其他处理"}
    name_lower = op_name.lower().replace("native:", "").replace("qgis:", "").replace("gdal:", "").replace("saga:", "").replace("grass7:", "")
    for keyword, (intent_en, intent_zh) in OP_INTENT.items():
        if keyword in name_lower:
            result["intent"] = intent_en
            result["intent_zh"] = intent_zh
            return result
    return result


# ── Template-based description generator ───────────────────────────

def generate_descriptions(
    qgis_ops: list[str],
    operator_names: list[str],
    catalog: dict[str, dict],
) -> dict:
    """Generate structured descriptions for one QGIS chain."""
    n = len(qgis_ops)
    if n == 0:
        return {"error": "empty_chain"}

    # Classify each operator
    op_classes = [classify_op(op) for op in qgis_ops]
    intents = [c["intent"] for c in op_classes]
    intents_zh = [c["intent_zh"] for c in op_classes]

    # Determine modality from catalog
    types = []
    for op in qgis_ops:
        cat = catalog.get(op.lower(), {})
        types.append(cat.get("data_type", "unknown"))
    vec_count = sum(1 for t in types if t == "vector")
    rast_count = sum(1 for t in types if t == "raster")
    if vec_count > 0 and rast_count > 0:
        modality = "mixed"
    elif rast_count > vec_count:
        modality = "pure_raster"
    else:
        modality = "pure_vector"

    # Input/output types
    input_types = list(set(types[:1])) if types else ["unknown"]
    output_types = list(set(types[-1:])) if types else ["unknown"]

    # Generate English description
    op_descs = []
    for name in operator_names:
        op_descs.append(name.lower())
    en_desc = ", ".join(op_descs[:4]) if op_descs else "QGIS processing workflow"

    # Generate Chinese description
    zh_parts = []
    for zh in intents_zh[:5]:
        if zh != "其他处理" and zh not in zh_parts:
            zh_parts.append(zh)
    if modality == "pure_vector":
        zh_prefix = "对输入矢量图层"
    elif modality == "pure_raster":
        zh_prefix = "对输入栅格数据"
    else:
        zh_prefix = "对输入数据"
    zh_desc = f"{zh_prefix}，依次进行{'、'.join(zh_parts) if zh_parts else 'GIS空间分析'}"

    # Intent tags
    intent_tags = list(dict.fromkeys([i for i in intents if i != "unknown"]))

    # Confidence: high if all ops classified, low if many unknowns
    unknown_count = sum(1 for i in intents if i == "unknown")
    if unknown_count == 0:
        confidence = 0.85
    elif unknown_count <= n // 3:
        confidence = 0.70
    else:
        confidence = 0.50

    # Ambiguity: short chains or all same intent are more ambiguous
    ambiguous = n <= 2 or len(intent_tags) <= 1

    return {
        "task_description_en": f"{en_desc}",
        "task_description_zh": f"{zh_desc}。",
        "task_description_query": f"how to {' '.join(op_descs[:4])} in QGIS",
        "intent_tags": intent_tags[:8],
        "modality": modality,
        "input_data_types": input_types,
        "output_data_types": output_types,
        "confidence": round(confidence, 2),
        "ambiguous_chain": ambiguous,
        "op_intent_detail": [
            {"op": qgis_ops[i], "name": operator_names[i] if i < len(operator_names) else "",
             "intent": intents[i]}
            for i in range(min(n, 8))
        ],
    }


# ── LLM-based enhancement (optional) ───────────────────────────────

def llm_generate_descriptions(
    qgis_ops: list[str],
    operator_names: list[str],
    modality: str,
    client=None,
) -> dict | None:
    """Use DashScope LLM to generate higher-quality descriptions."""
    if client is None:
        return None
    prompt = f"""Given this QGIS processing workflow:
Operators: {', '.join(f'{name}({op})' for op, name in zip(qgis_ops, operator_names))}
Modality: {modality}
Chain length: {len(qgis_ops)}

Generate a JSON object with:
- task_description_en: a natural English description of what this GIS workflow does (1 sentence)
- task_description_zh: a natural Chinese description (1 sentence)
- intent_tags: list of 2-5 keyword tags (e.g. ["buffer_analysis", "spatial_clip"])
- confidence: 0.0-1.0 your confidence in this interpretation

Return ONLY valid JSON, no other text."""

    try:
        from openai import OpenAI
        response = client.chat.completions.create(
            model=os.environ.get("LLM_MODEL", "qwen-plus"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3, max_tokens=300,
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```\w*\n?|```$", "", content).strip()
        return json.loads(content)
    except Exception as e:
        print(f"  [LLM ERROR] {e}")
        return None


# ── Main ───────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(DATASET_PATH))
    parser.add_argument("--catalog", default=str(CATALOG_PATH))
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--use-llm", action="store_true")
    parser.add_argument("--llm-base-url", default=os.environ.get("LLM_BASE_URL", ""))
    parser.add_argument("--llm-api-key", default=os.environ.get("LLM_API_KEY", ""))
    parser.add_argument("--max-chains", type=int, default=0, help="Limit LLM generation to N chains")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    print("=" * 60)
    print("QGIS Chain Description Generator")
    print("=" * 60)

    # Load catalog
    print(f"\n[1] Loading operator catalog ...")
    catalog = {}
    with Path(args.catalog).open("r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 6:
                continue
            alg_id = row[5].strip().lower()
            data_type = "unknown"
            for col in row[8:]:
                if col.strip() in ("vector", "raster"):
                    data_type = col.strip()
                    break
            catalog[alg_id] = {
                "name": row[2].strip() if len(row) > 2 else "",
                "data_type": data_type,
            }
    print(f"  {len(catalog)} operators")

    # Load dataset, dedup to unique chains
    print(f"\n[2] Loading dataset and deduplicating ...")
    chains: dict[tuple, dict] = {}
    with Path(args.input).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            key = tuple(item.get("qgis_ops", []))
            current = chains.get(key)
            item_has_l3 = "optional_l3_sequence" in item
            current_has_l3 = bool(current and "optional_l3_sequence" in current)
            if (
                current is None
                or (item_has_l3 and not current_has_l3)
                or (
                    item_has_l3 == current_has_l3
                    and len(item.get("task_text", "")) > len(current.get("task_text", ""))
                )
            ):
                chains[key] = item

    unique_ops = set()
    for ops in chains:
        for op in ops:
            unique_ops.add(op.lower())
    print(f"  Unique chains: {len(chains)}")
    print(f"  Unique operators: {len(unique_ops)}")

    # Init LLM client if requested
    llm_client = None
    if args.use_llm:
        from openai import OpenAI
        llm_client = OpenAI(
            base_url=args.llm_base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_key=args.llm_api_key or os.environ.get("DASHSCOPE_API_KEY", ""),
        )
        print(f"\n[3] LLM mode enabled (base={args.llm_base_url or 'dashscope'})")
    else:
        print(f"\n[3] Template mode (fast, deterministic)")

    # Generate descriptions
    print(f"\n[4] Generating descriptions for {len(chains)} unique chains ...")
    chain_list = list(chains.items())
    random.seed(args.seed)
    random.shuffle(chain_list)

    results = []
    stats = Counter()
    llm_count = 0

    for idx, (ops_tuple, item) in enumerate(chain_list):
        ops = list(ops_tuple)
        names = item.get("operator_names", [])
        has_l3 = "optional_l3_sequence" in item

        # Template generation (always)
        desc = generate_descriptions(ops, names, catalog)

        # LLM enhancement (optional, limited)
        if args.use_llm and (args.max_chains == 0 or llm_count < args.max_chains):
            llm_result = llm_generate_descriptions(ops, names, desc["modality"], llm_client)
            if llm_result:
                desc["task_description_en"] = llm_result.get("task_description_en", desc["task_description_en"])
                desc["task_description_zh"] = llm_result.get("task_description_zh", desc["task_description_zh"])
                desc["confidence"] = llm_result.get("confidence", desc["confidence"])
                desc["llm_generated"] = True
                llm_count += 1
            else:
                desc["llm_generated"] = False
        else:
            desc["llm_generated"] = False

        result = {
            "qgis_ops": ops,
            "operator_names": names,
            "source": item.get("source", ""),
            "task_text_original": item.get("task_text", ""),
            **desc,
        }
        if has_l3:
            result["optional_l3_sequence"] = item["optional_l3_sequence"]

        results.append(result)
        stats[desc["modality"]] += 1
        stats[f"ambiguous_{desc['ambiguous_chain']}"] += 1

        if (idx + 1) % 200 == 0:
            print(f"  {idx + 1}/{len(chains)} ...")

    # Write output
    print(f"\n[5] Writing {len(results)} records to {args.output} ...")
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.output).open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Summary
    print(f"\n{'='*60}")
    print(f"Summary")
    print(f"{'='*60}")
    print(f"  Total chains described: {len(results)}")
    print(f"  With L3 mapping:        {sum(1 for r in results if 'optional_l3_sequence' in r)}")
    print(f"  Pure vector:            {stats.get('pure_vector', 0)}")
    print(f"  Pure raster:            {stats.get('pure_raster', 0)}")
    print(f"  Mixed:                  {stats.get('mixed', 0)}")
    print(f"  Ambiguous chains:       {stats.get('ambiguous_True', 0)}")
    if args.use_llm:
        print(f"  LLM-generated:          {llm_count}")
    print(f"  Output:                 {args.output}")

    # Show samples
    print(f"\n  Sample descriptions:")
    for r in random.sample(results, min(5, len(results))):
        ops_str = " → ".join(r["qgis_ops"][:4])
        print(f"    [{r['modality']}] {ops_str}")
        print(f"      EN: {r['task_description_en'][:100]}")
        print(f"      ZH: {r['task_description_zh'][:100]}")
        print(f"      Tags: {r['intent_tags']}, conf={r['confidence']}")
        print()


if __name__ == "__main__":
    main()
