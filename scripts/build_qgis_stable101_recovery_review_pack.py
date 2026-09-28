#!/usr/bin/env python3
"""Build a human-review pack for the 29 stable101 recovered subworkflows."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECOVERED = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
    / "stable101_source_review_50_v1/recovered_subworkflows_v1/recovered_29_v1.jsonl"
)
DEFAULT_OUTPUT_DIR = DEFAULT_RECOVERED.parents[1] / "recovered_review_v1"

HUMAN_FIELDS = (
    "boundary_decision",
    "dependency_decision",
    "task_text_fidelity",
    "final_decision",
    "reviewer_notes",
)

TASK_NAMES = {
    "qgis_stable101_r3_chip_pair_dag": "重投影标注矢量并成对裁剪影像与掩膜",
    "qgis_stable101_r6_processing_csv": "清洗筛选矢量并按字段模板导出",
    "qgis_stable101_r42_cn_overlay_preprocess": "统一坐标系并叠加子流域、土地覆盖和土壤",
    "qgis_stable101_r9_soil_fix_clip": "修复并裁剪土壤面",
    "qgis_stable101_r10_basin_overlay": "将土壤图层叠加到流域范围",
    "qgis_stable101_r11_soil_postprocess": "修复裁剪并重投影土壤数据",
    "qgis_stable101_r13_classification_polygonize": "重分类栅格并转换为分类面",
    "qgis_stable101_r13_zonal_summary": "计算分区栅格统计",
    "qgis_stable101_r23_raster_preprocess": "对齐栅格并填补无数据区域",
    "qgis_stable101_r23_vector_mask": "栅格化矢量范围并裁剪栅格",
    "qgis_stable101_r24_vector_mask": "缓冲裁剪矢量并生成栅格掩膜",
    "qgis_stable101_r24_raster_mask": "对齐栅格并计算机会掩膜",
    "qgis_stable101_r29_dem_baseline": "基于高程基准计算并裁剪高度差栅格",
    "qgis_stable101_r29_polygon_baseline": "基于面基准计算并裁剪高度差栅格",
    "qgis_stable101_r34_fix_geometries": "修复矢量几何",
    "qgis_stable101_r34_singleparts": "将多部件要素拆分为单部件",
    "qgis_stable101_r34_clip": "按掩膜范围裁剪矢量",
    "qgis_stable101_r34_extract_expression": "按表达式筛选矢量要素",
    "qgis_stable101_r36_watershed_outputs": "提取流域出口、河网和流域面",
    "qgis_stable101_r37_web_vector_fix": "修复下载矢量的几何",
    "qgis_stable101_r37_protected_sites_merge": "修复并合并保护地矢量",
    "qgis_stable101_r38_complete_measure": "修复测量结果几何",
    "qgis_stable101_r38_blocks_selection": "修复选中街区的几何",
    "qgis_stable101_r38_registered_selection": "修复选中登记要素的几何",
    "qgis_stable101_r38_owner_layers": "分别修复街区和权属图层几何",
    "qgis_stable101_r40_dissolve_overlap": "按控制属性融合矢量要素",
    "qgis_stable101_r40_priority_stack": "按优先级消除重叠并合并土地利用图层",
    "qgis_stable101_r48_protected_join": "重投影保护区并连接建筑属性",
    "qgis_stable101_r48_overlap_groups": "计算建筑自相交关系",
}

OPERATOR_PHRASES = {
    "native:reprojectlayer": "将输入图层重投影到目标坐标系",
    "gdal:rasterize": "按指定字段和像元设置将矢量栅格化",
    "gdal:cliprasterbyextent": "按给定范围裁剪栅格",
    "native:fixgeometries": "修复无效矢量几何",
    "native:extractbyattribute": "按属性条件筛选要素",
    "native:refactorfields": "按字段模板重构属性表",
    "native:savefeatures": "保存处理后的矢量要素",
    "native:intersection": "计算输入图层的空间相交结果",
    "native:clip": "按掩膜范围裁剪矢量要素",
    "native:reclassifybytable": "按重分类表转换栅格类别",
    "gdal:polygonize": "将分类栅格转换为矢量面",
    "native:zonalstatisticsfb": "计算分区范围内的栅格统计量",
    "gdal:warpreproject": "将栅格重投影并对齐到目标网格",
    "native:fillnodata": "填补栅格中的无数据区域",
    "gdal:cliprasterbymasklayer": "使用掩膜图层裁剪栅格",
    "native:buffer": "按给定距离创建缓冲区",
    "gdal:rastercalculator": "根据输入栅格表达式计算新栅格",
    "native:multiparttosingleparts": "将多部件要素拆分为单部件要素",
    "native:extractbyexpression": "按表达式筛选矢量要素",
    "grass7:r.watershed": "从高程栅格计算汇流和流域分析结果",
    "grass7:r.water.outlet": "按出口位置提取上游流域",
    "grass7:r.to.vect": "将栅格结果转换为矢量要素",
    "native:mergevectorlayers": "合并结构兼容的矢量图层",
    "native:dissolve": "融合指定范围内的矢量要素",
    "native:difference": "从当前图层中扣除更高优先级范围",
    "native:removenullgeometries": "移除空几何要素",
    "native:union": "计算图层联合并保留叠加边界",
    "native:joinattributesbylocation": "按空间位置连接属性",
    "native:multiintersection": "计算多个图层之间的相交关系",
}

DESCRIPTION_OVERRIDES = {
    "qgis_stable101_r3_chip_pair_dag": (
        "将标注矢量重投影到目标坐标系并栅格化为掩膜，随后按同一范围分别裁剪原始影像和掩膜栅格，输出配对的影像切片与标签切片。"
    ),
    "qgis_stable101_r6_processing_csv": (
        "先修复输入矢量几何；若设置筛选字段则可选地按属性条件筛选要素，若目标坐标系不同则可选地重投影；随后按两个字段模板依次重构属性，并保存整理后的矢量结果。"
    ),
    "qgis_stable101_r42_cn_overlay_preprocess": (
        "必要时分别将子流域、土地覆盖和土壤图层重投影到共同坐标系，先相交土地覆盖与土壤图层，再将结果与子流域图层相交，输出三类属性的组合图层。"
    ),
    "qgis_stable101_r9_soil_fix_clip": (
        "修复已构建土壤面的无效几何，再按目标范围裁剪，输出范围内的土壤面。"
    ),
    "qgis_stable101_r10_basin_overlay": (
        "必要时将流域范围重投影到 WGS84，再与已获取的土壤图层相交，输出流域范围内的土壤要素。"
    ),
    "qgis_stable101_r11_soil_postprocess": (
        "先修复土壤面几何并按研究区裁剪，再将裁剪结果重投影到目标图层坐标系，最后再次修复几何。"
    ),
    "qgis_stable101_r13_zonal_summary": (
        "以分区边界和需求指数栅格为输入，计算各分区的平均值、中位数、最小值和最大值。"
    ),
    "qgis_stable101_r24_vector_mask": (
        "在点要素模式下先按给定距离创建缓冲区，其他矢量模式直接使用原要素；随后按当前区域裁剪，并将裁剪结果栅格化为掩膜。"
    ),
    "qgis_stable101_r24_raster_mask": (
        "将输入栅格重投影并裁剪到目标网格，再通过栅格计算把有效像元设为 1、无数据像元设为 0，输出二值机会掩膜。"
    ),
    "qgis_stable101_r29_dem_baseline": (
        "将基准高程栅格重投影并对齐到表面高程网格，计算表面高程减去基准高程，再按目标面掩膜裁剪高度差栅格。"
    ),
    "qgis_stable101_r29_polygon_baseline": (
        "按面要素的基准高程字段生成基准栅格，计算表面高程减去基准高程，再按目标面掩膜裁剪高度差栅格。"
    ),
    "qgis_stable101_r36_watershed_outputs": (
        "从高程栅格计算汇流结果，按指定出口提取上游流域，并把河网和流域栅格转换为矢量；修复生成几何后，分别按目标范围裁剪河网与流域面。"
    ),
    "qgis_stable101_r40_priority_stack": (
        "依照图层优先级逐层处理土地利用范围：必要时修复几何，从当前图层扣除已占用区域并移除空几何，再更新累计覆盖范围，最后合并保留下来的各层结果。"
    ),
    "qgis_stable101_r37_web_vector_fix": (
        "对 Web 服务返回且包含要素的矢量图层修复无效几何，输出可继续处理的下载矢量。"
    ),
    "qgis_stable101_r37_protected_sites_merge": (
        "对多个保护地 Web 服务返回的面图层逐个修复几何，再将修复后的图层集合合并为一个保护地矢量图层。"
    ),
    "qgis_stable101_r38_complete_measure": (
        "对用于计算边界测量值的选中地块先修复无效几何，输出供后续边界简化和测量字段计算使用的临时图层。"
    ),
    "qgis_stable101_r38_blocks_selection": (
        "当输入图层存在选中要素时，修复这些要素的无效几何，输出供后续街区文件生成使用的临时图层。"
    ),
    "qgis_stable101_r38_registered_selection": (
        "当输入图层存在选中要素时，修复这些要素的无效几何，输出供后续登记要素文件生成使用的临时图层。"
    ),
    "qgis_stable101_r38_owner_layers": (
        "分别修复权属人图层和占有人图层的无效几何，输出两个相互独立的临时清理图层。"
    ),
    "qgis_stable101_r40_dissolve_overlap": (
        "按控制属性融合输入矢量要素；若融合结果为空，则保留原输入图层。"
    ),
    "qgis_stable101_r48_protected_join": (
        "将保护区图层重投影到 EPSG:2154，再按相交关系把保护区属性连接到建筑图层，输出包含空间匹配字段的建筑图层。"
    ),
    "qgis_stable101_r48_overlap_groups": (
        "对建筑图层执行自相交并保留不同要素之间的相交关系，输出供后续重叠分组和几何合并使用的中间图层。"
    ),
}


@dataclass(frozen=True)
class ReviewResult:
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _generic_description(row: dict[str, Any]) -> str:
    optional = set(row.get("optional_operator_ordinals") or [])
    steps = []
    for ordinal, operator_id in enumerate(row["operator_sequence"]):
        phrase = OPERATOR_PHRASES[operator_id]
        if ordinal in optional:
            phrase = f"可选地{phrase}"
        steps.append(phrase)
    return "；随后".join(steps) + "，输出该局部子流程的处理结果。"


def _unmapped_operator_ids(row: dict[str, Any]) -> list[str]:
    return sorted(
        {
            operator_id
            for operator_id, l3_code, token_id in zip(
                row["operator_sequence"],
                row["l3_code_sequence"],
                row["l3_token_ids"],
            )
            if l3_code is None or token_id is None
        }
    )


def _expansion_snippet(row: dict[str, Any]) -> str:
    line_numbers = row["source_span"].get("expansion_call_lines") or []
    if not line_numbers:
        return ""
    source_path = Path(row["source_path"])
    if _sha256(source_path) != row["source_sha256"]:
        raise ValueError(f"source SHA256 mismatch for {row['unit_id']}")
    lines = source_path.read_text(encoding="utf-8").splitlines()
    blocks = []
    for line_number in line_numbers:
        start = max(1, int(line_number) - 1)
        end = min(len(lines), int(line_number) + 1)
        blocks.append(
            "\n".join(
                f"{current:4} | {lines[current - 1]}"
                for current in range(start, end + 1)
            )
        )
    return "\n...\n".join(blocks)


def build_review_rows(recovered_jsonl: Path) -> ReviewResult:
    recovered_rows = _load_jsonl(recovered_jsonl)
    rows: list[dict[str, Any]] = []
    for source in recovered_rows:
        unit_id = source["unit_id"]
        if unit_id not in TASK_NAMES:
            raise ValueError(f"missing deterministic task name for {unit_id}")
        missing_phrases = [
            operator_id
            for operator_id in source["operator_sequence"]
            if operator_id not in OPERATOR_PHRASES
        ]
        if missing_phrases:
            raise ValueError(f"missing operator phrases for {unit_id}: {missing_phrases}")

        unmapped = _unmapped_operator_ids(source)
        row = dict(source)
        row.update(
            {
                "draft_task_name": TASK_NAMES[unit_id],
                "draft_task_description": DESCRIPTION_OVERRIDES.get(
                    unit_id, _generic_description(source)
                ),
                "expansion_evidence_snippet": _expansion_snippet(source),
                "description_policy": "deterministic_semantic_template_v1",
                "unmapped_operator_ids": unmapped,
                "mapping_review_required": bool(unmapped),
                "review_eligible": not unmapped,
                "review_status": "pending_human_review",
                "training_admission": "not_granted",
                "validation_eligible": False,
                "test_eligible": False,
            }
        )
        row.update({field: "" for field in HUMAN_FIELDS})
        rows.append(row)

    if len(rows) != 29 or len({row["unit_id"] for row in rows}) != 29:
        raise ValueError("expected exactly 29 unique recovery review rows")
    counts = Counter(row["review_index"] for row in rows)
    summary = {
        "schema": "gis_recommend.qgis_stable101_recovery_review_summary.v1",
        "counts": {
            "rows": len(rows),
            "review_eligible": sum(row["review_eligible"] for row in rows),
            "mapping_review_required": sum(
                row["mapping_review_required"] for row in rows
            ),
            "source_review_indices": len(counts),
            "pending_human_review": sum(
                row["review_status"] == "pending_human_review" for row in rows
            ),
        },
        "decision": {
            "description_policy": "deterministic_semantic_template_v1",
            "llm_called": False,
            "training_admission": "not_granted",
            "next_gate": "human boundary, dependency, and task-text fidelity adjudication",
        },
    }
    return ReviewResult(rows=rows, summary=summary)


def _atomic_write(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding=encoding, newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def write_outputs(
    result: ReviewResult, output_dir: Path, recovered_jsonl: Path
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    csv_path = output_dir / "recovery_review_29_v1.csv"
    jsonl_path = output_dir / "recovery_review_29_v1.jsonl"
    summary_path = output_dir / "recovery_review_29_summary_v1.json"
    hash_path = output_dir / "recovery_review_29_hashes_v1.json"

    columns = list(result.rows[0])
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    writer.writerows(
        {key: _csv_value(value) for key, value in row.items()} for row in result.rows
    )
    _atomic_write(csv_path, buffer.getvalue(), encoding="utf-8-sig")
    _atomic_write(
        jsonl_path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in result.rows
        ),
    )
    _atomic_write(
        summary_path,
        json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            recovered_jsonl.name: {
                "path": str(recovered_jsonl),
                "sha256": _sha256(recovered_jsonl),
            }
        },
        "artifacts": {
            path.name: {
                "path": str(path),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in (csv_path, jsonl_path, summary_path)
        },
    }
    _atomic_write(
        hash_path,
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return {
        "csv": csv_path,
        "jsonl": jsonl_path,
        "summary": summary_path,
        "hash_ledger": hash_path,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recovered-jsonl", type=Path, default=DEFAULT_RECOVERED)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    result = build_review_rows(args.recovered_jsonl)
    return write_outputs(result, args.output_dir, args.recovered_jsonl)


if __name__ == "__main__":
    main()
