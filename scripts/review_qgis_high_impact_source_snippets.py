"""Review raw QGIS source snippets for high-impact blocker operators.

This script is intentionally read-only for source corpora. It joins the QGIS
layered unique-content index with the corpus manifest, selects a few
deduplicated source files per operator, and extracts AST-proven
``processing.run*`` call snippets.
"""

from __future__ import annotations

import argparse
import ast
import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any


TARGET_OPERATORS = [
    "native:reprojectlayer",
    "native:fixgeometries",
    "gdal:polygonize",
    "gdal:rasterize",
    "native:createspatialindex",
    "native:saveselectedfeatures",
]

PROPOSALS = {
    "native:reprojectlayer": ("L3_01_10_01", "Project/Reproject", "conservative"),
    "native:fixgeometries": ("L3_01_05_02", "Repair Geometry", "conservative"),
    "gdal:polygonize": ("L3_01_09_03", "Raster-Vector Conversion", "conservative"),
    "gdal:rasterize": ("L3_01_09_03", "Raster-Vector Conversion", "conservative"),
    "native:createspatialindex": ("L3_01_07_01", "Add Spatial Index", "support_boundary"),
    "native:saveselectedfeatures": (
        "L3_07_04_01",
        "Export To Shapefile",
        "export_boundary",
    ),
}

CALL_VERDICTS = {
    "native:reprojectlayer": "accept_mapping_after_authority",
    "native:fixgeometries": "accept_mapping_after_authority",
    "gdal:polygonize": "accept_mapping_after_authority",
    "gdal:rasterize": "accept_mapping_after_authority",
    "native:createspatialindex": "defer_training_support_step",
    "native:saveselectedfeatures": "defer_training_export_boundary",
}

REASONS_ZH = {
    "native:reprojectlayer": "真实调用使用 INPUT/TARGET_CRS/OUTPUT，语义是把矢量图层转换到目标CRS。",
    "native:fixgeometries": "真实调用使用 INPUT/OUTPUT 或 METHOD/INPUT/OUTPUT，语义是修复无效几何并产生修复后图层。",
    "gdal:polygonize": "真实调用使用 INPUT/BAND/FIELD/OUTPUT，语义是把栅格像元区域转换为矢量多边形。",
    "gdal:rasterize": "真实调用使用 INPUT/FIELD或BURN/EXTENT/尺寸/OUTPUT，语义是把矢量几何烧录为栅格。",
    "native:createspatialindex": "真实调用通常只接 INPUT，作用是创建空间索引以加速后续查询；它支撑流程，但不是面向任务的分析输出。",
    "native:saveselectedfeatures": "真实调用把当前选择集写成新图层，OUTPUT 有时是 TEMPORARY_OUTPUT、有时是文件路径；不能稳定等同 shapefile 导出。",
}

LAYER_PRIORITY = {
    "explicit_processing_multistep_catalog_exact": 0,
    "explicit_processing_single_catalog_exact": 1,
    "explicit_processing_catalog_miss": 2,
    "processing_algorithm_implementation_or_custom": 3,
}


def jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def expr_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = expr_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def is_processing_func(node: ast.AST) -> bool:
    name = expr_name(node)
    return name in {
        "processing.run",
        "processing.runAndLoadResults",
        "processing.runalg",
    } or name.endswith((".processing.run", ".processing.runAndLoadResults"))


def key_repr(node: ast.AST | None) -> str:
    if isinstance(node, ast.Constant):
        return str(node.value)
    if isinstance(node, ast.Name):
        return node.id
    return type(node).__name__


def value_repr(node: ast.AST) -> str:
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return expr_name(node)
    if isinstance(node, ast.Subscript):
        return f"{expr_name(node.value)}[...]"
    if isinstance(node, ast.Call):
        return f"{expr_name(node.func)}(...)"
    if isinstance(node, ast.Dict):
        return "{...}"
    if isinstance(node, ast.List):
        return "[...]"
    if isinstance(node, ast.Tuple):
        return "(...)"
    return type(node).__name__


