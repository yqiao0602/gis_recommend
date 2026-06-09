# -*- coding: utf-8 -*-
"""
Demo cases for weekly report — run a few example GIS queries through the full pipeline.
"""

import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.pipelines.interactive_system import InteractiveQGISSystem


DEMO_QUERIES = [
    "Land cover classification using satellite imagery",
    "Calculate NDVI from Landsat or Sentinel imagery to monitor vegetation health",
    "Map flood extent using SAR or optical satellite data after a flood event",
    "Monitor urban expansion over time using multi-temporal satellite imagery",
    "Compute slope and aspect from a DEM for terrain analysis",
]


def main():
    print("=" * 70)
    print("GIS 算子推荐系统 — 演示案例")
    print("=" * 70)

    system = InteractiveQGISSystem()

    results = []
    for i, query in enumerate(DEMO_QUERIES, 1):
        print(f"\n{'#' * 70}")
        print(f"# 案例 {i}: {query}")
        print(f"{'#' * 70}")

        try:
            result = system.process_user_query(query)
            results.append({
                "query": query,
                "success": True,
                "task_type": result.get("task_type", ""),
                "l3_sequence": result.get("l3_sequence", []),
                "qgis_chain": result.get("qgis_chain", []),
                "score": result.get("score"),
                "confidence": result.get("confidence"),
                "validation": result.get("validation", {}),
            })
        except Exception as e:
            print(f"  [ERROR] {e}")
            results.append({"query": query, "success": False, "error": str(e)})

    # Print summary
    print("\n" + "=" * 70)
    print("案例汇总")
    print("=" * 70)
    for i, r in enumerate(results, 1):
        print(f"\n案例 {i}: {r['query']}")
        if r["success"]:
            print(f"  任务类型: {r['task_type']}")
            print(f"  L3 序列: {' → '.join(r.get('l3_sequence', []))}")
            chain = r.get("qgis_chain", [])
            if chain:
                for j, op in enumerate(chain, 1):
                    print(f"    Step {j}: {op}")
            print(f"  置信度: {r.get('confidence', 'N/A')}")
        else:
            print(f"  失败: {r.get('error', 'unknown')}")

    # Save results
    out_path = PROJECT_ROOT / "outputs" / "demo_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到: {out_path}")

    system.close()


if __name__ == "__main__":
    main()