def target_repr(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return expr_name(node)
    if isinstance(node, ast.Subscript):
        return f"{expr_name(node.value)}[...]"
    if isinstance(node, ast.Tuple):
        return ",".join(target_repr(item) for item in node.elts)
    return type(node).__name__


def output_role(call: ast.Call) -> dict[str, Any]:
    parent = getattr(call, "parent", None)
    subscript_key = None
    if isinstance(parent, ast.Subscript):
        slice_node = parent.slice
        if isinstance(slice_node, ast.Constant):
            subscript_key = slice_node.value
        parent = getattr(parent, "parent", None)

    if isinstance(parent, ast.Assign):
        return {
            "role": "assigned",
            "target": ",".join(target_repr(target) for target in parent.targets),
            "subscript": subscript_key,
        }
    if isinstance(parent, ast.AnnAssign):
        return {
            "role": "assigned",
            "target": target_repr(parent.target),
            "subscript": subscript_key,
        }
    if isinstance(parent, ast.Return):
        return {"role": "returned", "target": "return", "subscript": subscript_key}
    if isinstance(parent, ast.Expr):
        return {
            "role": "side_effect_or_unassigned",
            "target": "expr",
            "subscript": subscript_key,
        }
    if isinstance(parent, ast.Dict):
        return {
            "role": "nested_in_param_dict",
            "target": "dict_value",
            "subscript": subscript_key,
        }
    if isinstance(parent, ast.Call):
        return {
            "role": "nested_in_call",
            "target": expr_name(parent.func),
            "subscript": subscript_key,
        }
    return {
        "role": type(parent).__name__ if parent else "unknown",
        "target": "",
        "subscript": subscript_key,
    }


def enclosing_scope(node: ast.AST) -> list[str]:
    scopes: list[str] = []
    current = node
    while getattr(current, "parent", None) is not None:
        current = current.parent
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            scopes.append(f"def {current.name}")
        elif isinstance(current, ast.ClassDef):
            scopes.append(f"class {current.name}")
    return list(reversed(scopes))


def extract_calls(path: Path, operator_id: str) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child.parent = node

    lines = text.splitlines()
    calls: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not is_processing_func(node.func):
            continue
        if not node.args:
            continue
        first_arg = node.args[0]
        value = None
        if isinstance(first_arg, ast.Constant):
            value = first_arg.value
        if value != operator_id:
            continue

        params: list[dict[str, str]] = []
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Dict):
            params = [
                {"key": key_repr(key), "value": value_repr(val)}
                for key, val in zip(node.args[1].keys, node.args[1].values)
            ]

        line_start = getattr(node, "lineno", 1)
        line_end = getattr(node, "end_lineno", line_start)
        snippet_start = max(1, line_start - 3)
        snippet_end = min(len(lines), line_end + 3)
        snippet = "\n".join(
            f"{line_no:04d}: {lines[line_no - 1]}"
            for line_no in range(snippet_start, snippet_end + 1)
        )
        calls.append(
            {
                "line_start": line_start,
                "line_end": line_end,
                "call_func": expr_name(node.func),
                "param_keys": [param["key"] for param in params],
                "param_preview": params[:20],
                "output_role": output_role(node),
                "enclosing_scope": enclosing_scope(node),
                "snippet": snippet,
            }
        )
    return calls


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect_evidence(
    layered_path: Path,
    manifest_path: Path,
    samples_per_operator: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidate_rows: list[dict[str, Any]] = []
    target_hashes: set[str] = set()
    counts: collections.Counter[str] = collections.Counter()
    layer_counts: dict[str, collections.Counter[str]] = collections.defaultdict(
        collections.Counter
    )

    with layered_path.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            operator_ids = row.get("literal_operator_ids") or []
            hits = [op for op in TARGET_OPERATORS if op in operator_ids]
            if not hits:
                continue
            row["_hit_ops"] = hits
            candidate_rows.append(row)
            target_hashes.add(row["content_sha256"])
            for op in hits:
                counts[op] += 1
                layer_counts[op][row.get("primary_layer")] += 1

    paths_by_hash: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    with manifest_path.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            content_hash = row.get("content_sha256")
            if content_hash in target_hashes and row.get("source_path"):
                paths_by_hash[content_hash].append(row)

    rows_by_operator: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in candidate_rows:
        for op in row["_hit_ops"]:
            rows_by_operator[op].append(row)

    selected: list[dict[str, Any]] = []
    per_operator: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    used_hashes: dict[str, set[str]] = collections.defaultdict(set)
    used_roots: dict[str, set[str]] = collections.defaultdict(set)

    for op in TARGET_OPERATORS:
        rows = sorted(
            rows_by_operator[op],
            key=lambda row: (
                LAYER_PRIORITY.get(row.get("primary_layer"), 9),
                row.get("duplicate_count", 0),
                row["content_sha256"],
            ),
        )
        for pass_no in (0, 1, 2):
            for row in rows:
                if len(per_operator[op]) >= samples_per_operator:
                    break
                content_hash = row["content_sha256"]
                if content_hash in used_hashes[op]:
                    continue
                sources = paths_by_hash.get(content_hash) or []
                canonical = row.get("canonical_source") or {}
                sources = sorted(
                    sources,
                    key=lambda source: (
                        0
                        if source.get("source_root_id")
                        == canonical.get("source_root_id")
                        and source.get("relative_path")
                        == canonical.get("relative_path")
                        else 1,
                        source.get("source_root_id") or "",
                        source.get("relative_path") or "",
                    ),
                )
                for source in sources:
                    root_id = source.get("source_root_id") or "unknown"
                    if pass_no == 0 and root_id in used_roots[op]:
                        continue
                    source_path = source.get("source_path")
                    if not source_path or not os.path.exists(source_path):
                        continue
                    calls = extract_calls(Path(source_path), op)
                    if not calls:
                        continue
                    l3_code, l3_name, scenario = PROPOSALS[op]
                    item = {
                        "operator_id": op,
                        "candidate_l3_code": l3_code,
                        "candidate_l3_name": l3_name,
                        "scenario": scenario,
                        "source_review_verdict": CALL_VERDICTS[op],
                        "review_note": REASONS_ZH[op],
                        "content_sha256": content_hash,
                        "duplicate_count": row.get("duplicate_count"),
                        "primary_layer": row.get("primary_layer"),
                        "broad_bucket": row.get("broad_bucket"),
                        "source_root_id": root_id,
                        "relative_path": source.get("relative_path"),
                        "source_path": source_path,
                        "observed_source_count_for_hash": len(sources),
                        "literal_operator_ids": row.get("literal_operator_ids"),
                        "active_processing_call": True,
                        "call": calls[0],
                    }
                    selected.append(item)
                    per_operator[op].append(item)
                    used_hashes[op].add(content_hash)
                    used_roots[op].add(root_id)
                    break

    summary = {
        "schema": "qgis_high_impact_6ops_source_snippet_review.v1",
        "date": "2026-07-24",
        "source_roots": [
            "/home/yll",
            str(layered_path.parent),
            str(manifest_path.parent),
        ],
        "target_operators": TARGET_OPERATORS,
        "unique_layer_hits": dict(counts),
        "layer_counts": {
            op: dict(layer_counts[op]) for op in TARGET_OPERATORS
        },
        "selected_per_operator": {
            op: len(per_operator[op]) for op in TARGET_OPERATORS
        },
        "selected_total": len(selected),
    }
    return selected, summary


def write_markdown(path: Path, selected: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    per_operator: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for item in selected:
        per_operator[item["operator_id"]].append(item)

    lines: list[str] = []
    lines.append("# QGIS 6个高影响阻塞算子源码片段复核（2026-07-24）")
    lines.append("")
    lines.append(
        "本报告是 `/home/yll` 服务器真实源码复核，不修改 stable-94/stable-98 authority，不生成训练集，不训练模型。"
    )
    lines.append("")
    lines.append("## 复核口径")
    lines.append("")
    lines.append("- 服务器：`qy@10.191.2.38`。")
    lines.append(
        "- 源码根：`/home/yll`，回溯索引：`/home/qy/system_redesign/outputs_v2/qgis_corpus_screening/nine_sources_canonical_v2`。"
    )
    lines.append(
        "- 抽样：每个目标算子 3 个 `content_sha256` 去重源码样本，优先 `explicit_processing_multistep_catalog_exact` 层。"
    )
    lines.append(
        "- 必须条件：源文件可读、AST 可解析、存在字面量 `processing.run*()` 且首参精确等于目标 operator ID。"
    )
    lines.append("- 复核字段：参数语义、输出角色、是否只是 support/export 边界、重复/镜像情况。")
    lines.append("")
    lines.append("## 总体结论")
    lines.append("")
    lines.append("| 算子 | 样本 | 源码层唯一命中 | 结论 | 训练准入建议 |")
    lines.append("|---|---:|---:|---|---|")
    for op in TARGET_OPERATORS:
        l3_code, l3_name, scenario = PROPOSALS[op]
        if scenario == "conservative":
            conclusion = f"真实源码支持 `{l3_code}` {l3_name} 映射"
            admission = "通过正式 authority 后可进 core 候选"
        elif op == "native:createspatialindex":
            conclusion = f"真实源码支持 `{l3_code}` {l3_name}，但多为性能支撑步骤"
            admission = "继续 deferred，不单独作为训练目标"
        else:
            conclusion = (
                f"真实源码支持“保存选择集为新图层”，但不稳定等同 `{l3_code}` shapefile 导出"
            )
            admission = "继续 deferred；需按 OUTPUT 类型细分"
        lines.append(
            f"| `{op}` | {len(per_operator[op])} | "
            f"{summary['unique_layer_hits'].get(op, 0)} | {conclusion} | {admission} |"
        )

    lines.append("")
    lines.append("## 分算子复核")
    for op in TARGET_OPERATORS:
        l3_code, l3_name, scenario = PROPOSALS[op]
        lines.append("")
        lines.append(f"### `{op}` -> `{l3_code}` {l3_name}")
        lines.append("")
        lines.append(f"- 草案场景：`{scenario}`。")
        lines.append(f"- 复核判断：`{CALL_VERDICTS[op]}`。")
        lines.append(f"- 依据：{REASONS_ZH[op]}")
        lines.append("")
        for index, item in enumerate(per_operator[op], 1):
            call = item["call"]
            role = call["output_role"]
            keys = ", ".join(f"`{key}`" for key in call.get("param_keys", []))
            if not keys:
                keys = "无字面量参数键"
            scope = " / ".join(call.get("enclosing_scope") or [])
            lines.append(f"**样本 {index}**")
            lines.append("")
            lines.append(f"- 路径：`{item['source_path']}`")
            lines.append(
                f"- source_root：`{item['source_root_id']}`；"
                f"primary_layer：`{item['primary_layer']}`；"
                f"duplicate_count：`{item['duplicate_count']}`；"
                f"hash：`{item['content_sha256'][:12]}...`"
            )
            lines.append(
                f"- 调用：`{call['call_func']}` 第 {call['line_start']}-{call['line_end']} 行；"
                f"scope：`{scope}`"
            )
            lines.append(f"- 参数键：{keys}")
            lines.append(
                f"- 输出角色：`{role.get('role')}` target=`{role.get('target')}` "
                f"subscript=`{role.get('subscript')}`"
            )
            lines.append("")
            lines.append("```python")
            lines.append(call["snippet"])
            lines.append("```")
            lines.append("")

    lines.append("## 后续处理")
    lines.append("")
    lines.append(
        "- `native:reprojectlayer`、`native:fixgeometries`、`gdal:polygonize`、`gdal:rasterize`：可以进入正式 stable-N 扩展草案，但仍需 taxonomy authority 明确批准。"
    )
    lines.append(
        "- `native:createspatialindex`：保留为 support/performance 步骤，可用于链完整性，但不建议作为自然语言任务训练目标。"
    )
    lines.append(
        "- `native:saveselectedfeatures`：先按 `OUTPUT` 为临时层/文件路径/shapefile 的情况拆分，未拆分前不并入 `Export To Shapefile` 训练目标。"
    )
    lines.append("- 本报告只覆盖抽样源码片段复核；不是全量 precision/recall 结论。")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--layered", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--samples-per-operator", type=int, default=3)
    parser.add_argument("--date", default="2026-07-24")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    selected, summary = collect_evidence(
        args.layered,
        args.manifest,
        args.samples_per_operator,
    )
    summary["date"] = args.date

    jsonl_path = args.out_dir / "qgis_high_impact_6ops_source_snippet_review_2026-07-24.jsonl"
    summary_path = (
        args.out_dir / "qgis_high_impact_6ops_source_snippet_review_2026-07-24.summary.json"
    )
    markdown_path = (
        args.out_dir / "qgis_high_impact_6ops_source_snippet_review_2026-07-24.md"
    )

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for item in selected:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    write_markdown(markdown_path, selected, summary)

    summary["artifact_sha256"] = {
        jsonl_path.name: sha256_file(jsonl_path),
        markdown_path.name: sha256_file(markdown_path),
    }
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
